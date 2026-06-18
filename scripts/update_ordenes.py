#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
update_ordenes.py — Versión 1.1.1 (Edición Órdenes del Día con OCR - URLs Fix)

FLUJO CONTROLADO SECUENCIAL:
1. Verifica el calendario quincenal (o atiende la bandera manual --force).
2. Mapea la nueva carpeta de Drive mediante tokens cruzados inmunes a bloqueos.
3. Escanea la subcarpeta exclusiva 'json_chunks/orden/' para saber el último index.
4. Filtra archivos válidos (YYYYMMDD*.pdf) y los ordena del más antiguo al más nuevo.
5. Descarga secuencialmente uno por uno.
6. Aplica OCR con Tesseract página por página cuidando la memoria del servidor.
7. Guarda el chunk normalizado a 4 dígitos en su subcarpeta correspondiente con URL exacta.
"""

import json
import os
import re
import io
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path
from urllib.parse import quote  # <-- AGREGADO PARA ARMAR LA URL EXACTA
import requests
import fitz  # PyMuPDF
import pytesseract
from PIL import Image

VERSION = "1.1.1"
FECHA_MODIFICACION = "18-06-2026"

# Cambiado para apuntar nativamente a la subcarpeta 'orden'
JSON_CHUNKS_DIR = Path("json_chunks/orden")
JSON_CHUNKS_DIR.mkdir(parents=True, exist_ok=True)

# ID de la carpeta provista para Órdenes del Día
FOLDER_ID = "1oWFnT-KijLjl315q-EcoDCi9XNRANTeJ"
DRIVE_FOLDER_URL = f"https://drive.google.com/drive/folders/{FOLDER_ID}"
# Forzamos que coincida con la nomenclatura asimétrica configurada en tu index.html
PREFIX = "hcd_orden_part_"

print("\n" + "=" * 60)
print(f"📄 ACTUALIZADOR OCR DE ÓRDENES DEL DÍA v{VERSION}")
print(f"📅 Última modificación: {FECHA_MODIFICACION}")
print("=" * 60 + "\n")

# =========================================================
# REGLA CALENDARIA QUINCENAL
# =========================================================
def obtener_martes_del_mes(anio, mes, n):
    primer_dia_mes = datetime(anio, mes, 1)
    dia_semana_primer_dia = primer_dia_mes.weekday()
    dias_al_primer_martes = (1 - dia_semana_primer_dia) % 7
    primer_martes = primer_dia_mes + timedelta(days=dias_al_primer_martes)
    return primer_martes + timedelta(weeks=(n - 1))

def es_periodo_de_actualizacion():
    hoy = datetime.now()
    segundo_martes = obtener_martes_del_mes(hoy.year, hoy.month, 2)
    sabado_previo_2do = segundo_martes - timedelta(days=3)
    cuarto_martes = obtener_martes_del_mes(hoy.year, hoy.month, 4)
    sabado_previo_4to = cuarto_martes - timedelta(days=3)
    
    print(f"[REGLA 1] Sábado previo al 2do Martes: {sabado_previo_2do.strftime('%Y-%m-%d')}")
    print(f"[REGLA 2] Sábado previo al 4to Martes: {sabado_previo_4to.strftime('%Y-%m-%d')}")
    print(f"[EJECUCIÓN] Fecha actual en el servidor: {hoy.strftime('%Y-%m-%d')}")
    
    if hoy >= sabado_previo_4to:
        return True
    elif hoy >= sabado_previo_2do and hoy < (sabado_previo_4to - timedelta(days=2)):
        return True
    return False

# =========================================================
# EXTRACCIÓN SEGURO DESDE DRIVE
# =========================================================
def get_next_free_chunk_index():
    indices = []
    # Busca solo dentro de json_chunks/orden/
    for f in JSON_CHUNKS_DIR.glob(f"{PREFIX}*.jsonl"):
        match = re.match(r"^" + PREFIX + r"(\d+)\.jsonl$", f.name, re.IGNORECASE)
        if match:
            indices.append(int(match.group(1)))
    if not indices:
        return 1
    return max(indices) + 1

def codigo_ya_indexado(id_base):
    # Busca duplicados solo dentro de la subcarpeta 'orden'
    for chunk_file in JSON_CHUNKS_DIR.glob(f"{PREFIX}*.jsonl"):
        try:
            with open(chunk_file, "r", encoding="utf-8") as cf:
                primera_ln = cf.readline()
                if primera_ln and id_base in primera_ln:
                    return True
        except Exception:
            continue
    return False

def listar_archivos_drive_publico(folder_id):
    files = []
    seen_ids = set()
    urls = [
        f"https://drive.google.com/embeddedfolderview?id={folder_id}&hl=es",
        f"https://drive.google.com/drive/folders/{folder_id}?hl=es"
    ]
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    }
    for url in urls:
        try:
            res = requests.get(url, headers=headers, timeout=15)
            if res.status_code != 200:
                continue
            html = res.text
            all_tokens = re.findall(r'"([^"\\]*(?:\\.[^"\\]*)*)"', html) + re.findall(r"'([^'\\]*(?:\\.[^'\\]*)*)'", html)
            
            for i in range(len(all_tokens)):
                tok = all_tokens[i]
                if tok.lower().endswith('.pdf') and re.match(r'^\d{8}', tok):
                    start = max(0, i - 15)
                    end = min(len(all_tokens), i + 15)
                    for j in range(start, end):
                        cand = all_tokens[j]
                        if len(cand) == 33 and re.match(r'^[a-zA-Z0-9_\-]+$', cand):
                            if cand not in seen_ids and cand != folder_id:
                                files.append({"id": cand, "name": tok})
                                seen_ids.add(cand)
                                break
        except Exception:
            continue
    return files

def descargar_pdf_drive(file_id, dest_path):
    url = "https://docs.google.com/uc"
    params = {"export": "download", "id": file_id}
    session = requests.Session()
    response = session.get(url, params=params, stream=True, timeout=30)
    
    token = None
    for key, value in response.cookies.items():
        if "download_warning" in key:
            token = value
            break
    if token:
        params["confirm"] = token
        response = session.get(url, params=params, stream=True, timeout=30)
        
    if response.status_code == 200:
        with open(dest_path, "wb") as f:
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)
        return True
    return False

def extraer_fecha_del_texto(texto):
    meses = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre"]
    patron_letras = r"(\d{1,2})\s+de\s+(" + "|".join(meses) + r")\s+de\s+(\d{4})"
    match_letras = re.search(patron_letras, texto, re.IGNORECASE)
    if match_letras:
        return f"{match_letras.group(1)} de {match_letras.group(2).capitalize()} de {match_letras.group(3)}"
    return "Fecha No Detectada"

# =========================================================
# MOTOR DE PROCESAMIENTO OCR PÁGINA A PÁGINA
# =========================================================
def procesar_pdf_local_ocr(pdf_path, chunk_index, file_name):
    try:
        doc = fitz.open(pdf_path)
    except Exception as e:
        print(f"  [ERROR] PyMuPDF falló al abrir el archivo: {e}")
        return False

    frags_finales = []
    texto_p1 = ""

    for index_pag in range(len(doc)):
        try:
            page = doc[index_pag]
            pix = page.get_pixmap(dpi=150)
            img_bytes = pix.tobytes("png")
            imagen_pil = Image.open(io.BytesIO(img_bytes))
            
            texto_extraido = pytesseract.image_to_string(imagen_pil, lang='spa').strip()
            imagen_pil.close()

            if index_pag == 0:
                texto_p1 = texto_extraido

            if texto_extraido:
                frags_finales.append({
                    "pagina": index_pag + 1,
                    "fragmento": texto_extraido
                })
        except Exception as e:
            print(f"  [⚠️ Error en Página {index_pag + 1}]: {e}")
            continue

    doc.close()

    if not frags_finales:
        print(f"  [⚠️] No se pudo rescatar texto OCR en ninguna página de: {file_name}")
        return False

    fecha_acta = extraer_fecha_del_texto(texto_p1 if texto_p1 else frags_finales[0]["fragmento"])
    id_base = file_name.replace(".pdf", "").replace(".PDF", "")
    timestamp_procesado = datetime.utcnow().isoformat()
    
    # CAMBIO: Relleno estricto con padding de 4 ceros f"{chunk_index:04d}"
    part_cuatro_digitos = f"{chunk_index:04d}"
    salida = JSON_CHUNKS_DIR / f"{PREFIX}{part_cuatro_digitos}.jsonl"

    # <-- AGREGADO: Armamos la URL exacta de búsqueda de Google Drive -->
    query = f'parent:{FOLDER_ID} title:"{file_name}"'
    nueva_url_drive = f"https://drive.google.com/drive/u/5/search?q={quote(query)}"

    with open(salida, "w", encoding="utf-8") as f:
        for f_data in frags_finales:
            chunk_linea = {
                "codigo": id_base,
                "url": nueva_url_drive,  # <-- CAMBIO: Ahora guarda la URL individual correcta
                "archivo": file_name,
                "id": f"{id_base}_p{f_data['pagina']}_f0",
                "pagina": f_data['pagina'],
                "fecha_acta": fecha_acta,
                "fragmento": f_data['fragmento'],
                "procesado": timestamp_procesado
            }
            f.write(json.dumps(chunk_linea, ensure_ascii=False) + "\n")
            
    print(f"  [OK] OCR Completo -> {salida} (Fecha de Orden: {fecha_acta})")
    return True

# =========================================================
# MAIN
# =========================================================
def main():
    forzar_ejecucion = (len(sys.argv) > 1 and sys.argv[1] == "--force")

    if not forzar_ejecucion and not es_periodo_de_actualizacion():
        print("[INFO] Automatización detenida por calendario quincenal.")
        sys.exit(0)

    print("[PROCESO] Conectando con la carpeta pública de Órdenes del Día en subcarpeta 'orden/'...")
    archivos_drive = listar_archivos_drive_publico(FOLDER_ID)
    
    if not archivos_drive:
        print("[⚠️] Carpeta de Drive inaccesible o vacía.")
        sys.exit(0)

    # Filtrar e identificar patrones YYYYMMDD*.pdf
    archivos_validos = []
    for f in archivos_drive:
        name = f["name"]
        if name.lower().endswith(".pdf") and re.match(r"^\d{8}", name):
            archivos_validos.append(f)
            
    # Ordenar cronológicamente (Viejos primero)
    archivos_validos.sort(key=lambda x: x["name"])
    print(f"[INFO] Se localizaron {len(archivos_validos)} órdenes válidas en Drive.")
    
    proximo_index_chunk = get_next_free_chunk_index()
    nuevos_hallazgos = 0

    for f in archivos_validos:
        name = f["name"]
        file_id = f["id"]
        id_base = name.replace(".pdf", "").replace(".PDF", "")

        if codigo_ya_indexado(id_base):
            continue

        print(f"\n[📥 DESCARGA + OCR SECUENCIAL] Procesando orden: {name}")
        temp_pdf = Path("temp_orden_ocr.pdf")
        
        if descargar_pdf_drive(file_id, temp_pdf):
            exito = procesar_pdf_local_ocr(temp_pdf, proximo_index_chunk, name)
            if temp_pdf.exists():
                temp_pdf.unlink()  # Liberación de espacio en disco inmediata
                
            if exito:
                proximo_index_chunk += 1
                nuevos_hallazgos += 1
                time.sleep(2)  # Delay preventivo para el servidor
        else:
            print(f"  [⚠️] Error de red al bajar: {name}")

    print(f"\n[INFO] Sincronización finalizada en 'json_chunks/orden/'. Chunks nuevos creados: {nuevos_hallazgos}")

if __name__ == "__main__":
    main()
