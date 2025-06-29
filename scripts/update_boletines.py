import os
import re
import json
import time
import requests
import fitz  # PyMuPDF

URL_LISTA = "https://quilmes.gov.ar/institucional/gobierno_abierto_boletines.php"
PDF_BASE_URL = "https://quilmes.gov.ar/pdf/boletines/"
JSON_CHUNKS_DIR = "json_chunks"
PDFS_DIR = "pdfs"
ULTIMA_ACTUALIZACION_FILE = "ultima_actualizacion.json"

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    'Accept-Language': 'es-ES,es;q=0.9',
    'Referer': 'https://quilmes.gov.ar/',
    'Connection': 'keep-alive'
}

def obtener_urls_pdf(max_reintentos=3, espera=10):
    for intento in range(max_reintentos):
        try:
            print(f"Intento {intento + 1} para obtener listado de boletines...")
            res = requests.get(URL_LISTA, headers=HEADERS, timeout=30)
            res.raise_for_status()
            urls = re.findall(r'href="(.*?boletin-\d+\.pdf)"', res.text)
            urls = sorted(set(urls))
            print(f"Encontrados {len(urls)} boletines en la web.")
            return urls
        except Exception as e:
            print(f"Error al obtener URLs: {e}")
            if intento < max_reintentos -1:
                print(f"Reintentando en {espera} segundos...")
                time.sleep(espera)
            else:
                print("No se pudo conectar al sitio para obtener boletines.")
                return []

def cargar_boletines_existentes():
    """Devuelve el set de PDFs ya descargados y procesados (desde json_chunks)."""
    existentes = set()
    if not os.path.isdir(JSON_CHUNKS_DIR):
        os.makedirs(JSON_CHUNKS_DIR)
        return existentes

    for archivo in os.listdir(JSON_CHUNKS_DIR):
        if archivo.endswith('.jsonl'):
            path = os.path.join(JSON_CHUNKS_DIR, archivo)
            try:
                with open(path, 'r', encoding='utf-8') as f:
                    for linea in f:
                        if not linea.strip():
                            continue
                        obj = json.loads(linea)
                        existentes.add(obj['archivo'])
            except Exception as e:
                print(f"Error leyendo {archivo}: {e}")
    return existentes

def descargar_pdf(pdf_url, destino):
    if os.path.exists(destino):
        print(f"PDF ya existe: {destino}")
        return True
    try:
        print(f"Descargando {pdf_url} ...")
        r = requests.get(pdf_url, headers=HEADERS, stream=True, timeout=60)
        r.raise_for_status()
        with open(destino, 'wb') as f:
            for chunk in r.iter_content(chunk_size=8192):
                f.write(chunk)
        print(f"Descargado {destino}")
        return True
    except Exception as e:
        print(f"Error descargando {pdf_url}: {e}")
        return False

def pdf_a_jsonl(pdf_path, archivo_nombre, offset_id=0):
    """Convierte un PDF a jsonl fragmentado (cada fragmento 1000 caracteres aprox)."""
    doc = fitz.open(pdf_path)
    chunks = []
    chunk_size = 1000
    count = offset_id

    for pagina_num in range(len(doc)):
        pagina = doc.load_page(pagina_num)
        texto = pagina.get_text("text")
        # Divide texto en fragmentos por chunk_size sin cortar palabras
        palabras = texto.split()
        frag = ""
        for palabra in palabras:
            if len(frag) + len(palabra) + 1 > chunk_size:
                chunks.append({
                    "id": f"{archivo_nombre}_{count}",
                    "archivo": archivo_nombre,
                    "fragmento": frag.strip(),
                    "pagina": pagina_num + 1
                })
                count += 1
                frag = palabra + " "
            else:
                frag += palabra + " "
        if frag.strip():
            chunks.append({
                "id": f"{archivo_nombre}_{count}",
                "archivo": archivo_nombre,
                "fragmento": frag.strip(),
                "pagina": pagina_num + 1
            })
            count += 1
    return chunks

def guardar_chunks_jsonl(chunks, parte_num):
    if not os.path.isdir(JSON_CHUNKS_DIR):
        os.makedirs(JSON_CHUNKS_DIR)
    archivo = os.path.join(JSON_CHUNKS_DIR, f"boletines_part_{parte_num}.jsonl")
    with open(archivo, 'w', encoding='utf-8') as f:
        for chunk in chunks:
            json.dump(chunk, f, ensure_ascii=False)
            f.write('\n')
    print(f"Guardado archivo {archivo} con {len(chunks)} fragmentos.")

def obtener_ultimo_num_part():
    if not os.path.isdir(JSON_CHUNKS_DIR):
        return 0
    nums = []
    for nombre in os.listdir(JSON_CHUNKS_DIR):
        m = re.match(r'boletines_part_(\d+)\.jsonl', nombre)
        if m:
            nums.append(int(m.group(1)))
    return max(nums) if nums else 0

def guardar_ultima_actualizacion(num_boletin, fecha_str):
    data = {
        "ultimo_boletin": num_boletin,
        "fecha": fecha_str
    }
    with open(ULTIMA_ACTUALIZACION_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False)
    print(f"Actualización guardada: boletín {num_boletin} fecha {fecha_str}")

def main():
    urls = obtener_urls_pdf()
    if not urls:
        print("No se pudo obtener la lista de boletines, saliendo.")
        return

    existentes = cargar_boletines_existentes()

    # Filtrar solo nuevos PDFs (el nombre final de archivo, ej: boletin-493.pdf)
    nuevos = []
    for url in urls:
        nombre_archivo = url.split('/')[-1]
        if nombre_archivo not in existentes:
            nuevos.append(url)
    if not nuevos:
        print("No hay boletines nuevos para procesar.")
        return

    print(f"Boletines nuevos a procesar: {len(nuevos)}")

    if not os.path.isdir(PDFS_DIR):
        os.makedirs(PDFS_DIR)

    ultimo_num_part = obtener_ultimo_num_part()
    parte_nueva = ultimo_num_part + 1

    all_chunks = []

    for pdf_url in nuevos:
        nombre_pdf = pdf_url.split('/')[-1]
        ruta_pdf_local = os.path.join(PDFS_DIR, nombre_pdf)
        exito = descargar_pdf(pdf_url, ruta_pdf_local)
        if not exito:
            print(f"No se pudo descargar {nombre_pdf}, saltando.")
            continue

        print(f"Procesando PDF {nombre_pdf}...")
        chunks = pdf_a_jsonl(ruta_pdf_local, nombre_pdf)
        all_chunks.extend(chunks)

    if not all_chunks:
        print("No se generaron fragmentos nuevos.")
        return

    # Guardar todos los fragmentos en un nuevo jsonl (puede ser muy grande, considerar dividir si querés)
    guardar_chunks_jsonl(all_chunks, parte_nueva)

    # Guardar última actualización con el boletín de mayor número y fecha (la fecha la extraemos del nombre yyyyMMdd)
    ultimo_boletin = max([int(re.search(r'boletin-(\d+)\.pdf', c['archivo']).group(1)) for c in all_chunks])
    fecha_ultimo = max([c['archivo'][:8] for c in all_chunks])  # yyyyMMdd string, puede ser reemplazado si querés otro formato
    fecha_ultimo_fmt = f"{fecha_ultimo[6:8]}/{fecha_ultimo[4:6]}/{fecha_ultimo[0:4]}"
    guardar_ultima_actualizacion(ultimo_boletin, fecha_ultimo_fmt)

if __name__ == "__main__":
    main()
