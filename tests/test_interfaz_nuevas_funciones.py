"""Regresiones para acciones de interfaz y navegacion del planificador."""

from app import create_app
from app import inicio as app_inicio
from planificador import crear_planificador, MODO_ACADEMICO
from app.inicio import calendario_eventos


app = create_app()


def _cliente():
    return app.test_client()


def test_botones_flotantes_tienen_acciones():
    body = _cliente().get("/").get_data(as_text=True)
    assert 'id="btn-fotografia"' in body
    assert "html2canvas" in body
    assert 'id="btn-reportar-error"' in body
    assert "https://wa.link/fq4ozm" in body


def test_progreso_sin_kardex_muestra_dos_opciones():
    response = _cliente().get("/progreso")
    assert response.status_code == 200
    body = response.get_data(as_text=True)
    assert "Cargar Kardex" in body
    assert "Agregar materias manualmente" in body
    assert 'href="/horario?modo=academico&origen=progreso"' in body
    assert 'href="/horario?modo=manual&origen=progreso"' in body


def test_horario_tiene_malla_historial_y_acordeon_de_niveles():
    client = _cliente()
    client.post("/horario/parcial/seleccionar-modo", data={"modo": "manual"})
    body = client.get("/horario").get_data(as_text=True)
    assert 'href="/malla"' in body
    assert "window.history.back()" in body
    assert "window.__nivelAbierto" in body
    assert "event.preventDefault()" in body
    assert "Volver a niveles" not in body


def test_horario_con_kardex_activo_no_vuelve_a_pedirlo():
    motor = app_inicio.get_motor()
    client = _cliente()
    with client.session_transaction() as session:
        session["kardex"] = motor["kardex"]
        session["plan"] = crear_planificador(2, 2026, MODO_ACADEMICO)
    body = client.get("/horario").get_data(as_text=True)
    assert "Cargar Kardex" not in body
    assert 'id="zona-materias"' in body
    assert "malla" in body.lower()


def test_flujo_desde_progreso_no_repite_boton_de_armar_horario():
    body = _cliente().get("/horario?modo=academico&origen=progreso").get_data(as_text=True)
    assert "Tengo mi kardex" in body
    assert "Quiero armar mi horario" not in body


def test_resumen_kardex_ofrece_horario_y_progreso():
    motor = app_inicio.get_motor()
    client = _cliente()
    with client.session_transaction() as session:
        session["kardex"] = motor["kardex"]
        session["plan"] = crear_planificador(2, 2026, MODO_ACADEMICO)
    body = client.get("/horario/kardex/resumen").get_data(as_text=True)
    assert "Armar mi horario" in body
    assert "Ver mi progreso" in body


def test_progreso_con_kardex_separa_obligatorias_y_electivas():
    motor = app_inicio.get_motor()
    client = _cliente()
    with client.session_transaction() as session:
        session["kardex"] = motor["kardex"]
        session["plan"] = crear_planificador(2, 2026, MODO_ACADEMICO)
    body = client.get("/progreso").get_data(as_text=True)
    assert "Obligatorias aprobadas" in body
    assert "Electivas aprobadas" in body
    assert "Estado de materias" in body
    assert "Menciones y T&eacute;cnicos activos" in body
    assert "Ver malla curricular" in body
    assert "Ver materias disponibles" in body
    assert "/ 8" in body or "Electivas aprobadas" in body


def test_calendario_contiene_bloques_limitados_a_su_celda():
    client = _cliente()
    client.post("/horario/parcial/seleccionar-modo", data={"modo": "manual"})
    body = client.get("/horario/parcial/calendario").get_data(as_text=True)
    assert "overflow: hidden" in body
    assert ".fc-timegrid-event-harness" in body
    assert "88px" in body
    assert "--pde-slot-height" in body
    assert "expandRows: false" in body
    assert "bloque.scrollHeight" in body
    assert "[AUX]" in body


def test_conflicto_solo_marca_el_bloque_horario_que_choca():
    plan = {
        "modo_aux": True,
        "conflictos": [{
            "materia1": "A", "grupo1": "01", "tipo1": "CLASE",
            "materia2": "B", "grupo2": "01", "tipo2": "CLASE",
            "dia": "LU", "hora_inicio1": "08:00", "hora_fin1": "09:30",
            "hora_inicio2": "08:30", "hora_fin2": "10:00",
        }],
        "grupos_seleccionados": [
            {"codigo_sis": "A", "grupo": "01", "nombre": "Materia A",
             "horarios": [
                 {"dia": "LU", "hora_inicio": "08:00", "hora_fin": "09:30", "aula": "E1"},
                 {"dia": "MA", "hora_inicio": "08:00", "hora_fin": "09:30", "aula": "E2"},
             ], "auxiliares": []},
            {"codigo_sis": "B", "grupo": "01", "nombre": "Materia B",
             "horarios": [{"dia": "LU", "hora_inicio": "08:30", "hora_fin": "10:00", "aula": "E3"}],
             "auxiliares": []},
        ],
    }
    eventos = calendario_eventos(plan)
    a = [e for e in eventos if e["extendedProps"]["codigo"] == "A"]
    assert [e["extendedProps"]["conflicto"] for e in a] == [True, False]
