#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import json
import csv
import re
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
CHUNKS_DIR = BASE_DIR / "json_chunks"
OUTPUT_CSV = BASE_DIR / "indice_documentos.csv"

def mapear_categoria(ruta_archivo):
    partes = ruta_archivo.parts
    if "bolet" in partes or "boletines" in ruta_archivo.name:
        return "boletines"
    elif "lici" in partes or "lici" in ruta_archivo.name:
        return "licitaciones"
    elif "taqui" in partes or "taqui" in ruta_archivo.name:
        return "taquigraficas"
    elif "orden" in partes or "orden" in ruta_archivo.name:
        return "ordenes"
    return "otros"

def extraer_fecha(texto, fragmento="", predeterminado=""):
    match_nombre = re.search(r'(\d{4})(\d{2})(\d{2})', texto)
    if match_nombre:
        return f"{match_nombre.group(1)}-{match_nombre.group(2)}-{match_nombre.group(3)}"
    
    match_fragmento = re.search(r'(\d{2})/(\d{2})/(\d{4})', fragmento)
    if match_fragmento:
        return f"{match_fragmento.group(3)}-{match_fragmento.group(2)}-{match_fragmento.group(1)}"
        
    return predeterminado

def limpiar_objeto_licitacion(fragmento):
    # Captura todo el texto continuo del objeto limpiando las comillas
    match = re.search(r'OBJETO:\s*[“"\'«]?([^”"\'»\n\r]+)', fragmento, re.IGNORECASE)
    if match:
        return match.group(1).strip().title()
    return ""

def generar_indice():
    print("[INFO] Iniciando la compilación del índice de documentos...")
    documentos_unicos = {}
    archivos_jsonl = list(CHUNKS_DIR.glob("**/*.jsonl"))
    
    for ruta_archivo in archivos_jsonl:
        categoria = mapear_categoria(ruta_archivo)
        
        try:
            with open(ruta_archivo, 'r', encoding='utf-8') as f:
                for linea in f:
                    linea = linea.strip()
                    if not linea:
                        continue
                    
                    try:
                        chunk = json.loads(linea)
                        url = chunk.get("url", "").strip()
                        archivo_pdf = chunk.get("archivo", "").strip()
                        
                        clave = url if url else archivo_pdf
                        if not clave:
                            continue
                            
                        fragmento = chunk.get("fragmento", "")
                        
                        if clave not in documentos_unicos:
                            fecha = extraer_fecha(archivo_pdf, fragmento, predeterminado=chunk.get("procesado", "")[:10])
                            resumen_objeto = ""
                            if categoria == "licitaciones":
                                resumen_objeto = limpiar_objeto_licitacion(fragmento)
                            
                            documentos_unicos[clave] = {
                                "categoria": categoria,
                                "archivo": archivo_pdf,
                                "url": url,
                                "fecha": fecha,
                                "extra_info": resumen_objeto,
                                "paginas": 1
                            }
                        else:
                            documentos_unicos[clave]["paginas"] = max(documentos_unicos[clave]["paginas"], chunk.get("pagina", 1))
                            if documentos_unicos[clave]["categoria"] == "licitaciones" and not documentos_unicos[clave]["extra_info"]:
                                documentos_unicos[clave]["extra_info"] = limpiar_objeto_licitacion(fragmento)
                                
                    except json.JSONDecodeError:
                        continue
        except Exception as e:
            print(f"[⚠️] Error al procesar el archivo {ruta_archivo.name}: {e}")

    columnas = ["categoria", "archivo", "url", "fecha", "extra_info", "paginas"]
    
    try:
        with open(OUTPUT_CSV, 'w', encoding='utf-8', newline='') as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=columnas)
            writer.writeheader()
            
            documentos_ordenados = sorted(
                documentos_unicos.values(), 
                key=lambda x: x["fecha"], 
                reverse=True
            )
            
            for doc in documentos_ordenados:
                writer.writerow(doc)
                
        print(f"[✅] ¡Índice CSV creado con éxito! Total de documentos: {len(documentos_ordenados)}")
        
    except Exception as e:
        print(f"[❌] Error crítico al escribir el archivo CSV: {e}")

if __name__ == "__main__":
    generar_indice()
