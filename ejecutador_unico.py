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
print(f"=========================================================")
print(f"🚀 SISTEMA UNIFICADO DE BOLETINES - Versión: {VERSION}")
print(f"📅 Última actualización de código: {FECHA_MODIFICACION}")
print(f"=========================================================\n")

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
    r = requests.get(url_descarga)
    r.raise_for_status()
    
    with open("temp.pdf", "wb") as f:
        f.write(r.content)

    doc = fitz.open("temp.pdf")
    paginas_con_texto = 0
    
    with open(ruta_salida_json, "w", encoding="utf8") as out:
        for page_num, page in enumerate(doc):
            texto = page.get_text().strip()
            if texto:
                fragmento = {
                    "id": generar_id(nombre_archivo, page_num),
                    "archivo": nombre_archivo,
                    "pagina": page_num + 1,
                    "fragmento": texto
                }
                out.write(json.dumps(fragmento, ensure_ascii=False) + "\n")
                paginas_con_texto += 1
                
    doc.close()
    os.remove("temp.pdf")
    print(f"   ✅ ÉXITO: Guardado {ruta_salida_json.name} con {paginas_con_texto} páginas procesadas.")

def main():
    # =========================================================================
    # FASE 1: AUDITORÍA DE LA WEB OFICIAL (Historial y enlaces con guiones mixtos)
    # =========================================================================
    print(f"\n🌐 [FASE 1] Escaneando listado oficial: {pagina_boletines}")
    try:
        html = requests.get(pagina_boletines).text
    except Exception as e:
        print(f"❌ Error crítico de conexión al portal oficial: {e}")
        html = ""

    # Captura enlaces tanto con guion medio (-) como con guion bajo (_)
    pdfs = re.findall(r'href="(.*?boletin[-_]\d+\.pdf)"', html)
    pdfs = sorted(set(pdfs))
    print(f"🔎 Se detectaron {len(pdfs)} enlaces de boletines en el HTML de la página.")

    boletines_descargados_fase1 = 0

    for pdf_url in pdfs:
        nombre = pdf_url.split("/")[-1]
        
        # Valida que el nombre contenga la palabra boletín y extrae su número
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
            # Reconstrucción de URLs relativas (Manejo de rutas con .. o /)
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
            print(f"   ❌ Error procesando {nombre}: {e} (URL: {pdf_url})")

    # =========================================================================
    # FASE 2: BÚSQUEDA DE CONTINGENCIA DIARIA (Prevenir demoras de actualización web)
    # =========================================================================
    print("\n🔍 [FASE 2] Iniciando verificación del boletín diario de contingencia...")
    ultimo_real = extraer_maximo_numero_real()
    siguiente_esperado = ultimo_real + 1
    json_esperado_path = json_folder / f"boletines_part_{siguiente_esperado}.jsonl"

    if json_esperado_path.exists():
        print(f"El boletín diario esperado ({siguiente_esperado}) ya se encuentra guardado en la carpeta chunks.")
    else:
        print(f"El número real más alto en tu carpeta es {ultimo_real}. Buscando proactivamente el esperado {siguiente_esperado}...")
        
        url_intento_medio = f"{dominio_base}/pdf/boletines/boletin-{siguiente_esperado}.pdf"
        nombre_intento_medio = f"boletin-{siguiente_esperado}.pdf"
        
        url_intento_bajo = f"{dominio_base}/pdf/boletines/boletin_{siguiente_esperado}.pdf"
        nombre_intento_bajo = f"boletin_{siguiente_esperado}.pdf"
        
        logrado_con_exito = False
        
        # Intento A: Probar con guion medio directo al servidor
        print(f"   Intentando acceso directo con guion medio: {url_intento_medio}")
        response_test = requests.head(url_intento_medio)
        if response_test.status_code == 200:
            try:
                procesar_pdf_a_jsonl(url_intento_medio, nombre_intento_medio, json_esperado_path)
                logrado_con_exito = True
            except Exception as e:
                print(f"   ❌ Error durante el procesamiento de la descarga directa (guion medio): {e}")

        # Intento B: Si falló, probar con guion bajo directo al servidor
        if not logrado con_exito:
            print(f"   No disponible con guion medio. Intentando acceso directo con guion bajo: {url_intento_bajo}")
            response_test = requests.head(url_intento_bajo)
            if response_test.status_code == 200:
                try:
                    procesar_pdf_a_jsonl(url_intento_bajo, nombre_intento_bajo, json_esperado_path)
                    logrado_con_exito = True
                except Exception as e:
                    print(f"   ❌ Error durante el procesamiento de la descarga directa (guion bajo): {e}")

        if not logrado_con_exito:
            print(f"📭 Fin del escaneo diario: El boletín número {siguiente_esperado} no está publicado aún en los servidores de Quilmes.")

    print("\n🏁 Proceso unificado finalizado.")

if __name__ == "__main__":
    main()
