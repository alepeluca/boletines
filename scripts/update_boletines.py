# scripts/update_boletines.py
import json
import os
import re
from pathlib import Path

VERSION = "1.0.5"
RAW_DIR = Path("raw")
OUTPUT_DIR = Path("data")
CHUNK_PREFIX = "boletines_part_"
CHUNK_EXTENSION = ".jsonl"

print(f"Versión del script: {VERSION}")

def find_last_chunk_file():
    chunk_files = [f for f in os.listdir(OUTPUT_DIR) if f.startswith(CHUNK_PREFIX) and f.endswith(CHUNK_EXTENSION)]
    chunk_numbers = [int(re.search(rf"{CHUNK_PREFIX}(\d+){CHUNK_EXTENSION}", f).group(1)) for f in chunk_files]
    if not chunk_numbers:
        raise ValueError("No chunk files found.")
    max_chunk_number = max(chunk_numbers)
    return OUTPUT_DIR / f"{CHUNK_PREFIX}{max_chunk_number}{CHUNK_EXTENSION}"

def extract_last_boletin_number(jsonl_path):
    last_line = None
    with open(jsonl_path, "r", encoding="utf-8") as f:
        for line in f:
            last_line = line.strip()
    if not last_line:
        raise ValueError("Last line in JSONL is empty.")
    
    last_data = json.loads(last_line)
    match = re.search(r"boletin-(\d+)", last_data["id"])
    if not match:
        raise ValueError(f"No boletin number found in id: {last_data['id']}")
    return int(match.group(1))

def main():
    print(f"Running update_boletines.py version {VERSION}")

    last_chunk = find_last_chunk_file()
    print(f"Last chunk file: {last_chunk.name}")
    
    last_boletin_number = extract_last_boletin_number(last_chunk)
    next_boletin_number = last_boletin_number + 1
    print(f"Último boletín encontrado: {last_boletin_number}")
    print(f"Iniciando búsqueda desde el boletín: {next_boletin_number}")

    # Acá iría la lógica para buscar y procesar nuevos boletines
    # (descarga, parsing, chunking, etc.)
    # Por ahora solo mostramos los datos extraídos
    print("Listo para buscar nuevos boletines...")

if __name__ == "__main__":
    main()
