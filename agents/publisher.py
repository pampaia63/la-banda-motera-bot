import os, requests, base64, time, re
from datetime import datetime, timedelta
import markdown2

WP_URL = os.environ["WP_URL"].rstrip("/")
WP_USER = os.environ["WP_USER"]
WP_APP_PASS = os.environ["WP_APP_PASS"]

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
                    continue

                html = resp.text

                # Buscar og:image en el HTML
                import re
                og_patterns = [
                    r'<meta[^>]+property=["']og:image["'][^>]+content=["']([^"']+)["']',
                    r'<meta[^>]+content=["']([^"']+)["'][^>]+property=["']og:image["']',
                    r'<meta[^>]+name=["']twitter:image["'][^>]+content=["']([^"']+)["']',
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

        print(f"  [Imagen] No se encontró imagen real para: {titulo[:50]}")
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
    CATEGORIA_IDS = {
        # Nombres nuevos
        "Competición":        9,
        "Reviews":            19,
        "Nuevos Lanzamientos": 15,
        "Marcas":             44,
        "Comparativas":       46,
        "Historias Moteras":  47,
        # Fallbacks nombres viejos del editor
        "Noticias":           9,   # → Competición
        "MotoGP":             9,   # → Competición
        "Adventure":          15,  # → Nuevos Lanzamientos
        "Custom":             44,  # → Marcas
        "Electrica":          15,  # → Nuevos Lanzamientos
        "Técnica":            19,  # → Reviews
        "Tecnica":            19,  # → Reviews
        "Seguridad":          19,  # → Reviews
    }
    cat_nombre = a.get("categoria", "Reviews")
    cat = CATEGORIA_IDS.get(cat_nombre, 19)  # default: Reviews (ID 19)
    print(f"  [Publisher] Categoría: '{cat_nombre}' → ID {cat}")

    # Programar para manana 17:00
    now = datetime.now()
    fecha_pub = (now + timedelta(days=1)).replace(hour=17, minute=0, second=0, microsecond=0).strftime("%Y-%m-%dT%H:%M:%S")
    titulo_pub = a.get("seo_title") or a.get("titulo", "Sin titulo")

    p = {
        "title": titulo_pub,
        "content": html_final,
        "excerpt": bajada,
        "slug": a.get("slug", ""),
        "status": "future",
        "date": fecha_pub,
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
