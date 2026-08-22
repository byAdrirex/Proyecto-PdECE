"""
Tests de integracion: motor_academico + lector_oferta_pdf
Requiere: Excel real, kardex real, PDF oferta real.
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "modulos"))

from motor_academico import (
    crear_motor, configurar_gestion, seleccionar_objetivos,
    cargar_oferta, determinar_estado_materia_completo,
    evaluar_todas, consultar_oferta_materia,
    OBJ_LIC, OBJ_M01,
)


RUTA_KARDEX = os.path.join(
    os.path.dirname(os.path.dirname(__file__)),
    "datos", "webSISS Sistema de Informaci\u00f3n San Sim\u00f3n.pdf",
)
RUTA_OFERTA = os.path.join(
    os.path.dirname(os.path.dirname(__file__)),
    "datos", "Oferta ECO - 2-2026.pdf",
)


def _crear_motor_con_datos():
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

    return motor


def test_oferta_cargada():
    motor = _crear_motor_con_datos()
    assert motor["oferta"] is not None
    assert motor["oferta"]["total_materias"] == 70
    assert motor["oferta"]["total_grupos"] == 146
    print("PASS: test_oferta_cargada (70 materias, 146 grupos)")


def test_6_materias_no_ofertadas():
    motor = _crear_motor_con_datos()
    no_ofertadas = ["TI01", "TI02", "TI03", "TI04", "1304140", "1304162"]
    for cod in no_ofertadas:
        info = determinar_estado_materia_completo(cod, motor)
        assert info["ofertada"] is False, \
            "%s deberia ser NO_OFERTADA, got %s" % (cod, info.get("estado_oferta"))
        assert info["estado_oferta"] == "NO_OFERTADA", \
            "%s estado_oferta deberia ser NO_OFERTADA" % cod
        assert len(info["grupos"]) == 0, \
            "%s no deberia tener grupos" % cod
    print("PASS: test_6_materias_no_ofertadas (%s)" % ", ".join(no_ofertadas))


def test_aprobada_no_cambia_por_oferta():
    motor = _crear_motor_con_datos()
    aprobadas = ["1304001", "1304003", "1304007", "1304018", "1304013"]
    for cod in aprobadas:
        info = determinar_estado_materia_completo(cod, motor)
        assert info["estado"] == "APROBADA", \
            "%s deberia ser APROBADA, got %s" % (cod, info["estado"])
        assert info["ofertada"] is True, \
            "%s deberia estar OFERTADA" % cod
        assert len(info["grupos"]) > 0, \
            "%s deberia tener grupos" % cod
    print("PASS: test_aprobada_no_cambia_por_oferta (5 materias verificadas)")


def test_bloqueada_no_cambia_por_oferta():
    motor = _crear_motor_con_datos()
    bloqueadas_con_oferta = [
        ("1304026", ["1304020"]),
        ("1304134", ["1304027"]),
        ("1304039", ["1304026"]),
    ]
    for cod, faltan_esperados in bloqueadas_con_oferta:
        info = determinar_estado_materia_completo(cod, motor)
        assert info["estado"] == "BLOQUEADA", \
            "%s deberia ser BLOQUEADA, got %s" % (cod, info["estado"])
        assert info["ofertada"] is True, \
            "%s deberia estar OFERTADA" % cod
        for f in faltan_esperados:
            assert f in info["faltan"], \
                "%s deberia faltar %s" % (cod, f)
    print("PASS: test_bloqueada_no_cambia_por_oferta (3 materias verificadas)")


def test_disponible_con_grupos():
    motor = _crear_motor_con_datos()
    disponibles = ["1304022", "1304032", "1304027"]
    for cod in disponibles:
        info = determinar_estado_materia_completo(cod, motor)
        assert info["estado"] == "DISPONIBLE", \
            "%s deberia ser DISPONIBLE, got %s" % (cod, info["estado"])
        assert info["ofertada"] is True, \
            "%s deberia estar OFERTADA" % cod
        assert len(info["grupos"]) > 0, \
            "%s deberia tener grupos" % cod
    print("PASS: test_disponible_con_grupos (3 materias verificadas)")


def test_grupos_con_auxiliares():
    motor = _crear_motor_con_datos()
    info = determinar_estado_materia_completo("1304001", motor)
    assert len(info["grupos"]) == 3, \
        "1304001 deberia tener 3 grupos, got %d" % len(info["grupos"])
    auxiliares_total = sum(
        len(g.get("auxiliares", [])) for g in info["grupos"]
    )
    assert auxiliares_total > 0, \
        "1304001 deberia tener auxiliares"
    print("PASS: test_grupos_con_auxiliares (1304001: 3 grupos, %d aux)" % auxiliares_total)


def test_por_designar_docente():
    motor = _crear_motor_con_datos()
    info = determinar_estado_materia_completo("1304003", motor)
    docentes = [g["docente"] for g in info["grupos"]]
    assert "POR DESIGNAR DOCENTE" in docentes, \
        "1304003 deberia tener POR DESIGNAR DOCENTE en algun grupo"
    print("PASS: test_por_designar_docente (1304003 tiene POR DESIGNAR DOCENTE)")


def test_consultar_oferta_materia():
    motor = _crear_motor_con_datos()
    r1 = consultar_oferta_materia("1304001", motor)
    assert r1["ofertada"] is True
    assert r1["estado_oferta"] == "OFERTADA"
    assert len(r1["grupos"]) == 3

    r2 = consultar_oferta_materia("TI01", motor)
    assert r2["ofertada"] is False
    assert r2["estado_oferta"] == "NO_OFERTADA"
    assert len(r2["grupos"]) == 0
    print("PASS: test_consultar_oferta_materia")


def test_total_materias_plan():
    motor = _crear_motor_con_datos()
    total_excel = len(motor["tipos_materias"])
    todas = evaluar_todas(motor)
    total_evaluadas = len(todas)
    assert total_evaluadas == total_excel, \
        "Deberia evaluar %d materias, got %d" % (total_excel, total_evaluadas)
    ofertadas = sum(1 for v in todas.values() if v.get("ofertada") is True)
    no_ofertadas = sum(1 for v in todas.values() if v.get("ofertada") is False)
    assert ofertadas == 70, "Deberia haber 70 ofertadas, got %d" % ofertadas
    assert no_ofertadas == 6, "Deberia haber 6 no ofertadas, got %d" % no_ofertadas
    print("PASS: test_total_materias_plan (%d total, %d ofertadas, %d no ofertadas)" % (
        total_evaluadas, ofertadas, no_ofertadas))


def test_materia_con_sustitucion_m03():
    motor = _crear_motor_con_datos()
    info = determinar_estado_materia_completo("1301031", motor)
    assert info["estado"] == "DISPONIBLE"
    assert info["ofertada"] is True
    assert len(info["grupos"]) > 0
    print("PASS: test_materia_con_sustitucion_m03 (1301031 MERCADOTECNIA I)")


def test_sin_oferta_no_afecta_estado():
    motor = _crear_motor_con_datos()
    info_con = determinar_estado_materia_completo("1304022", motor)
    motor["oferta"] = None
    info_sin = determinar_estado_materia_completo("1304022", motor)
    assert info_con["estado"] == info_sin["estado"], \
        "Estado academico no deberia cambiar sin oferta"
    assert info_sin["ofertada"] is None
    assert info_sin["estado_oferta"] is None
    print("PASS: test_sin_oferta_no_afecta_estado")


def test_recomendaciones_solo_ofertadas():
    motor = _crear_motor_con_datos()
    from motor_academico import _materias_recomendadas
    recs = _materias_recomendadas(motor)
    for r in recs:
        assert r.get("ofertada") is True, \
            "Recomendada %s deberia ser OFERTADA" % r["codigo"]
    print("PASS: test_recomendaciones_solo_ofertadas (%d recomendadas, todas OFERTADA)" % len(recs))


if __name__ == "__main__":
    tests = [
        test_oferta_cargada,
        test_6_materias_no_ofertadas,
        test_aprobada_no_cambia_por_oferta,
        test_bloqueada_no_cambia_por_oferta,
        test_disponible_con_grupos,
        test_grupos_con_auxiliares,
        test_por_designar_docente,
        test_consultar_oferta_materia,
        test_total_materias_plan,
        test_materia_con_sustitucion_m03,
        test_sin_oferta_no_afecta_estado,
        test_recomendaciones_solo_ofertadas,
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
    print("RESULTADOS: %d passed, %d failed, %d total" % (
        passed, failed, len(tests)))
    if failed == 0:
        print("TODOS LOS TESTS PASARON CORRECTAMENTE")
    else:
        print("ALGUNOS TESTS FALLARON")
    print("=" * 60)
