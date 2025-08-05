#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
update_boletines.py — Versión 1.0.6

1. Lee el directorio JSON_CHUNKS_DIR y detecta el archivo bo­letines_part_N.jsonl con N más alto.
2. Extrae de ese archivo el último número de boletín procesado (ej. 525).
3. Calcula NBOL = último + 1 (526).
4. Scrapea la web de Quilmes para confirmar si existe boletín NBOL.
5. Descarga el PDF https://quilmes.gov.ar/pdf/boletines/boletin-NBOL.pdf.
6. Procesa cada página del PDF en un objeto {id, archivo, página, fragmento}.
7. Guarda esos objetos en el nuevo chunk bo­letines_part_(N+1).jsonl.
"""

import os, re, json
import requests
import fitz  # PyMuPDF
from bs4 import BeautifulSoup
from pathlib import Path
from urllib.parse import urljoin

VERSION = "1.0.6"
JSON_CHUNKS_DIR = Path("json_chunks")
PDF_OUTPUT_DIR = Path("pdfs")
BASE_LIST_URL = "https://quilmes.gov.ar/institucional/gobierno_abierto_boletines.php"
PDF_BASE_URL  = "https://quilmes.gov.ar/pdf/boletines/"

print(f"\n=== Ejecutando update_boletines.py v{VERSION} ===\n")

def find_latest_chunk_index():
    files = [f.name for f in JSON_CHUNKS_DIR.glob("boletines_part_*.jsonl")]
    indices = [int(re.search(r"boletines_part_(\d+)\.jsonl", f).group(1)) for f in files]
    return max(indices) if indices else -1

def load_last_chunk_file(idx):
    path = JSON_CHUNKS_DIR / f"boletines_part_{idx}.jsonl"
    last_id = None
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            data = json.loads(line)
            last_id = data.get("id", last_id)
    if not last_id:
        raise RuntimeError(f"No se pudo leer último 'id' en {path}")
    return last_id

def extract_boletin_number_from_id(id_str):
    m = re.search(r"boletin-(\d+)\.pdf", id_str)
    if not m:
        raise RuntimeError(f"No pude extraer nro de boletín de id: {id_str}")
    return int(m.group(1))

def scrape_available_boletines():
    r = requests.get(BASE_LIST_URL, timeout=10)
    r.raise_for_status()
    soup = BeautifulSoup(r.text, "html.parser")
    links = []
    for a in soup.find_all("a", href=re.compile(r"boletin-\d+\.pdf")):
        url = a["href"]
        nro = int(re.search(r"boletin-(\d+)\.pdf", url).group(1))
        links.append((nro, url))
    return dict(links)

def download_pdf(nro):
    PDF_OUTPUT_DIR.mkdir(exist_ok=True)
    url = urljoin(PDF_BASE_URL, f"boletin-{nro}.pdf")
    dest = PDF_OUTPUT_DIR / f"boletin-{nro}.pdf"
    resp = requests.get(url, timeout=15)
    resp.raise_for_status()
    with open(dest, "wb") as f:
        f.write(resp.content)
    return dest

def pdf_to_fragments(pdf_path):
    fragments = []
    doc = fitz.open(pdf_path)
    for page_num in range(doc.page_count):
        text = doc.load_page(page_num).get_text().strip()
        frag = {
            "id":      f"{pdf_path.stem}_p{page_num+1}_f0",
            "archivo": pdf_path.name,
            "pagina":  page_num + 1,
            "fragmento": text
        }
        fragments.append(frag)
    return fragments

def save_new_chunk(idx, fragments):
    out = JSON_CHUNKS_DIR / f"boletines_part_{idx}.jsonl"
    with open(out, "w", encoding="utf-8") as f:
        for frag in fragments:
            f.write(json.dumps(frag, ensure_ascii=False) + "\n")
    return out

def main():
    # 1–2: último chunk y último boletín procesado
    last_chunk_idx = find_latest_chunk_index()
    print(f"Último chunk index: {last_chunk_idx}")
    if last_chunk_idx < 0:
        print("No hay chunks previos. Comenzar desde boletín 1.")
        last_boletin = 0
    else:
        last_id = load_last_chunk_file(last_chunk_idx)
        last_boletin = extract_boletin_number_from_id(last_id)
    print(f"Último boletín procesado: {last_boletin}")

    # 3–5: buscar si existe el siguiente boletín
    next_boletin = last_boletin + 1
    disponibles = scrape_available_boletines()
    if next_boletin not in disponibles:
        print(f"No existe aún boletín {next_boletin}. Nada que hacer.")
        return

    print(f"Nuevo boletín detectado: {next_boletin}")
    # 6: descargar
    pdf_path = download_pdf(next_boletin)
    print(f"Descargado: {pdf_path}")

    # 7: procesar y guardar nuevo chunk
    fragments = pdf_to_fragments(pdf_path)
    new_chunk_idx = last_chunk_idx + 1
    out_path = save_new_chunk(new_chunk_idx, fragments)
    print(f"Nuevo chunk generado: {out_path.name}")

if __name__ == "__main__":
    # Asegurarse de existir json_chunks/
    JSON_CHUNKS_DIR.mkdir(exist_ok=True)
    main()
