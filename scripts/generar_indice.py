#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
generar_indice.py
----------------
Genera un CSV limpio y consolidado. Agrupa por Archivo/URL.
"""

import json
import csv
import re
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
CHUNKS_DIR = BASE_DIR / "json_chunks"
OUTPUT_CSV = BASE_DIR / "indice_documentos.csv"

def mapear_categoria(ruta_archivo):
    """Mapea la categoría mirando SOLO el nombre del archivo o su carpeta inmediata."""
    # ruta_archivo.name = "lici_part_001.jsonl"
    # ruta_archivo.parent.name = "lici"
    identificador = (ruta_archivo.parent.name + "_" + ruta_archivo.name).lower()
    
    # El orden de los IF importa. Descartamos primero los específicos.
    if "lici" in identificador:
        return "licitaciones"
    elif "taqui" in identificador:
        return "taquigraficas"
    elif "orden" in identificador or "hcd" in identificador:
        return "ordenes"
    elif "bolet" in identificador:
        return "boletines"
    return "otros"

def limpiar_objeto_licitacion(fragmento):
    match = re.search(r'OBJETO:\s*[“"\'«]?([^”"\'»\n\r]+)', fragmento, re.IGNORECASE)
    if match:
        return match.group(1).strip().title()
    return ""

def procesar_fecha(fecha_raw):
    if not fecha_raw:
        return ""
    fecha_str = str(fecha_raw).strip()
    m_iso = re.search(r'(\d{4})-(\d{2})-(\d{2})', fecha_str)
    if m_iso:
        return m_iso.group(0)
    m_lat = re.search(r'(\d{2})/(\d{2})/(\d{4})', fecha_str)
    if m_lat:
        return f"{m_lat.group(3)}-{m_lat.group(2)}-{m_lat.group(1)}"
    return ""

def generar_indice():
    print("[INFO] Iniciando compilación de índice CSV corregido...")
    
    if not CHUNKS_DIR.exists():
        print("[⚠️] No existe json_chunks. Saliendo.")
        return

    archivos_jsonl = list(CHUNKS_DIR.rglob("*.jsonl"))
    documentos_unicos = {}

    for ruta_archivo in archivos_jsonl:
        categoria = mapear_categoria(ruta_archivo)
        
        try:
            with open(ruta_archivo, 'r', encoding='utf-8') as f:
                for linea in f:
                    linea = linea.strip()
                    if not linea: continue
                        
                    try:
                        chunk = json.loads(linea)
                        
                        url = chunk.get("url") or chunk.get("URL") or ""
                        url = url.strip()
                        
                        archivo_pdf = chunk.get("archivo") or chunk.get("Archivo") or ""
                        archivo_pdf = archivo_pdf.strip()
                        
                        # CLAVE ÚNICA REAL: Priorizamos el archivo PDF físico, si no, la URL.
                        # Esto asegura que todas las páginas del mismo PDF caigan en la misma fila.
                        clave = archivo_pdf if archivo_pdf else url
                        if not clave:
                            continue # Si no tiene nombre ni url, es un fragmento corrupto, se descarta.
                            
                        # Calcular páginas
                        try:
                            paginas = int(chunk.get("pagina") or chunk.get("pag") or 1)
                        except:
                            paginas = 1
                            
                        # Extraer fecha
                        fecha_final = ""
                        if categoria == "licitaciones":
                            texto_analisis = url + " " + archivo_pdf
                            match_lici = re.search(r'(\d{3})(\d{2})\d', texto_analisis)
                            if match_lici:
                                fecha_final = f"20{match_lici.group(2)}-01-01"
                            else:
                                fecha_final = "2025-01-01"
                        else:
                            fecha_chunk = chunk.get("fecha") or chunk.get("Fecha") or chunk.get("procesado") or ""
                            fecha_final = procesar_fecha(fecha_chunk)
                            if not fecha_final:
                                match_texto = re.search(r'(\d{4})(\d{2})(\d{2})', url + " " + archivo_pdf)
                                if match_texto:
                                    fecha_final = f"{match_texto.group(1)}-{match_texto.group(2)}-{match_texto.group(3)}"

                        # Objeto Licitación
                        info_objeto = limpiar_objeto_licitacion(chunk.get("fragmento", "")) if categoria == "licitaciones" else ""

                        # Agrupamiento
                        if clave not in documentos_unicos:
                            documentos_unicos[clave] = {
                                "categoria": categoria,
                                "url": url,
                                "fecha": fecha_final,
                                "info": info_objeto,
                                "paginas": paginas
                            }
                        else:
                            # Si ya existe, nos quedamos con el número de página más alto
                            documentos_unicos[clave]["paginas"] = max(documentos_unicos[clave]["paginas"], paginas)
                            
                            # Si no tenía URL pero este chunk sí lo tiene, lo guardamos
                            if not documentos_unicos[clave]["url"] and url:
                                documentos_unicos[clave]["url"] = url
                                
                            # Lo mismo para la información de la licitación
                            if not documentos_unicos[clave]["info"] and info_objeto:
                                documentos_unicos[clave]["info"] = info_objeto

                    except json.JSONDecodeError:
                        continue
        except Exception as e:
            print(f"[⚠️] Error al leer {ruta_archivo.name}: {e}")

    columnas = ["categoria", "url", "fecha", "info", "paginas"]
    try:
        with open(OUTPUT_CSV, 'w', encoding='utf-8', newline='') as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=columnas)
            writer.writeheader()
            
            documentos_ordenados = sorted(
                documentos_unicos.values(),
                key=lambda x: x.get("fecha", ""),
                reverse=True
            )
            for doc in documentos_ordenados:
                writer.writerow(doc)
                
        print(f"[✅] CSV generado. Se agruparon correctamente en {len(documentos_ordenados)} documentos únicos.")
    except Exception as e:
        print(f"[❌] Error escribiendo CSV: {e}")

if __name__ == "__main__":
    generar_indice()
