#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
update_boletines.py — Versión 1.0.8

1. Lee el directorio JSON_CHUNKS_DIR y detecta el archivo bo­letines_part_N.jsonl con N más alto.
2. Extrae de ese archivo el último número de boletín procesado (ej. 525).
3. Calcula NBOL = último + 1 (526).
4. Scrapea la web de Quilmes para confirmar si existe boletín NBOL.
5. Descarga el PDF https://quilmes.gov.ar/pdf/boletines/boletin-NBOL.pdf.
6. Procesa cada página del PDF en un objeto {id, archivo, página, fragmento}, usando la fecha extraída de la web.
7. Guarda esos objetos en el nuevo chunk bo­letines_part_(N+1).jsonl.
"""

import os
import re
import json
import requests
import fitz  # PyMuPDF
from bs4 import BeautifulSoup
from pathlib import Path
from urllib.parse import urljoin
from datetime import datetime

VERSION = "1.0.8"
JSON_CHUNKS_DIR = Path("json_chunks")
PDF_OUTPUT_DIR = Path("pdfs")
BASE_LIST_URL = "https://quilmes.gov.ar/institucional/gobierno_abierto_boletines.php"
PDF_BASE_URL  = "https://quilmes.gov.ar/pdf/boletines/"

print(f"\n=== Ejecutando update_boletines.py v{VERSION} ===\n")

def find_latest_chunk_index():
    JSON_CHUNKS_DIR.mkdir(exist_ok=True)
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

def extract_boletin_number(id_str):
    m = re.search(r"boletin-(\d+)\.pdf", id_str)
    if not m:
        raise RuntimeError(f"No pude extraer nro de boletín de id: {id_str}")
    return int(m.group(1))

def scrape_available_boletines():
    print("[INFO] Scrapeando lista de boletines en la web...")
    r = requests.get(BASE_LIST_URL, timeout=10)
    r.raise_for_status()
    soup = BeautifulSoup(r.text, "html.parser")
    boletines = {}
    for item in soup.find_all("div", class_="boletin-entry"):
        # Suponiendo estructura <div class="boletin-entry"><span class="fecha">25.07.25</span><a href="...boletin-526.pdf">...</a></div>
        fecha_txt = item.find("span", class_="fecha").get_text(strip=True)
        a = item.find("a", href=re.compile(r"boletin-\d+\.pdf"))
        href = a["href"]
        nro = int(re.search(r"boletin-(\d+)\.pdf", href).group(1))
        # convertir fecha dd.MM.yy a YYYYMMDD
        d, m, y = fecha_txt.split(".")
        full_year = "20" + y
        fecha_fmt = f"{full_year}{m}{d}"
        boletines[nro] = {"url": href, "fecha": fecha_fmt}
    return boletines

def download_pdf(nro):
    PDF_OUTPUT_DIR.mkdir(exist_ok=True)
    url = urljoin(PDF_BASE_URL, f"boletin-{nro}.pdf")
    dest = PDF_OUTPUT_DIR / f"boletin-{nro}.pdf"
    print(f"[INFO] Descargando {url} ...")
    resp = requests.get(url, timeout=15)
    resp.raise_for_status()
    with open(dest, "wb") as f:
        f.write(resp.content)
    return dest

def pdf_to_fragments(pdf_path, fecha):
    print(f"[INFO] Procesando PDF para generar fragmentos...")
    fragments = []
    doc = fitz.open(pdf_path)
    filename = f"{fecha} - {pdf_path.name}"
    # renombrar archivo con fecha
    new_path = pdf_path.parent / filename
    os.replace(pdf_path, new_path)
    for i, page in enumerate(doc, start=1):
        text = page.get_text().strip()
        frag = {
            "id":      f"{filename}_p{i}_f0",
            "archivo": filename,
            "pagina":  i,
            "fragmento": text
        }
        fragments.append(frag)
    return fragments

def save_new_chunk(idx, fragments):
    out = JSON_CHUNKS_DIR / f"boletines_part_{idx}.jsonl"
    print(f"[INFO] Guardando nuevo chunk: {out.name}")
    with open(out, "w", encoding="utf-8") as f:
        for frag in fragments:
            f.write(json.dumps(frag, ensure_ascii=False) + "\n")
    return out

def main():
    last_idx = find_latest_chunk_index()
    print(f"[INFO] Último chunk index: {last_idx}")
    if last_idx < 0:
        last_boletin = 0
    else:
        last_id = load_last_chunk_file(last_idx)
        last_boletin = extract_boletin_number(last_id)
    print(f"[INFO] Último boletín procesado: {last_boletin}")

    next_boletin = last_boletin + 1
    disponibles = scrape_available_boletines()
    if next_boletin not in disponibles:
        print(f"[INFO] Boletín {next_boletin} no disponible aún. Saliendo.")
        return

    info = disponibles[next_boletin]
    pdf_path = download_pdf(next_boletin)
    fragments = pdf_to_fragments(pdf_path, info["fecha"])
    new_chunk_idx = last_idx + 1
    save_new_chunk(new_chunk_idx, fragments)
    print(f"[OK] Se generó boletines_part_{new_chunk_idx}.jsonl con {len(fragments)} fragmentos.")

if __name__ == "__main__":
    main()
