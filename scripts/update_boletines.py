import os
import re
import json
from pathlib import Path
import requests
from urllib.parse import urljoin, urlparse
from bs4 import BeautifulSoup
import fitz  # PyMuPDF
from tqdm import tqdm

# Configuración de rutas
BASE_URL       = "https://quilmes.gov.ar"
BOLETINES_URL  = f"{BASE_URL}/boletines"
BOLETINES_DIR  = Path("boletines")
CHUNKS_DIR     = Path("json_chunks")
CHUNK_PATTERN  = re.compile(r"boletines_part_(\d+)\.jsonl")
PDF_PATTERN    = re.compile(r"boletin-(\d+)\.pdf")

def get_latest_chunk_number() -> int:
    """Devuelve el mayor índice N de 'boletines_part_N.jsonl' en json_chunks/."""
    CHUNKS_DIR.mkdir(exist_ok=True)
    nums = [int(m.group(1)) for f in CHUNKS_DIR.iterdir() 
            if (m := CHUNK_PATTERN.match(f.name))]
    return max(nums, default=-1)

def get_last_boletin_number() -> int:
    """Escanea todos los chunks y devuelve el mayor nro de boletín procesado."""
    last = 0
    for f in CHUNKS_DIR.glob("boletines_part_*.jsonl"):
        with open(f, encoding="utf-8") as fh:
            for line in fh:
                try:
                    obj = json.loads(line)
                    archivo = obj.get("archivo", "")
                    if (m := PDF_PATTERN.search(archivo)):
                        last = max(last, int(m.group(1)))
                except json.JSONDecodeError:
                    continue
    return last

def scrape_boletines():
    """Devuelve lista de {'nro': int, 'url': str} de los boletines en la web."""
    resp = requests.get(BOLETINES_URL, timeout=10,
                        headers={"User-Agent":"Mozilla/5.0"})
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")
    encontrados = []
    for a in soup.find_all("a", href=PDF_PATTERN):
        href = a["href"]
        nro = int(PDF_PATTERN.search(href).group(1))
        encontrados.append({"nro": nro, "url": href})
    return sorted(encontrados, key=lambda b: b["nro"])

def descarga_pdf(nro: int, url_rel: str) -> Path | None:
    """Descarga y guarda el PDF; retorna su Path o None."""
    pdf_url = urljoin(BASE_URL, url_rel.lstrip("/"))
    # validación mínima
    parsed = urlparse(pdf_url)
    if not parsed.scheme or not parsed.netloc:
        print(f"[ERROR] URL inválida: {pdf_url}")
        return None

    BOLETINES_DIR.mkdir(exist_ok=True)
    salida = BOLETINES_DIR / f"boletin-{nro}.pdf"
    try:
        r = requests.get(pdf_url, timeout=10,
                         headers={"User-Agent":"Mozilla/5.0"})
        r.raise_for_status()
        with open(salida, "wb") as f:
            f.write(r.content)
        return salida
    except Exception as e:
        print(f"[ERROR] al descargar {pdf_url}: {e}")
        return None

def process_pdf_to_fragments(pdf_path: Path) -> list[dict]:
    """Devuelve lista de fragments {id, archivo, pagina, fragmento}."""
    fragments = []
    with fitz.open(pdf_path) as doc:
        for i, page in enumerate(doc, start=1):
            text = page.get_text().strip()
            frag = {
                "id":   f"{pdf_path.stem}_p{i}_f0",
                "archivo": pdf_path.name,
                "pagina":  i,
                "fragmento": text
            }
            fragments.append(frag)
    return fragments

def save_fragments(chunk_num: int, frags: list[dict]):
    """Guarda los fragments en el archivo de chunk correspondiente."""
    out = CHUNKS_DIR / f"boletines_part_{chunk_num:03}.jsonl"
    with open(out, "w", encoding="utf-8") as f:
        for frag in frags:
            f.write(json.dumps(frag, ensure_ascii=False) + "\n")
    print(f"[OK] {len(frags)} fragmentos guardados en {out.name}")

def main():
    print("🔍 Detectando estado actual…")
    latest_chunk  = get_latest_chunk_number()
    last_boletin  = get_last_boletin_number()
    print(f"    Último chunk: {latest_chunk}")
    print(f"    Último boletín procesado: {last_boletin}")

    print("🌐 Scrapeando boletines en la web…")
    web_boletines = scrape_boletines()
    pendientes    = [b for b in web_boletines if b["nro"] > last_boletin]

    if not pendientes:
        print("✅ No hay boletines nuevos.")
        return

    siguiente = pendientes[0]
    print(f"⬇️  Nuevo boletín detectado: {siguiente['nro']} → descargando…")
    pdf_path = descarga_pdf(siguiente["nro"], siguiente["url"])
    if not pdf_path:
        return

    print("📄 Procesando PDF a fragmentos…")
    frags = process_pdf_to_fragments(pdf_path)

    print(f"💾 Guardando como chunk #{latest_chunk+1}…")
    save_fragments(latest_chunk+1, frags)

if __name__ == "__main__":
    main()
