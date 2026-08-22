"""
Gestion interna del kardex de un estudiante.
Trabaja exclusivamente con codigos SIS.
Independiente del origen de datos (PDF, OCR, manual).
"""

NOTA_MINIMA_APROBACION = 51

ESTADO_APROBADA = "APROBADA"
ESTADO_REPROBADA = "REPROBADA"
ESTADO_EN_CURSO = "EN_CURSO"
ESTADO_ABANDONADA = "ABANDONADA"
ESTADO_MESA = "MESA"

ESTADOS_VALIDOS = {
    ESTADO_APROBADA,
    ESTADO_REPROBADA,
    ESTADO_EN_CURSO,
    ESTADO_ABANDONADA,
    ESTADO_MESA,
}


def crear_kardex():
    return {}


def _validar_estado(nota, estado):
    if estado is not None:
        if estado not in ESTADOS_VALIDOS:
            raise ValueError(
                f"Estado invalido: '{estado}'. "
                f"Validos: {', '.join(sorted(ESTADOS_VALIDOS))}"
            )
        return estado

    if nota is None:
        return ESTADO_EN_CURSO
    if nota >= NOTA_MINIMA_APROBACION:
        return ESTADO_APROBADA
    return ESTADO_REPROBADA


def registrar_materia(kardex, codigo_sis, nota=None, estado=None):
    codigo_sis = str(codigo_sis)
    estado_final = _validar_estado(nota, estado)

    kardex[codigo_sis] = {
        "nota": nota,
        "estado": estado_final,
    }
    return kardex[codigo_sis]


def consultar_estado(kardex, codigo_sis):
    codigo_sis = str(codigo_sis)
    if codigo_sis not in kardex:
        return None
    return kardex[codigo_sis]["estado"]


def esta_aprobada(kardex, codigo_sis):
    return consultar_estado(kardex, codigo_sis) == ESTADO_APROBADA


def materias_aprobadas(kardex):
    return [c for c, v in kardex.items() if v["estado"] == ESTADO_APROBADA]


def materias_reprobadas(kardex):
    return [c for c, v in kardex.items() if v["estado"] == ESTADO_REPROBADA]


def materias_en_curso(kardex):
    return [c for c, v in kardex.items() if v["estado"] == ESTADO_EN_CURSO]


def creditos_aprobados(kardex, materias_df):
    aprobadas = set(materias_aprobadas(kardex))
    df = materias_df.copy()
    df["Codigo SIS"] = df["Codigo SIS"].astype(str)
    total = df[df["Codigo SIS"].isin(aprobadas)]["Creditos"].sum()
    return int(total) if total == int(total) else total


def resumen(kardex, materias_df=None):
    total = len(kardex)
    a = len(materias_aprobadas(kardex))
    r = len(materias_reprobadas(kardex))
    ec = len(materias_en_curso(kardex))
    print(f"Total registros: {total}")
    print(f"  Aprobadas : {a}")
    print(f"  Reprobadas: {r}")
    print(f"  En curso  : {ec}")
    if materias_df is not None:
        creds = creditos_aprobados(kardex, materias_df)
        print(f"  Creditos aprobados: {creds}")


def ejecutar_prueba():
    from carga_datos import cargar_materias

    print("=" * 60)
    print("PRUEBA DEL KARDEX - DATOS FICTICIOS")
    print("=" * 60)

    kardex = crear_kardex()

    datos_prueba = [
        ("1304001", 72, None),
        ("1304002", 65, None),
        ("1304003", 48, None),
        ("1304004", None, None),
        ("1304005", 80, None),
        ("1304007", 55, None),
        ("1304018", None, "EN_CURSO"),
    ]

    print("\n--- Registrando materias ---")
    for codigo, nota, estado in datos_prueba:
        info = registrar_materia(kardex, codigo, nota, estado)
        print(f"  {codigo}: nota={nota}, estado={info['estado']}")

    print("\n--- Resumen ---")
    df = cargar_materias()
    resumen(kardex, df)

    print("\n--- Verificaciones ---")
    for codigo, _, _ in datos_prueba:
        aprobada = "SI" if esta_aprobada(kardex, codigo) else "NO"
        estado = consultar_estado(kardex, codigo)
        print(f"  {codigo}: aprobada={aprobada}, estado={estado}")

    print("\n--- Materias aprobadas ---")
    for c in materias_aprobadas(kardex):
        info = kardex[c]
        print(f"  {c}: nota {info['nota']}")

    print("\n--- Estado inexistente ---")
    resultado = consultar_estado(kardex, "9999999")
    print(f"  9999999: {resultado}")

    print("\n" + "=" * 60)
    print("PRUEBA COMPLETADA")
    print("=" * 60)


if __name__ == "__main__":
    ejecutar_prueba()
