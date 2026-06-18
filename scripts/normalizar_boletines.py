import json
import glob
from pathlib import Path

def main():
    input_dir = Path('json_chunks/bolet')
    output_dir = Path('json_chunks/bolet_normalizado')
    
    # Creamos la carpeta de salida (si no existe) para no pisar la original
    output_dir.mkdir(parents=True, exist_ok=True)

    # Diccionario para agrupar fragmentos por archivo
    # Clave: nombre del archivo (ej. '20080901 - boletin-72.pdf')
    # Valor: lista de diccionarios (los chunks de ese PDF)
    documentos = {}

    archivos_jsonl = glob.glob(f'{input_dir}/*.jsonl')
    
    print(f"[INFO] Leyendo {len(archivos_jsonl)} archivos originales de boletines...")

    # PASO 1: Leer y agrupar todo por PDF
    for ruta_archivo in archivos_jsonl:
        with open(ruta_archivo, 'r', encoding='utf-8') as f:
            for linea in f:
                if not linea.strip():
                    continue
                try:
                    data = json.loads(linea)
                    # Usamos el campo 'archivo' como identificador único
                    nombre_archivo = data.get('archivo')
                    
                    # Fallback por si en algún chunk muy viejo solo se llamaba 'codigo'
                    if not nombre_archivo:
                        nombre_archivo = data.get('codigo', 'desconocido') + ".pdf"

                    if nombre_archivo not in documentos:
                        documentos[nombre_archivo] = []
                        
                    documentos[nombre_archivo].append(data)
                except json.JSONDecodeError:
                    print(f"[ERROR] Línea corrupta ignorada en: {ruta_archivo}")
                    continue
    
    cantidad_unicos = len(documentos)
    print(f"[INFO] Se detectaron {cantidad_unicos} boletines únicos. Normalizando...")

    # PASO 2: Ordenar cronológicamente (alfa-numérico por el YYYYMMDD)
    nombres_ordenados = sorted(documentos.keys())

    # PASO 3: Guardar 1 archivo por boletín con índice secuencial de 4 dígitos
    for index, nombre_archivo in enumerate(nombres_ordenados, start=1):
        nuevo_nombre_chunk = f"bolet_part_{index:04d}.jsonl"
        ruta_salida = output_dir / nuevo_nombre_chunk
        
        # Nos aseguramos de que las páginas estén ordenadas dentro del chunk
        fragmentos = documentos[nombre_archivo]
        fragmentos_ordenados = sorted(fragmentos, key=lambda x: x.get('pagina', 0))

        with open(ruta_salida, 'w', encoding='utf-8') as f:
            for frag in fragmentos_ordenados:
                f.write(json.dumps(frag, ensure_ascii=False) + '\n')

    print(f"\n✅ ¡Éxito! Se crearon {cantidad_unicos} archivos JSONL perfectamente separados.")
    print(f"📁 Revisa la carpeta: '{output_dir}'.")
    print("👉 Si todo está bien, borra la vieja carpeta 'bolet' y renombra 'bolet_normalizado' a 'bolet'.")

if __name__ == '__main__':
    main()
