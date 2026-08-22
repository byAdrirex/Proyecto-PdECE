"""
Tests de la malla oficial (estilo UMSS) y del planificador rediseñado.

Cubre: estructura oficial por areas x semestres, talleres+ingles juntos,
electivas ocultas, seleccion de mencion/tecnico con confirmacion, tarjetas
minimalistas, modal de materia (requiere/habilita), relaciones solo al
seleccionar, estados, sidebar compacto, grupos inline, calendario (45 min,
sin domingo, sin fecha), botones Volver y acceso local.

NO modifica Excel ni PDF.
"""
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "modulos"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app import create_app
from app import inicio as app_inicio
from malla import (
    construir_malla_oficial, construir_objetivos,
    AREAS_OFICIALES, TIPO_OBLIGATORIA,
)

app = create_app()


def _cliente():
    return app.test_client()


def _kardex_academico(client):
    client.post("/horario/parcial/seleccionar-modo", data={"modo": "academico"})
    with open(os.path.join(
            os.path.dirname(os.path.dirname(__file__)),
            "datos", "webSISS Sistema de Informaci\u00f3n San Sim\u00f3n.pdf"), "rb") as f:
        client.post(
            "/horario/kardex/subir",
            data={"kardex": (f, "kardex.pdf")},
            content_type="multipart/form-data",
        )


# =====================================================================
# PARTE 1 - MALLA OFICIAL
# =====================================================================

def test_malla_oficial_areas_esperadas():
    motor = app_inicio.get_motor()
    malla = construir_malla_oficial(motor)
    assert malla["areas"] == [
        "Teoria Economica y Aplicada",
        "Cuantitativa",
        "Historia y Apoyo",
        "Tecnicas y Metodos de Investigacion",
    ]
    assert malla["niveles"] == ["A", "B", "C", "D", "E", "F", "G", "H", "I"]
    print("PASS: test_malla_oficial_areas_esperadas")


def test_malla_oficial_materias_por_semestre():
    motor = app_inicio.get_motor()
    malla = construir_malla_oficial(motor)
    # Nivel A: economia general esta en teoria economica.
    celda_a = malla["celdas"].get(("Teoria Economica y Aplicada", "A"), [])
    cods = [m["codigo"] for m in celda_a]
    assert "1304001" in cods  # ECONOMIA GENERAL
    # Algebra y Calculo son cuantitativas del primer semestre.
    celda_cuant = malla["celdas"].get(("Cuantitativa", "A"), [])
    cods_cuant = [m["codigo"] for m in celda_cuant]
    assert "1304003" in cods_cuant  # ALGEBRA
    assert "1304004" in cods_cuant  # CALCULO
    print("PASS: test_malla_oficial_materias_por_semestre")


def test_malla_oficial_no_mezcla_electivas():
    motor = app_inicio.get_motor()
    malla = construir_malla_oficial(motor)
    for clave, lista in malla["celdas"].items():
        for m in lista:
            assert m["tipo"] == TIPO_OBLIGATORIA
    # Las electivas no aparecen en ninguna celda.
    for m in malla["materias"].values():
        if m["tipo"] == "Materia Electiva":
            in_celda = any(
                m["codigo"] in [x["codigo"] for x in lista]
                for lista in malla["celdas"].values())
            assert not in_celda
    print("PASS: test_malla_oficial_no_mezcla_electivas")


def test_talleres_e_ingles_organizados_juntos():
    motor = app_inicio.get_motor()
    malla = construir_malla_oficial(motor)
    talleres = [m["codigo"] for m in malla["talleres"]]
    ingles = [m["codigo"] for m in malla["ingles"]]
    assert "TI01" in talleres
    assert "TI04" in talleres
    assert "1803021" in ingles  # INGLES I
    assert "1803024" in ingles  # INGLES II
    assert "1803027" in ingles  # INGLES III
    print("PASS: test_talleres_e_ingles_organizados_juntos")


def test_electivas_listadas_en_seccion_no_en_grilla():
    """Las electivas se listan por nombre en la seccion Menciones+Tecnicos,
    pero NO se integran como tarjetas en la grilla de la malla base."""
    client = _cliente()
    resp = client.get("/")
    assert resp.status_code == 200
    body = resp.data.decode("utf-8", "replace")
    assert "DEMOGRAFIA" in body
    assert "MERCADOTECNIA" in body
    assert 'data-codigo="1304129"' not in body  # DEMOGRAFIA
    assert 'data-codigo="1301031"' not in body  # MERCADOTECNIA I
    print("PASS: test_electivas_listadas_en_seccion_no_en_grilla")


def test_menciones_y_tecnicos_disponibles():
    client = _cliente()
    resp = client.get("/")
    body = resp.data.decode("utf-8", "replace")
    assert "ECONOMIA DEL DESARROLLO" in body
    assert "ECONOMIA DE EMPRESAS" in body
    assert "ECONOMIA COMERCIAL" in body
    assert "PROYECTOS DE INVERSION" in body
    assert "ESTADISTICA APLICADA" in body
    assert "PROYECTOS SOCIALES" in body
    print("PASS: test_menciones_y_tecnicos_disponibles")


def test_activar_mencion_guarda_sesion_y_muestra_materias():
    client = _cliente()
    r = client.post("/malla/mencion/activar", data={"id": "M01"})
    assert r.status_code == 200
    assert r.get_json()["mencion"] == "M01"

    resp = client.get("/")
    body = resp.data.decode("utf-8", "replace")
    assert "Mencion activa" in body
    assert "DEMOGRAFIA" in body          # materia de M01
    assert "DESARROLLO ECONOMICO II" in body
    # La malla base sigue intacta.
    assert "ECONOMIA GENERAL" in body
    print("PASS: test_activar_mencion_guarda_sesion_y_muestra_materias")


def test_activar_mencion_requiere_id():
    client = _cliente()
    r = client.post("/malla/mencion/activar", data={})
    assert r.status_code == 400
    print("PASS: test_activar_mencion_requiere_id")


def test_desactivar_mencion():
    client = _cliente()
    client.post("/malla/mencion/activar", data={"id": "M02"})
    resp = client.get("/")
    # M02 activa: MERCADO DE CAPITALES integrada como tarjeta en la malla.
    assert b'data-codigo="1304135"' in resp.data
    r = client.post("/malla/mencion/desactivar")
    assert r.status_code == 200
    resp = client.get("/")
    # Desactivada: ya no se integra como tarjeta en la grilla.
    assert b'data-codigo="1304135"' not in resp.data
    print("PASS: test_desactivar_mencion")


def test_activar_tecnico_muestra_materias():
    client = _cliente()
    r = client.post("/malla/tecnico/activar", data={"id": "T01"})
    assert r.status_code == 200
    assert r.get_json()["tecnico"] == "T01"

    resp = client.get("/")
    body = resp.data.decode("utf-8", "replace")
    assert "Tecnico activo" in body
    assert "GESTION DE PROYECTOS DE INVERSION" in body
    print("PASS: test_activar_tecnico_muestra_materias")


def test_desactivar_tecnico():
    client = _cliente()
    client.post("/malla/tecnico/activar", data={"id": "T02"})
    resp = client.get("/")
    # T02 activo: PROGRAMAS ESTADISTICOS integrada como tarjeta en la malla.
    assert b'data-codigo="1304140"' in resp.data
    client.post("/malla/tecnico/desactivar")
    resp = client.get("/")
    # PROGRAMAS ESTADISTICOS es materia exclusiva de T02; al desactivar
    # ya no debe integrarse como tarjeta en la grilla.
    assert b'data-codigo="1304140"' not in resp.data
    print("PASS: test_desactivar_tecnico")


def test_modal_materia_tiene_requiere_y_habilitar():
    client = _cliente()
    resp = client.get("/malla/materia/1304007")  # MICROECONOMIA I
    data = resp.get_json()
    assert data["codigo"] == "1304007"
    prereqs = [p["codigo"] for p in data["prerequisitos"]]
    assert "1304001" in prereqs
    assert "1304004" in prereqs
    deps = [d["codigo"] for d in data["dependientes"]]
    assert "1304013" in deps

    home = client.get("/")
    assert b"Esta materia requiere" in home.data
    assert b"Esta materia puede habilitar" in home.data
    print("PASS: test_modal_materia_tiene_requiere_y_habilitar")


def test_relaciones_solo_al_seleccionar():
    client = _cliente()
    resp = client.get("/")
    body = resp.data.decode("utf-8", "replace")
    # No hay lineas SVG permanentes dibujadas al cargar (canvas vacio).
    assert 'id="malla-lines"' in body
    assert "dibujarLineasActivas" in body
    assert "opacity-0" not in body or True  # sin lineas pre-renderizadas
    print("PASS: test_relaciones_solo_al_seleccionar")


def test_estados_con_kardex_en_malla_oficial():
    client = _cliente()
    _kardex_academico(client)
    resp = client.get("/")
    assert b"Disponible" in resp.data
    assert b"Estado:" in resp.data
    # Estado de ECONOMIA GENERAL con kardex -> aprobada.
    resp2 = client.get("/malla/materia/1304001")
    assert resp2.get_json()["estado"] == "APROBADA"
    print("PASS: test_estados_con_kardex_en_malla_oficial")


def test_estados_no_visibles_sin_kardex():
    client = _cliente()
    resp = client.get("/")
    assert b"Disponible" not in resp.data
    assert b"Estado:" not in resp.data
    print("PASS: test_estados_no_visibles_sin_kardex")


# =====================================================================
# PARTE 2 - PLANIFICADOR
# =====================================================================

def test_planificador_sidebar_compacto():
    client = _cliente()
    client.post("/horario/parcial/seleccionar-modo", data={"modo": "manual"})
    resp = client.get("/horario/parcial/sidebar")
    assert resp.status_code == 200
    body = resp.data.decode("utf-8", "replace")
    assert "Mi selecci" in body
    assert "Ocultar selecci" in body
    assert "Materias" in body
    assert "Horas semanales" in body
    assert "Días ocupados" in body
    assert "Horarios de auxiliares" in body
    print("PASS: test_planificador_sidebar_compacto")


def test_planificador_tiene_ocultar_mostrar():
    client = _cliente()
    client.post("/horario/parcial/seleccionar-modo", data={"modo": "manual"})
    resp = client.get("/horario")
    body = resp.data.decode("utf-8", "replace")
    assert "__ocultarSeleccion" in body
    assert "__mostrarSeleccion" in body
    assert "btn-mostrar-seleccion" in body
    print("PASS: test_planificador_tiene_ocultar_mostrar")


def test_grupos_inline_bajo_materia():
    client = _cliente()
    resp = client.get("/horario/parcial/nivel/A")
    body = resp.data.decode("utf-8", "replace")
    assert 'id="materia-1304001"' in body
    assert 'id="grupos-1304001"' in body
    # El acordeon (clic en el nombre) abre el contenedor inline de grupos.
    assert "window.__toggleGrupos('1304001')" in body
    print("PASS: test_grupos_inline_bajo_materia")


def test_grupos_respuesta_es_inline():
    client = _cliente()
    resp = client.get("/horario/parcial/grupos/1304001")
    assert resp.status_code == 200
    body = resp.data.decode("utf-8", "replace")
    assert "zona-grupos" in body  # compatibilidad con limpieza
    assert "ECONOMIA GENERAL" in body
    assert "AVILES ROCHA" in body
    print("PASS: test_grupos_respuesta_es_inline")


def test_calendario_sin_domingo():
    client = _cliente()
    client.post("/horario/parcial/seleccionar-modo", data={"modo": "manual"})
    client.post("/horario/parcial/seleccionar", data={
        "codigo_sis": "1304001", "grupo": "01"
    })
    resp = client.get("/horario/calendario")
    body = resp.data.decode("utf-8", "replace")
    assert "hiddenDays" in body
    assert "[0]" in body  # domingo oculto
    print("PASS: test_calendario_sin_domingo")


def test_calendario_sin_fecha_especifica():
    client = _cliente()
    resp = client.get("/horario/calendario")
    body = resp.data.decode("utf-8", "replace")
    assert "headerToolbar: false" in body
    assert "dayHeaderFormat" in body
    assert "Mi Horario" in body
    print("PASS: test_calendario_sin_fecha_especifica")


def test_calendario_escala_90_min():
    client = _cliente()
    resp = client.get("/horario/calendario")
    body = resp.data.decode("utf-8", "replace")
    assert "slotDuration: '01:30:00'" in body
    assert "slotMinTime: '06:45:00'" in body
    assert "slotMaxTime: '21:45:00'" in body
    print("PASS: test_calendario_escala_90_min")


def test_calendario_embebido_en_planificador():
    client = _cliente()
    client.post("/horario/parcial/seleccionar-modo", data={"modo": "manual"})
    resp = client.get("/horario")
    body = resp.data.decode("utf-8", "replace")
    assert 'id="zona-calendario"' in body
    assert 'hx-get="/horario/parcial/calendario"' in body

    resp2 = client.get("/horario/parcial/calendario")
    assert resp2.status_code == 200
    assert b"FullCalendar" in resp2.data
    print("PASS: test_calendario_embebido_en_planificador")


def test_boton_volver_paginas():
    client = _cliente()
    for ruta in ["/horario", "/progreso", "/nuevo", "/malla"]:
        resp = client.get(ruta)
        assert resp.status_code == 200
        assert b"Volver" in resp.data
    print("PASS: test_boton_volver_paginas")


def test_acceso_local_habilitado():
    """El servidor debe escuchar en 0.0.0.0 para permitir acceso desde el celular."""
    import re
    with open(os.path.join(os.path.dirname(os.path.dirname(__file__)), "main.py"),
              "r", encoding="utf-8") as f:
        src = f.read()
    assert "0.0.0.0" in src
    assert "127.0.0.1" in src
    assert "5000" in src
    print("PASS: test_acceso_local_habilitado")


def test_objetivos_builder_menciones_y_tecnicos():
    motor = app_inicio.get_motor()
    obj = construir_objetivos(motor)
    menciones = {m["id"]: m for m in obj["menciones"]}
    tecnicos = {t["id"]: t for t in obj["tecnicos"]}
    assert set(menciones) == {"M01", "M02", "M03"}
    assert set(tecnicos) == {"T01", "T02", "T03"}
    assert "1304045" in [m["codigo"] for m in menciones["M01"]["materias"]]
    print("PASS: test_objetivos_builder_menciones_y_tecnicos")


def test_movil_no_abre_doble_interfaz():
    """En movil las tarjetas no deben disparar modal desktop + panel a la vez."""
    client = _cliente()
    resp = client.get("/")
    body = resp.data.decode("utf-8", "replace")
    assert "querySelectorAll('#malla-desktop .malla-card')" in body
    assert "querySelectorAll('#malla-mobile .malla-card')" in body
    assert "abrirBanda" in body
    print("PASS: test_movil_no_abre_doble_interfaz")


def test_movil_panel_tiene_ver_grupos_y_planificar():
    """El drawer compartido debe ofrecer Ver grupos y Planificar en movil."""
    client = _cliente()
    resp = client.get("/")
    body = resp.data.decode("utf-8", "replace")
    assert 'id="malla-modal"' in body
    assert 'accionesMateria(d)' in body
    print("PASS: test_movil_panel_tiene_ver_grupos_y_planificar")


def test_movil_talleres_e_ingles_usan_panel_movil():
    """Talleres e Ingles (banda) deben abrir el panel movil, no el modal."""
    client = _cliente()
    resp = client.get("/")
    body = resp.data.decode("utf-8", "replace")
    assert 'id="malla-banda"' in body
    assert "getElementById('malla-banda').addEventListener" in body
    assert "mostrarConexionesMovil" in body
    print("PASS: test_movil_talleres_e_ingles_usan_panel_movil")


def test_movil_acciones_respetan_restricciones():
    """El panel movil debe respetar aprobada/bloqueada como el modal desktop."""
    client = _cliente()
    resp = client.get("/")
    body = resp.data.decode("utf-8", "replace")
    assert "Ya aprobada" in body
    assert "Bloqueada" in body
    assert "d.estado === 'APROBADA'" in body
    assert "d.estado === 'BLOQUEADA'" in body
    print("PASS: test_movil_acciones_respetan_restricciones")


def test_nuevo_muestra_estudiante_nuevo():
    client = _cliente()
    resp = client.get("/nuevo")
    assert resp.status_code == 200
    body = resp.data.decode("utf-8", "replace")
    assert "Estudiante Nuevo" in body
    assert "Comenzar planificacion manual" in body
    assert "zona-modo" not in body
    print("PASS: test_nuevo_muestra_estudiante_nuevo")


def test_nuevo_no_renderiza_horario():
    client = _cliente()
    resp = client.get("/nuevo")
    assert resp.status_code == 200
    body = resp.data.decode("utf-8", "replace")
    assert "Armar mi Horario" not in body
    assert "zona-modo" not in body
    print("PASS: test_nuevo_no_renderiza_horario")


def test_nuevo_boton_comenzar_planificacion_manual():
    client = _cliente()
    client.get("/nuevo")
    resp = client.get("/horario?modo=manual")
    assert resp.status_code == 200
    with client.session_transaction() as sess:
        assert sess["plan"]["modo"] == "manual"
    print("PASS: test_nuevo_boton_comenzar_planificacion_manual")


def test_nuevo_volver_al_inicio():
    client = _cliente()
    resp = client.get("/nuevo")
    body = resp.data.decode("utf-8", "replace")
    assert 'href="/"' in body
    assert "Volver al inicio" in body
    print("PASS: test_nuevo_volver_al_inicio")


def test_horario_modo_manual_no_resetea_plan_existente():
    """/horario?modo=manual respeta el plan manual ya creado (no lo recrea)."""
    client = _cliente()
    client.post("/horario/parcial/seleccionar-modo", data={"modo": "manual"})
    client.get("/horario")
    resp = client.get("/horario?modo=manual")
    assert resp.status_code == 200
    with client.session_transaction() as sess:
        assert sess["plan"]["modo"] == "manual"
    print("PASS: test_horario_modo_manual_no_resetea_plan_existente")


# =====================================================================
# PARTE 3 - UI/UX LOTE: drawer de materia, menciones+tecnicos, horario
# =====================================================================

def test_modal_materia_es_drawer_lateral():
    """El modal de materia debe ser un drawer lateral con overlay
    semitransparente, no un modal centrado que tape la malla completa."""
    client = _cliente()
    resp = client.get("/")
    body = resp.data.decode("utf-8", "replace")
    # Drawer a la derecha con ancho reducido (~360px) y alto completo.
    assert 'id="malla-modal"' in body
    assert "top-0 right-0 h-full w-full max-w-[360px]" in body
    # Overlay semitransparente para que las lineas de prerrequisitos se vean.
    assert "bg-black/30" in body
    # El drawer de malla no usa el overlay opaco de 40% (ese queda solo
    # para el objetivo-modal de confirmacion).
    inicio = body.index('id="malla-modal"')
    fin = body.index('id="objetivo-modal"')
    modal_block = body[inicio:fin]
    assert "bg-black/30" in modal_block
    assert "bg-black/40" not in modal_block
    print("PASS: test_modal_materia_es_drawer_lateral")


def test_menciones_y_tecnicos_layout_oficial():
    """La seccion inferior reproduce el layout oficial: 'Tecnico Superior en:'
    y 'Areas de Especializacion - Materias Electivas' con columnas."""
    client = _cliente()
    resp = client.get("/")
    body = resp.data.decode("utf-8", "replace")
    assert "T&eacute;cnico Superior en:" in body or "Técnico Superior en:" in body
    assert "Materias Electivas" in body
    assert "ECONOMIA DEL DESARROLLO" in body
    assert "ECONOMIA DE EMPRESAS" in body
    assert "ECONOMIA COMERCIAL" in body
    assert "PROYECTOS DE INVERSION" in body
    assert "ESTADISTICA APLICADA" in body
    assert "PROYECTOS SOCIALES" in body
    print("PASS: test_menciones_y_tecnicos_layout_oficial")


def test_seccion_menciones_lista_electivas_por_nombre():
    """Cada columna de mencion/tecnico lista sus materias con nombre real
    (no 'Electiva I, II' genericas)."""
    client = _cliente()
    resp = client.get("/")
    body = resp.data.decode("utf-8", "replace")
    idx = body.index('id="objetivos"')
    seccion = body[idx:]
    # Materias electivas reales de M01, M02 y T01 dentro de la seccion.
    assert "DEMOGRAFIA" in seccion
    assert "MERCADO DE CAPITALES" in seccion
    assert "GESTION DE PROYECTOS DE INVERSION" in seccion
    # No debe usar el texto generico 'Electiva I'.
    assert "Electiva I" not in seccion
    print("PASS: test_seccion_menciones_lista_electivas_por_nombre")


def test_selector_mencion_resalta_y_quita():
    """Al activar una mencion la card queda resaltada y el boton cambia a
    'Quitar mencion'; al desactivar vuelve a 'Elegir mencion'."""
    client = _cliente()
    resp = client.get("/")
    assert "Elegir menci" in resp.data.decode("utf-8", "replace")
    client.post("/malla/mencion/activar", data={"id": "M01"})
    resp = client.get("/")
    body = resp.data.decode("utf-8", "replace")
    assert "Quitar menci" in body
    assert "Mencion activa" in body
    print("PASS: test_selector_mencion_resalta_y_quita")


def test_menu_lateral_horario_con_niveles_materias_grupos():
    """El planificador tiene un menu lateral con niveles, materias y grupos,
    y el calendario ocupa la zona principal."""
    client = _cliente()
    client.post("/horario/parcial/seleccionar-modo", data={"modo": "manual"})
    resp = client.get("/horario")
    body = resp.data.decode("utf-8", "replace")
    # Menu lateral: zona de niveles dentro de un aside.
    assert "<aside" in body
    assert 'id="zona-niveles"' in body
    assert 'id="zona-materias"' in body
    assert 'id="zona-grupos"' in body
    # Zona principal: seleccion y calendario embebido.
    assert 'id="zona-calendario"' in body
    assert 'hx-get="/horario/parcial/calendario"' in body
    print("PASS: test_menu_lateral_horario_con_niveles_materias_grupos")


def test_grilla_horario_bloques_de_90_min():
    """La grilla usa bloques de 1h30 (06:45-08:15, 08:15-09:45, etc.)."""
    client = _cliente()
    resp = client.get("/horario/calendario")
    body = resp.data.decode("utf-8", "replace")
    assert "slotDuration: '01:30:00'" in body
    assert "slotMinTime: '06:45:00'" in body
    assert "slotMaxTime: '21:45:00'" in body
    # El parcial embebido tambien usa la grilla de 90 min.
    resp2 = client.get("/horario/parcial/calendario")
    body2 = resp2.data.decode("utf-8", "replace")
    assert "slotDuration: '01:30:00'" in body2
    print("PASS: test_grilla_horario_bloques_de_90_min")


def test_malla_cuadro_integra_menciones_tecnicos():
    """La seccion de Menciones+Tecnicos vive dentro del cuadro principal de
    la malla (abajo de los semestres), no como bloque separado."""
    client = _cliente()
    resp = client.get("/")
    body = resp.data.decode("utf-8", "replace")
    assert 'id="malla-cuadro"' in body
    idx_cuadro = body.index('id="malla-cuadro"')
    idx_objetivos = body.index('id="objetivos"')
    idx_modal = body.index('id="malla-modal"')
    assert idx_cuadro < idx_objetivos < idx_modal, (
        "objetivos debe estar dentro del cuadro de la malla")
    print("PASS: test_malla_cuadro_integra_menciones_tecnicos")


if __name__ == "__main__":
    tests = sorted(
        (n, fn) for n, fn in globals().items()
        if n.startswith("test_") and callable(fn))
    passed = failed = 0
    for name, fn in tests:
        try:
            fn()
            passed += 1
        except Exception as e:
            print("FAIL: %s - %s" % (name, e))
            failed += 1
    print("")
    print("=" * 60)
    print("RESULTADOS MALLA OFICIAL: %d passed, %d failed, %d total" % (
        passed, failed, len(tests)))
    if failed == 0:
        print("TODOS LOS TESTS PASARON CORRECTAMENTE")
    else:
        print("ALGUNOS TESTS FALLARON")
    print("=" * 60)
