"""
Editor Agent - Genera articulos originales, ricos y con identidad editorial propia.
Cada articulo tiene: voz propia segun mercado, specs reales, imagen, link a YouTube de Isaias Rider.
"""
import os, requests, re
from datetime import datetime

ANTHROPIC_API_KEY = os.environ["ANTHROPIC_API_KEY"]
EXA_API_KEY = os.environ["EXA_API_KEY"]
YOUTUBE_CHANNEL_ID = "UCpUvpfssZld4So4nnnuxquQ"
YOUTUBE_CHANNEL_URL = "https://www.youtube.com/channel/UCpUvpfssZld4So4nnnuxquQ"

# ---- Perfiles de voz ----
VOCES = {
    "AR": {
        "nombre": "Mateo Quiroga",
        "ubicacion": "Buenos Aires, Argentina",
        "dialecto": "Rioplatense. Usa vos, che, fierro. Cercano y apasionado.",
        "bio": "Mateo Quiroga es periodista de motos desde Buenos Aires. Pilota desde los 17 anos y escribe con la pasion de quien ama andar.",
    },
    "MX": {
        "nombre": "Diego Salazar",
        "ubicacion": "Ciudad de Mexico, Mexico",
        "dialecto": "Espanol mexicano neutro. Claro, calido y profesional.",
        "bio": "Diego Salazar cubre el mundo de las motos desde la CDMX. Con anos de experiencia en pruebas en ruta, su analisis es tecnico pero accesible.",
    },
    "ES": {
        "nombre": "Carlos Herrera",
        "ubicacion": "Madrid, Espana",
        "dialecto": "Castellano peninsular. Usa vale, molar. Tono tecnico y editorial.",
        "bio": "Carlos Herrera es redactor jefe de motos desde Madrid. Especialista en tecnologia y mercado europeo.",
    },
    "CO": {
        "nombre": "Andres Gomez",
        "ubicacion": "Bogota, Colombia",
        "dialecto": "Espanol andino neutro. Calido y didactico.",
        "bio": "Andres Gomez escribe sobre motos desde Bogota. Su enfoque es accesible y orientado al rider latinoamericano.",
    },
}

# Señales geográficas por zona
SEÑALES_AR = [
    # Países
    "argentina", "argentino", "argentina", "buenos aires", "cordoba", "rosario",
    "mendoza", "tucuman", "salta", "montevideo", "uruguay", "paraguay", "chile",
    "bolivia", "peru", "ecuador", "cono sur", "latam", "latinoamerica",
    # Marcas locales
    "keller", "gilera", "zanella", "motomel", "corven", "mondial", "beta ar",
    "bajaj argentina", "rouser", "pulsar",
    # Medios
    "lamoto.com.ar", "motonews.com.ar", "informoto.com",
    # Eventos
    "rally dakar", "tc2000 motos", "superbike argentina",
]

SEÑALES_ES = [
    # Países
    "españa", "espana", "madrid", "barcelona", "valencia", "sevilla",
    "iberia", "peninsula", "espanol",
    # Marcas españolas
    "rieju", "derbi", "gas gas", "gasgas", "bultaco",
    # Medios
    "motorpasionmoto.com", "motosan.es", "soymotero.net", "motociclismo.es",
    "moto1pro.com",
    # Competición europea
    "motogp", "superbike worldsbk", "moto2", "moto3", "campeonato mundial",
    "gran premio de", "gp de aragon", "gp de jerez", "gp de catalunya",
    "rally dakar",  # Dakar tiene mucha presencia española
    "eicma", "intermot",
]

SEÑALES_MX = [
    # Países
    "mexico", "méxico", "cdmx", "ciudad de mexico", "guadalajara", "monterrey",
    "jalisco", "nuevo leon",
    # Marcas locales MX
    "italika", "vento", "carabela", "dinamo", "vorago",
    # Medios
    "revistamoto.com", "motociclo.com.mx",
]

SEÑALES_CO = [
    # Países
    "colombia", "bogota", "medellin", "cali", "barranquilla",
    "venezuela", "panama", "costa rica", "centroamerica",
    # Marcas
    "akt", "auteco", "hero",
    # Medios
    "demotos.com.co", "bimotos.com",
]

def elegir_voz(titulo, url="", resumen="", indice_articulo=0):
    """
    Asigna la voz según la zona geográfica del contenido.
    - Si el artículo es claramente de una región → voz de esa región.
    - Si es internacional/ambiguo → rotación basada en índice para garantizar variedad.
    """
    text = (titulo + " " + url + " " + resumen).lower()

    # Contar señales por zona
    score_ar = sum(1 for s in SEÑALES_AR if s in text)
    score_es = sum(1 for s in SEÑALES_ES if s in text)
    score_mx = sum(1 for s in SEÑALES_MX if s in text)
    score_co = sum(1 for s in SEÑALES_CO if s in text)

    scores = {"AR": score_ar, "ES": score_es, "MX": score_mx, "CO": score_co}
    max_score = max(scores.values())

    # Si hay señal clara (≥1 match), usar la voz de esa zona
    if max_score >= 1:
        ganadora = max(scores, key=scores.get)
        print(f"  [Editor] Voz asignada por región: {ganadora} (scores: {scores})")
        return VOCES[ganadora]

    # Sin señal clara → rotación por índice para garantizar variedad en artículos internacionales
    orden = ["AR", "ES", "MX", "CO"]
    fallback = orden[indice_articulo % len(orden)]
    print(f"  [Editor] Voz por rotación (sin señal regional): {fallback}")
    return VOCES[fallback]

def buscar_imagen_moto(titulo):
    """Busca una imagen relevante de la moto usando Exa."""
    try:
        # Extraer marca/modelo del titulo
        query = titulo.replace(":", "").replace("-", " ") + " moto foto oficial"
        r = requests.post(
            "https://api.exa.ai/search",
            headers={"x-api-key": EXA_API_KEY, "Content-Type": "application/json"},
            json={
                "query": query,
                "numResults": 3,
                "type": "neural",
                "contents": {"highlights": {"numSentences": 1}},
            },
        )
        results = r.json().get("results", [])
        # Tomar la URL de la primera fuente como referencia
        if results:
            return results[0].get("url", "")
    except Exception as e:
        print(f"  [Editor] Error buscando imagen: {e}")
    return ""

def buscar_video_youtube(titulo):
    """
    Busca el video mas relevante del canal de Isaias Rider usando la YouTube Data API.
    Estrategia: extrae marca/categoria del titulo y busca en el canal.
    Fallback: enlaza directamente al canal si no hay match especifico.
    """
    # Extraer palabras clave de marca del titulo
    marcas = ["KTM", "Honda", "Yamaha", "Suzuki", "Kawasaki", "BMW", "Ducati",
               "Royal Enfield", "Benelli", "CFMoto", "Keller", "Motomel", "Gilera",
               "Zanella", "Corven", "Mondial", "Beta", "Bajaj", "Rieju", "Triumph",
               "Husqvarna", "GasGas", "Harley", "Indian", "Moto Morini", "Moto Guzzi"]

    titulo_upper = titulo.upper()
    marca_encontrada = None
    for marca in marcas:
        if marca.upper() in titulo_upper:
            marca_encontrada = marca
            break

    # Intentar buscar via YouTube Search (sin API key, usando scraping basico)
    # Como alternativa confiable: enlazar al canal con query de busqueda
    if marca_encontrada:
        query = f"site:youtube.com/watch Isaias Rider {marca_encontrada} moto"
        try:
            r = requests.post(
                "https://api.exa.ai/search",
                headers={"x-api-key": EXA_API_KEY, "Content-Type": "application/json"},
                json={
                    "query": f"Isaias Rider motovlog {marca_encontrada} review canal YouTube",
                    "numResults": 3,
                    "includeDomains": ["youtube.com"],
                    "type": "neural",
                },
            )
            results = r.json().get("results", [])
            for res in results:
                url = res.get("url", "")
                title = res.get("title", "")
                # Verificar que sea del canal de Isaias y mencione la marca
                if ("UCpUvpfssZld4So4nnnuxquQ" in url or "isaiasrider" in url.lower() or
                    ("isaias" in title.lower() and marca_encontrada.lower() in title.lower())):
                    return {"url": url, "titulo": title, "marca": marca_encontrada}
            # Si no encontro el canal exacto pero encontro videos de la marca
            if results:
                # Fallback: link de busqueda en YouTube del canal
                canal_search = f"https://www.youtube.com/@isaiasrider10/search?query={marca_encontrada}"
                return {"url": canal_search, "titulo": f"Videos de {marca_encontrada} en Isaias Rider", "marca": marca_encontrada}
        except Exception as e:
            print(f"  [Editor] Error buscando video YouTube: {e}")

    # Fallback final: link al canal
    return {"url": YOUTUBE_CHANNEL_URL, "titulo": "Isaias Rider - Canal de motos", "marca": marca_encontrada or ""}

def generar_articulo(noticia, voz):
    """Genera un articulo editorial adaptando extensión y estructura según la categoría."""

    # --- Pre-detectar categoría probable para adaptar el prompt ---
    titulo_lower = noticia['titulo'].lower()
    resumen_lower = (noticia.get('resumen') or '').lower()

    es_lanzamiento = any(k in titulo_lower + resumen_lower for k in [
        'lanzamiento', 'presentacion', 'nueva moto', 'nuevo modelo', 'llega',
        'precio', 'disponible', '2026', '2027', 'desvela', 'revela', 'confirma',
        'launch', 'unveiled', 'revealed', 'announced', 'new model'
    ])

    es_competicion = any(k in titulo_lower + resumen_lower for k in [
        'motogp', 'superbike', 'worldsbk', 'carrera', 'campeonato', 'podio',
        'gp ', 'gran premio', 'dakar', 'enduro', 'rally', 'resultado',
        'ganador', 'gana', 'wins', 'race', 'championship'
    ])

    # Prompt de LANZAMIENTO — corto, ficha técnica, mercados, fecha
    if es_lanzamiento:
        prompt = f"""Sos {voz['nombre']}, periodista de motos que escribe para La Banda Motera desde {voz['ubicacion']}.
{voz['bio']}
Dialecto: {voz['dialecto']}

Escribi una nota de lanzamiento CONCISA y DIRECTA sobre:

TITULO: {noticia['titulo']}
CONTEXTO: {noticia['resumen'][:400] if noticia.get('resumen') else 'Sin resumen'}
URL: {noticia.get('url', '')}

INSTRUCCIONES — NOTA DE LANZAMIENTO (400-600 palabras MÁXIMO):
1. Abrí con 2-3 oraciones de contexto editorial: por qué importa esta moto en el mercado actual.
2. Ficha técnica rápida: motor, potencia, torque, peso, altura de asiento, capacidad de tanque, precio (si se conoce).
3. Mercados de lanzamiento: ¿dónde llega? ¿Argentina, España, México? ¿Cuándo?
4. 1-2 párrafos de info complementaria: rival directo, posicionamiento, equipamiento destacado.
5. Cierre con una línea de opinión editorial directa y clara.
6. Usa máximo 2 subtítulos H2 (## en markdown).
7. NO es una review, NO hay test, NO hay "sensaciones al manejarla". Es una nota de lanzamiento informativa con voz editorial.
8. Usa el dialecto de tu perfil de forma natural.
9. NUNCA copies el texto fuente — todo original desde tu conocimiento.

FORMATO JSON exacto:
{{
  "titulo": "titulo SEO atractivo (máximo 65 caracteres)",
  "bajada": "1-2 oraciones de gancho para el lector",
  "contenido_md": "la nota completa en markdown, 400-600 palabras",
  "seo_title": "titulo SEO (máximo 60 caracteres)",
  "meta_description": "meta description (150-155 caracteres exactos)",
  "slug": "url-amigable-sin-tildes-ni-espacios",
  "categoria": "Nuevos Lanzamientos",
  "tags": ["tag1", "tag2", "tag3"],
  "imagen_prompt": "prompt fotografico en inglés para imagen de la moto",
  "imagenes_secciones": []
}}

Responde SOLO el JSON, sin texto antes ni después, sin backticks."""

    # Prompt de COMPETICIÓN — resultados, datos, contexto de campeonato
    elif es_competicion:
        prompt = f"""Sos {voz['nombre']}, periodista de motos que escribe para La Banda Motera desde {voz['ubicacion']}.
{voz['bio']}
Dialecto: {voz['dialecto']}

Escribi una nota de competición DIRECTA Y DINÁMICA sobre:

TITULO: {noticia['titulo']}
CONTEXTO: {noticia['resumen'][:500] if noticia.get('resumen') else 'Sin resumen'}
URL: {noticia.get('url', '')}

INSTRUCCIONES — NOTA DE COMPETICIÓN (700-900 palabras):
1. Abrí con el resultado central: quién ganó, en qué circuito, en qué campeonato.
2. Desarrollá el relato de la carrera o evento: momentos clave, drama, batallas.
3. Impacto en el campeonato: ¿cómo queda la tabla? ¿Qué significa para el título?
4. Contexto de los protagonistas: resultados previos, situación en el campeonato.
5. Párrafo de opinión editorial sobre lo que muestra esta carrera.
6. Usá 3-4 subtítulos H2 para estructurar.
7. Tono dinámico, como si contaras la carrera a alguien que no la vio.
8. NUNCA inventes resultados — solo lo que esté en el contexto provisto.

FORMATO JSON exacto:
{{
  "titulo": "titulo SEO atractivo (máximo 65 caracteres)",
  "bajada": "1-2 oraciones de gancho",
  "contenido_md": "la nota completa en markdown, 700-900 palabras",
  "seo_title": "titulo SEO (máximo 60 caracteres)",
  "meta_description": "meta description (150-155 caracteres exactos)",
  "slug": "url-amigable-sin-tildes-ni-espacios",
  "categoria": "Competición",
  "tags": ["tag1", "tag2", "tag3"],
  "imagen_prompt": "prompt fotografico en inglés",
  "imagenes_secciones": [
    {{"seccion": "titulo exacto H2", "busqueda": "descripcion imagen"}}
  ]
}}

Responde SOLO el JSON, sin texto antes ni después, sin backticks."""

    # Detectar si es Historias Moteras
    es_historia = any(k in titulo_lower + resumen_lower for k in [
        'historia', 'historico', 'icono', 'iconica', 'legendario', 'clasico',
        'cultura', 'motera', 'motero', 'origenes', 'fundacion', 'nacio',
        'personaje', 'piloto legendario', 'marca historica', 'moto clasica',
        'cafe racer', 'scrambler historia', 'custom historia', 'born to ride',
        'comunidad', 'estilo de vida', 'lifestyle moto',
    ])

    # Prompt de HISTORIAS MOTERAS — narrativo, cultural, evocador
    if es_historia and not es_lanzamiento and not es_competicion:
        prompt = f"""Sos {voz['nombre']}, periodista de motos que escribe para La Banda Motera desde {voz['ubicacion']}.
{voz['bio']}
Dialecto: {voz['dialecto']}

Escribi un artículo de CULTURA E HISTORIA MOTERA, narrativo y evocador, sobre:

TITULO: {noticia['titulo']}
CONTEXTO: {noticia['resumen'][:500] if noticia.get('resumen') else 'Sin resumen'}
URL: {noticia.get('url', '')}

INSTRUCCIONES — HISTORIA/CULTURA MOTERA (1200-1600 palabras):
1. Tono narrativo, evocador, casi literario. Como si contaras una historia alrededor del fuego.
2. Contexto histórico rico: fechas, personajes, hitos técnicos o culturales.
3. Conectá el pasado con el presente: ¿por qué importa esto hoy?
4. Si es sobre una moto icónica: motor, diseño, por qué marcó una época, quiénes la pilotaron.
5. Si es sobre una marca: sus orígenes, fundadores, filosofía, modelos que la definieron.
6. Si es sobre cultura/personajes: el impacto en la comunidad motera, anécdotas, legado.
7. Opinión editorial al final: qué nos deja este pedazo de historia.
8. 4-5 H2 para estructurar. Tono más pausado y reflexivo que una nota de lanzamiento.
9. NUNCA copies texto fuente. Todo original desde tu conocimiento.

FORMATO JSON exacto:
{{
  "titulo": "titulo SEO atractivo (máximo 65 caracteres)",
  "bajada": "1-2 oraciones evocadoras de gancho",
  "contenido_md": "el artículo completo en markdown, 1200-1600 palabras, 4-5 H2",
  "seo_title": "titulo SEO (máximo 60 caracteres)",
  "meta_description": "meta description (150-155 caracteres exactos)",
  "slug": "url-amigable-sin-tildes-ni-espacios",
  "categoria": "Historias Moteras",
  "tags": ["tag1", "tag2", "tag3"],
  "imagen_prompt": "prompt fotografico en inglés para imagen evocadora",
  "imagenes_secciones": []
}}

Responde SOLO el JSON, sin texto antes ni después, sin backticks."""

    # Prompt de REVIEW / COMPARATIVA / MARCAS — extenso, profundo, ~2420 palabras
    else:
        prompt = f"""Sos {voz['nombre']}, periodista de motos que escribe para La Banda Motera desde {voz['ubicacion']}.
{voz['bio']}
Dialecto: {voz['dialecto']}

Escribi un articulo editorial EXTENSO, RICO y DETALLADO sobre:

TITULO DE REFERENCIA: {noticia['titulo']}
FUENTE/CONTEXTO: {noticia['resumen'][:600] if noticia.get('resumen') else 'Sin resumen disponible'}
URL FUENTE: {noticia.get('url', '')}

INSTRUCCIONES CRÍTICAS:
1. ~2.420 palabras totales (título + bajada + firma + subtítulos + cuerpo). Piso, no techo.
2. Desarrollá en profundidad: contexto histórico de la marca/segmento, motor y prestaciones con detalle técnico real, suspensión y ciclística, frenos y electrónica, ergonomía, diseño y calidad percibida, comparación con AL MENOS DOS rivales directos reales, precio y posicionamiento, conclusión editorial fuerte.
3. Cada bloque merece su H2 y al menos 150-200 palabras de desarrollo real con datos.
4. El lector termina sabiendo exactamente: motor, potencia, torque, tecnología, precio aproximado, puntos fuertes y débiles.
5. Opinión editorial fundamentada. No seas neutro.
6. Dialecto natural del perfil, sin exagerar.
7. NUNCA menciones "según la fuente" ni copies texto fuente.
8. Mínimo 7-8 H2. Incluye sección "Ficha técnica rápida" antes de la conclusión.

IMÁGENES POR SECCIÓN: entre 4 y 6 imágenes distribuidas. Para cada una:
- "seccion": título EXACTO del H2 donde va (debe coincidir letra por letra)
- "busqueda": descripción corta en español para buscar en páginas oficiales o revistas

FORMATO JSON exacto:
{{
  "titulo": "titulo SEO atractivo (máximo 65 caracteres)",
  "bajada": "gancho de 2-3 oraciones",
  "contenido_md": "artículo completo en markdown, mínimo 7-8 H2, ~2420 palabras",
  "seo_title": "titulo SEO (máximo 60 caracteres)",
  "meta_description": "meta description (150-155 caracteres exactos)",
  "slug": "url-amigable-sin-tildes-ni-espacios",
  "categoria": "una de: Reviews | Comparativas | Marcas | Historias Moteras",
  "tags": ["tag1", "tag2", "tag3", "tag4"],
  "imagen_prompt": "prompt fotografico en inglés para imagen destacada",
  "imagenes_secciones": [
    {{"seccion": "titulo exacto H2", "busqueda": "descripcion imagen"}}
  ]
}}

Responde SOLO el JSON, sin texto antes ni después, sin backticks."""


    # Tokens adaptados por tipo: lanzamiento=2000, competicion=4000, review=8000
    max_tok = 2000 if es_lanzamiento else (4000 if es_competicion else 8000)
    r = requests.post(
        "https://api.anthropic.com/v1/messages",
        headers={
            "x-api-key": ANTHROPIC_API_KEY,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        },
        json={
            "model": "claude-sonnet-4-6",
            "max_tokens": max_tok,
            "messages": [{"role": "user", "content": prompt}],
        },
    )
    r.raise_for_status()
    raw = r.json()["content"][0]["text"].strip()

    # Limpiar posibles backticks
    raw = re.sub(r"^```json\s*", "", raw)
    raw = re.sub(r"\s*```$", "", raw)

    import json
    return json.loads(raw)

def editar_noticias(noticias):
    """Procesa todas las noticias y devuelve articulos listos para publicar."""
    articulos = []
    for i, n in enumerate(noticias, 1):
        print(f"  -> Articulo {i}/{len(noticias)}: {n['titulo'][:60]}...")
        try:
            voz = elegir_voz(n["titulo"], n.get("url", ""), resumen=n.get("resumen", ""), indice_articulo=i-1)
            art = generar_articulo(n, voz)

            # Enriquecer con metadata
            art["autor"] = voz["nombre"]
            # Agregar firma visible al inicio del contenido_md
            firma = f"*Por {voz['nombre']} — La Banda Motera*\n\n"
            art["contenido_md"] = firma + art.get("contenido_md", "")
            art["titulo_original"] = n["titulo"]
            art["url_fuente"] = n.get("url", "")

            # Buscar video de YouTube relevante
            yt = buscar_video_youtube(n["titulo"])
            art["youtube"] = yt

            # Imagen de la moto
            art["imagen_fuente"] = buscar_imagen_moto(n["titulo"])

            articulos.append(art)
        except Exception as e:
            print(f"  [Editor] Error en articulo {i}: {e}")
            continue
    return articulos
