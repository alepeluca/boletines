import requests

BASE_URL = "https://quilmes.gov.ar/contrataciones/licpublicas/"

def verificar_url(url):
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    }
    try:
        response = requests.head(url, headers=headers, timeout=8.0)
        return response.status_code == 200
    except requests.RequestException:
        return False

def mapear_licitaciones():
    urls_encontradas = []
    
    for anio_int in range(26, -1, -1):
        anio = f"{anio_int:02d}"
        print(f"\n--- EVALUANDO AÑO: 20{anio} ---")
        
        hubo_licitaciones_en_este_anio = False
        
        for xxx_int in range(1, 1000):
            xxx = f"{xxx_int:03d}"
            encontrado_en_este_numero = False
            
            for z in range(1, 7):
                url = f"{BASE_URL}{xxx}{anio}0-{z}.pdf"
                
                print(f"Probando: {xxx}{anio}0-{z}.pdf ... ", end="", flush=True)
                
                if verificar_url(url):
                    print("¡ENCONTRADO!")
                    urls_encontradas.append(url)
                    encontrado_en_este_numero = True
                    hubo_licitaciones_en_este_anio = True
                else:
                    print("no existe")
                    break
            
            if not encontrado_en_este_numero:
                if xxx == "001":
                    print(f"El pliego 001 de 20{anio} no existe. Saltando de año...")
                    break
                elif hubo_licitaciones_en_este_anio:
                    print(f"Fin de datos para 20{anio}. Saltando de año...")
                    break
            
    print("\n=========================================")
    print("      REPORTE DE URLs ENCONTRADAS        ")
    print("=========================================")
    if urls_encontradas:
        for url_valida in urls_encontradas:
            print(url_valida)
    else:
        print("No se encontró ningún PDF válido.")
    print("=========================================")

if __name__ == "__main__":
    mapear_licitaciones()
