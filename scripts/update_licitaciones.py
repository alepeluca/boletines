#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
update_licitaciones.py — Versión 5.0.0

FLUJO MASIVO CONTINUO (OPTIMIZADO PARA LOTES GRANDES):
1. Lee todas las URLs del archivo estático 'LiciURL' de la raíz.
2. Calcula el punto de partida inicial en memoria.
3. Procesa de forma continua en un bucle 'while' todas las URLs pendientes.
4. Utiliza PyMuPDF (fitz) para renderizar hoja por hoja liberando RAM en cada paso.
5. Aplica Tesseract OCR obligatorio en idioma español.
6. Guarda de manera inmediata cada nuevo chunk indexado en 'json_chunks/'.
"""

import json
import os
import re
import io
import time
import random
from datetime import datetime
from pathlib import Path
import requests
import fitz  # PyMuPDF
import pytesseract
from PIL import Image

# =========================================================
# CONFIG
# =========================================================

VERSION = "5.0.0"
FECHA_MODIFICACION = "12-06-2026"

JSON_CHUNKS_DIR = Path("json_chunks")
LICI_URL_FILE = Path("LiciURL")

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0 Safari/537.36"
    )
}

JSON_CHUNKS_DIR.mkdir(exist_ok=True)

print("\n" + "=" * 60)
print(f"🚀 UPDATE LICITACIONES v{VERSION}")
print(f"📅 Última modificación: {FECHA_MODIFICACION}")
print("=" * 60 + "\n")


# =========================================================
# HELPERS
# =========================================================

def get_initial_processed_count():
    """
    Busca el número de índice máximo real entre los archivos jsonl existentes
    al arrancar para saber exactamente en qué posición de la lista retomar.
    """
    indices = []
    for f in JSON_CHUNKS_DIR.glob("licitaciones_part_*.jsonl"):
        match = re.search(r"licitaciones_part_(\d+)\.jsonl", f.name)
        if match:
            indices.append(int(match.group(1)))
            
    if not indices:
        return 0
        
    return max(indices) + 1


def cargar_urls_pendientes():
    """
    Lee el archivo LiciURL y devuelve una lista limpia de todas las URLs.
    """
    if not LICI_URL_FILE.exists():
        print(f"[ERROR] No se encontró el archivo de origen '{LICI_URL_FILE.name}' en la raíz.")
        return []
    
    urls = []
    with open(LICI_URL_FILE, "r", encoding="utf-8") as f:
        for linea in f:
            linea = linea.strip()
            if linea and linea.startswith("http"):
                urls.append(linea)
    return urls


def extraer_codigo_de_url(url):
    """
    Extrae el patrón de código flexible de la URL (ej. 001220-1 o 012260-2).
    """
    match = re.search(r"(\d{6}-\d+)", url)
    if match:
        return match.group(1)
    return "000000-0"


def limpiar_texto_objeto(texto_completo, max_palabras=5):
    """
    Utiliza una expresión regular insensible a mayúsculas para capturar el OBJETO,
    contemplando fallas comunes de lectura de Tesseract sobre los dos puntos (:).
    """
    match = re.search(r"OBJETO\s*[:;\-–—]?\s*(.+)", texto_completo, re.IGNORECASE)
    if not match:
        return "SinObjeto"
        
    primera_linea_objeto = match.group(1).strip()
    lineas = primera_linea_objeto.split("\n")
    texto_objeto = lineas[0].strip() if lineas else ""
    
    limpio = re.sub(r'[^\w\s]', '', texto_objeto)
    palabras = limpio.split()
    
    palabras_filtradas = [p for p in palabras if len(p) > 1 or p.lower() in ['de', 'en', 'la', 'lo']]
    palabras_finales = palabras_filtradas[:max_palabras]
    
    if not palabras_finales:
        return "DocumentoLicitacion"
        
    return "".join(p.capitalize() for p in palabras_finales)


def procesar_y_guardar_pdf(url, codigo_completo, chunk_index):
    """
    Descarga el PDF, valida su estructura y renderiza secuencialmente
    hoja por hoja a imagen para aplicarle el OCR de Tesseract de forma segura.
    """
    print(f"[INFO] Descargando pliego: {url}")
    print(f"[CODIGO] {codigo_completo}")
    print(f"[URL] {url}")
    
    try:
        response = requests.get(url, headers=HEADERS, timeout=30)
        response.raise_for_status()
    except requests.RequestException as e:
        print(f"[ERROR] No se pudo descargar el archivo: {e}")
        return False

    content_type = response.headers.get("Content-Type", "").lower()
    if "pdf" not in content_type:
        print(f"[ERROR] El archivo descargado no es un PDF válido. Content-Type: {content_type}")
        return False

    print("[INFO] Abriendo documento PDF en memoria para extracción por páginas...")
    frags_finales = []
    texto_p1 = ""

    try:
        with fitz.open(stream=response.content, filetype="pdf") as doc:
            total_paginas = len(doc)
            print(f"[INFO] Total de páginas detectadas: {total_paginas}")
            
            for index_pag in range(total_paginas):
                numero_pagina_real = index_pag + 1
                print(f"[OCR] Procesando página {numero_pagina_real}/{total_paginas}...")
                
                page = doc[index_pag]
                pix = page.get_pixmap(dpi=150)
                
                img_bytes = pix.tobytes("png")
                imagen_pil = Image.open(io.BytesIO(img_bytes))
                
                texto_extraido = pytesseract.image_to_string(imagen_pil, lang='spa').strip()
                
                if numero_pagina_real == 1:
                    texto_p1 = texto_extraido
                
                if texto_extraido:
                    frags_finales.append({
                        "pagina": numero_pagina_real,
                        "fragmento": texto_extraido
                    })
                    
                pix = None
                imagen_pil.close()
                
    except Exception as e:
        print(f"[ERROR] Falló el procesamiento por páginas con PyMuPDF / Tesseract: {e}")
        return False

    if frags_finales:
        objeto_camel = limpiar_texto_objeto(texto_p1, max_palabras=5)
        nombre_archivo_virtual = f"LiciPubli_{codigo_completo}_{objeto_camel}.pdf"
        timestamp_procesado = datetime.utcnow().isoformat()
        
        salida = JSON_CHUNKS_DIR / f"licitaciones_part_{chunk_index}.jsonl"
        with open(salida, "w", encoding="utf-8") as f:
            for f_data in frags_finales:
                chunk_linea = {
                    "codigo": codigo_completo,
                    "url": url,
                    "archivo": nombre_archivo_virtual,
                    "id": f"{nombre_archivo_virtual}_p{f_data['pagina']}_f0",
                    "pagina": f_data['pagina'],
                    "fragmento": f_data['fragmento'],
                    "procesado": timestamp_procesado
                }
                f.write(json.dumps(chunk_linea, ensure_ascii=False) + "\n")
                
        print(f"[OK] Chunk generado con éxito: {salida.name} -> {nombre_archivo_virtual}")
        return True

    print(f"[ERROR] No se pudo extraer texto legible mediante OCR de ninguna página del documento.")
    return False


# =========================================================
# MAIN
# =========================================================

def main():
    todas_las_urls = cargar_urls_pendientes()
    if not todas_las_urls:
        return

    # 1. Obtener el punto de partida inicial basándose en los archivos actuales en Git
    indice_actual = get_initial_processed_count()
    print(f"[INFO] Total de URLs registradas en LiciURL: {len(todas_las_urls)}")
    print(f"[INFO] Punto de partida inicial calculado: índice {indice_actual}")

    if indice_actual >= len(todas_las_urls):
        print("\n[INFO] No hay nuevas licitaciones para procesar. Todas las URLs completadas.")
        return

    # 2. Procesamiento masivo continuo controlado por memoria
    while indice_actual < len(todas_las_urls):
        url_objetivo = todas_las_urls[indice_actual]
        codigo_licitacion = extraer_codigo_de_url(url_objetivo)
        
        print(f"\n[PROCESO] Procesando elemento [{indice_actual + 1}/{len(todas_las_urls)}]")
        
        exito = procesar_y_guardar_pdf(url_objetivo, codigo_licitacion, indice_actual)
        
        if not exito:
            print(f"[ALERTA] Deteniendo ejecución debido a un problema con el índice {indice_actual}.")
            break
            
        # Avanzar a la siguiente URL en memoria de forma inmediata
        indice_actual += 1
        
        # Una pequeña pausa de cortesía para no saturar al servidor municipal
        time.sleep(random.uniform(1.0, 2.5))

    if indice_actual >= len(todas_las_urls):
        print("\n[INFO] Se han procesado con éxito todos los elementos del archivo LiciURL.")


if __name__ == "__main__":
    main()
