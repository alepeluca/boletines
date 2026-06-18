import json
import glob
from urllib.parse import quote

def main():
    # El ID de tu carpeta de Google Drive
    FOLDER_ID = "1oWFnT-KijLjl315q-EcoDCi9XNRANTeJ"
    
    # Busca recursivamente todos los archivos jsonl en json_chunks
    archivos_jsonl = glob.glob('json_chunks/**/*.jsonl', recursive=True)
    
    archivos_modificados = 0

    for archivo in archivos_jsonl:
        lineas_modificadas = []
        hubo_cambios = False

        with open(archivo, 'r', encoding='utf-8') as f:
            for linea in f:
                if not linea.strip():
                    continue
                    
                data = json.loads(linea)

                # Condición: si es una Orden del Día o si la URL actual es la de la carpeta
                if "ORDEN DEL DIA" in data.get('codigo', '') or FOLDER_ID in data.get('url', ''):
                    
                    # Extraemos el nombre del archivo (asumiendo que es el código + .pdf)
                    nombre_archivo = f"{data['codigo']}.pdf"

                    # Armamos una URL de búsqueda avanzada de Google Drive.
                    # Esto buscará estrictamente ese archivo dentro de esa carpeta.
                    query = f'parent:{FOLDER_ID} title:"{nombre_archivo}"'
                    nueva_url = f"https://drive.google.com/drive/u/5/search?q={quote(query)}"

                    # Si la URL vieja es distinta a la nueva, la actualizamos
                    if data.get('url') != nueva_url:
                        data['url'] = nueva_url
                        hubo_cambios = True

                lineas_modificadas.append(json.dumps(data, ensure_ascii=False))

        # Si detectamos que se arregló al menos una línea, reescribimos el archivo
        if hubo_cambios:
            with open(archivo, 'w', encoding='utf-8') as f:
                for linea in lineas_modificadas:
                    f.write(linea + '\n')
            print(f"✅ Corregido: {archivo}")
            archivos_modificados += 1

    print(f"\n[INFO] Proceso terminado. Se corrigieron {archivos_modificados} archivos JSONL.")

if __name__ == "__main__":
    main()
