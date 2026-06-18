#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
generar_indice.py
----------------
Compilador optimizado de índices JSONL a un CSV unificado para el Front-End.
Columnas finales: categoria, url, fecha, info, paginas
"""

import json
import csv
import re
from pathlib import Path

# Configuración de rutas
BASE_DIR = Path(__file__).resolve().parent.parent
CHUNKS_DIR = BASE_DIR / "json_chunks"
OUTPUT_CSV = BASE_DIR / "indice_documentos.csv"

def mapear_categoria(ruta_archivo):
    """Mapea con precisión la categoría según la subcarpeta o nombre del archivo."""
    ruta_str = str(ruta_archivo).lower()
    if "bolet" in ruta_str:
        return "boletines"
    elif "lici" in ruta_str:
        return "licitaciones"
    elif "taqui" in ruta_str:
        return "taquigraficas"
    elif "orden" in ruta_str or "hcd" in ruta_str:
        return "ordenes"
    return "otros"

def limpiar_objeto_licitacion(fragmento):
    """Extrae el objeto de la licitación sin el prefijo y en formato legible."""
    match = re.search(r'OBJETO:\s*[“"\'«]?([^”"\'»\n\r]+)', fragmento, re.IGNORECASE)
    if match:
        return match.group(1).strip().title()
    return ""

def procesar_fecha(fecha_raw):
    """Normaliza cualquier formato de fecha a YYYY-MM-DD."""
    if not fecha_raw:
        return ""
    fecha_str = str(fecha_raw).strip()
    
    # Intenta detectar formato ISO (YYYY-MM-DD)
    m_iso = re.search(r'(\d{4})-(\d{2})-(\d{2})', fecha_str)
    if m_iso:
        return m_iso.group(0)
        
    # Intenta detectar formato Latino (DD/MM/YYYY)
    m_lat = re.search(r'(\d{2})/(\d{2})/(\d{4})', fecha_str)
    if m_lat:
        return f"{m_lat.group(3)}-{m_lat.group(2)}-{m_lat.group(1)}"
        
    return ""

def generar_indice():
    print("[INFO] Iniciando la compilación del índice corregido...")
    
    # Asegurar que las carpetas existan por las dudas
    if not CHUNKS_DIR.exists():
        CHUNKS_DIR.mkdir(parents=True, exist_ok=True)
        for sub in ["bolet", "lici", "taqui", "orden"]:
            (CHUNKS_DIR / sub).mkdir(exist_ok=True)

    # Buscamos todos los archivos .jsonl recursivamente
    archivos_jsonl = list(CHUNKS_DIR.rglob("*.jsonl"))
    
    if not archivos_jsonl:
        print("[⚠️] No se encontraron archivos .jsonl en json_chunks/. Generando CSV vacío.")
        columnas = ["categoria", "url", "fecha", "info", "paginas"]
        with open(OUTPUT_CSV, 'w', encoding='utf-8', newline='') as csvfile:
            csv.DictWriter(csvfile, fieldnames=columnas).writeheader()
        return

    documentos_unicos = {}

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
                        
                        # Extraer URL nativa desde adentro del chunk
                        url = chunk.get("url") or chunk.get("URL") or chunk.get("link") or ""
                        url = url.strip()
                        
                        # Extraer datos de página
                        pag = chunk.get("pagina") or chunk.get("pag") or 1
                        try:
                            paginas = int(pag)
                        except:
                            paginas = 1
                            
                        fragmento = chunk.get("fragmento", "")
                        
                        # --- LÓGICA DE FECHAS SEGÚN CATEGORÍA ---
                        fecha_final = ""
                        
                        if categoria == "licitaciones":
                            # Regla: Tomar el año del código de 6 dígitos en la URL o archivo (ej: 052250 -> 25)
                            texto_analisis = url + " " + chunk.get("archivo", "")
                            match_lici = re.search(r'(\d{3})(\d{2})\d', texto_analisis)
                            if match_lici:
                                ano_2d = match_lici.group(2) # Extrae el '25' o '23'
                                fecha_final = f"20{ano_2d}-01-01"
                            else:
                                fecha_final = "2025-01-01" # Fallback preventivo para licitaciones
                                
                        else:
                            # Boletines, Taquigráficas y Órdenes: Tienen la fecha exacta adentro
                            fecha_chunk = chunk.get("fecha") or chunk.get("Fecha") or chunk.get("procesado") or ""
                            fecha_final = procesar_fecha(fecha_chunk)
                            
                            # Si de última no vino fecha interna, buscamos YYYYMMDD en el texto
                            if not fecha_final:
                                match_texto = re.search(r'(\d{4})(\d{2})(\d{2})', url + " " + chunk.get("archivo", ""))
                                if match_texto:
                                    fecha_final = f"{match_texto.group(1)}-{match_texto.group(2)}-{match_texto.group(3)}"
                                else:
                                    fecha_final = "2026-01-01" # Fallback general si está en blanco

                        # --- CONSOLIDACIÓN POR DOCUMENTO ÚNICO ---
                        # Usamos la URL como clave única para unificar partes
                        clave = url if url else f"sin_url_{categoria}_{fecha_final}_{hash(fragmento[:30])}"
                        
                        info_objeto = limpiar_objeto_licitacion(fragmento) if categoria == "licitaciones" else ""

                        if clave not in documentos_unicos:
                            documentos_unicos[clave] = {
                                "categoria": categoria,
                                "url": url,
                                "fecha": fecha_final,
                                "info": info_objeto,
                                "paginas": paginas
                            }
                        else:
                            # Si ya existe el documento, actualizamos el máximo de páginas encontradas
                            documentos_unicos[clave]["paginas"] = max(documentos_unicos[clave]["paginas"], paginas)
                            # Si no tenía el Objeto guardado y ahora apareció, lo sumamos
                            if not documentos_unicos[clave]["info"] and info_objeto:
                                documentos_unicos[clave]["info"] = info_objeto

                    except json.JSONDecodeError:
                        continue
        except Exception as e:
            print(f"[⚠️] Error al abrir/procesar {ruta_archivo.name}: {e}")

    # --- ESCRITURA DEL CSV FINAL ---
    columnas = ["categoria", "url", "fecha", "info", "paginas"]
    
    try:
        with open(OUTPUT_CSV, 'w', encoding='utf-8', newline='') as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=columnas)
            writer.writeheader()
            
            # Ordenamos del más reciente al más viejo
            documentos_ordenados = sorted(
                documentos_unicos.values(),
                key=lambda x: x.get("fecha", ""),
                reverse=True
            )
            
            for doc in documentos_ordenados:
                writer.writerow(doc)
                
        print(f"[✅] ¡Índice CSV recreado con éxito! Total de documentos procesados: {len(documentos_ordenados)}")
        
    except Exception as e:
        print(f"[❌] Error crítico escribiendo el CSV: {e}")

if __name__ == "__main__":
    generar_indice()
