# procesar_boletin.py
import os
import re
import json
import requests
import fitz  # PyMuPDF
from pathlib import Path

print("🚀 Iniciando Sistema Unificado de Boletines...")

CHUNKS_DIR = Path("json_chunks")
CHUNKS_DIR.mkdir(exist_ok=True)

DOMINIO_BASE = "https://quilmes.gov.ar"
PAGINA_BOLETINES = "https://quilmes.gov.ar"
CHUNK_SIZE = 1200

def get_latest_boletin_number():
    archivos = os.listdir(CHUNKS_DIR)
    numeros = [
        int(re.search(r'boletines_part_(\d+)\.jsonl', f).group(1))
        for f in archivos if re.match(r'boletines_part_\d+\.jsonl', f)
    ]
    return max(numeros) if numeros else 500

def generar_id(nombre, pagina):
    return f"{nombre}_{pagina}"

def procesar_y_guardar_pdf(full_url, nombre_pdf, numero_boletin):
    json_nombre = f"boletines_part_{numero_boletin}.jsonl"
    json_path = CHUNKS_DIR / json_nombre
    
    print(f"   📥 Descargando desde: {full_url}")
    r = requests.get(full_url)
    r.raise_for_status()
    
    temp_path = "temp.pdf"
    with open(temp_path, "wb") as f:
        f.write(r.content)

    print(f"   📄 Extrayendo texto y guardando en {json_nombre}...")
    doc = fitz.open(temp_path)
    paginas_procesadas = 0
    
    with open(json_path, "w", encoding="utf8") as out:
        for page_num, page in enumerate(doc):
            texto = page.get_text().strip()
            if texto:
                fragmento = {
                    "id": generar_id(nombre_pdf, page_num),
                    "archivo": nombre_pdf,
                    "pagina": page_num + 1,
                    "fragmento": texto
                }
                out.write(json.dumps(fragmento, ensure_ascii=False) + "\n")
                paginas_procesadas += 1
                
    doc.close()
    os.remove(temp_path)
    print(f"   ✅ ÉXITO: {json_nombre} guardado ({paginas_procesadas} páginas).")

def main():
    # --- FASE 1: AUDITORÍA DE LA WEB OFICIAL (Historial y enlaces del pasado) ---
    print(f"\n🌐 [FASE 1] Escaneando listado oficial: {PAGINA_BOLETINES}")
    try:
        html = requests.get(PAGINA_BOLETINES).text
    except Exception as e:
        print(f"❌ Error al conectar a la web oficial: {e}")
        html = ""

    # Captura boletines tanto con guion medio como con guion bajo
    urls_encontradas = re.findall(r'href="(.*?boletin[-_]\d+\.pdf)"', html)
    urls_encontradas = sorted(set(urls_encontradas))
    print(f"🔎 Se detectaron {len(urls_encontradas)} enlaces de boletines en la web.")

    boletines_procesados_esta_vez = 0

    for pdf_url in urls_encontradas:
        nombre = pdf_url.split("/")[-1]
        match = re.search(r"boletin[-_](\d+)", nombre)
        if not match:
            continue
            
        numero = int(match.group(1))
        json_path = CHUNKS_DIR / f"boletines_part_{numero}.jsonl"
        
        if json_path.exists():
            continue

        print(f"▶️ NUEVO HISTÓRICO DETECTADO: Boletín {numero}")
        try:
            # Reconstrucción de URL relativa si es necesario
            if pdf_url.startswith("..") or pdf_url.startswith("/"):
                url_limpia = pdf_url.lstrip(".")
                if not url_limpia.startswith("/"):
                    url_limpia = "/" + url_limpia
                full_url = f"{DOMINIO_BASE}{url_limpia}"
            elif not pdf_url.startswith("http"):
                full_url = f"{DOMINIO_BASE}/pdf/boletines/{nombre}"
            else:
                full_url = pdf_url

            procesar_y_guardar_pdf(full_url, nombre, numero)
            boletines_procesados_esta_vez += 1
        except Exception as e:
            print(f"   ❌ Error procesando {nombre}: {e}")

    # --- FASE 2: BÚSQUEDA PROACTIVA DEL BOLETÍN DIARIO (Siguiente número) ---
    print("\n🔍 [FASE 2] Buscando actualización del boletín diario...")
    ultimo = get_latest_boletin_number()
    siguiente = ultimo + 1
    json_siguiente_path = CHUNKS_DIR / f"boletines_part_{siguiente}.jsonl"

    if json_siguiente_path.exists():
        print(f"El boletín diario esperado ({siguiente}) ya se encuentra procesado.")
    else:
        print(f"El último número registrado en chunks es {ultimo}. Buscando el esperado {siguiente}...")
        
        # Intentamos buscar de forma proactiva con guion medio
        url_intento_medio = f"{DOMINIO_BASE}/pdf/boletines/boletin-{siguiente}.pdf"
        nombre_intento_medio = f"boletin-{siguiente}.pdf"
        
        # Intentamos buscar de forma proactiva con guion bajo
        url_intento_bajo = f"{DOMINIO_BASE}/pdf/boletines/boletin_{siguiente}.pdf"
        nombre_intento_bajo = f"boletin_{siguiente}.pdf"
        
        exito_diario = False
        
        # Probar primero con guion medio
        print(f"   Tentando descarga directa: {url_intento_medio}")
        r = requests.head(url_guion := url_intento_medio)
        if r.status_code == 200:
            try:
                procesar_y_guardar_pdf(url_intento_medio, nombre_intento_medio, siguiente)
                exito_diario = True
            except Exception as e:
                print(f"   ❌ Error en descarga directa con guion medio: {e}")
                
        # Si falló, probar con guion bajo
        if not exito_diario:
            print(f"   No encontrado con guion medio. Tentando descarga directa: {url_intento_bajo}")
            r = requests.head(url_intento_bajo)
            if r.status_code == 200:
                try:
                    procesar_y_guardar_pdf(url_intento_bajo, nombre_intento_bajo, siguiente)
                    exito_diario = True
                except Exception as e:
                    print(f"   ❌ Error en descarga directa con guion bajo: {e}")
                    
        if not exito_diario:
            print(f"📭 Fin de búsqueda: El boletín oficial {siguiente} aún no está disponible en el servidor remoto.")

    print("\n🏁 Proceso unificado finalizado.")

if __name__ == "__main__":
    main()
