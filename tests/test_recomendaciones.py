"""
Tests del sistema de RECOMENDACIONES del planificador.
Principio: "El sistema recomienda; el estudiante decide."
La recomendacion es informativa y NUNCA bloquea la seleccion, salvo
restricciones academicas reales (aprobada, prerrequisito, datos invalidos).
Utiliza datos reales del motor + grupos sinteticos para casos especificos.
NO modifica Excel ni PDF.
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "modulos"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from planificador import (
    crear_planificador, seleccionar_grupo, eliminar_grupo,
    recomendar_grupo, horas_semanales,
    MODO_ACADEMICO, MODO_MANUAL,
)
from app import inicio as app_inicio


def _grupo_mock(codigo, grupo, dia, h_ini, h_fin, nombre="MATERIA TEST",
                docente="DOCENTE TEST", aux=None):
    return {
        "codigo_sis": codigo,
        "nivel": "A",
        "grupo": grupo,
        "docente": docente,
        "nombre": nombre + " " + codigo,
        "auxiliares": aux or [],
        "horarios": [{"dia": dia, "hora_inicio": h_ini, "hora_fin": h_fin,
                      "aula": "E530"}],
        "anio": 2026,
        "gestion": 2,
        "tipo_periodo": "semestre regular",
    }


def _grupo_multi(codigo, grupo, horarios_list, aux=None):
    return {
        "codigo_sis": codigo,
        "nivel": "A",
        "grupo": grupo,
        "docente": "DOCENTE TEST",
        "nombre": "MATERIA TEST " + codigo,
        "auxiliares": aux or [],
        "horarios": horarios_list,
        "anio": 2026,
        "gestion": 2,
        "tipo_periodo": "semestre regular",
    }


def _h(dia, i, f):
    return {"dia": dia, "hora_inicio": i, "hora_fin": f, "aula": "E530"}


def test_grupo_compatible_recibe_recomendacion():
    plan = crear_planificador(gestion=2, anio=2026, modo=MODO_MANUAL)
    g1 = _grupo_mock("1304001", "01", "LU", "08:15", "09:45")
    rec = recomendar_grupo(plan, g1, None)
    assert rec["_recomendado"] is True
    assert rec["_calificacion_recomendacion"] >= 80
    assert rec["n_conflictos"] == 0
    assert "Sin conflictos" in rec["_comentario_recomendacion"]
    print("PASS: test_grupo_compatible_recibe_recomendacion (puntaje %d)" % rec["_calificacion_recomendacion"])


def test_grupo_con_conflicto_recibe_advertencia():
    plan = crear_planificador(gestion=2, anio=2026, modo=MODO_MANUAL)
    g1 = _grupo_mock("1304001", "01", "LU", "08:15", "09:45")
    g2 = _grupo_mock("1304002", "01", "LU", "09:00", "10:30")
    seleccionar_grupo(plan, g1, None)

    rec = recomendar_grupo(plan, g2, None)
    assert rec["n_conflictos"] > 0
    assert rec["_recomendado"] is not True
    assert rec["_calificacion_recomendacion"] < 80
    assert "Coincide con" in rec["_comentario_recomendacion"]
    print("PASS: test_grupo_con_conflicto_recibe_advertencia (puntaje %d, conflictos %d)"
          % (rec["_calificacion_recomendacion"], rec["n_conflictos"]))


def test_conflicto_no_impide_seleccionar():
    plan = crear_planificador(gestion=2, anio=2026, modo=MODO_MANUAL)
    g1 = _grupo_mock("1304001", "01", "LU", "08:15", "09:45")
    g2 = _grupo_mock("1304002", "01", "LU", "09:00", "10:30")
    seleccionar_grupo(plan, g1, None)

    ok, msg = seleccionar_grupo(plan, g2, None)
    assert ok, "El conflicto no debe impedir seleccionar: %s" % msg
    assert len(plan["conflictos"]) > 0
    print("PASS: test_conflicto_no_impide_seleccionar")


def test_recomendacion_cambia_segun_seleccion():
    plan = crear_planificador(gestion=2, anio=2026, modo=MODO_MANUAL)
    g1 = _grupo_mock("1304001", "01", "LU", "08:15", "09:45")
    g2 = _grupo_mock("1304002", "01", "LU", "09:00", "10:30")

    rec_vacio = recomendar_grupo(plan, g2, None)
    assert rec_vacio["n_conflictos"] == 0
    assert rec_vacio["_recomendado"] is True

    seleccionar_grupo(plan, g1, None)
    rec_con = recomendar_grupo(plan, g2, None)
    assert rec_con["n_conflictos"] > 0
    assert rec_con["_calificacion_recomendacion"] < rec_vacio["_calificacion_recomendacion"]
    print("PASS: test_recomendacion_cambia_segun_seleccion (%d -> %d)"
          % (rec_vacio["_calificacion_recomendacion"], rec_con["_calificacion_recomendacion"]))


def test_manual_no_bloquea_por_prerequisitos():
    motor = app_inicio.get_motor()
    cod_bloqueado = None
    from motor_academico import determinar_estado_materia_completo
    for codigo in motor["mapa_prereq"]:
        if determinar_estado_materia_completo(codigo, motor)["estado"] == "BLOQUEADA":
            cod_bloqueado = codigo
            break
    if cod_bloqueado is None:
        print("PASS: test_manual_no_bloquea_por_prerequisitos (skipped)")
        return

    grupos = app_inicio.get_grupos_por_materia(cod_bloqueado)
    if not grupos:
        print("PASS: test_manual_no_bloquea_por_prerequisitos (skipped: sin grupos)")
        return

    plan = crear_planificador(gestion=2, anio=2026, modo=MODO_MANUAL)
    ok, msg = seleccionar_grupo(plan, grupos[0], motor)
    assert ok, "Manual no debe bloquear por prerrequisitos: %s" % msg

    rec = recomendar_grupo(plan, grupos[0], motor)
    assert "_calificacion_recomendacion" in rec
    print("PASS: test_manual_no_bloquea_por_prerequisitos (%s)" % cod_bloqueado)


def test_academico_mantiene_restricciones():
    motor = app_inicio.get_motor()
    cod_aprobada = "1304001"
    plan = crear_planificador(gestion=2, anio=2026, modo=MODO_ACADEMICO)
    grupos = app_inicio.get_grupos_por_materia(cod_aprobada)
    assert grupos

    from motor_academico import determinar_estado_materia_completo
    assert determinar_estado_materia_completo(cod_aprobada, motor)["estado"] == "APROBADA"

    rec = recomendar_grupo(plan, grupos[0], motor)
    assert "_calificacion_recomendacion" in rec

    cod_bloqueado = None
    for codigo in motor["mapa_prereq"]:
        if determinar_estado_materia_completo(codigo, motor)["estado"] == "BLOQUEADA":
            cod_bloqueado = codigo
            break
    if cod_bloqueado is None:
        print("PASS: test_academico_mantiene_restricciones (sin bloqueada, verificado aprobada)")
        return

    gb = app_inicio.get_grupos_por_materia(cod_bloqueado)
    if gb:
        ok, msg = seleccionar_grupo(plan, gb[0], motor)
        assert not ok, "Academico debe bloquear prerrequisito: %s" % msg
    print("PASS: test_academico_mantiene_restricciones")


def test_recomendacion_usa_datos_reales():
    motor = app_inicio.get_motor()
    plan = crear_planificador(gestion=2, anio=2026, modo=MODO_MANUAL)

    grupos = app_inicio.get_grupos_por_materia("1304001")
    assert len(grupos) >= 2

    g1 = grupos[0]
    g2 = grupos[1]

    rec = recomendar_grupo(plan, g1, motor)
    assert rec["_calificacion_recomendacion"] > 0
    assert "Sin conflictos" in rec["_comentario_recomendacion"]

    seleccionar_grupo(plan, g1, motor)
    rec2 = recomendar_grupo(plan, g2, motor)
    for c in rec2["conflictos"]:
        assert c["dia"] in ("LU", "MA", "MI", "JU", "VI", "SA")
        assert c["hora_inicio"] and c["hora_fin"]
    print("PASS: test_recomendacion_usa_datos_reales (%d grupos en oferta)" % len(grupos))


def test_eliminar_grupo_recalcula_recomendaciones():
    plan = crear_planificador(gestion=2, anio=2026, modo=MODO_MANUAL)
    g1 = _grupo_mock("1304001", "01", "LU", "08:15", "09:45")
    g2 = _grupo_mock("1304002", "01", "MA", "09:00", "10:30")
    g3 = _grupo_mock("1304003", "01", "MA", "09:30", "11:00")

    seleccionar_grupo(plan, g1, None)
    seleccionar_grupo(plan, g2, None)

    rec_antes = recomendar_grupo(plan, g3, None)
    assert rec_antes["n_conflictos"] > 0

    eliminar_grupo(plan, "1304002", "01")
    rec_despues = recomendar_grupo(plan, g3, None)
    assert rec_despues["n_conflictos"] == 0, "Al eliminar debe recalcularse"
    print("PASS: test_eliminar_grupo_recalcula_recomendaciones (%d -> %d conflictos)"
          % (rec_antes["n_conflictos"], rec_despues["n_conflictos"]))


def test_aux_no_rompe_recomendaciones():
    motor = app_inicio.get_motor()
    plan = crear_planificador(gestion=2, anio=2026, modo=MODO_MANUAL)

    aux = {"nombre": "AUX TEST",
           "horarios": [_h("LU", "10:00", "11:30")]}
    g1 = _grupo_mock("1304001", "01", "LU", "08:15", "09:45", aux=[aux])

    rec = recomendar_grupo(plan, g1, motor)
    assert "_calificacion_recomendacion" in rec
    assert "auxiliar" in rec["_comentario_recomendacion"].lower()

    ok, msg = seleccionar_grupo(plan, g1, motor)
    assert ok, "AUX no debe romper seleccion: %s" % msg
    assert horas_semanales(plan) > 0
    print("PASS: test_aux_no_rompe_recomendaciones (puntaje %d)" % rec["_calificacion_recomendacion"])


def test_todos_grupos_seleccionables_sin_restriccion():
    motor = app_inicio.get_motor()
    plan = crear_planificador(gestion=2, anio=2026, modo=MODO_MANUAL)

    grupos = app_inicio.get_grupos_por_materia("1304001")
    assert len(grupos) >= 2

    for g in grupos:
        ok, msg = seleccionar_grupo(plan, g, motor)
        assert ok, "Grupo G%s no deberia bloquearse: %s" % (g["grupo"], msg)
    assert len(plan["grupos_seleccionados"]) == len(grupos)
    print("PASS: test_todos_grupos_seleccionables_sin_restriccion (%d grupos)" % len(grupos))


def test_web_muestra_recomendaciones_en_grupos():
    from app import create_app
    app = create_app()
    client = app.test_client()
    client.post("/horario/parcial/seleccionar-modo", data={"modo": "manual"})

    resp = client.get("/horario/parcial/grupos/1304001")
    assert resp.status_code == 200
    assert b"RECOMENDADO" in resp.data
    assert b"/100" in resp.data
    print("PASS: test_web_muestra_recomendaciones_en_grupos")


def test_web_sidebar_muestra_resumen():
    from app import create_app
    app = create_app()
    client = app.test_client()
    client.post("/horario/parcial/seleccionar-modo", data={"modo": "manual"})
    client.post("/horario/parcial/seleccionar",
                data={"codigo_sis": "1304001", "grupo": "01"})

    resp = client.get("/horario/parcial/sidebar")
    assert resp.status_code == 200
    assert b"Horas semanales" in resp.data
    assert "D\u00edas ocupados".encode("utf-8") in resp.data
    print("PASS: test_web_sidebar_muestra_resumen")


if __name__ == "__main__":
    tests = [
        test_grupo_compatible_recibe_recomendacion,
        test_grupo_con_conflicto_recibe_advertencia,
        test_conflicto_no_impide_seleccionar,
        test_recomendacion_cambia_segun_seleccion,
        test_manual_no_bloquea_por_prerequisitos,
        test_academico_mantiene_restricciones,
        test_recomendacion_usa_datos_reales,
        test_eliminar_grupo_recalcula_recomendaciones,
        test_aux_no_rompe_recomendaciones,
        test_todos_grupos_seleccionables_sin_restriccion,
        test_web_muestra_recomendaciones_en_grupos,
        test_web_sidebar_muestra_resumen,
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
    print("RESULTADOS RECOMENDACIONES: %d passed, %d failed, %d total" % (
        passed, failed, len(tests)))
    if failed == 0:
        print("TODOS LOS TESTS PASARON CORRECTAMENTE")
    else:
        print("ALGUNOS TESTS FALLARON")
    print("=" * 60)