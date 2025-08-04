import json
import os
import re
from pathlib import Path
import requests
from urllib.parse import urljoin, urlparse
from bs4 import BeautifulSoup  # Para web scraping
import fitz  # PyMuPDF para procesar PDFs
from tqdm import tqdm  # Para barras de progreso

# Configuración de directorios y constantes
CHUNKS_DIR = Path("json_chunks")  # Carpeta donde se guardan los chunks
CHUNK_SIZE = 1000  # Tamaño de cada chunk (número de boletines por archivo)
NEW_FILE_PATH = Path("nuevo_boletin.json")  # Ruta del nuevo boletín a agregar
BASE_URL = "https://quilmes.gov.ar"  # URL base del sitio web
BOLETINES_URL = f"{BASE_URL}/boletines"  # URL de la página con los boletines (ajustar si es necesario)

def is_valid_url(url):
    """Valida si una URL es correcta."""
    try:
        result = urlparse(url)
        return all([result.scheme, result.netloc])
    except ValueError:
        return False

def descarga_pdf(nro, url_rel):
    """Descarga un archivo PDF desde una URL relativa y lo guarda localmente."""
    # Construir la URL completa
    pdf_url = urljoin(BASE_URL, url_rel.strip("/"))  # Evita barras dobles
    if not is_valid_url(pdf_url):
        print(f"Error: URL inválida: {pdf_url}")
        return None

    print(f"Descargando boletin-{nro}.pdf desde {pdf_url}...")
    try:
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
        r = requests.get(pdf_url, timeout=10, headers=headers)
        r.raise_for_status()
        pdf_dir = Path("boletines")
        pdf_dir.mkdir(exist_ok=True)
        pdf_path = pdf_dir / f"boletin-{nro}.pdf"
        with open(pdf_path, "wb") as f:
            f.write(r.content)
        return str(pdf_path)
    except requests.exceptions.RequestException as e:
        print(f"Error al descargar {pdf_url}: {e}")
        return None

def scrape_boletines():
    """Obtiene la lista de boletines desde la página web."""
    print("Obteniendo listado de boletines desde la web...")
    try:
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
        response = requests.get(BOLETINES_URL, headers=headers, timeout=10)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")
        
        # Suposición: los boletines están en enlaces <a> con URLs que contienen "boletin-N.pdf"
        boletines = []
        for link in soup.find_all("a", href=re.compile(r"boletin-\d+\.pdf")):
            href = link.get("href")
            nro_match = re.search(r"boletin-(\d+)\.pdf", href)
            if nro_match:
                nro = int(nro_match.group(1))
                boletines.append({"nro": nro, "url": href})
        
        if not boletines:
            print("Advertencia: No se encontraron boletines en la página.")
            return []
        
        print(f"Total boletines encontrados en web: {len(boletines)} (del {min(b.nro for b in boletines)} al {max(b.nro for b in boletines)})")
        return sorted(boletines, key=lambda x: x["nro"])
    except requests.exceptions.RequestException as e:
        print(f"Error al scrapear boletines: {e}")
        return []

def load_chunks():
    """Carga y une todos los chunks existentes en orden (soporta JSONL)."""
    all_data = []
    chunk_files = sorted(
        CHUNKS_DIR.glob("boletines_part_*.jsonl"),
        key=lambda x: int(re.search(r"boletines_part_(\d+).jsonl", x.name).group(1))
    )
    for file in chunk_files:
        with open(file, "r", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    all_data.append(json.loads(line.strip()))
    print(f"Archivos JSONL en disco: {[f.name for f in chunk_files]}")
    print(f"Último chunk #: {len(chunk_files) - 1}, último boletín procesado: {all_data[-1]['nro'] if all_data else 0}")
    return all_data

def load_new_boletin():
    """Carga el nuevo boletín desde un archivo JSON."""
    try:
        with open(NEW_FILE_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        print(f"Error: No se encontró el archivo {NEW_FILE_PATH}")
        return None
    except json.JSONDecodeError as e:
        print(f"Error: Formato JSON inválido en {NEW_FILE_PATH}: {e}")
        return None

def save_chunks(data):
    """Divide y guarda los datos en archivos JSONL."""
    CHUNKS_DIR.mkdir(exist_ok=True)
    for old_file in CHUNKS_DIR.glob("boletines_part_*.jsonl"):
        old_file.unlink()
    
    for i in range(0, len(data), CHUNK_SIZE):
        chunk_data = data[i:i + CHUNK_SIZE]
        chunk_path = CHUNKS_DIR / f"boletines_part_{i // CHUNK_SIZE}.jsonl"
        with open(chunk_path, "w", encoding="utf-8") as f:
            for item in chunk_data:
                f.write(json.dumps(item, ensure_ascii=False) + "\n")

def process_pdf(pdf_path):
    """Procesa el PDF para extraer metadatos o contenido (ejemplo con PyMuPDF)."""
    try:
        with fitz.open(pdf_path) as doc:
            metadata = doc.metadata
            text = ""
            for page in doc:
                text += page.get_text()
        return {"metadata": metadata, "text_length": len(text)}
    except Exception as e:
        print(f"Error al procesar PDF {pdf_path}: {e}")
        return None

def main():
    """Función principal para procesar y actualizar los boletines."""
    print("Cargando chunks existentes...")
    all_boletines = load_chunks()
    
    print("Cargando nuevo boletín...")
    new_boletin = load_new_boletin()
    if new_boletin is None:
        print("Error: No se pudo cargar el nuevo boletín. Continuando con web scraping...")
    
    # Scrapear boletines desde la web
    web_boletines = scrape_boletines()
    
    # Filtrar boletines nuevos (no presentes en los chunks existentes)
    existing_nros = {b["nro"] for b in all_boletines}
    new_web_boletines = [b for b in web_boletines if b["nro"] not in existing_nros]
    
    # Descargar y procesar PDFs
    for boletin in tqdm(new_web_boletines, desc="Procesando boletines"):
        pdf_path = descarga_pdf(boletin["nro"], boletin["url"])
        if pdf_path:
            boletin["pdf_path"] = pdf_path
            pdf_info = process_pdf(pdf_path)
            if pdf_info:
                boletin.update(pdf_info)
            all_boletines.append(boletin)
    
    # Agregar el nuevo boletín del archivo JSON, si existe
    if new_boletin:
        nro = new_boletin.get("nro", "unknown")
        url_rel = new_boletin.get("url", "")
        if url_rel:
            pdf_path = descarga_pdf(nro, url_rel)
            if pdf_path:
                new_boletin["pdf_path"] = pdf_path
                pdf_info = process_pdf(pdf_path)
                if pdf_info:
                    new_boletin.update(pdf_info)
        all_boletines.append(new_boletin)
    
    print("Repartiendo boletines en chunks...")
    save_chunks(all_boletines)
    
    print("Proceso completado. Total de boletines ahora:", len(all_boletines))

if __name__ == "__main__":
    CHUNKS_DIR.mkdir(exist_ok=True)
    main()
