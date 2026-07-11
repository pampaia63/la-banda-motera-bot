import os, requests, base64, time, re
from datetime import datetime, timedelta
import markdown2

WP_URL = os.environ["WP_URL"].rstrip("/")
WP_USER = os.environ["WP_USER"]
WP_APP_PASS = os.environ["WP_APP_PASS"]
EXA_API_KEY = os.environ.get("EXA_API_KEY", "")

BROWSER_UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"

session = requests.Session()

def get_auth_header():
    t = base64.b64encode(f"{WP_USER}:{WP_APP_PASS}".encode()).decode()
    return {
        "Authorization": f"Basic {t}",
        "Content-Type": "application/json",
        "User-Agent": BROWSER_UA,
        "Accept": "application/json",
    }

def request_with_retry(method, url, headers, json_data=None, max_retries=4):
    for intento in range(1, max_retries + 1):
        try:
            if method == "GET":
                r = session.get(url, headers=headers, timeout=30)
            else:
                r = session.post(url, headers=headers, json=json_data, timeout=30)
            if r.status_code in (200, 201):
                return r
            if "aes.js" in r.text or "__test" in r.text.lower():
                time.sleep(intento * 3)
                continue
            return r
        except Exception as e:
            time.sleep(intento * 4)
    return None

def get_or_create(name, headers, ep):
    slug = name.lower().replace(" ", "-")
    r = request_with_retry("GET", f"{WP_URL}/wp-json/wp/v2/{ep}?slug={slug}", headers)
    if r is None:
        return 0
    try:
        d = r.json()
        if d and isinstance(d, list) and len(d) > 0:
            return d[0]["id"]
    except Exception:
        pass
    r2 = request_with_retry("POST", f"{WP_URL}/wp-json/wp/v2/{ep}", headers, {"name": name, "slug": slug})
    if r2 is None:
        return 0
    try:
        return r2.json().get("id", 0)
    except Exception:
        return 0

def buscar_imagen_real(titulo, imagen_prompt=None):
    """
    Busca una imagen real de la moto usando Exa.
    Prioriza páginas oficiales de marcas y revistas especializadas.
    Devuelve el contenido binario de la imagen o None si falla.
    """
    try:
        # Construir query de búsqueda específica para la moto
        query = imagen_prompt or titulo
        # Extraer marca y modelo para una búsqueda más precisa
        query_img = f"{query[:80]} official press photo motorcycle"

        print(f"  [Imagen] Buscando imagen real: {query[:60]}...")

        # Fuentes prioritarias: páginas oficiales y revistas especializadas
        fuentes_prioritarias = [
            "ducati.com", "ktm.com", "yamaha-motor.eu", "honda.com",
            "kawasaki.com", "bmw-motorrad.com", "aprilia.com", "triumph.co.uk",
            "benelli.com", "cfmoto.com", "royalenfield.com", "husqvarna-motorcycles.com",
            "moto-morini.com", "rieju.com", "sherco.com", "beta-motor.it",
            "revzilla.com", "motociclismo.es", "motoforum.pl", "motorrad.de",
            "cycleworld.com", "visordown.com", "bennetts.co.uk", "mcnews.com.au",
            "motosnet.com", "motociclismo.com.ar", "motolatino.com"
        ]

        r = requests.post(
            "https://api.exa.ai/search",
            headers={"x-api-key": EXA_API_KEY, "Content-Type": "application/json"},
            json={
                "query": query_img,
                "numResults": 8,
                "type": "neural",
                "includeDomains": fuentes_prioritarias,
                "contents": {
                    "text": {"maxCharacters": 100},
                    "highlights": {"numSentences": 1}
                },
            },
            timeout=30
        )

        results = r.json().get("results", [])
        print(f"  [Imagen] Exa encontró {len(results)} resultados en fuentes prioritarias")

        # Si no hay resultados con fuentes prioritarias, buscar sin restricción
        if not results:
            print(f"  [Imagen] Sin resultados en fuentes prioritarias, buscando en general...")
            r2 = requests.post(
                "https://api.exa.ai/search",
                headers={"x-api-key": EXA_API_KEY, "Content-Type": "application/json"},
                json={
                    "query": query_img,
                    "numResults": 5,
                    "type": "neural",
                    "contents": {"text": {"maxCharacters": 100}},
                },
                timeout=30
            )
            results = r2.json().get("results", [])

        # Intentar descargar la imagen de Open Graph de cada resultado
        headers_browser = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/125.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        }

        for result in results:
            url_pagina = result.get("url", "")
            if not url_pagina:
                continue

            try:
                # Intentar obtener la imagen OG de la página
                resp = requests.get(url_pagina, headers=headers_browser, timeout=15)
                if resp.status_code != 200:
                    print(f"  [Imagen] {url_pagina[:50]} → HTTP {resp.status_code}, descartado")
                    continue

                html = resp.text
                if len(html) < 500:
                    print(f"  [Imagen] {url_pagina[:50]} → respuesta muy corta ({len(html)} chars), posible bloqueo")
                    continue

                # Buscar og:image en el HTML
                import re
                og_patterns = [
                    r'<meta[^>]+property="og:image"[^>]+content="([^"]+)"',
                    r"<meta[^>]+property='og:image'[^>]+content='([^']+)'",
                    r'<meta[^>]+content="([^"]+)"[^>]+property="og:image"',
                    r'<meta[^>]+name="twitter:image"[^>]+content="([^"]+)"',
                ]

                img_url = None
                for pattern in og_patterns:
                    match = re.search(pattern, html, re.IGNORECASE)
                    if match:
                        img_url = match.group(1).strip()
                        break

                if not img_url:
                    continue

                # Asegurarse de que la URL es absoluta
                if img_url.startswith('//'):
                    img_url = 'https:' + img_url
                elif img_url.startswith('/'):
                    from urllib.parse import urlparse
                    parsed = urlparse(url_pagina)
                    img_url = f"{parsed.scheme}://{parsed.netloc}{img_url}"

                # Verificar que parece una imagen real
                if not any(ext in img_url.lower() for ext in ['.jpg', '.jpeg', '.png', '.webp']):
                    if 'image' not in img_url.lower() and 'photo' not in img_url.lower() and 'media' not in img_url.lower():
                        continue

                print(f"  [Imagen] Descargando desde: {img_url[:80]}...")
                img_resp = requests.get(img_url, headers=headers_browser, timeout=20)

                if img_resp.status_code == 200 and len(img_resp.content) > 20000:
                    # Verificar que es una imagen válida
                    content_type = img_resp.headers.get('Content-Type', '')
                    if 'image' in content_type or img_url.lower().endswith(('.jpg','.jpeg','.png','.webp')):
                        print(f"  [Imagen] ✓ Imagen real encontrada: {len(img_resp.content)//1024}KB desde {url_pagina[:50]}")
                        return img_resp.content

            except Exception as e_inner:
                print(f"  [Imagen] Error con {url_pagina[:40]}: {e_inner}")
                continue

        # Fallback final: buscar en Wikimedia Commons (no bloquea bots, imagenes libres)
        print(f"  [Imagen] Sin suerte en {len(results)} resultados, probando Wikimedia Commons...")
        try:
            wiki_query = requests.utils.quote(query[:60])
            wiki_url = f"https://commons.wikimedia.org/w/api.php?action=query&list=search&srsearch={wiki_query}&srnamespace=6&format=json&srlimit=5"
            wiki_resp = requests.get(wiki_url, headers=headers_browser, timeout=15)
            wiki_data = wiki_resp.json()
            search_results = wiki_data.get("query", {}).get("search", [])

            for item in search_results:
                titulo_archivo = item.get("title", "")
                if not titulo_archivo.startswith("File:"):
                    continue
                # Obtener la URL directa de la imagen
                info_url = f"https://commons.wikimedia.org/w/api.php?action=query&titles={requests.utils.quote(titulo_archivo)}&prop=imageinfo&iiprop=url&format=json"
                info_resp = requests.get(info_url, headers=headers_browser, timeout=15)
                info_data = info_resp.json()
                pages = info_data.get("query", {}).get("pages", {})
                for page_id, page_data in pages.items():
                    imageinfo = page_data.get("imageinfo", [])
                    if imageinfo:
                        img_direct_url = imageinfo[0].get("url", "")
                        if img_direct_url and img_direct_url.lower().endswith(('.jpg', '.jpeg', '.png')):
                            img_resp = requests.get(img_direct_url, headers=headers_browser, timeout=20)
                            if img_resp.status_code == 200 and len(img_resp.content) > 20000:
                                print(f"  [Imagen] ✓ Encontrada en Wikimedia Commons: {titulo_archivo[:50]}")
                                return img_resp.content
        except Exception as e_wiki:
            print(f"  [Imagen] Error en Wikimedia fallback: {e_wiki}")

        print(f"  [Imagen] No se encontró imagen real para: {titulo[:50]} (probados {len(results)} resultados + Wikimedia)")
        return None

    except Exception as e:
        print(f"  [Imagen] Error general: {e}")
        return None

def insertar_imagenes_en_secciones(html_contenido, imagenes_secciones, headers):
    """
    Busca una imagen real para cada seccion indicada por el editor,
    la sube a WP y la inserta como <figure> despues del H2 correspondiente.
    """
    if not imagenes_secciones:
        return html_contenido

    import re as re_module

    for img_spec in imagenes_secciones:
        seccion_titulo = img_spec.get("seccion", "").strip()
        busqueda = img_spec.get("busqueda", "")
        if not seccion_titulo or not busqueda:
            continue

        try:
            # Buscar la imagen real para esta seccion especifica
            imagen_bytes = buscar_imagen_real(busqueda, busqueda)
            if not imagen_bytes:
                print(f"  [Imagen seccion] Sin imagen para: {seccion_titulo[:40]}")
                continue

            media_id = subir_imagen_wp(imagen_bytes, f"{seccion_titulo}-{busqueda[:30]}", headers)
            if not media_id:
                continue

            # Obtener la URL de la imagen recien subida
            media_resp = session.get(f"{WP_URL}/wp-json/wp/v2/media/{media_id}", headers=headers, timeout=15)
            img_url = media_resp.json().get("source_url", "") if media_resp.status_code == 200 else ""
            if not img_url:
                continue

            figure_html = f'<figure style="margin:24px 0;"><img src="{img_url}" alt="{seccion_titulo}" style="width:100%;border-radius:6px;" loading="lazy"/></figure>'

            # Buscar el H2 exacto (o el mas parecido) en el HTML y insertar la imagen justo despues de su parrafo siguiente
            # El H2 en HTML viene como <h2 id="...">Texto</h2> tras la conversion de markdown2
            pattern = re_module.compile(
                r'(<h2[^>]*>\s*' + re_module.escape(seccion_titulo) + r'\s*</h2>\s*<p>.*?</p>)',
                re_module.IGNORECASE | re_module.DOTALL
            )
            match = pattern.search(html_contenido)
            if match:
                html_contenido = html_contenido[:match.end()] + figure_html + html_contenido[match.end():]
                print(f"  [Imagen seccion] ✓ Insertada en: {seccion_titulo[:40]}")
            else:
                # Fallback: insertar justo despues del H2 si no se encontro el patron con parrafo
                pattern_simple = re_module.compile(
                    r'(<h2[^>]*>\s*' + re_module.escape(seccion_titulo) + r'\s*</h2>)',
                    re_module.IGNORECASE
                )
                match2 = pattern_simple.search(html_contenido)
                if match2:
                    html_contenido = html_contenido[:match2.end()] + figure_html + html_contenido[match2.end():]
                    print(f"  [Imagen seccion] ✓ Insertada (fallback) en: {seccion_titulo[:40]}")
                else:
                    print(f"  [Imagen seccion] ✗ No se encontro el H2: {seccion_titulo[:40]}")

        except Exception as e:
            print(f"  [Imagen seccion] Error procesando '{seccion_titulo[:30]}': {e}")
            continue

    return html_contenido

def subir_imagen_wp(imagen_bytes, titulo, headers):
    """
    Sube la imagen a la Media Library de WordPress y devuelve el media ID.
    """
    try:
        slug_titulo = re.sub(r'[^a-z0-9]+', '-', titulo.lower())[:50]
        filename = f"lbm-{slug_titulo}.jpg"

        upload_headers = {
            "Authorization": headers["Authorization"],
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Content-Type": "image/jpeg",
            "User-Agent": BROWSER_UA,
        }

        r = session.post(
            f"{WP_URL}/wp-json/wp/v2/media",
            headers=upload_headers,
            data=imagen_bytes,
            timeout=60
        )

        if r.status_code in (200, 201):
            media_id = r.json().get("id")
            print(f"  [Imagen] Subida a WP - media ID: {media_id}")
            return media_id
        else:
            print(f"  [Imagen] Error subiendo a WP: {r.status_code} - {r.text[:100]}")
            return None
    except Exception as e:
        print(f"  [Imagen] Error upload: {e}")
        return None

def build_youtube_block(yt):
    if not yt or not yt.get("url"):
        return ""
    url = yt["url"]
    marca = yt.get("marca", "")
    if marca:
        texto_cta = f"En el canal de Isaias Rider encontras videos reales de {marca} en ruta y off-road. Dale un vistazo antes de decidir."
    else:
        texto_cta = "Seguimos este tema en el canal de Isaias Rider con pruebas reales en ruta."

    return f"""
<div style="background:#1A1A18;border-left:4px solid #E8541E;padding:20px 24px;margin:32px 0;border-radius:6px;">
<p style="color:#F4F0E9;font-size:14px;margin:0 0 8px;text-transform:uppercase;letter-spacing:1px;font-weight:600;">En video</p>
<p style="color:#D8D2C6;margin:0 0 14px;line-height:1.5;">{texto_cta}</p>
<a href="{url}" target="_blank" rel="noopener" style="display:inline-block;background:#E8541E;color:#fff;padding:10px 20px;border-radius:4px;text-decoration:none;font-weight:600;font-size:14px;">Ver en YouTube</a>
</div>"""

def publicar(a):
    h = get_auth_header()

    # Generar imagen con IA
    media_id = None
    imagen_prompt = a.get("imagen_prompt") or a.get("titulo", "")
    imagen_bytes = buscar_imagen_real(a.get("titulo", ""), imagen_prompt)
    if imagen_bytes:
        media_id = subir_imagen_wp(imagen_bytes, a.get("titulo", ""), h)

    # Construir HTML
    contenido_md = a.get("contenido_md", "")
    yt_block = build_youtube_block(a.get("youtube"))
    html_contenido = markdown2.markdown(contenido_md, extras=["fenced-code-blocks", "tables", "header-ids"])

    # Insertar imagenes reales en cada seccion indicada por el editor
    imagenes_secciones = a.get("imagenes_secciones", [])
    if imagenes_secciones:
        print(f"  [Publisher] Insertando {len(imagenes_secciones)} imagenes de seccion...")
        html_contenido = insertar_imagenes_en_secciones(html_contenido, imagenes_secciones, h)

    html_final = html_contenido + yt_block
    bajada = a.get("bajada", "")

    # Tags y categoria
    tags = [get_or_create(t, h, "tags") for t in a.get("tags", [])]
    # Mapa de categorías: nombre (viejo o nuevo) → ID real en WordPress
    # IDs reales del WordPress de La Banda Motera (verificados 06/07/2026)
    CATEGORIA_IDS = {
        "Reviews":             10,
        "Nuevos Lanzamientos": 11,
        "Competición":         12,
        "Marcas":              13,
        "Comparativas":        14,
        "Historias Moteras":   15,
        "Mecánica":            56,
        "Mecanica":            56,
        # Fallbacks por si el editor usa nombres alternativos
        "Lanzamientos":        11,
        "Noticias":            11,
        "Historia":            15,
        "Cultura":             15,
        "Tecnica":             56,
        "Técnica":             56,
        "MotoGP":              12,
        "Adventure":           11,
        "Custom":              13,
    }
    cat_nombre = a.get("categoria", "Nuevos Lanzamientos")
    cat = CATEGORIA_IDS.get(cat_nombre, 11)  # default: Nuevos Lanzamientos
    print(f"  [Publisher] Categoría: '{cat_nombre}' → ID {cat}")

    # Usar fecha programada del main.py (1 artículo por día) o fallback mañana 10:00 AR
    fecha_programada = a.get("fecha_programada")
    if not fecha_programada:
        now = datetime.utcnow()
        fecha_programada = (now + timedelta(days=1)).replace(
            hour=13, minute=0, second=0, microsecond=0
        ).strftime("%Y-%m-%dT%H:%M:%S")

    titulo_pub = a.get("titulo", "Sin titulo")  # Título completo como H1
    seo_title = a.get("seo_title") or titulo_pub  # SEO title para Yoast

    # Autor ficticio: agregar meta de Yoast para SEO title y meta description
    meta_yoast = {
        "_yoast_wpseo_title": seo_title[:60],
        "_yoast_wpseo_metadesc": a.get("meta_description", "")[:155],
        "_yoast_wpseo_focuskw": (a.get("tags", [""])[0] if a.get("tags") else ""),
    }

    p = {
        "title": titulo_pub,
        "content": html_final,
        "excerpt": bajada,
        "slug": a.get("slug", ""),
        "status": "future",
        "date": fecha_programada,
        "meta": meta_yoast,
        "tags": [t for t in tags if t],
        "categories": [cat] if cat else [],
    }

    # Agregar imagen destacada si se subio
    if media_id:
        p["featured_media"] = media_id

    r = request_with_retry("POST", f"{WP_URL}/wp-json/wp/v2/posts", h, p)
    if r is None:
        print("  [Publisher] Sin respuesta tras reintentos")
        return {"ok": False, "error": "no response"}
    if r.status_code in (200, 201):
        post_data = r.json()
        link = post_data.get("link", "publicado")
        post_id = post_data.get("id", "?")
        autor = a.get("autor", "isaiasrider")
        img_status = f"img:{media_id}" if media_id else "sin-img"
        print(f"  [Publisher] OK: ***/?p={post_id} | Autor: {autor} | {img_status}")
        return {"ok": True, "url": link, "id": post_id}
    print(f"  [Publisher] Error {r.status_code}: {r.text[:200]}")
    return {"ok": False, "error": r.text[:200]}


def actualizar_home_portada():
    """
    Actualiza la página de portada (ID 141) con los últimos 3 posts
    publicados/programados de cada categoría.
    """
    h = get_auth_header()
    WP_API = f"{WP_URL}/wp-json/wp/v2"

    CATEGORIAS = [
        {"id": 10, "nombre": "Reviews",            "slug": "reviews"},
        {"id": 11, "nombre": "Nuevos Lanzamientos","slug": "nuevos-lanzamientos"},
        {"id": 14, "nombre": "Comparativas",       "slug": "comparativas"},
        {"id": 56, "nombre": "Mecánica",           "slug": "mecanica"},
    ]
    HOME_PAGE_ID = 20

    def get_posts_categoria(cat_id, num=3):
        """Obtiene los últimos N posts (publish o future) de una categoría con su imagen."""
        r = request_with_retry(
            "GET",
            f"{WP_API}/posts?categories={cat_id}&per_page={num}&status=publish,future&orderby=date&order=desc&_fields=id,title,excerpt,link,featured_media",
            h
        )
        if not r:
            return []
        posts = r.json() if r.status_code == 200 else []
        resultado = []
        for p in posts:
            img_url = ""
            if p.get("featured_media"):
                ri = request_with_retry("GET", f"{WP_API}/media/{p['featured_media']}?_fields=source_url", h)
                if ri and ri.status_code == 200:
                    img_url = ri.json().get("source_url", "")
            resultado.append({
                "title": p["title"]["rendered"],
                "excerpt": p["excerpt"]["rendered"].replace("<p>","").replace("</p>","").strip()[:110],
                "link": p["link"],
                "img": img_url,
            })
        return resultado

    def main_card(p):
        img_html = f'<img src="{p["img"]}" alt="{p["title"]}" style="width:100%;height:260px;object-fit:cover;display:block;" loading="lazy"/>' if p["img"] else ''
        return f"""<a href="{p['link']}" style="text-decoration:none;color:inherit;display:block;">
  <div style="background:#fff;border-radius:8px;overflow:hidden;box-shadow:0 2px 8px rgba(0,0,0,0.10);">
    {img_html}
    <div style="padding:16px 18px;">
      <h3 style="margin:0 0 8px;font-size:19px;line-height:1.3;color:#1A1A18;font-family:Oswald,sans-serif;font-weight:600;">{p['title']}</h3>
      <p style="margin:0;font-size:13px;color:#666;line-height:1.5;">{p['excerpt']}...</p>
    </div>
  </div>
</a>"""

    def side_card(p):
        onerr = "this.style.display='none'"
        img_html = f'<img src="{p["img"]}" alt="{p["title"]}" style="width:100%;height:140px;object-fit:cover;display:block;" loading="lazy" onerror="{onerr}"/>' if p["img"] else ''
        return f"""<a href="{p['link']}" style="text-decoration:none;color:inherit;display:block;">
  <div style="background:#fff;border-radius:8px;overflow:hidden;box-shadow:0 2px 8px rgba(0,0,0,0.10);">
    {img_html}
    <div style="padding:12px 14px;">
      <h3 style="margin:0 0 6px;font-size:14px;line-height:1.3;color:#1A1A18;font-family:Oswald,sans-serif;font-weight:600;">{p['title']}</h3>
      <p style="margin:0;font-size:12px;color:#777;line-height:1.4;">{p['excerpt'][:90]}...</p>
    </div>
  </div>
</a>"""

    def build_section(cat, posts):
        if not posts:
            return f"""<section style="margin-bottom:48px;">
  <div style="display:flex;align-items:center;justify-content:space-between;border-bottom:3px solid #E8541E;padding-bottom:10px;margin-bottom:20px;">
    <h2 style="margin:0;font-size:24px;font-family:Oswald,sans-serif;text-transform:uppercase;color:#1A1A18;letter-spacing:.04em;">{cat['nombre']}</h2>
    <a href="/category/{cat['slug']}/" style="font-size:11px;color:#E8541E;text-decoration:none;font-weight:700;letter-spacing:.08em;text-transform:uppercase;">Ver todo &#8594;</a>
  </div>
  <div style="background:#fff;border-radius:8px;padding:32px;text-align:center;box-shadow:0 2px 8px rgba(0,0,0,0.08);">
    <p style="margin:0;font-size:15px;color:#888;font-family:Inter,sans-serif;">Próximamente: contenido de {cat['nombre'].lower()}.</p>
  </div>
</section>"""
        
        main_p = posts[0]
        sides = posts[1:]
        sides_html = "".join(f'<div style="margin-bottom:14px;">{side_card(p)}</div>' for p in sides)
        grid_cols = "2fr 1fr" if sides else "1fr"

        return f"""<section style="margin-bottom:48px;">
  <div style="display:flex;align-items:center;justify-content:space-between;border-bottom:3px solid #E8541E;padding-bottom:10px;margin-bottom:20px;">
    <h2 style="margin:0;font-size:24px;font-family:Oswald,sans-serif;text-transform:uppercase;color:#1A1A18;letter-spacing:.04em;">{cat['nombre']}</h2>
    <a href="/category/{cat['slug']}/" style="font-size:11px;color:#E8541E;text-decoration:none;font-weight:700;letter-spacing:.08em;text-transform:uppercase;">Ver todo &#8594;</a>
  </div>
  <div style="display:grid;grid-template-columns:{grid_cols};gap:20px;align-items:start;">
    <div>{main_card(main_p)}</div>
    {"<div>" + sides_html + "</div>" if sides else ""}
  </div>
</section>"""

    # Construir el HTML completo
    secciones_html = ""
    for cat in CATEGORIAS:
        print(f"  [Home] Cargando posts de {cat['nombre']}...")
        posts = get_posts_categoria(cat["id"])
        secciones_html += build_section(cat, posts)

    html_portada = f"""<!-- wp:html -->
<div style="max-width:1100px;margin:0 auto;padding:32px 20px;font-family:Inter,sans-serif;">
{secciones_html}
</div>
<!-- /wp:html -->"""

    # Actualizar la página de portada
    r = request_with_retry("POST", f"{WP_API}/pages/{HOME_PAGE_ID}", h, {"content": html_portada})
    if r and r.status_code == 200:
        print(f"  [Home] ✓ Portada actualizada correctamente")
        return True
    else:
        status = r.status_code if r else "sin respuesta"
        print(f"  [Home] ✗ Error actualizando portada: {status}")
        return False
