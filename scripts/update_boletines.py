"""
update_boletines.py - Versión 1.0.2
Actualiza el archivo boletines.jsonl unificando todos los jsonl de la carpeta json_chunks,
evitando duplicados según el campo "id" y ordenando por fecha.
"""

import os
import json
from datetime import datetime

VERSION = "1.0.2"
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

def normalizar_fecha(boletin):
    fecha_str = boletin.get("fecha", "")
    formatos = ["%Y-%m-%d", "%d-%m-%Y", "%Y/%m/%d"]
    for formato in formatos:
        try:
            return datetime.strptime(fecha_str, formato)
        except ValueError:
            continue
    print(f"[WARN] Fecha inválida o ausente en boletín ID {boletin.get('id')}: {fecha_str}")
    return datetime.min

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
            # Si hay conflicto de datos, se puede ajustar esta lógica
            unificados[b_id] = b
    return list(unificados.values())

def guardar_boletines(boletines, ruta):
    with open(ruta, "w", encoding="utf-8") as f:
        for b in boletines:
            f.write(json.dumps(b, ensure_ascii=False) + "\n")
    print(f"[OK] Se guardaron {len(boletines)} boletines únicos en {ruta}")

def main():
    print(f"== update_boletines.py (versión {VERSION}) ==")
    existentes = cargar_boletines_desde_archivo(OUTPUT_FILE)
    nuevos = obtener_boletines_de_chunks()
    todos = existentes + nuevos
    unificados = unificar_boletines(todos)
    unificados.sort(key=normalizar_fecha, reverse=True)
    guardar_boletines(unificados, OUTPUT_FILE)

if __name__ == "__main__":
    main()
