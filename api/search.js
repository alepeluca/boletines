# api/search.py
from http.server import BaseHTTPRequestHandler
import json
import csv
import os
import re
from urllib.parse import urlparse, parse_qs

class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        # 1. Parsear parámetros de consulta enviados por la UI
        parsed_url = urlparse(self.path)
        query_params = parse_qs(parsed_url.query)
        
        query_term = query_params.get("q", [""])[0].strip()
        categories_str = query_params.get("categories", [""])[0]
        search_type = query_params.get("searchType", ["contains"])[0]
        desde_val = query_params.get("desde", ["00000000"])[0]  # Formato YYYYMMDD o aproximado
        hasta_val = query_params.get("hasta", ["99999999"])[0]
        orden = query_params.get("orden", ["desc"])[0]
        
        active_categories = [c.strip() for c in categories_str.split(",") if c.strip()]
        
        resultados = []
        
        # 2. Localizar y parsear el archivo indice_documentos.csv en la raíz del deploy
        # Vercel clona el repositorio, por lo que el CSV está accesible de forma relativa
        csv_path = os.path.join(os.getcwd(), "indice_documentos.csv")
        
        if os.path.exists(csv_path):
            with open(csv_path, mode="r", encoding="utf-8") as f:
                # El parser de Python maneja de forma nativa los fragmentos que contienen comillas y comas
                reader = csv.DictReader(f)
                
                for row in reader:
                    # Filtro de Categoría
                    cat = row.get("categoria", "").lower()
                    # Mapeos por si el script difiere sutilmente en los nombres
                    if "bolet" in cat: cat_key = "boletines"
                    elif "lici" in cat: cat_key = "licitaciones"
                    elif "orden" in cat: cat_key = "hcd_orden"
                    elif "taqui" in cat: cat_key = "hcd_taqui"
                    else: cat_key = cat
                    
                    if active_categories and (cat_key not in active_categories):
                        continue
                    
                    # Normalización y extracción de la fecha para el ordenamiento dinámico
                    raw_fecha = row.get("fecha", "").replace("-", "")
                    match_std = re.search(r'\b(19[89]\d|20[0123]\d)([01]\d)([0-3]\d)\b', raw_fecha)
                    
                    if match_std:
                        sortable_date = match_std.group(1) + match_std.group(2) + match_std.group(3)
                        display_date = f"{match_std.group(3)}/{match_std.group(2)}/{match_std.group(1)}"
                    else:
                        # Fallback si no tiene fecha exacta pero contiene un año en el archivo/texto
                        match_year = re.search(r'\b(19[89]\d|20[0123]\d)\b', row.get("archivo", "") + " " + row.get("extra_info", ""))
                        if match_year:
                            sortable_date = match_year.group(1) + "0101"
                            display_date = f"Año {match_year.group(1)}"
                        else:
                            sortable_date = "19000101"
                            display_date = "S/F"
                    
                    # Filtro de Rango de Fechas
                    # Ajustamos los parámetros desde/hasta para hacer comparación de strings limpia de 8 dígitos
                    cmp_desde = desde_val[:8].ljust(8, "0")
                    cmp_hasta = hasta_val[:8].ljust(8, "9")
                    if not (cmp_desde <= sortable_date <= cmp_hasta):
                        continue
                    
                    # Campo de texto objetivo para la búsqueda textual profunda
                    fragmento = row.get("fragmento", "")
                    extra_info = row.get("extra_info", "")
                    target_text = (fragmento + " " + extra_info + " " + row.get("archivo", "")).lower()
                    term_lower = query_term.lower()
                    
                    # Filtro del Tipo de Búsqueda Textual
                    match_found = False
                    if not query_term:
                        match_found = True
                    elif search_type == "contains" and term_lower in target_text:
                        match_found = True
                    elif search_type == "endsWith" and target_text.endswith(term_lower):
                        match_found = True
                    elif search_type == "or":
                        words = [w.strip().lower() for w in query_term.split("|") if w.strip()]
                        if any(w in target_text for w in words):
                            match_found = True
                            
                    if match_found:
                        # Estructurar respuesta compatible con el renderizador del Front-End
                        resultados.append({
                            "categoria": cat_key,
                            "archivo": row.get("archivo", ""),
                            "url": row.get("url", ""),
                            "fecha": row.get("fecha", ""),
                            "fragmento": fragmento if fragmento else extra_info,
                            "pagina": row.get("pagina", "1"),
                            "datosFecha": {
                                "sortable": sortable_date,
                                "display": display_date
                            }
                        })
            
            # 3. Ordenamiento cronológico dinámico solicitado por el selector
            is_descending = (orden == "desc")
            resultados.sort(key=lambda x: x["datosFecha"]["sortable"], reverse=is_descending)
            
        # 4. Responder la petición HTTP en formato JSON
        self.send_response(200)
        self.send_header("Content-type", "application/json")
        # Habilitar CORS para pruebas locales cruzadas
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        
        self.wfile.write(json.dumps(resultados).encode("utf-8"))
        return
