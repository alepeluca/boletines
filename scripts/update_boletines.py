import os
import re
import json
import requests
import fitz  # pymupdf
from urllib.parse import urljoin
from tqdm import tqdm

BASE_URL = "https://quilmes.gov.ar"
LISTADO_URL = "https://quilmes.gov.ar/institucional/gobierno_abierto_boletines.php"
PDF_DIR = "pdfs"
JSON_CHUNKS_DIR = "json_chunks"
ULTIMA_ACTUALIZACION_FILE = "ultima_actualizacion.json"

# Asegura directorios
os.makedirs(PDF_DIR, exist_ok=True)
os.makedirs(JSON_CHUNKS_DIR, exist_ok=True)

def obtener_lista_boletines():
    print("Obteniendo listado de boletines...")
    r = requests.get(LISTADO_URL)
    r.raise_for_status()
    html = r.text
    # Busca href relativos a PDF: ../pdf/boletines/boletin-xxx.pdf
    urls = re.findall(r'href="(\.\./pdf/boletines/boletin-\d+\.pdf)"', html)
    urls = list(set(urls))  # evita duplicados
    urls.sort()
    return urls

def pdf_a_fragmentos(pdf_path, fragment_size=500):
    doc = fitz.open(pdf_path)
    fragments = []
    for page_num in range(doc.page_count):
        page = doc.load_page(page_num)
        text = page.get_text("text")
        # Dividir texto en fragmentos de tamaño fragment_size
        for i in range(0, len(text), fragment_size):
            fragment = text[i:i+fragment_size].strip()
            if fragment:
                fragments.append({
                    "pagina": page_num + 1,
                    "fragmento": fragment
                })
    return fragments

def generar_jsonl_chunk(nombre_chunk, boletines):
    # boletines: lista de diccionarios con keys archivo y fragmentos
    print(f"Generando {nombre_chunk} con {len(boletines)} boletines...")
    idx = 0
    with open(os.path.join(JSON_CHUNKS_DIR, nombre_chunk), "w", encoding="utf-8") as f:
        for b in boletines:
            archivo = b["archivo"]
            for frag in b["fragmentos"]:
                obj = {
                    "id": f"{archivo}_{idx}",
                    "archivo": archivo,
                    "fragmento": frag["fragmento"],
                    "pagina": frag["pagina"]
                }
                f.write(json.dumps(obj, ensure_ascii=False) + "\n")
                idx += 1

def cargar_ultima_actualizacion():
    if os.path.exists(ULTIMA_ACTUALIZACION_FILE):
        with open(ULTIMA_ACTUALIZACION_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"ultimo_numero": 0, "fecha": ""}

def guardar_ultima_actualizacion(numero, fecha):
    with open(ULTIMA_ACTUALIZACION_FILE, "w", encoding="utf-8") as f:
        json.dump({"ultimo_numero": numero, "fecha": fecha}, f, ensure_ascii=False)

def main():
    lista_relativa = obtener_lista_boletines()
    print(f"Encontrados {len(lista_relativa)} boletines en la web.")
    
    # Carga última actualización para no repetir descargas
    ultima = cargar_ultima_actualizacion()
    ultimo_numero = ultima.get("ultimo_numero", 0)
    print(f"Último boletín procesado: {ultimo_numero}")
    
    # Filtrar nuevos boletines (extraer nro del nombre)
    nuevos = []
    for url_rel in lista_relativa:
        m = re.search(r'boletin-(\d+)\.pdf', url_rel)
        if not m:
            continue
        nro = int(m.group(1))
        if nro > ultimo_numero:
            nuevos.append((nro, url_rel))
    nuevos.sort(key=lambda x: x[0])
    
    if not nuevos:
        print("No hay boletines nuevos para procesar.")
        return
    
    boletines_procesar = []
    for nro, url_rel in nuevos:
        url_completa = urljoin(BASE_URL, url_rel)
        pdf_filename = f"boletin-{nro}.pdf"
        pdf_path = os.path.join(PDF_DIR, pdf_filename)
        
        if not os.path.exists(pdf_path):
            print(f"Descargando {pdf_filename} ...")
            try:
                r = requests.get(url_completa)
                r.raise_for_status()
                with open(pdf_path, "wb") as f:
                    f.write(r.content)
            except Exception as e:
                print(f"Error descargando {pdf_filename}: {e}")
                continue
        else:
            print(f"{pdf_filename} ya existe, saltando descarga.")
        
        print(f"Procesando texto de {pdf_filename} ...")
        fragmentos = pdf_a_fragmentos(pdf_path)
        boletines_procesar.append({
            "archivo": pdf_filename.replace(".pdf", ".txt"),
            "fragmentos": fragmentos
        })
    
    # Generar nuevo chunk jsonl con estos boletines
    # Asumimos que los chunks previos terminan en boletines_part_17.jsonl
    chunk_num = 18
    nombre_chunk = f"boletines_part_{chunk_num}.jsonl"
    generar_jsonl_chunk(nombre_chunk, boletines_procesar)
    
    # Actualizar última actualización con el mayor nro procesado
    ultimo_procesado = max(n[0] for n in nuevos)
    guardar_ultima_actualizacion(ultimo_procesado, "")
    print(f"Proceso completado. Último boletín actualizado: {ultimo_procesado}")

if __name__ == "__main__":
    main()
