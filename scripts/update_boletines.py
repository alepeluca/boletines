import json
import os
from pathlib import Path

# Configuración de paths
chunks_dir = Path("json_chunks")
boletin_nuevo_path = Path("nuevo_boletin.json")

# Validaciones
if not boletin_nuevo_path.exists():
    raise FileNotFoundError("No se encontró el archivo 'nuevo_boletin.json'.")

# Leer el boletín nuevo
with open(boletin_nuevo_path, "r", encoding="utf-8") as f:
    boletin_nuevo = json.load(f)

# Verificar estructura esperada
if not isinstance(boletin_nuevo, list):
    raise ValueError("El archivo 'nuevo_boletin.json' debe contener una lista de entradas.")

# Obtener el número del chunk más alto existente
chunk_files = sorted(chunks_dir.glob("chunk_*.json"))
ultimo_numero = -1
for file in chunk_files:
    try:
        numero = int(file.stem.split("_")[1])
        if numero > ultimo_numero:
            ultimo_numero = numero
    except (IndexError, ValueError):
        continue

nuevo_numero = ultimo_numero + 1
nuevo_nombre = f"chunk_{nuevo_numero:03}.json"
nuevo_path = chunks_dir / nuevo_nombre

# Guardar el nuevo chunk
with open(nuevo_path, "w", encoding="utf-8") as f:
    json.dump(boletin_nuevo, f, ensure_ascii=False, indent=2)

print(f"✅ Nuevo chunk creado: {nuevo_nombre} con {len(boletin_nuevo)} registros.")
