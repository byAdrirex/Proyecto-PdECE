"""
Planificador de horario academico.
Dos modos:
  "academico" — utiliza kardex, prerrequisitos, restricciones academicas.
  "manual" — sin kardex, permite seleccionar materias ofertadas libremente,
             solo advertencias informativas sobre prerrequisitos.
Detecta conflictos, respeta limites, genera calendario compacto.
NO crea interfaz grafica, NO modifica archivos originales.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


MODO_ACADEMICO = "academico"
MODO_MANUAL = "manual"

LIMITE_REGULAR_NORMAL = 8
LIMITE_REGULAR_MESA = 2
LIMITE_INTERSEMESTRAL = 2

DIAS_ORDEN = ["LU", "MA", "MI", "JU", "VI", "SA"]

NIVELES_VALIDOS = ["A", "B", "C", "D", "E", "F", "G", "H", "I"]


def crear_planificador(gestion=None, anio=None, modo=MODO_ACADEMICO):
    if modo not in (MODO_ACADEMICO, MODO_MANUAL):
        raise ValueError("Modo invalido: %s. Use 'academico' o 'manual'." % modo)
    return {
        "modo": modo,
        "materias_seleccionadas": [],
        "grupos_seleccionados": [],
        "modo_aux": True,
        "conflictos": [],
        "advertencias": [],
        "gestion": gestion,
        "anio": anio,
    }


def _tiene_oferta(motor):
    return motor.get("oferta") is not None


def _indice_oferta(motor):
    if not _tiene_oferta(motor):
        return {}
    return motor["oferta"]["indice"]


def materias_ofertadas(motor):
    indice = _indice_oferta(motor)
    resultado = {}
    for codigo, grupos in indice.items():
        if grupos:
            nombre = grupos[0].get("nombre", "?")
            nivel = grupos[0].get("nivel", "?")
            resultado[codigo] = {"nombre": nombre, "nivel": nivel, "grupos": len(grupos)}
    return resultado


def materias_por_nivel(nivel, motor):
    nivel = str(nivel).upper()
    indice = _indice_oferta(motor)
    resultado = {}
    for codigo, grupos in indice.items():
        grupos_nivel = [g for g in grupos if g.get("nivel") == nivel]
        if grupos_nivel:
            nombre = grupos_nivel[0].get("nombre", "?")
            resultado[codigo] = {"nombre": nombre, "nivel": nivel, "grupos": grupos_nivel}
    return resultado


def grupos_de_materia(codigo, motor):
    codigo = str(codigo)
    indice = _indice_oferta(motor)
    grupos = indice.get(codigo, [])
    if grupos:
        return grupos
    from motor_academico import determinar_estado_materia_completo
    info = determinar_estado_materia_completo(codigo, motor)
    return info.get("grupos", [])


def verificar_prerequisitos(codigo, motor):
    codigo = str(codigo)
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
    return {
        "tiene_prerequisitos": True,
        "prerrequisitos": nombres,
    }


def _es_mesa(grupo):
    for h in grupo.get("horarios", []):
        if h.get("modalidad") == "E":
            return True
    return False


def _contar_seleccionados(plan):
    normal = 0
    mesa = 0
    for g in plan["grupos_seleccionados"]:
        if _es_mesa(g):
            mesa += 1
        else:
            normal += 1
    return normal, mesa


def limites(plan):
    gestion = plan.get("gestion")
    if gestion in (1, 2):
        tipo = "semestre regular"
        n_max = LIMITE_REGULAR_NORMAL
        m_max = LIMITE_REGULAR_MESA
    elif gestion in (3, 4):
        tipo = "intersemestral"
        n_max = LIMITE_INTERSEMESTRAL
        m_max = 0
    else:
        return None

    normal, mesa = _contar_seleccionados(plan)
    return {
        "tipo": tipo,
        "normal_max": n_max,
        "mesa_max": m_max,
        "normal_usados": normal,
        "mesa_usados": mesa,
        "normal_disponibles": max(0, n_max - normal),
        "mesa_disponibles": max(0, m_max - mesa),
    }


def _verificar_limite(plan, es_mesa):
    gestion = plan.get("gestion")
    if gestion in (1, 2):
        n_max = LIMITE_REGULAR_NORMAL
        m_max = LIMITE_REGULAR_MESA
    elif gestion in (3, 4):
        n_max = LIMITE_INTERSEMESTRAL
        m_max = 0
    else:
        return None, None

    normal, mesa = _contar_seleccionados(plan)
    if es_mesa:
        if mesa >= m_max:
            return False, "Ya tienes %d materias de mesa (maximo %d)." % (mesa, m_max)
    else:
        if normal >= n_max:
            return False, "Ya tienes %d materias normales seleccionadas (maximo %d)." % (normal, n_max)
    return True, None


def _horarios_superpuestos(h1, h2):
    if h1.get("dia") != h2.get("dia"):
        return False
    i1 = h1.get("hora_inicio", "99:99")
    f1 = h1.get("hora_fin", "00:00")
    i2 = h2.get("hora_inicio", "99:99")
    f2 = h2.get("hora_fin", "00:00")
    return i1 < f2 and i2 < f1


def detectar_conflicto(plan):
    conflictos = []
    grupos = plan["grupos_seleccionados"]
    modo_aux = plan.get("modo_aux", True)

    for i in range(len(grupos)):
        for j in range(i + 1, len(grupos)):
            g1 = grupos[i]
            g2 = grupos[j]
            if g1["codigo_sis"] == g2["codigo_sis"] and g1["grupo"] == g2["grupo"]:
                continue

            horarios_g1 = []
            for h in g1.get("horarios", []):
                horarios_g1.append({"dia": h["dia"], "hora_inicio": h["hora_inicio"],
                                    "hora_fin": h["hora_fin"], "tipo": "CLASE"})
            if modo_aux:
                for aux in g1.get("auxiliares", []):
                    for ha in aux.get("horarios", []):
                        horarios_g1.append({"dia": ha["dia"], "hora_inicio": ha["hora_inicio"],
                                            "hora_fin": ha["hora_fin"], "tipo": "AUX"})

            horarios_g2 = []
            for h in g2.get("horarios", []):
                horarios_g2.append({"dia": h["dia"], "hora_inicio": h["hora_inicio"],
                                    "hora_fin": h["hora_fin"], "tipo": "CLASE"})
            if modo_aux:
                for aux in g2.get("auxiliares", []):
                    for ha in aux.get("horarios", []):
                        horarios_g2.append({"dia": ha["dia"], "hora_inicio": ha["hora_inicio"],
                                            "hora_fin": ha["hora_fin"], "tipo": "AUX"})

            for hg1 in horarios_g1:
                for hg2 in horarios_g2:
                    if _horarios_superpuestos(hg1, hg2):
                        conflictos.append({
                            "materia1": g1["codigo_sis"],
                            "grupo1": g1["grupo"],
                            "materia2": g2["codigo_sis"],
                            "grupo2": g2["grupo"],
                            "dia": hg1["dia"],
                            "hora_inicio1": hg1["hora_inicio"],
                            "hora_fin1": hg1["hora_fin"],
                            "tipo1": hg1["tipo"],
                            "hora_inicio2": hg2["hora_inicio"],
                            "hora_fin2": hg2["hora_fin"],
                            "tipo2": hg2["tipo"],
                        })

    plan["conflictos"] = conflictos
    return conflictos


_DIAS_NOMBRE = {
    "LU": "Lunes", "MA": "Martes", "MI": "Miercoles",
    "JU": "Jueves", "VI": "Viernes", "SA": "Sabado",
}


def _horarios_de_grupo(grupo, modo_aux=True):
    bloques = []
    for h in grupo.get("horarios", []):
        bloques.append({
            "dia": h.get("dia"), "hora_inicio": h.get("hora_inicio"),
            "hora_fin": h.get("hora_fin"), "tipo": "CLASE",
        })
    if modo_aux:
        for aux in grupo.get("auxiliares", []):
            for ha in aux.get("horarios", []):
                bloques.append({
                    "dia": ha.get("dia"), "hora_inicio": ha.get("hora_inicio"),
                    "hora_fin": ha.get("hora_fin"), "tipo": "AUX",
                })
    return bloques


def _conflictos_grupo_con_seleccion(plan, grupo):
    modo_aux = plan.get("modo_aux", True)
    seleccionados = plan.get("grupos_seleccionados", [])
    bloques_g = _horarios_de_grupo(grupo, modo_aux)
    conflictos = []
    for sel in seleccionados:
        if (sel.get("codigo_sis") == grupo.get("codigo_sis")
                and sel.get("grupo") == grupo.get("grupo")):
            continue
        bloques_sel = _horarios_de_grupo(sel, modo_aux)
        for hg in bloques_g:
            for hs in bloques_sel:
                if _horarios_superpuestos(hg, hs):
                    conflictos.append({
                        "dia": hg["dia"],
                        "hora_inicio": hg["hora_inicio"],
                        "hora_fin": hg["hora_fin"],
                        "materia": sel.get("nombre", sel.get("codigo_sis")),
                        "codigo": sel.get("codigo_sis"),
                        "grupo": sel.get("grupo"),
                        "tipo": hg.get("tipo", "CLASE"),
                        "tipo_sel": hs.get("tipo", "CLASE"),
                    })
    return conflictos


def _horas_muertas_minutos(bloques):
    por_dia = {}
    for b in bloques:
        ini = _parsear_hora(b.get("hora_inicio"))
        fin = _parsear_hora(b.get("hora_fin"))
        if ini is None or fin is None:
            continue
        por_dia.setdefault(b["dia"], []).append((ini, fin))
    total = 0
    for dia, spans in por_dia.items():
        spans.sort()
        for k in range(len(spans) - 1):
            gap = spans[k + 1][0] - spans[k][1]
            if gap > 0:
                total += gap
    return total


def recomendar_grupo(plan, grupo, motor=None):
    """Calcula una recomendacion informativa para un grupo candidato
    en funcion de la seleccion actual. NO bloquea la seleccion.
    Reutiliza las claves existentes del planificador:
      _recomendado, _calificacion_recomendacion, _comentario_recomendacion.
    Puntuacion (0-100) basada solo en datos objetivos existentes."""
    modo = plan.get("modo", MODO_ACADEMICO)
    modo_aux = plan.get("modo_aux", True)
    conflictos = _conflictos_grupo_con_seleccion(plan, grupo)

    n_clase = sum(1 for c in conflictos if c["tipo"] == "CLASE" and c["tipo_sel"] == "CLASE")
    n_aux = len(conflictos) - n_clase

    puntaje = 90
    puntaje -= 25 * n_clase
    puntaje -= 12 * n_aux

    bloques_actuales = []
    for sel in plan.get("grupos_seleccionados", []):
        bloques_actuales += _horarios_de_grupo(sel, modo_aux)
    bloques_con = bloques_actuales + _horarios_de_grupo(grupo, modo_aux)
    delta_muertas = _horas_muertas_minutos(bloques_con) - _horas_muertas_minutos(bloques_actuales)
    if delta_muertas < 0:
        puntaje += 5
    elif delta_muertas > 0:
        puntaje -= min(10, delta_muertas // 120)

    dias = set(b["dia"] for b in bloques_con)
    if len(dias) > 4:
        puntaje -= (len(dias) - 4) * 5

    if grupo.get("auxiliares"):
        puntaje += 3

    estado = None
    if modo == MODO_ACADEMICO and motor is not None:
        from motor_academico import determinar_estado_materia_completo
        info = determinar_estado_materia_completo(grupo["codigo_sis"], motor)
        estado = info.get("estado")

    puntaje = max(0, min(100, int(round(puntaje))))

    if puntaje >= 80:
        etiqueta = "RECOMENDADO"
        recomendado = True
    elif puntaje >= 55:
        etiqueta = "ALTERNATIVA"
        recomendado = None
    else:
        etiqueta = "CONFLICTO"
        recomendado = False

    partes = []
    if not conflictos:
        partes.append("Sin conflictos con tu seleccion actual.")
        if len(dias) <= 3:
            partes.append("Distribucion equilibrada de horarios.")
        if delta_muertas < 0:
            partes.append("Reduce horas muertas de tu horario.")
        if grupo.get("auxiliares"):
            partes.append("Dispone de auxiliar.")
    else:
        for c in conflictos[:3]:
            dia_nombre = _DIAS_NOMBRE.get(c["dia"], c["dia"])
            partes.append(
                "Coincide con %s (G%s) el %s %s-%s." % (
                    c["materia"], c["grupo"], dia_nombre,
                    c["hora_inicio"], c["hora_fin"]))
        if len(conflictos) > 3:
            partes.append("Y %d choque(s) mas." % (len(conflictos) - 3))
        if grupo.get("auxiliares"):
            partes.append("Dispone de auxiliar.")
    if estado == "REPROBADA":
        partes.append("Reprobada en tu historial: puedes volver a cursarla.")
    if estado == "EN_CURSO":
        partes.append("Materia en curso en la gestion actual.")

    return {
        "_recomendado": recomendado,
        "_calificacion_recomendacion": puntaje,
        "_comentario_recomendacion": " ".join(partes) or "Seleccion posible.",
        "etiqueta": etiqueta,
        "conflictos": conflictos,
        "n_conflictos": len(conflictos),
    }


def horas_semanales(plan):
    total = 0
    modo_aux = plan.get("modo_aux", True)
    for g in plan.get("grupos_seleccionados", []):
        for h in g.get("horarios", []):
            ini = _parsear_hora(h.get("hora_inicio"))
            fin = _parsear_hora(h.get("hora_fin"))
            if ini is not None and fin is not None:
                total += (fin - ini)
        if modo_aux:
            for aux in g.get("auxiliares", []):
                for ha in aux.get("horarios", []):
                    ini = _parsear_hora(ha.get("hora_inicio"))
                    fin = _parsear_hora(ha.get("hora_fin"))
                    if ini is not None and fin is not None:
                        total += (fin - ini)
    return total / 60.0


def seleccionar_grupo(plan, grupo, motor):
    codigo = grupo["codigo_sis"]
    num_grupo = grupo["grupo"]
    modo = plan.get("modo", MODO_ACADEMICO)

    for g in plan["grupos_seleccionados"]:
        if g["codigo_sis"] == codigo and g["grupo"] == num_grupo:
            return False, "El grupo %s de %s ya esta seleccionado." % (num_grupo, codigo)

    advertencias_grupo = []

    if modo == MODO_ACADEMICO and motor is not None:
        from motor_academico import determinar_estado_materia_completo
        info_estado = determinar_estado_materia_completo(codigo, motor)
        estado = info_estado.get("estado", "")
        if estado == "APROBADA":
            advertencias_grupo.append(
                "Esta materia ya esta aprobada en tu historial."
            )
        elif estado == "BLOQUEADA":
            faltan = info_estado.get("faltan", [])
            nombres_faltan = []
            mapa = motor.get("mapa_prereq", {})
            for f in faltan:
                nf = mapa.get(f, {}).get("materia", f)
                nombres_faltan.append("%s (%s)" % (f, nf))
            return False, (
                "Materia bloqueada. Faltan prerrequisitos: %s"
                % ", ".join(nombres_faltan)
            )

    if modo == MODO_MANUAL and motor is not None:
        prereq_info = verificar_prerequisitos(codigo, motor)
        if prereq_info and prereq_info["tiene_prerequisitos"]:
            nombres = [p["materia"] for p in prereq_info["prerrequisitos"]]
            advertencias_grupo.append(
                "Esta materia tiene prerrequisitos. "
                "En modo manual no se verificara tu historial academico. "
                "Prerrequisitos: %s" % ", ".join(nombres)
            )

    es_mesa = _es_mesa(grupo)
    gestion = plan.get("gestion")
    ok, msg = _verificar_limite(plan, es_mesa)
    if not ok:
        if es_mesa or gestion in (3, 4):
            return False, msg
        plan["advertencias"].append({
            "codigo": codigo,
            "grupo": num_grupo,
            "mensaje": ("Has superado las 8 materias recomendadas para un "
                        "semestre regular. Puedes continuar, pero ten en "
                        "cuenta la carga academica."),
        })

    grupo_con_meta = dict(grupo)
    grupo_con_meta["_recomendado"] = None
    grupo_con_meta["_calificacion_recomendacion"] = None
    grupo_con_meta["_comentario_recomendacion"] = None

    plan["grupos_seleccionados"].append(grupo_con_meta)

    if codigo not in plan["materias_seleccionadas"]:
        plan["materias_seleccionadas"].append(codigo)

    for adv in advertencias_grupo:
        plan["advertencias"].append({
            "codigo": codigo,
            "grupo": num_grupo,
            "mensaje": adv,
        })

    detectar_conflicto(plan)
    return True, None


def eliminar_grupo(plan, codigo, num_grupo):
    codigo = str(codigo)
    encontrada = False
    for i, g in enumerate(plan["grupos_seleccionados"]):
        if g["codigo_sis"] == codigo and g["grupo"] == num_grupo:
            plan["grupos_seleccionados"].pop(i)
            encontrada = True
            break

    if not encontrada:
        return False, "Grupo %s de %s no encontrado en el horario." % (num_grupo, codigo)

    hay_otro = any(
        g["codigo_sis"] == codigo
        for g in plan["grupos_seleccionados"]
    )
    if not hay_otro:
        plan["materias_seleccionadas"] = [
            c for c in plan["materias_seleccionadas"] if c != codigo
        ]

    plan["advertencias"] = [
        a for a in plan["advertencias"]
        if not (a["codigo"] == codigo and a["grupo"] == num_grupo)
    ]

    detectar_conflicto(plan)
    return True, None


def _parsear_hora(hora_str):
    if not hora_str:
        return None
    partes = hora_str.split(":")
    return int(partes[0]) * 60 + int(partes[1])


def _formato_hora(minutos):
    return "%02d:%02d" % (minutos // 60, minutos % 60)


def calendario_compacto(plan):
    grupos = plan["grupos_seleccionados"]
    modo_aux = plan.get("modo_aux", True)

    bloques = []
    for g in grupos:
        codigo = g["codigo_sis"]
        num_grupo = g["grupo"]
        nombre = g.get("nombre", "?")
        docente = g.get("docente", "?")

        for h in g.get("horarios", []):
            bloques.append({
                "dia": h["dia"],
                "hora_inicio": h["hora_inicio"],
                "hora_fin": h["hora_fin"],
                "aula": h.get("aula", "-"),
                "codigo": codigo,
                "grupo": num_grupo,
                "materia": nombre,
                "docente": docente,
                "tipo": "CLASE",
            })

        if modo_aux:
            for aux in g.get("auxiliares", []):
                for ha in aux.get("horarios", []):
                    bloques.append({
                        "dia": ha["dia"],
                        "hora_inicio": ha["hora_inicio"],
                        "hora_fin": ha["hora_fin"],
                        "aula": ha.get("aula", "-"),
                        "codigo": codigo,
                        "grupo": num_grupo,
                        "materia": nombre,
                        "docente": aux.get("nombre", "?"),
                        "tipo": "AUX",
                    })

    if not bloques:
        return {
            "dias": [],
            "hora_inicio": None,
            "hora_fin": None,
            "bloques": [],
            "libres": [],
        }

    dias_usados = sorted(
        set(b["dia"] for b in bloques),
        key=lambda d: DIAS_ORDEN.index(d) if d in DIAS_ORDEN else 99,
    )

    horas_inicio = [_parsear_hora(b["hora_inicio"]) for b in bloques if b["hora_inicio"]]
    horas_fin = [_parsear_hora(b["hora_fin"]) for b in bloques if b["hora_fin"]]
    primera = min(horas_inicio) if horas_inicio else 0
    ultima = max(horas_fin) if horas_fin else 0

    libres = []
    for dia in dias_usados:
        bloques_dia = [b for b in bloques if b["dia"] == dia]
        horas_dia = []
        for b in bloques_dia:
            ini = _parsear_hora(b["hora_inicio"])
            fin = _parsear_hora(b["hora_fin"])
            horas_dia.append((ini, fin, b["tipo"]))

        horas_dia.sort(key=lambda x: x[0])

        for k in range(len(horas_dia) - 1):
            fin_actual = horas_dia[k][1]
            ini_siguiente = horas_dia[k + 1][0]
            if fin_actual < ini_siguiente:
                libres.append({
                    "dia": dia,
                    "hora_inicio": _formato_hora(fin_actual),
                    "hora_fin": _formato_hora(ini_siguiente),
                })

    return {
        "dias": dias_usados,
        "hora_inicio": _formato_hora(primera),
        "hora_fin": _formato_hora(ultima),
        "bloques": bloques,
        "libres": libres,
    }


def resumen_seleccion(plan, motor):
    mapa = motor["mapa_prereq"]
    grupos = plan["grupos_seleccionados"]
    modo = plan.get("modo", MODO_ACADEMICO)
    lineas = []
    lineas.append("Modo: %s" % modo.upper())
    lineas.append("Materias seleccionadas: %d" % len(plan["materias_seleccionadas"]))
    lim = limites(plan)
    if lim:
        lineas.append("Limite %s: %d/%d normales, %d/%d mesa" % (
            lim["tipo"], lim["normal_usados"], lim["normal_max"],
            lim["mesa_usados"], lim["mesa_max"]))

    conflictos = plan.get("conflictos", [])
    if conflictos:
        lineas.append("Conflictos detectados: %d" % len(conflictos))
    else:
        lineas.append("Sin conflictos")

    advertencias = plan.get("advertencias", [])
    if advertencias:
        lineas.append("Advertencias: %d" % len(advertencias))

    lineas.append("")
    for g in grupos:
        cod = g["codigo_sis"]
        nombre = mapa.get(cod, {}).get("materia", g.get("nombre", "?"))
        nivel = g.get("nivel", "?")
        auxs = g.get("auxiliares", [])
        aux_str = ""
        if auxs:
            aux_str = " AUX: %s" % ", ".join(a["nombre"] for a in auxs)
        horarios_str = " | ".join(
            "%s %s-%s %s" % (h["dia"], h["hora_inicio"], h["hora_fin"], h.get("aula", "-"))
            for h in g.get("horarios", [])
        )
        lineas.append("  [%s] %s %s G%s: %s%s" % (
            nivel, cod, nombre, g["grupo"], g.get("docente", "?"), aux_str))
        lineas.append("    %s" % horarios_str)

    return "\n".join(lineas)
