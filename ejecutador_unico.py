import re
# =========================================================
# MAIN
# =========================================================


def main():

    existentes = obtener_numeros_existentes()

    print(f"📚 Boletines ya descargados: {len(existentes)}")

    print(f"🌐 Escaneando: {PAGINA_BOLETINES}")

    try:

        html = descargar_html(PAGINA_BOLETINES)

    except Exception as e:

        print(f"❌ Error descargando HTML: {e}")
        return

    pdfs = extraer_pdfs(html)

    print(f"🔎 PDFs encontrados: {len(pdfs)}")

    nuevos = 0

    for pdf_url, numero in pdfs:

        if numero in existentes:
            continue

        print(
            f"▶️ NUEVO HISTÓRICO DETECTADO: "
            f"Boletín {numero}"
        )

        try:

            nombre = pdf_url.split("/")[-1]

            full_url = reconstruir_url(pdf_url, nombre)

            procesar_pdf_a_jsonl(full_url, numero)

            nuevos += 1

        except Exception as e:

            print(f"❌ Error procesando boletín {numero}: {e}")

    print()
    print(f"✅ Nuevos boletines descargados: {nuevos}")
    print("🏁 Proceso finalizado")


if __name__ == "__main__":
    main()
