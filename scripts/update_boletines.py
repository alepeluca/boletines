#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
update_boletines.py — Versión 1.0.9

1. Lee el directorio json_chunks/ y detecta el archivo boletines_part_N.jsonl con N más alto.
2. De ese archivo extrae el último “id” y determina el número de boletín procesado (ej. 525).
3. Calcula NBOL = último + 1 (526).
4. Scrapea https://quilmes.gov.ar/institucional/gobierno_abierto_boletines.php  
   — extrae, junto al enlace, la fecha que aparece como “dd.MM.yy” antes del link.
5. Descarga el PDF https://quilmes.gov.ar/pdf/boletines/boletin-NBOL.pdf.
6. Procesa cada página del PDF en objetos {id, archivo, página, fragmento}, usando la fecha formateada “aaaammdd”:
     - renombra el PDF a “aaaammdd - boletin-NBOL.pdf”
     - genera IDs como “aaaammdd - boletin-NBOL.pdf_pX_f0”
7. Guarda esos objetos en json_chunks/boletines_part_(N+1).jsonl
"""

import os
import re
import json
import requests
import fitz  # PyMuPDF
from bs4 import BeautifulSoup
from pathlib import Path
from urllib.parse import urljoin

VERSION = "1.0.9"
JSON_CHUNKS_DIR = Path("json_chunks")
PDF_DIR         = Path("pdfs")
LIST_URL        = "https://quilmes.gov.ar/institucional/gobierno_abierto_boletines.php"
PDF_BASE_URL    = "https://quilmes.gov.ar/pdf/boletines/"

print(f"\n=== Ejecutando update_boletines.py v{VERSION} ===\n")

def find_latest_chunk_index():
    JSON_CHUNKS_DIR.mkdir(exist_ok=True)
    files = [f.name for f in JSON_CHUNKS_DIR.glob("boletines_part_*.jsonl")]
    nums  = [int(re.search(r"boletines_part_(\d+)\.jsonl", f).group(1)) for f in files]
    return max(nums) if nums else -1

def load_last_boletin_number(chunk_idx):
    if chunk_idx < 0:
        return 0
    path = JSON_CHUNKS_DIR / f"boletines_part_{chunk_idx}.jsonl"
    last_id = None
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            obj = json.loads(line)
            last_id = obj.get("id", last_id)
    if not last_id:
        return 0
    m = re.search(r"boletin-(\d+)\.pdf", last_id)
    return int(m.group(1)) if m else 0

def scrape_boletines_list():
    """Devuelve dict[nro] = {"url": href, "fecha": "aaaammdd"}"""
    r = requests.get(LIST_URL, timeout=10)
    r.raise_for_status()
    soup = BeautifulSoup(r.text, "html.parser")
    result = {}
    entries = soup.find_all("a", href=re.compile(r"boletin-\d+\.pdf"))
    for a in entries:
        href = a["href"]
        nro = int(re.search(r"boletin-(\d+)\.pdf", href).group(1))
        # buscar fecha en el texto previo
        text = a.find_previous(text=True)
        m = re.search(r"(\d{2})\.(\d{2})\.(\d{2})", text or "")
        if not m:
            continue
        d, mo, y2 = m.groups()
        fecha = f"20{y2}{mo}{d}"
        result[nro] = {"url": href, "fecha": fecha}
    return result

def download_pdf(nro):
    PDF_DIR.mkdir(exist_ok=True)
    url = urljoin(PDF_BASE_URL, f"boletin-{nro}.pdf")
    dest = PDF_DIR / f"boletin-{nro}.pdf"
    print(f"[INFO] Descargando {url}")
    r = requests.get(url, timeout=15)
    r.raise_for_status()
    with open(dest, "wb") as f:
        f.write(r.content)
    return dest

def pdf_to_fragments(pdf_path: Path, fecha: str):
    print(f"[INFO] Procesando PDF {pdf_path.name}")
    doc = fitz.open(pdf_path)
    # renombrar con fecha
    new_name = f"{fecha} - {pdf_path.name}"
    new_path = pdf_path.parent / new_name
    os.replace(pdf_path, new_path)

    fragments = []
    for i, page in enumerate(doc, start=1):
        text = page.get_text().strip()
        fragments.append({
            "id":      f"{new_name}_p{i}_f0",
            "archivo": new_name,
            "pagina":  i,
            "fragmento": text
        })
    return fragments

def save_new_chunk(idx: int, frags: list):
    out = JSON_CHUNKS_DIR / f"boletines_part_{idx}.jsonl"
    print(f"[INFO] Guardando chunk {out.name} con {len(frags)} fragments")
    with open(out, "w", encoding="utf-8") as f:
        for frag in frags:
            f.write(json.dumps(frag, ensure_ascii=False) + "\n")

def main():
    # 1–3
    last_idx   = find_latest_chunk_index()
    last_bolet = load_last_boletin_number(last_idx)
    print(f"[INFO] Último chunk: {last_idx}, último boletín: {last_bolet}")

    # 4–5
    next_bolet = last_bolet + 1
    disponibles = scrape_boletines_list()
    if next_bolet not in disponibles:
        print(f"[INFO] Boletín {next_bolet} no disponible aún.")
        return

    info = disponibles[next_bolet]
    pdf_path = download_pdf(next_bolet)

    # 6
    fragments = pdf_to_fragments(pdf_path, info["fecha"])

    # 7
    save_new_chunk(last_idx + 1, fragments)
    print(f"[OK] Se generó boletines_part_{last_idx+1}.jsonl")

if __name__ == "__main__":
    main()
