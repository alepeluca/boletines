import os
import json
import requests
from pathlib import Path
from email.utils import parsedate_to_datetime

JSON_CHUNKS_DIR = Path("json_chunks")

def obtener_fecha_head(url):
    try:
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
        respuesta = requests.head(url, headers=headers, allow_redirects=True, timeout=8)
        last_modified = respuesta.headers.get("Last-Modified")
        if last_modified:
            dt = parsedate_to_datetime(last_modified)
            return dt.strftime("%Y-%m-%d")
    except Exception as e:
        print(f"  [⚠️] Error en HEAD para {url}: {e}")
    return None

def migrar_chunks():
    print("=== Iniciando migración de fechas vía HEAD en Chunks ===")
    
    # Cache para no repetir la petición HEAD si el mismo PDF aparece en varias páginas/líneas
    cache_fechas = {}

    # Recorremos todas las subcarpetas dentro de json_chunks/ (bolet, lici, taqui, orden)
    for ruta_archivo in JSON_CHUNKS_DIR.glob("**/*.jsonl"):
        print(f"Procesando: {ruta_archivo.name}")
        lineas_modificadas = []
        cambios = False
        
        with open(ruta_archivo, "r", encoding="utf-8") as f:
            for linea in f:
                if not linea.strip():
                    continue
                chunk = json.loads(linea)
                url = chunk.get("url")
                
                # Si el chunk ya tiene fecha válida, la dejamos. Si no, la buscamos.
                if not chunk.get("fecha") and url and "quilmes.gov.ar" in url:
                    if url not in cache_fechas:
                        print(f"  -> Consultando HEAD para: {url}")
                        fecha_servidor = obtener_fecha_head(url)
                        cache_fechas[url] = fecha_servidor
                    
                    if cache_fechas[url]:
                        chunk["fecha"] = cache_fechas[url]
                        cambios = True
                
                lineas_modificadas.append(json.dumps(chunk, ensure_ascii=False) + "\n")
        
        # Guardamos los cambios solo si modificamos alguna fecha
        if cambios:
            with open(ruta_archivo, "w", encoding="utf-8") as f:
                f.writelines(lineas_modificadas)
            print(f"  [✅] {ruta_archivo.name} actualizado con éxito.")

if __name__ == "__main__":
    migrar_chunks()
