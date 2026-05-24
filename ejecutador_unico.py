# ejecutador_unico.py

```python
import re
import json
import tempfile
from pathlib import Path

import fitz
import requests

# =========================================================
# CONFIG
# =========================================================

VERSION = "v3.0.0"
FECHA_MODIFICACION = "23-05-2026"

DOMINIO_BASE = "https://quilmes.gov.ar"
PAGINA_BOLETINES = (
    "https://quilmes.gov.ar/institucional/"
    "gobierno_abierto_boletines.php"
)

JSON_FOLDER = Path("json_chunks")
JSON_FOLDER.mkdir(exist_ok=True)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0 Safari/537.36"
    )
}

print("=" * 60)
print(f"🚀 SISTEMA UNIFICADO DE BOLETINES - {VERSION}")
print(f"📅 Última modificación: {FECHA_MODIFICACION}")
print("=" * 60)


# =========================================================
# HELPERS
# =========================================================


def generar_id(nombre_archivo, pagina):
    return f"{nombre_archivo}_{pagina}"



def obtener_numeros_existentes():
    """Devuelve un set con los boletines ya descargados."""

    existentes = set()

    for archivo in JSON_FOLDER.glob("boletines_part_*.jsonl"):

        match = re.search(r"boletines_part_(\d+)\.jsonl", archivo.name)

        if match:
            existentes.add(int(match.group(1)))

    return existentes



def descargar_html(url):

    response = requests.get(
        url,
        headers=HEADERS,
        timeout=30
    )

    response.raise_for_status()

    return response.text



def reconstruir_url(pdf_url, nombre):

    if pdf_url.startswith("http"):
        return pdf_url

    if pdf_url.startswith("..") or pdf_url.startswith("/"):

        url_limpia = pdf_url.lstrip(".")

        if not url_limpia.startswith("/"):
            url_limpia = "/" + url_limpia

        return f"{DOMINIO_BASE}{url_limpia}"

    return f"{DOMINIO_BASE}/pdf/boletines/{nombre}"



def extraer_pdfs(html):

    matches = re.findall(
        r'href=[\'"](.*?boletin[-_](\d+)\.pdf)[\'"]',
        html,
        re.IGNORECASE
    )

    resultado = []

    for url, numero in matches:
        resultado.append((url, int(numero)))

    resultado = list(set(resultado))
    resultado.sort(key=lambda x: x[1])

    return resultado



def procesar_pdf_a_jsonl(url_descarga, numero_boletin):

    nombre_archivo = url_descarga.split("/")[-1]

    salida = JSON_FOLDER / f"boletines_part_{numero_boletin}.jsonl"

    print(f"   📥 Descargando desde: {url_descarga}")

    response = requests.get(
        url_descarga,
        headers=HEADERS,
        timeout=60
    )

    response.raise_for_status()

    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:

        tmp.write(response.content)
        temp_pdf_path = tmp.name

    paginas_con_texto = 0

    try:

        doc = fitz.open(temp_pdf_path)

        with open(salida, "w", encoding="utf8") as out:

            for pagina_idx, page in enumerate(doc, start=1):

                texto = page.get_text().strip()

                if not texto:
                    continue

                fragmento = {
                    "id": generar_id(nombre_archivo, pagina_idx),
                    "archivo": nombre_archivo,
                    "pagina": pagina_idx,
                    "fragmento": texto
                }

                out.write(
                    json.dumps(fragmento, ensure_ascii=False)
                    + "\n"
                )

                paginas_con_texto += 1

        doc.close()

    finally:

        Path(temp_pdf_path).unlink(missing_ok=True)

    print(
        f"   ✅ ÉXITO: Guardado {salida.name} "
        f"con {paginas_con_texto} páginas procesadas."
    )


# =========================================================
# MAIN
# =========================================================


def main():

    existentes = obtener_numeros_existentes()

    print(f"📚 Boletines ya descargados: {len(existentes)}")

    print(f"🌐 Escaneando: {PAGINA_BOLETINES}")

    try:

        html = descargar_html(PAGINA_BOLETINES)

    except Exception as e:

        print(f"❌ Error descargando HTML: {e}")
        return

    pdfs = extraer_pdfs(html)

    print(f"🔎 PDFs encontrados: {len(pdfs)}")

    nuevos = 0

    for pdf_url, numero in pdfs:

        if numero in existentes:
            continue

        print(
            f"▶️ NUEVO HISTÓRICO DETECTADO: "
            f"Boletín {numero}"
        )

        try:

            nombre = pdf_url.split("/")[-1]

            full_url = reconstruir_url(pdf_url, nombre)

            procesar_pdf_a_jsonl(full_url, numero)

            nuevos += 1

        except Exception as e:

            print(f"❌ Error procesando boletín {numero}: {e}")

    print()
    print(f"✅ Nuevos boletines descargados: {nuevos}")
    print("🏁 Proceso finalizado")


if __name__ == "__main__":
    main()
