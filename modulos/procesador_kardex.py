"""
Procesador de kardex: integra lector PDF con importador interno.
Flujo: PDF -> lector_kardex_pdf -> procesador_kardex -> kardex interno
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from lector_kardex_pdf import leer_kardex_pdf
from importador_kardex import (
    crear_kardex, configurar_gestion, cargar_desde_dataframe,
    determinar_estado_materia, registrar_correccion,
    determinar_estado_con_correccion, resumen_kardex,
    ESTADO_APROBADA, ESTADO_REPROBADA, ESTADO_ABANDONADA,
    ESTADO_EN_CURSO, ESTADO_SIN_HISTORIAL, ESTADO_PROVISIONAL,
    RFIN_APR, RFIN_REP, RFIN_ABA, NOTA_MINIMA,
)

RUTA_EXCEL = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "datos", "Exel Plan de estudios.xlsx"
)

GESTIONES = {
    1: "semestre regular 1",
    2: "semestre regular 2",
    3: "intersemestral verano",
    4: "intersemestral invierno",
}

MODALIDADES = {"N": "Normal", "E": "Mesa"}


def _calcular_tipo_periodo(gestion):
    try:
        g = int(gestion)
    except (ValueError, TypeError):
        return None
    return GESTIONES.get(g)


def _calcular_modalidad(md):
    if md is None:
        return None
    return MODALIDADES.get(str(md).strip().upper())


def agregar_campos_calculados(df):
    df = df.copy()
    df["tipo_periodo"] = df["gestion"].apply(_calcular_tipo_periodo)
    df["modalidad"] = df["md"].apply(_calcular_modalidad)
    return df


def _clasificar_intentos(kardex):
    stats = {
        "total_intentos": 0,
        "materias_unicas": 0,
        "materias_repetidas": 0,
        "aprobadas": 0,
        "reprobadas": 0,
        "abandonadas": 0,
        "en_curso": 0,
        "sin_historial": 0,
        "provisionales": 0,
        "mesa": 0,
        "normal": 0,
        "semestre_regular": 0,
        "intersemestrales": 0,
        "codigos_desconocidos": len(kardex["codigos_desconocidos"]),
        "inconsistencias": len(kardex["inconsistencias"]),
        "advertencias": [],
        "filas_ignoradas": 0,
    }

    for codigo, intentos in kardex["intentos"].items():
        stats["total_intentos"] += len(intentos)
        if len(intentos) > 1:
            stats["materias_repetidas"] += 1

        for it in intentos:
            md = str(it.get("md", "")).strip().upper()
            gst = it.get("gestion")

            if md == "E":
                stats["mesa"] += 1
            elif md == "N":
                stats["normal"] += 1

            if gst in (1, 2):
                stats["semestre_regular"] += 1
            elif gst in (3, 4):
                stats["intersemestrales"] += 1

            if md == "N" and gst in (3, 4):
                t2 = it.get("t2")
                if t2 is None:
                    pass

        estado_info = determinar_estado_materia(codigo, kardex)
        estado = estado_info["estado"]
        provisional = estado_info["provisional"]

        if estado == ESTADO_APROBADA:
            stats["aprobadas"] += 1
        elif estado == ESTADO_REPROBADA:
            stats["reprobadas"] += 1
        elif estado == ESTADO_ABANDONADA:
            stats["abandonadas"] += 1
        elif estado == ESTADO_EN_CURSO:
            stats["en_curso"] += 1
        elif estado == ESTADO_SIN_HISTORIAL:
            stats["sin_historial"] += 1

        if provisional:
            stats["provisionales"] += 1

    stats["materias_unicas"] = len(kardex["intentos"])

    for inc in kardex["inconsistencias"]:
        stats["advertencias"].append(
            f"Inconsistencia {inc['codigo']} ({inc['anio']}/{inc['gestion']}): "
            f"{inc['detalle']}"
        )

    for desc in kardex["codigos_desconocidos"]:
        stats["advertencias"].append(
            f"Codigo desconocido: {desc['codigo']} (fila {desc['fila']})"
        )

    return stats


def imprimir_reporte(stats):
    print("=" * 60)
    print("REPORTE DE IMPORTACION DEL KARDEX")
    print("=" * 60)
    print(f"Total registros (intentos)    : {stats['total_intentos']}")
    print(f"Materias unicas               : {stats['materias_unicas']}")
    print(f"Materias con multiples intentos: {stats['materias_repetidas']}")
    print()
    print("--- Estado academico ---")
    print(f"  Aprobadas      : {stats['aprobadas']}")
    print(f"  Reprobadas     : {stats['reprobadas']}")
    print(f"  Abandonadas    : {stats['abandonadas']}")
    print(f"  En curso       : {stats['en_curso']}")
    print(f"  Sin historial  : {stats['sin_historial']}")
    print(f"  Provisionales  : {stats['provisionales']}")
    print()
    print("--- Periodo y modalidad ---")
    print(f"  Semestre regular (Gst 1/2)   : {stats['semestre_regular']}")
    print(f"  Intersemestrales (Gst 3/4)   : {stats['intersemestrales']}")
    print(f"  Normal (Md=N)                : {stats['normal']}")
    print(f"  Mesa (Md=E)                  : {stats['mesa']}")
    print()
    print("--- Validacion ---")
    print(f"  Codigos SIS desconocidos     : {stats['codigos_desconocidos']}")
    print(f"  Inconsistencias detectadas   : {stats['inconsistencias']}")
    print(f"  Filas ignoradas              : {stats['filas_ignoradas']}")
    if stats["advertencias"]:
        print(f"\nAdvertencias ({len(stats['advertencias'])}):")
        for a in stats["advertencias"]:
            print(f"  - {a}")
    print("=" * 60)


def imprimir_detalle_estado(kardex, mapa_prereq=None):
    print("\n--- Detalle por materia ---")
    print(f"{'Cod SIS':<10} {'Materia':<40} {'Estado':<15} {'Gst/Md':<10} "
          f"{'NFIN':<6} {'RFIN':<5} {'Prov'}")
    print("-" * 100)

    for codigo in sorted(kardex["intentos"].keys()):
        intentos = kardex["intentos"][codigo]
        nombre = "?"
        if mapa_prereq and codigo in mapa_prereq:
            nombre = mapa_prereq[codigo]["materia"]
        nombre = nombre[:38]

        estado_info = determinar_estado_materia(codigo, kardex)
        estado = estado_info["estado"]
        prov = "S" if estado_info["provisional"] else ""

        for it in intentos:
            gst = it.get("gestion", "?")
            md = it.get("md", "?")
            gst_md = f"{gst}/{md}"
            nfin = it.get("nfin")
            rfin = it.get("rfin", "-")
            nf_str = str(int(nfin)) if nfin else "-"
            rf_str = str(rfin) if rfin else "-"
            corr = it.get("correccion_estudiante")
            prov_marca = f" {prov}" if prov else ""

            print(f"{codigo:<10} {nombre:<40} {estado:<15} {gst_md:<10} "
                  f"{nf_str:<6} {rf_str:<5}{prov_marca}")
            nombre = ""
            estado = ""
            prov = ""

        if len(intentos) > 1:
            print(f"  {'':10} ({len(intentos)} intentos)")


def imprimir_historial_completo(kardex, mapa_prereq=None):
    print("\n--- Historial completo (todos los intentos) ---")
    for codigo in sorted(kardex["intentos"].keys()):
        intentos = kardex["intentos"][codigo]
        nombre = "?"
        if mapa_prereq and codigo in mapa_prereq:
            nombre = mapa_prereq[codigo]["materia"]
        print(f"\n{codigo}: {nombre} ({len(intentos)} intento(s))")
        for it in intentos:
            gst = it.get("gestion", "?")
            anio = it.get("anio", "?")
            md = it.get("md", "?")
            nfin = it.get("nfin")
            rfin = it.get("rfin", "-")
            nf_str = str(int(nfin)) if nfin else "-"
            corr = it.get("correccion_estudiante")
            corr_str = f" | corr: {corr}" if corr else ""
            print(f"  {anio}/{gst} Md={md} T1={it.get('t1', '-')} "
                  f"T2={it.get('t2', '-')} EF={it.get('ef', '-')} "
                  f"NFIN={nf_str} RFIN={rfin}{corr_str}")


def procesar_pdf(ruta_pdf, kardex, materias_df=None, mapa_prereq=None):
    print(f"Procesando: {ruta_pdf}")
    df_pdf, reporte_lector = leer_kardex_pdf(ruta_pdf)

    if df_pdf is None:
        print("Error: No se pudo extraer datos del PDF.")
        if reporte_lector:
            for err in reporte_lector:
                print(f"  {err}")
        return None

    print(f"Filas extraidas del PDF: {len(df_pdf)}")

    return procesar_dataframe(df_pdf, kardex, materias_df, mapa_prereq)


def procesar_dataframe(df_pdf, kardex, materias_df=None, mapa_prereq=None):
    df = agregar_campos_calculados(df_pdf)

    col_codigo = "codigo" if "codigo" in df.columns else "Codigo SIS"
    df_import = df.rename(columns={col_codigo: "Codigo SIS"})

    if "gestion" in df_import.columns:
        df_import = df_import.rename(columns={"gestion": "Gestion"})

    mask_no_nan = df_import["Codigo SIS"].notna()
    filas_ignoradas = int((~mask_no_nan).sum())
    df_import = df_import[mask_no_nan]

    kardex["intentos"] = {}
    cargar_desde_dataframe(df_import, kardex, materias_df)

    for codigo, intentos in kardex["intentos"].items():
        for it in intentos:
            gst = it.get("gestion")
            md = it.get("md")
            it["tipo_periodo"] = _calcular_tipo_periodo(gst)
            it["modalidad"] = _calcular_modalidad(md)

    stats = _clasificar_intentos(kardex)
    stats["filas_ignoradas"] = filas_ignoradas

    imprimir_reporte(stats)
    imprimir_detalle_estado(kardex, mapa_prereq)
    imprimir_historial_completo(kardex, mapa_prereq)

    return stats


def ejecutar_prueba():
    from prerrequisitos import cargar_materias, construir_mapa_prerequisitos

    print("=" * 60)
    print("PROCESADOR DE KARDEX - PRUEBA CON PDF REAL")
    print("=" * 60)

    ruta_pdf = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "datos", "webSISS Sistema de Informaci\u00f3n San Sim\u00f3n.pdf"
    )

    if not os.path.exists(ruta_pdf):
        print(f"PDF no encontrado: {ruta_pdf}")
        return

    df_materias = cargar_materias()
    mapa_prereq = construir_mapa_prerequisitos(df_materias)
    kardex = crear_kardex()
    configurar_gestion(kardex, anio=2026, gestion=1)

    print(f"\nGestion configurada: {kardex['configuracion']}\n")

    procesar_pdf(ruta_pdf, kardex, df_materias, mapa_prereq)

    print("\n--- Verificacion de casos especificos ---")
    casos = [
        ("1304157", "Gst=4 + Md=N -> Intersemestral invierno / Normal"),
        ("1304158", "Gst=4 + Md=N -> Intersemestral invierno / Normal"),
        ("1304017", "Gst=2 + Md=E -> Semestre regular / Mesa"),
        ("1304015", "Gst=1 + Md=E -> Semestre regular / Mesa"),
        ("1304023", "Gst=3 + Md=N -> Intersemestral verano / Normal"),
        ("1304025", "Gst=3 + Md=N -> Intersemestral verano / Normal"),
    ]
    for cod, desc in casos:
        intentos = kardex["intentos"].get(cod, [])
        if intentos:
            it = intentos[0]
            gst = it.get("gestion")
            md = it.get("md")
            tp = it.get("tipo_periodo", "?")
            mod = it.get("modalidad", "?")
            print(f"\n  {cod}: {desc}")
            print(f"    Gst={gst}, Md={md} -> {tp} / {mod}")
            ok = (tp == _calcular_tipo_periodo(gst)
                  and mod == _calcular_modalidad(md))
            print(f"    Correcto: {'SI' if ok else 'NO'}")
        else:
            print(f"\n  {cod}: NO ENCONTRADO")

    print("\n" + "=" * 60)
    print("PRUEBA COMPLETADA - NO SE MODIFICARON ARCHIVOS")
    print("=" * 60)


if __name__ == "__main__":
    ejecutar_prueba()
