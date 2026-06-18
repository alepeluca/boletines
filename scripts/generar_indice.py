import csv
import json
import glob
from pathlib import Path

# ... (tus configuraciones previas) ...

def compilar_indice():
    archivos_jsonl = glob.glob('json_chunks/**/*.jsonl', recursive=True)
    
    # Usamos un diccionario para agrupar por URL (así no hay duplicados)
    documentos_unicos = {}

    for ruta_archivo in archivos_jsonl:
        with open(ruta_archivo, 'r', encoding='utf-8') as f:
            for linea in f:
                if not linea.strip():
                    continue
                
                datos = json.loads(linea)
                url = datos.get('url', '')
                
                # Si es la primera vez que vemos este PDF, lo guardamos
                if url not in documentos_unicos:
                    # Extraer categoría de la ruta (boletines, lici, taqui, orden)
                    categoria = "boletines" # (Ajusta tu lógica de categoría acá)
                    if "lici" in ruta_archivo: categoria = "licitaciones"
                    elif "taqui" in ruta_archivo: categoria = "taquigraficas"
                    elif "orden" in ruta_archivo: categoria = "ordenes"

                    # Extraer info clave (como hacías con el OBJETO de las licitaciones)
                    extra_info = ""
                    if categoria == "licitaciones" and "OBJETO:" in datos.get('fragmento', ''):
                        # Extrae las primeras 5 palabras después de OBJETO:
                        fragmento = datos['fragmento']
                        try:
                            obj_texto = fragmento.split('OBJETO:')[1].strip()
                            extra_info = " ".join(obj_texto.split()[:5]) + "..."
                        except:
                            pass

                    # Guardamos la fila maestra del documento
                    documentos_unicos[url] = {
                        'categoria': categoria,
                        'archivo': datos.get('archivo', ''),
                        'url': url,
                        'fecha': datos.get('procesado', '')[:10], # o tu lógica de fecha
                        'extra_info': extra_info,
                        'paginas': 1, # Empezamos a contar
                        'fragmento': datos.get('fragmento', '')[:200] # Solo guardamos un poquito del inicio
                    }
                else:
                    # Si ya lo vimos (es la página 2, 3, etc.), solo le sumamos 1 al contador de páginas
                    documentos_unicos[url]['paginas'] += 1

    # Ahora sí, escribimos el CSV con solo 1 fila por documento
    with open('indice_documentos.csv', 'w', newline='', encoding='utf-8') as f_csv:
        columnas = ['categoria', 'archivo', 'url', 'fecha', 'extra_info', 'paginas', 'fragmento']
        writer = csv.DictWriter(f_csv, fieldnames=columnas)
        writer.writeheader()
        
        for doc in documentos_unicos.values():
            writer.writerow(doc)

    print(f"✅ Índice compilado con éxito. Total de documentos únicos: {len(documentos_unicos)}")

if __name__ == '__main__':
    compilar_indice()
