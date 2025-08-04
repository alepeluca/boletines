#!/usr/bin/env python3
import os
import re
import json
from pathlib import Path
import requests
import fitz  # PyMuPDF

# ------------------------------------------------------------
# RUTAS Y CONSTANTES
# ------------------------------------------------------------
# Base del repo: dos niveles arriba de este script
REPO_ROOT = Path(__file__).resolve().parent.parent

PDF_DIR         = REPO_ROOT / "pdfs"
JSON_CHUNKS_DIR = REPO_ROOT / "json_chunks"

LISTADO_URL     = "https://quilmes.gov.ar/institucional/gobierno_abierto_boletines.php"
BASE_URL        = "https://quilmes.gov.ar"
PDF_PATH_TMPL   = "../pdf/boletines/boletin-{}.pdf"  # como aparece en href

# Tamaño de cada fragmento de texto
FRAGMENT_SIZE = 1000

# ------------------------------------------------------------
# Asegura que existan directorios
# ------------------------------------------------------------
PDF_DIR.mkdir(parents=True, exist_ok=True)
JSON_CHUNKS_DIR.mkdir(parents=True, exist_ok=True)

# ------------------------------------------------------------
# 1) Detectar el último JSONL procesado y extraer su mayor boletín
# ------------------------------------------------------------
def detecta_ultimo_procesado():
    archivos = sorted(JSON_CHUNKS_DIR.glob("boletines_part_*.jsonl"))
    print("Archivos JSONL en disco:", [f.name for f in archivos])

    if not archivos:
        return 0, 0

    # Tomamos el que tenga el número más alto en su nombre
    ultimo_arch = archivos[-1]
    nro_chunk = int(re.search(r"boletines_part_(\d+)\.jsonl", ultimo_arch.name).group(1))

    # Leemos su última línea para extraer el último boletín procesado
    with open(ultimo_arch, "rb") as f:
        try:
            f.seek(-2, os.SEEK_END)
            while f.read(1) != b"\n":
                f.seek(-2, os.SEEK_CUR)
        except OSError:
            f.seek(0)
        ultima_linea = f.readline().decode("utf-8")

    data = json.loads(ultima_linea)
    # Su id viene como "boletin-525_1234"
    match = re.match(r"boletin-(\d+)_", data["id"])
    ultimo_boletin = int(match.group(1)) if match else 0

    print(f"Último chunk #: {nro_chunk}, último boletín procesado: {ultimo_boletin}")
    return nro_chunk, ultimo_boletin

# ------------------------------------------------------------
# 2) Leer la web y determinar el boletín mayor disponible
# ------------------------------------------------------------
def obtiene_lista_boletines_web():
    print("Obteniendo listado de boletines desde la web...")
    r = requests.get(LISTADO_URL)
    r.raise_for_status()
    html = r.text

    # Extraemos href="../pdf/boletines/boletin-XXX.pdf"
    matches = re.findall(r'href="(\.\./pdf/boletines/boletin-(\d+)\.pdf)"', html)
    boletines = [(int(n), url) for url, n in matches]
    boletines = sorted(set(boletines), key=lambda x: x[0])
    print(f"Total boletines encontrados en web: {len(boletines)} (del {boletines[0][0]} al {boletines[-1][0]})")
    return boletines

# ------------------------------------------------------------
# 3) Por cada boletín nuevo, descargar PDF y extraer fragmentos
# ------------------------------------------------------------
def descarga_pdf(nro, url_rel):
    pdf_url = BASE_URL + url_rel
    destino = PDF_DIR / f"boletin-{nro}.pdf"
    if destino.exists():
        print(f"  • boletin-{nro}.pdf ya existe, salteando descarga.")
        return destino
    print(f"  • Descargando boletin-{nro}.pdf …")
    r = requests.get(pdf_url)
    r.raise_for_status()
    destino.write_bytes(r.content)
    return destino

def pdf_a_fragmentos(pdf_path):
    doc = fitz.open(str(pdf_path))
    fragments = []
    for p in range(doc.page_count):
        text = doc.load_page(p).get_text("text")
        for i in range(0, len(text), FRAGMENT_SIZE):
            frag = text[i : i + FRAGMENT_SIZE].strip()
            if frag:
                fragments.append({"pagina": p + 1, "fragmento": frag})
    return fragments

# ------------------------------------------------------------
# 4) Generar el JSONL chunk con los nuevos boletines
# ------------------------------------------------------------
def generar_chunk(nro_chunk, boletines_data):
    nombre = f"boletines_part_{nro_chunk}.jsonl"
    dest = JSON_CHUNKS_DIR / nombre
    print(f"Generando {nombre} con {len(boletines_data)} boletines…")
    idx = 0
    with open(dest, "w", encoding="utf-8") as f:
        for b in boletines_data:
            for frag in b["fragmentos"]:
                obj = {
                    "id":      f"{b['archivo']}_{idx}",
                    "archivo": b["archivo"],
                    "pagina":  frag["pagina"],
                    "fragmento": frag["fragmento"]
                }
                f.write(json.dumps(obj, ensure_ascii=False) + "\n")
                idx += 1

# ------------------------------------------------------------
# MAIN
# ------------------------------------------------------------
def main():
    chunk_num, ultimo_proc = detecta_ultimo_procesado()
    lista_web = obtiene_lista_boletines_web()

    # Filtramos solo los boletines > último_proc
    nuevos = [(n, url) for (n, url) in lista_web if n > ultimo_proc]
    if not nuevos:
        print("No hay boletines nuevos para procesar. 💤")
        return

    boletines_data = []
    for nro, url_rel in nuevos:
        pdf_path = descarga_pdf(nro, url_rel)
        frags = pdf_a_fragmentos(pdf_path)
        boletines_data.append({
            "archivo": f"boletin-{nro}.txt",
            "fragmentos": frags
        })

    generar_chunk(chunk_num + 1, boletines_data)
    print("¡Listo! ✅")

if __name__ == "__main__":
    main()
