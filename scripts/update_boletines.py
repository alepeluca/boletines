import os
import re
import json
import requests
import fitz  # PyMuPDF
from urllib.parse import urljoin
from tqdm import tqdm

# Config
BASE_URL = "https://quilmes.gov.ar"
LISTADO_URL = f"{BASE_URL}/institucional/gobierno_abierto_boletines.php"
PDF_DIR = "pdfs"
CHUNKS_DIR = "json_chunks"
STATE_FILE = "ultima_actualizacion.json"

# Crear carpetas si no existen
os.makedirs(PDF_DIR, exist_ok=True)
os.makedirs(CHUNKS_DIR, exist_ok=True)

def obtener_lista_boletines():
    """Scrapea la lista de boletines disponibles en el sitio."""
    r = requests.get(LISTADO_URL, timeout=10)
    r.raise_for_status()
    matches = re.findall(r'href="(\.\./pdf/boletines/boletin-(\d+)\.pdf)"', r.text)
    urls = list(set(matches))
    return sorted([(int(n), url) for url, n in urls], key=lambda x: x[0])

def pdf_a_fragmentos(pdf_path, fragment_size=1000):
    """Divide el PDF en fragmentos de texto."""
    doc = fitz.open(pdf_path)
    fragments = []
    for page_num in range(doc.page_count):
        text = doc.load_page(page_num).get_text("text")
        for i in range(0, len(text), fragment_size):
            frag = text[i:i+fragment_size].strip()
            if frag:
                fragments.append({
                    "pagina": page_num + 1,
                    "fragmento": frag
                })
    return fragments

def generar_jsonl_chunk(nombre_chunk, boletines):
    """Guarda los fragmentos en un archivo .jsonl."""
    idx = 0
    path = os.path.join(CHUNKS_DIR, nombre_chunk)
    with open(path, "w", encoding="utf-8") as f:
        for b in boletines:
            for frag in b["fragmentos"]:
                f.write(json.dumps({
                    "id": f"{b['archivo']}_{idx}",
                    "archivo": b["archivo"],
                    "fragmento": frag["fragmento"],
                    "pagina": frag["pagina"]
                }, ensure_ascii=False) + "\n")
                idx += 1

def cargar_estado():
    """Lee el último número de boletín procesado."""
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"ultimo_numero": 0}

def guardar_estado(nro):
    """Guarda el último número de boletín procesado."""
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump({"ultimo_numero": nro}, f, ensure_ascii=False)

def detectar_proximo_chunk():
    """Detecta el número del siguiente chunk disponible."""
    archivos = os.listdir(CHUNKS_DIR)
    chunks = [int(re.search(r'boletines_part_(\d+)\.jsonl', f).group(1))
              for f in archivos if re.search(r'boletines_part_(\d+)\.jsonl', f)]
    return max(chunks, default=0) + 1

def main():
    print("🔍 Buscando boletines nuevos...")
    boletines = obtener_lista_boletines()
    estado = cargar_estado()
    nuevos = [(nro, url) for nro, url in boletines if nro > estado["ultimo_numero"]]

    if not nuevos:
        print("✅ No hay boletines nuevos.")
        return

    procesados = []
    for nro, url_rel in nuevos:
        url = urljoin(BASE_URL, url_rel)
        nombre_pdf = f"boletin-{nro}.pdf"
        path_pdf = os.path.join(PDF_DIR, nombre_pdf)

        if not os.path.exists(path_pdf):
            print(f"⬇️  Descargando {nombre_pdf}...")
            try:
                r = requests.get(url, timeout=10)
                r.raise_for_status()
                with open(path_pdf, "wb") as f:
                    f.write(r.content)
            except Exception as e:
                print(f"[ERROR] No se pudo descargar {nombre_pdf}: {e}")
                continue
        else:
            print(f"📁 {nombre_pdf} ya descargado.")

        print(f"🧩 Procesando {nombre_pdf}...")
        fragmentos = pdf_a_fragmentos(path_pdf)
        procesados.append({
            "archivo": nombre_pdf.replace(".pdf", ".txt"),
            "fragmentos": fragmentos
        })

    if procesados:
        chunk_num = detectar_proximo_chunk()
        chunk_name = f"boletines_part_{chunk_num:03}.jsonl"
        print(f"💾 Guardando fragmentos en {chunk_name}...")
        generar_jsonl_chunk(chunk_name, procesados)

        ultimo_nro = max(nro for nro, _ in nuevos)
        guardar_estado(ultimo_nro)
        print(f"✅ Chunk generado y estado actualizado ({ultimo_nro}).")
    else:
        print("⚠️  No se procesó ningún boletín.")

if __name__ == "__main__":
    main()
