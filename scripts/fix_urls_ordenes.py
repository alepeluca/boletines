import json
import glob
from urllib.parse import quote

def main():
    # El ID de tu carpeta de Google Drive para las Actas Taquigráficas
    FOLDER_ID = "1vBrQH0h1ddIlplj3ChZ0VkqAK8UjgecB"
    
    # Busca directamente en la subcarpeta de taquigráficas (ultra rápido)
    archivos_jsonl = glob.glob('json_chunks/taqui/*.jsonl')
    
    archivos_modificados = 0

    for archivo in archivos_jsonl:
        lineas_modificadas = []
        hubo_cambios = False

        with open(archivo, 'r', encoding='utf-8') as f:
            for linea in f:
                if not linea.strip():
                    continue
                    
                data = json.loads(linea)

                # Condición: Si la URL actual es el link general de la carpeta
                if FOLDER_ID in data.get('url', ''):
                    
                    # Usamos el campo 'archivo' que ya tiene el nombre completo con .pdf
                    nombre_archivo = data.get('archivo')
                    
                    # Por si en algún chunk viejo no existía 'archivo', armamos el fallback
                    if not nombre_archivo:
                        nombre_archivo = f"{data['codigo']}.pdf"

                    # Armamos la URL de búsqueda avanzada de Google Drive
                    query = f'parent:{FOLDER_ID} title:"{nombre_archivo}"'
                    nueva_url = f"https://drive.google.com/drive/u/5/search?q={quote(query)}"

                    # Si la URL vieja es distinta a la nueva, actualizamos
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

    print(f"\n[INFO] Proceso terminado. Se corrigieron {archivos_modificados} archivos JSONL de Taquigráficas.")

if __name__ == "__main__":
    main()
