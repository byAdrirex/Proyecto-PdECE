"""
Determina la disponibilidad de cada materia para un estudiante.
Integra prerrequisitos.py y kardex.py.
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from prerrequisitos import cargar_materias, construir_mapa_prerequisitos
from kardex import (
    consultar_estado,
    ESTADO_APROBADA,
    ESTADO_REPROBADA,
    ESTADO_EN_CURSO,
    ESTADO_ABANDONADA,
    ESTADO_MESA,
)

ESTADO_DISPONIBLE = "DISPONIBLE"
ESTADO_BLOQUEADA = "BLOQUEADA"
ESTADO_SIN_PRERREQUISITOS = "SIN_PRERREQUISITOS"


def evaluar_materia(codigo, mapa_prereq, kardex):
    codigo = str(codigo)
    info = mapa_prereq.get(codigo)
    if info is None:
        return None

    estado_kardex = consultar_estado(kardex, codigo)

    if estado_kardex == ESTADO_APROBADA:
        return {"estado": ESTADO_APROBADA, "faltan": []}
    if estado_kardex == ESTADO_REPROBADA:
        return {"estado": ESTADO_REPROBADA, "faltan": []}
    if estado_kardex == ESTADO_EN_CURSO:
        return {"estado": ESTADO_EN_CURSO, "faltan": []}
    if estado_kardex in (ESTADO_ABANDONADA, ESTADO_MESA):
        return {"estado": estado_kardex, "faltan": []}

    prereqs = info["prerrequisitos"]
    if not prereqs:
        return {"estado": ESTADO_SIN_PRERREQUISITOS, "faltan": []}

    faltan = [p for p in prereqs if not (
        consultar_estado(kardex, p) == ESTADO_APROBADA
    )]

    if not faltan:
        return {"estado": ESTADO_DISPONIBLE, "faltan": []}
    return {"estado": ESTADO_BLOQUEADA, "faltan": faltan}


def evaluar_todas(mapa_prereq, kardex):
    resultado = {}
    for codigo in mapa_prereq:
        resultado[codigo] = evaluar_materia(codigo, mapa_prereq, kardex)
    return resultado


def materias_por_estado(disponibilidad, estado):
    return [c for c, v in disponibilidad.items() if v["estado"] == estado]


def consultar_disponibilidad(codigo, disponibilidad):
    codigo = str(codigo)
    if codigo not in disponibilidad:
        return None
    return disponibilidad[codigo]


def imprimir_disponibilidad(codigo, disponibilidad, mapa_prereq):
    codigo = str(codigo)
    info = disponibilidad.get(codigo)
    if info is None:
        print(f"Error: Materia '{codigo}' no encontrada.")
        return

    nombre = mapa_prereq.get(codigo, {}).get("materia", "?")
    estado = info["estado"]
    faltan = info["faltan"]

    print(f"Codigo SIS : {codigo}")
    print(f"Materia    : {nombre}")
    print(f"Estado     : {estado}")

    if faltan:
        print(f"Faltan ({len(faltan)}):")
        for p in faltan:
            nombre_p = mapa_prereq.get(p, {}).get("materia", "?")
            print(f"  -> {p}: {nombre_p}")


def resumen_general(disponibilidad):
    conteo = {}
    for v in disponibilidad.values():
        e = v["estado"]
        conteo[e] = conteo.get(e, 0) + 1
    print("Resumen de disponibilidad:")
    for estado in sorted(conteo):
        print(f"  {estado}: {conteo[estado]}")


def ejecutar_prueba():
    from kardex import crear_kardex, registrar_materia

    print("=" * 60)
    print("MODULO DE DISPONIBILIDAD - PRUEBA")
    print("=" * 60)

    df = cargar_materias()
    mapa_prereq = construir_mapa_prerequisitos(df)
    kardex = crear_kardex()

    print("\n--- Registrando kardex ficticio ---")
    datos = [
        ("1304001", 72, None),
        ("1304002", 65, None),
        ("1304003", 48, None),
        ("1304004", 70, None),
        ("1304005", 80, None),
        ("1304007", 55, None),
        ("1304008", None, None),
        ("1304013", None, "EN_CURSO"),
    ]
    for codigo, nota, estado in datos:
        registrar_materia(kardex, codigo, nota, estado)
        e = consultar_estado(kardex, codigo)
        print(f"  {codigo}: nota={nota}, estado={e}")

    print("\n--- Evaluando disponibilidad ---")
    disp = evaluar_todas(mapa_prereq, kardex)

    print("\n--- Resumen general ---")
    resumen_general(disp)

    print("\n--- Materias por estado ---")
    for estado in [ESTADO_APROBADA, ESTADO_REPROBADA, ESTADO_EN_CURSO,
                   ESTADO_DISPONIBLE, ESTADO_BLOQUEADA, ESTADO_SIN_PRERREQUISITOS]:
        lista = materias_por_estado(disp, estado)
        if lista:
            print(f"\n  {estado} ({len(lista)}):")
            for c in lista:
                nombre = mapa_prereq.get(c, {}).get("materia", "?")
                print(f"    {c}: {nombre}")

    print("\n--- Detalle de materias clave ---")
    casos = [
        ("1304001", "Materia aprobada"),
        ("1304003", "Materia reprobada"),
        ("1304008", "Materia en curso"),
        ("1304007", "Materia con todos los prereqs aprobados (Micro I: 1304001 + 1304004)"),
        ("1304016", "Materia bloqueada (Estadistica I: requiere 1304158 que no esta aprobada)"),
        ("1304005", "Materia sin prerrequisitos"),
    ]
    for codigo, desc in casos:
        print(f"\n  [{desc}]")
        imprimir_disponibilidad(codigo, disp, mapa_prereq)

    print("\n--- Verificacion: Materias disponibles con prereqs completos ---")
    disponibles = materias_por_estado(disp, ESTADO_DISPONIBLE)
    for c in disponibles[:5]:
        nombre = mapa_prereq.get(c, {}).get("materia", "?")
        prereqs = mapa_prereq.get(c, {}).get("prerrequisitos", [])
        print(f"  {c}: {nombre} (prereqs: {', '.join(prereqs)})")

    print("\n" + "=" * 60)
    print("PRUEBA COMPLETADA")
    print("=" * 60)


if __name__ == "__main__":
    ejecutar_prueba()
