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
    "nueva moto lanzamiento 2026 motocicleta presentacion oficial",
    "MotoGP Superbike WorldSBK resultados carrera campeonato 2025 2026",
    "moto electrica scooter electrico novedad lanzamiento 2026",
    "adventure trail enduro moto review test comparativa",
    "custom cafe racer scrambler naked street fighter moto",
    "moto tecnologia suspension frenos motor innovacion",
    "rally dakar enduro cross country moto competicion",
    "moto accesible precio economica trail mediana cilindrada",
    "KTM Honda Yamaha Kawasaki BMW Ducati nueva moto 2026",
    "Benelli CFMoto Moto Morini Rieju Royal Enfield novedad moto",
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

def titulo_similar(t1, t2, umbral=0.6):
    """Detecta si dos títulos son muy similares (mismo tema con distinta redacción)."""
    # Normalizar: minúsculas, sin tildes, sin puntuación
    import re, unicodedata
    def normalizar(t):
        t = t.lower()
        t = unicodedata.normalize('NFD', t).encode('ascii', 'ignore').decode()
        t = re.sub(r'[^a-z0-9 ]', ' ', t)
        return set(t.split())

    palabras1 = normalizar(t1)
    palabras2 = normalizar(t2)

    # Filtrar palabras muy cortas y stopwords comunes
    stopwords = {'el','la','los','las','un','una','de','del','en','y','a','con','por','que','se','es','su','al','como'}
    palabras1 = {p for p in palabras1 if len(p) > 2 and p not in stopwords}
    palabras2 = {p for p in palabras2 if len(p) > 2 and p not in stopwords}

    if not palabras1 or not palabras2:
        return False

    # Jaccard similarity
    interseccion = palabras1 & palabras2
    union = palabras1 | palabras2
    similitud = len(interseccion) / len(union)
    return similitud >= umbral

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
            "startPublishedDate": (datetime.utcnow() - timedelta(days=14)).strftime("%Y-%m-%dT00:00:00Z"),
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

                # Verificar similitud con títulos ya recopilados (evita duplicados con misma noticia)
                es_duplicado = False
                for c in candidatos:
                    if titulo_similar(title, c["titulo"]):
                        print(f"  [Scout] Duplicado similar: {title[:50]}")
                        es_duplicado = True
                        break
                if es_duplicado:
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
