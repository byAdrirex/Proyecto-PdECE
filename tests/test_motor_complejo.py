"""
Test de estrés del motor académico con kardex ficticio complejo.
NO modifica módulos de producción.
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "modulos"))

from motor_academico import (
    crear_motor, configurar_gestion, seleccionar_objetivos,
    determinar_estado_materia_completo, evaluar_todas,
    progreso_general, cupos_disponibles, imprimir_progreso,
    OBJ_LIC, OBJ_M01, OBJ_M02, OBJ_M03, OBJ_T01, OBJ_T02, OBJ_T03,
    _materias_objetivo_con_sustituciones,
)
from importador_kardex import (
    crear_kardex as crear_kardex_base,
    cargar_desde_dataframe,
)
import pandas as pd

OK = 0
FALLOS = 0


def verificar(codigo, condicion, esperado, actual):
    global OK, FALLOS
    if condicion:
        OK += 1
    else:
        FALLOS += 1
        print("  FALLO %s: esperado %s, obtenido %s" % (codigo, esperado, actual))


def crear_kardex_complejo():
    """
    Crea un kardex ficticio con escenarios controlados.
    Materias del plan real (76 materias del Excel).
    """
    kardex = crear_kardex_base()

    filas = [
        # === OBLIGATORIAS APROBADAS (nivel A) ===
        # Prereqs de nada:基础课
        {"Codigo SIS": "1304001", "anio": 2025, "gestion": 1,
         "md": "N", "t1": 70, "t2": 75, "ef": 65, "nfin": 68, "rfin": "APR"},
        {"Codigo SIS": "1304002", "anio": 2025, "gestion": 1,
         "md": "N", "t1": 80, "t2": 70, "ef": 75, "nfin": 75, "rfin": "APR"},
        {"Codigo SIS": "1304003", "anio": 2025, "gestion": 1,
         "md": "N", "t1": 65, "t2": 70, "ef": 60, "nfin": 65, "rfin": "APR"},
        {"Codigo SIS": "1304004", "anio": 2025, "gestion": 1,
         "md": "N", "t1": 72, "t2": 68, "ef": 70, "nfin": 70, "rfin": "APR"},
        {"Codigo SIS": "1304005", "anio": 2025, "gestion": 1,
         "md": "N", "t1": 85, "t2": 80, "ef": 78, "nfin": 80, "rfin": "APR"},
        {"Codigo SIS": "1304006", "anio": 2025, "gestion": 1,
         "md": "N", "t1": 90, "t2": 85, "ef": 88, "nfin": 88, "rfin": "APR"},

        # === OBLIGATORIA REPROBADA (nivel B, prereq de otras) ===
        # 1304017 = ADMINISTRACION (sin prereqs, pero es prereq de nada directamente)
        {"Codigo SIS": "1304017", "anio": 2025, "gestion": 2,
         "md": "N", "t1": 35, "t2": 40, "ef": 30, "nfin": 35, "rfin": "REP"},

        # === OBLIGATORIA ABANDONADA ===
        # 1304012 = HISTORIA ECONOMICA DE BOLIVIA (sin prereqs)
        {"Codigo SIS": "1304012", "anio": 2025, "gestion": 2,
         "md": "N", "t1": 50, "t2": None, "ef": None, "nfin": None, "rfin": "ABA"},

        # === OBLIGATORIA EN CURSO (gestion actual 2026/1) ===
        # 1304019 = TEORIA FISCAL (sin prereqs)
        {"Codigo SIS": "1304019", "anio": 2026, "gestion": 1,
         "md": "N", "t1": 60, "t2": 55, "ef": None, "nfin": None, "rfin": None},

        # === REP -> APR (historial completo) ===
        # 1304007 = MICROECONOMIA I (prereqs: 1304001, 1304004)
        {"Codigo SIS": "1304007", "anio": 2025, "gestion": 2,
         "md": "N", "t1": 40, "t2": 35, "ef": 30, "nfin": 38, "rfin": "REP"},
        {"Codigo SIS": "1304007", "anio": 2026, "gestion": 1,
         "md": "N", "t1": 65, "t2": 70, "ef": 68, "nfin": 68, "rfin": "APR"},

        # === ABA -> APR (mesa, historial completo) ===
        # 1304018 = CONTABILIDAD BASICA (prereq: 1304003)
        {"Codigo SIS": "1304018", "anio": 2025, "gestion": 2,
         "md": "N", "t1": 30, "t2": 25, "ef": None, "nfin": None, "rfin": "ABA"},
        {"Codigo SIS": "1304018", "anio": 2025, "gestion": 3,
         "md": "E", "t1": None, "t2": None, "ef": 65, "nfin": 65, "rfin": "APR"},

        # === APROBADA POR MESA (comparar con normal) ===
        # 1304015 = HISTORIA DEL PENSAMIENTO ECONOMICO (prereq: 1304008)
        # Pero 1304008 no esta aprobada, la aprobamos primero
        # 1304008 = MACROECONOMIA I (prereqs: 1304001, 1304003, 1304004)
        {"Codigo SIS": "1304008", "anio": 2025, "gestion": 2,
         "md": "N", "t1": 70, "t2": 65, "ef": 72, "nfin": 70, "rfin": "APR"},
        # 1304015 aprobada por mesa
        {"Codigo SIS": "1304015", "anio": 2026, "gestion": 1,
         "md": "E", "t1": None, "t2": None, "ef": None, "nfin": 75, "rfin": "APR"},

        # === OBLIGATORIA BLOQUEADA (prereq faltante) ===
        # 1304013 = MICROECONOMIA II (prereq: 1304007) - 1304007 ya aprobada arriba
        # La aprobamos tambien para tener control
        {"Codigo SIS": "1304013", "anio": 2026, "gestion": 1,
         "md": "N", "t1": 70, "t2": 65, "ef": 68, "nfin": 68, "rfin": "APR"},

        # === ELECTIVAS APROBADAS (para progreso licenciatura) ===
        # 1304129 = DEMOGRAFIA (en M01, M02, T02, T03)
        {"Codigo SIS": "1304129", "anio": 2025, "gestion": 2,
         "md": "N", "t1": 75, "t2": 70, "ef": 72, "nfin": 72, "rfin": "APR"},
        # 1304063 = MUESTREO (en M02, T01, T02, T03) - COMPARTIDA
        {"Codigo SIS": "1304063", "anio": 2025, "gestion": 2,
         "md": "N", "t1": 80, "t2": 75, "ef": 78, "nfin": 78, "rfin": "APR"},
        # 1304134 = FINANZAS DE EMPRESAS (en M02, T01)
        {"Codigo SIS": "1304134", "anio": 2025, "gestion": 2,
         "md": "N", "t1": 70, "t2": 68, "ef": 72, "nfin": 70, "rfin": "APR"},
        # 1304113 = CONTABILIDAD NACIONAL (en M01)
        {"Codigo SIS": "1304113", "anio": 2025, "gestion": 2,
         "md": "N", "t1": 65, "t2": 70, "ef": 68, "nfin": 68, "rfin": "APR"},

        # === ELECTIVA REPROBADA ===
        # 1304155 = GESTION DE RRHH (en M02, T01)
        {"Codigo SIS": "1304155", "anio": 2025, "gestion": 2,
         "md": "N", "t1": 40, "t2": 35, "ef": 30, "nfin": 35, "rfin": "REP"},

        # === MATERIA COMPARTIDA M02+T01: 1304063 ya aprobada arriba ===

        # === M03 SUSTITUCION: verificar que 1304160 (sustituta de 1304022) funciona ===
        # 1304160 = ECONOMIA INDUSTRIAL (sustituta de 1304022 en M03)
        # La aprobamos
        {"Codigo SIS": "1304160", "anio": 2025, "gestion": 2,
         "md": "N", "t1": 72, "t2": 68, "ef": 70, "nfin": 70, "rfin": "APR"},
        # 1301031 = MERCADOTECNIA I (sustituta de 1304028 en M03) - pendiente
        # 1301034 = MERCADOTECNIA II (sustituta de 1304035 en M03) - pendiente

        # === PRERREQUISITOS PARCIALMENTE CUMPLIDOS ===
        # 1304021 = ECONOMIA FINANCIERA I (prereqs: 1304007, 1304018, 1304157)
        # 1304007 aprobada, 1304018 aprobada, 1304157 NO aprobada -> BLOQUEADA
        # 1304157 = ALGEBRA APLICADA (prereq: 1304003) - la aprobamos
        {"Codigo SIS": "1304157", "anio": 2025, "gestion": 2,
         "md": "N", "t1": 85, "t2": 80, "ef": 82, "nfin": 82, "rfin": "APR"},
        # Ahora 1304021 tiene todos los prereqs -> DISPONIBLE
        {"Codigo SIS": "1304021", "anio": 2026, "gestion": 1,
         "md": "N", "t1": 75, "t2": 70, "ef": 72, "nfin": 72, "rfin": "APR"},

        # === MATERIA BLOQUEADA REAL ===
        # 1304022 = ECONOMIA POLITICA I (prereqs: 1304008, 1304013) - ambas aprobadas
        # -> DISPONIBLE, no bloqueada
        # Usemos 1304030 = ECONOMETRIA I (prereqs: 1304007, 1304008, 1304023)
        # 1304023 NO aprobada -> BLOQUEADA
        {"Codigo SIS": "1304030", "anio": 2026, "gestion": 1,
         "md": "N", "t1": 70, "t2": 65, "ef": 68, "nfin": 68, "rfin": "APR"},

        # === OBLIGATORIA NO CURRICULAR ===
        {"Codigo SIS": "TI01", "anio": 2025, "gestion": 1,
         "md": "N", "t1": 80, "t2": 75, "ef": 78, "nfin": 78, "rfin": "APR"},
        {"Codigo SIS": "TI02", "anio": 2025, "gestion": 1,
         "md": "N", "t1": 75, "t2": 70, "ef": 72, "nfin": 72, "rfin": "APR"},
    ]

    df = pd.DataFrame(filas)
    cargar_desde_dataframe(df, kardex)
    return kardex


def ejecutar_tests():
    global OK, FALLOS

    print("=" * 70)
    print("test Motor Academico - Kardex Ficticio Complejo")
    print("=" * 70)

    motor = crear_motor()
    kardex = crear_kardex_complejo()
    motor["kardex"] = kardex
    configurar_gestion(motor, anio=2026, gestion=1)

    seleccionar_objetivos(motor, [OBJ_LIC, OBJ_M03, OBJ_T01])

    print("\n--- Verificaciones especificas ---\n")

    # 1. REP -> APR cuenta como aprobada para prerequisitos
    print("1. REP -> APR para prerrequisitos")
    r = determinar_estado_materia_completo("1304007", motor)
    verificar("1304007", r["estado"] == "APROBADA", "APROBADA", r["estado"])
    intentos = kardex["intentos"].get("1304007", [])
    verificar("1304007_intentos", len(intentos) == 2, 2, len(intentos))

    # 2. ABA -> APR cuenta como aprobada
    print("2. ABA -> APR para prerrequisitos")
    r = determinar_estado_materia_completo("1304018", motor)
    verificar("1304018", r["estado"] == "APROBADA", "APROBADA", r["estado"])

    # 3. REP sin aprobacion posterior -> bloqueada
    print("3. REP sin aprobacion posterior")
    r = determinar_estado_materia_completo("1304017", motor)
    verificar("1304017", r["estado"] == "REPROBADA", "REPROBADA", r["estado"])

    # 4. Materia en curso no es aprobada para prerequisitos
    print("4. EN_CURSO no cuenta como aprobada")
    r = determinar_estado_materia_completo("1304019", motor)
    verificar("1304019", r["estado"] == "EN_CURSO", "EN_CURSO", r["estado"])

    # 5. Aprobada por mesa = igual que normal
    print("5. Mesa cuenta igual que normal")
    r_mesa = determinar_estado_materia_completo("1304015", motor)
    r_normal = determinar_estado_materia_completo("1304001", motor)
    verificar("1304015_mesa", r_mesa["estado"] == "APROBADA", "APROBADA", r_mesa["estado"])
    verificar("igual_mesa_normal", r_mesa["estado"] == r_normal["estado"],
              r_normal["estado"], r_mesa["estado"])

    # 6. Materia compartida no se duplica
    print("6. Materia compartida no duplica")
    # 1304063 esta en M02 y T01
    m02 = _materias_objetivo_con_sustituciones(OBJ_M02, motor)
    t01 = _materias_objetivo_con_sustituciones(OBJ_T01, motor)
    verificar("1304063_en_M02", "1304063" in m02, "SI", "NO")
    verificar("1304063_en_T01", "1304063" in t01, "SI", "NO")
    verificar("sin_duplicar", m02.count("1304063") == 1, 1, m02.count("1304063"))

    # 7. Sustitucion M03 solo aplica con M03 seleccionado
    print("7. Sustitucion M03 solo con M03")
    seleccionar_objetivos(motor, [OBJ_LIC])  # Sin M03
    materias_sin_m03 = motor["materias_df"]
    # 1304022 debe seguir existiendo como materia obligatoria
    seleccionar_objetivos(motor, [OBJ_LIC, OBJ_M03])  # Con M03
    # En M03, 1304022 se reemplaza por 1304160
    m03 = _materias_objetivo_con_sustituciones(OBJ_M03, motor)
    verificar("M03_1304160", "1304160" in m03, "SI", "NO")
    verificar("M03_1304022_ausente", "1304022" not in m03, "SI",
             "PRESENTE" if "1304022" in m03 else "NO")

    # 8. Sustituta aprobada satisface requisito de M03
    print("8. Sustituta aprobada satisface M03")
    # 1304160 esta aprobada en el kardex y es sustituta de 1304022 en M03
    r_sust = determinar_estado_materia_completo("1304160", motor)
    verificar("1304160_sust_aprobada", r_sust["estado"] == "APROBADA",
              "APROBADA", r_sust["estado"])

    # Restaurar objetivos completos para tests 9-10
    seleccionar_objetivos(motor, [OBJ_LIC, OBJ_M03, OBJ_T01])

    # 9. Progreso licenciatura cuenta 8 electivas
    # Electivas aprobadas: 1304063, 1304113, 1304129, 1304134, 1304160 = 5
    print("9. Progreso licenciatura (8 electivas)")
    pg = progreso_general(motor)
    el = pg["electivas_licenciatura"]
    verificar("electivas_aprobadas", len(el["aprobadas"]) == 5, 5, len(el["aprobadas"]))
    verificar("electivas_faltan", el["faltan"] == 3, 3, el["faltan"])
    verificar("electivas_cumplido", not el["cumplido"], False, el["cumplido"])

    # 10. Progreso mencion independiente de tecnicos
    print("10. Progreso mencion independiente")
    pg_m03 = pg["menciones"].get("M03", {})
    pg_t01 = pg["tecnicos"].get("T01", {})
    verificar("M03_independiente", pg_m03.get("total", 0) > 0, ">0", pg_m03.get("total", 0))
    verificar("T01_independiente", pg_t01.get("total", 0) > 0, ">0", pg_t01.get("total", 0))

    # 11. Limite semestre regular
    print("11. Limite semestre regular (8N + 2M)")
    configurar_gestion(motor, anio=2026, gestion=1)
    cupos = cupos_disponibles(motor)
    verificar("cupos_tipo_reg", cupos["tipo"] == "semestre regular",
              "semestre regular", cupos["tipo"])
    verificar("cupos_N_max", cupos["normal_max"] == 8, 8, cupos["normal_max"])
    verificar("cupos_M_max", cupos["mesa_max"] == 2, 2, cupos["mesa_max"])

    # 12. Limite intersemestral
    print("12. Limite intersemestral (2N)")
    configurar_gestion(motor, anio=2026, gestion=3)
    cupos = cupos_disponibles(motor)
    verificar("cupos_tipo_inter", cupos["tipo"] == "intersemestral",
              "intersemestral", cupos["tipo"])
    verificar("cupos_inter_N", cupos["normal_max"] == 2, 2, cupos["normal_max"])
    verificar("cupos_inter_M", cupos["mesa_max"] == 0, 0, cupos["mesa_max"])

    # 13. Gst y Md nunca se confunden
    print("13. Gst y Md independientes")
    for intento in kardex["intentos"].get("1304015", []):
        verificar("1304015_md_E", intento.get("md") == "E", "E", intento.get("md"))
        verificar("1304015_tp_no_mesa", "mesa" not in (intento.get("tipo_periodo") or "").lower(),
                  "no mesa", intento.get("tipo_periodo"))
    for intento in kardex["intentos"].get("1304018", []):
        if intento.get("anio") == 2025 and intento.get("gestion") == 3:
            verificar("1304018_inter_md_E", intento.get("md") == "E", "E", intento.get("md"))
            verificar("1304018_inter_tp_verano", "verano" in (intento.get("tipo_periodo") or ""),
                      "verano", intento.get("tipo_periodo"))

    # === TABLA DE ESTADOS ===
    print("\n" + "=" * 70)
    print("TABLA DE ESTADOS POR MATERIA")
    print("=" * 70)
    fmt = "%-10s %-35s %-15s %-10s %s"
    print(fmt % ("Cod SIS", "Materia", "Estado", "Prereq", "Objetivos"))
    print("-" * 110)

    codigos_importantes = [
        "1304001", "1304003", "1304007", "1304008", "1304012", "1304013",
        "1304015", "1304017", "1304018", "1304019", "1304021", "1304022",
        "1304030", "1304063", "1304113", "1304129", "1304134", "1304155",
        "1304157", "1304160", "1301031", "TI01",
    ]

    eval_all = evaluar_todas(motor)
    for cod in codigos_importantes:
        info = motor["mapa_prereq"].get(cod, {})
        nombre = info.get("materia", "?")[:33]
        r = eval_all.get(cod, {})
        estado = r.get("estado", "?")
        faltan = r.get("faltan", [])
        prereq_str = "OK" if not faltan else "Falta: " + ", ".join(faltan)
        if len(prereq_str) > 30:
            prereq_str = prereq_str[:27] + "..."

        objs = []
        for obj in [OBJ_M01, OBJ_M02, OBJ_M03, OBJ_T01, OBJ_T02, OBJ_T03]:
            tipo = "mencion" if obj.startswith("M") else "tecnico"
            codigos_obj = _materias_objetivo_con_sustituciones(obj, motor)
            if cod in codigos_obj:
                objs.append(obj)
        obj_str = ",".join(objs) if objs else "-"

        print(fmt % (cod, nombre, estado, prereq_str, obj_str))

    # === TABLA DE PROGRESO ===
    print("\n" + "=" * 70)
    print("TABLA DE PROGRESO POR OBJETIVO")
    print("=" * 70)
    fmt2 = "%-20s %-10s %-10s %-10s %s"
    print(fmt2 % ("Objetivo", "Aprob", "Pend", "Porc", "Cumple"))
    print("-" * 65)

    pg = progreso_general(motor)

    # Obligatorias
    o = pg["obligatorias"]
    print(fmt2 % ("Obligatorias", "%d/%d" % (len(o["aprobadas"]), o["total"]),
                  str(len(o["pendientes"])), "%.1f%%" % o["porcentaje"],
                  "SI" if o["porcentaje"] == 100 else "NO"))

    # No curriculares
    nc = pg["no_curriculares"]
    print(fmt2 % ("No curriculares", "%d/%d" % (len(nc["aprobadas"]), nc["total"]),
                  str(len(nc["pendientes"])), "%.1f%%" % nc["porcentaje"],
                  "SI" if nc["porcentaje"] == 100 else "NO"))

    # Electivas licenciatura
    el = pg["electivas_licenciatura"]
    print(fmt2 % ("Electivas Lic.", "%d/%d" % (len(el["aprobadas"]), el["necesarias"]),
                  str(el["faltan"]), "-",
                  "SI" if el["cumplido"] else "NO"))

    # Menciones
    for obj, data in pg["menciones"].items():
        print(fmt2 % (obj, "%d/%d" % (len(data["aprobadas"]), data["total"]),
                      str(len(data["pendientes"])), "%.1f%%" % data["porcentaje"],
                      "SI" if data["porcentaje"] == 100 else "NO"))

    # Tecnicos
    for obj, data in pg["tecnicos"].items():
        print(fmt2 % (obj, "%d/%d" % (len(data["aprobadas"]), data["total"]),
                      str(len(data["pendientes"])), "%.1f%%" % data["porcentaje"],
                      "SI" if data["porcentaje"] == 100 else "NO"))

    # === RESUMEN ===
    print("\n" + "=" * 70)
    print("RESUMEN DE TESTS")
    print("=" * 70)
    print("Verificaciones pasadas: %d" % OK)
    print("Verificaciones fallidas: %d" % FALLOS)
    if FALLOS == 0:
        print("TODOS LOS TESTS PASARON CORRECTAMENTE")
    else:
        print("HAY %d FALLO(S)" % FALLOS)
    print("=" * 70)


if __name__ == "__main__":
    ejecutar_tests()
