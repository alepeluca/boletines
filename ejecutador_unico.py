# ejecutador_unico.py
import os
import re
import json
import requests
import fitz  # PyMuPDF
from pathlib import Path

# --- SECCIÓN DE CONTROL DE VERSIONES ---
VERSION = "v2.1.0"
FECHA_MODIFICACION = "23-05-2026"

print("=========================================================")
print(f"🚀 SISTEMA UNIFICADO DE BOLETINES - Versión: {VERSION}")
print(f"📅 Última actualización de código: {FECHA_MODIFICACION}")
print("=========================================================\n")

CHUNKS_DIR = Path("json_chunks")

print("🚀 Iniciando Sistema Unificado de Boletines...")

json_folder = Path("json_chunks")
json_folder.mkdir(exist_ok=True)

dominio_base = "https://quilmes.gov.ar"
pagina_boletines = "https://quilmes.gov.ar/institucional/gobierno_abierto_boletines.php"


def extraer_maximo_numero_real():
    """Inspecciona los nombres de archivos jsonl para encontrar el boletín más alto."""
    archivos = list(json_folder.glob("*.jsonl"))
    numeros = []

    for f in archivos:
        match = re.search(r"boletines_part_(\d+)\.jsonl", f.name)
        if match:
            numeros.append(int(match.group(1)))

    return max(numeros) if numeros else 500


def generar_id(nombre, pagina):
    return f"{nombre}_{pagina}"


def procesar_pdf_a_jsonl(url_descarga, nombre_archivo, ruta_salida_json):
    """Descarga un PDF, extrae su contenido y escribe el archivo jsonl correspondiente."""

    print(f"   📥 Descargando desde: {url_descarga}")

    r = requests.get(url_descarga, timeout=30)
    r.raise_for_status()

    temp_pdf = "temp.pdf"

    with open(temp_pdf, "wb") as f:
        f.write(r.content)

    doc = fitz.open(temp_pdf)
    paginas_con_texto = 0

    with open(ruta_salida_json, "w", encoding="utf8") as out:

        for page_num, page in enumerate(doc):

            texto = page.get_text().strip()

            if texto:
                fragmento = {
                    "id": generar_id(nombre_archivo, page_num + 1),
                    "archivo": nombre_archivo,
                    "pagina": page_num + 1,
                    "fragmento": texto
                }

                out.write(json.dumps(fragmento, ensure_ascii=False) + "\n")
                paginas_con_texto += 1

    doc.close()

    if os.path.exists(temp_pdf):
        os.remove(temp_pdf)

    print(
        f"   ✅ ÉXITO: Guardado {ruta_salida_json.name} "
        f"con {paginas_con_texto} páginas procesadas."
    )


def main():

    # =========================================================================
    # FASE 1: AUDITORÍA DE LA WEB OFICIAL
    # =========================================================================

    print(f"\n🌐 [FASE 1] Escaneando listado oficial: {pagina_boletines}")

    try:
        response = requests.get(pagina_boletines, timeout=30)
        response.raise_for_status()
        html = response.text

    except Exception as e:
        print(f"❌ Error crítico de conexión al portal oficial: {e}")
        html = ""

    # Captura enlaces con guion medio o bajo
    pdfs = re.findall(
        r'href="(.*?boletin[-_]\d+\.pdf)"',
        html,
        re.IGNORECASE
    )

    pdfs = sorted(set(pdfs))

    print(f"🔎 Se detectaron {len(pdfs)} enlaces de boletines.")

    boletines_descargados_fase1 = 0

    for pdf_url in pdfs:

        nombre = pdf_url.split("/")[-1]

        match_numero = re.search(r"boletin[-_](\d+)", nombre)

        if not match_numero:
            continue

        numero = int(match_numero.group(1))

        json_nombre = f"boletines_part_{numero}.jsonl"
        json_path = json_folder / json_nombre

        if json_path.exists():
            continue

        print(f"▶️ NUEVO HISTÓRICO DETECTADO: Boletín {numero} ({nombre})")

        try:

            # Reconstrucción de URLs
            if pdf_url.startswith("..") or pdf_url.startswith("/"):

                url_limpia = pdf_url.lstrip(".")

                if not url_limpia.startswith("/"):
                    url_limpia = "/" + url_limpia

                full_url = f"{dominio_base}{url_limpia}"

            elif not pdf_url.startswith("http"):

                full_url = f"{dominio_base}/pdf/boletines/{nombre}"

            else:
                full_url = pdf_url

            procesar_pdf_a_jsonl(full_url, nombre, json_path)

            boletines_descargados_fase1 += 1

        except Exception as e:
            print(f"   ❌ Error procesando {nombre}: {e}")

    # =========================================================================
    # FASE 2: BÚSQUEDA DE CONTINGENCIA DIARIA
    # =========================================================================

    print("\n🔍 [FASE 2] Verificación del boletín diario...")

    ultimo_real = extraer_maximo_numero_real()

    siguiente_esperado = ultimo_real + 1

    json_esperado_path = (
        json_folder /
        f"boletines_part_{siguiente_esperado}.jsonl"
    )

    if json_esperado_path.exists():

        print(
            f"El boletín {siguiente_esperado} "
            f"ya existe en la carpeta."
        )

    else:

        print(
            f"Último boletín detectado: {ultimo_real}. "
            f"Buscando el {siguiente_esperado}..."
        )

        url_intento_medio = (
            f"{dominio_base}/pdf/boletines/"
            f"boletin-{siguiente_esperado}.pdf"
        )

        nombre_intento_medio = (
            f"boletin-{siguiente_esperado}.pdf"
        )

        url_intento_bajo = (
            f"{dominio_base}/pdf/boletines/"
            f"boletin_{siguiente_esperado}.pdf"
        )

        nombre_intento_bajo = (
            f"boletin_{siguiente_esperado}.pdf"
        )

        logrado_con_exito = False

        # Intento A
        print(f"   Intentando: {url_intento_medio}")

        try:

            response_test = requests.head(
                url_intento_medio,
                timeout=15,
                allow_redirects=True
            )

            if response_test.status_code == 200:

                procesar_pdf_a_jsonl(
                    url_intento_medio,
                    nombre_intento_medio,
                    json_esperado_path
                )

                logrado_con_exito = True

        except Exception as e:
            print(f"   ❌ Error en intento A: {e}")

        # Intento B
        if not logrado_con_exito:

            print(f"   Intentando: {url_intento_bajo}")

            try:

                response_test = requests.head(
                    url_intento_bajo,
                    timeout=15,
                    allow_redirects=True
                )

                if response_test.status_code == 200:

                    procesar_pdf_a_jsonl(
                        url_intento_bajo,
                        nombre_intento_bajo,
                        json_esperado_path
                    )

                    logrado_con_exito = True

            except Exception as e:
                print(f"   ❌ Error en intento B: {e}")

        if not logrado_con_exito:

            print(
                f"📭 El boletín número "
                f"{siguiente_esperado} "
                f"todavía no está publicado."
            )

    print("\n🏁 Proceso unificado finalizado.")


if __name__ == "__main__":
    main()
