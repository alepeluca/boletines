import os
import re

def normalizar_nombres_lici(directorio="json_chunks"):
    if not os.path.exists(directorio):
        print(f"Error: La carpeta '{directorio}' no existe.")
        return

    # Captura lici_part seguido de los números iniciales y descarta el resto
    patron = re.compile(r'^lici_part(\d+)(.*)\.jsonl$', re.IGNORECASE)
    
    archivos = os.listdir(directorio)
    contador = 0

    print("Iniciando normalización a 4 dígitos (NNNN)...")

    for nombre_archivo in archivos:
        match = patron.match(nombre_archivo)
        if match:
            numero_str = match.group(1)
            numero_int = int(numero_str)
            
            # Forzamos 4 dígitos con ceros a la izquierda (ej: '0196')
            numero_normalizado = str(numero_int).zfill(4)
            nuevo_nombre = f"lici_part{numero_normalizado}.jsonl"
            
            ruta_antigua = os.path.join(directorio, nombre_archivo)
            ruta_nueva = os.path.join(directorio, nuevo_nombre)
            
            if nombre_archivo != nuevo_nombre:
                try:
                    os.rename(ruta_antigua, ruta_nueva)
                    print(f"Renombrado: {nombre_archivo}  ==>  {nuevo_nombre}")
                    contador += 1
                except Exception as e:
                    print(f"Error al renombrar {nombre_archivo}: {e}")

    print(f"\n¡Proceso terminado! Se normalizaron {contador} archivos a formato NNNN.")

if __name__ == "__main__":
    normalizar_nombres_lici()
