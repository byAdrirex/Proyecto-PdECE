"""
Objetivos academicos: menciones, tecnicos y sustituciones.
Integra las hojas Menciones, Materia.Mencion, Tecnicos,
Materia.Tecnico y Sustituciones del Excel.
"""

import os
import pandas as pd

from kardex import (
    consultar_estado,
    ESTADO_APROBADA,
    ESTADO_EN_CURSO,
    ESTADO_REPROBADA,
)

RUTA_EXCEL = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "datos", "Exel Plan de estudios.xlsx"
)

CREDITOS_ELECTIVA_LIC = 8


def cargar_objetivos(ruta_excel=RUTA_EXCEL):
    xls = pd.ExcelFile(ruta_excel)
    menciones = pd.read_excel(xls, sheet_name="Menciones")
    materia_mencion = pd.read_excel(xls, sheet_name="Materia.Mencion")
    tecnicos = pd.read_excel(xls, sheet_name="Tecnicos")
    materia_tecnico = pd.read_excel(xls, sheet_name="Materia.Tecnico")
    sustituciones = pd.read_excel(xls, sheet_name="Sustituciones")

    materia_mencion["Codigo SIS"] = materia_mencion["Codigo SIS"].astype(str)
    materia_tecnico["Codigo SIS"] = materia_tecnico["Codigo SIS"].astype(str)
    sustituciones["SIS Materia Original"] = sustituciones["SIS Materia Original"].astype(str)
    sustituciones["SIS Materia Sustituta"] = sustituciones["SIS Materia Sustituta"].astype(str)

    return {
        "menciones": menciones,
        "materia_mencion": materia_mencion,
        "tecnicos": tecnicos,
        "materia_tecnico": materia_tecnico,
        "sustituciones": sustituciones,
    }


def _aplicar_sustituciones(materias, id_objetivo, tipo, datos):
    if tipo != "mencion":
        return materias

    sust = datos["sustituciones"]
    reglas = sust[sust["ID Mencion"] == id_objetivo]
    if reglas.empty:
        return materias

    originales = set(reglas["SIS Materia Original"])
    sustitutas = set(reglas["SIS Materia Sustituta"])

    resultado = []
    for m in materias:
        if m in originales:
            if m not in sustitutas:
                continue
        resultado.append(m)

    for _, row in reglas.iterrows():
        orig = row["SIS Materia Original"]
        sust = row["SIS Materia Sustituta"]
        if sust not in resultado and orig in originales:
            resultado.append(sust)

    return resultado


def materias_por_objetivo(id_objetivo, tipo, datos):
    if tipo == "mencion":
        mm = datos["materia_mencion"]
        codigos = mm[mm["ID Mencion"] == id_objetivo]["Codigo SIS"].tolist()
    elif tipo == "tecnico":
        mt = datos["materia_tecnico"]
        codigos = mt[mt["ID Tecnico"] == id_objetivo]["Codigo SIS"].tolist()
    else:
        return []

    return _aplicar_sustituciones(codigos, id_objetivo, tipo, datos)


def sustituciones_de_objetivo(id_objetivo, tipo, datos):
    if tipo != "mencion":
        return []
    sust = datos["sustituciones"]
    reglas = sust[sust["ID Mencion"] == id_objetivo]
    return [
        {"original": row["SIS Materia Original"],
         "sustituta": row["SIS Materia Sustituta"]}
        for _, row in reglas.iterrows()
    ]


def progreso_objetivo(id_objetivo, tipo, datos, kardex):
    materias = materias_por_objetivo(id_objetivo, tipo, datos)
    aprobadas = []
    en_curso = []
    pendientes = []

    for m in materias:
        estado = consultar_estado(kardex, m)
        if estado == ESTADO_APROBADA:
            aprobadas.append(m)
        elif estado == ESTADO_EN_CURSO:
            en_curso.append(m)
        else:
            pendientes.append(m)

    total = len(materias)
    porcentaje = (len(aprobadas) / total * 100) if total > 0 else 0

    return {
        "total": total,
        "aprobadas": aprobadas,
        "en_curso": en_curso,
        "pendientes": pendientes,
        "porcentaje": round(porcentaje, 1),
    }


def progreso_electivas_licenciatura(datos, kardex, materias_df):
    from importador_kardex import determinar_estado_materia

    df = materias_df.copy() if materias_df is not None else None
    if df is None:
        from prerrequisitos import cargar_materias
        df = cargar_materias()
    df["Codigo SIS"] = df["Codigo SIS"].astype(str)

    mm_codes = set(datos["materia_mencion"]["Codigo SIS"].astype(str))
    mt_codes = set(datos["materia_tecnico"]["Codigo SIS"].astype(str))
    obligatoria_codes = set(
        df[df["Tipo"] == "Obligatoria"]["Codigo SIS"]
    )

    electivas = df[
        (~df["Codigo SIS"].isin(obligatoria_codes))
        & (df["Codigo SIS"].isin(mm_codes | mt_codes))
    ]

    aprobadas = []
    pendientes = []
    for _, row in electivas.iterrows():
        codigo = row["Codigo SIS"]
        estado = determinar_estado_materia(codigo, kardex)
        if estado["aprobada"]:
            aprobadas.append(codigo)
        else:
            pendientes.append(codigo)

    faltan = max(0, CREDITOS_ELECTIVA_LIC - len(aprobadas))

    return {
        "necesarias": CREDITOS_ELECTIVA_LIC,
        "aprobadas": aprobadas,
        "pendientes": pendientes,
        "faltan": faltan,
        "cumplido": len(aprobadas) >= CREDITOS_ELECTIVA_LIC,
    }


def imprimir_objetivo(id_objetivo, tipo, datos, kardex, mapa_prereq=None):
    if tipo == "mencion":
        info = datos["menciones"]
        nombre_row = info[info["ID Mencion"] == id_objetivo]
        nombre = nombre_row["Nombre"].values[0] if not nombre_row.empty else "?"
    else:
        info = datos["tecnicos"]
        nombre_row = info[info["ID Tecnico"] == id_objetivo]
        nombre = nombre_row["Nombre"].values[0] if not nombre_row.empty else "?"

    print(f"ID         : {id_objetivo}")
    print(f"Nombre     : {nombre}")
    print(f"Tipo       : {tipo}")

    progreso = progreso_objetivo(id_objetivo, tipo, datos, kardex)
    print(f"Total      : {progreso['total']}")
    print(f"Aprobadas  : {len(progreso['aprobadas'])}")
    print(f"En curso   : {len(progreso['en_curso'])}")
    print(f"Pendientes : {len(progreso['pendientes'])}")
    print(f"Progreso   : {progreso['porcentaje']}%")

    sust = sustituciones_de_objetivo(id_objetivo, tipo, datos)
    if sust:
        print(f"Sustituciones ({len(sust)}):")
        for s in sust:
            print(f"  {s['original']} -> {s['sustituta']}")

    print("Aprobadas:")
    for m in progreso["aprobadas"]:
        nombre_m = "?"
        if mapa_prereq and m in mapa_prereq:
            nombre_m = mapa_prereq[m]["materia"]
        print(f"  {m}: {nombre_m}")

    print("En curso:")
    for m in progreso["en_curso"]:
        nombre_m = "?"
        if mapa_prereq and m in mapa_prereq:
            nombre_m = mapa_prereq[m]["materia"]
        print(f"  {m}: {nombre_m}")

    print("Pendientes:")
    for m in progreso["pendientes"]:
        nombre_m = "?"
        if mapa_prereq and m in mapa_prereq:
            nombre_m = mapa_prereq[m]["materia"]
        print(f"  {m}: {nombre_m}")


def ejecutar_prueba():
    from kardex import crear_kardex, registrar_materia
    from prerrequisitos import cargar_materias, construir_mapa_prerequisitos

    print("=" * 60)
    print("MODULO DE OBJETIVOS ACADEMICOS - PRUEBA")
    print("=" * 60)

    datos = cargar_objetivos()
    df_materias = cargar_materias()
    mapa_prereq = construir_mapa_prerequisitos(df_materias)
    kardex = crear_kardex()

    print("\n--- Kardex ficticio ---")
    kardex_data = [
        ("1304001", 72, None),
        ("1304002", 65, None),
        ("1304003", 48, None),
        ("1304004", 70, None),
        ("1304005", 80, None),
        ("1304007", 55, None),
        ("1304013", None, None),
        ("1304008", None, None),
        ("1304129", 60, None),
        ("1304131", 75, None),
        ("1304141", None, "EN_CURSO"),
        ("1304113", 58, None),
        ("1304063", 68, None),
        ("1304134", 72, None),
        ("1304139", None, None),
        ("1304155", 65, None),
        ("1304065", 70, None),
        ("1302004", 62, None),
        ("1302006", None, "EN_CURSO"),
    ]
    for codigo, nota, estado in kardex_data:
        registrar_materia(kardex, codigo, nota, estado)

    print("\n" + "=" * 60)
    print("PRUEBA 1: MENCION - M01 (Economia del Desarrollo)")
    print("=" * 60)
    imprimir_objetivo("M01", "mencion", datos, kardex, mapa_prereq)

    print("\n" + "=" * 60)
    print("PRUEBA 2: TECNICO - T01 (Proyectos de Inversion)")
    print("=" * 60)
    imprimir_objetivo("T01", "tecnico", datos, kardex, mapa_prereq)

    print("\n" + "=" * 60)
    print("PRUEBA 3: SUSTITUCIONES - M03 (Economia Comercial)")
    print("=" * 60)
    materias_m03 = materias_por_objetivo("M03", "mencion", datos)
    print(f"Materias de M03 ({len(materias_m03)}): {materias_m03}")
    sust = sustituciones_de_objetivo("M03", "mencion", datos)
    print(f"Sustituciones:")
    for s in sust:
        print(f"  {s['original']} -> {s['sustituta']}")
    imprimir_objetivo("M03", "mencion", datos, kardex, mapa_prereq)

    print("\n" + "=" * 60)
    print("PRUEBA 4: ELECTIVAS LICENCIATURA (8 necesarias)")
    print("=" * 60)
    electivas = progreso_electivas_licenciatura(datos, kardex, df_materias)
    print(f"Necesarias : {electivas['necesarias']}")
    print(f"Aprobadas  : {len(electivas['aprobadas'])} -> {electivas['aprobadas']}")
    print(f"Pendientes : {len(electivas['pendientes'])} -> {electivas['pendientes']}")
    print(f"Faltan     : {electivas['faltan']}")
    print(f"Cumplido   : {electivas['cumplido']}")

    print("\n" + "=" * 60)
    print("PRUEBA 5: MATERIAS EN MULTIPLES OBJETIVOS")
    print("=" * 60)
    mt = datos["materia_tecnico"]
    for cod in ["1304063", "1304129"]:
        menciones = datos["materia_mencion"][
            datos["materia_mencion"]["Codigo SIS"] == cod
        ]["ID Mencion"].tolist()
        tecs = mt[mt["Codigo SIS"] == cod]["ID Tecnico"].tolist()
        print(f"  {cod}: menciones={menciones}, tecnicos={tecs}")

    print("\n" + "=" * 60)
    print("PRUEBA COMPLETADA")
    print("=" * 60)


if __name__ == "__main__":
    ejecutar_prueba()
