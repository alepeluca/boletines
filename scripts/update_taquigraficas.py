#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
update_taquigraficas.py — Versión 1.2.0
"""

import json
import os
import re
import io
import sys
from datetime import datetime, timedelta
from pathlib import Path
import fitz  # PyMuPDF

VERSION = "1.2.0"
FECHA_MODIFICACION = "16-06-2026"

JSON_CHUNKS_DIR = Path("json_chunks")
JSON_CHUNKS_DIR.mkdir(exist_ok=True)

DRIVE_FOLDER_URL = "https://drive.google.com/drive/folders/1vBrQH0h1ddIlplj3ChZ0VkqAK8UjgecB"

print("\n" + "=" * 60)
print(f"🎙️ ACTUALIZADOR DE ACTAS TAQUIGRÁFICAS v{VERSION}")
print(f"📅 Última modificación: {FECHA_MODIFICACION}")
print("=" * 60 + "\n")

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

def get_next_free_chunk_index():
    indices = []
    for f in JSON_CHUNKS_DIR.glob("taqui_part*.jsonl"):
        match = re.match(r"^taqui_part(\d+)\.jsonl$", f.name, re.IGNORECASE)
        if match:
            indices.append(int(match.group(1)))
    if not indices:
        return 1
    return max(indices) + 1

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

def procesar_pdf_taquigrafica(pdf_path, chunk_index):
    try:
        doc = fitz.open(pdf_path)
    except Exception as e:
        print(f"[ERROR] No se pudo abrir {pdf_path.name}: {e}")
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
    nombre_archivo = pdf_path.name
    id_base = nombre_archivo.replace(".pdf", "").replace(".PDF", "")
    
    timestamp_procesado = datetime.utcnow().isoformat()
    part_cuatro_digitos = f"{chunk_index:04d}"
    salida = JSON_CHUNKS_DIR / f"taqui_part{part_cuatro_digitos}.jsonl"

    with open(salida, "w", encoding="utf-8") as f:
        for f_data in frags_finales:
            chunk_linea = {
                "codigo": id_base,
                "url": DRIVE_FOLDER_URL,
                "archivo": nombre_archivo,
                "id": f"{nombre_archivo}_p{f_data['pagina']}_f0",
                "pagina": f_data['pagina'],
                "fecha_acta": fecha_acta,
                "fragmento": f_data['fragmento'],
                "procesado": timestamp_processed := timestamp_procesado
            }
            f.write(json.dumps(chunk_linea, ensure_ascii=False) + "\n")
    print(f"[OK] CHUNK GENERADO -> {salida.name} (Fecha: {fecha_acta})")
    return True

def main():
    # Detectar si GitHub Actions nos ordena ignorar el calendario
    forzar_ejecucion = (len(sys.argv) > 1 and sys.argv[1] == "--force")

    if forzar_ejecucion:
        print("[MODO] MODO FORZADO ACTIVADO: Ignorando restricción de fechas calendarias.")
    else:
        if not es_periodo_de_actualizacion():
            print("[INFO] Automatización detenida: No corresponde actualización según el calendario.")
            sys.exit(0)

    print("[PROCESO] Buscando actas en el directorio...")
    proximo_index_chunk = get_next_free_chunk_index()
    
    # Buscar PDFs en la raíz o en una carpeta temporal donde los descargue tu flujo
    directorio_origen = Path(".")
    archivos_pdf = list(directorio_origen.glob("*.pdf")) + list(directorio_origen.glob("*.PDF"))
    
    nuevos_hallazgos = 0
    for pdf_file in archivos_pdf:
        id_base = pdf_file.name.replace(".pdf", "").replace(".PDF", "")
        archivo_ya_existe = False
        
        for chunk_file in JSON_CHUNKS_DIR.glob("taqui_part*.jsonl"):
            try:
                with open(chunk_file, "r", encoding="utf-8") as cf:
                    primera_ln = cf.readline()
                    if primera_ln and id_base in primera_ln:
                        archivo_ya_existe = True
                        break
            except Exception:
                continue
                
        if not archivo_ya_existe:
            print(f"\n[NUEVO] Analizando: {pdf_file.name}")
            exito = procesar_pdf_taquigrafica(pdf_file, proximo_index_chunk)
            if exito:
                proximo_index_chunk += 1
                nuevos_hallazgos += 1
                
    print(f"\n[INFO] Tarea finalizada. Nuevas actas indexadas: {nuevos_hallazgos}")

if __name__ == "__main__":
    main()
