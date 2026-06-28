"""
Scout Agent - Busca noticias frescas del mundo moto usando Exa API.
Devuelve las mas relevantes y filtra duplicados vs. articulos ya publicados.
Solo motos - filtra autos, coches y vehiculos de 4 ruedas.
"""
import os, json, hashlib, requests
from datetime import datetime, timedelta

EXA_API_KEY = os.environ["EXA_API_KEY"]
PUBLISHED_LOG = "published_hashes.json"

# Queries especificas de motos - nunca de autos
QUERIES = [
    "novedades motos motocicletas 2026 lanzamiento nueva moto",
    "MotoGP Superbike resultados carrera campeonato",
    "motos electricas scooter electrico moto novedad 2026",
    "adventure trail enduro moto review test",
    "custom cafe racer scrambler naked moto noticias",
    "moto seguridad casco equipo normativa conduccion",
]

# Palabras que indican que el resultado es sobre autos, no motos
AUTO_KEYWORDS = [
    "automovil", "automobile", "auto electrico", "coche electrico",
    "sedan", " suv ", "crossover auto", "pick-up", "camion",
    "ioniq", "tesla", "volkswagen golf", "toyota corolla",
    "hibrido enchufable coche", "vehiculo electrico cuatro ruedas",
]

def is_moto_content(title, url=""):
    """Retorna False si el articulo parece ser sobre autos, no motos."""
    text = (title + " " + url).lower()
    for kw in AUTO_KEYWORDS:
        if kw in text:
            return False
    return True

def load_published():
    try:
        with open(PUBLISHED_LOG) as f:
            return set(json.load(f))
    except FileNotFoundError:
        return set()

def save_published(hashes):
    with open(PUBLISHED_LOG, "w") as f:
        json.dump(list(hashes), f)

def slug_hash(title):
    return hashlib.md5(title.lower().strip().encode()).hexdigest()[:12]

def search_news(query, num=5):
    r = requests.post(
        "https://api.exa.ai/search",
        headers={"x-api-key": EXA_API_KEY, "Content-Type": "application/json"},
        json={
            "query": query,
            "numResults": num,
            "type": "neural",
            "useAutoprompt": True,
            "startPublishedDate": (datetime.utcnow() - timedelta(days=7)).strftime("%Y-%m-%dT00:00:00Z"),
            "contents": {"text": {"maxCharacters": 800}},
        },
    )
    r.raise_for_status()
    return r.json().get("results", [])

def buscar_noticias(max_noticias=5):
    published = load_published()
    candidatos = []
    seen_hashes = set(published)

    for q in QUERIES:
        try:
            results = search_news(q, num=4)
            for item in results:
                title = item.get("title", "").strip()
                url = item.get("url", "")
                text = item.get("text", "")

                if not title or len(title) < 10:
                    continue

                # Filtrar si es sobre autos, no motos
                if not is_moto_content(title, url):
                    print(f"  [Scout] Descartado (no es moto): {title[:60]}")
                    continue

                h = slug_hash(title)
                if h in seen_hashes:
                    continue

                seen_hashes.add(h)
                candidatos.append({
                    "titulo": title,
                    "url": url,
                    "resumen": text[:500] if text else "",
                    "hash": h,
                })
        except Exception as e:
            print(f"  [Scout] Error en query '{q}': {e}")
            continue

    noticias = candidatos[:max_noticias]
    nuevos_hashes = published | {n["hash"] for n in noticias}
    save_published(nuevos_hashes)
    return noticias


# Alias para compatibilidad con main.py
run = buscar_noticias
