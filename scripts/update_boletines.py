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
REPO_ROOT        = Path(__file__).resolve().parent.parent
PDF_DIR          = REPO_ROOT / "pdfs"
JSON_CHUNKS_DIR  = REPO_ROOT / "json_chunks"

LISTADO_URL    = "https://quilmes.gov.ar/institucional/gobierno_abierto_boletines.php"
BASE_URL       = "https://quilmes.gov.ar"
PDF_PATH_REGEX = r'href="(\.\./pdf/boletines/boletin-(\d+)\.pdf)"'

FRAGMENT_SIZE = 1000  # caracteres por fragmento

# ------------------------------------------------------------
# Asegura que existan los directorios
# ------------------------------------------------------------
PDF_DIR.mkdir(parents=True, exist_ok=True)
JSON_CHUNKS_DIR.mkdir(parents=True, exist_ok=True)

# ------------------------------------------------------------
# 1) Detecta el último chunk procesado y su último boletín
# ------------------------------------------------------------
def detecta_ultimo_procesado():
    archivos = list(JSON_CHUNKS_DIR.glob("boletines_part_*.jsonl"))
    # Ordenar por número de chunk (no lex)
    archivos.sort(key=lambda f: int(re.search(r"boletines_part_(\d+)\.jsonl", f.name).group(1)))
    print("DEBUG: JSONL encontrados:", [f.name for f in archivos])

    if not archivos:
        return 0, 0

    ultimo_arch = archivos[-1]
    nro_chunk = int(re.search(r"boletines_part_(\d+)\.jsonl", ultimo_arch.name).group(1))

    # Leer la última línea para extraer último boletín procesado
    with open(ultimo_arch, "rb") as f:
        try:
            f.seek(-2, os.SEEK_END)
            while f.read(1) != b"\n":
                f.seek(-2, os.SEEK_CUR)
        except OSError:
            f.seek(0)
        ultima_linea = f.readline().decode("utf-8")

    data = json.loads(ultima_linea)
    m = re.match(r"boletin-(\d+)_", data["id"])
    ultimo_boletin = int(m.group(1)) if m else 0

    print(f"DEBUG: último chunk={nro_chunk}, último boletín procesado={ultimo_boletin}")
    return nro_chunk, ultimo_boletin

# ------------------------------------------------------------
# 2) Listar boletines disponibles en la web
# ------------------------------------------------------------
def obtiene_lista_boletines_web():
    print("Obteniendo listado de boletines desde la web...")
    r = requests.get(LISTADO_URL)
    r.raise_for_status()
    html = r.text

    matches = re.findall(PDF_PATH_REGEX, html)
    boletines = sorted({ (int(n), url) for url, n in matches }, key=lambda x: x[0])
    print(f"Total en web: {len(boletines)} boletines (del {boletines[0][0]} al {boletines[-1][0]})")
    return boletines

# ------------------------------------------------------------
# 3) Descargar y fragmentar cada PDF nuevo
# ------------------------------------------------------------
def descarga_pdf(nro, url_rel):
    # Normaliza la ruta: elimina "../" para obtener "/pdf/boletines/..."
    rel = url_rel.replace("../", "/")
    pdf_url = BASE_URL.rstrip("/") + rel
    destino = PDF_DIR / f"boletin-{nro}.pdf"

    if destino.exists():
        print(f"  • boletin-{nro}.pdf ya existe, salteando.")
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
# 4) Generar el nuevo JSONL chunk
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
                    "id":        f"{b['archivo']}_{idx}",
                    "archivo":   b["archivo"],
                    "pagina":    frag["pagina"],
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

    # Solo boletines con nro > último procesado
    nuevos = [(n, url) for (n, url) in lista_web if n > ultimo_proc]
    if not nuevos:
        print("No hay boletines nuevos. 💤")
        return

    boletines_data = []
    for nro, url_rel in nuevos:
        pdf_path = descarga_pdf(nro, url_rel)
        frags = pdf_a_fragmentos(pdf_path)
        boletines_data.append({
            "archivo":   f"boletin-{nro}.txt",
            "fragmentos": frags
        })

    generar_chunk(chunk_num + 1, boletines_data)
    print("¡Proceso completado! ✅")

if __name__ == "__main__":
    main()
