"""
Tests de los dos modos del planificador: academico y manual.
Valida diferencias de comportamiento entre modos.
NO modifica Excel ni PDF.
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "modulos"))

from planificador import (
    crear_planificador, seleccionar_grupo, eliminar_grupo,
    detectar_conflicto, limites, calendario_compacto,
    materias_ofertadas, materias_por_nivel, grupos_de_materia,
    verificar_prerequisitos,
    MODO_ACADEMICO, MODO_MANUAL, NIVELES_VALIDOS,
)


RUTA_KARDEX = os.path.join(
    os.path.dirname(os.path.dirname(__file__)),
    "datos", "webSISS Sistema de Informaci\u00f3n San Sim\u00f3n.pdf",
)
RUTA_OFERTA = os.path.join(
    os.path.dirname(os.path.dirname(__file__)),
    "datos", "Oferta ECO - 2-2026.pdf",
)

_MOTOR_CACHE = None


def _crear_motor_real():
    global _MOTOR_CACHE
    if _MOTOR_CACHE is not None:
        return _MOTOR_CACHE
    from motor_academico import (
        crear_motor, configurar_gestion, seleccionar_objetivos,
        cargar_oferta, OBJ_LIC, OBJ_M01,
    )
    motor = crear_motor()
    configurar_gestion(motor, anio=2026, gestion=2)
    seleccionar_objetivos(motor, [OBJ_LIC, OBJ_M01])

    from procesador_kardex import procesar_pdf
    if os.path.exists(RUTA_KARDEX):
        procesar_pdf(RUTA_KARDEX, motor["kardex"], motor["materias_df"],
                     motor["mapa_prereq"])

    from lector_oferta_pdf import leer_oferta_pdf
    if os.path.exists(RUTA_OFERTA):
        resultado = leer_oferta_pdf(RUTA_OFERTA, 2026, 2)
        cargar_oferta(motor, resultado)

    _MOTOR_CACHE = motor
    return motor


def test_modo_default_academico():
    plan = crear_planificador(gestion=2, anio=2026)
    assert plan["modo"] == MODO_ACADEMICO
    print("PASS: test_modo_default_academico")


def test_modo_manual():
    plan = crear_planificador(gestion=2, anio=2026, modo=MODO_MANUAL)
    assert plan["modo"] == MODO_MANUAL
    assert plan["advertencias"] == []
    print("PASS: test_modo_manual")


def test_modo_invalido():
    try:
        crear_planificador(gestion=2, anio=2026, modo="otro")
        assert False, "Deberia lanzar error"
    except ValueError:
        pass
    print("PASS: test_modo_invalido")


def test_manualSelecciona_con_prereq_faltantes():
    motor = _crear_motor_real()
    plan = crear_planificador(gestion=2, anio=2026, modo=MODO_MANUAL)

    cod_bloqueado = None
    for codigo in motor["mapa_prereq"]:
        from motor_academico import determinar_estado_materia_completo
        info = determinar_estado_materia_completo(codigo, motor)
        if info["estado"] == "BLOQUEADA":
            cod_bloqueado = codigo
            break

    assert cod_bloqueado is not None, "Deberia haber al menos una materia bloqueada"

    grupos = grupos_de_materia(cod_bloqueado, motor)
    if not grupos:
        print("PASS: test_manualSelecciona_con_prereq_faltantes (skipped: no groups in offering)")
        return

    ok, msg = seleccionar_grupo(plan, grupos[0], motor)
    assert ok, "Manual mode should allow blocked materia: %s" % msg

    advs = [a for a in plan["advertencias"] if a["codigo"] == cod_bloqueado]
    assert len(advs) > 0, "Deberia haber advertencia de prerrequisitos"
    assert "prerrequisitos" in advs[0]["mensaje"].lower()
    print("PASS: test_manualSelecciona_con_prereq_faltantes (%s aceptada con advertencia)" % cod_bloqueado)


def test_academicoBloquea_con_prereq_faltantes():
    motor = _crear_motor_real()
    plan = crear_planificador(gestion=2, anio=2026, modo=MODO_ACADEMICO)

    cod_bloqueado = None
    for codigo in motor["mapa_prereq"]:
        from motor_academico import determinar_estado_materia_completo
        info = determinar_estado_materia_completo(codigo, motor)
        if info["estado"] == "BLOQUEADA":
            cod_bloqueado = codigo
            break

    assert cod_bloqueado is not None

    grupos = grupos_de_materia(cod_bloqueado, motor)
    if not grupos:
        print("PASS: test_academicoBloquea_con_prereq_faltantes (skipped)")
        return

    ok, msg = seleccionar_grupo(plan, grupos[0], motor)
    assert not ok, "Academico mode should block materia with missing prereqs"
    assert "bloqueada" in msg.lower() or "faltan" in msg.lower()
    print("PASS: test_academicoBloquea_con_prereq_faltantes (%s bloqueada)" % cod_bloqueado)


def test_materias_ofertadas():
    motor = _crear_motor_real()
    ofertadas = materias_ofertadas(motor)
    assert len(ofertadas) == 70, "Deberia haber 70 materias ofertadas, got %d" % len(ofertadas)
    for cod, info in ofertadas.items():
        assert "nombre" in info
        assert "nivel" in info
        assert "grupos" in info
        assert info["grupos"] > 0
    print("PASS: test_materias_ofertadas (70 materias)")


def test_materias_por_nivel():
    motor = _crear_motor_real()
    nivel_a = materias_por_nivel("A", motor)
    assert len(nivel_a) > 0, "Nivel A deberia tener materias"
    for cod, info in nivel_a.items():
        assert info["nivel"] == "A"
        assert len(info["grupos"]) > 0
        for g in info["grupos"]:
            assert g.get("nivel") == "A"
    print("PASS: test_materias_por_nivel (nivel A: %d materias)" % len(nivel_a))


def test_todos_niveles():
    motor = _crear_motor_real()
    total = 0
    for nivel in NIVELES_VALIDOS:
        materias = materias_por_nivel(nivel, motor)
        total += len(materias)
    assert total == 70, "Total por niveles deberia ser 70, got %d" % total
    print("PASS: test_todos_niveles (70 materias en 9 niveles)")


def test_manualSelecciona_aprobada():
    motor = _crear_motor_real()
    plan = crear_planificador(gestion=2, anio=2026, modo=MODO_MANUAL)
    cod_aprob = "1304001"
    grupos = grupos_de_materia(cod_aprob, motor)
    assert len(grupos) > 0

    ok, msg = seleccionar_grupo(plan, grupos[0], motor)
    assert ok, "Manual deberia aceptar materia aprobada: %s" % msg
    advs = [a for a in plan["advertencias"] if a["codigo"] == cod_aprob]
    assert len(advs) == 0, "Materia aprobada no deberia generar advertencia"
    print("PASS: test_manualSelecciona_aprobada")


def test_ambos_modos_conflicto():
    motor = _crear_motor_real()
    for modo in (MODO_ACADEMICO, MODO_MANUAL):
        plan = crear_planificador(gestion=2, anio=2026, modo=modo)
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
        seleccionar_grupo(plan, g1, motor)
        seleccionar_grupo(plan, g2, motor)
        assert len(plan["conflictos"]) > 0, "Modo %s deberia detectar conflicto" % modo
    print("PASS: test_ambos_modos_conflicto")


def test_ambos_modos_limite():
    motor = _crear_motor_real()
    for modo in (MODO_ACADEMICO, MODO_MANUAL):
        plan = crear_planificador(gestion=2, anio=2026, modo=modo)
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
        assert ok, "Modo %s deberia aceptar novena materia con advertencia: %s" % (modo, msg)
        assert len(plan["grupos_seleccionados"]) == 9
        advs = [a for a in plan.get("advertencias", [])
                if "8 materias" in a.get("mensaje", "")]
        assert len(advs) >= 1, "Modo %s deberia registrar advertencia de >8 materias" % modo
    print("PASS: test_ambos_modos_limite (advertencia no bloqueante)")


def test_recomendado_estructura():
    motor = _crear_motor_real()
    plan = crear_planificador(gestion=2, anio=2026, modo=MODO_MANUAL)
    grupos = grupos_de_materia("1304001", motor)
    assert len(grupos) > 0

    seleccionar_grupo(plan, grupos[0], motor)
    g = plan["grupos_seleccionados"][0]
    assert "_recomendado" in g
    assert "_calificacion_recomendacion" in g
    assert "_comentario_recomendacion" in g
    assert g["_recomendado"] is None
    print("PASS: test_recomendado_estructura")


def test_advertencias_se_elimina_con_grupo():
    motor = _crear_motor_real()
    plan = crear_planificador(gestion=2, anio=2026, modo=MODO_MANUAL)

    cod_bloqueado = None
    for codigo in motor["mapa_prereq"]:
        from motor_academico import determinar_estado_materia_completo
        info = determinar_estado_materia_completo(codigo, motor)
        if info["estado"] == "BLOQUEADA":
            cod_bloqueado = codigo
            break

    if cod_bloqueado is None:
        print("PASS: test_advertencias_se_elimina_con_grupo (skipped)")
        return

    grupos = grupos_de_materia(cod_bloqueado, motor)
    if not grupos:
        print("PASS: test_advertencias_se_elimina_con_grupo (skipped: no groups)")
        return

    seleccionar_grupo(plan, grupos[0], motor)
    assert len(plan["advertencias"]) > 0

    eliminar_grupo(plan, cod_bloqueado, grupos[0]["grupo"])
    advs_restantes = [a for a in plan["advertencias"] if a["codigo"] == cod_bloqueado]
    assert len(advs_restantes) == 0
    print("PASS: test_advertencias_se_elimina_con_grupo")


def test_verificar_prerequisitos():
    motor = _crear_motor_real()
    r1 = verificar_prerequisitos("1304001", motor)
    assert r1 is None or r1["tiene_prerequisitos"] is False or len(r1["prerrequisitos"]) == 0

    r2 = verificar_prerequisitos("1304026", motor)
    assert r2 is not None
    assert r2["tiene_prerequisitos"] is True
    assert len(r2["prerrequisitos"]) > 0
    for p in r2["prerrequisitos"]:
        assert "codigo" in p
        assert "materia" in p
    print("PASS: test_verificar_prerequisitos")


def test_niveles_validos():
    assert len(NIVELES_VALIDOS) == 9
    assert NIVELES_VALIDOS == ["A", "B", "C", "D", "E", "F", "G", "H", "I"]
    print("PASS: test_niveles_validos")


if __name__ == "__main__":
    tests = [
        test_modo_default_academico,
        test_modo_manual,
        test_modo_invalido,
        test_manualSelecciona_con_prereq_faltantes,
        test_academicoBloquea_con_prereq_faltantes,
        test_materias_ofertadas,
        test_materias_por_nivel,
        test_todos_niveles,
        test_manualSelecciona_aprobada,
        test_ambos_modos_conflicto,
        test_ambos_modos_limite,
        test_recomendado_estructura,
        test_advertencias_se_elimina_con_grupo,
        test_verificar_prerequisitos,
        test_niveles_validos,
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
    print("RESULTADOS MODOS: %d passed, %d failed, %d total" % (
        passed, failed, len(tests)))
    if failed == 0:
        print("TODOS LOS TESTS PASARON CORRECTAMENTE")
    else:
        print("ALGUNOS TESTS FALLARON")
    print("=" * 60)
