"""
Tests del lote de correcciones UI/flujos:
  1. Seleccionar/eliminar grupo responden JSON (sin overlay).
  2. Calendario grande arriba de la seleccion, sin "Vista completa", estilos pastel.
  3. Alta manual de materias + nota (fallback OCR) con autocompletado.
  4. Nuevos textos de navegacion: "Quiero armar mi horario", sin "Nuevo",
     boton de reportar error, "Elegir tecnico".
  5. Flujo de modo: "Cargar Kardex", "Seleccionar manualmente", "Soy nuevo".
NO modifica Excel ni PDF.
"""
import os
import re
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "modulos"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app import create_app

app = create_app()


def _cliente():
    return app.test_client()


def _modo_manual(client):
    client.get("/horario")
    return client.post(
        "/horario/parcial/seleccionar-modo", data={"modo": "manual"}
    )


def test_seleccionar_devuelve_json():
    client = _cliente()
    _modo_manual(client)
    resp = client.post(
        "/horario/parcial/seleccionar",
        data={"codigo_sis": "1304001", "grupo": "01"},
    )
    assert resp.status_code == 200
    data = resp.get_json()
    assert data is not None
    assert data["ok"] is True
    assert "msg" in data
    print("PASS: test_seleccionar_devuelve_json")


def test_eliminar_devuelve_json():
    client = _cliente()
    _modo_manual(client)
    client.post(
        "/horario/parcial/seleccionar",
        data={"codigo_sis": "1304001", "grupo": "01"},
    )
    resp = client.post(
        "/horario/parcial/eliminar",
        data={"codigo_sis": "1304001", "grupo": "01"},
    )
    assert resp.status_code == 200
    data = resp.get_json()
    assert data is not None
    assert data["ok"] is True
    print("PASS: test_eliminar_devuelve_json")


def test_eliminar_quita_del_plan():
    client = _cliente()
    _modo_manual(client)
    client.post(
        "/horario/parcial/seleccionar",
        data={"codigo_sis": "1304001", "grupo": "01"},
    )
    client.post(
        "/horario/parcial/eliminar",
        data={"codigo_sis": "1304001", "grupo": "01"},
    )
    resp = client.get("/horario/parcial/sidebar")
    body = resp.data.decode("utf-8", "replace")
    assert "ECONOMIA GENERAL" not in body
    print("PASS: test_eliminar_quita_del_plan")


def test_calendario_parcial_sin_vista_completa_y_grande():
    client = _cliente()
    _modo_manual(client)
    resp = client.get("/horario/parcial/calendario")
    assert resp.status_code == 200
    body = resp.data.decode("utf-8", "replace")
    assert "Vista completa" not in body
    assert "min-height: 1200px" not in body
    assert "min-height: 2000px" not in body
    assert "slotMinHeight: 88" in body
    assert "ajustarAlturaDeSlots" in body
    assert ".fc-col-header-cell" in body
    assert "fc-day-today" in body
    assert "expandRows: false" in body
    assert "'/horario/parcial/calendario-eventos'" in body
    print("PASS: test_calendario_parcial_sin_vista_completa_y_grande")


def test_calendario_fuentes_grandes():
    client = _cliente()
    _modo_manual(client)
    resp = client.get("/horario/parcial/calendario")
    body = resp.data.decode("utf-8", "replace")
    assert "font-size: 16px" in body
    assert ".fc-bloque-nombre { font-size: 12px" in body
    assert "overflow: hidden" in body
    assert ".fc-hora-rango { font-size: 13px" in body
    print("PASS: test_calendario_fuentes_grandes")


def test_calendario_miercoles_no_blanco_y_hora_oscura():
    client = _cliente()
    _modo_manual(client)
    resp = client.get("/horario/parcial/calendario")
    body = resp.data.decode("utf-8", "replace")
    assert ".fc-timegrid-col.fc-day-today" in body
    assert re.search(r"\.fc-day-today\s*\{", body) is None
    assert "#e2e8f0" in body
    assert ".fc-timegrid-axis.fc-col-header-cell" in body
    assert ".fc-timegrid-slot-main, .fc-timegrid-col { background: #ffffff; }" in body
    print("PASS: test_calendario_miercoles_no_blanco_y_hora_oscura")


def test_planificador_calendario_arriba_de_seleccion():
    client = _cliente()
    _modo_manual(client)
    resp = client.get("/horario")
    body = resp.data.decode("utf-8", "replace")
    idx_cal = body.index('id="zona-calendario"')
    idx_sel = body.index('id="zona-seleccion"')
    assert idx_cal < idx_sel
    print("PASS: test_planificador_calendario_arriba_de_seleccion")


def test_grupos_tienen_checkboxes_sin_boton():
    client = _cliente()
    _modo_manual(client)
    resp = client.get("/horario/parcial/grupos/1304001")
    body = resp.data.decode("utf-8", "replace")
    assert "__toggleGrupo" in body
    assert "type=\"checkbox\"" in body
    assert "Seleccionar este grupo" not in body
    print("PASS: test_grupos_tienen_checkboxes_sin_boton")


def test_api_materias():
    client = _cliente()
    resp = client.get("/horario/api/materias")
    assert resp.status_code == 200
    lista = resp.get_json()
    assert isinstance(lista, list)
    codigos = {m["codigo"] for m in lista}
    assert "1304001" in codigos
    assert all("nombre" in m for m in lista)
    print("PASS: test_api_materias (%d materias)" % len(lista))


def test_agregar_manual_muestra_pagina():
    client = _cliente()
    client.get("/horario")
    resp = client.get("/horario/kardex/manual")
    assert resp.status_code == 200
    body = resp.data.decode("utf-8", "replace")
    assert "Agregar materias manualmente" in body
    assert "mat-datalist" in body
    assert "/horario/api/materias" in body
    assert "Continuar al planificador" in body
    print("PASS: test_agregar_manual_muestra_pagina")


def test_agregar_manual_guarda_kardex():
    client = _cliente()
    client.get("/horario")
    resp = client.post(
        "/horario/kardex/manual/agregar",
        data={"codigo_sis": "1304001", "nota": "71"},
    )
    assert resp.status_code == 200
    with client.session_transaction() as sess:
        kardex = sess.get("kardex")
        assert kardex is not None
        assert "1304001" in kardex["intentos"]
        ultimo = kardex["intentos"]["1304001"][-1]
        assert ultimo["estado_calculado"] == "APROBADA"
    print("PASS: test_agregar_manual_guarda_kardex")


def test_agregar_manual_nota_invalida():
    client = _cliente()
    client.get("/horario")
    resp = client.post(
        "/horario/kardex/manual/agregar",
        data={"codigo_sis": "1304001", "nota": "abc"},
    )
    assert resp.status_code == 200
    assert b"nota valida" in resp.data.lower()
    print("PASS: test_agregar_manual_nota_invalida")


def test_base_nav_nuevos_textos():
    client = _cliente()
    resp = client.get("/")
    body = resp.data.decode("utf-8", "replace")
    assert "Quiero armar mi horario" in body
    assert 'href="/nuevo"' not in body
    assert "Necesito ayuda" in body
    assert "https://wa.link/fq4ozm" in body
    print("PASS: test_base_nav_nuevos_textos")


def test_modo_seleccion_nuevos_botones():
    client = _cliente()
    client.get("/horario")
    resp = client.get("/horario")
    body = resp.data.decode("utf-8", "replace")
    assert "Quieres cargar tu Kardex" in body
    assert "Cargar Kardex" in body
    assert "Seleccionar manualmente" in body
    assert "Soy nuevo" in body
    print("PASS: test_modo_seleccion_nuevos_botones")


def test_index_elegir_tecnico():
    client = _cliente()
    resp = client.get("/")
    body = resp.data.decode("utf-8", "replace")
    assert "Elegir t&eacute;cnico" in body
    assert "Seguir t&eacute;cnico" not in body
    assert "Elegir menci&oacute;n" in body
    print("PASS: test_index_elegir_tecnico")


def test_malla_banner_materias_integradas():
    client = _cliente()
    client.post("/malla/mencion/activar", data={"id": "M01"})
    resp = client.get("/")
    body = resp.data.decode("utf-8", "replace")
    assert "Materias integradas en la malla" not in body
    assert "Trayectorias activas" in body
    print("PASS: test_malla_banner_materias_integradas")


def test_calendario_eventos_endpoint_json():
    client = _cliente()
    _modo_manual(client)
    client.post(
        "/horario/parcial/seleccionar",
        data={"codigo_sis": "1304001", "grupo": "01"},
    )
    resp = client.get("/horario/parcial/calendario-eventos")
    assert resp.status_code == 200
    eventos = resp.get_json()
    assert isinstance(eventos, list)
    assert any(e["extendedProps"]["tipo"] == "CLASE" for e in eventos)
    print("PASS: test_calendario_eventos_endpoint_json")


def test_calendario_columnas_blancas_y_rojo_intenso():
    client = _cliente()
    _modo_manual(client)
    resp = client.get("/horario/parcial/calendario")
    body = resp.data.decode("utf-8", "replace")
    assert ".fc-timegrid-slots .fc-timegrid-slot { background: transparent; }" in body
    assert "#eef2ff" not in body
    assert "#ef4444" in body
    print("PASS: test_calendario_columnas_blancas_y_rojo_intenso")


def test_planificador_tiene_menu_colapsable():
    client = _cliente()
    _modo_manual(client)
    resp = client.get("/horario")
    body = resp.data.decode("utf-8", "replace")
    assert 'id="btn-menu"' in body
    assert "window.__toggleMenu" in body
    assert 'id="menu-lateral"' in body
    assert 'id="zona-principal"' in body
    print("PASS: test_planificador_tiene_menu_colapsable")


def test_base_tiene_boton_fotografia():
    client = _cliente()
    resp = client.get("/")
    body = resp.data.decode("utf-8", "replace")
    assert 'id="btn-fotografia"' in body
    assert "Hacer fotograf" in body
    print("PASS: test_base_tiene_boton_fotografia")


def test_base_nav_conserva_el_plan_activo():
    client = _cliente()
    resp = client.get("/")
    body = resp.data.decode("utf-8", "replace")
    assert 'href="/horario"' in body
    print("PASS: test_base_nav_conserva_el_plan_activo")


def test_elegir_tecnico_mencion_enlaces_directos():
    client = _cliente()
    resp = client.get("/")
    body = resp.data.decode("utf-8", "replace")
    assert 'href="/malla/tecnico/activar/' in body
    assert 'href="/malla/mencion/activar/' in body
    print("PASS: test_elegir_tecnico_mencion_enlaces_directos")


def test_activar_tecnico_por_enlace_actualiza_malla():
    client = _cliente()
    resp = client.get("/malla/tecnico/activar/T01")
    assert resp.status_code in (302, 303)
    resp = client.get("/")
    body = resp.data.decode("utf-8", "replace")
    assert "Tecnico activo" in body
    assert "GESTION DE PROYECTOS DE INVERSION" in body
    print("PASS: test_activar_tecnico_por_enlace_actualiza_malla")


def test_activar_mencion_por_enlace_actualiza_malla():
    client = _cliente()
    resp = client.get("/malla/mencion/activar/M01")
    assert resp.status_code in (302, 303)
    resp = client.get("/")
    body = resp.data.decode("utf-8", "replace")
    assert "Mencion activa" in body
    assert "DEMOGRAFIA" in body
    print("PASS: test_activar_mencion_por_enlace_actualiza_malla")


def test_calendario_misma_carga_para_aux():
    from app.inicio import calendario_eventos
    from planificador import crear_planificador, seleccionar_grupo

    plan = crear_planificador(gestion=2, anio=2026, modo="manual")
    grupos = None
    from app.inicio import get_motor
    motor = get_motor()
    from planificador import grupos_de_materia
    g = grupos_de_materia("1304001", motor)[0]
    g = dict(g)
    g["auxiliares"] = [{
        "nombre": "AUX 1",
        "horarios": [{"dia": "LU", "hora_inicio": "14:00", "hora_fin": "15:30", "aula": "E1"}],
    }]
    seleccionar_grupo(plan, g, motor)
    eventos = calendario_eventos(plan)
    clase = [e for e in eventos if e["extendedProps"]["tipo"] == "CLASE"][0]
    aux = [e for e in eventos if e["extendedProps"]["tipo"] == "AUX"][0]
    assert clase["backgroundColor"] == aux["backgroundColor"]
    print("PASS: test_calendario_misma_carga_para_aux")


def test_grupos_misma_materia_colores_distintos():
    from app.inicio import calendario_eventos
    from planificador import crear_planificador, seleccionar_grupo

    plan = crear_planificador(gestion=2, anio=2026, modo="manual")
    g1 = {
        "codigo_sis": "COLOR01", "nivel": "A", "grupo": "01",
        "docente": "DOC A", "nombre": "COLOR TEST", "auxiliares": [],
        "horarios": [{"dia": "LU", "hora_inicio": "08:00", "hora_fin": "09:30", "aula": "E1"}],
    }
    g2 = {
        "codigo_sis": "COLOR01", "nivel": "A", "grupo": "02",
        "docente": "DOC A", "nombre": "COLOR TEST", "auxiliares": [],
        "horarios": [{"dia": "MA", "hora_inicio": "08:00", "hora_fin": "09:30", "aula": "E1"}],
    }
    seleccionar_grupo(plan, g1, None)
    seleccionar_grupo(plan, g2, None)
    eventos = calendario_eventos(plan)
    clases = [e for e in eventos if e["extendedProps"]["tipo"] == "CLASE"]
    assert len(clases) == 2
    assert clases[0]["backgroundColor"] != clases[1]["backgroundColor"], \
        "Grupos distintos de la misma materia deben usar colores distintos"
    print("PASS: test_grupos_misma_materia_colores_distintos")


def test_materia_nombre_acordeon():
    client = _cliente()
    resp = client.get("/horario/parcial/nivel/A")
    body = resp.data.decode("utf-8", "replace")
    assert "window.__toggleGrupos" in body
    assert 'onclick="window.__toggleGrupos' in body
    print("PASS: test_materia_nombre_acordeon")


def test_planificador_solo_un_volver():
    client = _cliente()
    _modo_manual(client)
    resp = client.get("/horario")
    body = resp.data.decode("utf-8", "replace")
    assert body.count("&larr; Volver") == 1
    print("PASS: test_planificador_solo_un_volver")


def test_cambiar_modo_generico_en_modo_academico():
    from planificador import crear_planificador, MODO_ACADEMICO

    client = _cliente()
    client.get("/horario")
    with client.session_transaction() as sess:
        sess["plan"] = crear_planificador(gestion=2, anio=2026, modo=MODO_ACADEMICO)
        sess["kardex"] = {"intentos": {}}
    resp = client.get("/horario")
    body = resp.data.decode("utf-8", "replace")
    assert ">Cambiar modo</a>" in body or "Cambiar modo" in body
    assert "Cambiar a modo con Kardex" not in body

    client.post("/horario/parcial/seleccionar-modo", data={"modo": "manual"})
    resp = client.get("/horario")
    body = resp.data.decode("utf-8", "replace")
    assert "Cambiar a modo con Kardex" in body
    print("PASS: test_cambiar_modo_generico_en_modo_academico")


def test_manual_datalist_opciones_servidor():
    client = _cliente()
    client.get("/horario")
    resp = client.get("/horario/kardex/manual")
    body = resp.data.decode("utf-8", "replace")
    assert "1304001 - ECONOMIA GENERAL" in body
    assert "mat-codigo" in body
    assert "mat-busqueda" in body
    print("PASS: test_manual_datalist_opciones_servidor")


def test_quitar_materia_manual():
    client = _cliente()
    client.get("/horario")
    client.post(
        "/horario/kardex/manual/agregar",
        data={"codigo_sis": "1304001", "nota": "71"},
    )
    resp = client.post(
        "/horario/kardex/manual/quitar",
        data={"codigo_sis": "1304001"},
    )
    assert resp.status_code == 200
    with client.session_transaction() as sess:
        kardex = sess.get("kardex")
        assert "1304001" not in kardex["intentos"]
    print("PASS: test_quitar_materia_manual")


def test_economia_politica_g01_con_viernes():
    from app.inicio import get_motor
    motor = get_motor()
    grupos = motor["oferta"]["indice"]["1304022"]
    g01 = [g for g in grupos if str(g.get("grupo")) == "01"][0]
    dias = [h["dia"] for h in g01["horarios"]]
    assert "VI" in dias, "ECONOMIA POLITICA I G01 debe incluir el viernes: %s" % dias
    print("PASS: test_economia_politica_g01_con_viernes")


def test_malla_card_texto_mas_grande():
    client = _cliente()
    resp = client.get("/")
    body = resp.data.decode("utf-8", "replace")
    assert "text-[13px]" in body
    print("PASS: test_malla_card_texto_mas_grande")


def test_malla_scroll_al_abrir_materia():
    client = _cliente()
    resp = client.get("/")
    body = resp.data.decode("utf-8", "replace")
    assert "scrollIntoView" in body
    print("PASS: test_malla_scroll_al_abrir_materia")


def test_kardex_resumen_opcion_editar():
    from flask import render_template
    from app import create_app as _app
    with _app().test_request_context():
        body = render_template(
            "horario/08_resumen_kardex.html",
            plan={},
            resumen={
                "aprobadas": 0, "reprobadas": 0, "en_curso": 0,
                "materias_unicas": 0, "provisionales": 0,
                "codigos_desconocidos": 0, "inconsistencias": 0,
                "detalle": [],
            },
        )
    assert "Agregar/editar materias" in body
    assert "/horario/kardex/manual" in body
    print("PASS: test_kardex_resumen_opcion_editar")


def test_agregar_manual_forma_apunta_a_lista_manual():
    """El formulario re-renderiza solo la lista (#lista-manual), nunca el
    formulario completo: el autocompletado sigue funcionando despues de agregar."""
    client = _cliente()
    client.get("/horario")
    resp = client.get("/horario/kardex/manual")
    body = resp.data.decode("utf-8", "replace")
    assert 'hx-target="#lista-manual"' in body
    assert 'id="lista-manual"' in body
    # Al agregar, la respuesta es el parcial con la lista, no el formulario.
    resp2 = client.post(
        "/horario/kardex/manual/agregar",
        data={"codigo_sis": "1304001", "nota": "71"},
    )
    assert resp2.status_code == 200
    body2 = resp2.data.decode("utf-8", "replace")
    assert "Materia agregada correctamente." in body2
    assert "mat-busqueda" not in body2  # el formulario no se re-renderiza
    print("PASS: test_agregar_manual_forma_apunta_a_lista_manual")


def test_grupos_sin_botones_superiores():
    """El acordeon es el unico control: no hay Ver grupos ni Ocultar grupos
    ni Volver a materias."""
    client = _cliente()
    _modo_manual(client)
    resp = client.get("/horario/parcial/nivel/A")
    body = resp.data.decode("utf-8", "replace")
    assert "Ver grupos" not in body
    assert 'hx-target="#grupos-' not in body
    resp2 = client.get("/horario/parcial/grupos/1304001")
    body2 = resp2.data.decode("utf-8", "replace")
    assert "Ocultar grupos" not in body2
    assert "Volver a materias" not in body2
    assert "zona-grupos" in body2
    print("PASS: test_grupos_sin_botones_superiores")


def test_malla_se_adapta_al_drawer():
    """Al abrir/cerrar el drawer de una materia, la malla se achica/restaura
    via body class + margin-right."""
    client = _cliente()
    resp = client.get("/")
    body = resp.data.decode("utf-8", "replace")
    assert "pde-drawer-abierto" in body
    assert "margin-right: 23rem" in body
    print("PASS: test_malla_se_adapta_al_drawer")


def test_base_sin_planificar_flotante_ni_card():
    """La pantalla principal ya no ofrece el boton Planificar redundante."""
    client = _cliente()
    resp = client.get("/")
    body = resp.data.decode("utf-8", "replace")
    assert ">Planificar</" not in body
    assert "Planificar</a>" not in body
    print("PASS: test_base_sin_planificar_flotante_ni_card")


def test_tecnico_mencion_en_una_sola_fila():
    """Los 6 bloques (3 tecnicos + 3 menciones) van en una sola fila y cada
    objetivo tiene un color distinto (fuera de la paleta de la malla)."""
    client = _cliente()
    resp = client.get("/")
    body = resp.data.decode("utf-8", "replace")
    assert "lg:grid-cols-6" in body
    assert "hover:border-teal-300" in body
    assert "hover:border-fuchsia-300" in body
    assert "hover:border-lime-300" in body
    assert "hover:border-cyan-300" in body
    assert "hover:border-orange-300" in body
    assert "hover:border-indigo-300" in body
    assert "border-violet-400" not in body
    print("PASS: test_tecnico_mencion_en_una_sola_fila")


def test_banda_talleres_ingles_una_fila():
    """Talleres + Ingles van en una sola fila (lg:grid-cols-7) y son tarjetas
    seleccionables (malla-card)."""
    client = _cliente()
    resp = client.get("/")
    body = resp.data.decode("utf-8", "replace")
    assert "lg:grid-cols-7" in body
    assert 'id="malla-banda"' in body
    assert "malla-card" in body
    print("PASS: test_banda_talleres_ingles_una_fila")


def test_botones_flotantes_intercambiados():
    """La camara queda arriba y Ayuda abajo."""
    import re
    client = _cliente()
    resp = client.get("/")
    body = resp.data.decode("utf-8", "replace")
    foto = re.search(r'<button[^>]*id="btn-fotografia"[^>]*>', body).group(0)
    assert "bottom-20" in foto
    report = re.search(r'<a[^>]*id="btn-reportar-error"[^>]*>', body).group(0)
    assert "bottom-4" in report
    assert "wa.link/fq4ozm" in report
    print("PASS: test_botones_flotantes_intercambiados")


def test_calendario_celda_hora_etiqueta():
    """La primera celda del encabezado (columna de horas) dice 'Hora'."""
    client = _cliente()
    _modo_manual(client)
    resp = client.get("/horario/parcial/calendario")
    body = resp.data.decode("utf-8", "replace")
    assert "textContent = 'Hora'" in body
    print("PASS: test_calendario_celda_hora_etiqueta")


if __name__ == "__main__":
    tests = [
        test_seleccionar_devuelve_json,
        test_eliminar_devuelve_json,
        test_eliminar_quita_del_plan,
        test_calendario_parcial_sin_vista_completa_y_grande,
        test_planificador_calendario_arriba_de_seleccion,
        test_grupos_tienen_checkboxes_sin_boton,
        test_api_materias,
        test_agregar_manual_muestra_pagina,
        test_agregar_manual_guarda_kardex,
        test_agregar_manual_nota_invalida,
        test_base_nav_nuevos_textos,
        test_modo_seleccion_nuevos_botones,
        test_index_elegir_tecnico,
        test_malla_banner_materias_integradas,
        test_calendario_eventos_endpoint_json,
        test_calendario_columnas_blancas_y_rojo_intenso,
        test_planificador_tiene_menu_colapsable,
        test_base_tiene_boton_fotografia,
        test_base_nav_apunta_a_cambiar_modo,
        test_elegir_tecnico_mencion_enlaces_directos,
        test_activar_tecnico_por_enlace_actualiza_malla,
        test_activar_mencion_por_enlace_actualiza_malla,
        test_calendario_misma_carga_para_aux,
        test_grupos_misma_materia_colores_distintos,
        test_materia_nombre_acordeon,
        test_planificador_solo_un_volver,
        test_cambiar_modo_generico_en_modo_academico,
        test_manual_datalist_opciones_servidor,
        test_quitar_materia_manual,
        test_economia_politica_g01_con_viernes,
        test_malla_card_texto_mas_grande,
        test_malla_scroll_al_abrir_materia,
        test_kardex_resumen_opcion_editar,
        test_agregar_manual_forma_apunta_a_lista_manual,
        test_grupos_sin_botones_superiores,
        test_malla_se_adapta_al_drawer,
        test_base_sin_planificar_flotante_ni_card,
        test_tecnico_mencion_en_una_sola_fila,
        test_banda_talleres_ingles_una_fila,
        test_botones_flotantes_intercambiados,
        test_calendario_celda_hora_etiqueta,
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
    print("RESULTADOS LOTE CORRECCIONES: %d passed, %d failed, %d total" % (
        passed, failed, len(tests)))
    if failed == 0:
        print("TODOS LOS TESTS PASARON CORRECTAMENTE")
    else:
        print("ALGUNOS TESTS FALLARON")
    print("=" * 60)
