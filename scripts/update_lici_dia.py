#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
update_licitaciones.py — Versión 6.1.0 (Modo Vigilancia Activa)

FLUJO DIARIO AUTOMÁTICA CON NORMALIZACIÓN NNNN:
1. Escanea la carpeta 'json_chunks/' para saber cuál fue la última licitación procesada de 2026.
2. Setea el inicio de 2026 en ese número (ej: 037) y el inicio de 2027 en el número 001.
3. Prueba la existencia de las URLs en el servidor municipal (controlando subpliegos Z).
4. Si encuentra algo nuevo: aplica OCR con Tesseract, extrae el OBJETO en CamelCase
   y guarda el chunk con el formato estandarizado estricto de 4 dígitos: lici_partNNNN.jsonl
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

VERSION = "6.1.0"
FECHA_MODIFICACION = "15-06-2026"

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
    """Busca el número de índice máximo real entre los archivos normalizados."""
    indices = []
    # Captura lici_part seguido de cualquier cantidad de dígitos
    for f in JSON_CHUNKS_DIR.glob("lici_part*.jsonl"):
        match = re.match(r"^lici_part(\d+)\.jsonl$", f.name, re.IGNORECASE)
        if match:
            indices.append(int(match.group(1)))
        else:
            # Fallback por si todavía quedan archivos con el formato viejo de guion bajo
            match_viejo = re.search(r"lici_part(\d+)_", f.name)
            if match_viejo:
                indices.append(int(match_viejo.group(1)))
                
    if not indices:
        return 1  # Empezamos en la parte 1 si está vacía
    return max(indices) + 1


def get_last_processed_xxx_for_year(anio_str):
    """Revisa los chunks para ver cuál es el número XXX más alto guardado de un año específico."""
    max_xxx = 0
    # Inspeccionamos el contenido interno de los archivos para ver a qué código de pliego corresponden
    for f in JSON_CHUNKS_DIR.glob("lici_part*.jsonl"):
        try:
            with open(f, "r", encoding="utf-8") as file:
                primera_linea = file.readline()
                if not primera_linea:
                    continue
                data = json.loads(primera_linea)
                codigo = data.get("codigo", "") # ej: "196260-1"
                
                # Verificamos si pertenece al año buscado (ej: "26" o "27")
                if len(codigo) >= 5 and codigo[3:5] == anio_str:
                    xxx_val = int(codigo[:3])
                    if xxx_val > max_xxx:
                        max_xxx = xxx_val
        except Exception:
            continue
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
    """Descarga el PDF, aplica OCR obligatorio y guarda con el formato NNNN limpio."""
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
        
        # NUEVO: Formatear el índice de chunk estrictamente a 4 dígitos (NNNN)
        part_cuatro_digitos = f"{chunk_index:04d}"
        # NUEVO: Quitamos el sufijo del código para normalizar el nombre
        salida = JSON_CHUNKS_DIR / f"lici_part{part_cuatro_digitos}.jsonl"
        
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
        for xxx_int in range(xxx_inicio, xxx_inicio + 15):
            xxx_str = f"{xxx_int:03d}"
            
            for z in range(1, 7):
                codigo_licitacion = f"{xxx_str}{anio}0-{z}"
                url_prueba = f"{BASE_URL}{codigo_licitacion}.pdf"
                
                try:
                    res = requests.head(url_prueba, headers=HEADERS, timeout=10)
                    existe = (res.status_code == 200)
                except requests.RequestException:
                    existe = False
                
                if existe:
                    # Buscamos si el código ya fue indexado en algún archivo para no duplicar
                    archivo_ya_existe = False
                    for chunk_file in JSON_CHUNKS_DIR.glob("lici_part*.jsonl"):
                        try:
                            with open(chunk_file, "r", encoding="utf-8") as cf:
                                primera_ln = cf.readline()
                                if primera_ln and codigo_licitacion in primera_ln:
                                    archivo_ya_existe = True
                                    break
                        except Exception:
                            continue
                            
                    if not archivo_ya_existe:
                        print(f"¡Hallazgo! Descubierto pliego nuevo: {codigo_licitacion}.pdf")
                        exito = procesar_y_guardar_pdf(url_prueba, codigo_licitacion, proximo_index_chunk)
                        if exito:
                            proximo_index_chunk += 1
                            nuevos_hallazgos += 1
                else:
                    break # Si la variante Z=1 no existe, frena la sub-búsqueda para ese número XXX
            
            time.sleep(1.5)

    print(f"\n[INFO] Tarea de vigilancia diaria terminada. Nuevos pliegos encontrados: {nuevos_hallazgos}")


if __name__ == "__main__":
    main()
