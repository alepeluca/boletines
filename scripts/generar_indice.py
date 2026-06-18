#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
generar_indice.py
----------------
Genera un CSV consolidando versiones de licitaciones.
"""

import json
import csv
import re
from pathlib import Path
from collections import defaultdict

BASE_DIR = Path(__file__).resolve().parent.parent
CHUNKS_DIR = BASE_DIR / "json_chunks"
OUTPUT_CSV = BASE_DIR / "indice_documentos.csv"

def mapear_categoria(ruta_archivo):
    # La carpeta json_chunks/lici/ indica la categoría
    if "lici" in str(ruta_archivo):
        return "licitaciones"
    elif "taqui" in str(ruta_archivo):
        return "taquigraficas"
    elif "orden" in str(ruta_archivo) or "hcd" in str(ruta_archivo):
        return "ordenes"
    elif "bolet" in str(ruta_archivo):
        return "boletines"
    return "otros"

def extraer_info_licitacion(fragmento):
    match = re.search(r'OBJETO:\s*[“"\'«]?([^”"\'»\n\r]+)', fragmento, re.IGNORECASE)
    if match:
        return match.group(1).strip().title()
    return ""

def generar_indice():
    print("[INFO] Iniciando compilación de índice CSV con agrupación de licitaciones...")
    
    # Estructura: grupos[base_id] = { 'info': '...', 'items': [] }
    grupos = defaultdict(lambda: {'info': None, 'items': []})
    otros_documentos = []

    archivos_jsonl = list(CHUNKS_DIR.rglob("*.jsonl"))

    for ruta_archivo in archivos_jsonl:
        categoria = mapear_categoria(ruta_archivo)
        
        with open(ruta_archivo, 'r', encoding='utf-8') as f:
            for linea in f:
                try:
                    chunk = json.loads(linea)
                    archivo_nombre = chunk.get("archivo", "")
                    url = chunk.get("url", "")
                    
                    if categoria == "licitaciones":
                        # Intentar extraer base ID: LiciPubli_033240-1.pdf -> 033240
                        match = re.search(r'LiciPubli_(\d+)(?:-(\d+))?', archivo_nombre)
                        if match:
                            base_id = match.group(1)
                            version = match.group(2) if match.group(2) else "1"
                            
                            info = extraer_info_licitacion(chunk.get("fragmento", ""))
                            
                            # Si este chunk tiene info, guardarla como la buena para el grupo
                            if info and not grupos[base_id]['info']:
                                grupos[base_id]['info'] = info
                            
                            grupos[base_id]['items'].append({
                                "categoria": categoria,
                                "url": url,
                                "archivo": archivo_nombre,
                                "version": version,
                                "fecha": chunk.get("fecha", ""),
                                "paginas": chunk.get("pagina", 1)
                            })
                        else:
                            # Caso raro que no siga el formato, tratar como otro
                            otros_documentos.append({**chunk, "categoria": categoria, "info": ""})
                    else:
                        otros_documentos.append({**chunk, "categoria": categoria, "info": ""})
                except:
                    continue

    # Escribir CSV
    columnas = ["categoria", "url", "fecha", "info", "paginas"]
    
    with open(OUTPUT_CSV, 'w', encoding='utf-8', newline='') as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=columnas)
        writer.writeheader()

        # 1. Escribir Licitaciones procesadas
        for base_id, grupo in grupos.items():
            info_final = grupo['info'] if grupo['info'] else "Licitación sin descripción"
            
            for item in grupo['items']:
                # Aquí pegamos el nombre modificado: "Nombre (N)"
                nombre_visual = f"{info_final}({item['version']})"
                writer.writerow({
                    "categoria": item['categoria'],
                    "url": item['url'],
                    "fecha": item['fecha'],
                    "info": nombre_visual,
                    "paginas": item['paginas']
                })

        # 2. Escribir el resto
        for doc in otros_documentos:
            writer.writerow({
                "categoria": doc.get("categoria"),
                "url": doc.get("url", ""),
                "fecha": doc.get("fecha", ""),
                "info": doc.get("info", ""),
                "paginas": doc.get("pagina", 1)
            })

    print(f"[✅] CSV generado con {len(grupos)} grupos de licitaciones y {len(otros_documentos)} documentos extra.")

if __name__ == "__main__":
    generar_indice()
