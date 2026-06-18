import json
import glob
import re
import os
import shutil
from pathlib import Path

def construir_url_boletin(nombre_archivo):
    # Excepción para boletín 543
    if "543" in nombre_archivo:
        return "https://quilmes.gov.ar/pdf/boletines/boletin_543.pdf"
    
    match = re.search(r'boletin[-_](\d+)', nombre_archivo, re.IGNORECASE)
    if match:
        return f"https://quilmes.gov.ar/pdf/boletines/boletin-{match.group(1)}.pdf"
    return "https://quilmes.gov.ar/institucional/boletines.php"

def main():
    src_dir = Path('json_chunks/bolet_normalizado')
    dest_dir = Path('json_chunks/bolet')
    
    # Asegurar carpeta destino
    dest_dir.mkdir(parents=True, exist_ok=True)

    archivos = list(src_dir.glob('*.jsonl'))
    print(f"[INFO] Procesando {len(archivos)} archivos desde '{src_dir}' hacia '{dest_dir}'...")

    for ruta_archivo in archivos:
        nuevas_lineas = []
        with open(ruta_archivo, 'r', encoding='utf-8') as f:
            for linea in f:
                data = json.loads(linea)
                # Inyectar URL
                nombre_archivo = data.get('archivo', '')
                data['url'] = construir_url_boletin(nombre_archivo)
                nuevas_lineas.append(json.dumps(data, ensure_ascii=False))
        
        # Guardar en destino
        ruta_destino = dest_dir / ruta_archivo.name
        with open(ruta_destino, 'w', encoding='utf-8') as f:
            for ln in nuevas_lineas:
                f.write(ln + '\n')

    print(f"✅ Todos los archivos movidos e inyectados con URLs en '{dest_dir}'.")
    # Opcional: print("Podes borrar 'json_chunks/bolet_normalizado' ahora.")

if __name__ == '__main__':
    main()
