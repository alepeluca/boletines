"""
update_boletines.py - v1.0.7

Este script escanea archivos PDF nuevos en la carpeta 'boletines_pdf/',
verifica cuál fue el último boletín procesado (mirando el archivo JSONL más reciente
en orden numérico del nombre), y genera un archivo JSONL con la información extraída
de los PDFs nuevos para ser usada por sistemas posteriores.

Autor: Alejandro Orellano
"""

import os
import glob
import json
import re
from PyPDF2 import PdfReader
from datetime import datetime

# Carpetas
PDF_FOLDER = "boletines_pdf"
JSONL_FOLDER = "boletines_jsonl"

# Prefijo del nombre de salida
OUTPUT_PREFIX = "boletines_part_"

# Versión del script
VERSION = "1.0.7"


def get_last_processed_boletin_number():
    """Lee el último archivo JSONL y detecta el número del último boletín procesado."""
    jsonl_files = sorted(glob.glob(os.path.join(JSONL_FOLDER, "*.jsonl")))
    if not jsonl_files:
        return 0

    # Tomar el archivo de mayor número (asumiendo que están en orden)
    last_jsonl_file = jsonl_files[-1]
    last_boletin_number = 0

    with open(last_jsonl_file, "r", encoding="utf-8") as f:
        for line in f:
            try:
                data = json.loads(line)
                match = re.search(r"boletin-(\d+)\.pdf", data.get("id", ""))
                if match:
                    num = int(match.group(1))
                    if num > last_boletin_number:
                        last_boletin_number = num
            except json.JSONDecodeError:
                continue

    return last_boletin_number


def extract_text_from_pdf(pdf_path):
    """Extrae el texto completo del PDF."""
    try:
        reader = PdfReader(pdf_path)
        text = ""
        for page in reader.pages:
            text += page.extract_text() or ""
        return text.strip()
    except Exception as e:
        print(f"Error leyendo {pdf_path}: {e}")
        return ""


def main():
    print(f"[update_boletines v{VERSION}]")

    last_processed = get_last_processed_boletin_number()
    print(f"Último boletín procesado: {last_processed}")

    pdf_files = sorted(glob.glob(os.path.join(PDF_FOLDER, "*.pdf")))
    nuevos_boletines = []

    for pdf_file in pdf_files:
        match = re.search(r"boletin-(\d+)\.pdf", os.path.basename(pdf_file))
        if not match:
            continue
        num = int(match.group(1))
        if num > last_processed:
            nuevos_boletines.append((num, pdf_file))

    if not nuevos_boletines:
        print("No hay boletines nuevos para procesar.")
        return

    output_index = len(glob.glob(os.path.join(JSONL_FOLDER, "*.jsonl"))) + 1
    output_filename = f"{OUTPUT_PREFIX}{output_index}.jsonl"
    output_path = os.path.join(JSONL_FOLDER, output_filename)

    print(f"Procesando {len(nuevos_boletines)} boletines nuevos...")
    with open(output_path, "w", encoding="utf-8") as out_file:
        for num, pdf_path in nuevos_boletines:
            texto = extract_text_from_pdf(pdf_path)
            out = {
                "id": f"{datetime.now().strftime('%Y%m%d')} - {os.path.basename(pdf_path).replace('.pdf', '')}_p1_f0",
                "text": texto,
            }
            out_file.write(json.dumps(out, ensure_ascii=False) + "\n")
            print(f"✔️ Procesado boletín {num}")

    print(f"Listo. Archivo generado: {output_filename}")


if __name__ == "__main__":
    main()
