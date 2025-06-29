# update_boletines.py
import os, re, json, requests, fitz
from datetime import datetime
from pathlib import Path

# Carpeta donde guardar los jsonl
json_folder = Path("json_chunks")
json_folder.mkdir(exist_ok=True)

# URL base
url_base = "https://quilmes.gov.ar/pdf/boletines/"
pagina_boletines = "https://quilmes.gov.ar/institucional/gobierno_abierto_boletines.php"

# Obtener lista de boletines actuales en GitHub
actuales = {f.name for f in json_folder.glob("*.jsonl")}

# Obtener HTML de la página oficial
html = requests.get(pagina_boletines).text
pdfs = re.findall(r'href="(.*?boletin-\d+\.pdf)"', html)
pdfs = sorted(set(pdfs))

def generar_id(nombre, pagina):
    return f"{nombre}_{pagina}"

# Procesar los nuevos
for pdf_url in pdfs:
    nombre = pdf_url.split("/")[-1]
    numero = re.search(r"boletin-(\d+)", nombre)
    if not numero:
        continue
    numero = int(numero.group(1))
    json_nombre = f"boletines_part_{numero}.jsonl"
    json_path = json_folder / json_nombre
    if json_path.exists():
        print(f"Ya existe: {json_nombre}")
        continue

    print(f"Procesando: {nombre}")
    try:
        r = requests.get(pdf_url)
        r.raise_for_status()
        with open("temp.pdf", "wb") as f:
            f.write(r.content)

        doc = fitz.open("temp.pdf")
        with open(json_path, "w", encoding="utf8") as out:
            for page_num, page in enumerate(doc):
                texto = page.get_text().strip()
                if texto:
                    fragmento = {
                        "id": generar_id(nombre, page_num),
                        "archivo": nombre,
                        "pagina": page_num + 1,
                        "fragmento": texto
                    }
                    out.write(json.dumps(fragmento, ensure_ascii=False) + "\n")
        doc.close()
        os.remove("temp.pdf")
    except Exception as e:
        print(f"Error con {nombre}: {e}")
