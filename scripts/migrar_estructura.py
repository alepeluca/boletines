import os
import re
import shutil

# Rutas origen y destino
BASE_DIR = "json_chunks"
DESTINOS = {
    "bolet": os.path.join(BASE_DIR, "bolet"),
    "lici": os.path.join(BASE_DIR, "lici"),
    "taqui": os.path.join(BASE_DIR, "taqui"),
    "orden": os.path.join(BASE_DIR, "orden")
}

def migrar():
    print("Iniciando reestructuración de chunks...")
    
    # 1. Crear las subcarpetas si no existen
    for carpeta in DESTINOS.values():
        os.makedirs(carpeta, exist_ok=True)
    
    # 2. Leer archivos sueltos en json_chunks/
    if not os.path.exists(BASE_DIR):
        print(f"La carpeta {BASE_DIR} no existe.")
        return

    archivos = [f for f in os.listdir(BASE_DIR) if os.path.isfile(os.path.join(BASE_DIR, f))]
    
    for archivo in archivos:
        ruta_origen = os.path.join(BASE_DIR, archivo)
        nombre_lower = archivo.lower()
        
        # Identificar categoría y definir destino
        if "boletin" in nombre_lower:
            # Corregir secuencial a 4 dígitos (ej: boletines_part_1.jsonl -> boletines_part_0001.jsonl)
            match = re.search(r'(boletines_part_)(\d+)(\.jsonl)', archivo, re.IGNORECASE)
            if match:
                prefijo, numero, sufijo = match.groups()
                nuevo_nombre = f"{prefijo}{int(numero):04d}{sufijo}"
            else:
                nuevo_nombre = archivo
                
            ruta_destino = os.path.join(DESTINOS["bolet"], nuevo_nombre)
            shutil.move(ruta_origen, ruta_destino)
            print(f"Movido y Renombrado: {archivo} -> bolet/{nuevo_nombre}")
            
        elif "lici" in nombre_lower:
            ruta_destino = os.path.join(DESTINOS["lici"], archivo)
            shutil.move(ruta_origen, ruta_destino)
            print(f"Movido: {archivo} -> lici/{archivo}")
            
        elif "taqui" in nombre_lower or "acta" in nombre_lower:
            ruta_destino = os.path.join(DESTINOS["taqui"], archivo)
            shutil.move(ruta_origen, ruta_destino)
            print(f"Movido: {archivo} -> taqui/{archivo}")
            
        elif "orden" in nombre_lower:
            ruta_destino = os.path.join(DESTINOS["orden"], archivo)
            shutil.move(ruta_origen, ruta_destino)
            print(f"Movido: {archivo} -> orden/{archivo}")
            
    print("¡Migración y estandarización completada con éxito!")

if __name__ == "__main__":
    migrar()
