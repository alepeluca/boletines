import json
import os
import re
from pathlib import Path
import requests
from urllib.parse import urljoin, urlparse

# Configuración de directorios y constantes
CHUNKS_DIR = Path("json_chunks")  # Carpeta donde se guardan los chunks
CHUNK_SIZE = 1000  # Tamaño de cada chunk (número de boletines por archivo)
NEW_FILE_PATH = Path("nuevo_boletin.json")  # Ruta del nuevo boletín a agregar
BASE_URL = "https://quilmes.gov.ar"  # URL base del sitio web (ajustar si es necesario)

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

    print(f"Descargando {pdf_url}...")
    try:
        # Realizar la solicitud HTTP con un tiempo de espera
        r = requests.get(pdf_url, timeout=10)
        r.raise_for_status()  # Lanza una excepción si el código HTTP indica error
        # Guardar el PDF en la carpeta 'boletines'
        pdf_dir = Path("boletines")
        pdf_dir.mkdir(exist_ok=True)  # Crear la carpeta si no existe
        pdf_path = pdf_dir / f"boletin-{nro}.pdf"
        with open(pdf_path, "wb") as f:
            f.write(r.content)
        return str(pdf_path)
    except requests.exceptions.RequestException as e:
        print(f"Error al descargar {pdf_url}: {e}")
        return None

def load_chunks():
    """Carga y une todos los chunks existentes en orden (soporta JSONL)."""
    all_data = []
    # Buscar archivos JSONL en el directorio
    chunk_files = sorted(
        CHUNKS_DIR.glob("boletines_part_*.jsonl"),
        key=lambda x: int(re.search(r"boletines_part_(\d+).jsonl", x.name).group(1))
    )
    if not chunk_files:  # Si no hay JSONL, intentar con JSON
        chunk_files = sorted(
            CHUNKS_DIR.glob("chunk_*.json"),
            key=lambda x: int(re.search(r"chunk_(\d+).json", x.name).group(1))
        )
        for file in chunk_files:
            with open(file, "r", encoding="utf-8") as f:
                chunk = json.load(f)
                all_data.extend(chunk)
    else:
        # Cargar archivos JSONL
        for file in chunk_files:
            with open(file, "r", encoding="utf-8") as f:
                for line in f:
                    if line.strip():  # Ignorar líneas vacías
                        all_data.append(json.loads(line.strip()))
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
    """Divide y guarda los datos en archivos JSONL (boletines_part_N.jsonl)."""
    # Crear el directorio si no existe
    CHUNKS_DIR.mkdir(exist_ok=True)
    
    # Eliminar archivos antiguos
    for old_file in CHUNKS_DIR.glob("boletines_part_*.jsonl"):
        old_file.unlink()
    for old_file in CHUNKS_DIR.glob("chunk_*.json"):
        old_file.unlink()

    # Guardar nuevos chunks en formato JSONL
    for i in range(0, len(data), CHUNK_SIZE):
        chunk_data = data[i:i + CHUNK_SIZE]
        chunk_path = CHUNKS_DIR / f"boletines_part_{i // CHUNK_SIZE}.jsonl"
        with open(chunk_path, "w", encoding="utf-8") as f:
            for item in chunk_data:
                f.write(json.dumps(item, ensure_ascii=False) + "\n")

def main():
    """Función principal para procesar y actualizar los boletines."""
    print("Cargando chunks existentes...")
    all_boletines = load_chunks()
    print(f"Total de boletines existentes: {len(all_boletines)}")

    print("Cargando nuevo boletín...")
    new_boletin = load_new_boletin()
    if new_boletin is None:
        print("Error: No se pudo cargar el nuevo boletín. Proceso terminado.")
        return

    print("Agregando nuevo boletín...")
    # Descargar el PDF asociado al nuevo boletín
    nro = new_boletin.get("nro", "unknown")
    url_rel = new_boletin.get("url", "")
    if url_rel:
        pdf_path = descarga_pdf(nro, url_rel)
        if pdf_path:
            new_boletin["pdf_path"] = pdf_path  # Agregar la ruta del PDF al boletín
        else:
            print(f"Advertencia: No se pudo descargar el PDF para el boletín {nro}")
    all_boletines.append(new_boletin)

    print("Repartiendo boletines en chunks...")
    save_chunks(all_boletines)

    print("Proceso completado. Total de boletines ahora:", len(all_boletines))

if __name__ == "__main__":
    # Crear directorio para chunks si no existe
    CHUNKS_DIR.mkdir(exist_ok=True)
    main()
