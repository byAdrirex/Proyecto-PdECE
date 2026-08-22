import os
import sys

_MODULOS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "modulos")
if _MODULOS_DIR not in sys.path:
    sys.path.insert(0, _MODULOS_DIR)

_RUTA_KARDEX = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "datos", "webSISS Sistema de Informaci\u00f3n San Sim\u00f3n.pdf",
)
_RUTA_OFERTA = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "datos", "Oferta ECO - 2-2026.pdf",
)

_motor_cache = None


def get_motor():
    global _motor_cache
    if _motor_cache is not None:
        return _motor_cache

    from motor_academico import (
        crear_motor, configurar_gestion, seleccionar_objetivos,
        cargar_oferta, OBJ_LIC, OBJ_M01,
    )
    motor = crear_motor()
    configurar_gestion(motor, anio=2026, gestion=2)
    seleccionar_objetivos(motor, [OBJ_LIC, OBJ_M01])

    from procesador_kardex import procesar_pdf
    if os.path.exists(_RUTA_KARDEX):
        procesar_pdf(_RUTA_KARDEX, motor["kardex"], motor["materias_df"],
                     motor["mapa_prereq"])

    from lector_oferta_pdf import leer_oferta_pdf
    if os.path.exists(_RUTA_OFERTA):
        resultado = leer_oferta_pdf(_RUTA_OFERTA, 2026, 2)
        cargar_oferta(motor, resultado)

    _motor_cache = motor
    return motor


def get_motor_para_kardex(kardex):
    """Devuelve un motor que usa el kardex dado (modo academico con PDF subido).
    Reutiliza el motor base cacheado para oferta/plan de estudios y solo
    reemplaza el kardex, evitando re-procesar Excel y PDFs en cada peticion."""
    if kardex is None:
        return get_motor()
    import copy
    motor = copy.copy(get_motor())
    motor["kardex"] = kardex
    return motor

    from motor_academico import (
        crear_motor, configurar_gestion, seleccionar_objetivos,
        cargar_oferta, OBJ_LIC, OBJ_M01,
    )
    motor = crear_motor()
    configurar_gestion(motor, anio=2026, gestion=2)
    seleccionar_objetivos(motor, [OBJ_LIC, OBJ_M01])

    from procesador_kardex import procesar_pdf
    if os.path.exists(_RUTA_KARDEX):
        procesar_pdf(_RUTA_KARDEX, motor["kardex"], motor["materias_df"],
                     motor["mapa_prereq"])

    from lector_oferta_pdf import leer_oferta_pdf
    if os.path.exists(_RUTA_OFERTA):
        resultado = leer_oferta_pdf(_RUTA_OFERTA, 2026, 2)
        cargar_oferta(motor, resultado)

    _motor_cache = motor
    return motor


def get_oferta_niveles():
    motor = get_motor()
    idx = motor["oferta"]["indice"]
    niveles = set()
    for code, groups in idx.items():
        for g in groups:
            n = g.get("nivel")
            if n:
                niveles.add(n)
    return sorted(niveles)


def get_materias_por_nivel(nivel):
    motor = get_motor()
    idx = motor["oferta"]["indice"]
    resultado = {}
    for code, groups in idx.items():
        grupos_nivel = [g for g in groups if g.get("nivel") == nivel]
        if grupos_nivel:
            resultado[code] = {
                "codigo_sis": code,
                "nombre": grupos_nivel[0].get("nombre", "?"),
                "nivel": nivel,
                "num_grupos": len(grupos_nivel),
            }
    return resultado


def get_grupos_por_materia(codigo):
    motor = get_motor()
    idx = motor["oferta"]["indice"]
    return idx.get(codigo, [])


def agrupar_grupos(grupos):
    secciones = {}
    for g in grupos:
        num = g.get("grupo", "?")
        if num not in secciones:
            secciones[num] = {
                "numero": num,
                "docente": g.get("docente", "POR DESIGNAR DOCENTE"),
                "horarios": g.get("horarios", []),
                "auxiliares": g.get("auxiliares", []),
                "grupo": g,
            }
    return secciones


def verificar_prerequisitos(codigo):
    motor = get_motor()
    mapa = motor.get("mapa_prereq", {})
    info = mapa.get(codigo)
    if info is None:
        return None
    prereqs = info.get("prerrequisitos", [])
    if not prereqs:
        return None
    nombres = []
    for p in prereqs:
        p_info = mapa.get(p, {})
        nombres.append({"codigo": p, "materia": p_info.get("materia", "?")})
    return nombres


def format_dias(horarios):
    DIAS_LARGO = {
        "LU": "Lunes", "MA": "Martes", "MI": "Miercoles",
        "JU": "Jueves", "VI": "Viernes", "SA": "Sabado",
    }
    seen = []
    for h in horarios:
        d = h.get("dia", "")
        if d and d not in seen:
            seen.append(d)
    return " - ".join(DIAS_LARGO.get(d, d) for d in seen)


def format_horario(horarios):
    if not horarios:
        return ""
    parts = []
    for h in horarios:
        parts.append("%s-%s" % (h.get("hora_inicio", "?"), h.get("hora_fin", "?")))
    return ", ".join(parts)


def format_aulas(horarios):
    seen = []
    for h in horarios:
        a = h.get("aula", "-")
        if a not in seen:
            seen.append(a)
    return " / ".join(seen)


_DIAS_MAP = {
    "LU": "monday", "MA": "tuesday", "MI": "wednesday",
    "JU": "thursday", "VI": "friday", "SA": "saturday",
}

_DIAS_MAP_NUM = {
    "monday": 1, "tuesday": 2, "wednesday": 3,
    "thursday": 4, "friday": 5, "saturday": 6,
}


_PASTEL = [
    ("#bfdbfe", "#1d4ed8"),
    ("#bbf7d0", "#16a34a"),
    ("#fde68a", "#b45309"),
    ("#fbcfe8", "#db2777"),
    ("#ddd6fe", "#7c3aed"),
    ("#a5f3fc", "#0e7490"),
    ("#fed7aa", "#ea580c"),
    ("#d1fae5", "#059669"),
    ("#e0e7ff", "#4f46e5"),
    ("#fce7f3", "#be185d"),
]
_ROJO = ("#ef4444", "#b91c1c")
_AUX = ("#fde68a", "#d97706")


def _color_pastel(codigo):
    idx = sum(ord(c) for c in str(codigo)) % len(_PASTEL)
    return _PASTEL[idx]


def _colores_plan(plan):
    """Asigna un color pastel a cada grupo seleccionado garantizando que
    dos grupos de la misma materia nunca compartan color (rotacion secuencial
    por materia, sin colisiones por numeros de grupo tipo 01 vs 21)."""
    colores = {}
    usados = {}
    for g in plan.get("grupos_seleccionados", []):
        codigo = g.get("codigo_sis")
        grupo = g.get("grupo")
        clave = (codigo, grupo)
        if clave in colores:
            continue
        if codigo not in usados:
            usados[codigo] = (
                sum(ord(c) * (i + 1) for i, c in enumerate(str(codigo)))
                % len(_PASTEL)
            )
        colores[clave] = _PASTEL[usados[codigo]]
        usados[codigo] = (usados[codigo] + 1) % len(_PASTEL)
    return colores


def calendario_eventos(plan):
    modo_aux = plan.get("modo_aux", True)
    eventos = []

    conflicto = set()
    for c in plan.get("conflictos", []):
        conflicto.add((
            c.get("materia1"), c.get("grupo1"), c.get("tipo1"),
            c.get("dia"), c.get("hora_inicio1"), c.get("hora_fin1"),
        ))
        conflicto.add((
            c.get("materia2"), c.get("grupo2"), c.get("tipo2"),
            c.get("dia"), c.get("hora_inicio2"), c.get("hora_fin2"),
        ))

    colores = _colores_plan(plan)
    for g in plan.get("grupos_seleccionados", []):
        clave = (g.get("codigo_sis"), g.get("grupo"))
        for h in g.get("horarios", []):
            dia_semana = _DIAS_MAP.get(h.get("dia"))
            if not dia_semana:
                continue
            bloque_conflicto = (
                g.get("codigo_sis"), g.get("grupo"), "CLASE",
                h.get("dia"), h.get("hora_inicio"), h.get("hora_fin"),
            ) in conflicto
            if bloque_conflicto:
                bg, bd = _ROJO
                texto = "#ffffff"
            else:
                bg, bd = colores.get(clave, _color_pastel(g.get("codigo_sis", "")))
                texto = "#1f2937"
            eventos.append({
                "title": "%s (G%s)" % (g.get("nombre", "?"), g.get("grupo", "?")),
                "startRecur": "2026-08-17",
                "endRecur": "2026-12-19",
                "startTime": h.get("hora_inicio"),
                "endTime": h.get("hora_fin"),
                "daysOfWeek": [_DIAS_MAP_NUM[dia_semana]],
                "backgroundColor": bg,
                "borderColor": bd,
                "textColor": texto,
                "extendedProps": {
                    "tipo": "CLASE",
                    "nombre": g.get("nombre", "?"),
                    "aula": h.get("aula", "-"),
                    "grupo": g.get("grupo"),
                    "codigo": g.get("codigo_sis"),
                    "conflicto": bloque_conflicto,
                },
            })

        if modo_aux:
            for aux in g.get("auxiliares", []):
                for ha in aux.get("horarios", []):
                    dia_semana = _DIAS_MAP.get(ha.get("dia"))
                    if not dia_semana:
                        continue
                    bloque_conflicto = (
                        g.get("codigo_sis"), g.get("grupo"), "AUX",
                        ha.get("dia"), ha.get("hora_inicio"), ha.get("hora_fin"),
                    ) in conflicto
                    if bloque_conflicto:
                        bg, bd = _ROJO
                        texto = "#ffffff"
                    else:
                        bg, bd = colores.get(clave, _color_pastel(g.get("codigo_sis", "")))
                        texto = "#1f2937"
                    eventos.append({
                        "title": "AUX %s (G%s)" % (g.get("nombre", "?"), g.get("grupo", "?")),
                        "startRecur": "2026-08-17",
                        "endRecur": "2026-12-19",
                        "startTime": ha.get("hora_inicio"),
                        "endTime": ha.get("hora_fin"),
                        "daysOfWeek": [_DIAS_MAP_NUM[dia_semana]],
                        "backgroundColor": bg,
                        "borderColor": bd,
                        "textColor": texto,
                        "extendedProps": {
                            "tipo": "AUX",
                            "nombre": g.get("nombre", "?"),
                            "aula": ha.get("aula", "-"),
                            "grupo": g.get("grupo"),
                            "codigo": g.get("codigo_sis"),
                            "conflicto": bloque_conflicto,
                            "docente_aux": aux.get("nombre", "?"),
                        },
                    })

    return eventos


def construir_resumen_kardex(kardex):
    """Construye el resumen del kardex para la interfaz web.
    Reutiliza la logica existente de importador_kardex (determinar_estado_materia)
    y el mapa de materias del motor para mostrar nombres."""
    from importador_kardex import (
        determinar_estado_materia,
        ESTADO_APROBADA, ESTADO_REPROBADA, ESTADO_EN_CURSO,
        ESTADO_ABANDONADA, ESTADO_SIN_HISTORIAL,
    )

    motor = get_motor()
    mapa = motor.get("mapa_prereq", {})

    detalle = []
    contadores = {
        ESTADO_APROBADA: 0, ESTADO_REPROBADA: 0, ESTADO_EN_CURSO: 0,
        ESTADO_ABANDONADA: 0, ESTADO_SIN_HISTORIAL: 0,
    }
    provisionales = 0

    for codigo in sorted(kardex["intentos"].keys()):
        r = determinar_estado_materia(codigo, kardex)
        estado = r["estado"]
        contadores[estado] = contadores.get(estado, 0) + 1
        if r.get("provisional"):
            provisionales += 1

        intentos = kardex["intentos"].get(codigo, [])
        ultimo = None
        if intentos:
            ultimo = max(
                intentos,
                key=lambda x: (x.get("anio") or 0, x.get("gestion") or 0),
            )

        nombre = mapa.get(codigo, {}).get("materia", "?")
        detalle.append({
            "codigo": codigo,
            "nombre": nombre,
            "estado": estado,
            "nota": (ultimo or {}).get("nfin"),
            "anio": (ultimo or {}).get("anio"),
            "gestion": (ultimo or {}).get("gestion"),
            "tipo_periodo": (ultimo or {}).get("tipo_periodo"),
            "modalidad": (ultimo or {}).get("modalidad"),
            "origen_manual": any(i.get("origen_manual") for i in intentos),
            "origen_pdf": any(i.get("origen", "pdf") == "pdf"
                               and not i.get("origen_manual") for i in intentos),
        })

    return {
        "aprobadas": contadores.get(ESTADO_APROBADA, 0),
        "reprobadas": contadores.get(ESTADO_REPROBADA, 0),
        "en_curso": contadores.get(ESTADO_EN_CURSO, 0),
        "abandonadas": contadores.get(ESTADO_ABANDONADA, 0),
        "sin_historial": contadores.get(ESTADO_SIN_HISTORIAL, 0),
        "provisionales": provisionales,
        "materias_unicas": len(kardex["intentos"]),
        "total_intentos": sum(len(v) for v in kardex["intentos"].values()),
        "codigos_desconocidos": len(kardex["codigos_desconocidos"]),
        "inconsistencias": len(kardex["inconsistencias"]),
        "detalle": detalle,
    }
