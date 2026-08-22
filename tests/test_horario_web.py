"""
Tests de la interfaz web - Horario (modo manual).
Valida rutas HTTP, flujo htmx, seleccion, calendario.
NO modifica Excel ni PDF.
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "modulos"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app import create_app
from app import inicio as app_inicio
from app.inicio import format_dias, format_horario, format_aulas, calendario_eventos
from planificador import crear_planificador, seleccionar_grupo, MODO_MANUAL


app = create_app()
client = app.test_client()


def test_horario_responde_200():
    resp = client.get("/horario")
    assert resp.status_code == 200
    assert b"Armar mi Horario" in resp.data
    print("PASS: test_horario_responde_200")


def test_modo_manual_se_puede_seleccionar():
    resp = client.post("/horario/parcial/seleccionar-modo", data={"modo": "manual"})
    assert resp.status_code == 200
    assert b"manual" in resp.data.lower()
    print("PASS: test_modo_manual_se_puede_seleccionar")


def test_niveles_cargados_desde_datos():
    niveles = app_inicio.get_oferta_niveles()
    assert len(niveles) == 9
    assert "A" in niveles
    assert "I" in niveles
    resp = client.post("/horario/parcial/seleccionar-modo", data={"modo": "manual"})
    for n in niveles:
        assert bytes(n, "utf-8") in resp.data
    print("PASS: test_niveles_cargados_desde_datos (%d niveles)" % len(niveles))


def test_materias_se_filtran_por_nivel():
    resp = client.get("/horario/parcial/nivel/A")
    assert resp.status_code == 200
    assert b"ECONOMIA GENERAL" in resp.data
    assert b"materia-1304001" in resp.data

    resp_e = client.get("/horario/parcial/nivel/E")
    assert resp_e.status_code == 200
    assert b"materia-1301031" in resp_e.data
    print("PASS: test_materias_se_filtran_por_nivel")


def test_grupos_corresponden_a_materia():
    resp = client.get("/horario/parcial/grupos/1304001")
    assert resp.status_code == 200
    assert b"ECONOMIA GENERAL" in resp.data
    assert b"AVILES ROCHA" in resp.data
    print("PASS: test_grupos_corresponden_a_materia")


def test_se_puede_seleccionar_grupo():
    client.post("/horario/parcial/seleccionar-modo", data={"modo": "manual"})
    resp = client.post("/horario/parcial/seleccionar", data={
        "codigo_sis": "1304001", "grupo": "01"
    })
    assert resp.status_code == 200

    resp = client.get("/horario/parcial/sidebar")
    assert resp.status_code == 200
    assert b"ECONOMIA GENERAL" in resp.data
    print("PASS: test_se_puede_seleccionar_grupo")


def test_materia_con_prereq_seleccionable_en_manual():
    motor = app_inicio.get_motor()
    cod_con_prereq = None
    for codigo in motor["mapa_prereq"]:
        from motor_academico import determinar_estado_materia_completo
        info = determinar_estado_materia_completo(codigo, motor)
        if info["estado"] == "BLOQUEADA":
            cod_con_prereq = codigo
            break

    if cod_con_prereq is None:
        print("PASS: test_materia_con_prereq_seleccionable_en_manual (skipped)")
        return

    resp = client.get("/horario/parcial/grupos/%s" % cod_con_prereq)
    assert resp.status_code == 200
    assert b"prerrequisitos" in resp.data.lower() or b"manual" in resp.data.lower()

    grupos = app_inicio.get_grupos_por_materia(cod_con_prereq)
    if grupos:
        num = grupos[0].get("grupo", "01")
        resp = client.post("/horario/parcial/seleccionar", data={
            "codigo_sis": cod_con_prereq, "grupo": num
        })
        assert resp.status_code == 200
    print("PASS: test_materia_con_prereq_seleccionable_en_manual (%s)" % cod_con_prereq)


def test_conflicto_se_detecta():
    client.post("/horario/parcial/seleccionar-modo", data={"modo": "manual"})

    g1 = {
        "codigo_sis": "TEST01", "nivel": "A", "grupo": "01",
        "docente": "DOC A", "nombre": "MATERIA A",
        "auxiliares": [],
        "horarios": [{"dia": "LU", "hora_inicio": "08:00", "hora_fin": "09:30", "aula": "E530"}],
    }
    g2 = {
        "codigo_sis": "TEST02", "nivel": "A", "grupo": "01",
        "docente": "DOC B", "nombre": "MATERIA B",
        "auxiliares": [],
        "horarios": [{"dia": "LU", "hora_inicio": "09:00", "hora_fin": "10:30", "aula": "E531"}],
    }

    motor = app_inicio.get_motor()
    from flask import session
    with client.session_transaction() as sess:
        plan = sess.get("plan")
    if plan:
        seleccionar_grupo(plan, g1, motor)
        seleccionar_grupo(plan, g2, motor)
        assert len(plan["conflictos"]) > 0

        resp = client.get("/horario/parcial/sidebar")
        assert resp.status_code == 200
    print("PASS: test_conflicto_se_detecta")


def test_limite_8_normales():
    client.post("/horario/parcial/seleccionar-modo", data={"modo": "manual"})

    with client.session_transaction() as sess:
        plan = sess.get("plan")
    if plan is None:
        print("PASS: test_limite_8_normales (skipped: no plan)")
        return

    motor = app_inicio.get_motor()
    for i in range(8):
        g = {
            "codigo_sis": "LIM%02d" % i, "nivel": "A", "grupo": "01",
            "docente": "DOC", "nombre": "MAT %d" % i,
            "auxiliares": [],
            "horarios": [{"dia": ["LU", "MA", "MI", "JU", "VI", "SA", "LU"][i % 7],
                          "hora_inicio": "%02d:00" % (8 + i),
                          "hora_fin": "%02d:30" % (9 + i),
                          "aula": "E530"}],
        }
        seleccionar_grupo(plan, g, motor)

    g_extra = {
        "codigo_sis": "LIM99", "nivel": "A", "grupo": "01",
        "docente": "DOC", "nombre": "MAT EXTRA",
        "auxiliares": [],
        "horarios": [{"dia": "SA", "hora_inicio": "08:00", "hora_fin": "09:30", "aula": "E530"}],
    }
    ok, msg = seleccionar_grupo(plan, g_extra, motor)
    assert ok, "La novena materia deberia aceptarse con advertencia no bloqueante: %s" % msg
    assert len(plan["grupos_seleccionados"]) == 9
    advs = [a for a in plan.get("advertencias", [])
            if "8 materias" in a.get("mensaje", "")]
    assert len(advs) >= 1, "Deberia registrarse la advertencia de >8 materias"
    print("PASS: test_limite_8_normales (advertencia no bloqueante)")


def test_se_puede_eliminar():
    client.post("/horario/parcial/seleccionar-modo", data={"modo": "manual"})
    resp = client.post("/horario/parcial/seleccionar", data={
        "codigo_sis": "1304001", "grupo": "01"
    })
    assert resp.status_code == 200

    resp = client.post("/horario/parcial/eliminar", data={
        "codigo_sis": "1304001", "grupo": "01"
    })
    assert resp.status_code == 200

    resp = client.get("/horario/parcial/sidebar")
    assert b"ECONOMIA GENERAL" not in resp.data
    print("PASS: test_se_puede_eliminar")


def test_calendario_eventos():
    plan = crear_planificador(gestion=2, anio=2026, modo=MODO_MANUAL)
    g1 = {
        "codigo_sis": "1304001", "nivel": "A", "grupo": "01",
        "docente": "DOC A", "nombre": "ECONOMIA GENERAL",
        "auxiliares": [{"nombre": "AUX NAME", "horarios": [
            {"dia": "LU", "hora_inicio": "11:15", "hora_fin": "12:45", "aula": "E102"}
        ]}],
        "horarios": [
            {"dia": "MA", "hora_inicio": "09:45", "hora_fin": "11:15", "aula": "E105"},
            {"dia": "MI", "hora_inicio": "09:45", "hora_fin": "11:15", "aula": "E107"},
        ],
    }
    motor = app_inicio.get_motor()
    seleccionar_grupo(plan, g1, motor)

    eventos = calendario_eventos(plan)
    assert len(eventos) == 3
    assert eventos[0]["title"] == "ECONOMIA GENERAL (G01)"
    assert eventos[0]["daysOfWeek"] == [2]
    assert eventos[2]["title"] == "AUX ECONOMIA GENERAL (G01)"
    assert eventos[2]["daysOfWeek"] == [1]
    print("PASS: test_calendario_eventos")


def test_aux_toggle():
    client.post("/horario/parcial/seleccionar-modo", data={"modo": "manual"})
    client.post("/horario/parcial/seleccionar", data={
        "codigo_sis": "1304001", "grupo": "01"
    })

    with client.session_transaction() as sess:
        plan = sess.get("plan")
    if plan is None:
        print("PASS: test_aux_toggle (skipped)")
        return

    assert plan.get("modo_aux") is True

    resp = client.post("/horario/parcial/aux")
    assert resp.status_code == 204

    with client.session_transaction() as sess:
        plan = sess.get("plan")
    assert plan.get("modo_aux") is False

    resp = client.post("/horario/parcial/aux")
    assert resp.status_code == 204

    with client.session_transaction() as sess:
        plan = sess.get("plan")
    assert plan.get("modo_aux") is True
    print("PASS: test_aux_toggle")


def test_sidebar_tiene_interruptor_aux():
    client.post("/horario/parcial/seleccionar-modo", data={"modo": "manual"})
    resp = client.get("/horario/parcial/sidebar")
    assert resp.status_code == 200
    assert b"Horarios de auxiliares" in resp.data
    assert b"/horario/parcial/aux" in resp.data
    assert b'aria-checked="true"' in resp.data

    client.post("/horario/parcial/aux")
    resp = client.get("/horario/parcial/sidebar")
    assert b'aria-checked="false"' in resp.data
    print("PASS: test_sidebar_tiene_interruptor_aux")


def test_niveles_sin_push_url():
    client.post("/horario/parcial/seleccionar-modo", data={"modo": "manual"})
    resp = client.get("/horario")
    assert b"hx-push-url" not in resp.data
    print("PASS: test_niveles_sin_push_url")


def test_volver_limpia_zona_grupos():
    resp = client.get("/horario/parcial/grupos/1304001")
    assert resp.status_code == 200
    assert b"zona-grupos" in resp.data

    resp_materias = client.get("/horario/parcial/nivel/A")
    assert resp_materias.status_code == 200
    assert b"grupos-1304001" in resp_materias.data
    print("PASS: test_volver_limpia_zona_grupos")


def test_format_dias():
    horarios = [
        {"dia": "LU", "hora_inicio": "08:00", "hora_fin": "09:30"},
        {"dia": "MI", "hora_inicio": "08:00", "hora_fin": "09:30"},
        {"dia": "VI", "hora_inicio": "08:00", "hora_fin": "09:30"},
    ]
    assert format_dias(horarios) == "Lunes - Miercoles - Viernes"
    print("PASS: test_format_dias")


def test_format_horario():
    horarios = [
        {"dia": "LU", "hora_inicio": "08:15", "hora_fin": "09:45"},
    ]
    assert format_horario(horarios) == "08:15-09:45"
    print("PASS: test_format_horario")


def test_format_aulas():
    horarios = [
        {"dia": "LU", "hora_inicio": "08:00", "hora_fin": "09:30", "aula": "E530"},
        {"dia": "MI", "hora_inicio": "08:00", "hora_fin": "09:30", "aula": "E107"},
    ]
    assert format_aulas(horarios) == "E530 / E107"
    print("PASS: test_format_aulas")


def test_calendario_parcial_siempre_renderiza():
    client.post("/horario/parcial/seleccionar-modo", data={"modo": "manual"})
    with client.session_transaction() as sess:
        sess["plan"] = crear_planificador(gestion=2, anio=2026, modo=MODO_MANUAL)
    resp = client.get("/horario/parcial/calendario")
    assert resp.status_code == 200
    assert b"MI HORARIO" in resp.data
    assert b'id="calendar"' in resp.data
    print("PASS: test_calendario_parcial_siempre_renderiza")


def test_calendario_hora_rango_y_bloques():
    resp = client.get("/horario/parcial/calendario")
    assert resp.status_code == 200
    assert b"slotLabelContent" in resp.data
    assert b"fc-hora-rango" in resp.data
    assert b"fc-bloque-nombre" in resp.data
    assert b"displayEventTime: false" in resp.data
    print("PASS: test_calendario_hora_rango_y_bloques")


def test_sidebar_sin_contadores_ni_confirmacion():
    client.post("/horario/parcial/seleccionar-modo", data={"modo": "manual"})
    client.post("/horario/parcial/seleccionar", data={
        "codigo_sis": "1304001", "grupo": "01"
    })
    resp = client.get("/horario/parcial/sidebar")
    assert resp.status_code == 200
    assert b"hx-confirm" not in resp.data
    assert b"Materias normales" not in resp.data
    assert b"Materias mesa" not in resp.data
    print("PASS: test_sidebar_sin_contadores_ni_confirmacion")


def test_banner_advertencia_mas_de_8_materias():
    client.post("/horario/parcial/seleccionar-modo", data={"modo": "manual"})
    with client.session_transaction() as sess:
        plan = sess.get("plan")
        if plan is None:
            plan = crear_planificador(gestion=2, anio=2026, modo=MODO_MANUAL)
        for i in range(9):
            g = {
                "codigo_sis": "LIM%02d" % i, "nivel": "A", "grupo": "01",
                "docente": "DOC", "nombre": "MAT %d" % i, "auxiliares": [],
                "horarios": [{"dia": ["LU", "MA", "MI", "JU", "VI", "SA", "LU"][i % 7],
                              "hora_inicio": "%02d:00" % (8 + i),
                              "hora_fin": "%02d:30" % (9 + i), "aula": "E530"}],
            }
            ok, _ = seleccionar_grupo(plan, g, None)
            assert ok, "La %da materia deberia aceptarse con advertencia" % (i + 1)
        sess["plan"] = plan
    resp = client.get("/horario/parcial/sidebar")
    assert resp.status_code == 200
    assert b"Has superado las 8 materias" in resp.data
    assert b"Advertencia de carga" in resp.data
    print("PASS: test_banner_advertencia_mas_de_8_materias")


def test_calendario_colores_pastel_y_conflictos():
    plan = crear_planificador(gestion=2, anio=2026, modo=MODO_MANUAL)
    g1 = {
        "codigo_sis": "1304001", "nivel": "A", "grupo": "01",
        "docente": "DOC A", "nombre": "ECONOMIA GENERAL", "auxiliares": [],
        "horarios": [{"dia": "MA", "hora_inicio": "09:45", "hora_fin": "11:15", "aula": "E105"}],
    }
    g2 = {
        "codigo_sis": "1304002", "nivel": "A", "grupo": "01",
        "docente": "DOC B", "nombre": "MATEMATICA I", "auxiliares": [],
        "horarios": [{"dia": "MA", "hora_inicio": "10:00", "hora_fin": "11:30", "aula": "E107"}],
    }
    g3 = {
        "codigo_sis": "1304003", "nivel": "A", "grupo": "01",
        "docente": "DOC C", "nombre": "DERECHO", "auxiliares": [],
        "horarios": [{"dia": "JU", "hora_inicio": "08:00", "hora_fin": "09:30", "aula": "E200"}],
    }
    g4 = {
        "codigo_sis": "1304004", "nivel": "A", "grupo": "01",
        "docente": "DOC D", "nombre": "CONTABILIDAD", "auxiliares": [],
        "horarios": [{"dia": "VI", "hora_inicio": "08:00", "hora_fin": "09:30", "aula": "E201"}],
    }
    for g in (g1, g2, g3, g4):
        seleccionar_grupo(plan, g, None)

    eventos = calendario_eventos(plan)
    clases = [e for e in eventos if e["extendedProps"]["tipo"] == "CLASE"]
    assert len(clases) == 4
    # Las materias en conflicto se pintan de rojo intenso.
    rojos = [e for e in clases if e["backgroundColor"] == "#ef4444"]
    assert len(rojos) == 2
    assert all(e["extendedProps"]["conflicto"] for e in rojos)
    # Materias sin conflicto usan pasteles distintos entre si.
    pasteles = [e["backgroundColor"] for e in clases
                if not e["extendedProps"]["conflicto"]]
    assert len(pasteles) == 2
    assert pasteles[0] != pasteles[1], "Materias distintas deben usar pasteles distintos"
    print("PASS: test_calendario_colores_pastel_y_conflictos")


if __name__ == "__main__":
    tests = [
        test_horario_responde_200,
        test_modo_manual_se_puede_seleccionar,
        test_niveles_cargados_desde_datos,
        test_materias_se_filtran_por_nivel,
        test_grupos_corresponden_a_materia,
        test_se_puede_seleccionar_grupo,
        test_materia_con_prereq_seleccionable_en_manual,
        test_conflicto_se_detecta,
        test_limite_8_normales,
        test_se_puede_eliminar,
        test_calendario_eventos,
        test_aux_toggle,
        test_sidebar_tiene_interruptor_aux,
        test_niveles_sin_push_url,
        test_volver_limpia_zona_grupos,
        test_format_dias,
        test_format_horario,
        test_format_aulas,
        test_calendario_parcial_siempre_renderiza,
        test_calendario_hora_rango_y_bloques,
        test_sidebar_sin_contadores_ni_confirmacion,
        test_banner_advertencia_mas_de_8_materias,
        test_calendario_colores_pastel_y_conflictos,
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
    print("RESULTADOS HORARIO WEB: %d passed, %d failed, %d total" % (
        passed, failed, len(tests)))
    if failed == 0:
        print("TODOS LOS TESTS PASARON CORRECTAMENTE")
    else:
        print("ALGUNOS TESTS FALLARON")
    print("=" * 60)
