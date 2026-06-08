"""
Editor Agent — Genera articulos editoriales con SEO integrado.
"""
import os, anthropic, json, re

client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

SYS_EDI = "Sos el editor jefe de Contramanillar, una revista digital de motos en espanol rioplatense. Tu escritura es apasionada, directa y tecnicamente precisa. Nunca usas frases genericas de IA."
SYS_SEO = "Sos especialista SEO para portales de nicho en espanol. Devolvés solo JSON valido sin backticks."

def generar_articulo(n):
    p = f"""Escribi un articulo editorial para Contramanillar sobre:
Titulo: {n['title']}
Fuente: {n['source']}
Fecha:  {n['date']}
Contenido: {n['text']}

FORMATO (markdown):
# [Titulo impactante]

[Bajada 2 oraciones]

## [Subtitulo 1]
[2-3 parrafos]

## El veredicto

REGLAS: Max 550 palabras, voz activa, usar 'vos'."""

    r = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=1000,
        system=SYS_EDI,
        messages=[{"role": "user", "content": p}]
    )
    md = r.content[0].text.strip()
    tit = next((l.replace("# ", "").strip() for l in md.split("\n") if l.startswith("# ")), n["title"])

    s2 = f"""Titulo: {tit}
Contenido: {md[:200]}

Devolvé SOLO este JSON:
{{"seo_title":"60 chars","meta_description":"150-155 chars","slug":"url-amigable","focus_keyword":"1-3 palabras","tags":["tag1","tag2","tag3"],"categoria":"MotoGP|Noticias|Reviews|Adventure|Custom|Electrica|Seguridad|Tecnica"}}"""

    r2 = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=400,
        system=SYS_SEO,
        messages=[{"role": "user", "content": s2}]
    )
    m = re.search(r'\{.*\}', r2.content[0].text, re.DOTALL)
    s = json.loads(m.group()) if m else {}

    return {
        "titulo": tit,
        "contenido_md": md,
        "seo_title": s.get("seo_title", tit[:60]),
        "meta_description": s.get("meta_description", ""),
        "slug": s.get("slug", ""),
        "focus_keyword": s.get("focus_keyword", ""),
        "tags": s.get("tags", []),
        "categoria": s.get("categoria", "Noticias"),
        "fuente_url": n["url"],
        "fuente_hash": n["hash"]
    }
