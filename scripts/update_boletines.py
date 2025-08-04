import os
import re
import json
from pathlib import Path
import requests
from bs4 import BeautifulSoup
from PyPDF2 import PdfReader

# Directorios y URLs
BASE_URL = "https://quilmes.gov.ar/gobierno/boletin_oficial.php"
PDF_BASE_URL = "https://quilmes.gov.ar/archivos/boletin-oficial/pdf/boletin-{}.pdf"
PDF_DIR = "boletines"
JSON_CHUNKS_DIR = "json_chunks"

os.makedirs(PDF_DIR, exist_ok=True)
os.makedirs(JSON_CHUNKS_DIR, exist_ok=True)

def obtener_ultimo_boletin_web():
    print("Obteniendo listado de boletines...")
    response = requests.get(BASE_URL)
    soup = BeautifulSoup(response.content, "html.parser")

    links = soup.find_all("a", href=re.compile(r"boletin-\d+\.pdf"))
    numeros = [int(re.search(r"boletin-(\d+)\.pdf", a['href']).group(1)) for a in links]
    ultimo = max(numeros)
    print(f"Último boletín en la web: {ultimo}")
    return ultimo

def obtener_ultimo_boletin_procesado():
    # Buscar último archivo jsonl
    archivos = list(Path(JSON_CHUNKS_DIR).glob("boletines_part_*.jsonl"))
    if not archivos:
        print("No hay archivos jsonl previos. Comenzando desde cero.")
        return 0, 0  # último archivo número, último boletín procesado

    # Obtener el número máximo de archivo jsonl
    nums = [int(re.search(r"boletines_part_(\d+)\.jsonl", a.name).group(1)) for a in archivos]
    ultimo_arch_num = max(nums)
    ultimo_arch = JSON_CHUNKS_DIR + f"/boletines_part_{ultimo_arch_num}.jsonl"

    print(f"Último archivo jsonl encontrado: {ultimo_arch}")

    # Leer última línea del archivo para obtener último boletín procesado
    with open(ultimo_arch, "rb") as f:
        try:
            f.seek(-2, os.SEEK_END)  # Ir casi al final
            while f.read(1) != b"\n":
                f.seek(-2, os.SEEK_CUR)
        except OSError:
            f.seek(0)
        ultima_linea = f.readline().decode()
    ultimo_boletin = json.loads(ultima_linea).get("id", "")
    # El id es como "boletin-526_12345"
    nro_match = re.search(r"boletin-(\d+)_", ultimo_boletin)
    if nro_match:
        ultimo_numero_boletin = int(nro_match.group(1))
    else:
        ultimo_numero_boletin = 0

    print(f"Último boletín procesado: {ultimo_numero_boletin}")
    return ultimo_arch_num, ultimo_numero_boletin

def descargar_boletin(numero):
    pdf_path = os.path.join(PDF_DIR, f"boletin-{numero}.pdf")
    if os.path.exists(pdf_path):
        print(f"boletin-{numero}.pdf ya existe. No se descarga.")
        return pdf_path
    url = PDF_BASE_URL.format(numero)
    print(f"Descargando boletin-{numero}.pdf...")
    r = requests.get(url)
    if r.status_code == 200:
        with open(pdf_path, "wb") as f:
            f.write(r.content)
        return pdf_path
    else:
        print(f"No se pudo descargar el boletín {numero}")
        return None

def pdf_a_fragmentos(pdf_path, fragment_size=500):
    reader = PdfReader(pdf_path)
    fragments = []
    for i, page in enumerate(reader.pages):
        text = page.extract_text() or ""
        for j in range(0, len(text), fragment_size):
            fragment = text[j:j+fragment_size].strip()
            if fragment:
                fragments.append({"pagina": i+1, "fragmento": fragment})
    return fragments

def generar_jsonl_chunk(nombre_chunk, boletines):
    print(f"Generando {nombre_chunk} con {len(boletines)} boletines...")
    idx = 0
    with open(os.path.join(JSON_CHUNKS_DIR, nombre_chunk), "w", encoding="utf-8") as f:
        for b in boletines:
            archivo = b["archivo"]
            for frag in b["fragmentos"]:
                obj = {
                    "id": f"{archivo}_{idx}",
                    "archivo": archivo,
                    "fragmento": frag["fragmento"],
                    "pagina": frag["pagina"]
                }
                f.write(json.dumps(obj, ensure_ascii=False) + "\n")
                idx += 1

def main():
    ultimo_arch_num, ultimo_boletin_procesado = obtener_ultimo_boletin_procesado()
    ultimo_boletin_web = obtener_ultimo_boletin_web()

    if ultimo_boletin_web <= ultimo_boletin_procesado:
        print("No hay boletines nuevos para procesar.")
        return

    nuevos_boletines = []
    for nro in range(ultimo_boletin_procesado + 1, ultimo_boletin_web + 1):
        pdf_path = descargar_boletin(nro)
        if not pdf_path:
            continue
        fragmentos = pdf_a_fragmentos(pdf_path)
        nuevos_boletines.append({
            "archivo": f"boletin-{nro}.txt",
            "fragmentos": fragmentos
        })

    if not nuevos_boletines:
        print("No se procesaron boletines nuevos.")
        return

    siguiente_num = ultimo_arch_num + 1
    nombre_chunk = f"boletines_part_{siguiente_num}.jsonl"
    generar_jsonl_chunk(nombre_chunk, nuevos_boletines)
    print(f"Archivo generado: {nombre_chunk}")

if __name__ == "__main__":
    main()
