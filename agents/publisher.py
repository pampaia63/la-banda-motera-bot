import os, requests, base64, time
from datetime import datetime, timedelta
import markdown2

WP_URL = os.environ["WP_URL"].rstrip("/")
WP_USER = os.environ["WP_USER"]
WP_APP_PASS = os.environ["WP_APP_PASS"]

# User-Agent de navegador para evitar el bloqueo anti-bot de InfinityFree
BROWSER_UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"

# Sesion global con reintentos
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
    """Hace requests con reintentos y backoff para superar el anti-bot de InfinityFree."""
    for intento in range(1, max_retries + 1):
        try:
            if method == "GET":
                r = session.get(url, headers=headers, timeout=30)
            else:
                r = session.post(url, headers=headers, json=json_data, timeout=30)
            # Si InfinityFree devuelve su pagina de proteccion, reintentar
            if r.status_code == 200 or r.status_code == 201:
                return r
            if "aes.js" in r.text or "__test" in r.text.lower():
                print(f"  [Intento {intento}] InfinityFree anti-bot detectado, reintentando...")
                time.sleep(intento * 3)
                continue
            return r
        except (requests.exceptions.ConnectionError, requests.exceptions.Timeout) as e:
            print(f"  [Intento {intento}/{max_retries}] Conexion fallo: {type(e).__name__}, esperando...")
            time.sleep(intento * 4)
    return None

def get_or_create(name, headers, ep):
    slug = name.lower().replace(" ", "-")
    r = request_with_retry("GET", f"{WP_URL}/wp-json/wp/v2/{ep}?slug={slug}", headers)
    if r is None:
        return 0
    try:
        d = r.json()
        if d and isinstance(d, list):
            return d[0]["id"]
    except Exception:
        pass
    r = request_with_retry("POST", f"{WP_URL}/wp-json/wp/v2/{ep}", headers, {"name": name, "slug": slug})
    if r is None:
        return 0
    try:
        return r.json().get("id", 0)
    except Exception:
        return 0

def publicar(a):
    h = get_auth_header()
    html = markdown2.markdown(a["contenido_md"])
    tags = [get_or_create(t, h, "tags") for t in a.get("tags", [])]
    cat = get_or_create(a.get("categoria", "Noticias"), h, "categories")
    now = datetime.now()
    fecha = (now + timedelta(days=1)).replace(
        hour=9 if now.hour < 12 else 17, minute=0, second=0, microsecond=0
    ).strftime("%Y-%m-%dT%H:%M:%S")
    p = {
        "title": a["seo_title"] or a["titulo"],
        "content": html,
        "slug": a["slug"],
        "status": "future",
        "date": fecha,
        "tags": tags,
        "categories": [cat] if cat else [],
        "excerpt": a["meta_description"],
    }
    r = request_with_retry("POST", f"{WP_URL}/wp-json/wp/v2/posts", h, p)
    if r is None:
        print("  [Publisher] Sin respuesta tras reintentos")
        return {"ok": False, "error": "no response"}
    if r.status_code in (200, 201):
        link = r.json().get("link", "publicado")
        print(f"  [Publisher] OK: {link}")
        return {"ok": True, "url": link}
    print(f"  [Publisher] Error {r.status_code}: {r.text[:150]}")
    return {"ok": False, "error": r.text[:150]}
