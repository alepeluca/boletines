import os
import re
import json
import requests
import fitz  # PyMuPDF, para leer PDFs
from urllib.parse import urljoin
from tqdm import tqdm  # opcional para progreso

# URL base del sitio y de la página que lista los boletines
BASE_URL = "https://quilmes.gov.ar"
LISTADO_URL = "https://quilmes.gov.ar/institucional/gobierno_abierto_boletines.php"

# Directorios donde se guardan los archivos descargados y procesados
PDF_DIR = "pdfs"
JSON_CHUNKS_DIR = "json_chunks"
ULTIMA_ACTUALIZACION_FILE = "ultima_actualizacion.json"

# Crea los directorios si no existen
os.makedirs(PDF_DIR, exist_ok=True)
os.makedirs(JSON_CHUNKS_DIR, exist_ok=True)

# 🔍 Extrae la lista de boletines desde el HTML
def obtener_lista_boletines():
    r = requests.get(LISTADO_URL)
    r.raise_for_status()
    
    # Busca en el HTML los enlaces que coincidan con ../pdf/boletines/boletin-XXX.pdf
    matches = re.findall(r'href="(\.\./pdf/boletines/boletin-(\d+)\.pdf)"', r.text)

    # Devuelve una lista de tuplas: (número, url relativa)
    boletines = [(int(nro), url) for url, nro in matches]
    boletines = list(set(boletines))  # elimina duplicados
    boletines.sort()  # ordena por número de boletín
    return boletines

# 📄 Divide el texto de cada PDF en fragmentos
def pdf_a_fragmentos(pdf_path, fragment_size=1000):
    doc = fitz.open(pdf_path)
    fragments = []

    for page_num in range(doc.page_count):
        text = doc.load_page(page_num).get_text("text")

        # Divide el texto de la página en bloques de 'fragment_size' caracteres
        for i in range(0, len(text), fragment_size):
            frag = text[i:i+fragment_size].strip()
            if frag:
                fragments.append({
                    "pagina": page_num + 1,
                    "fragmento": frag
                })

    return fragments

# 🧾 Genera un archivo JSONL con los fragmentos de varios boletines
def generar_jsonl_chunk(nombre_chunk, boletines):
    idx = 0
    path = os.path.join(JSON_CHUNKS_DIR, nombre_chunk)

    with open(path, "w", encoding="utf-8") as f:
        for b in boletines:
            for frag in b["fragmentos"]:
                f.write(json.dumps({
                    "id": f"{b['archivo']}_{idx}",
                    "archivo": b["archivo"],
                    "fragmento": frag["fragmento"],
                    "pagina": frag["pagina"]
                }, ensure_ascii=False) + "\n")
                idx += 1

# 📁 Carga el número del último boletín procesado (desde archivo local)
def cargar_ultima_actualizacion():
    if os.path.exists(ULTIMA_ACTUALIZACION_FILE):
        with open(ULTIMA_ACTUALIZACION_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"ultimo_numero": 0}

# 💾 Guarda el número del último boletín procesado
def guardar_ultima_actualizacion(numero):
    with open(ULTIMA_ACTUALIZACION_FILE, "w", encoding="utf-8") as f:
        json.dump({"ultimo_numero": numero}, f, ensure_ascii=False)

# 🔢 Detecta el próximo número disponible para nombrar el nuevo chunk
def detectar_proximo_chunk():
    archivos = os.listdir(JSON_CHUNKS_DIR)
    
    # Busca todos los archivos tipo boletines_part_XX.jsonl
    chunks = [int(re.search(r'boletines_part_(\d+)\.jsonl', f).group(1))
              for f in archivos if re.match(r'boletines_part_\d+\.jsonl', f)]
    
    # Retorna el siguiente número (o 1 si no hay ningún chunk aún)
    return max(chunks, default=0) + 1

# 🧠 Función principal del script
def main():
    # Lista completa de boletines disponibles en la web
    lista_boletines = obtener_lista_boletines()
    print(f"Encontrados {len(lista_boletines)} boletines en la web.")

    # Carga el último número procesado previamente
    ultima = cargar_ultima_actualizacion()
    ultimo_num = ultima.get("ultimo_numero", 0)
    print(f"Último boletín procesado: {ultimo_num}")

    # Filtra sólo los boletines nuevos (mayores al último procesado)
    nuevos = [(nro, url_rel) for nro, url_rel in lista_boletines if nro > ultimo_num]

    if not nuevos:
        print("No hay boletines nuevos.")
        return

    boletines_procesar = []

    for nro, url_rel in nuevos:
        url_completa = urljoin(BASE_URL, url_rel)
        pdf_filename = f"boletin-{nro}.pdf"
        pdf_path = os.path.join(PDF_DIR, pdf_filename)

        print(f"Descargando {pdf_filename} ...")
        try:
            r = requests.get(url_completa)
            r.raise_for_status()
            with open(pdf_path, "wb") as f:
                f.write(r.content)
        except Exception as e:
            print(f"Error descargando {pdf_filename}: {e}")
            continue

        print(f"Procesando texto de {pdf_filename} ...")
        fragmentos = pdf_a_fragmentos(pdf_path)
        boletines_procesar.append({
            "archivo": pdf_filename.replace(".pdf", ".txt"),
            "fragmentos": fragmentos
        })

    # Detecta número de chunk a generar
    chunk_num = detectar_proximo_chunk()
    chunk_name = f"boletines_part_{chunk_num}.jsonl"

    # Genera el archivo JSONL con todos los boletines nuevos
    generar_jsonl_chunk(chunk_name, boletines_procesar)

    # Guarda el último número procesado
    ultimo_procesado = max(nro for nro, _ in nuevos)
    guardar_ultima_actualizacion(ultimo_procesado)

    print(f"Proceso completado. Último boletín actualizado: {ultimo_procesado}")

# 🏁 Punto de entrada del script
if __name__ == "__main__":
    main()
