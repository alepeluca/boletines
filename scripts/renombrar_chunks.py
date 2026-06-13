#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
renombrar_chunks.py — Versión 1.0.0

FLUJO DE RENOMBRADO:
1. Recorre la carpeta 'json_chunks/' buscando los archivos originales 'licitaciones_part_*.jsonl'.
2. Abre la primera línea de cada archivo para leer la clave interna '"codigo"'.
3. Formatea el número del 'part' a 3 dígitos estrictos (ej: part_5 -> part005) para ordenamiento perfecto.
4. Renombra el archivo al nuevo formato requerido: lici_partXXX_CODIGO.jsonl
"""

import json
import os
import re
from pathlib import Path

# Configuración de rutas
JSON_CHUNKS_DIR = Path("json_chunks")

print("\n" + "=" * 60)
print("🚀 INICIANDO RENOMBRADO MASIVO DE CHUNKS")
print("=" * 60 + "\n")

def ejecutar_renombrado():
    if not JSON_CHUNKS_DIR.exists():
        print(f"[ERROR] No se encontró la carpeta '{JSON_CHUNKS_DIR}' en el repositorio.")
        return

    archivos_procesados = 0
    
    # Listar los archivos para procesar
    for f in JSON_CHUNKS_DIR.glob("licitaciones_part_*.jsonl"):
        # Extraer el número de parte original
        match_part = re.search(r"licitaciones_part_(\d+)\.jsonl", f.name)
        if not match_part:
            continue
            
        numero_part_int = int(match_part.group(1))
        # Formatear el número de parte estrictamente a 3 dígitos (ej: 001, 045, 141)
        part_tres_digitos = f"{numero_part_int:03d}"
        
        codigo_licitacion = None
        
        # Leer la primera línea para extraer el código interno rápidamente sin cargar todo el archivo
        try:
            with open(f, "r", encoding="utf-8") as archivo_lectura:
                primera_linea = archivo_lectura.readline()
                if primera_linea:
                    data_json = json.loads(primera_linea)
                    codigo_licitacion = data_json.get("codigo")
        except Exception as e:
            print(f"[ERROR] No se pudo leer el contenido de {f.name}: {e}")
            continue

        # Si el archivo está vacío o no tiene la clave código, usamos un fallback seguro
        if not codigo_licitacion:
            print(f"[ALERTA] {f.name} no contiene la clave 'codigo'. Se omitirá temporalmente.")
            continue

        # Construir el nuevo nombre requerido: lici_partXXX_CODIGO.jsonl
        nuevo_nombre_archivo = f"lici_part{part_tres_digitos}_{codigo_licitacion}.jsonl"
        nueva_ruta_completa = JSON_CHUNKS_DIR / nuevo_nombre_archivo
        
        # Ejecutar el renombrado en el disco
        try:
            os.rename(f, nueva_ruta_completa)
            print(f"[RENOMBRADO] {f.name} ---> {nuevo_nombre_archivo}")
            archivos_procesados += 1
        except Exception as e:
            print(f"[ERROR] Falló el renombrado de {f.name}: {e}")

    print("\n" + "=" * 60)
    print(f"[OK] Proceso finalizado. Se renombraron {archivos_procesados} archivos correctamente.")
    print("=" * 60 + "\n")

if __name__ == "__main__":
    ejecutar_renombrado()
