#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
update_licitaciones.py — Versión 6.0.0 (Modo Vigilancia Activa)

FLUJO DIARIO AUTOMÁTICO:
1. Escanea la carpeta 'json_chunks/' para saber cuál fue la última licitación procesada de 2026.
2. Setea el inicio de 2026 en ese número (ej: 037) y el inicio de 2027 en el número 001.
3. Prueba la existencia de las URLs en el servidor municipal (controlando subpliegos Z).
4. Si encuentra algo nuevo: aplica OCR con Tesseract, extrae el OBJETO en CamelCase
   y guarda el chunk con el formato estandarizado de 3 dígitos: lici_partXXX_CODIGO.jsonl
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

VERSION = "6.0.0"
FECHA_MODIFICACION = "13-06-2026"

JSON_CHUNKS_DIR = Path("json_chunks")
BASE_URL = "https://quilmes.gov.ar/contrataciones/licpublicas/"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0 Safari/537.36"
    )
}

JSON_CHUNKS_DIR.mkdir(exist_ok=True)

print("\n" + "=" * 60)
print(f"📡 MODO VIGILANCIA ACTIVA DE LICITACIONES v{VERSION}")
print(f"📅 Última modificación: {FECHA_MODIFICACION}")
print("=" * 60 + "\n")


# =========================================================
# HELPERS
# =========================================================

def get_next_free_chunk_index():
    """Busca el número de índice máximo real entre los archivos renombrados."""
    indices = []
    for f in JSON_CHUNKS_DIR.glob("lici_part*.jsonl"):
        match = re.search(r"lici_part(\d+)_", f.name)
        if match:
            indices.append(int(match.group(1)))
    if not indices:
        return 0
    return max(indices) + 1


def get_last_processed_xxx_for_year(anio_str):
    """Revisa los chunks para ver cuál es el número XXX más alto guardado de un año específico."""
    max_xxx = 0
    for f in JSON_CHUNKS_DIR.glob(f"lici_part*_*260-*.jsonl" if anio_str == "26" else f"lici_part*_*270-*.jsonl"):
        match = re.search(r"_(\d{3})\d{2}0-\d\.jsonl", f.name)
        if match:
            xxx_val = int(match.group(1))
            if xxx_val > max_xxx:
                max_xxx = xxx_val
    return max_xxx


def limpiar_texto_objeto(texto_completo, max_palabras=5):
    """Busca 'OBJETO:' en el texto del OCR, toma la línea y extrae N palabras en CamelCase."""
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
    """Descarga el PDF, aplica OCR obligatorio y guarda con el formato nuevo."""
    try:
        response = requests.get(url, headers=HEADERS, timeout=30)
        response.raise_for_status()
    except requests.RequestException:
        return False

    content_type = response.headers.get("Content-Type", "").lower()
    if "pdf" not in content_type:
        return False

    frags_finales = []
    texto_p1 = ""

    try:
        with fitz.open(stream=response.content, filetype="pdf") as doc:
            for index_pag in range(len(doc)):
                page = doc[index_pag]
                pix = page.get_pixmap(dpi=150)
                img_bytes = pix.tobytes("png")
                imagen_pil = Image.open(io.BytesIO(img_bytes))
                
                texto_extraido = pytesseract.image_to_string(imagen_pil, lang='spa').strip()
                if index_pag == 0:
                    texto_p1 = texto_extraido
                
                if texto_extraido:
                    frags_finales.append({"pagina": index_pag + 1, "fragmento": texto_extraido})
                imagen_pil.close()
    except Exception:
        return False

    if frags_finales:
        objeto_camel = limpiar_texto_objeto(texto_p1, max_palabras=5)
        nombre_archivo_virtual = f"LiciPubli_{codigo_completo}_{objeto_camel}.pdf"
        timestamp_procesado = datetime.utcnow().isoformat()
        
        # Formatear el índice de chunk estrictamente a 3 dígitos
        part_tres_digitos = f"{chunk_index:03d}"
        salida = JSON_CHUNKS_DIR / f"lici_part{part_tres_digitos}_{codigo_completo}.jsonl"
        
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
        print(f"[OK] NUEVA LICITACIÓN DETECTADA Y GUARDADA: {salida.name}")
        return True
    return False


# =========================================================
# MAIN
# =========================================================

def main():
    proximo_index_chunk = get_next_free_chunk_index()
    
    # 1. Definir los años bajo vigilancia (Año anterior '26' y Año corriente '27')
    monitoreo_config = [
        {"anio_str": "26", "start_xxx": get_last_processed_xxx_for_year("26") + 1},
        {"anio_str": "27", "start_xxx": get_last_processed_xxx_for_year("27") + 1}
    ]
    
    nuevos_hallazgos = 0

    for item in monitoreo_config:
        anio = item["anio_str"]
        xxx_inicio = item["start_xxx"]
        
        print(f"[VIGILANCIA] Analizando año 20{anio}. Buscando desde el número {xxx_inicio:03d}...")
        
        # Probamos una ventana de hasta 15 números correlativos hacia adelante por día
        # para detectar si subieron elementos nuevos en lote.
        for xxx_int in range(xxx_inicio, xxx_inicio + 15):
            xxx_str = f"{xxx_int:03d}"
            encontrado_en_este_numero = False
            
            for z in range(1, 7):
                codigo_licitacion = f"{xxx_str}{anio}0-{z}"
                url_prueba = f"{BASE_URL}{codigo_licitacion}.pdf"
                
                # Hacemos una consulta HEAD rápida para no consumir recursos
                try:
                    res = requests.head(url_prueba, headers=HEADERS, timeout=10)
                    existe = (res.status_code == 200)
                except requests.RequestException:
                    existe = False
                
                if existe:
                    # Si el archivo físico no existe en nuestra carpeta, lo procesamos
                    archivo_ya_existe = any(JSON_CHUNKS_DIR.glob(f"lici_part*_{codigo_licitacion}.jsonl"))
                    if not archivo_ya_existe:
                        print(f"¡Hallazgo! Descubierto pliego nuevo: {codigo_licitacion}.pdf")
                        exito = procesar_y_guardar_pdf(url_prueba, codigo_licitacion, proximo_index_chunk)
                        if exito:
                            proximo_index_chunk += 1
                            nuevos_hallazgos += 1
                            encontrado_en_este_numero = True
                else:
                    break # Si la variante Z=1 no existe, frena la sub-búsqueda
            
            # Margen de cortesía anti-bloqueo de IP
            time.sleep(1.5)

    print(f"\n[INFO] Tarea de vigilancia diaria terminada. Nuevos pliegos encontrados: {nuevos_hallazgos}")


if __name__ == "__main__":
    main()
