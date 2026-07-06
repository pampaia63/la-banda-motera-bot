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

    es_mecanica = any(k in titulo_lower + resumen_lower for k in [
        'desmodromic', 'desmo', 'telelever', 'duolever', 'paralever',
        'boxer', 'motor boxer', 'v-twin', 'inline four', 'cuatro cilindros',
        'refrigeracion liquida', 'refrigeracion aire', 'inyeccion electronica',
        'carburador', 'frenos abs', 'control traccion', 'quickshifter',
        'autoblipper', 'suspension', 'horquilla invertida', 'monoshock',
        'monoamortiguador', 'basculante', 'chasis tubular', 'chasis perimetral',
        'mecanica', 'tecnica', 'sistema', 'funcionamiento', 'como funciona',
        'tecnologia moto', 'ingenieria moto', 'transmision cadena',
        'transmision correa', 'transmision cardan', 'embrague', 'caja cambios',
        'valvulas', 'arbol levas', 'cigüeñal', 'pistones', 'lubricacion',
        'refrigeracion', 'escape', 'escape moto',
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

INSTRUCCIONES — NOTA DE LANZAMIENTO (800-1000 palabras):
1. Abrí con 2-3 oraciones de contexto editorial: por qué importa esta moto en el mercado actual.
2. Contexto del segmento: qué lugar ocupa esta moto en el mercado, cómo llegó la marca hasta acá, qué vacío viene a llenar.
3. Ficha técnica COMPLETA y detallada: motor, potencia, torque, cilindrada, refrigeración, caja de cambios, peso, altura de asiento, capacidad de tanque, neumáticos, frenos, suspensiones, electrónica.
4. Mercados de lanzamiento: ¿dónde llega? ¿Argentina, España, México? ¿Cuándo? ¿A qué precio?
5. Equipamiento destacado: qué trae de serie que la diferencia de la competencia.
6. Análisis de rivales directos: compará con al menos 2 modelos que compiten en el mismo segmento, precio y perfil.
7. ¿Para quién es esta moto? Perfil del usuario ideal.
8. Cierre con opinión editorial clara y fundamentada: ¿llega a tiempo? ¿Tiene sentido? ¿Qué le falta?
9. Usá 3-4 subtítulos H2 (## en markdown) para estructurar bien el artículo.
10. NO es una review de manejo, pero sí un análisis editorial profundo basado en specs y contexto de mercado.
11. Usá el dialecto de tu perfil de forma natural.
12. NUNCA copies el texto fuente — todo original desde tu conocimiento.
IMPORTANTE: El artículo debe tener entre 800 y 1000 palabras. Desarrollá cada sección con datos concretos y análisis editorial real, sin relleno.

FORMATO JSON exacto:
{{
  "titulo": "titulo SEO atractivo (máximo 65 caracteres)",
  "bajada": "1-2 oraciones de gancho para el lector",
  "contenido_md": "la nota completa en markdown, 800-1000 palabras, mínimo 5 H2",
  "seo_title": "titulo SEO (máximo 60 caracteres)",
  "meta_description": "meta description (150-155 caracteres exactos)",
  "slug": "url-amigable-sin-tildes-ni-espacios",
  "categoria": "Nuevos Lanzamientos",
  "tags": ["tag1", "tag2", "tag3"],
  "imagen_prompt": "prompt fotografico en inglés para imagen de la moto",
  "imagenes_secciones": []
}}

Responde SOLO el JSON, sin texto antes ni después, sin backticks."""

    # Prompt de MECÁNICA — explicación técnica + comparativa con sistema convencional
    elif es_mecanica:
        prompt = f"""Sos {voz['nombre']}, periodista de motos que escribe para La Banda Motera desde {voz['ubicacion']}.
{voz['bio']}
Dialecto: {voz['dialecto']}

Escribi un artículo de MECÁNICA Y TECNOLOGÍA MOTERA, educativo, claro y apasionante sobre:

TITULO: {noticia['titulo']}
CONTEXTO: {noticia['resumen'][:500] if noticia.get('resumen') else 'Sin resumen'}
URL: {noticia.get('url', '')}

INSTRUCCIONES — ARTÍCULO DE MECÁNICA (1200-1500 palabras):
1. Abrí con un párrafo de enganche: por qué este sistema o tecnología importa, qué problema vino a resolver.
2. Explicá cómo funciona el sistema en detalle: componentes, principio físico, cómo interactúan las partes. Usá analogías simples para que lo entienda alguien que no es ingeniero.
3. Historia y origen: quién lo inventó o desarrolló, en qué año, qué moto lo estrenó, cómo evolucionó.
4. COMPARATIVA CON EL SISTEMA CONVENCIONAL: dedicá una sección completa a comparar este sistema con la solución tradicional (ej: Desmodromic vs resortes convencionales, Telelever vs horquilla telescópica, etc.). Ventajas y desventajas de cada uno, con datos concretos.
5. Motos que lo usan hoy: modelos actuales que equipa este sistema, en qué segmentos se encuentra.
6. ¿Vale la pena? Opinión editorial fundamentada: ¿es este sistema superior en todos los casos? ¿Tiene sentido en motos de calle? ¿Cuándo conviene y cuándo no?
7. Datos técnicos donde corresponda: tolerancias, materiales, diferencias de mantenimiento, costos de servicio.
8. Usá 5-6 H2 para estructurar. Tono educativo pero apasionado, no un manual de taller.
9. Terminá con algo que el lector pueda llevarse: una frase o conclusión que cambie cómo mira esa tecnología.
10. NUNCA inventes datos técnicos que no conozcas — si hay incertidumbre, marcala.
IMPORTANTE: El artículo debe tener entre 1200 y 1500 palabras. Explicá bien, no apures.

FORMATO JSON exacto:
{{
  "titulo": "titulo SEO atractivo (máximo 65 caracteres)",
  "bajada": "1-2 oraciones que expliquen de qué trata y por qué vale leerlo",
  "contenido_md": "el artículo completo en markdown, 1200-1500 palabras, 5-6 H2",
  "seo_title": "titulo SEO (máximo 60 caracteres)",
  "meta_description": "meta description (150-155 caracteres exactos)",
  "slug": "url-amigable-sin-tildes-ni-espacios",
  "categoria": "Mecánica",
  "tags": ["tag1", "tag2", "tag3", "tag4"],
  "imagen_prompt": "prompt fotografico en inglés mostrando el sistema mecánico",
  "imagenes_secciones": [
    {{"seccion": "titulo exacto H2", "busqueda": "descripcion imagen técnica"}}
  ]
}}

Responde SOLO el JSON, sin texto antes ni después, sin backticks."""

    # Detectar si es Historias Moteras / Cultura
    es_historia = any(k in titulo_lower + resumen_lower for k in [
        'historia', 'historico', 'icono', 'iconica', 'legendario', 'clasico',
        'cultura', 'motera', 'motero', 'origenes', 'fundacion', 'nacio',
        'personaje', 'piloto legendario', 'marca historica', 'moto clasica',
        'cafe racer', 'scrambler historia', 'custom historia', 'born to ride',
        'comunidad', 'estilo de vida', 'lifestyle moto', 'patrimonio',
        'aniversario', 'cumple anos', 'decadas', 'historia de la marca',
        'evolucion', 'generaciones', 'clasico moderno',
    ])

    # Prompt de HISTORIAS MOTERAS — narrativo, cultural, evocador
    if es_historia and not es_lanzamiento and not es_mecanica:
        prompt = f"""Sos {voz['nombre']}, periodista de motos que escribe para La Banda Motera desde {voz['ubicacion']}.
{voz['bio']}
Dialecto: {voz['dialecto']}

Escribi un artículo de CULTURA E HISTORIA MOTERA, narrativo y evocador, sobre:

TITULO: {noticia['titulo']}
CONTEXTO: {noticia['resumen'][:500] if noticia.get('resumen') else 'Sin resumen'}
URL: {noticia.get('url', '')}

INSTRUCCIONES — HISTORIA Y CULTURA MOTERA (1200-1600 palabras):
Este artículo NO es una review de manejo ni una prueba técnica. Es un artículo de fondo sobre historia, cultura, identidad y significado.

1. Tono narrativo, evocador, casi literario. Como si contaras una historia alrededor del fuego. El lector tiene que sentir que está leyendo algo que vale la pena leer despacio.
2. Contexto histórico rico: fechas exactas, nombres de personas reales, hitos técnicos o culturales concretos. No generalidades — datos que anclen la historia en la realidad.
3. Conectá el pasado con el presente: ¿por qué importa esto hoy? ¿Qué dejó en la cultura motera contemporánea?
4. Si es sobre una moto icónica: cómo nació el proyecto, decisiones de diseño que la definieron, por qué marcó una época, quiénes la pilotaron, cómo fue recibida en su momento vs. cómo se la valora hoy.
5. Si es sobre una marca: orígenes, fundadores y su visión, crisis y renacimientos, filosofía que la distingue, modelos que la definieron en cada era.
6. Si es sobre cultura motera (café racer, scrambler, custom, etc.): dónde y cuándo surgió, qué lo impulsó, cómo evolucionó, quiénes son sus referentes actuales, por qué sigue vigente.
7. Si es sobre un piloto o personaje: su impacto real en el deporte o la cultura, anécdotas concretas, lo que cambió gracias a él/ella, cómo se lo recuerda hoy.
8. Párrafo de opinión editorial al final: qué nos deja esta historia, qué podemos aprender de ella, cómo cambia la forma de ver las motos de hoy.
9. 4-5 H2 para estructurar. Tono más pausado y reflexivo que una nota de lanzamiento. No tengas apuro.
10. NUNCA copies texto fuente. Todo original desde tu conocimiento y desde el contexto provisto.
11. NO describas cómo se maneja la moto, no hagas análisis de suspensiones ni frenos desde la perspectiva de un test de ruta. Eso es una review. Esto es historia.
IMPORTANTE: El artículo completo debe tener MÍNIMO 1200 palabras (idealmente 1400-1600). Desarrollá con riqueza narrativa real.

FORMATO JSON exacto:
{{
  "titulo": "titulo SEO atractivo y narrativo (máximo 65 caracteres)",
  "bajada": "1-2 oraciones evocadoras que hagan querer seguir leyendo",
  "contenido_md": "el artículo completo en markdown, 1200-1600 palabras, 4-5 H2",
  "seo_title": "titulo SEO (máximo 60 caracteres)",
  "meta_description": "meta description narrativa (150-155 caracteres exactos)",
  "slug": "url-amigable-sin-tildes-ni-espacios",
  "categoria": "Historias Moteras",
  "tags": ["tag1", "tag2", "tag3", "tag4"],
  "imagen_prompt": "prompt fotografico en inglés para imagen evocadora, vintage o cultural",
  "imagenes_secciones": []
}}

Responde SOLO el JSON, sin texto antes ni después, sin backticks."""

    # Prompt de COMPARATIVAS / MARCAS — extenso, profundo, ~2420 palabras
    # NOTA: Las reviews de manejo las genera Isaías Rider desde su canal de YouTube.
    # El bot genera solo Comparativas y artículos de Marcas.
    else:
        prompt = f"""Sos {voz['nombre']}, periodista de motos que escribe para La Banda Motera desde {voz['ubicacion']}.
{voz['bio']}
Dialecto: {voz['dialecto']}

Escribi un articulo editorial EXTENSO, RICO y DETALLADO sobre:

TITULO DE REFERENCIA: {noticia['titulo']}
FUENTE/CONTEXTO: {noticia['resumen'][:600] if noticia.get('resumen') else 'Sin resumen disponible'}
URL FUENTE: {noticia.get('url', '')}

INSTRUCCIONES CRÍTICAS:
1. ~2.420 palabras totales (título + bajada + firma + subtítulos + cuerpo). Piso ABSOLUTO mínimo 1000 palabras, objetivo 2420.
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
  "categoria": "una de: Comparativas | Marcas",
  "tags": ["tag1", "tag2", "tag3", "tag4"],
  "imagen_prompt": "prompt fotografico en inglés para imagen destacada",
  "imagenes_secciones": [
    {{"seccion": "titulo exacto H2", "busqueda": "descripcion imagen"}}
  ]
}}

Responde SOLO el JSON, sin texto antes ni después, sin backticks."""


    # Tokens adaptados por tipo: lanzamiento=2000, competicion=4000, review=8000
    max_tok = 4000 if es_lanzamiento else (6000 if es_mecanica else 8000)
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
