#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
update_licitaciones.py — Versión 3.0.0

FLUJO:
1. Lee todas las URLs del archivo estático 'LiciURL' de la raíz.
2. Cuenta cuántos archivos 'licitaciones_part_*.jsonl' ya existen en 'json_chunks/'.
3. Dado que cada archivo JSONL representa exactamente una licitación procesada de forma secuencial,
   el script reanuda salteándose las primeras N URLs (donde N es la cantidad de chunks existentes).
4. Descarga la siguiente URL pendiente, ejecuta OCR obligatorio en todas sus páginas usando Tesseract.
5. Busca "OBJETO:" en la primera página, extrae hasta 5 palabras para armar CamelCase.
6. Guarda el resultado en un nuevo chunk incremental 'licitaciones_part_N.jsonl'.
"""

import json
import os
import re
from pathlib import Path
import requests
import pytesseract
from pdf2image import convert_from_bytes

# =========================================================
# CONFIG
# =========================================================

VERSION = "3.0.0"
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

def get_processed_count():
    """
    Cuenta cuántos archivos JSONL válidos e indexados existen en la carpeta json_chunks.
    Cada archivo corresponde exactamente a una licitación ya procesada de forma secuencial.
    """
    contador = 0
    for f in JSON_CHUNKS_DIR.glob("licitaciones_part_*.jsonl"):
        match = re.search(r"licitaciones_part_(\d+)\.jsonl", f.name)
        if match:
            contador += 1
    return contador


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
    Extrae el patrón de código XXXYY0-Z de la URL.
    Ejemplo: https://.../001220-1.pdf -> 001220-1
    """
    match = re.search(r"(\d{3}\d{2}0-\d)", url)
    if match:
        return match.group(1)
    # Fallback si por alguna razón la URL no sigue el patrón estricto
    return "000000-0"


def limpiar_texto_objeto(texto_completo, max_palabras=5):
    """Busca 'OBJETO:' en el texto del OCR, toma la línea y extrae N palabras en CamelCase."""
    if "OBJETO:" not in texto_completo:
        return "SinObjeto"
    
    partes = texto_completo.split("OBJETO:", 1)
    if len(partes) < 2:
        return "SinObjeto"
        
    parte_objeto = partes[1].strip()
    lineas_objeto = parte_objeto.split("\n")
    primera_linea = lineas_objeto[0].strip() if lineas_objeto else ""
    
    limpio = re.sub(r'[^\w\s]', '', primera_linea)
    palabras = limpio.split()
    
    palabras_filtradas = [p for p in palabras if len(p) > 1 or p.lower() in ['de', 'en', 'la', 'lo']]
    palabras_finales = palabras_filtradas[:max_palabras]
    
    if not palabras_finales:
        return "DocumentoLicitacion"
        
    return "".join(p.capitalize() for p in palabras_finales)


def procesar_y_guardar_pdf(url, codigo_completo, chunk_index):
    """Descarga el PDF y le aplica OCR obligatorio a todas sus páginas."""
    print(f"[INFO] Descargando pliego: {url}")
    try:
        response = requests.get(url, headers=HEADERS, timeout=30)
        response.raise_for_status()
    except requests.RequestException as e:
        print(f"[ERROR] No se pudo descargar el archivo: {e}")
        return False

    print("[INFO] Iniciando conversión a imagen para procesamiento OCR obligatorio...")
    frags_finales = []
    texto_p1 = ""

    try:
        # Convertir bytes de PDF a imágenes (150 DPI para balancear velocidad y precisión)
        paginas_imagenes = convert_from_bytes(response.content, dpi=150)
        
        for i, imagen in enumerate(paginas_imagenes, start=1):
            print(f"[OCR] Procesando página {i}/{len(paginas_imagenes)}...")
            
            # Forzar ejecución de Tesseract en idioma español
            texto_extraido = pytesseract.image_to_string(imagen, lang='spa').strip()
            
            if i == 1:
                texto_p1 = texto_extraido
            
            if texto_extraido:
                frags_finales.append({
                    "pagina": i,
                    "fragmento": texto_extraido
                })
                
    except Exception as e:
        print(f"[ERROR] Falló el motor de Tesseract / pdf2image: {e}")
        return False

    if frags_finales:
        # Procesar las 5 palabras del objeto en CamelCase desde la página 1 del OCR
        objeto_camel = limpiar_texto_objeto(texto_p1, max_palabras=5)
        nombre_archivo_virtual = f"LiciPubli_{codigo_completo}_{objeto_camel}.pdf"
        
        # Armar y guardar el archivo JSONL con el nuevo índice consecutivo
        salida = JSON_CHUNKS_DIR / f"licitaciones_part_{chunk_index}.jsonl"
        with open(salida, "w", encoding="utf-8") as f:
            for f_data in frags_finales:
                chunk_linea = {
                    "id": f"{nombre_archivo_virtual}_p{f_data['pagina']}_f0",
                    "archivo": nombre_archivo_virtual,
                    "pagina": f_data['pagina'],
                    "fragmento": f_data['fragmento']
                }
                f.write(json.dumps(chunk_linea, ensure_ascii=False) + "\n")
                
        print(f"[OK] Chunk generado con OCR obligatorio: {salida.name} -> {nombre_archivo_virtual}")
        return True

    print(f"[ERROR] No se pudo extraer texto legible mediante OCR del documento {url}")
    return False


# =========================================================
# MAIN
# =========================================================

def main():
    # 1. Leer todas las URLs disponibles desde el archivo estático
    todas_las_urls = cargar_urls_pendientes()
    if not todas_las_urls:
        return

    # 2. Detectar el progreso actual contando los archivos .jsonl existentes
    chunks_procesados_count = get_processed_count()
    print(f"[INFO] Total de URLs registradas en LiciURL: {len(todas_las_urls)}")
    print(f"[INFO] Cantidad de licitaciones ya procesadas (chunks): {chunks_procesados_count}")

    # 3. Determinar el índice de la próxima URL a procesar
    # Si chunks_procesados_count es 0, empieza de la URL index 0. 
    # Si es 5, saltará las posiciones 0,1,2,3,4 y procesará la posición 5.
    if chunks_procesados_count >= len(todas_las_urls):
        print("\n[INFO] No hay nuevas licitaciones para procesar.")
        return

    url_objetivo = todas_las_urls[chunks_procesados_count]
    codigo_licitacion = extraer_codigo_de_url(url_objetivo)
    
    print(f"[INFO] Reanudando ejecución en URL índice [{chunks_procesados_count}]: {url_objetivo}")
    
    # 4. Procesar de forma incremental la licitación actual asignándole su índice secuencial correspondiente
    exito = procesar_y_guardar_pdf(url_objetivo, codigo_licitacion, chunks_procesados_count)
    
    if exito:
        print("[OK] Proceso completado para la ejecución actual.")
    else:
        print("[ERROR] No se pudo procesar la licitación actual.")


if __name__ == "__main__":
    main()
