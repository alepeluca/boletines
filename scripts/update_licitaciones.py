#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
update_licitaciones.py — Versión 4.1.1

FLUJO INCREMENTAL ROBUSTO (OPTIMIZADO PARA MEMORIA):
1. Lee todas las URLs del archivo estático 'LiciURL' de la raíz.
2. Calcula el próximo índice numérico real buscando el número máximo de chunk existente.
3. Toma la URL correspondiente a ese índice y procesa UN SOLO archivo por corrida.
4. Valida rigurosamente que las cabeceras de respuesta correspondan a un archivo PDF.
5. Utiliza PyMuPDF (fitz) para renderizar el PDF hoja por hoja de forma secuencial,
   evitando desbordamientos de memoria RAM en GitHub Actions.
6. Ejecuta Tesseract OCR obligatorio en cada página procesada (idioma español).
7. Guarda un JSONL enriquecido con metadatos nativos (codigo, url, archivo, id, fragmento).
"""

import json
import os
import re
import io
from datetime import datetime
from pathlib import Path
import requests
import fitz  # PyMuPDF
import pytesseract
from PIL import Image

# =========================================================
# CONFIG
# =========================================================

VERSION = "4.1.0"
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

def get_next_chunk_index():
    """
    Busca el número de índice máximo real entre los archivos jsonl existentes
    para evitar problemas si faltan archivos intermedios en la secuencia.
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
        # Abrimos el documento de forma directa usando fitz desde los bytes en memoria
        with fitz.open(stream=response.content, filetype="pdf") as doc:
            total_paginas = len(doc)
            print(f"[INFO] Total de páginas detectadas de forma nativa: {total_paginas}")
            
            # Iteramos página por página de forma secuencial
            for index_pag in range(total_paginas):
                numero_pagina_real = index_pag + 1
                print(f"[OCR] Procesando página {numero_pagina_real}/{total_paginas}...")
                
                # Cargamos la página aislada y la renderizamos a una matriz de pixeles (150 DPI)
                page = doc[index_pag]
                pix = page.get_pixmap(dpi=150)
                
                # Convertimos los pixeles a bytes PNG e inicializamos el objeto de imagen PIL
                img_bytes = pix.tobytes("png")
                imagen_pil = Image.open(io.BytesIO(img_bytes))
                
                # Ejecutamos Tesseract sobre la imagen de la página actual
                texto_extraido = pytesseract.image_to_string(imagen_pil, lang='spa').strip()
                
                if numero_pagina_real == 1:
                    texto_p1 = texto_extraido
                
                if texto_extraido:
                    frags_finales.append({
                        "pagina": numero_pagina_real,
                        "fragmento": texto_extraido
                    })
                    
                # Liberamos memoria explícitamente en cada ciclo de página
                pix = None
                imagen_pil.close()
                
    except Exception as e:
        print(f"[ERROR] Falló el procesamiento por páginas con PyMuPDF / Tesseract: {e}")
        return False

    if frags_finales:
        objeto_camel = limpiar_texto_objeto(texto_p1, max_palabras=5)
        nombre_archivo_virtual = f"LiciPubli_{codigo_completo}_{objeto_camel}.pdf"
        timestamp_procesado = datetime.utcnow().isoformat()
        
        # Guardar el archivo JSONL incremental
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

    proximo_indice_pendiente = get_next_chunk_index()
    print(f"[INFO] Total de URLs registradas en LiciURL: {len(todas_las_urls)}")
    print(f"[INFO] Cantidad de licitaciones ya procesadas: {proximo_indice_pendiente}")

    if proximo_indice_pendiente >= len(todas_las_urls):
        print("\n[INFO] No hay nuevas licitaciones para procesar.")
        return

    url_objetivo = todas_las_urls[proximo_indice_pendiente]
    codigo_licitacion = extraer_codigo_de_url(url_objetivo)
    
    print(f"\n[PROCESO] Iniciando ejecución para el elemento índice [{proximo_indice_pendiente}]")
    
    exito = procesar_y_guardar_pdf(url_objetivo, codigo_licitacion, proximo_indice_pendiente)
    
    if exito:
        print("[OK] Ejecución incremental finalizada correctamente de a un archivo.")
    else:
        print("[ERROR] La ejecución actual falló al procesar el elemento.")


if __name__ == "__main__":
    main()
