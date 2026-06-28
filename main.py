"""
main.py - Orquestador principal de La Banda Motera Bot.
Flujo: Scout -> Editor -> Publisher
"""
import sys
from datetime import datetime
from agents.scout import buscar_noticias
from agents.editor import editar_noticias
from agents.publisher import publicar

def main():
    print("=" * 50)
    print(f"  MotoPress Bot - {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print("=" * 50)

    # 1. Scout: buscar noticias nuevas
    print("\n[1/3] Scout buscando noticias...")
    noticias = buscar_noticias(max_noticias=5)

    if not noticias:
        print("Sin noticias nuevas. Hasta la proxima.")
        sys.exit(0)

    # 2. Editor: generar articulos
    print(f"\n[2/3] Editor procesando {len(noticias)} noticias...")
    articulos = editar_noticias(noticias)

    if not articulos:
        print("No se generaron articulos.")
        sys.exit(0)

    # 3. Publisher: publicar en WordPress
    print(f"\n[3/3] Publisher subiendo {len(articulos)} articulos...")
    ok = 0
    for a in articulos:
        resultado = publicar(a)
        if resultado.get("ok"):
            ok += 1

    print(f"\n Corrida completa. {ok}/{len(articulos)} articulos procesados.")

if __name__ == "__main__":
    main()
