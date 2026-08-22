"""Regresión de la ronda funcional: trayectorias, Kardex, flujo y UI."""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "modulos"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app import create_app
from app import inicio as app_inicio
from malla import construir_malla_oficial, construir_objetivos, integrar_objetivos
from motor_academico import determinar_estado_materia_completo
from importador_kardex import crear_kardex, configurar_gestion
from planificador import crear_planificador, MODO_ACADEMICO


app = create_app()


def _cliente():
    return app.test_client()


def _kardex_simple(codigo="1304001", nota=70):
    kardex = crear_kardex()
    configurar_gestion(kardex, 2026, 2)
    kardex["intentos"][codigo] = [{
        "nro": 1, "anio": 2025, "gestion": 2,
        "codigo_sis": codigo, "nfin": nota, "rfin": "APR",
        "estado_calculado": "APROBADA", "inconsistencias": [],
        "correccion_estudiante": None, "origen": "pdf",
    }]
    return kardex


def _activar(client, ruta, ids):
    for identificador in ids:
        respuesta = client.post(ruta, data={"id": identificador})
        assert respuesta.status_code == 200


def test_selecciona_tres_menciones_y_conserva_sesion():
    client = _cliente()
    _activar(client, "/malla/mencion/activar", ["M01", "M02", "M03"])
    with client.session_transaction() as sesion:
        assert sesion["menciones"] == ["M01", "M02", "M03"]
    body = client.get("/").data.decode("utf-8", "replace")
    assert body.count("Mencion activa") == 3


def test_selecciona_tres_tecnicos_y_no_duplica_ids():
    client = _cliente()
    _activar(client, "/malla/tecnico/activar", ["T01", "T02", "T03"])
    client.post("/malla/tecnico/activar", data={"id": "T02"})
    with client.session_transaction() as sesion:
        assert sesion["tecnicos"] == ["T01", "T02", "T03"]


def test_materia_compartida_se_consolida_con_pertenencias():
    motor = app_inicio.get_motor()
    malla = construir_malla_oficial(motor)
    objetivos = construir_objetivos(motor, malla)
    integrar_objetivos(malla, objetivos, ["M02"], ["T01"])
    materia = malla["integradas"]["1304063"]
    assert len(materia["pertenencias"]) == 2
    assert {p["id"] for p in materia["pertenencias"]} == {"M02", "T01"}


def test_materia_compartida_se_mantiene_al_desactivar_una_y_desaparece_al_desactivar_ambas():
    client = _cliente()
    _activar(client, "/malla/mencion/activar", ["M02"])
    _activar(client, "/malla/tecnico/activar", ["T01"])
    body = client.get("/").data.decode("utf-8", "replace")
    desktop = body.split('id="malla-mobile"')[0]
    assert desktop.count('data-codigo="1304063"') == 1

    client.post("/malla/mencion/desactivar", data={"id": "M02"})
    body = client.get("/").data.decode("utf-8", "replace")
    assert body.split('id="malla-mobile"')[0].count('data-codigo="1304063"') == 1

    client.post("/malla/tecnico/desactivar", data={"id": "T01"})
    body = client.get("/").data.decode("utf-8", "replace")
    assert 'data-codigo="1304063"' not in body


def test_taller_e_ingles_comparten_detalle_responsive():
    client = _cliente()
    body = client.get("/").data.decode("utf-8", "replace")
    assert 'id="malla-banda"' in body
    assert 'data-codigo="TI01"' in body
    assert 'data-codigo="1803027"' in body
    assert "abrirBanda" in body
    assert "mostrarConexionesMovil" in body
    detalle = client.get("/malla/materia/1803027").get_json()
    assert detalle["nombre"] == "INGLES III"
    assert "prerequisitos" in detalle and "dependientes" in detalle


def test_malla_movil_monta_todos_los_semestres_en_grilla_horizontal():
    body = _cliente().get("/").get_data(as_text=True)
    assert 'id="malla-mobile-grid"' in body
    assert 'aria-label="Malla curricular desplazable horizontalmente"' in body
    assert "malla-mobile-semestre" in body
    assert "Desliza horizontalmente" in body
    assert "nivel-tab" not in body


def test_talleres_e_ingles_pasan_por_el_drawer_compartido():
    body = _cliente().get("/").get_data(as_text=True)
    assert 'id="malla-banda"' in body
    assert "mostrarConexionesMovil" in body
    assert "abrirModal(card.dataset.codigo)" in body
    for codigo in ("TI01", "TI02", "TI03", "TI04", "1803027"):
        assert 'data-codigo="%s"' % codigo in body


def test_eliminar_materia_importada_solo_afecta_la_sesion():
    client = _cliente()
    kardex = _kardex_simple()
    with client.session_transaction() as sesion:
        sesion["kardex"] = kardex
        sesion["plan"] = crear_planificador(2, 2026, MODO_ACADEMICO)
    inicial = client.get("/horario/kardex/resumen").get_data(as_text=True)
    assert "¿Eliminar esta materia del Kardex?" in inicial
    respuesta = client.post("/horario/kardex/quitar",
                            data={"codigo_sis": "1304001"})
    assert respuesta.status_code == 200
    with client.session_transaction() as sesion:
        assert "1304001" not in sesion["kardex"]["intentos"]


def test_manual_redirige_a_malla_y_no_crea_kardex():
    client = _cliente()
    respuesta = client.post(
        "/horario/parcial/seleccionar-modo", data={"modo": "manual"}
    )
    assert respuesta.headers.get("HX-Redirect") == "/malla"
    with client.session_transaction() as sesion:
        assert sesion["plan"]["modo"] == "manual"
        assert "kardex" not in sesion


def test_resumen_continua_a_malla():
    client = _cliente()
    kardex = _kardex_simple()
    with client.session_transaction() as sesion:
        sesion["kardex"] = kardex
        sesion["plan"] = crear_planificador(2, 2026, MODO_ACADEMICO)
    body = client.get("/horario/kardex/resumen").get_data(as_text=True)
    assert 'href="/malla"' in body
    assert "Continuar a la malla" in body


def test_materia_disponible_se_destaca_en_planificador():
    motor = app_inicio.get_motor()
    codigo = next(
        c for c in motor["mapa_prereq"]
        if determinar_estado_materia_completo(c, motor)["estado"] == "DISPONIBLE"
        and app_inicio.get_grupos_por_materia(c)
    )
    nivel = app_inicio.get_grupos_por_materia(codigo)[0]["nivel"]
    client = _cliente()
    with client.session_transaction() as sesion:
        sesion["kardex"] = motor["kardex"]
        sesion["plan"] = crear_planificador(2, 2026, MODO_ACADEMICO)
    body = client.get("/horario/parcial/nivel/" + nivel).get_data(as_text=True)
    assert "Disponible para tomar" in body


def test_footer_identifica_umss_economia():
    body = _cliente().get("/").get_data(as_text=True)
    assert "Planificador Acad&eacute;mico &mdash; UMSS Carrera de Econom&iacute;a" in body


def test_calendario_conserva_filas_y_separa_dias():
    client = _cliente()
    client.post("/horario/parcial/seleccionar-modo", data={"modo": "manual"})
    body = client.get("/horario/parcial/calendario").get_data(as_text=True)
    assert "slotMinHeight: 88" in body
    assert "ajustarAlturaDeSlots" in body
    assert ".fc-timegrid-col { border-left: 1px solid #e5e7eb; }" in body
    assert "hiddenDays: [0]" in body
    assert "slotDuration: '01:30:00'" in body
    assert 'id="calendar-scroll"' in body
    assert "eventDidMount" in body
    assert "bloque.scrollHeight" in body
    assert "overflow: hidden" in body
    assert "#calendar { min-width: 860px; }" in body


def test_colores_divididos_para_una_dos_tres_y_cuatro_trayectorias():
    motor = app_inicio.get_motor()
    base = construir_malla_oficial(motor)
    objetivos = construir_objetivos(motor, base)
    todos = [("mencion", o["id"]) for o in objetivos["menciones"]]
    todos += [("tecnico", o["id"]) for o in objetivos["tecnicos"]]
    codigos = {}
    for tipo, objetivo in todos:
        lista = next(x for x in objetivos["menciones" if tipo == "mencion" else "tecnicos"]
                     if x["id"] == objetivo)["materias"]
        for materia in lista:
            codigos.setdefault(materia["codigo"], set()).add((tipo, objetivo))
    for cantidad in (1, 2, 3, 4):
        codigo, pertenencias = next(
            (c, p) for c, p in codigos.items() if len(p) >= cantidad
        )
        seleccion = list(pertenencias)[:cantidad]
        menciones = [x[1] for x in seleccion if x[0] == "mencion"]
        tecnicos = [x[1] for x in seleccion if x[0] == "tecnico"]
        integrar_objetivos(base, objetivos, menciones, tecnicos)
        materia = base["integradas"][codigo]
        assert len(materia["pertenencias"]) == cantidad
        assert materia["color_gradient"].count("#") == cantidad


def test_detalle_muestra_solo_pertenencias_activas_y_creditos_completos():
    client = _cliente()
    client.post("/malla/mencion/activar", data={"id": "M02"})
    client.post("/malla/tecnico/activar", data={"id": "T01"})
    detalle = client.get("/malla/materia/1304063").get_json()
    assert {p["id"] for p in detalle["pertenencias"]} == {"M02", "T01"}
    body = client.get("/").get_data(as_text=True)
    assert "créditos" in body
    assert "Materia integrada en la malla" not in body


def test_economia_comercial_aplica_las_sustituciones_del_excel():
    client = _cliente()
    client.post("/malla/mencion/activar", data={"id": "M03"})
    body = client.get("/").get_data(as_text=True)
    desktop = body.split('id="malla-mobile"')[0]
    for original in ("1304022", "1304028", "1304035", "1304033"):
        assert 'data-codigo="%s"' % original not in desktop
    for sustituta in ("1304160", "1301031", "1301034", "1304159"):
        assert 'data-codigo="%s"' % sustituta in desktop
    assert "Sustituye:" in body


def test_horario_filtra_electivas_por_trayectoria_activa():
    motor = app_inicio.get_motor()
    objetivos = construir_objetivos(motor)
    m01 = next(o for o in objetivos["menciones"] if o["id"] == "M01")
    m02 = next(o for o in objetivos["menciones"] if o["id"] == "M02")
    exclusiva = next(
        m["codigo"] for m in m01["materias"]
        if m["codigo"] not in {x["codigo"] for x in m02["materias"]}
        and app_inicio.get_grupos_por_materia(m["codigo"])
    )
    nivel = app_inicio.get_grupos_por_materia(exclusiva)[0]["nivel"]
    client = _cliente()
    client.post("/malla/mencion/activar", data={"id": "M02"})
    client.post("/horario/parcial/seleccionar-modo", data={"modo": "manual"})
    body = client.get("/horario/parcial/nivel/" + nivel).get_data(as_text=True)
    assert 'materia-%s' % exclusiva not in body
    assert "ECONOMIA GENERAL" in client.get("/horario/parcial/nivel/A").get_data(as_text=True)


def test_soy_nuevo_va_directamente_al_horario():
    client = _cliente()
    response = client.post(
        "/horario/parcial/seleccionar-modo",
        data={"modo": "manual", "destino": "horario"},
    )
    assert response.headers.get("HX-Redirect") == "/horario"
