#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
update_boletines.py — Versión 2.1.0

FLUJO:
1. Detecta el último chunk existente en la subcarpeta 'bolet/'.
2. Lee el último boletín guardado dentro de ese chunk.
3. Calcula el siguiente boletín esperado.
4. Scrapea la web oficial.
5. Si el siguiente boletín existe, lo procesa y genera el nuevo chunk incremental con 4 dígitos.

MEJORAS DE ARQUITECTURA:
- Apunta nativamente a json_chunks/bolet/
- Nomenclatura uniforme con padding de 4 ceros (_part_0001.jsonl)
"""

import json
import re
import tempfile
from pathlib import Path
from urllib.parse import urljoin

import fitz
import requests
from bs4 import BeautifulSoup

# =========================================================
# CONFIG
# =========================================================

VERSION = "2.1.0"
FECHA_MODIFICACION = "17-06-2026"

# Cambiado para que apunte directamente a la subcarpeta de boletines
JSON_CHUNKS_DIR = Path("json_chunks/bolet")
PDF_DIR = Path("pdfs")

LIST_URL = (
    "https://quilmes.gov.ar/institucional/"
    "gobierno_abierto_boletines.php"
)

PDF_BASE_URL = (
    "https://quilmes.gov.ar/pdf/boletines/"
)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 "
        "(Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 "
        "(KHTML, like Gecko) "
        "Chrome/124.0 Safari/537.36"
    )
}

# Crea la estructura completa si no existe
JSON_CHUNKS_DIR.mkdir(parents=True, exist_ok=True)
PDF_DIR.mkdir(exist_ok=True)

print("\n" + "=" * 60)
print(f"🚀 UPDATE BOLETINES v{VERSION}")
print(f"📅 Última modificación: {FECHA_MODIFICACION}")
print("=" * 60 + "\n")


# =========================================================
# HELPERS
# =========================================================

def find_latest_chunk():
    archivos = []

    # Ahora busca dentro de la nueva subcarpeta
    for f in JSON_CHUNKS_DIR.glob("boletines_part_*.jsonl"):
        # Adaptado para capturar tanto formatos viejos (_part_1) como nuevos (_part_0001)
        match = re.search(r"boletines_part_(\d+)\.jsonl", f.name)
        if match:
            archivos.append((int(match.group(1)), f))

    if not archivos:
        return -1, None

    archivos.sort(key=lambda x: x[0])
    return archivos[-1]


def load_last_boletin_number(chunk_path):
    ultima_linea = None

    with open(chunk_path, "r", encoding="utf-8") as f:
        for linea in f:
            linea = linea.strip()
            if linea:
                ultima_linea = linea

    if not ultima_linea:
        return 0

    obj = json.loads(ultima_linea)
    archivo = obj.get("archivo", "")

    match = re.search(r"boletin[-_](\d+)\.pdf", archivo, re.IGNORECASE)
    if not match:
        return 0

    return int(match.group(1))


def scrape_boletines_list():
    print("[INFO] Scrapeando lista de boletines...")
    response = requests.get(LIST_URL, headers=HEADERS, timeout=30)
    response.raise_for_status()

    soup = BeautifulSoup(response.text, "html.parser")
    resultado = {}

    regex = re.compile(r"boletin[-_](\d+)\.pdf", re.IGNORECASE)

    for a in soup.find_all("a", href=regex):
        href = a.get("href", "")
        match = regex.search(href)
        if not match:
            continue

        numero = int(match.group(1))
        container = a.parent
        raw = container.get_text(separator=" ", strip=True)

        fecha_match = re.search(r"(\d{2})\.(\d{2})\.(\d{2})", raw)
        fecha = None
        if fecha_match:
            d, mo, y2 = fecha_match.groups()
            fecha = f"20{y2}{mo}{d}"

        resultado[numero] = {
            "href": href,
            "fecha": fecha
        }

    return resultado


def construir_url_pdf(href, numero):
    if href.startswith("http"):
        return href
    if href.startswith(".."):
        href = href.lstrip(".")
    if href.startswith("/"):
        return f"https://quilmes.gov.ar{href}"

    return urljoin(PDF_BASE_URL, f"boletin-{numero}.pdf")


def download_pdf(url, numero):
    destino = PDF_DIR / f"boletin-{numero}.pdf"
    print(f"[INFO] Descargando {url}")
    response = requests.get(url, headers=HEADERS, timeout=60)
    response.raise_for_status()
    destino.write_bytes(response.content)
    return destino


def pdf_to_fragments(pdf_path: Path, fecha: str):
    print(f"[INFO] Procesando PDF {pdf_path.name}")
    doc = fitz.open(pdf_path)

    if fecha:
        new_name = f"{fecha} - {pdf_path.name}"
    else:
        new_name = pdf_path.name

    frags = []
    for i, page in enumerate(doc, start=1):
        text = page.get_text().strip()
        if not text:
            continue

        frags.append({
            "id": f"{new_name}_p{i}_f0",
            "archivo": new_name,
            "pagina": i,
            "fragmento": text
        })

    doc.close()
    return frags


def save_new_chunk(chunk_index: int, fragments: list):
    # MEJORA: f"{chunk_index:04d}" asegura que el archivo se guarde siempre con 4 dígitos (ej: 0024)
    salida = JSON_CHUNKS_DIR / f"boletines_part_{chunk_index:04d}.jsonl"

    print(f"[INFO] Guardando {salida.name}")
    with open(salida, "w", encoding="utf-8") as f:
        for frag in fragments:
            f.write(json.dumps(frag, ensure_ascii=False) + "\n")

    print(f"[OK] Chunk generado en subcarpeta: {salida}")


# =========================================================
# MAIN
# =========================================================

def main():
    last_idx, last_chunk = find_latest_chunk()

    if not last_chunk:
        print("[ERROR] No existen chunks previos en la carpeta json_chunks/bolet/.")
        return

    last_bolet = load_last_boletin_number(last_chunk)

    print(f"[INFO] Último chunk detectado: {last_idx:04d}")
    print(f"[INFO] Último boletín procesado: {last_bolet}")

    next_bolet = last_bolet + 1
    print(f"[INFO] Buscando boletín {next_bolet}")

    disponibles = scrape_boletines_list()

    if next_bolet not in disponibles:
        print(f"[INFO] El boletín {next_bolet} todavía no existe.")
        return

    info = disponibles[next_bolet]
    pdf_url = construir_url_pdf(info["href"], next_bolet)

    try:
        pdf = download_pdf(pdf_url, next_bolet)
        frags = pdf_to_fragments(pdf, info["fecha"])

        # Pasamos al generador el índice correlativo siguiente
        save_new_chunk(last_idx + 1, frags)
        print("[OK] Nuevo chunk incremental generado correctamente.")

    except Exception as e:
        print(f"[ERROR] Falló el procesamiento: {e}")


if __name__ == "__main__":
    main()
