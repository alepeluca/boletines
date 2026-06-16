#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
update_taquigraficas.py — Versión 2.0.0

FLUJO INTELIGENTE:
1. Revisa si corresponde ejecutar según el calendario (o si es manual vía --force).
2. Escanea la API pública de Google Drive para listar los archivos de la carpeta.
3. Filtra archivos que empiecen con fecha (8 dígitos YYYYMMDD) y terminen en .pdf.
4. Los ordena cronológicamente (desde el más antiguo).
5. Descarga y procesa UNO a UNO sólo aquellos archivos que no existan ya en json_chunks/.
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

VERSION = "2.0.0"
FECHA_MODIFICACION = "16-06-2026"

JSON_CHUNKS_DIR = Path("json_chunks")
JSON_CHUNKS_DIR.mkdir(exist_ok=True)

# Parámetros públicos de Google Drive
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
# LÓGICA DE CHUNKS Y DRIVE
# =========================================================
def get_next_free_chunk_index():
    """Determina el siguiente índice de chunk 'taqui_partNNNN.jsonl'."""
    indices = []
    for f in JSON_CHUNKS_DIR.glob("taqui_part*.jsonl"):
        match = re.match(r"^taqui_part(\d+)\.jsonl$", f.name, re.IGNORECASE)
        if match:
            indices.append(int(match.group(1)))
    if not indices:
        return 1
    return max(indices) + 1

def codigo_ya_indexado(id_base):
    """Verifica si el acta ya tiene un chunk asignado."""
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
    """Consulta la API de vista de Drive para listar archivos sin tokens privados."""
    url = f"https://www.googleapis.com/drive/v3/files"
    params = {
        "q": f"'{folder_id}' in parents and trashed = false",
        "key": os.environ.get("GOOGLE_DRIVE_API_KEY", ""), # Opcional por si se alcanza límite público
        "fields": "files(id, name)",
        "pageSize": 1000
    }
    
    # Fallback si no hay API KEY: Usar el endpoint de exportación pública de catálogo de Drive
    try:
        # Intentamos obtenerlo simulando la carga del catálogo web público
        url_alt = f"https://docs.google.com/thumbnails?id={folder_id}" # Trick para chequear conectividad
        res = requests.get(url, params=params, timeout=20)
        if res.status_code == 200:
            return res.json().get("files", [])
    except Exception:
        pass
        
    # Endpoint secundario robusto para carpetas compartidas (Scraping de la estructura básica de Drive)
    try:
        url_scrape = f"https://drive.google.com/embeddedfolderview?id={folder_id}"
        res = requests.get(url_scrape, timeout=20)
        html = res.text
        # Capturamos pares de IDs y Nombres mediante expresiones regulares en el HTML embebido
        matches = re.findall(r'\["([^"]+)"\s*,\s*"([^"]+)"\s*,\s*"\w+"', html)
        files = []
        for fid, fname in matches:
            if fname.lower().endswith('.pdf'):
                files.append({"id": fid, "name": fname})
        return files
    except Exception as e:
        print(f"[ERROR] No se pudo acceder al listado de la carpeta pública de Drive: {e}")
        return []

def descargar_pdf_drive(file_id, dest_path):
    """Descarga un archivo PDF de Drive de forma individual resolviendo advertencias de tamaño."""
    url = "https://docs.google.com/uc"
    params = {"export": "download", "id": file_id}
    
    session = requests.Session()
    response = session.get(url, params=params, stream=True, timeout=30)
    
    # Chequear si Drive puso una página de confirmación por escaneo de virus
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
        print(f"  [ERROR] Al abrir el PDF: {e}")
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
            
    print(f"  [OK] Chunk guardado -> {salida.name} (Fecha Acta: {fecha_acta})")
    return True

# =========================================================
# MAIN
# =========================================================
def main():
    forzar_ejecucion = (len(sys.argv) > 1 and sys.argv[1] == "--force")

    if not forzar_ejecucion and not es_periodo_de_actualizacion():
        print("[INFO] Automatización saltada por calendario.")
        sys.exit(0)

    print("[PROCESO] Conectando con Google Drive para listar archivos...")
    archivos_drive = listar_archivos_drive_publico(FOLDER_ID)
    
    if not archivos_drive:
        print("[⚠️] No se encontraron archivos legibles en la carpeta de Drive o está inaccesible.")
        sys.exit(0)

    # Filtrar solo archivos válidos: ej: 20240312... .pdf (que empiecen con 8 números de fecha YYYYMMDD)
    archivos_validos = []
    for f in archivos_drive:
        name = f["name"]
        if name.lower().endswith(".pdf") and re.match(r"^\d{8}", name):
            archivos_validos.append(f)
            
    # CRUCIAL: Ordenar por nombre de menor a mayor (Cronológicamente desde el más viejo: 2024... -> 2025...)
    archivos_validos.sort(key=lambda x: x["name"])
    
    print(f"[INFO] Se detectaron {len(archivos_validos)} actas válidas en Drive (Ordenadas desde la más antigua).")
    
    proximo_index_chunk = get_next_free_chunk_index()
    nuevos_hallazgos = 0

    # Procesamiento secuencial uno a uno
    for f in archivos_validos:
        name = f["name"]
        file_id = f["id"]
        id_base = name.replace(".pdf", "").replace(".PDF", "")

        # Verificamos si ya existe el chunk local para saltarlo y no gastar ancho de banda
        if codigo_ya_indexado(id_base):
            continue

        print(f"\n[📥 DESCARGA UNITARIA] Traiendo acta faltante: {name}")
        temp_pdf = Path(f"temp_acta_corriente.pdf")
        
        if descargar_pdf_drive(file_id, temp_pdf):
            # Una vez descargado con éxito, se fragmenta inmediatamente
            exito = procesar_pdf_local(temp_pdf, proximo_index_chunk, name)
            if temp_pdf.exists():
                temp_pdf.unlink() # Borramos el archivo temporal al instante para liberar espacio
                
            if exito:
                proximo_index_chunk += 1
                nuevos_hallazgos += 1
                time.sleep(1) # Delay prudencial de 1 segundo entre actas
        else:
            print(f"  [⚠️] Error al descargar de Drive el archivo {name}")

    print(f"\n[INFO] Sincronización finalizada con éxito. Actas procesadas en esta corrida: {nuevos_hallazgos}")

if __name__ == "__main__":
    main()
