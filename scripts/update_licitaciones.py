#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
update_licitaciones.py — Versión 1.0.0

FLUJO:
1. Detecta el último chunk existente de licitaciones.
2. Lee la última licitación procesada y calcula la siguiente según tu lógica:
   - Recorre años del presente al pasado (26 al 00).
   - Recorre números crecientes (001 al 999).
   - Controla subpliegos Z (1 al 6).
3. Si la variante Z=1 no existe en un número, pasa al número siguiente.
4. Si la variante Z=1 no existe en el número 001 de un año, o si se interrumpe la correlatividad, salta de año.
5. Si existe: descarga el PDF, busca en la pág. 1 la palabra "OBJETO:", extrae 5 palabras en CamelCase,
   y genera un nombre estructurado: LiciPubli_XXXYY0-Z_TextoObjeto.pdf para los fragmentos del chunk.
"""

import json
import os
import re
from pathlib import Path
import fitz
import requests

# =========================================================
# CONFIG
# =========================================================

VERSION = "1.0.0"
FECHA_MODIFICACION = "12-06-2026"

JSON_CHUNKS_DIR = Path("json_chunks")
BASE_URL = "https://quilmes.gov.ar"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0 Safari/537.36"
    )
}

JSON_CHUNKS_DIR.mkdir(exist_ok=True)

print("\n" + "=" * 60)
print(f"🚀 UPDATE LICITACIONES v{VERSION}")
print(f"📅 Última modificación: {FECHA_MODIFICACION}")
print("=" * 60 + "\n")


# =========================================================
# HELPERS
# =========================================================

def find_latest_chunk():
    archivos = []
    for f in JSON_CHUNKS_DIR.glob("licitaciones_part_*.jsonl"):
        match = re.search(r"licitaciones_part_(\d+)\.jsonl", f.name)
        if match:
            archivos.append((int(match.group(1)), f))
    if not archivos:
        return -1, None
    archivos.sort(key=lambda x: x[0])
    return archivos[-1]


def load_last_licitacion_state(chunk_path):
    """
    Retorna el estado de la última licitación del último chunk: (anio_int, xxx_int, z_int, hubo_exito_en_anio)
    Si el chunk está vacío o no hay, inicializa en el punto de partida (año 26, número 1, z 0).
    """
    ultima_linea = None
    if not chunk_path:
        return 26, 1, 0, False

    with open(chunk_path, "r", encoding="utf-8") as f:
        for linea in f:
            linea = linea.strip()
            if linea:
                ultima_linea = linea

    if not ultima_linea:
        return 26, 1, 0, False

    obj = json.loads(ultima_linea)
    archivo_id = obj.get("id", "")
    
    # Extraer el código XXXYY0-Z del ID guardado
    match = re.search(r"LiciPubli_(\d{3})(\d{2})0-(\d)_", archivo_id)
    if not match:
        return 26, 1, 0, False

    xxx_int = int(match.group(1))
    anio_int = int(match.group(2))
    z_int = int(match.group(3))
    
    return anio_int, xxx_int, z_int, True


def verificar_existencia_url(url):
    """Verifica si la URL existe mediante HEAD."""
    try:
        response = requests.head(url, headers=HEADERS, timeout=10)
        return response.status_code == 200
    except requests.RequestException:
        return False


def limpiar_texto_objeto(texto_completo, max_palabras=5):
    """Busca 'OBJETO:' en el texto, toma la línea y extrae N palabras en CamelCase."""
    if "OBJETO:" not in texto_completo:
        return "SinObjeto"
    
    # Extraer el contenido después de OBJETO:
    parte_objeto = texto_completo.split("OBJETO:", 1)[1].strip()
    # Tomar la primera línea significativa
    primera_linea = parte_objeto.split("\n")[0].strip()
    
    # Remover caracteres especiales y quedarse con letras/números
    limpio = re.sub(r'[^\w\s]', '', primera_linea)
    palabras = limpio.split()
    
    # Filtrar y capitalizar para armar CamelCase
    palabras_filtradas = [p for p in palabras if len(p) > 1 or p.lower() in ['de', 'en', 'la', 'lo']]
    palabras_finales = palabras_filtradas[:max_palabras]
    
    if not palabras_finales:
        return "DocumentoLicitacion"
        
    return "".join(p.capitalize() for p in palabras_finales)


def procesar_y_guardar_pdf(url, codigo_completo, chunk_index):
    """Descarga el PDF a memoria temporal, analiza y guarda el nuevo chunk incremental."""
    print(f"[INFO] Descargando pliego: {url}")
    response = requests.get(url, headers=HEADERS, timeout=20)
    response.raise_for_status()

    # Escribir contenido en un archivo temporal para que PyMuPDF lo lea
    with os.fdopen(os.open(os.devnull, os.O_RDWR), 'w') as devnull: # Safe initialization
        pass
        
    with fitz.open(stream=response.content, filetype="pdf") as doc:
        # Obtener texto de la primera página para determinar el Objeto
        texto_p1 = doc[0].get_text() if len(doc) > 0 else ""
        objeto_camel = limpiar_texto_objeto(texto_p1, max_palabras=5)
        
        # Estructura del nombre de archivo requerida por el usuario
        nombre_archivo_virtual = f"LiciPubli_{codigo_completo}_{objeto_camel}.pdf"
        
        frags = []
        for i, page in enumerate(doc, start=1):
            text = page.get_text().strip()
            if not text:
                continue
                
            frags.append({
                "id": f"{nombre_archivo_virtual}_p{i}_f0",
                "archivo": nombre_archivo_virtual,
                "pagina": i,
                "fragmento": text
            })

    if frags:
        salida = JSON_CHUNKS_DIR / f"licitaciones_part_{chunk_index}.jsonl"
        with open(salida, "w", encoding="utf-8") as f:
            for frag in frags:
                f.write(json.dumps(frag, ensure_ascii=False) + "\n")
        print(f"[OK] Chunk generado con éxito: {salida.name} -> {nombre_archivo_virtual}")
        return True
    return False


# =========================================================
# MAIN
# =========================================================

def main():
    last_idx, last_chunk = find_latest_chunk()
    
    # Calcular el estado inicial de búsqueda
    anio_actual, xxx_actual, z_actual, hubo_exito_previo = load_last_licitacion_state(last_chunk)
    
    # Determinar los siguientes índices a probar basados en dónde quedó el último JSONL
    if z_actual > 0 and z_actual < 6:
        # Si quedó a mitad de las variantes Z de una licitación que existía, prueba la siguiente Z
        siguiente_anio = anio_actual
        siguiente_xxx = xxx_actual
        siguiente_z = z_actual + 1
    else:
        # Si terminó las Z o es un proceso nuevo, pasa al siguiente número correlativo XXX
        siguiente_anio = anio_actual
        siguiente_xxx = xxx_actual + 1 if last_chunk else 1
        siguiente_z = 1

    # Iniciar la máquina de estado secuencial e inteligente
    chunk_index_nuevo = last_idx + 1
    
    print(f"[INFO] Último chunk procesado: {last_idx}")
    print(f"[INFO] Buscando próximo elemento a partir de Año: 20{siguiente_anio:02d}, Número: {siguiente_xxx:03d}, Z: {siguiente_z}")

    # Iterar años hacia el pasado
    for anio_int in range(siguiente_anio, -1, -1):
        anio_str = f"{anio_int:02d}"
        
        # Si saltamos de año, el contador XXX se reinicia en 1 y Z en 1
        start_xxx = siguiente_xxx if anio_int == siguiente_anio else 1
        hubo_licitaciones_en_este_anio = hubo_exito_previo if anio_int == suficiente_anio else False
        
        for xxx_int in range(start_xxx, 1000):
            xxx_str = f"{xxx_int:03d}"
            start_z = siguiente_z if (anio_int == siguiente_anio and xxx_int == start_xxx) else 1
            
            encontrado_en_este_numero = False
            
            for z in range(start_z, 7):
                codigo_licitacion = f"{xxx_str}{anio_str}0-{z}"
                url_prueba = f"{BASE_URL}{codigo_licitacion}.pdf"
                
                print(f"Probando: {codigo_licitacion}.pdf ... ", end="", flush=True)
                
                if verificar_existencia_url(url_prueba):
                    print("¡EXISTE!")
                    # Descargar, procesar texto y guardar nuevo chunk incremental
                    exito = procesar_y_guardar_pdf(url_prueba, codigo_licitacion, chunk_index_nuevo)
                    if exito:
                        return # Terminamos la ejecución por hoy (descarga incremental de a 1 archivo)
                else:
                    print("no existe")
                    break # Si no existe la variante, frena el bucle Z
            
            # Control de saltos inteligentes idéntico a tu lógica de consola
            if start_z == 1 and not encontrado_en_este_numero:
                if xxx_str == "001":
                    print(f"[AVISO] Licitación inicial 001 de 20{anio_str} no existe. Saltando de año...")
                    break
                elif hubo_licitaciones_en_este_anio:
                    print(f"[FIN DE PERÍODO] Fin de secuencia correlativa para 20{anio_str}. Saltando de año...")
                    break
                    
        # Resetear el inicio de las XXX si pasamos al año anterior en el bucle externo
        siguiente_z = 1
        siguiente_xxx = 1

    print("[INFO] No se encontraron nuevas licitaciones disponibles para procesar.")

if __name__ == "__main__":
    main()
