"""
Tests del planificador.
Valida limites, conflictos, AUX, calendario compacto.
Utiliza datos reales del motor + datos sinteticos para casos especificos.
NO modifica Excel ni PDF.
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "modulos"))

from planificador import (
    crear_planificador, seleccionar_grupo, eliminar_grupo,
    detectar_conflicto, limites, calendario_compacto,
    _es_mesa, _horarios_superpuestos, _contar_seleccionados,
    LIMITE_REGULAR_NORMAL, LIMITE_REGULAR_MESA, LIMITE_INTERSEMESTRAL,
)


def _grupo_mock(codigo, grupo, dia, h_ini, h_fin, aula="E530",
                docente="DOCENTE TEST", aux=None, modalidad="N"):
    g = {
        "codigo_sis": codigo,
        "nivel": "A",
        "grupo": grupo,
        "docente": docente,
        "nombre": "MATERIA TEST " + codigo,
        "auxiliares": aux or [],
        "horarios": [{"dia": dia, "hora_inicio": h_ini, "hora_fin": h_fin,
                      "aula": aula, "modalidad": modalidad}],
        "anio": 2026,
        "gestion": 2,
        "tipo_periodo": "semestre regular",
    }
    return g


def _grupo_multi(codigo, grupo, horarios_list, docente="DOCENTE TEST", aux=None):
    return {
        "codigo_sis": codigo,
        "nivel": "A",
        "grupo": grupo,
        "docente": docente,
        "nombre": "MATERIA TEST " + codigo,
        "auxiliares": aux or [],
        "horarios": horarios_list,
        "anio": 2026,
        "gestion": 2,
        "tipo_periodo": "semestre regular",
    }


def _h(dia, i, f):
    return {"dia": dia, "hora_inicio": i, "hora_fin": f, "aula": "E530"}


def test_seleccionar_grupo_basico():
    plan = crear_planificador(gestion=2, anio=2026)
    g1 = _grupo_mock("1304001", "01", "LU", "08:15", "09:45")
    ok, msg = seleccionar_grupo(plan, g1, None)
    assert ok, "Deberia aceptar: %s" % msg
    assert len(plan["grupos_seleccionados"]) == 1
    assert "1304001" in plan["materias_seleccionadas"]
    print("PASS: test_seleccionar_grupo_basico")


def test_cambiar_grupo():
    plan = crear_planificador(gestion=2, anio=2026)
    g1a = _grupo_mock("1304001", "01", "LU", "08:15", "09:45")
    g1b = _grupo_mock("1304001", "02", "MA", "10:00", "11:30")
    seleccionar_grupo(plan, g1a, None)
    ok, msg = seleccionar_grupo(plan, g1b, None)
    assert ok, "Deberia aceptar segundo grupo de otra seccion: %s" % msg
    assert len(plan["grupos_seleccionados"]) == 2
    assert "1304001" in plan["materias_seleccionadas"]
    print("PASS: test_cambiar_grupo")


def test_eliminar_grupo():
    plan = crear_planificador(gestion=2, anio=2026)
    g1 = _grupo_mock("1304001", "01", "LU", "08:15", "09:45")
    g2 = _grupo_mock("1304002", "01", "MA", "10:00", "11:30")
    seleccionar_grupo(plan, g1, None)
    seleccionar_grupo(plan, g2, None)
    assert len(plan["grupos_seleccionados"]) == 2

    ok, msg = eliminar_grupo(plan, "1304001", "01")
    assert ok, "Deberia eliminar: %s" % msg
    assert len(plan["grupos_seleccionados"]) == 1
    assert "1304001" not in plan["materias_seleccionadas"]
    assert "1304002" in plan["materias_seleccionadas"]
    print("PASS: test_eliminar_grupo")


def test_eliminar_grupo_inexistente():
    plan = crear_planificador(gestion=2, anio=2026)
    ok, msg = eliminar_grupo(plan, "9999999", "01")
    assert not ok
    assert "no encontrado" in msg.lower()
    print("PASS: test_eliminar_grupo_inexistente")


def test_limite_8_normales():
    plan = crear_planificador(gestion=2, anio=2026)
    for i in range(LIMITE_REGULAR_NORMAL):
        cod = "1304%03d" % (i + 1)
        g = _grupo_mock(cod, "01", "LU", "08:00", "09:30")
        horarios = [{"dia": ["LU", "MA", "MI", "JU", "VI", "SA", "LU"][i % 7],
                     "hora_inicio": "%02d:00" % (8 + i),
                     "hora_fin": "%02d:30" % (9 + i),
                     "aula": "E530"}]
        g["horarios"] = horarios
        ok, msg = seleccionar_grupo(plan, g, None)
        assert ok, "Grupo %d deberia aceptarse: %s" % (i + 1, msg)

    g_nueva = _grupo_mock("1304999", "01", "SA", "08:00", "09:30")
    g_nueva["horarios"] = [{"dia": "SA", "hora_inicio": "08:00",
                            "hora_fin": "09:30", "aula": "E530"}]
    ok, msg = seleccionar_grupo(plan, g_nueva, None)
    assert ok, "La novena materia deberia aceptarse con advertencia no bloqueante: %s" % msg
    assert len(plan["grupos_seleccionados"]) == LIMITE_REGULAR_NORMAL + 1
    advs = [a for a in plan.get("advertencias", [])
            if "8 materias" in a.get("mensaje", "")]
    assert len(advs) >= 1, "Deberia registrarse la advertencia de >8 materias"
    print("PASS: test_limite_8_normales (advertencia no bloqueante)")


def test_limite_2_mesa():
    plan = crear_planificador(gestion=2, anio=2026)
    g1 = _grupo_mock("1304001", "01", "LU", "08:00", "09:30", modalidad="E")
    g2 = _grupo_mock("1304002", "01", "MA", "08:00", "09:30", modalidad="E")
    ok1, _ = seleccionar_grupo(plan, g1, None)
    ok2, _ = seleccionar_grupo(plan, g2, None)
    assert ok1 and ok2
    assert _contar_seleccionados(plan) == (0, 2)

    g3 = _grupo_mock("1304003", "01", "MI", "08:00", "09:30", modalidad="E")
    ok3, msg3 = seleccionar_grupo(plan, g3, None)
    assert not ok3
    assert "mesa" in msg3.lower()
    print("PASS: test_limite_2_mesa")


def test_limite_intersemestral():
    plan = crear_planificador(gestion=3, anio=2026)
    g1 = _grupo_mock("1304001", "01", "LU", "08:00", "09:30")
    g2 = _grupo_mock("1304002", "01", "MA", "08:00", "09:30")
    ok1, _ = seleccionar_grupo(plan, g1, None)
    ok2, _ = seleccionar_grupo(plan, g2, None)
    assert ok1 and ok2

    g3 = _grupo_mock("1304003", "01", "MI", "08:00", "09:30")
    ok3, msg3 = seleccionar_grupo(plan, g3, None)
    assert not ok3
    assert "2" in msg3
    print("PASS: test_limite_intersemestral")


def test_conflicto_horario():
    plan = crear_planificador(gestion=2, anio=2026)
    g1 = _grupo_mock("1304001", "01", "LU", "08:15", "09:45")
    g2 = _grupo_mock("1304002", "01", "LU", "09:00", "10:30")
    seleccionar_grupo(plan, g1, None)
    seleccionar_grupo(plan, g2, None)
    conflictos = detectar_conflicto(plan)
    assert len(conflictos) == 1
    c = conflictos[0]
    assert c["dia"] == "LU"
    assert c["materia1"] == "1304001"
    assert c["materia2"] == "1304002"
    print("PASS: test_conflicto_horario")


def test_no_conflicto_consecutivo():
    plan = crear_planificador(gestion=2, anio=2026)
    g1 = _grupo_mock("1304001", "01", "LU", "12:45", "14:15")
    g2 = _grupo_mock("1304002", "01", "LU", "14:15", "15:45")
    seleccionar_grupo(plan, g1, None)
    seleccionar_grupo(plan, g2, None)
    conflictos = detectar_conflicto(plan)
    assert len(conflictos) == 0
    print("PASS: test_no_conflicto_consecutivo")


def test_conflicto_aux_habilitado():
    plan = crear_planificador(gestion=2, anio=2026)
    plan["modo_aux"] = True
    aux = {"nombre": "AUX TEST", "horarios": [
        {"dia": "LU", "hora_inicio": "10:00", "hora_fin": "11:30", "aula": "E520"}
    ]}
    g1 = _grupo_mock("1304001", "01", "LU", "08:00", "09:30", aux=[aux])
    g2 = _grupo_mock("1304002", "01", "LU", "10:00", "11:30")
    seleccionar_grupo(plan, g1, None)
    seleccionar_grupo(plan, g2, None)
    conflictos = detectar_conflicto(plan)
    aux_conflictos = [c for c in conflictos if c["tipo1"] == "AUX" or c["tipo2"] == "AUX"]
    assert len(aux_conflictos) > 0
    print("PASS: test_conflicto_aux_habilitado")


def test_no_conflicto_aux_deshabilitado():
    plan = crear_planificador(gestion=2, anio=2026)
    plan["modo_aux"] = False
    aux = {"nombre": "AUX TEST", "horarios": [
        {"dia": "LU", "hora_inicio": "10:00", "hora_fin": "11:30", "aula": "E520"}
    ]}
    g1 = _grupo_mock("1304001", "01", "LU", "08:00", "09:30", aux=[aux])
    g2 = _grupo_mock("1304002", "01", "LU", "10:00", "11:30")
    seleccionar_grupo(plan, g1, None)
    seleccionar_grupo(plan, g2, None)
    conflictos = detectar_conflicto(plan)
    assert len(conflictos) == 0
    print("PASS: test_no_conflicto_aux_deshabilitado")


def test_calendario_dias_utilizados():
    plan = crear_planificador(gestion=2, anio=2026)
    g1 = _grupo_mock("1304001", "01", "LU", "08:00", "09:30")
    g2 = _grupo_mock("1304002", "01", "MI", "10:00", "11:30")
    seleccionar_grupo(plan, g1, None)
    seleccionar_grupo(plan, g2, None)
    cal = calendario_compacto(plan)
    assert "LU" in cal["dias"]
    assert "MI" in cal["dias"]
    assert "MA" not in cal["dias"]
    assert "JU" not in cal["dias"]
    print("PASS: test_calendario_dias_utilizados")


def test_calendario_primera_ultima_hora():
    plan = crear_planificador(gestion=2, anio=2026)
    g1 = _grupo_multi("1304001", "01", [
        _h("LU", "12:45", "14:15"),
        _h("MI", "12:45", "14:15"),
    ])
    g2 = _grupo_multi("1304002", "01", [
        _h("MA", "18:30", "20:00"),
        _h("JU", "18:30", "20:00"),
    ])
    seleccionar_grupo(plan, g1, None)
    seleccionar_grupo(plan, g2, None)
    cal = calendario_compacto(plan)
    assert cal["hora_inicio"] == "12:45"
    assert cal["hora_fin"] == "20:00"
    print("PASS: test_calendario_primera_ultima_hora")


def test_calendario_mantiene_huecos():
    plan = crear_planificador(gestion=2, anio=2026)
    g1 = _grupo_multi("1304001", "01", [
        _h("LU", "08:00", "09:30"),
        _h("MI", "08:00", "09:30"),
    ])
    g2 = _grupo_multi("1304002", "01", [
        _h("LU", "14:00", "15:30"),
        _h("MI", "14:00", "15:30"),
    ])
    seleccionar_grupo(plan, g1, None)
    seleccionar_grupo(plan, g2, None)
    cal = calendario_compacto(plan)
    libres_lu = [l for l in cal["libres"] if l["dia"] == "LU"]
    assert len(libres_lu) == 1
    assert libres_lu[0]["hora_inicio"] == "09:30"
    assert libres_lu[0]["hora_fin"] == "14:00"
    print("PASS: test_calendario_mantiene_huecos")


def test_materias_varios_grupos():
    plan = crear_planificador(gestion=2, anio=2026)
    g1a = _grupo_mock("1304001", "01", "LU", "08:00", "09:30")
    g1b = _grupo_mock("1304001", "02", "MA", "10:00", "11:30")
    seleccionar_grupo(plan, g1a, None)
    seleccionar_grupo(plan, g1b, None)
    assert len(plan["grupos_seleccionados"]) == 2
    assert plan["materias_seleccionadas"].count("1304001") == 0 or \
           len([g for g in plan["grupos_seleccionados"] if g["codigo_sis"] == "1304001"]) == 2
    assert "1304001" in plan["materias_seleccionadas"]
    print("PASS: test_materias_varios_grupos")


def test_grupos_duplicados():
    plan = crear_planificador(gestion=2, anio=2026)
    g1 = _grupo_mock("1304001", "01", "LU", "08:00", "09:30")
    seleccionar_grupo(plan, g1, None)
    ok, msg = seleccionar_grupo(plan, g1, None)
    assert not ok
    assert "ya esta seleccionado" in msg.lower() or "ya seleccionado" in msg.lower()
    print("PASS: test_grupos_duplicados")


def test_sabado_no_aparece_si_no_hay():
    plan = crear_planificador(gestion=2, anio=2026)
    g1 = _grupo_mock("1304001", "01", "LU", "08:00", "09:30")
    seleccionar_grupo(plan, g1, None)
    cal = calendario_compacto(plan)
    assert "SA" not in cal["dias"]
    print("PASS: test_sabado_no_aparece_si_no_hay")


def test_plan_vacio_calendario():
    plan = crear_planificador(gestion=2, anio=2026)
    cal = calendario_compacto(plan)
    assert cal["dias"] == []
    assert cal["hora_inicio"] is None
    assert cal["hora_fin"] is None
    assert cal["bloques"] == []
    assert cal["libres"] == []
    print("PASS: test_plan_vacio_calendario")


def test_eliminar_ultima_materia_limpia_lista():
    plan = crear_planificador(gestion=2, anio=2026)
    g1 = _grupo_mock("1304001", "01", "LU", "08:00", "09:30")
    seleccionar_grupo(plan, g1, None)
    assert "1304001" in plan["materias_seleccionadas"]
    eliminar_grupo(plan, "1304001", "01")
    assert "1304001" not in plan["materias_seleccionadas"]
    print("PASS: test_eliminar_ultima_materia_limpia_lista")


if __name__ == "__main__":
    tests = [
        test_seleccionar_grupo_basico,
        test_cambiar_grupo,
        test_eliminar_grupo,
        test_eliminar_grupo_inexistente,
        test_limite_8_normales,
        test_limite_2_mesa,
        test_limite_intersemestral,
        test_conflicto_horario,
        test_no_conflicto_consecutivo,
        test_conflicto_aux_habilitado,
        test_no_conflicto_aux_deshabilitado,
        test_calendario_dias_utilizados,
        test_calendario_primera_ultima_hora,
        test_calendario_mantiene_huecos,
        test_materias_varios_grupos,
        test_grupos_duplicados,
        test_sabado_no_aparece_si_no_hay,
        test_plan_vacio_calendario,
        test_eliminar_ultima_materia_limpia_lista,
    ]

    passed = 0
    failed = 0
    for test in tests:
        try:
            test()
            passed += 1
        except Exception as e:
            print("FAIL: %s - %s" % (test.__name__, str(e)))
            failed += 1

    print("")
    print("=" * 60)
    print("RESULTADOS PLANIFICADOR: %d passed, %d failed, %d total" % (
        passed, failed, len(tests)))
    if failed == 0:
        print("TODOS LOS TESTS PASARON CORRECTAMENTE")
    else:
        print("ALGUNOS TESTS FALLARON")
    print("=" * 60)
