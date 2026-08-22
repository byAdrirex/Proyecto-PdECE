"""
Motor academico central.
Integra todos los modulos para determinar la situacion academica del estudiante.
NO crea interfaz grafica, NO procesa horarios, NO modifica archivos originales.
Separa:
  - estado_academico (prerrequisitos/kardex): APROBADA, REPROBADA, ABANDONADA,
    EN_CURSO, SIN_PRERREQUISITOS, DISPONIBLE, BLOQUEADA
  - estado_oferta (oferta actual): OFERTADA, NO_OFERTADA, None (sin cargar)
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from prerrequisitos import (
    cargar_materias, construir_mapa_prerequisitos,
    COLUMNAS_PREREQ,
)
from importador_kardex import (
    crear_kardex as crear_kardex_base,
    determinar_estado_materia,
    ESTADO_APROBADA as K_APROBADA,
    ESTADO_REPROBADA as K_REPROBADA,
    ESTADO_ABANDONADA as K_ABANDONADA,
    ESTADO_EN_CURSO as K_EN_CURSO,
    ESTADO_SIN_HISTORIAL,
)
from objetivos import (
    cargar_objetivos, materias_por_objetivo,
    progreso_objetivo, sustituciones_de_objetivo,
    progreso_electivas_licenciatura,
)
from disponibilidad import (
    evaluar_materia as _evaluar_disponibilidad,
    ESTADO_DISPONIBLE, ESTADO_BLOQUEADA, ESTADO_SIN_PRERREQUISITOS,
)

RUTA_EXCEL = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "datos", "Exel Plan de estudios.xlsx"
)

LIMITE_REGULAR_NORMAL = 8
LIMITE_REGULAR_MESA = 2
LIMITE_INTERSEMESTRAL = 2
ELECTIVAS_LICENCIATURA = 8

OBJ_LIC = "LICENCIATURA"
OBJ_M01 = "M01"
OBJ_M02 = "M02"
OBJ_M03 = "M03"
OBJ_T01 = "T01"
OBJ_T02 = "T02"
OBJ_T03 = "T03"


def crear_motor():
    df_materias = cargar_materias()
    mapa_prereq = construir_mapa_prerequisitos(df_materias)
    datos_objetivos = cargar_objetivos()

    tipos = {}
    for _, row in df_materias.iterrows():
        cod = str(row["Codigo SIS"])
        tipos[cod] = row["Tipo"]

    return {
        "materias_df": df_materias,
        "mapa_prereq": mapa_prereq,
        "datos_objetivos": datos_objetivos,
        "kardex": crear_kardex_base(),
        "configuracion": {
            "anio_actual": None,
            "gestion_actual": None,
            "tipo_periodo_actual": None,
        },
        "objetivos": [],
        "tipos_materias": tipos,
        "oferta": None,
    }


def configurar_gestion(motor, anio, gestion, tipo_periodo="semestre"):
    from importador_kardex import configurar_gestion as cfg
    cfg(motor["kardex"], anio, gestion, tipo_periodo)
    motor["configuracion"]["anio_actual"] = anio
    motor["configuracion"]["gestion_actual"] = gestion
    motor["configuracion"]["tipo_periodo_actual"] = tipo_periodo


def seleccionar_objetivos(motor, objetivos):
    validos = {OBJ_LIC, OBJ_M01, OBJ_M02, OBJ_M03, OBJ_T01, OBJ_T02, OBJ_T03}
    for obj in objetivos:
        if obj not in validos:
            raise ValueError("Objetivo invalido: %s" % obj)
    motor["objetivos"] = list(objetivos)


def cargar_oferta(motor, resultado_oferta):
    indice = {}
    for g in resultado_oferta.grupos:
        cod = g["codigo_sis"]
        if cod is None:
            continue
        indice.setdefault(cod, []).append(g)
    motor["oferta"] = {
        "indice": indice,
        "anio": resultado_oferta.anio,
        "gestion": resultado_oferta.gestion,
        "tipo_periodo": resultado_oferta.tipo_periodo,
        "total_materias": resultado_oferta.materias_unicas,
        "total_grupos": resultado_oferta.total_grupos,
    }


def _es_aprobada_para_prereq(codigo, kardex):
    r = determinar_estado_materia(codigo, kardex)
    return r["aprobada"]


def _prereqs_faltantes(codigo, mapa_prereq, kardex):
    info = mapa_prereq.get(codigo)
    if info is None:
        return []
    faltan = []
    for p in info["prerrequisitos"]:
        if not _es_aprobada_para_prereq(p, kardex):
            faltan.append(p)
    return faltan


def determinar_estado_materia_completo(codigo, motor):
    codigo = str(codigo)
    kardex = motor["kardex"]
    mapa_prereq = motor["mapa_prereq"]
    oferta = motor.get("oferta")

    r_kardex = determinar_estado_materia(codigo, kardex)
    estado_kardex = r_kardex["estado"]
    provisional = r_kardex.get("provisional", False)

    if estado_kardex == K_APROBADA:
        resultado = {"estado": "APROBADA", "faltan": [], "provisional": False}
    elif estado_kardex == K_REPROBADA:
        resultado = {"estado": "REPROBADA", "faltan": [], "provisional": provisional}
    elif estado_kardex == K_ABANDONADA:
        resultado = {"estado": "ABANDONADA", "faltan": [], "provisional": provisional}
    elif estado_kardex == K_EN_CURSO:
        resultado = {"estado": "EN_CURSO", "faltan": [], "provisional": provisional}
    else:
        info = mapa_prereq.get(codigo)
        if info is None:
            resultado = {"estado": "SIN_PRERREQUISITOS", "faltan": [], "provisional": False}
        else:
            prereqs = info["prerrequisitos"]
            if not prereqs:
                resultado = {"estado": "SIN_PRERREQUISITOS", "faltan": [], "provisional": False}
            else:
                faltan = _prereqs_faltantes(codigo, mapa_prereq, kardex)
                if not faltan:
                    resultado = {"estado": "DISPONIBLE", "faltan": [], "provisional": False}
                else:
                    resultado = {"estado": "BLOQUEADA", "faltan": faltan, "provisional": False}

    if oferta is not None:
        indice = oferta["indice"]
        grupos = indice.get(codigo, [])
        resultado["ofertada"] = len(grupos) > 0
        resultado["estado_oferta"] = "OFERTADA" if grupos else "NO_OFERTADA"
        resultado["grupos"] = grupos
    else:
        resultado["ofertada"] = None
        resultado["estado_oferta"] = None
        resultado["grupos"] = []

    return resultado


def evaluar_todas(motor):
    resultado = {}
    for codigo in motor["mapa_prereq"]:
        resultado[codigo] = determinar_estado_materia_completo(codigo, motor)
    return resultado


def _materias_objetivo_con_sustituciones(objetivo, motor):
    tipo = "mencion" if objetivo.startswith("M") else "tecnico"
    datos = motor["datos_objetivos"]
    return materias_por_objetivo(objetivo, tipo, datos)


def progreso_categoria(codigos, motor):
    aprobadas = []
    en_curso = []
    pendientes = []
    for c in codigos:
        estado = determinar_estado_materia_completo(c, motor)
        if estado["estado"] == "APROBADA":
            aprobadas.append(c)
        elif estado["estado"] == "EN_CURSO":
            en_curso.append(c)
        else:
            pendientes.append(c)
    total = len(codigos)
    pct = round(len(aprobadas) / total * 100, 1) if total > 0 else 0
    return {
        "total": total, "aprobadas": aprobadas,
        "en_curso": en_curso, "pendientes": pendientes,
        "porcentaje": pct,
    }


def progreso_general(motor):
    df = motor["materias_df"]
    kardex = motor["kardex"]
    objetivos = motor["objetivos"]
    tipos = motor["tipos_materias"]

    obligatorias = [c for c, t in tipos.items() if t == "Obligatoria"]
    no_curriculares = [c for c, t in tipos.items()
                       if t == "Obligatoria No Curricular"]

    progreso_oblig = progreso_categoria(obligatorias, motor)
    progreso_no_cur = progreso_categoria(no_curriculares, motor)

    electivas_lic = progreso_electivas_licenciatura(
        motor["datos_objetivos"], kardex, df
    )

    menciones = {}
    for obj in objetivos:
        if obj.startswith("M"):
            codigos = _materias_objetivo_con_sustituciones(obj, motor)
            menciones[obj] = progreso_categoria(codigos, motor)

    tecnicos = {}
    for obj in objetivos:
        if obj.startswith("T"):
            codigos = _materias_objetivo_con_sustituciones(obj, motor)
            tecnicos[obj] = progreso_categoria(codigos, motor)

    return {
        "obligatorias": progreso_oblig,
        "no_curriculares": progreso_no_cur,
        "electivas_licenciatura": electivas_lic,
        "menciones": menciones,
        "tecnicos": tecnicos,
    }


def cupos_disponibles(motor):
    gestion = motor["configuracion"]["gestion_actual"]
    if gestion in (1, 2):
        return {
            "tipo": "semestre regular",
            "normal_max": LIMITE_REGULAR_NORMAL,
            "mesa_max": LIMITE_REGULAR_MESA,
            "normal_usados": 0,
            "mesa_usados": 0,
            "normal_disponibles": LIMITE_REGULAR_NORMAL,
            "mesa_disponibles": LIMITE_REGULAR_MESA,
        }
    elif gestion in (3, 4):
        return {
            "tipo": "intersemestral",
            "normal_max": LIMITE_INTERSEMESTRAL,
            "mesa_max": 0,
            "normal_usados": 0,
            "mesa_usados": 0,
            "normal_disponibles": LIMITE_INTERSEMESTRAL,
            "mesa_disponibles": 0,
        }
    return None


def _materias_recomendadas(motor):
    eval_all = evaluar_todas(motor)
    objetivos = motor["objetivos"]
    tipos = motor["tipos_materias"]
    mapa = motor["mapa_prereq"]
    tiene_oferta = motor.get("oferta") is not None

    electivas_obj = set()
    for obj in objetivos:
        for c in _materias_objetivo_con_sustituciones(obj, motor):
            electivas_obj.add(c)

    recomendadas = []
    for codigo, info in eval_all.items():
        estado = info["estado"]
        if estado != "DISPONIBLE":
            continue
        if tiene_oferta and not info.get("ofertada", False):
            continue

        tipo = tipos.get(codigo, "")
        es_oblig = tipo == "Obligatoria"
        es_no_cur = tipo == "Obligatoria No Curricular"
        es_elect = tipo == "Materia Electiva"

        razon = []
        if es_oblig:
            razon.append("Es obligatoria en tu plan")
        elif es_no_cur:
            razon.append("Es obligatoria no curricular")
        elif es_elect and codigo in electivas_obj:
            razon.append("Pertenece a tu objetivo academico")
        elif es_elect:
            razon.append("Es electiva disponible")

        nombre = mapa.get(codigo, {}).get("materia", "?")
        recomendadas.append({
            "codigo": codigo,
            "materia": nombre,
            "razon": razon,
            "tipo": tipo,
            "ofertada": info.get("ofertada"),
            "grupos": info.get("grupos", []),
        })

    oblig_recomendadas = [r for r in recomendadas if r["tipo"] == "Obligatoria"]
    elect_recomendadas = [r for r in recomendadas if r["tipo"] == "Materia Electiva"]
    nocur_recomendadas = [r for r in recomendadas
                          if r["tipo"] == "Obligatoria No Curricular"]

    return oblig_recomendadas + nocur_recomendadas + elect_recomendadas


def imprimir_estado_materia(codigo, motor):
    info = determinar_estado_materia_completo(codigo, motor)
    mapa = motor["mapa_prereq"]
    nombre = mapa.get(codigo, {}).get("materia", "?")
    print("  %s: %s" % (codigo, nombre))
    print("    Estado academico: %s" % info["estado"])
    if info["faltan"]:
        print("    Faltan:")
        for f in info["faltan"]:
            nombre_f = mapa.get(f, {}).get("materia", "?")
            print("      - %s: %s" % (f, nombre_f))
    if info.get("estado_oferta") is not None:
        print("    Oferta: %s" % info["estado_oferta"])
        if info.get("grupos"):
            for g in info["grupos"]:
                auxs = g.get("auxiliares", [])
                aux_str = ""
                if auxs:
                    aux_str = " AUX: %s" % ", ".join(
                        a["nombre"] for a in auxs
                    )
                horarios_str = " | ".join(
                    "%s %s-%s %s" % (
                        h.get("dia", "?"),
                        h.get("hora_inicio", "??:??"),
                        h.get("hora_fin", "??:??"),
                        h.get("aula", "-"),
                    )
                    for h in g.get("horarios", [])
                )
                print("      G%s: %s%s  %s" % (
                    g.get("grupo", "?"),
                    g.get("docente", "???"),
                    aux_str,
                    horarios_str,
                ))


def consultar_oferta_materia(codigo, motor):
    codigo = str(codigo)
    oferta = motor.get("oferta")
    if oferta is None:
        return {"ofertada": None, "estado_oferta": None, "grupos": []}
    indice = oferta["indice"]
    grupos = indice.get(codigo, [])
    return {
        "ofertada": len(grupos) > 0,
        "estado_oferta": "OFERTADA" if grupos else "NO_OFERTADA",
        "grupos": grupos,
    }


def tabla_situacion_completa(motor):
    mapa = motor["mapa_prereq"]
    tipos = motor["tipos_materias"]
    tiene_oferta = motor.get("oferta") is not None

    codigos = sorted(set(tipos.keys()) | set(mapa.keys()))

    lineas = []
    hdr = "%-10s %-45s %-15s %-14s %-8s %-15s" % (
        "Codigo", "Materia", "Estado Acad.", "Oferta", "Grupos", "Objetivo")
    lineas.append(hdr)
    lineas.append("-" * 115)

    for cod in codigos:
        nombre = mapa.get(cod, {}).get("materia", tipos.get(cod, "?"))
        if nombre and len(nombre) > 43:
            nombre = nombre[:40] + "..."
        estado_info = determinar_estado_materia_completo(cod, motor)
        estado = estado_info["estado"]
        if tiene_oferta:
            n_grupos = len(estado_info.get("grupos", []))
            estado_oferta = estado_info.get("estado_oferta", "?")
            grupos_str = str(n_grupos) if n_grupos > 0 else "-"
        else:
            estado_oferta = "-"
            grupos_str = "-"

        tipos_list = []
        if cod in tipos:
            t = tipos[cod]
            if t == "Obligatoria":
                tipos_list.append("OBL")
            elif t == "Obligatoria No Curricular":
                tipos_list.append("OBL-NC")
            elif t == "Materia Electiva":
                tipos_list.append("ELECT")
        objetivo_str = ",".join(tipos_list) if tipos_list else "-"

        lineas.append("%-10s %-45s %-15s %-14s %-8s %-15s" % (
            cod, nombre, estado, estado_oferta, grupos_str, objetivo_str))

    return "\n".join(lineas)


def tabla_grupos_oferta(motor):
    oferta = motor.get("oferta")
    if oferta is None:
        return "No hay oferta cargada."

    indice = oferta["indice"]
    lineas = []
    hdr = "%-10s %-6s %-35s %-5s %-35s %-8s %-20s %-15s" % (
        "Codigo", "Grupo", "Docente", "AUX", "Auxiliar",
        "Dia", "Horario", "Aula")
    lineas.append(hdr)
    lineas.append("-" * 170)

    for cod in sorted(indice.keys()):
        grupos = indice[cod]
        for g in grupos:
            docente = g.get("docente", "???")
            if docente and len(docente) > 33:
                docente = docente[:30] + "..."
            auxiliares = g.get("auxiliares", [])
            aux_names = [a["nombre"] for a in auxiliares]
            horarios = g.get("horarios", [])

            if horarios:
                for i, h in enumerate(horarios):
                    if i == 0:
                        aux_flag = "Si" if auxiliares else "-"
                        aux_name = aux_names[0] if aux_names else "-"
                    else:
                        aux_flag = ""
                        aux_name = ""
                    dia = h.get("dia", "?")
                    hora = "%s-%s" % (
                        h.get("hora_inicio", "??:??"),
                        h.get("hora_fin", "??:??"))
                    aula = h.get("aula", "-")
                    lineas.append(
                        "%-10s %-6s %-35s %-5s %-35s %-8s %-20s %-15s" % (
                            cod, g.get("grupo", "?"), docente,
                            aux_flag, aux_name,
                            dia, hora, aula))
            else:
                aux_flag = "Si" if auxiliares else "-"
                aux_name = aux_names[0] if aux_names else "-"
                lineas.append(
                    "%-10s %-6s %-35s %-5s %-35s %-8s %-20s %-15s" % (
                        cod, g.get("grupo", "?"), docente,
                        aux_flag, aux_name,
                        "-", "-", "-"))

    return "\n".join(lineas)


def imprimir_progreso(progreso, titulo="Progreso"):
    print("\n--- %s ---" % titulo)
    for k, v in progreso.items():
        if isinstance(v, dict) and "total" in v:
            print("  %s: %d/%d (%.1f%%)" % (
                k, len(v["aprobadas"]), v["total"], v["porcentaje"]))
        elif isinstance(v, dict):
            for k2, v2 in v.items():
                if isinstance(v2, dict) and "total" in v2:
                    print("  %s %s: %d/%d (%.1f%%)" % (
                        k, k2, len(v2["aprobadas"]),
                        v2["total"], v2["porcentaje"]))
        elif isinstance(v, dict) and "necesarias" in v:
            print("  %s: %d/%d (%s)" % (
                k, len(v["aprobadas"]), v["necesarias"],
                "CUMPLIDO" if v["cumplido"] else "Incompleto"))


def imprimir_recomendaciones(motor):
    recs = _materias_recomendadas(motor)
    print("\n--- Materias recomendadas (%d) ---" % len(recs))
    for r in recs[:10]:
        print("  * %s (%s)" % (r["codigo"], r["materia"]))
        for raz in r["razon"]:
            print("    - %s" % raz)


def ejecutar_prueba():
    print("=" * 60)
    print("MOTOR ACADEMICO - PRUEBA COMPLETA")
    print("=" * 60)

    motor = crear_motor()
    configurar_gestion(motor, anio=2026, gestion=1)

    print("\n--- Cargando kardex del PDF real ---")
    from procesador_kardex import procesar_pdf
    ruta_kardex = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "datos", "webSISS Sistema de Informaci\u00f3n San Sim\u00f3n.pdf")
    if os.path.exists(ruta_kardex):
        procesar_pdf(ruta_kardex, motor["kardex"], motor["materias_df"],
                     motor["mapa_prereq"])

    print("\n--- Cargando oferta academica ---")
    from lector_oferta_pdf import leer_oferta_pdf
    ruta_oferta = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "datos", "Oferta ECO - 2-2026.pdf")
    if os.path.exists(ruta_oferta):
        resultado_oferta = leer_oferta_pdf(ruta_oferta, 2026, 2)
        cargar_oferta(motor, resultado_oferta)
        print("Oferta cargada: %d materias, %d grupos" % (
            motor["oferta"]["total_materias"],
            motor["oferta"]["total_grupos"]))
    else:
        print("PDF de oferta no encontrado: %s" % ruta_oferta)

    seleccionar_objetivos(motor, [OBJ_LIC, OBJ_M01])

    print("\n" + "=" * 60)
    print("TABLA DE SITUACION COMPLETA")
    print("=" * 60)
    print(tabla_situacion_completa(motor))

    print("\n" + "=" * 60)
    print("MATERIAS NO OFERTADAS (verificacion de las 6)")
    print("=" * 60)
    no_ofertadas = []
    for cod in sorted(motor["tipos_materias"].keys()):
        info = determinar_estado_materia_completo(cod, motor)
        if info.get("estado_oferta") == "NO_OFERTADA":
            no_ofertadas.append(cod)
            nombre = motor["mapa_prereq"].get(cod, {}).get("materia", "?")
            print("  %s: %s [%s]" % (cod, nombre, info["estado"]))
    print("Total no ofertadas: %d" % len(no_ofertadas))

    print("\n" + "=" * 60)
    print("VERIFICACION: APROBADA + OFERTADA = sigue APROBADA")
    print("=" * 60)
    for cod in ["1304001", "1304003", "1304007", "1304018"]:
        info = determinar_estado_materia_completo(cod, motor)
        nombre = motor["mapa_prereq"].get(cod, {}).get("materia", "?")
        n_grupos = len(info.get("grupos", []))
        print("  %s %s: %s / %s (%d grupos)" % (
            cod, nombre, info["estado"],
            info.get("estado_oferta", "?"), n_grupos))

    print("\n" + "=" * 60)
    print("VERIFICACION: BLOQUEADA + OFERTADA = BLOQUEADA")
    print("=" * 60)
    for cod in ["1304021", "1304134"]:
        info = determinar_estado_materia_completo(cod, motor)
        nombre = motor["mapa_prereq"].get(cod, {}).get("materia", "?")
        n_grupos = len(info.get("grupos", []))
        faltan = ", ".join(info.get("faltan", []))
        print("  %s %s: %s / %s (%d grupos) falta: %s" % (
            cod, nombre, info["estado"],
            info.get("estado_oferta", "?"), n_grupos, faltan))

    print("\n" + "=" * 60)
    print("VERIFICACION: DISPONIBLE + OFERTADA = inscribible")
    print("=" * 60)
    for cod in ["1304019", "1304022"]:
        info = determinar_estado_materia_completo(cod, motor)
        nombre = motor["mapa_prereq"].get(cod, {}).get("materia", "?")
        n_grupos = len(info.get("grupos", []))
        print("  %s %s: %s / %s (%d grupos)" % (
            cod, nombre, info["estado"],
            info.get("estado_oferta", "?"), n_grupos))

    print("\n" + "=" * 60)
    print("VERIFICACION: DISPONIBLE + NO OFERTADA")
    print("=" * 60)
    for cod in ["TI01", "TI02", "TI03", "TI04", "1304140", "1304162"]:
        info = determinar_estado_materia_completo(cod, motor)
        nombre = motor["mapa_prereq"].get(cod, {}).get("materia", "?")
        print("  %s %s: %s / %s" % (
            cod, nombre, info["estado"],
            info.get("estado_oferta", "?")))

    print("\n" + "=" * 60)
    print("MATERIAS CON GRUPOS Y AUXILIARES")
    print("=" * 60)
    for cod in ["1304001", "1304003", "1304008"]:
        info = determinar_estado_materia_completo(cod, motor)
        nombre = motor["mapa_prereq"].get(cod, {}).get("materia", "?")
        print("  %s %s: %d grupos" % (
            cod, nombre, len(info.get("grupos", []))))
        for g in info.get("grupos", []):
            auxs = g.get("auxiliares", [])
            aux_str = " AUX: %s" % ", ".join(a["nombre"] for a in auxs) if auxs else ""
            print("    G%s: %s%s" % (
                g.get("grupo", "?"),
                g.get("docente", "???"),
                aux_str))

    print("\n" + "=" * 60)
    print("RECOMENDACIONES (solo ofertadas)")
    print("=" * 60)
    recs = _materias_recomendadas(motor)
    print("Total recomendadas: %d" % len(recs))
    for r in recs[:8]:
        n_grupos = len(r.get("grupos", []))
        print("  * %s (%s) - %d grupos" % (
            r["codigo"], r["materia"], n_grupos))
        for raz in r["razon"]:
            print("    - %s" % raz)

    print("\n" + "=" * 60)
    print("PRUEBA COMPLETADA")
    print("=" * 60)


if __name__ == "__main__":
    ejecutar_prueba()
