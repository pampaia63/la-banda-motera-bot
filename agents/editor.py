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

def elegir_voz(titulo, url=""):
    """Asigna una voz segun palabras clave del tema."""
    text = (titulo + " " + url).lower()
    if any(k in text for k in ["espana", "madrid", "barcelona", "espanol", "iberia", "euro"]):
        return VOCES["ES"]
    if any(k in text for k in ["mexico", "cdmx", "italika", "vento", "carabela", "jalisco"]):
        return VOCES["MX"]
    if any(k in text for k in ["colombia", "bogota", "peru", "ecuador", "bolivia", "akt"]):
        return VOCES["CO"]
    return VOCES["AR"]  # default: Mateo Quiroga para todo LATAM generico

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
    """Genera un articulo editorial rico, con specs reales y conocimiento profundo."""

    prompt = f"""Sos {voz['nombre']}, periodista de motos que escribe para La Banda Motera desde {voz['ubicacion']}.
{voz['bio']}
Dialecto: {voz['dialecto']}

Escrihi un articulo editorial EXTENSO y RICO sobre la siguiente noticia de motos:

TITULO DE REFERENCIA: {noticia['titulo']}
FUENTE/CONTEXTO: {noticia['resumen'][:600] if noticia.get('resumen') else 'Sin resumen disponible'}
URL FUENTE: {noticia.get('url', '')}

INSTRUCCIONES CRITICAS:
1. El articulo debe tener entre 700 y 1000 palabras. No menos.
2. El lector debe terminar de leer sabiendo exactamente de que moto hablamos: motor, potencia, tecnologia, precio aproximado si se conoce, puntos fuertes y debiles reales.
3. Compara la moto con al menos UNO o DOS rivales directos del mercado (motos reales, no inventadas).
4. Da tu opinion editorial fundamentada. No seas neutro ni tibio - tenes que tener una postura.
5. Usa el dialecto de tu perfil de forma natural, sin exagerar.
6. NUNCA menciones "segun la fuente" ni atribuyas texto a un periodista externo. Vos sos el unico autor.
7. NUNCA copies texto de la fuente - todo es original.
8. Estructura con subtitulos (usa ## para H2 y ### para H3 en markdown).
9. Incluye una seccion "Ficha tecnica rapida" con los datos clave en formato lista al final.
10. Termina con un parrafo de conclusion que sea opinion editorial fuerte.

FORMATO DE RESPUESTA - JSON con esta estructura exacta:
{{
  "titulo": "titulo SEO atractivo (maximo 65 caracteres)",
  "bajada": "primer parrafo de gancho (2-3 oraciones que enganchen al lector)",
  "contenido_md": "el articulo completo en markdown (sin el titulo ni la bajada que ya van aparte)",
  "seo_title": "titulo para SEO (maximo 60 caracteres)",
  "meta_description": "meta description (150-155 caracteres exactos)",
  "slug": "url-amigable-sin-tildes-ni-espacios",
  "categoria": "una de: Noticias | Reviews | Adventure | Electrica | MotoGP | Custom | Seguridad | Tecnica",
  "tags": ["tag1", "tag2", "tag3", "tag4"],
  "imagen_prompt": "prompt fotografico en ingles para generar imagen IA de la moto: marca modelo año, tipo de moto, colores, fondo neutro, sin personas, alta calidad fotografica, photorealistic"
}}

Responde SOLO el JSON, sin texto antes ni despues, sin backticks."""

    r = requests.post(
        "https://api.anthropic.com/v1/messages",
        headers={
            "x-api-key": ANTHROPIC_API_KEY,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        },
        json={
            "model": "claude-sonnet-4-6",
            "max_tokens": 4000,
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
            voz = elegir_voz(n["titulo"], n.get("url", ""))
            art = generar_articulo(n, voz)

            # Enriquecer con metadata
            art["autor"] = voz["nombre"]
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
