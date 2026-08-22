"""
Construye la estructura de la malla curricular de la carrera.
Consume el motor academico existente (plan de estudios + mapa de
prerrequisitos + oferta) como fuente unica de verdad.
"""

import os
import sys
from copy import deepcopy

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from motor_academico import determinar_estado_materia_completo

# Correcciones SOLO de presentacion (los datos originales no se modifican).
AREA_DISPLAY = {
    "Histotia y Apoyo": "Historia y Apoyo",
    "e": "Teoria Economica y Aplicada",
}

AREA_CLASES = {
    "Teoria Economica y Aplicada": "border-blue-300 bg-blue-50 text-blue-900",
    "Cuantitativa": "border-violet-300 bg-violet-50 text-violet-900",
    "Materia Electiva": "border-emerald-300 bg-emerald-50 text-emerald-900",
    "Historia y Apoyo": "border-amber-300 bg-amber-50 text-amber-900",
    "Materia Obligatoria No Curricular": "border-gray-300 bg-gray-100 text-gray-700",
    "Tecnicas y Metodos de Investigacion": "border-rose-300 bg-rose-50 text-rose-900",
}

AREA_CHIP_CLASES = {
    "Teoria Economica y Aplicada": "bg-blue-100 text-blue-800",
    "Cuantitativa": "bg-violet-100 text-violet-800",
    "Materia Electiva": "bg-emerald-100 text-emerald-800",
    "Historia y Apoyo": "bg-amber-100 text-amber-800",
    "Materia Obligatoria No Curricular": "bg-gray-200 text-gray-700",
    "Tecnicas y Metodos de Investigacion": "bg-rose-100 text-rose-800",
}

ESTADO_INFO = {
    "DISPONIBLE": ("Disponible", "verde", "\U0001F7E2"),
    "SIN_PRERREQUISITOS": ("Disponible", "verde", "\U0001F7E2"),
    "APROBADA": ("Aprobada", "azul", "\U0001F535"),
    "EN_CURSO": ("En curso", "amarillo", "\U0001F7E1"),
    "REPROBADA": ("Reprobada", "rojo", "\U0001F534"),
    "ABANDONADA": ("Abandonada", "rojo", "\U0001F534"),
    "BLOQUEADA": ("Bloqueada", "negro", "\u26AB"),
}

ESTADO_CLASES = {
    "verde": "bg-emerald-100 text-emerald-800 border-emerald-300",
    "azul": "bg-blue-100 text-blue-800 border-blue-300",
    "amarillo": "bg-amber-100 text-amber-800 border-amber-300",
    "rojo": "bg-red-100 text-red-800 border-red-300",
    "negro": "bg-gray-200 text-gray-800 border-gray-400",
}

NIVEL_LABEL = {
    "A": "1\u00b0", "B": "2\u00b0", "C": "3\u00b0", "D": "4\u00b0", "E": "5\u00b0",
    "F": "6\u00b0", "G": "7\u00b0", "H": "8\u00b0", "I": "9\u00b0",
}


def _es_nulo(valor):
    if valor is None:
        return True
    try:
        import math
        return math.isnan(float(valor))
    except (TypeError, ValueError):
        return False


def _num(valor):
    if _es_nulo(valor):
        return None
    try:
        f = float(valor)
        return int(f) if f.is_integer() else f
    except (TypeError, ValueError):
        return valor


def _texto(valor):
    if _es_nulo(valor):
        return ""
    return str(valor)


def _area_display(area):
    area = _texto(area)
    return AREA_DISPLAY.get(area, area)


def _estado_visual(estado):
    etiqueta, color, emoji = ESTADO_INFO.get(
        estado, (estado, "negro", "\u26AA"))
    clases = ESTADO_CLASES.get(color, ESTADO_CLASES["negro"])
    return {"etiqueta": etiqueta, "clases": clases, "emoji": emoji}


def construir_malla(motor):
    """Construye la malla completa de la carrera a partir del motor."""
    df = motor["materias_df"]
    mapa = motor["mapa_prereq"]
    oferta_idx = (motor.get("oferta") or {}).get("indice", {})

    dependientes = {}
    for cod, info in mapa.items():
        for p in info.get("prerrequisitos", []):
            dependientes.setdefault(p, []).append(cod)

    materias = {}
    por_nivel = {}
    sin_nivel = []
    niveles = []

    for _, fila in df.iterrows():
        cod = str(fila["Codigo SIS"])
        nivel = fila["Nivel"]
        if _es_nulo(nivel):
            nivel = None
        else:
            nivel = str(nivel).upper()

        area_raw = _texto(fila["Area"])
        area = _area_display(area_raw)
        prereqs = [str(p) for p in mapa.get(cod, {}).get("prerrequisitos", [])]
        deps = list(dependientes.get(cod, []))
        grupos = oferta_idx.get(cod, [])

        mat = {
            "codigo": cod,
            "nombre": _texto(fila["Materia"]),
            "nivel": nivel,
            "area_raw": area_raw,
            "area": area,
            "area_clases": AREA_CLASES.get(area, "border-gray-300 bg-gray-100 text-gray-700"),
            "area_chip": AREA_CHIP_CLASES.get(area, "bg-gray-200 text-gray-700"),
            "horas": _num(fila["Horas"]),
            "creditos": _num(fila["Creditos"]),
            "sigla": _texto(fila["Sigla"]),
            "tipo": _texto(fila["Tipo"]),
            "prerequisitos": prereqs,
            "dependientes": deps,
            "ofertada": len(grupos) > 0,
            "num_grupos": len(grupos),
            "estado": None,
            "estado_visual": _estado_visual(None),
        }
        materias[cod] = mat

        if nivel is None:
            sin_nivel.append(mat)
        else:
            por_nivel.setdefault(nivel, []).append(mat)
            if nivel not in niveles:
                niveles.append(nivel)

    niveles.sort()
    for nivel in niveles:
        por_nivel[nivel].sort(key=lambda m: m["nombre"])

    conexiones = []
    for cod, mat in materias.items():
        for p in mat["prerequisitos"]:
            if p in materias:
                conexiones.append({"desde": p, "hasta": cod})

    return {
        "materias": materias,
        "por_nivel": por_nivel,
        "sin_nivel": sin_nivel,
        "niveles": niveles,
        "nivel_label": NIVEL_LABEL,
        "conexiones": conexiones,
        "total": len(materias),
        "areas": sorted(set(_area_display(a) for a in df["Area"])),
    }


def aplicar_estados(malla, motor):
    """Aplica estados academicos a todas las materias (kardex del motor)."""
    for cod, mat in malla["materias"].items():
        r = determinar_estado_materia_completo(cod, motor)
        mat["estado"] = r["estado"]
        mat["faltan"] = r.get("faltan", [])
        mat["estado_visual"] = _estado_visual(r["estado"])
    return malla


# Areas de la malla oficial (orden de presentacion, igual que la malla UMSS).
AREAS_OFICIALES = [
    "Teoria Economica y Aplicada",
    "Cuantitativa",
    "Historia y Apoyo",
    "Tecnicas y Metodos de Investigacion",
]

TIPO_OBLIGATORIA = "Obligatoria"
TIPO_OBLIGATORIA_NO_CURRICULAR = "Obligatoria No Curricular"
TIPO_ELECTIVA = "Materia Electiva"


def construir_malla_oficial(motor, con_estados=False):
    """Malla estilo oficial UMSS: areas como filas x semestres como columnas.

    Solo materias Obligatorias van a la grilla. Las electivas NO aparecen
    (se muestran al activar una mencion o tecnico). Los talleres
    complementarios (TI01-TI04) e Ingles (I/II/III) forman una banda propia.
    """
    base = construir_malla(motor)
    if con_estados:
        aplicar_estados(base, motor)

    materias = base["materias"]

    # Grilla (area, nivel) -> [materias obligatorias].
    celdas = {}
    for mat in materias.values():
        if mat["tipo"] == TIPO_OBLIGATORIA:
            clave = (mat["area"], mat["nivel"])
            celdas.setdefault(clave, []).append(mat)
    for clave in celdas:
        celdas[clave].sort(key=lambda m: m["nombre"])

    # Talleres (TI01-TI04) e Ingles (I/II/III): Obligatoria No Curricular.
    talleres = []
    ingles = []
    for mat in materias.values():
        if mat["tipo"] != TIPO_OBLIGATORIA_NO_CURRICULAR:
            continue
        if str(mat["codigo"]).upper().startswith("TI"):
            talleres.append(mat)
        else:
            ingles.append(mat)
    talleres.sort(key=lambda m: m["codigo"])
    ingles.sort(key=lambda m: (m["nivel"] or "", m["codigo"]))

    # Para la vista movil: nivel -> {area: [materias]}.
    por_nivel_area = {}
    for (area, nivel), lista in celdas.items():
        por_nivel_area.setdefault(nivel, {}).setdefault(area, []).extend(lista)

    return {
        "materias": materias,
        "niveles": base["niveles"],
        "nivel_label": base["nivel_label"],
        "areas": AREAS_OFICIALES,
        "celdas": celdas,
        "por_nivel_area": por_nivel_area,
        "talleres": talleres,
        "ingles": ingles,
        "conexiones": base["conexiones"],
        "total": base["total"],
        "total_obligatorias": sum(len(v) for v in celdas.values()),
    }


def integrar_objetivos(malla, objetivos, menciones_activas=None,
                       tecnicos_activos=None, sustituciones=None):
    """Une las materias de trayectorias activas sin duplicarlas visualmente."""
    menciones_activas = {str(x) for x in (menciones_activas or [])}
    tecnicos_activos = {str(x) for x in (tecnicos_activos or [])}
    seleccionados = []
    for tipo, ids, clave in (
        ("mencion", menciones_activas, "menciones"),
        ("tecnico", tecnicos_activos, "tecnicos"),
    ):
        for objetivo in objetivos.get(clave, []):
            if str(objetivo["id"]) in ids:
                seleccionados.append((tipo, objetivo))

    integradas = {}
    for tipo, objetivo in seleccionados:
        pertenencia = {
            "tipo": tipo,
            "id": str(objetivo["id"]),
            "nombre": objetivo["nombre"],
            "color": objetivo.get("color", {}),
        }
        for referencia in objetivo.get("materias", []):
            codigo = str(referencia["codigo"])
            base = malla["materias"].get(codigo)
            if base is None:
                continue
            if codigo not in integradas:
                integradas[codigo] = deepcopy(base)
                integradas[codigo]["pertenencias"] = []
            if not any(p["tipo"] == tipo and p["id"] == pertenencia["id"]
                       for p in integradas[codigo]["pertenencias"]):
                integradas[codigo]["pertenencias"].append(pertenencia)

    sustituciones = sustituciones or {}
    malla["sustituciones_activas"] = dict(sustituciones)
    for original, sustituta in sustituciones.items():
        original_mat = malla["materias"].get(original)
        sustituta_mat = malla["materias"].get(sustituta)
        if original_mat is None or sustituta_mat is None:
            continue
        sustituta_mat.setdefault("reemplaza", []).append({
            "codigo": original,
            "nombre": original_mat["nombre"],
        })
        if sustituta in integradas:
            integradas[sustituta].setdefault("reemplaza", []).append({
                "codigo": original,
                "nombre": original_mat["nombre"],
            })

    if sustituciones:
        for clave, lista in list(malla["celdas"].items()):
            malla["celdas"][clave] = [
                materia for materia in lista
                if materia["codigo"] not in sustituciones
            ]

    for materia in integradas.values():
        colores = [p.get("color", {}).get("hex", "#d1d5db")
                   for p in materia["pertenencias"]]
        paso = 100 / len(colores)
        partes = []
        for i, color in enumerate(colores):
            inicio = round(i * paso, 3)
            fin = round((i + 1) * paso, 3)
            partes.append(f"{color} {inicio}% {fin}%")
        materia["color_gradient"] = (
            "linear-gradient(90deg, " + ", ".join(partes) + ")"
        )

    por_nivel = {}
    for materia in integradas.values():
        por_nivel.setdefault(materia["nivel"], []).append(materia)
    for lista in por_nivel.values():
        lista.sort(key=lambda m: m["nombre"])

    malla["integradas"] = integradas
    malla["integradas_por_nivel"] = por_nivel
    return malla


def sustituciones_activas(motor, menciones_activas=None):
    """Devuelve original -> sustituta para las menciones seleccionadas."""
    activas = {str(x) for x in (menciones_activas or [])}
    datos = motor.get("datos_objetivos") or {}
    tabla = datos.get("sustituciones")
    if tabla is None:
        return {}
    resultado = {}
    for _, fila in tabla.iterrows():
        if str(fila["ID Mencion"]) in activas:
            resultado[str(fila["SIS Materia Original"])] = str(
                fila["SIS Materia Sustituta"])
    return resultado


def construir_objetivos(motor, malla=None):
    """Devuelve menciones y tecnicos con sus materias asociadas."""
    if malla is None:
        malla = construir_malla(motor)
    datos = motor.get("datos_objetivos") or {}
    materias = malla["materias"]

    def _materias(cods_df, id_col, id_val):
        lista = []
        if cods_df is None:
            return lista
        cods = [str(c) for c in
                cods_df.loc[cods_df[id_col] == id_val, "Codigo SIS"].tolist()]
        for c in cods:
            mat = materias.get(c)
            if mat:
                lista.append({
                    "codigo": c,
                    "nombre": mat["nombre"],
                    "nivel": mat["nivel"],
                    "area": mat["area"],
                    "tipo": mat["tipo"],
                    "estado": mat.get("estado"),
                    "estado_visual": mat.get("estado_visual"),
                })
        lista.sort(key=lambda x: (x["nivel"] or "", x["nombre"]))
        return lista

    menciones = []
    menciones_df = datos.get("menciones")
    if menciones_df is not None:
        for _, fila in menciones_df.iterrows():
            mid = str(fila["ID Mencion"])
            menciones.append({
                "id": mid,
                "nombre": str(fila["Nombre"]),
                "materias": _materias(datos.get("materia_mencion"),
                                      "ID Mencion", mid),
            })

    tecnicos = []
    tecnicos_df = datos.get("tecnicos")
    if tecnicos_df is not None:
        for _, fila in tecnicos_df.iterrows():
            tid = str(fila["ID Tecnico"])
            tecnicos.append({
                "id": tid,
                "nombre": str(fila["Nombre"]),
                "materias": _materias(datos.get("materia_tecnico"),
                                      "ID Tecnico", tid),
            })

    return {"menciones": menciones, "tecnicos": tecnicos}
