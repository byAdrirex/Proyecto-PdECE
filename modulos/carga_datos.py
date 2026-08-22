"""
Módulo de carga y validación de la base de datos académica.
Carga el archivo Excel y valida la hoja "Materias".
"""

import os
import pandas as pd


RUTA_EXCEL = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "datos", "Exel Plan de estudios.xlsx"
)

COLUMNAS_ESPERADAS = [
    "Codigo SIS", "Materia", "Nivel", "Area", "Horas", "Sigla", "Creditos",
    "Prerrequisito 1", "Prerrequisito 2", "Prerrequisito 3",
    "Prerrequisito 4", "Prerrequisito 5", "Prerrequisito 6", "Tipo"
]

COLUMNAS_OBLIGATORIAS = [
    "Codigo SIS", "Materia", "Nivel", "Area", "Creditos", "Tipo"
]


def listar_hojas(ruta_excel=RUTA_EXCEL):
    xls = pd.ExcelFile(ruta_excel)
    print(f"Hoja(s) disponible(s): {xls.sheet_names}")
    return xls.sheet_names


def cargar_materias(ruta_excel=RUTA_EXCEL):
    df = pd.read_excel(ruta_excel, sheet_name="Materias")
    print(f"Materias cargadas: {len(df)}")
    return df


def validar_columnas(df):
    columnas_reales = list(df.columns)
    faltantes = [c for c in COLUMNAS_ESPERADAS if c not in columnas_reales]
    extra = [c for c in columnas_reales if c not in COLUMNAS_ESPERADAS]

    if faltantes:
        print(f"Columnas faltantes: {faltantes}")
        return False

    if extra:
        print(f"Columnas adicionales (no esperadas): {extra}")

    print("Columnas validadas correctamente.")
    return True


def diagnosticar_nulos(df):
    nulos = df.isnull().sum()
    con_nulos = nulos[nulos > 0]

    if con_nulos.empty:
        print("No se encontraron valores nulos.")
        return

    print("Valores nulos por columna:")
    for col, cant in con_nulos.items():
        etiqueta = " [OBLIGATORIA]" if col in COLUMNAS_OBLIGATORIAS else ""
        print(f"  {col}: {cant}{etiqueta}")


def mostrar_primeras_filas(df, n=5):
    print(f"\nPrimeras {n} filas:")
    print(df.head(n).to_string(index=False))


def ejecutar_carga():
    print("=" * 60)
    print("CARGA Y VALIDACIÓN DE BASE DE DATOS ACADÉMICA")
    print("=" * 60)

    if not os.path.exists(RUTA_EXCEL):
        print(f"Error: No se encontró el archivo en {RUTA_EXCEL}")
        return None

    listar_hojas()
    df = cargar_materias()

    if not validar_columnas(df):
        print("Error: La estructura de columnas no es la esperada.")
        return None

    diagnosticar_nulos(df)
    mostrar_primeras_filas(df)

    print("\n" + "=" * 60)
    print("Carga completada exitosamente.")
    print("=" * 60)
    return df


if __name__ == "__main__":
    ejecutar_carga()
