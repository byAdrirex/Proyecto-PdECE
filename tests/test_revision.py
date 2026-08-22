"""
Tests de regresion de la revision tecnica.
Cubre bugs reales corregidos:
  1. num_grupos siempre 1 en app.inicio.get_materias_por_nivel
  2. materias_por_nivel con 1 solo grupo en planificador
  3. HTMX "Volver a niveles" cargaba el sidebar en #zona-materias
  4. HTMX "Volver a materias" apuntaba a #zona-grupos (ahora el acordeon
     es el unico control; los botones de la cabecera de grupos se eliminaron)
  5. Sin limite de tamano de PDF en /horario/kardex/subir
  6. Ruta /nuevo (base.html la enlazaba y daba 404)
NO modifica Excel ni PDF.
"""
import io
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "modulos"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app import create_app
from app import inicio as app_inicio
from planificador import materias_por_nivel

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


def test_num_grupos_correctos_web():
    motor = app_inicio.get_motor()
    idx = motor["oferta"]["indice"]
    for nivel in app_inicio.get_oferta_niveles():
        materias = app_inicio.get_materias_por_nivel(nivel)
        for cod, mat in materias.items():
            real = len(idx.get(cod, []))
            assert mat["num_grupos"] == real, (
                "%s nivel %s: num_grupos=%d real=%d" % (
                    cod, nivel, mat["num_grupos"], real))
    print("PASS: test_num_grupos_correctos_web")


def test_num_grupos_mayor_a_uno():
    motor = app_inicio.get_motor()
    idx = motor["oferta"]["indice"]
    cod = "1304001"
    assert len(idx.get(cod, [])) > 1
    mats = app_inicio.get_materias_por_nivel("A")
    assert mats[cod]["num_grupos"] == len(idx[cod])
    assert mats[cod]["num_grupos"] > 1
    print("PASS: test_num_grupos_mayor_a_uno (1304001: %d)" % mats[cod]["num_grupos"])


def test_materias_por_nivel_grupos_completos():
    motor = app_inicio.get_motor()
    idx = motor["oferta"]["indice"]
    for nivel in ["A", "B", "C"]:
        materias = materias_por_nivel(nivel, motor)
        for cod, info in materias.items():
            assert len(info["grupos"]) == len(idx.get(cod, [])), (
                "%s nivel %s: %d vs %d" % (
                    cod, nivel, len(info["grupos"]), len(idx.get(cod, []))))
            assert len(info["grupos"]) > 0
    print("PASS: test_materias_por_nivel_grupos_completos")


def test_materias_por_nivel_1304001_tres_grupos():
    motor = app_inicio.get_motor()
    materias = materias_por_nivel("A", motor)
    assert "1304001" in materias
    assert len(materias["1304001"]["grupos"]) == 3
    print("PASS: test_materias_por_nivel_1304001_tres_grupos")


def test_nivel_se_muestra_sin_enlace_volver_a_niveles():
    client = _nuevo_cliente()
    client.post("/horario/parcial/seleccionar-modo", data={"modo": "manual"})
    resp = client.get("/horario/parcial/nivel/A")
    assert resp.status_code == 200
    texto = resp.data.decode("utf-8")
    assert "Volver a niveles" not in texto
    assert "Nivel" in texto
    print("PASS: test_nivel_se_muestra_sin_enlace_volver_a_niveles")


def test_limpiar_materias_devuelve_placeholder():
    client = _nuevo_cliente()
    client.post("/horario/parcial/seleccionar-modo", data={"modo": "manual"})
    resp = client.get("/horario/parcial/limpiar-materias")
    assert resp.status_code == 200
    assert b"Selecciona un nivel" in resp.data
    print("PASS: test_limpiar_materias_devuelve_placeholder")


def test_volver_a_materias_apunta_a_zona_materias():
    client = _nuevo_cliente()
    client.post("/horario/parcial/seleccionar-modo", data={"modo": "manual"})
    resp = client.get("/horario/parcial/grupos/1304001")
    assert resp.status_code == 200
    texto = resp.data.decode("utf-8")
    # El acordeon es el unico control: sin botones de cabecera redundantes.
    assert "Volver a materias" not in texto
    assert "Ocultar grupos" not in texto
    assert 'id="zona-grupos"' in texto
    print("PASS: test_volver_a_materias_apunta_a_zona_materias")


def test_pdf_vacio_rechazado():
    client = _nuevo_cliente()
    _iniciar_academico(client)
    resp = client.post(
        "/horario/kardex/subir",
        data={"kardex": (io.BytesIO(b""), "vacio.pdf")},
        content_type="multipart/form-data",
    )
    assert resp.status_code == 400
    assert b"vacio" in resp.data.lower()
    print("PASS: test_pdf_vacio_rechazado")


def test_pdf_grande_rechazado():
    client = _nuevo_cliente()
    _iniciar_academico(client)
    grande = b"%PDF-1.4" + (b"x" * (11 * 1024 * 1024))
    resp = client.post(
        "/horario/kardex/subir",
        data={"kardex": (io.BytesIO(grande), "grande.pdf")},
        content_type="multipart/form-data",
    )
    assert resp.status_code == 400
    assert b"10 MB" in resp.data
    with client.session_transaction() as sess:
        assert "kardex" not in sess
    print("PASS: test_pdf_grande_rechazado")


def test_nuevo_devuelve_200_y_limpia_sesion():
    client = _nuevo_cliente()
    client.post("/horario/parcial/seleccionar-modo", data={"modo": "manual"})
    with client.session_transaction() as sess:
        assert "plan" in sess
    resp = client.get("/nuevo")
    assert resp.status_code == 200
    assert b"Estudiante Nuevo" in resp.data
    assert b"Comenzar planificacion manual" in resp.data
    with client.session_transaction() as sess:
        assert "plan" not in sess
        assert "kardex" not in sess
    print("PASS: test_nuevo_devuelve_200_y_limpia_sesion")


def test_nuevo_muestra_pantalla_estudiante_nuevo():
    client = _nuevo_cliente()
    resp = client.get("/nuevo")
    assert resp.status_code == 200
    body = resp.data.decode("utf-8", "replace")
    assert "Estudiante Nuevo" in body
    assert "Arma tu horario sin historial academico" in body
    assert "zona-modo" not in body
    print("PASS: test_nuevo_muestra_pantalla_estudiante_nuevo")


def test_nuevo_boton_planificacion_manual_activa_manual():
    client = _nuevo_cliente()
    client.get("/nuevo")
    resp = client.get("/horario?modo=manual")
    assert resp.status_code == 200
    with client.session_transaction() as sess:
        assert sess["plan"]["modo"] == "manual"
    print("PASS: test_nuevo_boton_planificacion_manual_activa_manual")


if __name__ == "__main__":
    tests = [
        test_num_grupos_correctos_web,
        test_num_grupos_mayor_a_uno,
        test_materias_por_nivel_grupos_completos,
        test_materias_por_nivel_1304001_tres_grupos,
        test_volver_a_niveles_usa_limpiar_materias,
        test_limpiar_materias_devuelve_placeholder,
        test_volver_a_materias_apunta_a_zona_materias,
        test_pdf_vacio_rechazado,
        test_pdf_grande_rechazado,
        test_nuevo_devuelve_200_y_limpia_sesion,
        test_nuevo_muestra_pantalla_estudiante_nuevo,
        test_nuevo_boton_planificacion_manual_activa_manual,
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
    print("RESULTADOS REVISION: %d passed, %d failed, %d total" % (
        passed, failed, len(tests)))
    if failed == 0:
        print("TODOS LOS TESTS PASARON CORRECTAMENTE")
    else:
        print("ALGUNOS TESTS FALLARON")
    print("=" * 60)
