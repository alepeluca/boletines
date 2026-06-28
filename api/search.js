# api/search.py
from http.server import BaseHTTPRequestHandler
import json
import os
import re
from urllib.parse import urlparse, parse_qs

class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        # 1. Capturar parámetros de la UI
        parsed_url = urlparse(self.path)
        query_params = parse_qs(parsed_url.query)
        
        query_term = query_params.get("q", [""])[0].strip().lower()
        categories_str = query_params.get("categories", [""])[0]
        search_type = query_params.get("searchType", ["contains"])[0]
        desde_val = query_params.get("desde", ["00000000"])[0][:8].ljust(8, "0")
        hasta_val = query_params.get("hasta", ["99999999"])[0][:8].ljust(8, "9")
        orden = query_params.get("orden", ["desc"])[0]
        
        active_categories = [c.strip() for c in categories_str.split(",") if c.strip()]
        resultados = []

        # Configuración de carpetas físicas de chunks en el repositorio
        CONFIG_FOLDERS = {
            "boletines": "json_chunks/bolet",
            "licitaciones": "json_chunks/lici",
            "hcd_orden": "json_chunks/orden",
            "hcd_taqui": "json_chunks/taqui"
        }

        # Auxiliar para normalizar y extraer fechas válidas
        def extraer_sortable_date(item, cat):
            archivo = item.get("archivo", "")
            # Si el item ya trae campo fecha
            if "fecha" in item and item["fecha"]:
                raw = item["fecha"].replace("-", "")
                m = re.search(r'\b(19[89]\d|20[0123]\d)([01]\d)([0-3]\d)\b', raw)
                if m: return m.group(1) + m.group(2) + m.group(3), f"{m.group(3)}/{m.group(2)}/{m.group(1)}"
            
            # Fallback por nombre de archivo (Boletines: YYYYMMDD...)
            m_year = re.search(r'\b(19[89]\d|20[0123]\d)\b', archivo)
            if m_year:
                if cat == "boletines" and len(archivo) >= 8 and archivo[:8].isdigit():
                    return archivo[:8], f"{archivo[6:8]}/{archivo[4:6]}/{archivo[:4]}"
                return m_year.group(1) + "0101", f"Año {m_year.group(1)}"
            
            return "19000101", "S/F"

        # 2. Iterar sobre las carpetas de las categorías seleccionadas
        for cat_key in active_categories:
            folder_relative = CONFIG_FOLDERS.get(cat_key)
            if not folder_relative:
                continue
                
            folder_path = os.path.join(os.getcwd(), folder_relative)
            if not os.path.exists(folder_path):
                continue

            # Escanear todos los archivos .jsonl en la carpeta de la categoría
            for file_name in sorted(os.listdir(folder_path)):
                if not file_name.endswith(".jsonl"):
                    continue
                    
                file_path = os.path.join(folder_path, file_name)
                
                # Leer renglón por renglón el chunk
                with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                    for line in f:
                        line = line.strip()
                        if not line:
                            continue
                        try:
                            item = json.loads(line)
                            
                            # Extraer campos de texto a buscar
                            fragmento = item.get("fragmento", "")
                            objeto = item.get("objeto", item.get("extra_info", ""))
                            archivo_text = item.get("archivo", "")
                            target_text = f"{fragmento} {objeto} {archivo_text}".lower()
                            
                            # Filtro de búsqueda por texto
                            match_found = False
                            if not query_term:
                                match_found = True
                            elif search_type == "contains" and query_term in target_text:
                                match_found = True
                            elif search_type == "endsWith" and target_text.endswith(query_term):
                                match_found = True
                            elif search_type == "or":
                                words = [w.strip() for w in query_term.split("|") if w.strip()]
                                if any(w in target_text for w in words):
                                    # Asegurarse de compilar las palabras en un regex seguro
                                    match_found = True

                            if not match_found:
                                continue

                            # Filtro de Rangos de Fechas usando chunks
                            sortable_date, display_date = extraer_sortable_date(item, cat_key)
                            if not (desde_val <= sortable_date <= hasta_val):
                                continue

                            # Estructurar resultado unificado para la interfaz
                            resultados.append({
                                "categoria": cat_key,
                                "archivo": archivo_text,
                                "url": item.get("url", ""),
                                "fecha": item.get("fecha", ""),
                                "fragmento": fragmento if fragmento else objeto,
                                "pagina": str(item.get("pagina", "1")),
                                "datosFecha": {
                                    "sortable": sortable_date,
                                    "display": display_date
                                }
                            })
                        except Exception:
                            continue # Ignorar líneas corruptas del JSONL

        # 3. Ordenar dinámicamente los aciertos de los chunks
        resultados.sort(key=lambda x: x["datosFecha"]["sortable"], reverse=(orden == "desc"))

        # 4. Enviar JSON al Front
        self.send_response(200)
        self.send_header("Content-type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(json.dumps(resultados).encode("utf-8"))
        return
