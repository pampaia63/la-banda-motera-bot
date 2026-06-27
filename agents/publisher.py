import os, requests, base64, time
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
                print(f"  [Intento {intento}] Anti-bot, reintentando...")
                time.sleep(intento * 3)
                continue
            return r
        except (requests.exceptions.ConnectionError, requests.exceptions.Timeout) as e:
            print(f"  [Intento {intento}/{max_retries}] Conexion fallo: {type(e).__name__}")
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

def build_youtube_block(yt):
    """Genera el bloque HTML del CTA de YouTube al final del articulo."""
    if not yt or not yt.get("url"):
        return ""
    url = yt["url"]
    marca = yt.get("marca", "")
    titulo_video = yt.get("titulo", "Isaias Rider en YouTube")

    if marca:
        texto_cta = f"En el canal de Isaias Rider encontras videos reales de {marca} en ruta y off-road. Dale un vistazo antes de decidir."
    else:
        texto_cta = "Seguimos este tema en el canal de Isaias Rider con pruebas reales en ruta. Dale un vistazo."

    return f"""
<div style="background:#1A1A18;border-left:4px solid #E8541E;padding:20px 24px;margin:32px 0;border-radius:6px;">
<p style="color:#F4F0E9;font-size:14px;margin:0 0 8px;text-transform:uppercase;letter-spacing:1px;font-weight:600;">🎬 En video</p>
<p style="color:#D8D2C6;margin:0 0 14px;line-height:1.5;">{texto_cta}</p>
<a href="{url}" target="_blank" rel="noopener" style="display:inline-block;background:#E8541E;color:#fff;padding:10px 20px;border-radius:4px;text-decoration:none;font-weight:600;font-size:14px;">Ver en YouTube →</a>
</div>"""

def publicar(a):
    h = get_auth_header()

    # Construir contenido HTML
    contenido_md = a.get("contenido_md", "")

    # Agregar bloque de YouTube al final
    yt_block = build_youtube_block(a.get("youtube"))

    # Convertir markdown a HTML
    html_contenido = markdown2.markdown(
        contenido_md,
        extras=["fenced-code-blocks", "tables", "header-ids"]
    )

    html_final = html_contenido + yt_block

    # Bajada como extracto
    bajada = a.get("bajada", "")

    # Tags y categoria
    tags = [get_or_create(t, h, "tags") for t in a.get("tags", [])]
    cat = get_or_create(a.get("categoria", "Noticias"), h, "categories")

    # Programar para manana a las 17:00
    now = datetime.now()
    fecha_pub = (now + timedelta(days=1)).replace(
        hour=17, minute=0, second=0, microsecond=0
    ).strftime("%Y-%m-%dT%H:%M:%S")

    # Titulo: usar seo_title o titulo
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
        "meta": {
            "_yoast_wpseo_title": a.get("seo_title", ""),
            "_yoast_wpseo_metadesc": a.get("meta_description", ""),
        }
    }

    r = request_with_retry("POST", f"{WP_URL}/wp-json/wp/v2/posts", h, p)
    if r is None:
        print("  [Publisher] Sin respuesta tras reintentos")
        return {"ok": False, "error": "no response"}
    if r.status_code in (200, 201):
        post_data = r.json()
        link = post_data.get("link", "publicado")
        post_id = post_data.get("id", "?")
        autor = a.get("autor", "isaiasrider")
        print(f"  [Publisher] OK: {link} | Autor: {autor} | ID: {post_id}")
        return {"ok": True, "url": link, "id": post_id}
    print(f"  [Publisher] Error {r.status_code}: {r.text[:200]}")
    return {"ok": False, "error": r.text[:200]}
