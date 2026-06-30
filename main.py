"""
main.py - Orquestador principal de La Banda Motera Bot.
Flujo: Scout -> Editor -> Publisher -> Actualizar Home
- Un articulo por dia: cada corrida genera N articulos y los programa
  en dias consecutivos (manana, pasado manana, etc.)
- Actualiza la pagina de portada automaticamente al final.
"""
import sys
from datetime import datetime, timedelta
from agents.scout import buscar_noticias
from agents.editor import editar_noticias
from agents.publisher import publicar, actualizar_home_portada

def main():
    print("=" * 50)
    print(f"  MotoPress Bot - {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print("=" * 50)

    # 1. Scout: buscar noticias nuevas
    print("\n[1/3] Scout buscando noticias...")
    noticias = buscar_noticias(max_noticias=4)  # max 4 = una por dia, 4 dias adelante

    if not noticias:
        print("Sin noticias nuevas. Hasta la proxima.")
        sys.exit(0)

    # 2. Editor: generar articulos
    print(f"\n[2/3] Editor procesando {len(noticias)} noticias...")
    articulos = editar_noticias(noticias)

    if not articulos:
        print("No se generaron articulos.")
        sys.exit(0)

    # 3. Publisher: publicar en WordPress — uno por dia, a las 10:00 AM hora Buenos Aires (UTC-3 = 13:00 UTC)
    print(f"\n[3/3] Publisher subiendo {len(articulos)} articulos (1 por dia)...")
    ok = 0
    publicados = []
    for i, a in enumerate(articulos):
        # Dia de publicacion: manana + i dias
        # Publica a las 10:00 AM hora Argentina (13:00 UTC)
        fecha_pub = datetime.utcnow().replace(hour=13, minute=0, second=0, microsecond=0) + timedelta(days=i+1)
        a["fecha_programada"] = fecha_pub.strftime("%Y-%m-%dT%H:%M:%S")

        resultado = publicar(a)
        if resultado.get("ok"):
            ok += 1
            publicados.append(resultado)
            print(f"  ✓ Programado para {fecha_pub.strftime('%d/%m/%Y 10:00 AR')}: {a.get('titulo','')[:50]}")

    # 4. Actualizar pagina de portada con los nuevos articulos
    if publicados:
        print("\n[4/4] Actualizando pagina de portada...")
        actualizar_home_portada()

    print(f"\n Corrida completa. {ok}/{len(articulos)} articulos procesados.")

if __name__ == "__main__":
    main()
