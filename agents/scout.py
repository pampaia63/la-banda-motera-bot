"""
Scout Agent - Busca noticias frescas del mundo moto usando Exa API.
Devuelve las mas relevantes y filtra duplicados vs. articulos ya publicados.
Solo motos - filtra autos, coches y vehiculos de 4 ruedas.
"""
import os, json, hashlib, requests
from datetime import datetime, timedelta

EXA_API_KEY = os.environ["EXA_API_KEY"]
PUBLISHED_LOG = "published_hashes.json"

# Queries organizadas por mercado objetivo y tipo de contenido
# Prioriza motos que se venden en AR/ES/MX y noticias relevantes para esos mercados

QUERIES = [
    # --- LANZAMIENTOS Argentina/Cono Sur ---
    "nueva moto lanzamiento Argentina 2025 2026 precio disponible",
    "moto nueva llega Argentina Colombia Chile Uruguay 2026",
    "Benelli CFMoto QJ Motor Moto Morini Royal Enfield lanzamiento Argentina",
    "Zontes Voge Rieju beta nueva moto Argentina España 2026",
    # --- LANZAMIENTOS España ---
    "nueva moto lanzamiento España 2025 2026 precio presentacion",
    "KTM Honda Yamaha Kawasaki BMW Ducati Aprilia Triumph novedad España 2026",
    # --- LANZAMIENTOS México/LATAM ---
    "nueva moto lanzamiento Mexico Colombia 2025 2026 precio",
    "Italika Honda Yamaha Kawasaki novedad Mexico 2026",
    # --- MODELOS CLAVE PARA LOS 3 MERCADOS ---
    "moto mediana cilindrada 300cc 500cc 650cc 800cc nueva 2026",
    "trail adventure naked scrambler nuevo modelo 2025 2026",
    # --- REVIEWS Y COMPARATIVAS ---
    "review prueba test moto trail adventure naked 2025 2026",
    "comparativa moto mediana cilindrada trail adventure 2026",
    # --- MECÁNICA Y TECNOLOGÍA MOTO ---
    "sistema desmodromic ducati como funciona valvulas moto",
    "telelever duolever bmw suspension delantera moto explicacion",
    "motor boxer bmw refrigeracion aire cilindros opuestos moto",
    "transmision cardan cadena correa moto diferencias ventajas",
    "frenos abs moto como funciona cornering abs curvas",
    "control traccion moto tcs funcionamiento antibloqueo",
    "horquilla invertida telescopica diferencias suspension moto",
    "motor v twin paralelo cilindros moto diferencias caracter",
    "inyeccion electronica carburador moto historia evolucion",
    "quickshifter autoblipper moto como funciona cambio sin embrague",
    "chasis perimetral tubular moto diferencias rigidez torsion",
    "sistema refrigeracion liquida aire moto explicacion comparativa",
    # --- HISTORIAS MOTERAS Y CULTURA ---
    "historia moto iconica clasica legendaria marca motocicleta",
    "cultura motera cafe racer scrambler custom historia origen",
    "piloto moto legendario historia campeonato icono",
    "moto electrica 2026 novedad autonomia precio España Argentina",
]

# Marcas SIN presencia en LATAM ni España — excluir sus noticias
MARCAS_IRRELEVANTES = [
    # Marcas exclusivamente asiáticas o de EE.UU. sin distribución confirmada
    "zero motorcycles",  # moto eléctrica cara, sin red en LATAM
    "indian motorcycle",  # muy marginal en LATAM
    "norton",  # sin presencia real
    "ural",    # rusa, sin presencia
    "cleveland cyclewerks",
    "curtiss motorcycle",
    "arch motorcycle",
    "buell",
    # Marcas japonesas de alta gama sin presencia local
    "confederate motors",
    # Marcas de competición pura sin road relevance
    "husaberg",
]

def is_marca_relevante(title, url=""):
    """Excluye noticias de marcas irrelevantes para LATAM/España."""
    text = (title + " " + url).lower()
    for marca in MARCAS_IRRELEVANTES:
        if marca in text:
            print(f"  [Scout] Excluida (marca irrelevante): {title[:50]}")
            return False
    return True

# Palabras que indican que el resultado es sobre autos, no motos
AUTO_KEYWORDS = [
    "automovil", "automobile", "auto electrico", "coche electrico",
    "sedan", " suv ", "crossover auto", "pick-up", "camion",
    "ioniq", "tesla", "volkswagen golf", "toyota corolla",
    "hibrido enchufable coche", "vehiculo electrico cuatro ruedas",
]

# Palabras que indican noticias completamente fuera del foco editorial
IRRELEVANT_KEYWORDS = [
    "australian superbike", "british superbike", "bsb",
    "enduro australia", "enduro usa", "american flat track",
    "prix de france", "isle of man tt",
    "motogp carrera resultado", "superbike resultado carrera",
    "rally dakar etapa resultado",  # resultados de carrera — no cubre el bot
]

def is_moto_content(title, url=""):
    """Retorna False si el articulo parece ser sobre autos, no motos,
    o si es una competición completamente irrelevante para LATAM/España."""
    text = (title + " " + url).lower()
    # Filtrar autos
    for kw in AUTO_KEYWORDS:
        if kw in text:
            return False
    # Filtrar competiciones hiperespecíficas sin interés para nuestros mercados
    for kw in IRRELEVANT_KEYWORDS:
        if kw in text:
            return False
    return True

def calcular_relevancia(title, url="", resumen=""):
    """
    Puntúa la relevancia de una noticia para los mercados AR/ES/MX.
    Mayor puntaje = más relevante = mayor prioridad.
    """
    text = (title + " " + url + " " + resumen).lower()
    score = 0

    # Motos que se venden en LATAM/España — alta relevancia
    marcas_relevantes = [
        "ktm", "honda", "yamaha", "kawasaki", "suzuki", "bmw",
        "ducati", "triumph", "aprilia", "royal enfield", "benelli",
        "cfmoto", "qj motor", "moto morini", "voge", "rieju",
        "husqvarna", "gasgas", "beta", "sherco", "jawa",
        "keller", "gilera", "zanella", "motomel", "corven", "mondial"
    ]
    for marca in marcas_relevantes:
        if marca in text:
            score += 3

    # Palabras clave de interés editorial
    keywords_positivos = [
        "argentina", "españa", "mexico", "colombia", "latam",
        "lanzamiento", "precio", "disponible", "llega",
        "trail", "adventure", "naked", "enduro", "scrambler",
        "review", "prueba", "test", "comparativa",
        "mecanica", "tecnica", "como funciona", "sistema",
        "desmodromic", "telelever", "suspension", "frenos abs",
        "historia", "cultura", "icono", "clasico", "origen"
    ]
    for kw in keywords_positivos:
        if kw in text:
            score += 1

    # Penalizar si es muy específico de un mercado lejano
    keywords_lejanos = [
        "australian", "british", "american", "thai gp",
        "indian open", "malaysian gp"
    ]
    for kw in keywords_lejanos:
        if kw in text:
            score -= 2

    return score

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

# Medios de referencia por audiencia y relevancia editorial (España + LATAM)
MEDIOS_REFERENCIA = [
    # España - mayor audiencia confirmada (GfK DAM)
    "motorpasionmoto.com",   # líder absoluto de audiencia en España
    "motosan.es",
    "soymotero.net",
    "lamoto.es",
    "motociclismo.es",
    "moto1pro.com",          # revista digital de referencia técnica
    "motorbikemag.es",
    "motofichas.com",
    # Argentina
    "lamoto.com.ar",         # referencia histórica, usada como benchmark de diseño
    "motonews.com.ar",
    "informoto.com",
    "motorpress.com.ar",
    # México
    "revistamoto.com",       # la más grande de México
    "motociclo.com.mx",
    # Colombia
    "demotos.com.co",
    "bimotos.com",
    "revistaautosmas.com",
    # Internacional / técnico en inglés (para lanzamientos globales y MotoGP)
    "motorcyclenews.com",
    "cycleworld.com",
    "visordown.com",
]

def search_news(query, num=5, usar_medios_referencia=True):
    payload = {
        "query": query,
        "numResults": num,
        "type": "neural",
        "useAutoprompt": True,
        "startPublishedDate": (datetime.utcnow() - timedelta(days=14)).strftime("%Y-%m-%dT00:00:00Z"),
        "contents": {"text": {"maxCharacters": 800}},
    }
    if usar_medios_referencia:
        payload["includeDomains"] = MEDIOS_REFERENCIA

    r = requests.post(
        "https://api.exa.ai/search",
        headers={"x-api-key": EXA_API_KEY, "Content-Type": "application/json"},
        json=payload,
    )
    r.raise_for_status()
    results = r.json().get("results", [])

    # Si la búsqueda restringida a medios de referencia no trae nada, reintentar sin restricción
    if not results and usar_medios_referencia:
        print(f"  [Scout] Sin resultados en medios de referencia para '{query[:40]}', ampliando búsqueda...")
        payload.pop("includeDomains", None)
        r2 = requests.post(
            "https://api.exa.ai/search",
            headers={"x-api-key": EXA_API_KEY, "Content-Type": "application/json"},
            json=payload,
        )
        r2.raise_for_status()
        results = r2.json().get("results", [])

    return results

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

                # Filtrar marcas sin relevancia en LATAM/España
                if not is_marca_relevante(title, url):
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
                relevancia = calcular_relevancia(title, url, text)
                candidatos.append({
                    "titulo": title,
                    "url": url,
                    "resumen": text[:500] if text else "",
                    "hash": h,
                    "relevancia": relevancia,
                })
        except Exception as e:
            print(f"  [Scout] Error en query '{q}': {e}")
            continue

    # Ordenar por relevancia descendente antes de tomar los primeros N
    candidatos.sort(key=lambda x: x.get("relevancia", 0), reverse=True)
    print(f"  [Scout] Top candidatos por relevancia:")
    for c in candidatos[:max_noticias]:
        print(f"    [{c.get('relevancia',0):+d}] {c['titulo'][:60]}")
    noticias = candidatos[:max_noticias]
    nuevos_hashes = published | {n["hash"] for n in noticias}
    save_published(nuevos_hashes)
    return noticias


# Alias para compatibilidad con main.py
run = buscar_noticias
