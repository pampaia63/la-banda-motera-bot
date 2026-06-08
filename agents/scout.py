"""
Scout Agent — Busca noticias frescas del mundo moto usando Exa API.
Devuelve las más relevantes y filtra duplicados vs. artículos ya publicados.
"""
import os, json, hashlib, requests
from datetime import datetime, timedelta

EXA_API_KEY = os.environ["EXA_API_KEY"]
PUBLISHED_LOG = "published_hashes.json"

QUERIES = [
    "novedades motos 2026 lanzamiento",
    "MotoGP resultados carrera",
    "motos eléctricas noticias",
    "adventure trail touring moto review",
    "custom cafe racer scrambler noticias",
    "moto accidente seguridad vial normativa",
]

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
            "startPublishedDate": (datetime.now() - timedelta(days=3)).strftime("%Y-%m-%dT00:00:00Z"),
            "contents": {"text": {"maxCharacters": 800}, "highlights": {"numSentences": 3}},
        },
        timeout=20,
    )
    r.raise_for_status()
    return r.json().get("results", [])

def run():
    published = load_published()
    candidates = []
    for query in QUERIES:
        try:
            results = search_news(query)
            for item in results:
                h = slug_hash(item.get("title", ""))
                if h in published: continue
                candidates.append({"title":item.get("title",""),"url":item.get("url",""),"source":item.get("author") or item.get("url","").split("/")[2],"text":item.get("text","")[:800],"highlights":item.get("highlights",[]),"date":item.get("publishedDate","")[:10],"hash":h,"query":query})
        except Exception as e: print(f"[Scout] Error: {e}")
    candidates.sort(key=lambda x: len(x["text"]), reverse=True)
    return candidates[:5], published

if __name__ == "__main__":
    n,_ = run()
    print(json.dumps(n, ensure_ascii=False, indent=2))
