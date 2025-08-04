import json
import os
import re
from pathlib import Path

# Carpeta donde están los chunks
CHUNKS_DIR = Path("json_chunks")
CHUNK_SIZE = 1000

# Ruta del archivo nuevo (editá según donde tengas el nuevo boletín)
NEW_FILE_PATH = Path("nuevo_boletin.json")

def load_chunks():
    """Carga y une todos los chunks existentes en orden."""
    all_data = []
    chunk_files = sorted(
        CHUNKS_DIR.glob("chunk_*.json"),
        key=lambda x: int(re.search(r"chunk_(\d+).json", x.name).group(1))
    )
    for file in chunk_files:
        with open(file, "r", encoding="utf-8") as f:
            chunk = json.load(f)
            all_data.extend(chunk)
    return all_data

def load_new_boletin():
    """Carga el nuevo boletín desde un archivo JSON."""
    with open(NEW_FILE_PATH, "r", encoding="utf-8") as f:
        return json.load(f)

def save_chunks(data):
    """Divide y guarda los datos en archivos chunk_N.json."""
    # Eliminar archivos antiguos
    for old_file in CHUNKS_DIR.glob("chunk_*.json"):
        old_file.unlink()

    # Guardar nuevos chunks
    for i in range(0, len(data), CHUNK_SIZE):
        chunk_data = data[i:i + CHUNK_SIZE]
        chunk_path = CHUNKS_DIR / f"chunk_{i // CHUNK_SIZE}.json"
        with open(chunk_path, "w", encoding="utf-8") as f:
            json.dump(chunk_data, f, indent=2, ensure_ascii=False)

def main():
    print("Cargando chunks existentes...")
    all_boletines = load_chunks()
    print(f"Total de boletines existentes: {len(all_boletines)}")

    print("Cargando nuevo boletín...")
    new_boletin = load_new_boletin()

    print("Agregando nuevo boletín...")
    all_boletines.append(new_boletin)

    print("Repartiendo boletines en chunks...")
    save_chunks(all_boletines)

    print("Proceso completado. Total de boletines ahora:", len(all_boletines))

if __name__ == "__main__":
    main()
