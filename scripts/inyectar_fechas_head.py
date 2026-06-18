import os
import json
from pathlib import Path

# Directorio estricto de boletines
JSON_BOLET_DIR = Path("json_chunks/bolet")

def limpiar_fechas_boletines():
    if not JSON_BOLET_DIR.exists():
        print(f"❌ Error: No se encontró la carpeta de boletines en {JSON_BOLET_DIR}")
        return

    print("=== Iniciando limpieza: Eliminando campo 'fecha' de Boletines ===")
    
    for ruta_archivo in JSON_BOLET_DIR.glob("*.jsonl"):
        lineas_modificadas = []
        cambios = False
        
        with open(ruta_archivo, "r", encoding="utf-8") as f:
            for linea in f:
                if not linea.strip():
                    continue
                chunk = json.loads(linea)
                
                # Si el chunk contiene la clave "fecha", la removemos
                if "fecha" in chunk:
                    del chunk["fecha"]
                    cambios = True
                
                lineas_modificadas.append(json.dumps(chunk, ensure_ascii=False) + "\n")
        
        if cambios:
            with open(ruta_archivo, "w", encoding="utf-8") as f:
                f.writelines(lineas_modificadas)
            print(f"  [🧹] Limpiado: {ruta_archivo.name}")

if __name__ == "__main__":
    limpiar_fechas_boletines()
    print("=== Proceso finalizado. Boletines restaurados ===")
