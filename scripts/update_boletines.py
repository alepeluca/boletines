#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
update_boletines.py — Versión 1.0.10

1. Lee json_chunks/ y detecta el boletines_part_N.jsonl con N más alto.
2. Extrae de ese archivo el último número de boletín (ej. 525).
3. Calcula NBOL = último + 1 (526).
4. Scrapea la web:
     - Encuentra todos los <a href="...boletin-XXX.pdf">
     - Toma el texto completo de su contenedor (parent), que incluye “25.07.25Boletín…”
     - Extrae la fecha “dd.MM.yy” y la convierte a “YYYYMMDD”.
5. Descarga https://quilmes.gov.ar/pdf/boletines/boletin-NBOL.pdf.
6. Procesa cada página en {id, archivo, página, fragmento}, renombrando el PDF a
     “YYYYMMDD - boletin-NBOL.pdf”.
7. Guarda en json_chunks/boletines_part_(N+1).jsonl.
"""

import os, re, json, requests, fitz
from bs4 import BeautifulSoup
from pathlib import Path
from urllib.parse import urljoin

VERSION = "1.0.10"
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

def load_last_boletin_number(idx):
    if idx < 0: return 0
    path = JSON_CHUNKS_DIR / f"boletines_part_{idx}.jsonl"
    last_id = None
    for line in path.read_text(encoding="utf-8").splitlines():
        obj = json.loads(line)
        last_id = obj.get("id", last_id)
    if not last_id: return 0
    m = re.search(r"boletin-(\d+)\.pdf", last_id)
    return int(m.group(1)) if m else 0

def scrape_boletines_list():
    print("[INFO] Scrapeando lista de boletines en la web...")
    r = requests.get(LIST_URL, timeout=10)
    r.raise_for_status()
    soup = BeautifulSoup(r.text, "html.parser")
    result = {}
    for a in soup.find_all("a", href=re.compile(r"boletin-\d+\.pdf")):
        href = a["href"]
        nro = int(re.search(r"boletin-(\d+)\.pdf", href).group(1))
        container = a.parent  # toma todo el texto del contenedor
        raw = container.get_text(separator=" ", strip=True)
        # Buscar fecha dd.MM.yy
        m = re.search(r"(\d{2})\.(\d{2})\.(\d{2})", raw)
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
    dest.write_bytes(r.content)
    return dest

def pdf_to_fragments(pdf_path: Path, fecha: str):
    print(f"[INFO] Procesando PDF {pdf_path.name}")
    doc = fitz.open(pdf_path)
    new_name = f"{fecha} - {pdf_path.name}"
    new_path = pdf_path.parent / new_name
    os.replace(pdf_path, new_path)

    frags = []
    for i, page in enumerate(doc, start=1):
        text = page.get_text().strip()
        frags.append({
            "id":      f"{new_name}_p{i}_f0",
            "archivo": new_name,
            "pagina":  i,
            "fragmento": text
        })
    return frags

def save_new_chunk(idx: int, fragments: list):
    out = JSON_CHUNKS_DIR / f"boletines_part_{idx}.jsonl"
    print(f"[INFO] Guardando chunk {out.name} ({len(fragments)} fragmentos)")
    with open(out, "w", encoding="utf-8") as f:
        for frag in fragments:
            f.write(json.dumps(frag, ensure_ascii=False) + "\n")

def main():
    last_idx   = find_latest_chunk_index()
    last_bolet = load_last_boletin_number(last_idx)
    print(f"[INFO] Último chunk: {last_idx}, último boletín: {last_bolet}")

    next_bolet = last_bolet + 1
    disponibles = scrape_boletines_list()
    if next_bolet not in disponibles:
        print(f"[INFO] Boletín {next_bolet} no disponible aún.")
        return

    info    = disponibles[next_bolet]
    pdf     = download_pdf(next_bolet)
    frags   = pdf_to_fragments(pdf, info["fecha"])
    save_new_chunk(last_idx + 1, frags)

    print(f"[OK] Se generó json_chunks/boletines_part_{last_idx+1}.jsonl")

if __name__ == "__main__":
    main()
