"""
Motor básico de prerrequisitos.
Trabaja exclusivamente con códigos SIS.
"""

import os
import pandas as pd


RUTA_EXCEL = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "datos", "Exel Plan de estudios.xlsx"
)

COLUMNAS_PREREQ = [
    "Prerrequisito 1", "Prerrequisito 2", "Prerrequisito 3",
    "Prerrequisito 4", "Prerrequisito 5", "Prerrequisito 6"
]


def cargar_materias(ruta_excel=RUTA_EXCEL):
    df = pd.read_excel(ruta_excel, sheet_name="Materias")
    df["Codigo SIS"] = df["Codigo SIS"].astype(str)
    for c in COLUMNAS_PREREQ:
        df[c] = df[c].where(df[c].notna(), other=None)
    return df


def construir_mapa_prerequisitos(df):
    mapa = {}
    for _, row in df.iterrows():
        codigo = row["Codigo SIS"]
        prereqs = []
        for c in COLUMNAS_PREREQ:
            val = row[c]
            if pd.notna(val):
                prereqs.append(str(int(val)))
        mapa[codigo] = {
            "materia": row["Materia"],
            "nivel": row["Nivel"],
            "tipo": row["Tipo"],
            "prerrequisitos": prereqs
        }
    return mapa


def consultar_materia(codigo, mapa):
    codigo = str(codigo)
    if codigo not in mapa:
        print(f"Error: No existe materia con codigo SIS '{codigo}'.")
        return None
    info = mapa[codigo]
    print(f"Codigo SIS  : {codigo}")
    print(f"Materia     : {info['materia']}")
    print(f"Nivel       : {info['nivel']}")
    print(f"Tipo        : {info['tipo']}")
    prereqs = info["prerrequisitos"]
    if prereqs:
        print(f"Prerequisitos ({len(prereqs)}): {', '.join(prereqs)}")
        for p in prereqs:
            if p in mapa:
                print(f"  -> {p}: {mapa[p]['materia']}")
            else:
                print(f"  -> {p}: [NO ENCONTRADO]")
    else:
        print("Prerequisitos: Ninguno (materia sin prerrequisitos)")
    return info


def tiene_prerrequisitos(codigo, mapa):
    codigo = str(codigo)
    if codigo not in mapa:
        return None
    return len(mapa[codigo]["prerrequisitos"]) > 0


def materias_sin_prerrequisitos(mapa):
    return [c for c, v in mapa.items() if len(v["prerrequisitos"]) == 0]


def materias_con_prerrequisitos(mapa):
    return [(c, len(v["prerrequisitos"])) for c, v in mapa.items()
            if len(v["prerrequisitos"]) > 0]


def ejecutar_demo():
    print("=" * 60)
    print("MOTOR DE PRERREQUISITOS - DEMO")
    print("=" * 60)

    df = cargar_materias()
    mapa = construir_mapa_prerequisitos(df)

    sin_prereq = materias_sin_prerrequisitos(mapa)
    con_prereq = materias_con_prerrequisitos(mapa)

    print(f"\nTotal materias: {len(mapa)}")
    print(f"Sin prerrequisitos: {len(sin_prereq)}")
    print(f"Con prerrequisitos: {len(con_prereq)}")

    print("\n--- Materias sin prerrequisitos ---")
    for c in sin_prereq:
        print(f"  {c}: {mapa[c]['materia']}")

    print("\n--- Consulta de ejemplo: 1304007 (Microeconomia I) ---")
    consultar_materia("1304007", mapa)

    print("\n--- Consulta de ejemplo: 1304210 (Investigacion Operativa, 6 prereqs) ---")
    consultar_materia("1304210", mapa)

    print("\n--- Consulta de ejemplo: 1304001 (Economia General, sin prereqs) ---")
    consultar_materia("1304001", mapa)

    print("\n" + "=" * 60)
    print("DEMO COMPLETADA")
    print("=" * 60)


if __name__ == "__main__":
    ejecutar_demo()
