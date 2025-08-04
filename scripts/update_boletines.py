import os
import re
import requests
from bs4 import BeautifulSoup
from PyPDF2 import PdfReader

# URL base de los boletines municipales
BASE_URL = "https://quilmes.gov.ar/gobierno/boletin_oficial.php"
PDF_BASE_URL = "https://quilmes.gov.ar/archivos/boletin-oficial/pdf/boletin-{}.pdf"

# Carpeta donde se guardan los boletines descargados
CARPETA_BOLETINES = "boletines"
os.makedirs(CARPETA_BOLETINES, exist_ok=True)

# Función para obtener el número del último boletín disponible en la web
def obtener_ultimo_boletin():
    print("Obteniendo listado de boletines...")
    response = requests.get(BASE_URL)
    soup = BeautifulSoup(response.content, "html.parser")

    # Buscar todos los links que coincidan con el patrón boletin-XXX.pdf
    links = soup.find_all("a", href=re.compile(r"boletin-\d+\.pdf"))
    numeros = []
    for link in links:
        match = re.search(r"boletin-(\d+)\.pdf", link["href"])
        if match:
            numeros.append(int(match.group(1)))

    ultimo = max(numeros)
    print(f"Último boletín encontrado en la web: {ultimo}")
    return ultimo

# Función para descargar un boletín PDF dado su número
def descargar_boletin(numero):
    url = PDF_BASE_URL.format(numero)
    ruta_archivo = os.path.join(CARPETA_BOLETINES, f"boletin-{numero}.pdf")
    print(f"Descargando boletin-{numero}.pdf ...")
    response = requests.get(url)
    if response.status_code == 200:
        with open(ruta_archivo, "wb") as f:
            f.write(response.content)
        return ruta_archivo
    else:
        print(f"No se pudo descargar el boletín {numero}")
        return None

# Función para extraer texto de un PDF y guardarlo como TXT
def procesar_boletin(ruta_pdf):
    numero = re.search(r"boletin-(\d+)\.pdf", ruta_pdf).group(1)
    ruta_txt = os.path.join(CARPETA_BOLETINES, f"boletin-{numero}.txt")
    print(f"Procesando texto de boletin-{numero}.pdf ...")
    try:
        reader = PdfReader(ruta_pdf)
        texto = ""
        for page in reader.pages:
            texto += page.extract_text() + "\n"

        with open(ruta_txt, "w", encoding="utf-8") as f:
            f.write(texto)
    except Exception as e:
        print(f"Error al procesar el PDF: {e}")

# MAIN: Ejecutar el flujo
def main():
    ultimo = obtener_ultimo_boletin()
    ruta_pdf = os.path.join(CARPETA_BOLETINES, f"boletin-{ultimo}.pdf")

    # Si el PDF ya está en la carpeta, no lo descargamos de nuevo
    if not os.path.exists(ruta_pdf):
        ruta_pdf = descargar_boletin(ultimo)
        if ruta_pdf:
            procesar_boletin(ruta_pdf)
    else:
        print(f"El boletín-{ultimo}.pdf ya fue descargado. Revisando si falta el .txt...")
        ruta_txt = ruta_pdf.replace(".pdf", ".txt")
        if not os.path.exists(ruta_txt):
            procesar_boletin(ruta_pdf)
        else:
            print("Ya está procesado.")

if __name__ == "__main__":
    main()
