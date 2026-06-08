import os, requests, base64
from datetime import datetime, timedelta
import markdown2

WP_URL = os.environ["WP_URL"]
WP_USER = os.environ["WP_USER"]  
WP_APP_PASS = os.environ["WP_APP_PASS"]

def get_auth_header():
    t = base64.b64encode(f"{WP_USER}:{WP_APP_PASS}".encode()).decode()
    return {"Authorization": f"Basic {t}", "Content-Type": "application/json"}

def get_or_create(name, headers, ep):
    slug = name.lower().replace(" ", "-")
    r = requests.get(f"{WP_URL}/wp-json/wp/v2/{ep}?slug={slug}", headers=headers)
    d = r.json()
    if d: return d[0]["id"]
    r = requests.post(f"{WP_URL}/wp-json/wp/v2/{ep}", headers=headers, json={"name": name, "slug": slug})
    return r.json().get("id", 0)

def publicar(a):
    h = get_auth_header()
    html = markdown2.markdown(a["contenido_md"])
    tags = [get_or_create(t, h, "tags") for t in a.get("tags", [])]
    cat = get_or_create(a.get("categoria", "Noticias"), h, "categories")
    now = datetime.now()
    fecha = (now + __import__("datetime").timedelta(days=1)).replace(
        hour=9 if now.hour < 12 else 17, minute=0, second=0, microsecond=0
    ).strftime("%Y-%m-%dT%H:%M:%S")
    p = {"title": a["seo_title"] or a["titulo"], "content": html, "slug": a["slug"],
         "status": "future", "date": fecha, "tags": tags,
         "categories": [cat] if cat else [], "excerpt": a["meta_description"]}
    r = requests.post(f"{WP_URL}/wp-json/wp/v2/posts", headers=h, json=p)
    if r.status_code in (200, 201):
        return {"ok": True, "url": r.json().get("link")}
    return {"ok": False, "error": r.text[:200]}
