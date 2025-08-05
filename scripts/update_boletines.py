import os
import re
import json

VERSION = "1.0.3"
CHUNKS_DIR = "json_chunks"
OUTPUT_FILE = "boletines.jsonl"

def cargar_boletines_desde_archivo(ruta):
    boletines = []
    if os.path.exists(ruta):
        with open(ruta, "r", encoding="utf-8") as f:
            for linea in f:
                try:
                    boletines.append(json.loads(linea))
                except json.JSONDecodeError as e:
                    print(f"Error decodificando JSON en {ruta}: {e}")
    return boletines

def obtener_boletines_de_chunks():
    boletines = []
    archivos = sorted([
        f for f in os.listdir(CHUNKS_DIR) if f.endswith(".jsonl")
    ])
    print(f"[INFO] Archivos encontrados en {CHUNKS_DIR}: {archivos}")
    for archivo in archivos:
        ruta = os.path.join(CHUNKS_DIR, archivo)
        boletines += cargar_boletines_desde_archivo(ruta)
    return boletines

def unificar_boletines(boletines):
    unificados = {}
    for b in boletines:
        b_id = b.get("id")
        if not b_id:
            print(f"[WARN] Boletín sin ID: {b}")
            continue
        if b_id not in unificados:
            unificados[b_id] = b
        else:
            # Podés modificar esta lógica para manejo de duplicados
            unificados[b_id] = b
    return list(unificados.values())

def main():
    print(f"Versión del script: {VERSION}")

    print("Cargando boletines existentes...")
    existentes = cargar_boletines_desde_archivo(OUTPUT_FILE)

    print("Cargando boletines desde chunks...")
    nuevos = obtener_boletines_de_chunks()

    all_data = existentes + nuevos

    # Último nro seguro (evita KeyError)
    last_boletin = next(
        (item['nro'] for item in reversed(all_data) if isinstance(item, dict) and 'nro' in item),
        "Desconocido"
    )

    print(f"Archivos JSONL en disco: {sorted(os.listdir(CHUNKS_DIR))}")
    print(f"Último boletín procesado (nro): {last_boletin}")

    unificados = unificar_boletines(all_data)

    # Opcional: ordenar por nro o fecha, según tengas campo
    unificados.sort(key=lambda x: x.get("nro", 0), reverse=True)

    print(f"Guardando {len(unificados)} boletines unificados en {OUTPUT_FILE}...")
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        for b in unificados:
            f.write(json.dumps(b, ensure_ascii=False) + "\n")

    print("Proceso completado con éxito.")

if __name__ == "__main__":
    main()
