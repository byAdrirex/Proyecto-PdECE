"""
Importador y modelo interno del kardex.
Capa que transforma, valida y mantiene el historial academico.
NO lee PDF, NO hace OCR, NO modifica el Excel.
"""

import os
import pandas as pd

RUTA_EXCEL = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "datos", "Exel Plan de estudios.xlsx"
)

ESTADO_APROBADA = "APROBADA"
ESTADO_REPROBADA = "REPROBADA"
ESTADO_ABANDONADA = "ABANDONADA"
ESTADO_EN_CURSO = "EN_CURSO"
ESTADO_SIN_HISTORIAL = "SIN_HISTORIAL"
ESTADO_PROVISIONAL = "PROVISIONAL"

RFIN_APR = "APR"
RFIN_REP = "REP"
RFIN_ABA = "ABA"

NOTA_MINIMA = 51

GESTIONES = {1: "semestre 1", 2: "semestre 2",
             3: "intersemestral verano", 4: "intersemestral invierno"}


def crear_kardex():
    return {
        "intentos": {},
        "configuracion": {
            "anio_actual": None,
            "gestion_actual": None,
            "tipo_periodo_actual": None,
        },
        "codigos_desconocidos": [],
        "inconsistencias": [],
    }


def configurar_gestion(kardex, anio, gestion, tipo_periodo="semestre"):
    if gestion not in GESTIONES:
        raise ValueError(
            f"Gestion invalida: {gestion}. Validas: {list(GESTIONES.keys())}"
        )
    kardex["configuracion"]["anio_actual"] = anio
    kardex["configuracion"]["gestion_actual"] = gestion
    kardex["configuracion"]["tipo_periodo_actual"] = tipo_periodo


def _normalizar_codigo(codigo):
    return str(codigo).strip()


def _es_gestion_actual(kardex, anio, gestion):
    cfg = kardex["configuracion"]
    return (cfg["anio_actual"] == anio
            and cfg["gestion_actual"] == gestion)


def _detectar_inconsistencias(intento):
    inc = []
    nf = intento.get("nfin")
    rf = intento.get("rfin")
    if nf is not None and rf is not None:
        try:
            nf_num = float(nf)
            if nf_num >= NOTA_MINIMA and rf == RFIN_REP:
                inc.append(f"nFIN={nf}>=51 pero RFIN=REP")
            elif nf_num < NOTA_MINIMA and rf == RFIN_APR:
                inc.append(f"nFIN={nf}<51 pero RFIN=APR")
        except (ValueError, TypeError):
            pass
    return inc


def _calcular_estado_intento(intento):
    rf = intento.get("rfin")
    if rf == RFIN_APR:
        return ESTADO_APROBADA
    if rf == RFIN_REP:
        return ESTADO_REPROBADA
    if rf == RFIN_ABA:
        return ESTADO_ABANDONADA
    nf = intento.get("nfin")
    if nf is not None:
        try:
            if float(nf) >= NOTA_MINIMA:
                return ESTADO_APROBADA
            return ESTADO_REPROBADA
        except (ValueError, TypeError):
            pass
    return None


def cargar_desde_dataframe(df, kardex, materias_df=None):
    codigos_validos = set()
    if materias_df is not None:
        codigos_validos = set(materias_df["Codigo SIS"].astype(str))

    for idx, row in df.iterrows():
        codigo = _normalizar_codigo(row.get("Codigo SIS", row.get("codigo", "")))
        if not codigo:
            continue

        anio = row.get("Anio", row.get("anio", row.get("Año")))
        gestion = row.get("Gestion", row.get("gestion"))
        try:
            anio = int(anio) if pd.notna(anio) else None
        except (ValueError, TypeError):
            anio = None
        try:
            gestion = int(gestion) if pd.notna(gestion) else None
        except (ValueError, TypeError):
            gestion = None

        def _val(col_names):
            if isinstance(col_names, str):
                col_names = [col_names]
            for cn in col_names:
                if cn in row and pd.notna(row[cn]):
                    return row[cn]
            return None

        def _num(col_names):
            v = _val(col_names)
            if v is None:
                return None
            try:
                return float(v)
            except (ValueError, TypeError):
                return None

        intento = {
            "nro": _val(["Nro", "nro"]),
            "anio": anio,
            "gestion": gestion,
            "codigo_sis": codigo,
            "nivel": _val(["Nivel", "nivel"]),
            "tp": _val(["TP", "tp"]),
            "md": _val(["MD", "md"]),
            "cv": _val(["CV", "cv"]),
            "gr": _val(["GR", "gr"]),
            "grpr": _val(["GRPR", "grpr"]),
            "t1": _num(["T1", "t1"]),
            "t2": _num(["T2", "t2"]),
            "t3": None,
            "p1": None,
            "p2": None,
            "ef": _num(["EF", "ef"]),
            "2da": _num(["2da", "2da"]),
            "mdTI": _val(["MDTI", "mdTI", "mdti"]),
            "eg": _num(["EG", "eg"]),
            "nfin": _num(["NFIN", "nFIN", "nfin"]),
            "rfin": _val(["RFIN", "rfin"]),
            "correccion_estudiante": None,
            "estado_calculado": None,
            "inconsistencias": [],
            "origen": "pdf",
        }

        if codigo not in codigos_validos and codigos_validos:
            kardex["codigos_desconocidos"].append({
                "codigo": codigo, "fila": idx
            })

        intento["inconsistencias"] = _detectar_inconsistencias(intento)
        intento["estado_calculado"] = _calcular_estado_intento(intento)

        tp_map = {1: "semestre regular", 2: "semestre regular",
                  3: "intersemestral verano", 4: "intersemestral invierno"}
        intento["tipo_periodo"] = tp_map.get(gestion) if gestion else None

        if codigo not in kardex["intentos"]:
            kardex["intentos"][codigo] = []
        kardex["intentos"][codigo].append(intento)

    kardex["inconsistencias"] = []
    for codigo, intentos in kardex["intentos"].items():
        for it in intentos:
            for inc in it["inconsistencias"]:
                kardex["inconsistencias"].append({
                    "codigo": codigo,
                    "anio": it["anio"],
                    "gestion": it["gestion"],
                    "detalle": inc,
                })

    return kardex


def reconstruir_inconsistencias(kardex):
    """Recalcula inconsistencias después de editar el kardex en sesión."""
    inconsistencias = []
    for codigo, intentos in kardex.get("intentos", {}).items():
        for intento in intentos:
            intento["inconsistencias"] = _detectar_inconsistencias(intento)
            intento["estado_calculado"] = _calcular_estado_intento(intento)
            for detalle in intento["inconsistencias"]:
                inconsistencias.append({
                    "codigo": codigo,
                    "anio": intento.get("anio"),
                    "gestion": intento.get("gestion"),
                    "detalle": detalle,
                })
    kardex["inconsistencias"] = inconsistencias
    return kardex


def registrar_correccion(kardex, codigo_sis, anio, gestion, campos):
    codigo_sis = _normalizar_codigo(codigo_sis)
    intentos = kardex["intentos"].get(codigo_sis, [])
    objetivo = None
    for it in intentos:
        if it["anio"] == anio and it["gestion"] == gestion:
            objetivo = it
            break
    if objetivo is None:
        return False

    if objetivo["correccion_estudiante"] is None:
        objetivo["correccion_estudiante"] = {}

    objetivo["correccion_estudiante"].update(campos)
    return True


def _tiene_aprobacion_historica(intentos):
    for it in intentos:
        if it["estado_calculado"] == ESTADO_APROBADA:
            return True
    return False


def _intento_mas_reciente(intentos):
    if not intentos:
        return None
    return max(intentos, key=lambda x: (x["anio"] or 0, x["gestion"] or 0))


def determinar_estado_materia(codigo_sis, kardex):
    codigo_sis = _normalizar_codigo(codigo_sis)
    intentos = kardex["intentos"].get(codigo_sis, [])

    if not intentos:
        return {
            "estado": ESTADO_SIN_HISTORIAL,
            "provisional": False,
            "detalle": "Materia sin registros en el kardex.",
            "aprobada": False,
        }

    aprobada = _tiene_aprobacion_historica(intentos)
    reciente = _intento_mas_reciente(intentos)
    es_actual = _es_gestion_actual(
        kardex, reciente["anio"], reciente["gestion"]
    ) if reciente["anio"] and reciente["gestion"] else False

    if aprobada:
        return {
            "estado": ESTADO_APROBADA,
            "provisional": False,
            "detalle": "Materia con al menos una aprobacion en el historial.",
            "aprobada": True,
        }

    if es_actual:
        if reciente["estado_calculado"] is None:
            return {
                "estado": ESTADO_EN_CURSO,
                "provisional": True,
                "detalle": "Gestion actual, sin resultado oficial.",
                "aprobada": False,
            }
        return {
            "estado": reciente["estado_calculado"],
            "provisional": True,
            "detalle": (
                f"Gestion actual: {reciente['estado_calculado']}. "
                "Resultado sujeto a cambio."
            ),
            "aprobada": False,
        }

    ultimo_estado = reciente["estado_calculado"]
    if ultimo_estado == ESTADO_ABANDONADA:
        return {
            "estado": ESTADO_ABANDONADA,
            "provisional": False,
            "detalle": "Ultimo registro es abandono, sin aprobaciones previas.",
            "aprobada": False,
        }
    if ultimo_estado == ESTADO_REPROBADA:
        return {
            "estado": ESTADO_REPROBADA,
            "provisional": False,
            "detalle": "Ultimo registro es reprobacion, sin aprobaciones previas.",
            "aprobada": False,
        }

    return {
        "estado": ultimo_estado or ESTADO_SIN_HISTORIAL,
        "provisional": False,
        "detalle": "Estado determinado por el ultimo registro.",
        "aprobada": False,
    }


def determinar_estado_con_correccion(codigo_sis, anio, gestion, kardex):
    codigo_sis = _normalizar_codigo(codigo_sis)
    intentos = kardex["intentos"].get(codigo_sis, [])
    for it in intentos:
        if it["anio"] == anio and it["gestion"] == gestion:
            corr = it.get("correccion_estudiante")
            if corr is None:
                return it["estado_calculado"]

            nfin_corr = corr.get("nfin", it.get("nfin"))
            rfin_corr = corr.get("rfin", it.get("rfin"))

            if rfin_corr == RFIN_APR:
                return ESTADO_APROBADA
            if rfin_corr == RFIN_REP:
                return ESTADO_REPROBADA
            if rfin_corr == RFIN_ABA:
                return ESTADO_ABANDONADA

            if nfin_corr is not None:
                try:
                    if float(nfin_corr) >= NOTA_MINIMA:
                        return ESTADO_APROBADA
                    return ESTADO_REPROBADA
                except (ValueError, TypeError):
                    pass
            return None
    return None


def resumen_kardex(kardex, materias_df=None):
    total_intentos = sum(len(v) for v in kardex["intentos"].values())
    materias_registradas = len(kardex["intentos"])

    conteo = {ESTADO_APROBADA: 0, ESTADO_REPROBADA: 0,
              ESTADO_ABANDONADA: 0, ESTADO_EN_CURSO: 0,
              ESTADO_SIN_HISTORIAL: 0}
    for codigo in kardex["intentos"]:
        r = determinar_estado_materia(codigo, kardex)
        conteo[r["estado"]] = conteo.get(r["estado"], 0) + 1

    print(f"Total intentos: {total_intentos}")
    print(f"Materias registradas: {materias_registradas}")
    for estado, cant in sorted(conteo.items()):
        if cant > 0:
            print(f"  {estado}: {cant}")

    if kardex["codigos_desconocidos"]:
        print(f"Codigos desconocidos: {len(kardex['codigos_desconocidos'])}")
        for e in kardex["codigos_desconocidos"]:
            print(f"  {e['codigo']} (fila {e['fila']})")

    if kardex["inconsistencias"]:
        print(f"Inconsistencias: {len(kardex['inconsistencias'])}")
        for inc in kardex["inconsistencias"]:
            print(f"  {inc['codigo']} ({inc['anio']}/{inc['gestion']}): "
                  f"{inc['detalle']}")


def ejecutar_prueba():
    print("=" * 60)
    print("IMPORTADOR KARDEX - PRUEBA")
    print("=" * 60)

    from prerrequisitos import cargar_materias
    df_materias = cargar_materias()

    kardex = crear_kardex()
    configurar_gestion(kardex, anio=2026, gestion=1)

    print("\n--- Configuracion ---")
    print(f"  Gestion actual: {kardex['configuracion']}")

    df_prueba = pd.DataFrame([
        {"Codigo SIS": "1304001", "Anio": 2025, "Gestion": 2,
         "MD": "N", "T1": 70, "T2": 75, "EF": 68, "NFIN": 71, "RFIN": "APR"},
        {"Codigo SIS": "1304003", "Anio": 2025, "Gestion": 2,
         "MD": "N", "T1": 40, "T2": 35, "EF": 30, "NFIN": 35, "RFIN": "REP"},
        {"Codigo SIS": "1304003", "Anio": 2026, "Gestion": 1,
         "MD": "N", "T1": 60, "T2": 55, "EF": 58, "NFIN": 58, "RFIN": "APR"},
        {"Codigo SIS": "1304004", "Anio": 2025, "Gestion": 2,
         "MD": "N", "T1": 30, "T2": 25, "EF": None, "NFIN": None, "RFIN": "ABA"},
        {"Codigo SIS": "1304004", "Anio": 2025, "Gestion": 3,
         "MD": "E", "T1": None, "T2": None, "EF": 65, "NFIN": 65, "RFIN": "APR"},
        {"Codigo SIS": "1304005", "Anio": 2026, "Gestion": 1,
         "MD": "N", "T1": None, "T2": None, "EF": None,
         "NFIN": None, "RFIN": None},
        {"Codigo SIS": "1304007", "Anio": 2026, "Gestion": 1,
         "MD": "N", "T1": 50, "T2": 45, "EF": 40, "NFIN": 42, "RFIN": "REP"},
        {"Codigo SIS": "1304008", "Anio": 2025, "Gestion": 2,
         "MD": "N", "T1": 72, "T2": 68, "EF": 70, "NFIN": 70, "RFIN": "APR"},
        {"Codigo SIS": "1304013", "Anio": 2025, "Gestion": 2,
         "MD": "N", "T1": 60, "T2": 55, "EF": 62, "NFIN": 59, "RFIN": "REP"},
        {"Codigo SIS": "1304013", "Anio": 2026, "Gestion": 1,
         "MD": "N", "T1": 55, "T2": 50, "EF": None,
         "NFIN": None, "RFIN": None},
        {"Codigo SIS": "XXXX999", "Anio": 2025, "Gestion": 2,
         "MD": "N", "T1": 80, "T2": 75, "EF": 70, "NFIN": 75, "RFIN": "APR"},
        {"Codigo SIS": "1304016", "Anio": 2025, "Gestion": 2,
         "MD": "N", "T1": 65, "T2": 60, "EF": 55, "NFIN": 58, "RFIN": "REP"},
    ])

    print("\n--- Cargando kardex ---")
    cargar_desde_dataframe(df_prueba, kardex, df_materias)

    print("\n--- Correccion de estudiante ---")
    print("  1304005 (gestion actual, sin RFIN oficial)")
    print("  Estudiante indica: T1=70, T2=75, EF=68, nFIN=71")
    registrar_correccion(kardex, "1304005", 2026, 1,
                         {"t1": 70, "t2": 75, "ef": 68, "nfin": 71})

    print("\n  1304013 (gestion actual, REP oficial)")
    print("  Estudiante indica: T1=65, T2=60, EF=58, nFIN=61")
    registrar_correccion(kardex, "1304013", 2026, 1,
                         {"t1": 65, "t2": 60, "ef": 58, "nfin": 61})

    print("\n--- Estado de cada materia ---")
    codigos_prueba = [
        "1304001", "1304003", "1304004", "1304005",
        "1304007", "1304008", "1304013", "1304016", "XXXX999",
    ]
    for cod in codigos_prueba:
        r = determinar_estado_materia(cod, kardex)
        marcador = " *PROVISIONAL*" if r["provisional"] else ""
        print(f"  {cod}: {r['estado']}{marcador}")
        print(f"    {r['detalle']}")

    print("\n--- Estado con correccion del estudiante ---")
    for cod in ["1304005", "1304013"]:
        est = determinar_estado_con_correccion(cod, 2026, 1, kardex)
        print(f"  {cod} (2026/1): {est}")

    print("\n--- Verificacion: historial completo ---")
    for cod in ["1304003", "1304004", "1304013"]:
        intentos = kardex["intentos"].get(cod, [])
        print(f"  {cod}: {len(intentos)} intentos")
        for it in intentos:
            corr = it.get("correccion_estudiante")
            corr_str = f", correccion={corr}" if corr else ""
            print(f"    {it['anio']}/{it['gestion']}: "
                  f"RFIN={it['rfin']}, nFIN={it['nfin']}, "
                  f"md={it['md']}{corr_str}")

    print("\n--- Resumen ---")
    resumen_kardex(kardex, df_materias)

    print("\n" + "=" * 60)
    print("PRUEBA COMPLETADA")
    print("=" * 60)


if __name__ == "__main__":
    ejecutar_prueba()
