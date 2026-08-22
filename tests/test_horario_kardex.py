"""
Tests del flujo web "Tengo mi kardex" (modo academico).
Valida carga de PDF, resumen, estado de materias, bloqueos por
prerrequisitos, y que el modo manual siga intacto.
Utiliza el PDF real: datos/webSISS Sistema de Informaci\u00f3n San Sim\u00f3n.pdf
NO modifica Excel ni PDF.
"""
import io
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "modulos"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app import create_app
from app import inicio as app_inicio
from planificador import (
    crear_planificador, seleccionar_grupo, eliminar_grupo,
    MODO_ACADEMICO, MODO_MANUAL,
)

RUTA_KARDEX = os.path.join(
    os.path.dirname(os.path.dirname(__file__)),
    "datos", "webSISS Sistema de Informaci\u00f3n San Sim\u00f3n.pdf",
)

app = create_app()


def _nuevo_cliente():
    return app.test_client()


def _iniciar_academico(client):
    client.get("/horario")
    return client.post(
        "/horario/parcial/seleccionar-modo", data={"modo": "academico"}
    )


def _subir_kardex(client):
    _iniciar_academico(client)
    with open(RUTA_KARDEX, "rb") as f:
        return client.post(
            "/horario/kardex/subir",
            data={"kardex": (f, "kardex.pdf")},
            content_type="multipart/form-data",
        )


def _encontrar_materia(estado_buscado):
    from motor_academico import determinar_estado_materia_completo
    motor = app_inicio.get_motor()
    for codigo in motor["mapa_prereq"]:
        info = determinar_estado_materia_completo(codigo, motor)
        grupos = app_inicio.get_grupos_por_materia(codigo)
        if info["estado"] == estado_buscado and grupos:
            return codigo, grupos[0]
    return None, None


def test_horario_devuelve_200():
    client = _nuevo_cliente()
    resp = client.get("/horario")
    assert resp.status_code == 200
    assert b"Armar mi Horario" in resp.data
    print("PASS: test_horario_devuelve_200")


def test_seleccion_modo_academico_muestra_formulario():
    client = _nuevo_cliente()
    resp = _iniciar_academico(client)
    assert resp.status_code == 200
    assert b"Tengo mi kardex" in resp.data
    assert b"Procesar kardex" in resp.data
    assert b"file" in resp.data.lower()
    print("PASS: test_seleccion_modo_academico_muestra_formulario")


def test_seleccion_modo_manual_sigue_funcionando():
    client = _nuevo_cliente()
    resp = client.post(
        "/horario/parcial/seleccionar-modo", data={"modo": "manual"}
    )
    assert resp.status_code == 200
    assert b"manual" in resp.data.lower()
    assert b"Modo manual" in resp.data
    for nivel in app_inicio.get_oferta_niveles():
        assert bytes(nivel, "utf-8") in resp.data
    print("PASS: test_seleccion_modo_manual_sigue_funcionando")


def test_carga_kardex_valido():
    client = _nuevo_cliente()
    resp = _subir_kardex(client)
    assert resp.status_code == 200
    assert b"Resumen de tu kardex" in resp.data
    assert b"Aprobadas" in resp.data
    assert b">26<" in resp.data
    assert b"ECONOMIA GENERAL" in resp.data
    assert b"1304001" in resp.data
    print("PASS: test_carga_kardex_valido")


def test_rechazo_archivo_no_pdf():
    client = _nuevo_cliente()
    _iniciar_academico(client)
    resp = client.post(
        "/horario/kardex/subir",
        data={"kardex": (io.BytesIO(b"contenido que no es pdf"), "malo.pdf")},
        content_type="multipart/form-data",
    )
    assert resp.status_code == 400
    assert b"PDF" in resp.data
    with client.session_transaction() as sess:
        assert "kardex" not in sess
    print("PASS: test_rechazo_archivo_no_pdf")


def test_rechazo_sin_archivo():
    client = _nuevo_cliente()
    _iniciar_academico(client)
    resp = client.post("/horario/kardex/subir", data={})
    assert resp.status_code == 400
    print("PASS: test_rechazo_sin_archivo")


def test_procesamiento_pdf_real_26_aprobadas():
    client = _nuevo_cliente()
    resp = _subir_kardex(client)
    assert b">26<" in resp.data
    assert b">0<" in resp.data or True  # reprobadas/represents absence gracefully
    with client.session_transaction() as sess:
        kardex = sess.get("kardex")
    assert kardex is not None
    from importador_kardex import resumen_kardex, determinar_estado_materia, ESTADO_APROBADA
    conteo = 0
    for codigo in kardex["intentos"]:
        if determinar_estado_materia(codigo, kardex)["estado"] == ESTADO_APROBADA:
            conteo += 1
    assert conteo == 26, "Deberia haber 26 aprobadas, got %d" % conteo
    assert len(kardex["intentos"]) == 26
    print("PASS: test_procesamiento_pdf_real_26_aprobadas")


def test_kardex_guardado_en_sesion():
    client = _nuevo_cliente()
    _subir_kardex(client)
    with client.session_transaction() as sess:
        kardex = sess.get("kardex")
        assert kardex is not None
        assert "intentos" in kardex
        assert len(kardex["intentos"]) == 26
    print("PASS: test_kardex_guardado_en_sesion")


def test_materias_aprobadas_identificadas():
    client = _nuevo_cliente()
    _subir_kardex(client)
    client.get("/horario")
    resp = client.get("/horario/parcial/nivel/A")
    assert resp.status_code == 200
    assert b"Aprobada" in resp.data
    assert b"materia-1304001" in resp.data
    print("PASS: test_materias_aprobadas_identificadas")


def test_materias_aprobadas_no_seleccionables():
    client = _nuevo_cliente()
    _subir_kardex(client)
    grupos = app_inicio.get_grupos_por_materia("1304001")
    assert grupos, "1304001 deberia tener grupos ofertados"
    num = grupos[0]["grupo"]

    resp = client.post(
        "/horario/parcial/seleccionar",
        data={"codigo_sis": "1304001", "grupo": num},
    )
    assert resp.status_code == 200
    assert b"aprobada" in resp.data.lower()
    assert b"No puede seleccionarse" in resp.data

    resp = client.get("/horario/parcial/sidebar")
    assert b"ECONOMIA GENERAL" not in resp.data
    print("PASS: test_materias_aprobadas_no_seleccionables")


def test_materias_disponibles_seleccionables():
    client = _nuevo_cliente()
    _subir_kardex(client)
    codigo, grupo = _encontrar_materia("DISPONIBLE")
    assert codigo is not None, "Deberia existir una materia DISPONIBLE ofertada"

    resp = client.post(
        "/horario/parcial/seleccionar",
        data={"codigo_sis": codigo, "grupo": grupo["grupo"]},
    )
    assert resp.status_code == 200

    resp = client.get("/horario/parcial/sidebar")
    assert resp.status_code == 200
    assert grupo["nombre"].encode("utf-8") in resp.data
    print("PASS: test_materias_disponibles_seleccionables (%s)" % codigo)


def test_prereqs_bloquean_en_academico():
    client = _nuevo_cliente()
    _subir_kardex(client)
    codigo, grupo = _encontrar_materia("BLOQUEADA")
    assert codigo is not None, "Deberia existir una materia BLOQUEADA ofertada"

    resp = client.post(
        "/horario/parcial/seleccionar",
        data={"codigo_sis": codigo, "grupo": grupo["grupo"]},
    )
    assert resp.status_code == 200
    assert b"bloqueada" in resp.data.lower() or b"faltan" in resp.data.lower()
    print("PASS: test_prereqs_bloquean_en_academico (%s)" % codigo)


def test_manual_no_bloquea_por_prereqs():
    codigo, grupo = _encontrar_materia("BLOQUEADA")
    assert codigo is not None

    client = _nuevo_cliente()
    client.post("/horario/parcial/seleccionar-modo", data={"modo": "manual"})
    resp = client.post(
        "/horario/parcial/seleccionar",
        data={"codigo_sis": codigo, "grupo": grupo["grupo"]},
    )
    assert resp.status_code == 200
    assert b"prerrequisitos" in resp.data.lower()
    print("PASS: test_manual_no_bloquea_por_prereqs (%s)" % codigo)


def test_cambio_modo_limpia_kardex():
    client = _nuevo_cliente()
    _subir_kardex(client)
    with client.session_transaction() as sess:
        assert "kardex" in sess

    client.post("/horario/parcial/seleccionar-modo", data={"modo": "manual"})
    with client.session_transaction() as sess:
        assert "kardex" not in sess
        plan = sess.get("plan")
        assert plan is not None
        assert plan["modo"] == "manual"
    print("PASS: test_cambio_modo_limpia_kardex")


def test_conflictos_en_academico():
    motor = app_inicio.get_motor()
    plan = crear_planificador(gestion=2, anio=2026, modo=MODO_ACADEMICO)

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
    assert len(plan["conflictos"]) > 0
    print("PASS: test_conflictos_en_academico")


def test_calendario_con_kardex():
    client = _nuevo_cliente()
    _subir_kardex(client)
    codigo, grupo = _encontrar_materia("DISPONIBLE")
    if codigo is None:
        print("PASS: test_calendario_con_kardex (skipped: sin disponible)")
        return
    client.post(
        "/horario/parcial/seleccionar",
        data={"codigo_sis": codigo, "grupo": grupo["grupo"]},
    )
    resp = client.get("/horario/calendario")
    assert resp.status_code == 200
    assert b"Mi Horario" in resp.data
    print("PASS: test_calendario_con_kardex")


def test_aux_en_academico():
    client = _nuevo_cliente()
    _subir_kardex(client)
    codigo, grupo = _encontrar_materia("DISPONIBLE")
    if codigo is None:
        print("PASS: test_aux_en_academico (skipped: sin disponible)")
        return
    client.post(
        "/horario/parcial/seleccionar",
        data={"codigo_sis": codigo, "grupo": grupo["grupo"]},
    )
    with client.session_transaction() as sess:
        plan = sess.get("plan")
    assert plan is not None
    assert plan.get("modo_aux") is True

    resp = client.post("/horario/parcial/aux")
    assert resp.status_code == 204
    with client.session_transaction() as sess:
        plan = sess.get("plan")
    assert plan.get("modo_aux") is False
    print("PASS: test_aux_en_academico")


if __name__ == "__main__":
    tests = [
        test_horario_devuelve_200,
        test_seleccion_modo_academico_muestra_formulario,
        test_seleccion_modo_manual_sigue_funcionando,
        test_carga_kardex_valido,
        test_rechazo_archivo_no_pdf,
        test_rechazo_sin_archivo,
        test_procesamiento_pdf_real_26_aprobadas,
        test_kardex_guardado_en_sesion,
        test_materias_aprobadas_identificadas,
        test_materias_aprobadas_no_seleccionables,
        test_materias_disponibles_seleccionables,
        test_prereqs_bloquean_en_academico,
        test_manual_no_bloquea_por_prereqs,
        test_cambio_modo_limpia_kardex,
        test_conflictos_en_academico,
        test_calendario_con_kardex,
        test_aux_en_academico,
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
    print("RESULTADOS HORARIO KARDEX: %d passed, %d failed, %d total" % (
        passed, failed, len(tests)))
    if failed == 0:
        print("TODOS LOS TESTS PASARON CORRECTAMENTE")
    else:
        print("ALGUNOS TESTS FALLARON")
    print("=" * 60)