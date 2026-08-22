"""
Lector de kardex desde PDF con texto seleccionable.
Utiliza pdfplumber para extraer texto.
Arquitectura preparada para agregar OCR/pdf escaneado posteriormente.

NO lee imagenes, NO hace OCR, NO modifica archivos.
"""

import os
import re
import pdfplumber
import pandas as pd

COLUMNAS_KARDEX = [
    "nro", "anio", "gestion", "codigo", "nivel", "tp", "md",
    "cv", "gr", "grpr", "t1", "t2", "t3", "p1", "p2",
    "ef", "2da", "mdti", "eg", "nfin", "rfin"
]

COLUMNAS_NO_USADAS = {"t3", "p1", "p2"}

ALIAS_COLUMNAS = {
    "nro": ["nro", "n", "n.", "num", "numero", "#"],
    "anio": ["anio", "año", "a", "year"],
    "gestion": ["gestion", "gest", "gst", "g", "sem", "semestre"],
    "codigo": ["codigo", "cod", "sis", "código", "cod_sis"],
    "nivel": ["nivel", "niv", "nv", "niv."],
    "tp": ["tp"],
    "md": ["md", "modalidad"],
    "cv": ["cv"],
    "gr": ["gr"],
    "grpr": ["grpr"],
    "t1": ["t1"],
    "t2": ["t2"],
    "t3": ["t3"],
    "p1": ["p1"],
    "p2": ["p2"],
    "ef": ["ef", "exfinal", "ex final", "examen final", "final"],
    "2da": ["2da", "segunda", "seg", "2"],
    "mdti": ["mdti", "mdtl", "md ti", "md_ti", "mdTI"],
    "eg": ["eg", "gracia"],
    "nfin": ["nfin", "n final", "nota final", "nf", "nFIN"],
    "rfin": ["rfin", "r final", "resultado final", "resultado", "res", "RFIN"],
}


def extraer_texto_pdf(ruta_pdf):
    texto_paginas = []
    with pdfplumber.open(ruta_pdf) as pdf:
        for i, pagina in enumerate(pdf.pages):
            texto = pagina.extract_text()
            texto_paginas.append({
                "numero_pagina": i + 1,
                "texto": texto,
                "lineas": texto.split("\n") if texto else [],
            })
    return texto_paginas


def extraer_tablas_pdf(ruta_pdf):
    tablas_encontradas = []
    with pdfplumber.open(ruta_pdf) as pdf:
        for i, pagina in enumerate(pdf.pages):
            tables = pagina.extract_tables()
            for j, tabla in enumerate(tables):
                tablas_encontradas.append({
                    "pagina": i + 1,
                    "tabla_index": j,
                    "datos": tabla,
                })
    return tablas_encontradas


def _normalizar_encabezado(texto):
    if texto is None:
        return ""
    return re.sub(r"[^a-z0-9]", "", texto.lower().strip())


def _mapear_columna(nombre_detectado):
    norm = _normalizar_encabezado(nombre_detectado)
    for col_estandar, aliases in ALIAS_COLUMNAS.items():
        if norm == _normalizar_encabezado(col_estandar):
            return col_estandar
        for alias in aliases:
            if norm == _normalizar_encabezado(alias):
                return col_estandar
    return None


def detectar_encabezados(fila):
    if not fila:
        return None, []

    mapeos = []
    for i, celda in enumerate(fila):
        col = _mapear_columna(celda)
        if col:
            mapeos.append((i, col))

    if len(mapeos) < 3:
        return None, []

    columnas = [None] * len(fila)
    for idx, col in mapeos:
        columnas[idx] = col

    return mapeos, columnas


def _convertir_valor(valor, columna):
    if valor is None:
        return None
    valor = str(valor).strip()
    if valor == "" or valor.lower() in ("null", "none", "-", "n/a"):
        return None

    if columna in ("nro", "anio", "gestion", "t1", "t2", "t3",
                    "ef", "2da", "eg", "nfin"):
        try:
            return float(valor)
        except ValueError:
            return valor

    if columna in ("cv", "gr", "grpr"):
        try:
            return float(valor)
        except ValueError:
            return valor

    return valor


def extraer_filas(tabla_datos, mapeos_encabezado):
    if not mapeos_encabezado:
        return [], []

    filas_procesadas = []
    errores = []

    for i, fila in enumerate(tabla_datos):
        if not fila or all(c is None or str(c).strip() == "" for c in fila):
            continue

        es_encabezado = False
        for idx, col in mapeos_encabezado:
            if idx < len(fila):
                norm = _normalizar_encabezado(fila[idx])
                for alias in ALIAS_COLUMNAS.get(col, []):
                    if norm == _normalizar_encabezado(alias):
                        es_encabezado = True
                        break
            if es_encabezado:
                break

        if es_encabezado:
            continue

        registro = {}
        problemas = []

        for idx, col in mapeos_encabezado:
            valor = fila[idx] if idx < len(fila) else None
            registro[col] = _convertir_valor(valor, col)

        codigo = registro.get("codigo")
        if codigo is None or str(codigo).strip() == "":
            problemas.append("Sin codigo SIS")

        if problemas:
            errores.append({
                "fila_original": i,
                "datos": registro,
                "problemas": problemas,
            })

        filas_procesadas.append(registro)

    return filas_procesadas, errores


def validar_estructura(filas, errores):
    reporte = {
        "total_filas": len(filas),
        "filas_validas": 0,
        "filas_con_problemas": len(errores),
        "errores": errores,
        "columnas_detectadas": set(),
        "codigos_encontrados": set(),
    }

    for fila in filas:
        reporte["columnas_detectadas"].update(fila.keys())
        cod = fila.get("codigo")
        if cod:
            reporte["codigos_encontrados"].add(str(cod))

    reporte["filas_validas"] = (
        reporte["total_filas"] - reporte["filas_con_problemas"]
    )
    reporte["columnas_detectadas"] = sorted(reporte["columnas_detectadas"])

    return reporte


def leer_kardex_pdf(ruta_pdf):
    if not os.path.exists(ruta_pdf):
        return None, [{"error": f"Archivo no encontrado: {ruta_pdf}"}]

    tablas = extraer_tablas_pdf(ruta_pdf)

    if not tablas:
        texto_paginas = extraer_texto_pdf(ruta_pdf)
        lineas_total = []
        for pag in texto_paginas:
            lineas_total.extend(pag["lineas"])

        filas_simuladas = [l.split("\t") for l in lineas_total if l.strip()]
        mapeos, columnas = detectar_encabezados(
            next((f for f in filas_simuladas
                  if any(_mapear_columna(c) for c in f)), [])
        ) if filas_simuladas else (None, [])

        if mapeos:
            filas, errores = extraer_filas(filas_simuladas, mapeos)
        else:
            return None, [{
                "error": "No se detecto tabla ni encabezados en el PDF.",
                "sugerencia": (
                    "El PDF podria no tener texto seleccionable. "
                    "Considere usar OCR (pendiente de implementar)."
                )
            }]
    else:
        todas_filas = []
        todos_errores = []
        mapeos_global = None

        for tabla_info in tablas:
            datos = tabla_info["datos"]
            if not datos:
                continue

            for fila in datos:
                mapeos, _ = detectar_encabezados(fila)
                if mapeos:
                    mapeos_global = mapeos
                    break
            if mapeos_global:
                break

        if not mapeos_global:
            return None, [{
                "error": "No se detectaron encabezados en las tablas del PDF.",
                "tablas_encontradas": len(tablas),
                "sugerencia": (
                    "Los encabezados no coinciden con los esperados. "
                    "Verifique el formato del PDF."
                )
            }]

        for tabla_info in tablas:
            datos = tabla_info["datos"]
            filas, errores = extraer_filas(datos, mapeos_global)
            todas_filas.extend(filas)
            todos_errores.extend(errores)

        filas = todas_filas
        errores = todos_errores

    reporte = validar_estructura(filas, errores)
    df = pd.DataFrame(filas)

    return df, reporte


def imprimir_reporte(reporte):
    print("REPORTE DE EXTRACCION DEL PDF")
    print("=" * 50)
    print(f"Total filas extraidas : {reporte['total_filas']}")
    print(f"Filas validas         : {reporte['filas_validas']}")
    print(f"Filas con problemas   : {reporte['filas_con_problemas']}")
    print(f"Columnas detectadas   : {reporte['columnas_detectadas']}")
    print(f"Codigos SIS encontrados: {len(reporte['codigos_encontrados'])}")

    if reporte["errores"]:
        print(f"\nERRORES ({len(reporte['errores'])}):")
        for err in reporte["errores"]:
            print(f"  Fila {err['fila_original']}: {err['problemas']}")
            if err.get("datos", {}).get("codigo"):
                print(f"    Codigo: {err['datos']['codigo']}")


def ejecutar_prueba():
    print("=" * 60)
    print("LECTOR DE KARDEX PDF - PRUEBA CON DATOS FICTICIOS")
    print("=" * 60)

    print("\n--- Simulacion de extraccion PDF ---")
    print("No hay PDF real disponible. Se simula la estructura\n"
          "que devolveria pdfplumber con un PDF de kardex.\n")

    tabla_simulada = [
        ["Nro", "Año", "Gestion", "Codigo", "Nivel", "TP", "MD",
         "CV", "GR", "GRPR", "T1", "T2", "T3", "P1", "P2",
         "EF", "2da", "MDTI", "EG", "NFIN", "RFIN"],
        ["1", "2025", "2", "1304001", "A", "", "N",
         "", "", "", "70", "75", "", "", "", "68", "", "", "", "71", "APR"],
        ["2", "2025", "2", "1304003", "A", "", "N",
         "", "", "", "40", "35", "", "", "", "30", "", "", "", "35", "REP"],
        ["3", "2026", "1", "1304003", "A", "", "N",
         "", "", "", "60", "55", "", "", "", "58", "", "", "", "58", "APR"],
        ["4", "2025", "2", "1304007", "B", "", "N",
         "", "", "", "45", "50", "", "", "", "40", "", "", "", "42", "REP"],
        ["5", "2026", "1", "1304007", "B", "", "N",
         "", "", "", "", "", "", "", "", "", "", "", "", "", ""],
        ["6", "2025", "2", "1304004", "A", "", "N",
         "", "", "", "30", "25", "", "", "", "", "", "", "", "", "ABA"],
        ["7", "2025", "3", "1304004", "A", "", "E",
         "", "", "", "", "", "", "", "", "65", "", "", "", "65", "APR"],
    ]

    print("Tabla detectada (simulada):")
    for fila in tabla_simulada[:3]:
        print(f"  {fila[:6]}...")
    print(f"  ... ({len(tabla_simulada)} filas totales)")

    mapeos, columnas = detectar_encabezados(tabla_simulada[0])
    print(f"\nEncabezados detectados: {len(mapeos)} columnas")
    for idx, col in mapeos:
        print(f"  Columna {idx}: {col}")

    filas, errores = extraer_filas(tabla_simulada, mapeos)
    reporte = validar_estructura(filas, errores)

    print()
    imprimir_reporte(reporte)

    if filas:
        print("\n--- Primeras filas procesadas ---")
        for f in filas[:3]:
            print(f"  Codigo: {f.get('codigo')}, "
                  f"T1: {f.get('t1')}, T2: {f.get('t2')}, "
                  f"EF: {f.get('ef')}, NFIN: {f.get('nfin')}, "
                  f"RFIN: {f.get('rfin')}")

    print("\n--- Verificacion: tipo de datos ---")
    if filas:
        f = filas[0]
        print(f"  codigo: {type(f['codigo']).__name__} = {f['codigo']}")
        print(f"  anio:   {type(f['anio']).__name__} = {f['anio']}")
        print(f"  t1:     {type(f['t1']).__name__} = {f['t1']}")
        print(f"  nfin:   {type(f['nfin']).__name__} = {f['nfin']}")
        print(f"  rfin:   {type(f['rfin']).__name__} = {f['rfin']}")

    print("\n--- Preparacion para importador_kardex ---")
    df = pd.DataFrame(filas)
    print(f"  DataFrame shape: {df.shape}")
    print(f"  Columnas: {list(df.columns)}")
    print("  Este DataFrame puede pasarse directamente a "
          "cargar_desde_dataframe()")

    print("\n--- Preparacion para OCR futuro ---")
    print("  Arquitectura en capas:")
    print("  Capa 1: Extraccion de texto (pdfplumber / OCR)")
    print("  Capa 2: Deteccion de encabezados (adaptativa)")
    print("  Capa 3: Parseo de filas (reutilizable)")
    print("  Capa 4: Validacion y reporte")
    print("  Para agregar OCR, solo reemplazar Capa 1.")

    print("\n" + "=" * 60)
    print("PRUEBA COMPLETADA")
    print("=" * 60)


if __name__ == "__main__":
    ejecutar_prueba()
