#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
update_licitaciones.py — Versión 3.1.0

FLUJO CONTINUO:
1. Lee todas las URLs del archivo estático 'LiciURL' de la raíz.
2. Detecta cuántas ya se procesaron contando los archivos en 'json_chunks/'.
3. Ejecuta un bucle continuo para procesar TODAS las URLs pendientes una detrás
   de otra en la misma corrida, aplicando OCR obligatorio.
4. Si finalizan todas las URLs, muestra el aviso de completado.
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

VERSION = "3.1.0"
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
    Cuenta cuántos archivos JSONL válidos existen en la carpeta json_chunks.
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
    """
    match = re.search(r"(\d{3}\d{2}0-\d)", url)
    if match:
        return match.group(1)
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
        paginas_imagenes = convert_from_bytes(response.content, dpi=150)
        
        for i, imagen in enumerate(paginas_imagenes, start=1):
            print(f"[OCR] Procesando página {i}/{len(paginas_imagenes)}...")
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
        objeto_camel = limpiar_texto_objeto(texto_p1, max_palabras=5)
        nombre_archivo_virtual = f"LiciPubli_{codigo_completo}_{objeto_camel}.pdf"
        
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
    todas_las_urls = cargar_urls_pendientes()
    if not todas_las_urls:
        return

    # Iniciar ciclo de procesamiento continuo
    while True:
        chunks_procesados_count = get_processed_count()
        
        # Condición de salida si se terminaron todas las URLs listadas
        if chunks_procesados_count >= len(todas_las_urls):
            print("\n[INFO] No hay nuevas licitaciones para procesar. Todas las URLs completadas.")
            break

        url_objetivo = todas_las_urls[chunks_procesados_count]
        codigo_licitacion = extraer_codigo_de_url(url_objetivo)
        
        print(f"\n[PROCESO] Procesando elemento [{chunks_procesados_count + 1}/{len(todas_las_urls)}]")
        print(f"[INFO] URL: {url_objetivo}")
        
        exito = procesar_y_guardar_pdf(url_objetivo, codigo_licitacion, chunks_procesados_count)
        
        if not exito:
            print(f"[ALERTA] Deteniendo ejecución continua debido a un error en el índice {chunks_procesados_count}.")
            break


if __name__ == "__main__":
    main()
