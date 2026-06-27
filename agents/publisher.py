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

def generar_imagen_ia(titulo, imagen_prompt=None):
    """
    Genera una imagen con IA usando Pollinations.ai (gratis, sin API key).
    Devuelve el contenido binario de la imagen o None si falla.
    """
    try:
        # Construir prompt fotografico de la moto
        if imagen_prompt:
            prompt = imagen_prompt
        else:
            # Extraer marca y modelo del titulo para el prompt
            prompt = f"Professional motorcycle photography, {titulo[:80]}, no people, studio lighting, photorealistic, high detail, 4k"

        # Limpiar el prompt para la URL
        prompt_encoded = requests.utils.quote(prompt)
        url = f"https://image.pollinations.ai/prompt/{prompt_encoded}?width=1280&height=720&nologo=true&enhance=true&model=flux"

        print(f"  [Imagen] Generando con IA: {prompt[:60]}...")
        r = requests.get(url, timeout=60)

        if r.status_code == 200 and len(r.content) > 10000:
            print(f"  [Imagen] OK - {len(r.content)//1024}KB")
            return r.content
        else:
            print(f"  [Imagen] Fallo: status {r.status_code}, size {len(r.content)}")
            return None
    except Exception as e:
        print(f"  [Imagen] Error: {e}")
        return None

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
    imagen_bytes = generar_imagen_ia(a.get("titulo", ""), imagen_prompt)
    if imagen_bytes:
        media_id = subir_imagen_wp(imagen_bytes, a.get("titulo", ""), h)

    # Construir HTML
    contenido_md = a.get("contenido_md", "")
    yt_block = build_youtube_block(a.get("youtube"))
    html_contenido = markdown2.markdown(contenido_md, extras=["fenced-code-blocks", "tables", "header-ids"])
    html_final = html_contenido + yt_block
    bajada = a.get("bajada", "")

    # Tags y categoria
    tags = [get_or_create(t, h, "tags") for t in a.get("tags", [])]
    cat = get_or_create(a.get("categoria", "Noticias"), h, "categories")

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
