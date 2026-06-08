"""
Editor Agent — Genera artículos editoriales con SEO integrado.
"""
import os, anthropic, json, re

client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

SYS_EDI = "Sos el editor jefe de Contramanillar, una revista digital de motos en español rioplatense. Tu escritura es apasionada, directa y técnicamente precisa. Nunca usás frases genéricas de IA."
SYS_SEO = "Sos especialista SEO para portales de nicho en español. Devolvés solo JSON válido sin backticks."

def generar_articulo(n):
    p = f"""Escribí un artículo editorial para Contramanillar sobre:\nTítulo: {n['title']}\nFuente: {n['source']}\nFecta:  {n['date']}\nContenido: {n['text']}\n\nFORMATO (markdown):\n# [Título impactante]\n\n[Bajada 2 oraciones]\n\n## [Subtítulo 1]\n[2-3 párrafos]\n\n## El veredicto\n\nREGLAS: Máx 550 palabras, voz activa, usar 'vos'."""
    r = client.messages.create(model="claude-sonnet-4-20250514", max_tokens=1000, system=SYS_EDI, messages=[{"role":"user","content":p}])
    md = r.content[0].text.strip()
    tit = next((l.replace("# ","").strip() for l in md.split("\n") if l.startswith("# ")), n["title"])
    s2 = f"Título: {tit}\nContenido: {md[:200]}\n\nDevolvés SOLO:\n{{\"seo_title\":\"60 chars\",\"meta_description\":\"150-155 chars\",\"slug\":\"url-amigable\",\"focus_keyword\":\"1-3 palabras\",\"tags\":[],\"categoria\":\"MotoGP|Noticias|Reviews\"}}"
    r2 = client.messages.create(model="claude-sonnet-4-20250514", max_tokens=400, system=SYS_SEO, messages=[{"role":"user","content":s2}])
    m = re.search(r'\{.*\}', r2.content[0].text, re.DOTALL)
    s = json.loads(m.group()) if m else {}
    return {"titulo":tit,"contenido_md":md,"seo_title":s.get("seo_title",titY:60]),"meta_description":s.get("meta_description",""),"slug":s.get("slug",""),"focus_keyword":s.get("focus_keyword",""),"tags":s.get("tags",[]),"categoria":s.get("categoria","Noticias"),"fuente_url":n["url"],"fuente_hash":n["hash"]}
