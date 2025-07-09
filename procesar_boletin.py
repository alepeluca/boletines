# procesar_boletin.py

import os
import re
import json
import requests
import fitz  # PyMuPDF

CHUNKS_DIR = "json_chunks"
PDF_BASE_URL = "https://quilmes.gov.ar/pdf/boletines/"
CHUNK_SIZE = 1200


def get_latest_boletin_number():
    os.makedirs(CHUNKS_DIR, exist_ok=True)
    archivos = os.listdir(CHUNKS_DIR)
    numeros = [
        int(re.search(r'boletines_part_(\d+)\.jsonl', f).group(1))
        for f in archivos if re.match(r'boletines_part_\d+\.jsonl', f)
    ]
    return max(numeros) if numeros else 500  # asumimos empieza desde el 500


def descargar_pdf(numero):
    url = f"{PDF_BASE_URL}boletin-{numero}.pdf"
    response = requests.get(url)
    if response.status_code == 200:
        path = f"boletin-{numero}.pdf"
        with open(path, "wb") as f:
            f.write(response.content)
        return path
    return None


def extraer_texto(path_pdf):
    texto_total = ""
    with fitz.open(path_pdf) as doc:
        for pagina in doc:
            texto_total += pagina.get_text()
    return texto_total


def dividir_en_chunks(texto, max_chars):
    return [texto[i:i + max_chars].strip() for i in range(0, len(texto), max_chars)]


def guardar_chunks_jsonl(chunks, numero, archivo_pdf):
    salida_path = os.path.join(CHUNKS_DIR, f"boletines_part_{numero}.jsonl")
    with open(salida_path, "w", encoding="utf-8") as f:
        for i, chunk in enumerate(chunks):
            json.dump({
                "id": f"{archivo_pdf}_p1_f{i}",
                "archivo": archivo_pdf,
                "pagina": 1,
                "fragmento": chunk
            }, f, ensure_ascii=False)
            f.write("\n")
    print(f"✅ Guardado: {salida_path}")


def main():
    ultimo = get_latest_boletin_number()
    siguiente = ultimo + 1
    nombre_pdf = f"boletin-{siguiente}.pdf"

    print(f"🔍 Buscando {nombre_pdf}...")
    pdf_path = descargar_pdf(siguiente)

    if not pdf_path:
        print("📭 No hay boletín nuevo disponible.")
        return

    print(f"📥 Descargado {pdf_path}")
    texto = extraer_texto(pdf_path)
    chunks = dividir_en_chunks(texto, CHUNK_SIZE)
    guardar_chunks_jsonl(chunks, siguiente, nombre_pdf)

    os.remove(pdf_path)  # limpieza opcional


if __name__ == "__main__":
    main()
