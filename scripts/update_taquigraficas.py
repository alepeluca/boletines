#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
update_taquigraficas.py — Versión 2.3.0

FLUJO HYPER-ROBUSTO CON SUBDIR 'taqui' Y FORMATO 4 DÍGITOS f"{idx:04d}":
1. Verifica el calendario quincenal (o atiende la bandera manual --force).
2. Consulta múltiples endpoints públicos de Google Drive evadiendo bloqueos de cookies.
3. Escanea la subcarpeta exclusiva 'json_chunks/taqui/' para saber el último index.
4. Filtra actas válidas (YYYYMMDD*.pdf) y las ordena de la más vieja a la más nueva.
5. Descarga, procesa y elimina de forma secuencial una por una para cuidar los recursos.
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

VERSION = "2.3.0"
FECHA_MODIFICACION = "17-06-2026"

# Cambiado para que opere directamente en la subcarpeta 'taqui'
JSON_CHUNKS_DIR = Path("json_chunks/taqui")
JSON_CHUNKS_DIR.mkdir(parents=True, exist_ok=True)

FOLDER_ID = "1vBrQH0h1ddIlplj3ChZ0VkqAK8UjgecB"
DRIVE_FOLDER_URL = f"https://drive.google.com/drive/folders/{FOLDER_ID}"

print("\n" + "=" * 60)
print(f"🎙️ ACTUALIZADOR ULTRA-ROBUSTO DE ACTAS TAQUIGRÁFICAS v{VERSION}")
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
# EXTRACCIÓN INTELIGENTE DE DRIVE MULTI-ENDPOINT
# =========================================================
def get_next_free_chunk_index():
    indices = []
    # Busca solo dentro de json_chunks/taqui/
    for f in JSON_CHUNKS_DIR.glob("taqui_part*.jsonl"):
        match = re.match(r"^taqui_part(\d+)\.jsonl$", f.name, re.IGNORECASE)
        if match:
            indices.append(int(match.group(1)))
    if not indices:
        return 1
    return max(indices) + 1

def codigo_ya_indexado(id_base):
    # Busca duplicados solo dentro de la subcarpeta 'taqui'
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
    Escanea la carpeta pública usando una ventana de proximidad de tokens cruzados
    sobre múltiples URLs espejo para garantizar la lectura en servidores en la nube.
    """
    files = []
    seen_ids = set()
    
    urls = [
        f"https://drive.google.com/embeddedfolderview?id={folder_id}&hl=es",
        f"https://drive.google.com/drive/folders/{folder_id}?hl=es",
        f"https://docs.google.com/embeddedfolderview?id={folder_id}"
    ]
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
        "Accept-Language": "es-ES,es;q=0.9,en;q=0.8"
    }
    
    for url in urls:
        try:
            print(f"[CONEXIÓN] Buscando catálogo en: {url}")
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
        except Exception as e:
            print(f"  [AVISO] No se pudo leer este canal: {e}")
            continue
            
    return files

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
            for chunk in response.iter_content(chunk_size=8192):
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
        print(f"  [ERROR] El archivo PDF está corrupto o incompleto: {e}")
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
    
    # CAMBIO: Nomenclatura uniforme estricta de 4 dígitos f"{chunk_index:04d}"
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
            
    print(f"  [OK] Chunk guardado -> {salida} (Fecha de Sesión: {fecha_acta})")
    return True

# =========================================================
# MAIN
# =========================================================
def main():
    forzar_ejecucion = (len(sys.argv) > 1 and sys.argv[1] == "--force")

    if not forzar_ejecucion and not es_periodo_de_actualizacion():
        print("[INFO] Automatización saltada por calendario quincenal.")
        sys.exit(0)

    print("[PROCESO] Analizando el catálogo de Drive en subcarpeta 'taqui/'...")
    archivos_validos = listar_archivos_drive_publico(FOLDER_ID)
    
    if not archivos_validos:
        print("[⚠️] No se pudo mapear la carpeta de Drive con los métodos actuales.")
        sys.exit(1)

    # Ordenar cronológicamente por nombre (Menor a Mayor: YYYYMMDD antiguos primero)
    archivos_validos.sort(key=lambda x: x["name"])
    print(f"[INFO] Se detectaron {len(archivos_validos)} actas en total dentro de Drive.")
    
    proximo_index_chunk = get_next_free_chunk_index()
    nuevos_hallazgos = 0

    for f in archivos_validos:
        name = f["name"]
        file_id = f["id"]
        id_base = name.replace(".pdf", "").replace(".PDF", "")

        if codigo_ya_indexado(id_base):
            continue

        print(f"\n[📥 DESCARGA] Sincronizando acta quincenal: {name}")
        temp_pdf = Path("temp_acta_procesamiento.pdf")
        
        if descargar_pdf_drive(file_id, temp_pdf):
            exito = procesar_pdf_local(temp_pdf, proximo_index_chunk, name)
            if temp_pdf.exists():
                temp_pdf.unlink()  # Borrado inmediato del PDF para liberar espacio
                
            if exito:
                proximo_index_chunk += 1
                nuevos_hallazgos += 1
                time.sleep(1.5)  # Delay prudencial antispam
        else:
            print(f"  [⚠️] Falla al descargar archivo: {name}")

    print(f"\n[INFO] Sincronización finalizada en 'json_chunks/taqui/'. Chunks nuevos creados: {nuevos_hallazgos}")

if __name__ == "__main__":
    main()
