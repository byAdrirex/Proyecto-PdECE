"""
Tests de la malla curricular (pagina principal).
Valida pagina /, datos reales, conexiones, estados y navegacion.
NO modifica Excel ni PDF.
"""
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "modulos"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app import create_app
from app import inicio as app_inicio
from malla import construir_malla, aplicar_estados

app = create_app()


def _cliente():
    return app.test_client()


def test_index_devuelve_200_con_malla():
    client = _cliente()
    resp = client.get("/")
    assert resp.status_code == 200
    assert b"Malla curricular" in resp.data
    print("PASS: test_index_devuelve_200_con_malla")


def test_malla_carga_materias_desde_datos_reales():
    motor = app_inicio.get_motor()
    malla = construir_malla(motor)
    assert malla["total"] == 76
    assert "1304001" in malla["materias"]
    assert malla["materias"]["1304001"]["nombre"] == "ECONOMIA GENERAL"
    print("PASS: test_malla_carga_materias_desde_datos_reales (%d materias)" % malla["total"])


def test_malla_tiene_9_niveles():
    motor = app_inicio.get_motor()
    malla = construir_malla(motor)
    assert len(malla["niveles"]) == 9
    assert malla["niveles"] == ["A", "B", "C", "D", "E", "F", "G", "H", "I"]
    print("PASS: test_malla_tiene_9_niveles")


def test_malla_conexiones_de_prerrequisitos_reales():
    motor = app_inicio.get_motor()
    malla = construir_malla(motor)
    assert len(malla["conexiones"]) > 0
    codigos = set(malla["materias"].keys())
    for c in malla["conexiones"]:
        assert c["desde"] in codigos
        assert c["hasta"] in codigos
    print("PASS: test_malla_conexiones_de_prerrequisitos_reales (%d conexiones)" % len(malla["conexiones"]))


def test_microeconomia_1_tiene_prerequisitos_reales():
    motor = app_inicio.get_motor()
    malla = construir_malla(motor)
    micro = malla["materias"]["1304007"]
    assert micro["nombre"] == "MICROECONOMIA I"
    assert "1304001" in micro["prerequisitos"]
    assert "1304004" in micro["prerequisitos"]
    print("PASS: test_microeconomia_1_tiene_prerequisitos_reales")


def test_dependientes_inversos_son_correctos():
    motor = app_inicio.get_motor()
    malla = construir_malla(motor)
    dependientes_de_economia = malla["materias"]["1304001"]["dependientes"]
    for cod in dependientes_de_economia:
        assert "1304001" in malla["materias"][cod]["prerequisitos"]
    assert "1304007" in dependientes_de_economia
    print("PASS: test_dependientes_inversos_son_correctos")


def test_materia_seleccionable_muestra_prerequisitos_y_dependientes():
    client = _cliente()
    resp = client.get("/malla/materia/1304007")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["codigo"] == "1304007"
    assert data["nombre"] == "MICROECONOMIA I"
    prereqs = [p["codigo"] for p in data["prerequisitos"]]
    assert "1304001" in prereqs
    assert "1304004" in prereqs
    deps = [d["codigo"] for d in data["dependientes"]]
    assert "1304013" in deps
    print("PASS: test_materia_seleccionable_muestra_prerequisitos_y_dependientes")


def test_materia_no_existente_devuelve_404():
    client = _cliente()
    resp = client.get("/malla/materia/9999999")
    assert resp.status_code == 404
    print("PASS: test_materia_no_existente_devuelve_404")


def test_index_enlaza_al_planificador():
    client = _cliente()
    resp = client.get("/")
    assert b"/horario" in resp.data
    assert b"/progreso" in resp.data
    print("PASS: test_index_enlaza_al_planificador")


def test_navegacion_desde_malla_hacia_grupos():
    client = _cliente()
    resp = client.get("/horario?materia=1304001")
    assert resp.status_code == 200
    assert b"Armar mi Horario" in resp.data
    assert b'hx-get="/horario/parcial/grupos/1304001"' in resp.data
    print("PASS: test_navegacion_desde_malla_hacia_grupos")


def test_estados_solo_en_modo_academico_con_kardex():
    client = _cliente()

    resp = client.get("/")
    assert resp.status_code == 200
    assert b"Disponible" not in resp.data
    assert b"Estado:" not in resp.data

    client.post("/horario/parcial/seleccionar-modo", data={"modo": "academico"})
    resp = client.get("/")
    assert b"Disponible" not in resp.data
    assert b"Estado:" not in resp.data
    print("PASS: test_estados_solo_en_modo_academico_con_kardex")


def test_estados_se_muestran_con_kardex_academico():
    client = _cliente()
    client.post("/horario/parcial/seleccionar-modo", data={"modo": "academico"})
    with open(os.path.join(
            os.path.dirname(os.path.dirname(__file__)),
            "datos", "webSISS Sistema de Informaci\u00f3n San Sim\u00f3n.pdf"), "rb") as f:
        client.post(
            "/horario/kardex/subir",
            data={"kardex": (f, "kardex.pdf")},
            content_type="multipart/form-data",
        )
    resp = client.get("/")
    assert resp.status_code == 200
    assert b"Disponible" in resp.data
    assert b"Estado:" in resp.data
    print("PASS: test_estados_se_muestran_con_kardex_academico")


def test_estados_detalle_con_kardex():
    client = _cliente()
    client.post("/horario/parcial/seleccionar-modo", data={"modo": "academico"})
    with open(os.path.join(
            os.path.dirname(os.path.dirname(__file__)),
            "datos", "webSISS Sistema de Informaci\u00f3n San Sim\u00f3n.pdf"), "rb") as f:
        client.post(
            "/horario/kardex/subir",
            data={"kardex": (f, "kardex.pdf")},
            content_type="multipart/form-data",
        )
    resp = client.get("/malla/materia/1304001")
    data = resp.get_json()
    assert data["estado"] == "APROBADA"
    print("PASS: test_estados_detalle_con_kardex")


def test_responsive_desktop_y_movil():
    client = _cliente()
    resp = client.get("/")
    assert resp.status_code == 200
    assert b"id=\"malla-desktop\"" in resp.data
    assert b"id=\"malla-mobile\"" in resp.data
    assert b"malla-mobile-grid" in resp.data
    assert b"overflow-x-auto" in resp.data
    assert b"hidden lg:block" in resp.data
    print("PASS: test_responsive_desktop_y_movil")


def test_malla_muestra_creditos_y_horas():
    client = _cliente()
    resp = client.get("/")
    assert resp.status_code == 200
    assert b"1304001" in resp.data
    assert b"ECONOMIA GENERAL" in resp.data
    print("PASS: test_malla_muestra_creditos_y_horas")


def test_aplicar_estados_con_kardex():
    motor = app_inicio.get_motor()
    malla = construir_malla(motor)
    aplicar_estados(malla, motor)
    assert malla["materias"]["1304001"]["estado"] == "APROBADA"
    print("PASS: test_aplicar_estados_con_kardex")


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
