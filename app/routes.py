import json
import os
import tempfile
from flask import (Blueprint, render_template, request, session, jsonify,
                   redirect, url_for, make_response)

from app.inicio import (
    get_motor, get_motor_para_kardex, get_oferta_niveles,
    get_materias_por_nivel, get_grupos_por_materia, agrupar_grupos,
    verificar_prerequisitos, format_dias, format_horario, format_aulas,
    calendario_eventos, construir_resumen_kardex,
)

from planificador import (
    crear_planificador, seleccionar_grupo, eliminar_grupo,
    detectar_conflicto, limites, MODO_MANUAL, MODO_ACADEMICO,
    recomendar_grupo, horas_semanales,
)

from importador_kardex import (
    crear_kardex, configurar_gestion, reconstruir_inconsistencias,
)
from procesador_kardex import procesar_pdf
from motor_academico import determinar_estado_materia_completo
from malla import (
    construir_malla, construir_malla_oficial, construir_objetivos,
    aplicar_estados, integrar_objetivos, sustituciones_activas,
)

bp = Blueprint("main", __name__)


def _get_plan():
    return session.get("plan")


def _save_plan(plan):
    session["plan"] = plan


def _get_motor():
    """Motor adecuado segun el modo activo.
    Academico con kardex subido -> motor con ese kardex.
    Manual (o sin kardex)      -> motor base cacheado."""
    plan = _get_plan()
    if plan and plan.get("modo") == MODO_ACADEMICO:
        kardex = session.get("kardex")
        if kardex:
            return get_motor_para_kardex(kardex)
    return get_motor()


_OBJ_COLORES = [
    {"borde": "border-teal-400", "hover": "hover:border-teal-300", "ring": "ring-teal-200",
     "punto": "bg-teal-500", "badge": "bg-teal-100 text-teal-700",
     "activo": "border-teal-400 ring-2 ring-teal-200",
     "enlace": "text-teal-700 hover:bg-teal-50 border-teal-200",
      "card": "border-teal-300 bg-teal-50 text-teal-900", "label": "text-teal-500", "hex": "#a8ddd7"},
    {"borde": "border-fuchsia-400", "hover": "hover:border-fuchsia-300", "ring": "ring-fuchsia-200",
     "punto": "bg-fuchsia-500", "badge": "bg-fuchsia-100 text-fuchsia-700",
     "activo": "border-fuchsia-400 ring-2 ring-fuchsia-200",
     "enlace": "text-fuchsia-700 hover:bg-fuchsia-50 border-fuchsia-200",
      "card": "border-fuchsia-300 bg-fuchsia-50 text-fuchsia-900", "label": "text-fuchsia-500", "hex": "#e4c1e4"},
    {"borde": "border-lime-400", "hover": "hover:border-lime-300", "ring": "ring-lime-200",
     "punto": "bg-lime-500", "badge": "bg-lime-100 text-lime-700",
     "activo": "border-lime-400 ring-2 ring-lime-200",
     "enlace": "text-lime-700 hover:bg-lime-50 border-lime-200",
      "card": "border-lime-300 bg-lime-50 text-lime-900", "label": "text-lime-500", "hex": "#d7e6b2"},
    {"borde": "border-cyan-400", "hover": "hover:border-cyan-300", "ring": "ring-cyan-200",
     "punto": "bg-cyan-500", "badge": "bg-cyan-100 text-cyan-700",
     "activo": "border-cyan-400 ring-2 ring-cyan-200",
     "enlace": "text-cyan-700 hover:bg-cyan-50 border-cyan-200",
      "card": "border-cyan-300 bg-cyan-50 text-cyan-900", "label": "text-cyan-500", "hex": "#b5dfe6"},
    {"borde": "border-orange-400", "hover": "hover:border-orange-300", "ring": "ring-orange-200",
     "punto": "bg-orange-500", "badge": "bg-orange-100 text-orange-700",
     "activo": "border-orange-400 ring-2 ring-orange-200",
     "enlace": "text-orange-700 hover:bg-orange-50 border-orange-200",
      "card": "border-orange-300 bg-orange-50 text-orange-900", "label": "text-orange-500", "hex": "#f2c7a6"},
    {"borde": "border-indigo-400", "hover": "hover:border-indigo-300", "ring": "ring-indigo-200",
     "punto": "bg-indigo-500", "badge": "bg-indigo-100 text-indigo-700",
     "activo": "border-indigo-400 ring-2 ring-indigo-200",
     "enlace": "text-indigo-700 hover:bg-indigo-50 border-indigo-200",
      "card": "border-indigo-300 bg-indigo-50 text-indigo-900", "label": "text-indigo-500", "hex": "#c6c9e8"},
]


def _asignar_colores_objetivos(objetivos):
    for i, o in enumerate(objetivos.get("tecnicos", [])):
        o["color"] = _OBJ_COLORES[i % len(_OBJ_COLORES)]
    for i, o in enumerate(objetivos.get("menciones", [])):
        o["color"] = _OBJ_COLORES[(3 + i) % len(_OBJ_COLORES)]
    return objetivos


def _ids_sesion(clave_plural, clave_antigua):
    valores = session.get(clave_plural)
    if valores is None:
        antiguo = session.get(clave_antigua)
        valores = [antiguo] if antiguo else []
    resultado = []
    for valor in valores:
        valor = str(valor)
        if valor and valor not in resultado:
            resultado.append(valor)
    return resultado


def _guardar_ids_sesion(clave_plural, clave_antigua, valores):
    valores = list(dict.fromkeys(str(x) for x in valores if x))
    if valores:
        session[clave_plural] = valores
        session[clave_antigua] = valores[0]
    else:
        session.pop(clave_plural, None)
        session.pop(clave_antigua, None)
    return valores


@bp.route("/")
def index(desde_malla=False):
    plan = _get_plan()
    kardex = session.get("kardex")
    con_estados = bool(plan and plan.get("modo") == MODO_ACADEMICO and kardex)
    motor = get_motor_para_kardex(kardex) if con_estados else get_motor()
    menciones_activas = _ids_sesion("menciones", "mencion")
    tecnicos_activos = _ids_sesion("tecnicos", "tecnico")
    malla = construir_malla_oficial(motor, con_estados=con_estados)
    objetivos = _asignar_colores_objetivos(construir_objetivos(motor, malla))
    integrar_objetivos(
        malla, objetivos, menciones_activas, tecnicos_activos,
        sustituciones_activas(motor, menciones_activas),
    )

    mencion_activa = menciones_activas[0] if menciones_activas else ""
    tecnico_activo = tecnicos_activos[0] if tecnicos_activos else ""
    mencion_obj = next(
        (o for o in objetivos["menciones"] if o["id"] == mencion_activa), None)
    tecnico_obj = next(
        (o for o in objetivos["tecnicos"] if o["id"] == tecnico_activo), None)
    return render_template(
        "index.html",
        malla=malla,
        objetivos=objetivos,
        con_estados=con_estados,
        mencion_activa=mencion_activa,
        tecnico_activo=tecnico_activo,
        menciones_activas=menciones_activas,
        tecnicos_activos=tecnicos_activos,
        mencion_obj=mencion_obj,
        tecnico_obj=tecnico_obj,
        desde_malla=desde_malla,
    )


@bp.route("/guia")
def guia():
    """Pagina informativa independiente de la logica academica."""
    return render_template("guia.html")


@bp.route("/calendario-academico")
def calendario_academico():
    """Visor del calendario academico institucional, si el PDF esta disponible."""
    pdf_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                           "static", "calendarios")
    pdf_filename = "calendario_academico.pdf"
    pdf_path = os.path.join(pdf_dir, pdf_filename)
    if not os.path.isfile(pdf_path):
        disponibles = sorted(
            nombre for nombre in os.listdir(pdf_dir)
            if nombre.lower().endswith(".pdf")
        ) if os.path.isdir(pdf_dir) else []
        pdf_filename = disponibles[0] if disponibles else pdf_filename
        pdf_path = os.path.join(pdf_dir, pdf_filename)
    return render_template(
        "calendario_academico.html",
        pdf_disponible=os.path.isfile(pdf_path),
        pdf_filename=pdf_filename,
    )


@bp.route("/malla")
def malla():
    """Vista de la malla curricular (alias de /)."""
    return index(desde_malla=True)


@bp.route("/malla/mencion/activar", methods=["POST"])
def malla_mencion_activar():
    """Activa una mencion en la sesion del usuario (no modifica Excel)."""
    id_mencion = request.form.get("id", "")
    if not id_mencion:
        return jsonify({"error": "Falta id de mencion"}), 400
    motor = get_motor()
    ids_validos = {str(x) for x in motor.get("datos_objetivos", {})
                   .get("menciones", []).get("ID Mencion", [])}
    if ids_validos and id_mencion not in ids_validos:
        return jsonify({"error": "Mencion no encontrada"}), 400
    activos = _ids_sesion("menciones", "mencion")
    if id_mencion not in activos:
        activos.append(id_mencion)
    activos = _guardar_ids_sesion("menciones", "mencion", activos)
    return jsonify({"ok": True, "mencion": id_mencion,
                    "menciones": activos})


@bp.route("/malla/mencion/desactivar", methods=["POST"])
def malla_mencion_desactivar():
    id_mencion = request.form.get("id", "")
    activos = _ids_sesion("menciones", "mencion")
    if id_mencion:
        activos = [x for x in activos if x != id_mencion]
    else:
        activos = []
    activos = _guardar_ids_sesion("menciones", "mencion", activos)
    return jsonify({"ok": True, "menciones": activos})


@bp.route("/malla/tecnico/activar", methods=["POST"])
def malla_tecnico_activar():
    """Activa un tecnico en la sesion del usuario (no modifica Excel)."""
    id_tecnico = request.form.get("id", "")
    if not id_tecnico:
        return jsonify({"error": "Falta id de tecnico"}), 400
    motor = get_motor()
    ids_validos = {str(x) for x in motor.get("datos_objetivos", {})
                   .get("tecnicos", []).get("ID Tecnico", [])}
    if ids_validos and id_tecnico not in ids_validos:
        return jsonify({"error": "Tecnico no encontrado"}), 400
    activos = _ids_sesion("tecnicos", "tecnico")
    if id_tecnico not in activos:
        activos.append(id_tecnico)
    activos = _guardar_ids_sesion("tecnicos", "tecnico", activos)
    return jsonify({"ok": True, "tecnico": id_tecnico,
                    "tecnicos": activos})


@bp.route("/malla/tecnico/desactivar", methods=["POST"])
def malla_tecnico_desactivar():
    id_tecnico = request.form.get("id", "")
    activos = _ids_sesion("tecnicos", "tecnico")
    if id_tecnico:
        activos = [x for x in activos if x != id_tecnico]
    else:
        activos = []
    activos = _guardar_ids_sesion("tecnicos", "tecnico", activos)
    return jsonify({"ok": True, "tecnicos": activos})


@bp.route("/malla/tecnico/activar/<id_tecnico>")
def malla_tecnico_activar_enlace(id_tecnico):
    activos = _ids_sesion("tecnicos", "tecnico")
    if id_tecnico not in activos:
        activos.append(id_tecnico)
    _guardar_ids_sesion("tecnicos", "tecnico", activos)
    return redirect(url_for("main.index"))


@bp.route("/malla/tecnico/desactivar/enlace")
def malla_tecnico_desactivar_enlace():
    id_tecnico = request.args.get("id", "")
    activos = _ids_sesion("tecnicos", "tecnico")
    if id_tecnico:
        activos = [x for x in activos if x != id_tecnico]
    else:
        activos = []
    _guardar_ids_sesion("tecnicos", "tecnico", activos)
    return redirect(url_for("main.index"))


@bp.route("/malla/mencion/activar/<id_mencion>")
def malla_mencion_activar_enlace(id_mencion):
    activos = _ids_sesion("menciones", "mencion")
    if id_mencion not in activos:
        activos.append(id_mencion)
    _guardar_ids_sesion("menciones", "mencion", activos)
    return redirect(url_for("main.index"))


@bp.route("/malla/mencion/desactivar/enlace")
def malla_mencion_desactivar_enlace():
    id_mencion = request.args.get("id", "")
    activos = _ids_sesion("menciones", "mencion")
    if id_mencion:
        activos = [x for x in activos if x != id_mencion]
    else:
        activos = []
    _guardar_ids_sesion("menciones", "mencion", activos)
    return redirect(url_for("main.index"))


@bp.route("/malla/materia/<codigo>")
def malla_materia(codigo):
    plan = _get_plan()
    kardex = session.get("kardex")
    con_estados = bool(plan and plan.get("modo") == MODO_ACADEMICO and kardex)
    motor = get_motor_para_kardex(kardex) if con_estados else get_motor()
    malla = construir_malla(motor)
    if con_estados:
        aplicar_estados(malla, motor)

    mat = malla["materias"].get(str(codigo))
    if mat is None:
        return jsonify({"error": "Materia no encontrada"}), 404

    objetivos = construir_objetivos(motor, malla)
    pertenencias = []
    for tipo, ids, clave in (
        ("mencion", _ids_sesion("menciones", "mencion"), "menciones"),
        ("tecnico", _ids_sesion("tecnicos", "tecnico"), "tecnicos"),
    ):
        for objetivo in objetivos.get(clave, []):
            if objetivo["id"] not in ids:
                continue
            if any(str(ref["codigo"]) == str(codigo)
                   for ref in objetivo.get("materias", [])):
                pertenencias.append({
                    "tipo": tipo,
                    "id": objetivo["id"],
                    "nombre": objetivo["nombre"],
                })

    prereqs = []
    for p in mat["prerequisitos"]:
        pm = malla["materias"].get(p)
        if pm:
            prereqs.append({
                "codigo": p,
                "nombre": pm["nombre"],
                "nivel": pm["nivel"],
                "estado": pm["estado"],
                "estado_visual": pm["estado_visual"],
            })

    dependientes = []
    for d in mat["dependientes"]:
        dm = malla["materias"].get(d)
        if dm:
            dependientes.append({
                "codigo": d,
                "nombre": dm["nombre"],
                "nivel": dm["nivel"],
                "estado": dm["estado"],
                "estado_visual": dm["estado_visual"],
            })

    return jsonify({
        "codigo": mat["codigo"],
        "nombre": mat["nombre"],
        "nivel": mat["nivel"],
        "area": mat["area"],
        "sigla": mat["sigla"],
        "tipo": mat["tipo"],
        "horas": mat["horas"],
        "creditos": mat["creditos"],
        "ofertada": mat["ofertada"],
        "num_grupos": mat["num_grupos"],
        "pertenencias": pertenencias,
        "estado": mat["estado"],
        "estado_visual": mat["estado_visual"],
        "prerequisitos": prereqs,
        "dependientes": dependientes,
    })


@bp.route("/progreso")
def progreso():
    kardex = session.get("kardex")
    menciones_activas = _ids_sesion("menciones", "mencion")
    tecnicos_activos = _ids_sesion("tecnicos", "tecnico")
    if not kardex:
        return render_template(
            "progreso.html",
            progreso={"tiene_kardex": False},
        )

    motor = get_motor_para_kardex(kardex) if kardex else get_motor()
    malla = construir_malla(motor)
    aplicar_estados(malla, motor)
    objetivos = construir_objetivos(motor, malla)

    materias = list(malla.get("materias", {}).values())
    obligatorias = [
        materia for materia in materias
        if materia.get("tipo") in ("Obligatoria", "Obligatoria No Curricular")
    ]
    electivas = [materia for materia in materias
                 if materia.get("tipo") == "Materia Electiva"]
    obligatorias_aprobadas = sum(
        1 for materia in obligatorias if materia.get("estado") == "APROBADA"
    )

    seleccionadas = set(menciones_activas) | set(tecnicos_activos)
    electivas_trayectoria = set()
    for tipo, clave in (("mencion", "menciones"), ("tecnico", "tecnicos")):
        for objetivo in objetivos.get(clave, []):
            if str(objetivo["id"]) in seleccionadas:
                electivas_trayectoria.update(
                    str(materia["codigo"])
                    for materia in objetivo.get("materias", [])
                )
    if electivas_trayectoria:
        electivas_evaluadas = [
            materia for materia in electivas
            if str(materia.get("codigo")) in electivas_trayectoria
        ]
        electivas_total = len(electivas_evaluadas)
    else:
        electivas_evaluadas = electivas
        electivas_total = 8
    electivas_aprobadas = sum(
        1 for materia in electivas_evaluadas
        if materia.get("estado") == "APROBADA"
    )
    electivas_aprobadas_nombres = [
        materia.get("nombre") for materia in electivas_evaluadas
        if materia.get("estado") == "APROBADA"
    ]
    total_objetivo = len(obligatorias) + electivas_total
    aprobadas = obligatorias_aprobadas + min(electivas_aprobadas, electivas_total)
    restantes = max(total_objetivo - aprobadas, 0)
    porcentaje = round((aprobadas / total_objetivo) * 100) if total_objetivo else 0

    estados = {"APROBADA": 0, "EN_CURSO": 0, "DISPONIBLE": 0,
               "BLOQUEADA": 0, "REPROBADA": 0, "NO_CURSADA": 0}
    for materia in materias:
        estado_materia = materia.get("estado")
        if estado_materia in ("DISPONIBLE", "SIN_PRERREQUISITOS"):
            if materia.get("num_grupos"):
                estados["DISPONIBLE"] += 1
            else:
                estados["NO_CURSADA"] += 1
        elif estado_materia in estados:
            estados[estado_materia] += 1
        else:
            estados["NO_CURSADA"] += 1

    trayectorias = []
    for clave, etiqueta in (("menciones", "Mencion"), ("tecnicos", "Tecnico")):
        activos = {str(valor) for valor in (menciones_activas if clave == "menciones" else tecnicos_activos)}
        for objetivo in objetivos.get(clave, []):
            if str(objetivo["id"]) in activos:
                trayectorias.append({
                    "tipo": etiqueta,
                    "nombre": objetivo["nombre"],
                    "materias": len(objetivo.get("materias", [])),
                })

    def creditos_de(materia):
        try:
            return float(materia.get("creditos") or 0)
        except (TypeError, ValueError):
            return 0

    creditos = float(sum(
        creditos_de(materia) for materia in materias
        if materia.get("estado") == "APROBADA"
    ))
    creditos = int(creditos) if creditos.is_integer() else round(creditos, 2)
    if restantes == 0:
        estado = "Plan de estudios completado"
        mensaje = "No quedan materias registradas como pendientes en este calculo."
    else:
        estado = "Vas bien"
        mensaje = "Te faltan %s materias segun el avance detectado en tu Kardex." % restantes

    return render_template(
        "progreso.html",
        progreso={
            "obligatorias_aprobadas": obligatorias_aprobadas,
            "obligatorias_total": len(obligatorias),
            "electivas_aprobadas": electivas_aprobadas,
            "electivas_total": electivas_total,
            "electivas_aprobadas_nombres": electivas_aprobadas_nombres,
            "porcentaje": porcentaje,
            "creditos": creditos,
            "restantes": restantes,
            "estados": estados,
            "disponibles": estados["DISPONIBLE"],
            "trayectorias": trayectorias,
            "estado": estado,
            "mensaje": mensaje,
            "tiene_kardex": bool(kardex),
        },
    )


@bp.route("/nuevo")
def nuevo():
    session.pop("plan", None)
    session.pop("kardex", None)
    return render_template("nuevo.html")


@bp.route("/horario")
def horario():
    plan = _get_plan()
    kardex = session.get("kardex")
    materia_inicial = request.args.get("materia", "")
    modo_arg = request.args.get("modo", "")
    origen = request.args.get("origen", "")
    if request.args.get("disponibles") == "1":
        session["filtrar_disponibles"] = True
    elif not origen:
        session.pop("filtrar_disponibles", None)

    if plan and plan.get("modo") == MODO_ACADEMICO and not kardex:
        plan = None

    if modo_arg == MODO_MANUAL and (plan is None or plan.get("modo") != MODO_MANUAL):
        session.pop("kardex", None)
        plan = crear_planificador(gestion=2, anio=2026, modo=MODO_MANUAL)
        _save_plan(plan)

    if modo_arg == MODO_ACADEMICO and (plan is None or plan.get("modo") != MODO_ACADEMICO):
        plan = crear_planificador(gestion=2, anio=2026, modo=MODO_ACADEMICO)
        _save_plan(plan)

    if materia_inicial and plan is None:
        modo = MODO_ACADEMICO if kardex else MODO_MANUAL
        plan = crear_planificador(gestion=2, anio=2026, modo=modo)
        _save_plan(plan)

    niveles = []
    if plan:
        niveles = get_oferta_niveles()
    return render_template(
        "horario.html",
        plan=plan,
        kardex=kardex,
        modo_inicio=modo_arg,
        origen=origen,
        filtrar_disponibles=bool(session.get("filtrar_disponibles")),
        niveles=niveles,
        niveles_json=json.dumps(niveles),
        materia_inicial=materia_inicial,
    )


@bp.route("/horario/cambiar-modo")
def horario_cambiar_modo():
    session.pop("plan", None)
    session.pop("kardex", None)
    return redirect(url_for("main.horario"))


@bp.route("/horario/parcial/seleccionar-modo", methods=["POST"])
def horario_seleccionar_modo():
    modo = request.form.get("modo", MODO_MANUAL)
    if modo not in (MODO_ACADEMICO, MODO_MANUAL):
        modo = MODO_MANUAL
    plan = crear_planificador(gestion=2, anio=2026, modo=modo)
    _save_plan(plan)
    session.pop("kardex", None)
    niveles = get_oferta_niveles()

    if modo == MODO_ACADEMICO:
        return render_template("horario/07_subir_kardex.html", plan=plan)

    response = make_response(render_template(
        "horario/09_planificador.html",
        plan=plan,
        niveles=niveles,
        niveles_json=json.dumps(niveles),
    ))
    destino = request.form.get("destino", "malla")
    response.headers["HX-Redirect"] = (
        url_for("main.horario") if destino == "horario"
        else url_for("main.malla")
    )
    return response


@bp.route("/horario/parcial/limpiar-modo")
def horario_limpiar_modo():
    session.pop("plan", None)
    session.pop("kardex", None)
    return render_template("horario/00_seleccionar_modo.html")


@bp.route("/horario/kardex/subir", methods=["POST"])
def horario_kardex_subir():
    plan = _get_plan()
    if plan is None or plan.get("modo") != MODO_ACADEMICO:
        return jsonify({"error": "No hay plan academico activo"}), 400

    archivo = request.files.get("kardex")
    if archivo is None or not archivo.filename:
        return render_template(
            "horario/07_subir_kardex.html", plan=plan,
            error="Selecciona un archivo PDF."), 400

    MAX_PDF_BYTES = 10 * 1024 * 1024
    datos = archivo.read()
    if len(datos) == 0:
        return render_template(
            "horario/07_subir_kardex.html", plan=plan,
            error="El archivo esta vacio."), 400
    if len(datos) > MAX_PDF_BYTES:
        return render_template(
            "horario/07_subir_kardex.html", plan=plan,
            error="El archivo supera el tamano maximo de 10 MB."), 400
    if not datos[:4] == b"%PDF":
        return render_template(
            "horario/07_subir_kardex.html", plan=plan,
            error="El archivo no es un PDF valido."), 400

    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf")
    try:
        tmp.write(datos)
        tmp.close()

        kardex = crear_kardex()
        configurar_gestion(kardex, anio=2026, gestion=2)
        motor = get_motor()
        stats = procesar_pdf(
            tmp.name, kardex, motor["materias_df"], motor["mapa_prereq"]
        )

        if stats is None or len(kardex["intentos"]) == 0:
            return render_template(
                "horario/07_subir_kardex.html", plan=plan,
                error="No se pudo reconocer el kardex en el PDF. "
                      "Verifica que sea el reporte academico de SISS."), 422

        session["kardex"] = kardex
        resumen = construir_resumen_kardex(kardex)
        return render_template(
            "horario/08_resumen_kardex.html",
            plan=plan,
            resumen=resumen,
        )
    finally:
        tmp.close()
        if os.path.exists(tmp.name):
            os.unlink(tmp.name)


@bp.route("/horario/api/materias")
def horario_api_materias():
    """Lista de materias reales del sistema para el buscador manual."""
    motor = get_motor()
    q = request.args.get("q", "").strip().lower()
    mapa = motor.get("mapa_prereq", {})
    items = []
    for codigo, info in mapa.items():
        nombre = info.get("materia", "")
        if q and q not in codigo.lower() and q not in nombre.lower():
            continue
        items.append({"codigo": codigo, "nombre": nombre,
                      "nivel": info.get("nivel", "")})
    return jsonify(items)


@bp.route("/horario/kardex/manual")
def horario_kardex_manual():
    """Carga manual de materias + nota (cuando el OCR del kardex fallo)."""
    plan = _get_plan()
    if plan is None or plan.get("modo") != MODO_ACADEMICO:
        plan = crear_planificador(gestion=2, anio=2026, modo=MODO_ACADEMICO)
        _save_plan(plan)
    kardex = session.get("kardex")
    if kardex is None:
        kardex = crear_kardex()
        configurar_gestion(kardex, anio=2026, gestion=2)
        session["kardex"] = kardex

    mapa = get_motor().get("mapa_prereq", {})
    agregadas = _listar_agregadas_manual(kardex, mapa)

    return render_template(
        "horario/07b_agregar_manual.html",
        plan=plan,
        agregadas=agregadas,
        materias=_lista_materias_manual(mapa),
        exito=request.args.get("ok"),
    )


@bp.route("/horario/kardex/resumen")
def horario_kardex_resumen():
    plan = _get_plan()
    kardex = session.get("kardex")
    if kardex is None:
        return redirect(url_for("main.horario"))
    return render_template(
        "horario/08_resumen_kardex.html",
        plan=plan,
        resumen=construir_resumen_kardex(kardex),
    )


@bp.route("/horario/kardex/manual/agregar", methods=["POST"])
def horario_kardex_manual_agregar():
    plan = _get_plan()
    if plan is None or plan.get("modo") != MODO_ACADEMICO:
        plan = crear_planificador(gestion=2, anio=2026, modo=MODO_ACADEMICO)
        _save_plan(plan)
    kardex = session.get("kardex")
    if kardex is None:
        kardex = crear_kardex()
        configurar_gestion(kardex, anio=2026, gestion=2)

    from importador_kardex import (
        _calcular_estado_intento, _detectar_inconsistencias,
    )

    codigo = request.form.get("codigo_sis", "").strip()
    nota_raw = request.form.get("nota", "").strip()
    mapa = get_motor().get("mapa_prereq", {})

    if codigo not in mapa:
        agregadas = _listar_agregadas_manual(kardex, mapa)
        return render_template(
            "horario/07c_lista_manual.html",
            agregadas=agregadas,
            error="El codigo SIS no corresponde a una materia del sistema.",
        )

    try:
        nota = float(nota_raw)
    except (ValueError, TypeError):
        nota = None
    if nota is None or nota < 0 or nota > 100:
        agregadas = _listar_agregadas_manual(kardex, mapa)
        return render_template(
            "horario/07c_lista_manual.html",
            agregadas=agregadas,
            error="Ingresa una nota valida entre 0 y 100.",
        )

    nfin = nota
    rfin = "APR" if nfin >= 51 else "REP"
    intento = {
        "nro": len(kardex["intentos"].get(codigo, [])) + 1,
        "anio": 2026,
        "gestion": 2,
        "codigo_sis": codigo,
        "nivel": mapa.get(codigo, {}).get("nivel"),
        "tp": None, "md": None, "cv": None, "gr": None, "grpr": None,
        "t1": None, "t2": None, "t3": None, "p1": None, "p2": None,
        "ef": None, "2da": None, "mdTI": None, "eg": None,
        "nfin": nfin,
        "rfin": rfin,
        "correccion_estudiante": None,
        "estado_calculado": None,
        "inconsistencias": [],
        "tipo_periodo": "semestre regular",
        "origen_manual": True,
        "origen": "manual",
    }
    intento["inconsistencias"] = _detectar_inconsistencias(intento)
    intento["estado_calculado"] = _calcular_estado_intento(intento)

    if codigo not in kardex["intentos"]:
        kardex["intentos"][codigo] = []
    kardex["intentos"][codigo].append(intento)
    session["kardex"] = kardex

    return render_template(
        "horario/07c_lista_manual.html",
        agregadas=_listar_agregadas_manual(kardex, mapa),
        exito=True,
    )


def _listar_agregadas_manual(kardex, mapa):
    agregadas = []
    for codigo, intentos in kardex.get("intentos", {}).items():
        ultimo = max(intentos, key=lambda x: (x.get("anio") or 0, x.get("gestion") or 0))
        agregadas.append({
            "codigo": codigo,
            "nombre": mapa.get(codigo, {}).get("materia", codigo),
            "nota": ultimo.get("nfin"),
            "origen_manual": any(i.get("origen_manual") for i in intentos),
            "origen_pdf": any(i.get("origen", "pdf") == "pdf"
                               and not i.get("origen_manual") for i in intentos),
        })
    agregadas.sort(key=lambda x: x["codigo"])
    return agregadas


@bp.route("/horario/kardex/manual/quitar", methods=["POST"])
def horario_kardex_manual_quitar():
    """Quita las materias agregadas manualmente (no las leidas por OCR)."""
    plan = _get_plan()
    if plan is None or plan.get("modo") != MODO_ACADEMICO:
        plan = crear_planificador(gestion=2, anio=2026, modo=MODO_ACADEMICO)
        _save_plan(plan)
    kardex = session.get("kardex")
    if kardex is None:
        kardex = crear_kardex()
        configurar_gestion(kardex, anio=2026, gestion=2)
        session["kardex"] = kardex

    codigo = request.form.get("codigo_sis", "").strip()
    if codigo and codigo in kardex.get("intentos", {}):
        kardex["intentos"][codigo] = [
            i for i in kardex["intentos"][codigo]
            if not i.get("origen_manual")
        ]
        if not kardex["intentos"][codigo]:
            del kardex["intentos"][codigo]
        session["kardex"] = kardex

    mapa = get_motor().get("mapa_prereq", {})
    return render_template(
        "horario/07c_lista_manual.html",
        agregadas=_listar_agregadas_manual(kardex, mapa),
        exito_quitar=bool(codigo),
    )


@bp.route("/horario/kardex/quitar", methods=["POST"])
def horario_kardex_quitar():
    """Elimina una materia completa del kardex almacenado en sesión."""
    plan = _get_plan()
    kardex = session.get("kardex")
    codigo = request.form.get("codigo_sis", "").strip()
    if kardex is None or not codigo:
        return jsonify({"error": "No hay kardex o código de materia"}), 400
    if codigo not in kardex.get("intentos", {}):
        return jsonify({"error": "Materia no encontrada en el kardex"}), 404
    del kardex["intentos"][codigo]
    reconstruir_inconsistencias(kardex)
    session["kardex"] = kardex
    if request.headers.get("HX-Target") == "lista-manual":
        mapa = get_motor().get("mapa_prereq", {})
        return render_template(
            "horario/07c_lista_manual.html",
            agregadas=_listar_agregadas_manual(kardex, mapa),
            exito_quitar=True,
        )
    return render_template(
        "horario/08_resumen_kardex.html",
        plan=plan,
        resumen=construir_resumen_kardex(kardex),
    )


def _lista_materias_manual(mapa):
    materias = []
    for codigo, info in mapa.items():
        materias.append({
            "codigo": codigo,
            "nombre": info.get("materia", ""),
            "nivel": info.get("nivel", ""),
        })
    materias.sort(key=lambda x: x["codigo"])
    return materias


def _codigos_horario_por_trayectorias(motor):
    """Filtra electivas por las trayectorias visibles elegidas en la malla."""
    menciones = _ids_sesion("menciones", "mencion")
    tecnicos = _ids_sesion("tecnicos", "tecnico")
    if not menciones and not tecnicos:
        return None

    permitidas = {
        codigo for codigo, tipo in motor.get("tipos_materias", {}).items()
        if tipo in ("Obligatoria", "Obligatoria No Curricular")
    }
    objetivos = construir_objetivos(motor)
    for objetivo in objetivos.get("menciones", []):
        if objetivo["id"] in menciones:
            permitidas.update(str(m["codigo"]) for m in objetivo["materias"])
    for objetivo in objetivos.get("tecnicos", []):
        if objetivo["id"] in tecnicos:
            permitidas.update(str(m["codigo"]) for m in objetivo["materias"])
    permitidas.difference_update(sustituciones_activas(motor, menciones))
    return permitidas


@bp.route("/horario/parcial/nivel/<nivel>")
def horario_nivel(nivel):
    nivel = str(nivel).upper()
    materias = get_materias_por_nivel(nivel)
    plan = _get_plan()
    modo = plan.get("modo") if plan else None
    codigos_visibles = _codigos_horario_por_trayectorias(get_motor())
    if codigos_visibles is not None:
        materias = {
            codigo: materia for codigo, materia in materias.items()
            if codigo in codigos_visibles
        }

    if modo == MODO_ACADEMICO:
        motor = _get_motor()
        for cod, mat in materias.items():
            info = determinar_estado_materia_completo(cod, motor)
            mat["estado"] = info["estado"]
            mat["faltan"] = info.get("faltan", [])
            mat["provisional"] = info.get("provisional", False)
            mat["disponible_para_tomar"] = (
                info["estado"] in ("DISPONIBLE", "SIN_PRERREQUISITOS")
                and bool(get_grupos_por_materia(cod))
            )
        if session.get("filtrar_disponibles"):
            materias = {
                codigo: materia for codigo, materia in materias.items()
                if materia.get("disponible_para_tomar")
            }

    return render_template(
        "horario/02_materias.html",
        nivel=nivel,
        materias=materias,
        modo=modo,
    )


@bp.route("/horario/parcial/grupos/<codigo>")
def horario_grupos(codigo):
    grupos_raw = get_grupos_por_materia(codigo)
    secciones = agrupar_grupos(grupos_raw)
    nombre = ""
    nivel = ""
    if grupos_raw:
        nombre = grupos_raw[0].get("nombre", "?")
        nivel = grupos_raw[0].get("nivel", "")
    prereqs = verificar_prerequisitos(codigo)

    plan = _get_plan()
    modo = plan.get("modo") if plan else None
    estado = None
    disponible_para_tomar = False
    faltan_detalle = []
    motor = _get_motor()

    plan_para_rec = plan if plan is not None else crear_planificador(
        gestion=2, anio=2026, modo=MODO_MANUAL)
    for sec in secciones.values():
        sec["recomendacion"] = recomendar_grupo(plan_para_rec, sec["grupo"], motor)

    if modo == MODO_ACADEMICO:
        info = determinar_estado_materia_completo(codigo, motor)
        estado = info["estado"]
        if estado == "BLOQUEADA":
            mapa = motor.get("mapa_prereq", {})
            for f in info.get("faltan", []):
                faltan_detalle.append({
                    "codigo": f,
                    "materia": mapa.get(f, {}).get("materia", "?"),
                })
        disponible_para_tomar = (
            estado in ("DISPONIBLE", "SIN_PRERREQUISITOS")
            and bool(grupos_raw)
        )

    seleccionados = set()
    if plan:
        for g in plan.get("grupos_seleccionados", []):
            seleccionados.add((g.get("codigo_sis"), str(g.get("grupo"))))

    return render_template(
        "horario/03_grupos.html",
        codigo=codigo,
        nombre=nombre,
        nivel=nivel,
        secciones=secciones,
        prerequisitos=prereqs,
        modo=modo,
        estado=estado,
        disponible_para_tomar=disponible_para_tomar,
        faltan_detalle=faltan_detalle,
        seleccionados=seleccionados,
        format_dias=format_dias,
        format_horario=format_horario,
        format_aulas=format_aulas,
    )


@bp.route("/horario/parcial/seleccionar", methods=["POST"])
def horario_seleccionar():
    plan = _get_plan()
    if plan is None:
        return jsonify({"error": "No hay plan activo"}), 400

    codigo = request.form.get("codigo_sis", "")
    grupo_num = request.form.get("grupo", "")
    motor = _get_motor()

    grupos_raw = get_grupos_por_materia(codigo)
    grupo_seleccionado = None
    for g in grupos_raw:
        if g.get("grupo") == grupo_num:
            grupo_seleccionado = g
            break

    if grupo_seleccionado is None:
        return jsonify({"error": "Grupo no encontrado"}), 404

    if plan.get("modo") == MODO_ACADEMICO:
        info = determinar_estado_materia_completo(codigo, motor)
        if info["estado"] == "APROBADA":
            return jsonify({
                "ok": False,
                "msg": "Esta materia ya esta aprobada en tu historial. "
                       "No puede seleccionarse nuevamente.",
            })

    ok, msg = seleccionar_grupo(plan, grupo_seleccionado, motor)
    if ok and not msg:
        advs = [a["mensaje"] for a in plan.get("advertencias", [])
                if a.get("codigo") == codigo
                and a.get("grupo") == grupo_seleccionado.get("grupo")]
        if advs:
            msg = "Seleccionado. " + " ".join(advs)
    _save_plan(plan)
    return jsonify({"ok": ok, "msg": msg})


@bp.route("/horario/parcial/eliminar", methods=["POST"])
def horario_eliminar():
    plan = _get_plan()
    if plan is None:
        return jsonify({"ok": False, "msg": "No hay plan activo"}), 400

    codigo = request.form.get("codigo_sis", "")
    grupo_num = request.form.get("grupo", "")
    eliminar_grupo(plan, codigo, grupo_num)
    _save_plan(plan)
    return jsonify({"ok": True, "msg": None})


@bp.route("/horario/parcial/sidebar")
def horario_sidebar():
    plan = _get_plan()
    if plan is None:
        plan = crear_planificador(gestion=2, anio=2026, modo=MODO_MANUAL)
    from planificador import calendario_compacto
    cal = calendario_compacto(plan)
    resumen = {
        "dias": cal.get("dias", []),
        "horas_semanales": horas_semanales(plan),
        "materias": len(plan["grupos_seleccionados"]),
    }
    return render_template(
        "horario/04_seleccion.html",
        plan=plan,
        resumen=resumen,
        format_dias=format_dias,
    )


@bp.route("/horario/parcial/limpiar-materias")
def horario_limpiar_materias():
    return render_template("horario/10_placeholder_materias.html")


@bp.route("/horario/parcial/aux", methods=["POST"])
def horario_aux():
    plan = _get_plan()
    if plan is None:
        return jsonify({"error": "No hay plan activo"}), 400
    plan["modo_aux"] = not plan.get("modo_aux", True)
    _save_plan(plan)
    return "", 204


@bp.route("/horario/calendario")
def horario_calendario():
    plan = _get_plan()
    if plan is None:
        plan = crear_planificador(gestion=2, anio=2026, modo=MODO_MANUAL)
    eventos = calendario_eventos(plan)
    return render_template(
        "horario/06_calendario.html",
        plan=plan,
        eventos_json=json.dumps(eventos),
    )


@bp.route("/horario/parcial/calendario")
def horario_calendario_parcial():
    """Calendario embebido dentro del planificador (vista simultanea)."""
    plan = _get_plan()
    if plan is None:
        plan = crear_planificador(gestion=2, anio=2026, modo=MODO_MANUAL)
    eventos = calendario_eventos(plan)
    return render_template(
        "horario/12_calendario_parcial.html",
        plan=plan,
        eventos_json=json.dumps(eventos),
    )


@bp.route("/horario/parcial/calendario-eventos")
def horario_calendario_eventos():
    """Eventos en JSON para que FullCalendar los refresque sin recargar la grilla."""
    plan = _get_plan()
    if plan is None:
        plan = crear_planificador(gestion=2, anio=2026, modo=MODO_MANUAL)
    eventos = calendario_eventos(plan)
    return jsonify(eventos)
