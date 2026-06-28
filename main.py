"""
main.py â Orquestador principal de MotoPress Bot.
Corre: Scout â Editor â Publisher â guarda hashes publicados.
Invocado por GitHub Actions cada 6 horas.
"""
import json, os, sys
from agents.scout     import run as scout_run, save_published
from agents.editor    import generar_articulo
from agents.publisher import publicar

LOG_FILE = "published_hashes.json"

def cargar_hashes():
    try:
        with open(LOG_FILE) as f:
            return set(json.load(f))
    except FileNotFoundError:
        return set()

def guardar_hashes(hashes):
    with open(LOG_FILE, "w") as f:
        json.dump(list(hashes), f)

def main():
    print("=" * 50)
    print(f"ðï¸  MotoPress Bot â {__import__('datetime').datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print("=" * 50)
    print("\n[1/3] Scout buscando noticias...")
    noticias = scout_run()
    if not noticias:
        print("Sin noticias nuevas. Hasta la prÃ³xima.")
        sys.exit(0)
    print(f"\n[2/3] Editor procesando {len(noticias)} noticias...")
    articulos = []
    for i, noticia in enumerate(noticias, 1):
        print(f"  â ArtÃ­culo {i}/{len(noticias)}: {noticia['title'][:60]}...")
        try:
            art = generar_articulo(noticia)
            articulos.append(art)
        except Exception as e:
            print(f"  â ï¸  Error: {e}")
    print(f"\n[3/3] Publisher subiendo {len(articulos)} artÃ­culos...")
    nuevos_hashes = set(hashes_publicados)
    for art in articulos:
        resultado = publicar(art)
        if resultado.get("ok"):
            nuevos_hashes.add(art["fuente_hash"])
    guardar_hashes(nuevos_hashes)
    print(f"\nâ Corrida completa. {len(articulos)} artÃ­culos procesados.")

if __name__ == "__main__":
    main()
