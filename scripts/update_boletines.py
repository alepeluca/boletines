# update_boletines.py - Versión 1.0.4

import os
import json
from datetime import datetime

VERSION = "1.0.4"
CHUNKS_DIR = "json_chunks"
OUTPUT_FILE = "boletines.jsonl"

print(f"Versión del script: {VERSION}")

def cargar_chunks():
    archivos = sorted([
        f for f in os.listdir(CHUNKS_DIR)
        if f.endswith(".jsonl")
    ])
    print(f"Archivos detectados: {archivos}")
    boletines = []
    for archivo in archivos:
        path = os.path.join(CHUNKS_DIR, archivo)
        with open(path, "r", encoding="utf-8") as f:
            for linea in f:
                boletines.append(json.loads(linea.strip()))
    return boletines

def guardar_jsonl(lista, path):
    with open(path, "w", encoding="utf-8") as f:
        for entrada in lista:
            f.write(json.dumps(entrada, ensure_ascii=False) + "\n")

def eliminar_duplicados(boletines):
    vistos = set()
    resultado = []
    for entrada in boletines:
        clave = (entrada.get("fecha", ""), entrada.get("nro_boletin", ""))
        if clave not in vistos:
            vistos.add(clave)
            resultado.append(entrada)
    return resultado

def convertir_fecha(fecha_str):
    for fmt in ("%Y-%m-%d", "%d-%m-%Y", "%d/%m/%Y"):
        try:
            return datetime.strptime(fecha_str, fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    return fecha_str  # si falla, devolver original

def normalizar_fechas(boletines):
    for entrada in boletines:
        if "fecha" in entrada:
            entrada["fecha"] = convertir_fecha(entrada["fecha"])
    return boletines

def main():
    boletines = cargar_chunks()
    print(f"Total cargados: {len(boletines)}")
    boletines = eliminar_duplicados(boletines)
    print(f"Sin duplicados: {len(boletines)}")
    boletines = normalizar_fechas(boletines)
    guardar_jsonl(boletines, OUTPUT_FILE)
    print(f"Guardado final en: {OUTPUT_FILE}")

if __name__ == "__main__":
    main()
