import json
import os
import glob

CHUNKS_FOLDER = "data/chunks"
NUEVOS_BOLETINES_PATH = "data/boletines_nuevos.jsonl"

def load_chunks():
    all_data = []
    chunk_files = sorted(glob.glob(f"{CHUNKS_FOLDER}/boletines_part_*.jsonl"))

    for file in chunk_files:
        with open(file, "r", encoding="utf-8") as f:
            for line in f:
                try:
                    item = json.loads(line.strip())
                    if isinstance(item, dict) and "nro" in item:
                        all_data.append(item)
                except json.JSONDecodeError:
                    continue  # Ignorar líneas inválidas

    if not all_data:
        print("No se encontraron datos válidos en los chunks.")
        return all_data

    all_data.sort(key=lambda x: x["nro"])  # Asegura orden por nro
    print(f"Último chunk #: {len(chunk_files) - 1}, último boletín procesado: {all_data[-1]['nro']}")
    return all_data

def load_nuevos_boletines():
    nuevos = []
    with open(NUEVOS_BOLETINES_PATH, "r", encoding="utf-8") as f:
        for line in f:
            try:
                item = json.loads(line.strip())
                if isinstance(item, dict) and "nro" in item:
                    nuevos.append(item)
            except json.JSONDecodeError:
                continue  # Ignorar líneas inválidas

    return nuevos

def save_chunks(data):
    chunk_size = 100
    os.makedirs(CHUNKS_FOLDER, exist_ok=True)

    for i in range(0, len(data), chunk_size):
        chunk = data[i:i+chunk_size]
        chunk_file = os.path.join(CHUNKS_FOLDER, f"boletines_part_{i//chunk_size + 1}.jsonl")
        with open(chunk_file, "w", encoding="utf-8") as f:
            for item in chunk:
                f.write(json.dumps(item, ensure_ascii=False) + "\n")

def main():
    actuales = load_chunks()
    nuevos = load_nuevos_boletines()

    if not nuevos:
        print("No se encontraron nuevos boletines válidos.")
        return

    nro_actuales = {item["nro"] for item in actuales}
    nuevos_unicos = [b for b in nuevos if b["nro"] not in nro_actuales]

    if not nuevos_unicos:
        print("No hay boletines nuevos para agregar.")
        return

    print(f"Agregando {len(nuevos_unicos)} boletines nuevos.")
    todos = actuales + nuevos_unicos
    todos.sort(key=lambda x: x["nro"])
    save_chunks(todos)
    print("Actualización completada.")

if __name__ == "__main__":
    main()
