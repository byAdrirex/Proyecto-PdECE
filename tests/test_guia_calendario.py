"""Regresiones para la Guia y el visor del Calendario Academico."""

from app import create_app


app = create_app()


def _cliente():
    return app.test_client()


def test_navegacion_y_inicio_muestran_guia_y_calendario_academico():
    body = _cliente().get("/").get_data(as_text=True)
    assert 'href="/guia"' in body
    assert 'href="/calendario-academico"' in body
    assert "Calendario Acad&eacute;mico" in body

    nav = body.split("<main", 1)[0]
    assert 'href="/guia"' in nav
    assert 'href="/calendario-academico"' in nav


def test_guia_contiene_acordeones_textos_y_tarjetas():
    response = _cliente().get("/guia")
    assert response.status_code == 200
    body = response.get_data(as_text=True)
    assert body.count("<details class=\"guia-acordeon\"") == 10
    assert "Esta plataforma fue creada de forma independiente" in body
    assert "Aprobar 8 materias electivas" in body
    assert "Modalidades de Titulaci&oacute;n" in body
    assert "Esta secci&oacute;n se ir&aacute; completando" in body
    assert "https://websis.umss.edu.bo/serv_estudiantes.asp" in body
    assert "https://moodle.fce.umss.edu.bo/login/index.php" in body
    assert "https://www.umss.edu.bo/tramites/" in body
    assert "guia-enlace" in body


def test_calendario_academico_muestra_visores_o_aviso_de_pdf():
    response = _cliente().get("/calendario-academico")
    assert response.status_code == 200
    body = response.get_data(as_text=True)
    assert "Calendario Acad&eacute;mico" in body
    assert "calendarios/" in body
    assert "pdf-viewer" in body
    assert "pdfjsLib.getDocument" in body
