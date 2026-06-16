#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
update_taquigraficas.py — Versión 2.1.0

FLUJO INTELIGENTE OPTIMIZADO:
1. Revisa calendario o atiende bandera --force.
2. Lee la carpeta de Drive pública mediante un mapeo directo de strings planos (Inmune a cambios HTML).
3. Filtra archivos válidos que comiencen estrictamente con YYYYMMDD y terminen en .pdf.
4. Ordena cronológicamente (Menor a Mayor), descarga secuencialmente uno por uno, procesa y elimina.
"""

import json
import os
import re
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path
import requests
import fitz  # PyMuPDF

VERSION = "2.1.0"
FECHA_MODIFICACION = "16-06-2026"

JSON_CHUNKS_DIR = Path("json_chunks")
JSON_CHUNKS_DIR.mkdir(exist_ok=True)

FOLDER_ID = "1vBrQH0h1ddIlplj3ChZ0VkqAK8UjgecB"
DRIVE_FOLDER_URL = f"https://drive.google.com/drive/folders/{FOLDER_ID}"

print("\n" + "=" * 60)
print(f"🎙️ ACTUALIZADOR INTELIGENTE DE ACTAS TAQUIGRÁFICAS v{VERSION}")
print(f"📅 Última modificación: {FECHA_MODIFICACION}")
print("=" * 60 + "\n")

# =========================================================
# REGLA CALENDARIA
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
# OPERACIONES DE CHUNKS Y DRIVE
# =========================================================
def get_next_free_chunk_index():
    indices = []
    for f in JSON_CHUNKS_DIR.glob("taqui_part*.jsonl"):
        match = re.match(r"^taqui_part(\d+)\.jsonl$", f.name, re.IGNORECASE)
        if match:
            indices.append(int(match.group(1)))
    if not indices:
        return 1
    return max(indices) + 1

def codigo_ya_indexado(id_base):
    for chunk_file in JSON_CHUNKS_DIR.glob("taqui_part*.jsonl"):
        try:
            with open(chunk_file, "r", encoding="utf-8") as cf:
                primera_ln = cf.readline()
                if primera_ln and id_base in primera_ln:
                    return True
        except Exception:
            continue
    return False

def listar_archivos_drive_publico(folder_id):
    """
    Lee de forma robusta la lista de archivos usando la API pública sin necesidad de token.
    En caso de error de cuota, recurre al parseo simplificado del catálogo de recursos.
    """
    # Intentamos primero por el canal oficial sin autenticación
    try:
        url_api = f"https://www.googleapis.com/drive/v3/files"
        params = {
            "q": f"'{folder_id}' in parents and trashed = false and mimeType = 'application/pdf'",
            "fields": "files(id, name)",
            "pageSize": 1000
        }
        res = requests.get(url_api, params=params, timeout=15)
        if res.status_code == 200:
            return res.json().get("files", [])
    except Exception:
        pass

    # Método alternativo ultraestable: Analizar la carga directa por strings crudos de metadatos públicos
    try:
        url_drive = f"https://drive.google.com/embeddedfolderview?id={folder_id}"
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        }
        res = requests.get(url_drive, headers=headers, timeout=20)
        html = res.text
        
        # Google Drive guarda los datos de los ítems en un array JSON dentro del HTML.
        # Buscamos estructuras del tipo: ["ID_DEL_ARCHIVO", "NOMBRE_DEL_ARCHIVO.pdf"]
        items = re.findall(r'\["([^"]+)"\s*,\s*"([^"]+\.[pP][dD][fF])"', html)
        
        files = []
        for fid, fname in items:
            # Evitamos duplicados en la lista capturada
            if not any(f["id"] == fid for f in files):
                files.append({"id": fid, "name": fname})
        return files
    except Exception as e:
        print(f"[ERROR] No se pudo parsear el contenido de la carpeta: {e}")
        return []

def descargar_pdf_drive(file_id, dest_path):
    url = "https://docs.google.com/uc"
    params = {"export": "download", "id": file_id}
    
    session = requests.Session()
    headers = {"User-Agent": "Mozilla/5.0"}
    response = session.get(url, params=params, headers=headers, stream=True, timeout=30)
    
    token = None
    for key, value in response.cookies.items():
        if "download_warning" in key:
            token = value
            break
            
    if token:
        params["confirm"] = token
        response = session.get(url, params=params, headers=headers, stream=True, timeout=30)
        
    if response.status_code == 200:
        with open(dest_path, "wb") as f:
            for chunk in response.iter_content(chunk_size=8112):
                if chunk:
                    f.write(chunk)
        return True
    return False

def extraer_fecha_del_texto(texto):
    meses = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre"]
    patron_letras = r"(\d{1,2})\s+de\s+(" + "|".join(meses) + r")\s+de\s+(\d{4})"
    patron_numeros = r"(\d{1,2})[-/](\d{1,2})[-/](\d{4})"
    
    match_letras = re.search(patron_letras, texto, re.IGNORECASE)
    if match_letras:
        return f"{match_letras.group(1)} de {match_letras.group(2).capitalize()} de {match_letras.group(3)}"
    match_numeros = re.search(patron_numeros, texto)
    if match_numeros:
        return f"{match_numeros.group(1)}/{match_numeros.group(2)}/{match_numeros.group(3)}"
    return "Fecha No Detectada"

def procesar_pdf_local(pdf_path, chunk_index, file_name):
    try:
        doc = fitz.open(pdf_path)
    except Exception as e:
        print(f"  [ERROR] PyMuPDF no pudo leer el archivo: {e}")
        return False

    frags_finales = []
    texto_p1 = ""
    for index_pag in range(len(doc)):
        page = doc[index_pag]
        texto_extraido = page.get_text().strip()
        if index_pag == 0:
            texto_p1 = texto_extraido
        if texto_extraido:
            frags_finales.append({"pagina": index_pag + 1, "fragmento": texto_extraido})
    doc.close()

    if not frags_finales:
        return False

    fecha_acta = extraer_fecha_del_texto(texto_p1 if texto_p1 else frags_finales[0]["fragmento"])
    id_base = file_name.replace(".pdf", "").replace(".PDF", "")
    timestamp_procesado = datetime.utcnow().isoformat()
    
    part_cuatro_digitos = f"{chunk_index:04d}"
    salida = JSON_CHUNKS_DIR / f"taqui_part{part_cuatro_digitos}.jsonl"

    with open(salida, "w", encoding="utf-8") as f:
        for f_data in frags_finales:
            chunk_linea = {
                "codigo": id_base,
                "url": DRIVE_FOLDER_URL,
                "archivo": file_name,
                "id": f"{id_base}_p{f_data['pagina']}_f0",
                "pagina": f_data['pagina'],
                "fecha_acta": fecha_acta,
                "fragmento": f_data['fragmento'],
                "procesado": timestamp_procesado
            }
            f.write(json.dumps(chunk_linea, ensure_ascii=False) + "\n")
            
    print(f"  [OK] Chunk indexado -> {salida.name} (Fecha: {fecha_acta})")
    return True

# =========================================================
# MAIN
# =========================================================
def main():
    forzar_ejecucion = (len(sys.argv) > 1 and sys.argv[1] == "--force")

    if not forzar_ejecucion and not es_periodo_de_actualizacion():
        print("[INFO] Automatización detenida por calendario.")
        sys.exit(0)

    print("[PROCESO] Conectando con la API y estructura de Drive...")
    archivos_drive = listar_archivos_drive_publico(FOLDER_ID)
    
    if not archivos_drive:
        print("[⚠️] No se encontraron archivos legibles en la carpeta de Drive o está inaccesible.")
        sys.exit(0)

    # Filtrado: Que inicien con 8 números correlativos (YYYYMMDD) y sean .pdf
    archivos_validos = []
    for f in archivos_drive:
        name = f["name"]
        if name.lower().endswith(".pdf") and re.match(r"^\d{8}", name):
            archivos_validos.append(f)
            
    # Ordenar estrictamente por nombre de menor a mayor (Cronológico)
    archivos_validos.sort(key=lambda x: x["name"])
    
    print(f"[INFO] {len(archivos_validos)} actas encontradas en Drive listas para procesar.")
    
    proximo_index_chunk = get_next_free_chunk_index()
    nuevos_hallazgos = 0

    for f in archivos_validos:
        name = f["name"]
        file_id = f["id"]
        id_base = name.replace(".pdf", "").replace(".PDF", "")

        # Evitar procesar lo que ya existe
        if codigo_ya_indexado(id_base):
            continue

        print(f"\n[📥 DESCARGANDO] Sincronizando: {name}")
        temp_pdf = Path(f"temp_acta_corriente.pdf")
        
        if descargar_pdf_drive(file_id, temp_pdf):
            exito = procesar_pdf_local(temp_pdf, proximo_index_chunk, name)
            if temp_pdf.exists():
                temp_pdf.unlink()
                
            if exito:
                proximo_index_chunk += 1
                nuevos_hallazgos += 1
                time.sleep(1)
        else:
            print(f"  [⚠️] Error al intentar descargar: {name}")

    print(f"\n[INFO] Ejecución completada. Chunks creados en esta corrida: {nuevos_hallazgos}")

if __name__ == "__main__":
    main()
