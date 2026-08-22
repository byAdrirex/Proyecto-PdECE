"""
Lector de oferta academica desde PDF.
Estructura real del PDF: Nivel | Materia | Grupo | Docente | Dia | Hora | Aula
Una fila = un slot horario (dia+hora+aula) de un grupo.
Multiples filas conforman el horario completo de un grupo.
Diseñado para permitir OCR posteriormente.
"""

import os
import re
import pandas as pd

try:
    import pdfplumber
except ImportError:
    pdfplumber = None

RUTA_EXCEL = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "datos", "Exel Plan de estudios.xlsx"
)

GESTIONES = {
    1: "semestre regular",
    2: "semestre regular",
    3: "intersemestral verano",
    4: "intersemestral invierno",
}

DIAS_NORMALIZADOS = {
    "LU": "LU", "LUN": "LU", "LUNES": "LU",
    "MA": "MA", "MAR": "MA", "MARTES": "MA",
    "MI": "MI", "MIE": "MI", "MIER": "MI", "MIERCOLES": "MI",
    "JU": "JU", "JUE": "JU", "JUEVES": "JU",
    "VI": "VI", "VIE": "VI", "VIERNES": "VI",
    "SA": "SA", "SAB": "SA", "SABADO": "SA",
}

ALIAS_COLUMNAS = {
    "nivel": ["nivel", "niv"],
    "materia": ["materia", "asignatura", "materia/asignatura"],
    "grupo": ["grupo", "grp", "gpo", "seccion"],
    "docente": ["docente", "profesor", "prof.", "catedratico"],
    "dia": ["dia", "dia(s)", "dias", "horario"],
    "hora": ["hora", "horario", "hora(s)"],
    "aula": ["aula", "sede", "lugar", "salon"],
}


def _normalizar(texto):
    if texto is None:
        return ""
    return re.sub(r"\s+", " ", str(texto).strip())


def _normalizar_codigo(valor):
    return _normalizar(valor).replace(".", "")


def _es_codigo_sis(valor):
    valor = _normalizar(valor).replace(".", "")
    if not valor:
        return False
    if valor.startswith("TI"):
        return True
    if re.match(r"^\d{5,7}$", valor):
        return True
    return False


def separar_codigo_nombre(texto):
    texto = _normalizar(texto)
    if not texto:
        return None, None
    m = re.match(r"^(\d{5,7})\s*[-–—]\s*(.+)$", texto)
    if m:
        return m.group(1), _normalizar(m.group(2))
    m2 = re.match(r"^(TI\d+)\s*[-–—]\s*(.+)$", texto)
    if m2:
        return m2.group(1), _normalizar(m2.group(2))
    if _es_codigo_sis(texto):
        return texto, None
    return None, texto


def normalizar_dia(texto):
    texto = _normalizar(texto).upper()
    for alias, norm in DIAS_NORMALIZADOS.items():
        if texto == alias:
            return norm
    for alias, norm in DIAS_NORMALIZADOS.items():
        if alias in texto:
            return norm
    return texto


def parsear_hora(texto):
    texto = _normalizar(texto)
    if not texto:
        return None
    m = re.match(
        r"(\d{1,2})[:\uff1a](\d{2})\s*[-–a]\s*(\d{1,2})[:\uff1a](\d{2})",
        texto, re.IGNORECASE,
    )
    if m:
        h1 = m.group(1).zfill(2)
        mi1 = m.group(2)
        h2 = m.group(3).zfill(2)
        mi2 = m.group(4)
        return "%s:%s" % (h1, mi1), "%s:%s" % (h2, mi2)
    m2 = re.match(r"(\d{1,2})[:\uff1a](\d{2})", texto)
    if m2:
        return "%s:%s" % (m2.group(1).zfill(2), m2.group(2)), None
    return texto, None


def _parsear_hora_simple(texto):
    resultado = parsear_hora(texto)
    if resultado:
        return resultado[0]
    return None


def _parsear_rango_hora(texto):
    resultado = parsear_hora(texto)
    if resultado:
        return resultado
    return None, None


def _detectar_mapeo(headers):
    mapeo = {}
    headers_norm = [_normalizar(h).lower() for h in headers]
    for campo, aliases in ALIAS_COLUMNAS.items():
        for i, hnorm in enumerate(headers_norm):
            if not hnorm:
                continue
            for alias in aliases:
                if alias == hnorm or alias in hnorm or hnorm in alias:
                    if campo not in mapeo:
                        mapeo[campo] = i
                    break
            if campo in mapeo:
                break
    return mapeo


_RE_MATERIA = re.compile(
    r"^([A-I])\s+(\d{5,7}|TI\d+)\s+(.+)$"
)
_RE_GRUPOCompleto = re.compile(
    r"^(\d{2})\s+(\[AUX\]\s+)?(.+?)\s+"
    r"(LU|MA|MI|JU|VI|SA|LUN|MAR|MIE|JUE|VIE|SAB)\s+"
    r"(\d{1,2}:\d{2})\s*[-–]\s*(\d{1,2}:\d{2})\s+"
    r"(.+)$"
)
_RE_GRUPO_docente = re.compile(
    r"^(\d{2})\s+(\[AUX\]\s+)?(.+)$"
)
_RE_HORARIO = re.compile(
    r"^(LU|MA|MI|JU|VI|SA|LUN|MAR|MIE|JUE|VIE|SAB)\s+"
    r"(\d{1,2}:\d{2})\s*[-–]\s*(\d{1,2}:\d{2})\s+"
    r"(.+)$"
)
_RE_HEADER = re.compile(
    r"^NIVEL\s+MATERIA|HORARIO\s+DE\s+CLASES|Procesado|Gesti.n\s+Acad.mica",
    re.IGNORECASE,
)
_RE_FOOTER = re.compile(r"^P.gina\s+\d+", re.IGNORECASE)

# Frases fijas de encabezado/pie de pagina del PDF que a veces quedan pegadas
# a una fila de horario y contaminan el nombre del docente, provocando que se
# pierda ese dia en el grupo (ej: ECONOMIA POLITICA I G01 perdia el viernes).
_FRASES_ENCABEZADO = (
    "UNIVERSIDAD MAYOR DE SAN SIMON",
    "FACULTAD DE CIENCIAS ECONOMICAS",
    "LICENCIATURA EN ECONOMIA",
    "CARRERA DE LICENCIATURA EN ECONOMIA",
    "HORARIO DE CLASES",
    "GESTION ACADEMICA",
)


def _limpiar_frases_fijas(linea):
    for frase in _FRASES_ENCABEZADO:
        linea = re.sub(re.escape(frase), " ", linea, flags=re.IGNORECASE)
    return _normalizar(linea)


def _es_linea_materia(linea):
    return _RE_MATERIA.match(linea) is not None


def _parsear_linea_materia(linea):
    m = _RE_MATERIA.match(linea)
    if not m:
        return None, None, None
    return m.group(1), m.group(2), _normalizar(m.group(3))


def _parsear_grupo_completo(linea):
    m = _RE_GRUPOCompleto.match(linea)
    if not m:
        return None
    grupo = m.group(1)
    es_aux = m.group(2) is not None
    docente_raw = _normalizar(m.group(3))
    dia = normalizar_dia(m.group(4))
    h_inicio = "%s:%s" % (m.group(5).split(":")[0].zfill(2), m.group(5).split(":")[1])
    h_fin = "%s:%s" % (m.group(6).split(":")[0].zfill(2), m.group(6).split(":")[1])
    aula = _normalizar(m.group(7))
    return {
        "grupo": grupo, "docente": docente_raw, "es_aux": es_aux,
        "dia": dia, "hora_inicio": h_inicio, "hora_fin": h_fin, "aula": aula,
    }


def _parsear_grupo_docente(linea):
    m = _RE_GRUPO_docente.match(linea)
    if not m:
        return None
    grupo = m.group(1)
    es_aux = m.group(2) is not None
    docente_raw = _normalizar(m.group(3))
    return {"grupo": grupo, "docente": docente_raw, "es_aux": es_aux}


def _parsear_horario(linea):
    m = _RE_HORARIO.match(linea)
    if not m:
        return None
    dia = normalizar_dia(m.group(1))
    h1 = m.group(2)
    h2 = m.group(3)
    h_inicio = "%s:%s" % (h1.split(":")[0].zfill(2), h1.split(":")[1])
    h_fin = "%s:%s" % (h2.split(":")[0].zfill(2), h2.split(":")[1])
    aula = _normalizar(m.group(4))
    return {"dia": dia, "hora_inicio": h_inicio, "hora_fin": h_fin, "aula": aula}


def extraer_lineas_pdf(ruta_pdf):
    if pdfplumber is None:
        raise ImportError("pdfplumber no esta instalado: pip install pdfplumber")
    lineas = []
    with pdfplumber.open(ruta_pdf) as pdf:
        for page_idx, page in enumerate(pdf.pages):
            text = page.extract_text()
            if text:
                for linea in text.split("\n"):
                    lineas.append({"texto": linea.strip(), "pagina": page_idx + 1})
    return lineas


def _parsear_lineas_oferta(lineas_extraidas):
    resultado = []
    nivel_actual = None
    codigo_actual = None
    nombre_actual = None
    grupo_actual = None
    docente_actual = None
    es_aux_actual = False
    slots_pendientes = []

    for item in lineas_extraidas:
        linea = _limpiar_frases_fijas(item["texto"])
        if not linea:
            continue
        if _RE_HEADER.match(linea) or _RE_FOOTER.match(linea):
            continue

        es_materia = _es_linea_materia(linea)
        es_grupo_compl = _parsear_grupo_completo(linea) is not None
        es_grupo_doc = (not es_grupo_compl and
                        _parsear_grupo_docente(linea) is not None)
        es_horario = (not es_grupo_compl and not es_grupo_doc and
                      _parsear_horario(linea) is not None)

        if es_materia:
            if codigo_actual and grupo_actual and docente_actual and slots_pendientes:
                for slot in slots_pendientes:
                    resultado.append({
                        "nivel": nivel_actual, "codigo_sis": codigo_actual,
                        "nombre": nombre_actual, "grupo": grupo_actual,
                        "docente": docente_actual, "es_aux": es_aux_actual,
                        "dia": slot["dia"], "hora_inicio": slot["hora_inicio"],
                        "hora_fin": slot["hora_fin"], "aula": slot["aula"],
                        "pagina": item["pagina"],
                    })
            elif codigo_actual and grupo_actual and docente_actual and not slots_pendientes:
                resultado.append({
                    "nivel": nivel_actual, "codigo_sis": codigo_actual,
                    "nombre": nombre_actual, "grupo": grupo_actual,
                    "docente": docente_actual, "es_aux": es_aux_actual,
                    "dia": None, "hora_inicio": None,
                    "hora_fin": None, "aula": None,
                    "pagina": item["pagina"],
                })
            nivel_actual, codigo_actual, nombre_actual = _parsear_linea_materia(linea)
            grupo_actual = None
            docente_actual = None
            es_aux_actual = False
            slots_pendientes = []
            continue

        if es_grupo_compl:
            if codigo_actual and grupo_actual and docente_actual and slots_pendientes:
                for slot in slots_pendientes:
                    resultado.append({
                        "nivel": nivel_actual, "codigo_sis": codigo_actual,
                        "nombre": nombre_actual, "grupo": grupo_actual,
                        "docente": docente_actual, "es_aux": es_aux_actual,
                        "dia": slot["dia"], "hora_inicio": slot["hora_inicio"],
                        "hora_fin": slot["hora_fin"], "aula": slot["aula"],
                        "pagina": item["pagina"],
                    })
            elif codigo_actual and grupo_actual and docente_actual and not slots_pendientes:
                resultado.append({
                    "nivel": nivel_actual, "codigo_sis": codigo_actual,
                    "nombre": nombre_actual, "grupo": grupo_actual,
                    "docente": docente_actual, "es_aux": es_aux_actual,
                    "dia": None, "hora_inicio": None,
                    "hora_fin": None, "aula": None,
                    "pagina": item["pagina"],
                })

            datos = _parsear_grupo_completo(linea)
            grupo_actual = datos["grupo"]
            docente_actual = datos["docente"]
            es_aux_actual = datos["es_aux"]
            slots_pendientes = [{
                "dia": datos["dia"], "hora_inicio": datos["hora_inicio"],
                "hora_fin": datos["hora_fin"], "aula": datos["aula"],
            }]
            continue

        if es_grupo_doc:
            if codigo_actual and grupo_actual and docente_actual and slots_pendientes:
                for slot in slots_pendientes:
                    resultado.append({
                        "nivel": nivel_actual, "codigo_sis": codigo_actual,
                        "nombre": nombre_actual, "grupo": grupo_actual,
                        "docente": docente_actual, "es_aux": es_aux_actual,
                        "dia": slot["dia"], "hora_inicio": slot["hora_inicio"],
                        "hora_fin": slot["hora_fin"], "aula": slot["aula"],
                        "pagina": item["pagina"],
                    })
            elif codigo_actual and grupo_actual and docente_actual and not slots_pendientes:
                resultado.append({
                    "nivel": nivel_actual, "codigo_sis": codigo_actual,
                    "nombre": nombre_actual, "grupo": grupo_actual,
                    "docente": docente_actual, "es_aux": es_aux_actual,
                    "dia": None, "hora_inicio": None,
                    "hora_fin": None, "aula": None,
                    "pagina": item["pagina"],
                })

            datos = _parsear_grupo_docente(linea)
            grupo_actual = datos["grupo"]
            docente_actual = datos["docente"]
            es_aux_actual = datos["es_aux"]
            slots_pendientes = []
            continue

        if es_horario:
            slot = _parsear_horario(linea)
            if slot:
                slots_pendientes.append(slot)
            continue

        if codigo_actual and grupo_actual and docente_actual:
            docente_actual = docente_actual + " " + linea
            continue

    if codigo_actual and grupo_actual and docente_actual and slots_pendientes:
        for slot in slots_pendientes:
            resultado.append({
                "nivel": nivel_actual, "codigo_sis": codigo_actual,
                "nombre": nombre_actual, "grupo": grupo_actual,
                "docente": docente_actual, "es_aux": es_aux_actual,
                "dia": slot["dia"], "hora_inicio": slot["hora_inicio"],
                "hora_fin": slot["hora_fin"], "aula": slot["aula"],
                "pagina": 0,
            })
    elif codigo_actual and grupo_actual and docente_actual:
        resultado.append({
            "nivel": nivel_actual, "codigo_sis": codigo_actual,
            "nombre": nombre_actual, "grupo": grupo_actual,
            "docente": docente_actual, "es_aux": es_aux_actual,
            "dia": None, "hora_inicio": None,
            "hora_fin": None, "aula": None,
            "pagina": 0,
        })

    return resultado


def agrupar_grupos(filas_extraidas):
    from collections import OrderedDict

    pre_grupos = OrderedDict()
    for f in filas_extraidas:
        cod = f["codigo_sis"]
        nivel = f["nivel"]
        grupo = f["grupo"]
        docente = f["docente"]
        es_aux = f["es_aux"]
        dia = f["dia"]
        h_inicio = f["hora_inicio"]
        h_fin = f["hora_fin"]
        aula = f["aula"]

        slot = None
        if dia and h_inicio:
            slot = {"dia": dia, "hora_inicio": h_inicio,
                    "hora_fin": h_fin, "aula": aula}

        clave_base = (nivel or "", cod or "", grupo or "")
        if clave_base not in pre_grupos:
            pre_grupos[clave_base] = {
                "codigo_sis": cod, "nombre": f.get("nombre"),
                "nivel": nivel, "grupo": grupo,
                "docentes": OrderedDict(),
            }
        pg = pre_grupos[clave_base]
        if f.get("nombre") and not pg["nombre"]:
            pg["nombre"] = f.get("nombre")

        if es_aux:
            nombre_aux = docente or "AUX"
            clave_aux = "__AUX__" + nombre_aux
            if clave_aux not in pg["docentes"]:
                pg["docentes"][clave_aux] = {
                    "docente": None, "es_aux": True,
                    "nombre_aux": nombre_aux, "slots": [],
                }
            if slot:
                pg["docentes"][clave_aux]["slots"].append(slot)
        else:
            clave_doc = docente or "__SIN_DOCENTE__"
            if clave_doc not in pg["docentes"]:
                pg["docentes"][clave_doc] = {
                    "docente": docente, "es_aux": False,
                    "nombre_aux": None, "slots": [],
                }
            if slot:
                pg["docentes"][clave_doc]["slots"].append(slot)

    grupos = []
    for clave_base, pg in pre_grupos.items():
        principales = []
        auxiliares = []

        for dk, dv in pg["docentes"].items():
            if dv["es_aux"]:
                horarios = []
                seen = set()
                for s in dv["slots"]:
                    key = (s.get("dia"), s.get("hora_inicio"),
                           s.get("hora_fin"), s.get("aula"))
                    if key not in seen:
                        seen.add(key)
                        horarios.append(s)
                auxiliares.append({
                    "nombre": dv["nombre_aux"],
                    "horarios": horarios,
                })
            else:
                principales.append(dv)

        # Un mismo grupo puede haber quedado dividido en varias entradas de
        # docente (por contaminacion de texto del PDF); se unen todos sus slots.
        if principales:
            principal = {
                "docente": principales[0]["docente"],
                "slots": [],
            }
            for p in principales:
                principal["slots"].extend(p.get("slots", []))
        else:
            principal = {"docente": None, "slots": []}

        horarios_consolidados = []
        seen = set()
        for s in principal.get("slots", []):
            key = (s.get("dia"), s.get("hora_inicio"),
                   s.get("hora_fin"), s.get("aula"))
            if key not in seen:
                seen.add(key)
                horarios_consolidados.append(s)

        grupos.append({
            "codigo_sis": pg["codigo_sis"],
            "nombre": pg["nombre"],
            "nivel": pg["nivel"],
            "grupo": pg["grupo"],
            "docente": principal.get("docente"),
            "auxiliares": auxiliares,
            "horarios": horarios_consolidados,
        })

    return grupos


def extraer_tablas_pdf(ruta_pdf):
    if pdfplumber is None:
        raise ImportError("pdfplumber no esta instalado: pip install pdfplumber")

    tablas_raw = []
    with pdfplumber.open(ruta_pdf) as pdf:
        for page_idx, page in enumerate(pdf.pages):
            tables = page.extract_tables()
            for t_idx, tabla in enumerate(tables):
                if tabla and len(tabla) > 1:
                    tablas_raw.append({
                        "pagina": page_idx + 1,
                        "tabla_idx": t_idx,
                        "datos": tabla,
                    })

            if not tables:
                text = page.extract_text()
                if text:
                    lineas = text.split("\n")
                    tabla_texto = []
                    for linea in lineas:
                        partes = re.split(r"\s{2,}", linea.strip())
                        if len(partes) >= 3:
                            tabla_texto.append(partes)
                    if len(tabla_texto) >= 3:
                        tablas_raw.append({
                            "pagina": page_idx + 1,
                            "tabla_idx": -1,
                            "datos": tabla_texto,
                            "fuente": "texto",
                        })

    return tablas_raw


def leer_oferta_pdf(ruta_pdf, anio, gestion):
    if gestion not in GESTIONES:
        raise ValueError(
            "Gestion invalida: %d. Validas: %s"
            % (gestion, list(GESTIONES.keys()))
        )

    lineas_extraidas = extraer_lineas_pdf(ruta_pdf)
    filas_raw = _parsear_lineas_oferta(lineas_extraidas)
    grupos = agrupar_grupos(filas_raw)

    for g in grupos:
        g["anio"] = anio
        g["gestion"] = gestion
        g["tipo_periodo"] = GESTIONES.get(gestion, "")

    resultado = ResultadoOferta(
        grupos=grupos, anio=anio, gestion=gestion, ruta_pdf=ruta_pdf,
    )
    resultado.validar()
    return resultado


class ResultadoOferta:
    def __init__(self, grupos, anio, gestion, ruta_pdf):
        self.grupos = grupos
        self.anio = anio
        self.gestion = gestion
        self.ruta_pdf = ruta_pdf
        self.tipo_periodo = GESTIONES.get(gestion, "")
        self.advertencias = []
        self.errores = []
        self.codigos_desconocidos = []
        self.niveles_inconsistentes = []
        self.duplicados = []
        self.docentes_vacios = []
        self.grupos_sin_horarios = []
        self.grupos_con_auxiliares = []
        self._df_materias = None
        self._niveles_excel = {}

    @property
    def total_grupos(self):
        return len(self.grupos)

    @property
    def materias_unicas(self):
        return len(set(
            g["codigo_sis"] for g in self.grupos if g["codigo_sis"]
        ))

    @property
    def docentes_unicos(self):
        return len(set(
            g["docente"] for g in self.grupos if g["docente"]
        ))

    @property
    def total_auxiliares(self):
        return sum(len(g.get("auxiliares", [])) for g in self.grupos)

    @property
    def total_horarios(self):
        return sum(len(g.get("horarios", [])) for g in self.grupos)

    @property
    def aulas_detectadas(self):
        aulas = set()
        for g in self.grupos:
            for h in g.get("horarios", []):
                if h.get("aula"):
                    aulas.add(h["aula"])
        return aulas

    @property
    def niveles_detectados(self):
        return sorted(set(
            g["nivel"] for g in self.grupos if g["nivel"]
        ))

    def _cargar_materias(self):
        try:
            if os.path.exists(RUTA_EXCEL):
                df = pd.read_excel(RUTA_EXCEL, sheet_name="Materias")
                df["Codigo SIS"] = df["Codigo SIS"].astype(str)
                return df
        except Exception:
            pass
        return None

    def validar(self):
        self.advertencias = []
        self.errores = []
        self.codigos_desconocidos = []
        self.niveles_inconsistentes = []
        self.duplicados = []
        self.docentes_vacios = []
        self.grupos_sin_horarios = []
        self.grupos_con_auxiliares = []

        self._df_materias = self._cargar_materias()
        if self._df_materias is not None:
            for _, row in self._df_materias.iterrows():
                cod = str(row["Codigo SIS"])
                nivel = row.get("Nivel")
                if pd.notna(nivel):
                    self._niveles_excel[cod] = str(nivel).strip().upper()

        if not self.grupos:
            self.errores.append(
                "No se extrajeron grupos del PDF. "
                "Verifique que el PDF contiene tablas con oferta academica."
            )
            return

        codigos_vistos = {}
        for g in self.grupos:
            cod = g["codigo_sis"]

            if cod is None:
                self.errores.append(
                    "Grupo sin codigo SIS detectado (nivel=%s, nombre=%s)"
                    % (g["nivel"], g["nombre"])
                )
                continue

            if cod and cod not in self._niveles_excel and self._df_materias is not None:
                self.codigos_desconocidos.append(cod)
                self.advertencias.append("Codigo SIS desconocido: %s" % cod)

            if cod and g["nivel"] and cod in self._niveles_excel:
                nivel_excel = self._niveles_excel[cod]
                if g["nivel"] != nivel_excel:
                    self.niveles_inconsistentes.append({
                        "codigo_sis": cod,
                        "nivel_pdf": g["nivel"],
                        "nivel_excel": nivel_excel,
                    })
                    self.advertencias.append(
                        "Nivel diferente para %s: PDF=%s, Excel=%s"
                        % (cod, g["nivel"], nivel_excel)
                    )

            if not g["docente"]:
                self.docentes_vacios.append(cod)

            if not g["horarios"]:
                self.grupos_sin_horarios.append(cod)

            if g.get("auxiliares"):
                self.grupos_con_auxiliares.append(cod)

            clave = (cod, g.get("grupo"))
            if clave in codigos_vistos:
                self.duplicados.append({
                    "codigo_sis": cod,
                    "grupo": g.get("grupo"),
                })
            else:
                codigos_vistos[clave] = g

    def primeros_grupos(self, n=10):
        return self.grupos[:n]

    def resumen(self):
        lineas = []
        lineas.append("=" * 65)
        lineas.append("REPORTE DE OFERTA ACADEMICA")
        lineas.append("=" * 65)
        lineas.append("PDF: %s" % os.path.basename(self.ruta_pdf))
        lineas.append("Periodo: %s %d/G%d" % (
            self.tipo_periodo, self.anio, self.gestion))
        lineas.append("")
        lineas.append("--- Estadisticas ---")
        lineas.append("Materias detectadas  : %d" % self.materias_unicas)
        lineas.append("Grupos detectados    : %d" % self.total_grupos)
        lineas.append("Docentes principales : %d" % self.docentes_unicos)
        lineas.append("Auxiliares           : %d" % self.total_auxiliares)
        lineas.append("Horarios totales     : %d" % self.total_horarios)
        lineas.append("Aulas detectadas     : %d" % len(self.aulas_detectadas))
        lineas.append("Niveles              : %s" % (
            ", ".join(self.niveles_detectados) if self.niveles_detectados else "-"))
        lineas.append("")
        lineas.append("--- Validacion ---")
        lineas.append("Codigos desconocidos  : %d" % len(self.codigos_desconocidos))
        lineas.append("Niveles inconsistentes: %d" % len(self.niveles_inconsistentes))
        lineas.append("Duplicados            : %d" % len(self.duplicados))
        lineas.append("Docentes vacios       : %d" % len(self.docentes_vacios))
        lineas.append("Grupos sin horarios   : %d" % len(self.grupos_sin_horarios))
        lineas.append("Grupos con auxiliares  : %d" % len(self.grupos_con_auxiliares))
        lineas.append("Errores               : %d" % len(self.errores))

        if self.advertencias:
            lineas.append("")
            lineas.append("--- Advertencias ---")
            for adv in self.advertencias[:25]:
                lineas.append("  * %s" % adv)
            if len(self.advertencias) > 25:
                lineas.append("  ... y %d mas" % (
                    len(self.advertencias) - 25))

        if self.errores:
            lineas.append("")
            lineas.append("--- Errores ---")
            for err in self.errores:
                lineas.append("  [!] %s" % err)

        if self.grupos:
            lineas.append("")
            n = min(10, len(self.grupos))
            lineas.append("--- Primeros %d registros completos ---" % n)
            for i, g in enumerate(self.grupos[:n]):
                lineas.append("")
                lineas.append("  [%d] %s - %s" % (
                    i + 1, g["codigo_sis"] or "???",
                    g["nombre"] or "???"))
                lineas.append("      Nivel: %s | Grupo: %s | Docente: %s" % (
                    g["nivel"] or "?", g["grupo"] or "?",
                    g["docente"] or "???"))
                if g.get("auxiliares"):
                    for aux in g["auxiliares"]:
                        lineas.append("      AUX: %s" % aux["nombre"])
                for h in g.get("horarios", []):
                    lineas.append("      %s %s-%s  Aula: %s" % (
                        h.get("dia") or "??",
                        h.get("hora_inicio") or "??:??",
                        h.get("hora_fin") or "??:??",
                        h.get("aula") or "-"))

        lineas.append("")
        lineas.append("=" * 65)
        return "\n".join(lineas)


def ejecutar_prueba_ficticia():
    print("No hay PDF real de oferta academica en datos/.")
    print("Ejecutando prueba con datos ficticios...\n")

    lineas_mock = [
        {"texto": "NIVEL MATERIA GRUPO DOCENTE DIA HORA AULA", "pagina": 1},
        {"texto": "A 1304001 ECONOMIA GENERAL", "pagina": 1},
        {"texto": "01 DRA. MARIA TORRES MA 08:00 - 09:30 E530", "pagina": 1},
        {"texto": "01 DRA. MARIA TORRES JU 08:00 - 09:30 E530", "pagina": 1},
        {"texto": "02 DR. LUIS GARCIA VI 14:15 - 15:45 E531", "pagina": 1},
        {"texto": "A 1304003 ALGEBRA", "pagina": 1},
        {"texto": "01 DR. ROBERTO SANCHEZ LU 07:00 - 08:30 E510", "pagina": 1},
        {"texto": "01 DR. ROBERTO SANCHEZ MI 07:00 - 08:30 E510", "pagina": 1},
        {"texto": "01 DR. ROBERTO SANCHEZ VI 07:00 - 08:30 E510", "pagina": 1},
        {"texto": "B 1304007 MICROECONOMIA I", "pagina": 1},
        {"texto": "01 DR. CARLOS MENDEZ LU 10:15 - 11:45 E530", "pagina": 1},
        {"texto": "01 DR. CARLOS MENDEZ MI 10:15 - 11:45 E530", "pagina": 1},
        {"texto": "02 DRA. ANA LOPEZ MA 12:45 - 14:15 E531", "pagina": 1},
        {"texto": "02 DRA. ANA LOPEZ JU 12:45 - 14:15 E531", "pagina": 1},
        {"texto": "B 1304008 MACROECONOMIA I", "pagina": 1},
        {"texto": "01 DR. FERNANDO RUIZ LU 14:15 - 15:45 E520", "pagina": 1},
        {"texto": "01 DR. FERNANDO RUIZ MI 14:15 - 15:45 E520", "pagina": 1},
        {"texto": "01 [AUX] LAURA PEREZ MA 14:15 - 15:45 E520", "pagina": 1},
        {"texto": "C 1304015 HISTORIA DEL PENSAMIENTO ECONOMICO", "pagina": 1},
        {"texto": "01 DRA. ELENA MORALES MI 18:30 - 20:00 E601", "pagina": 1},
        {"texto": "01 DRA. ELENA MORALES VI 18:30 - 20:00 E601", "pagina": 1},
        {"texto": "A 1304018 CONTABILIDAD BASICA", "pagina": 1},
        {"texto": "01 ING. PATRICIA MENDOZA MA 07:00 - 08:30 E510", "pagina": 1},
        {"texto": "01 ING. PATRICIA MENDOZA JU 07:00 - 08:30 E510", "pagina": 1},
        {"texto": "D 1304129 DEMOGRAFIA", "pagina": 1},
        {"texto": "01 DRA. SOFIA RIOS VI 08:00 - 11:00 E602", "pagina": 1},
        {"texto": "B 9999999 MATERIA FANTASMA", "pagina": 1},
        {"texto": "01 LU 10:00 - 11:30 E999", "pagina": 1},
    ]

    filas_raw = _parsear_lineas_oferta(lineas_mock)
    grupos = agrupar_grupos(filas_raw)
    for g in grupos:
        g["anio"] = 2026
        g["gestion"] = 2
        g["tipo_periodo"] = "semestre regular"

    resultado = ResultadoOferta(
        grupos=grupos, anio=2026, gestion=2,
        ruta_pdf="[datos ficticios]",
    )
    resultado.validar()
    print(resultado.resumen())
    return resultado


if __name__ == "__main__":
    import sys
    if len(sys.argv) >= 3:
        ruta = sys.argv[1]
        anio = int(sys.argv[2])
        gestion = int(sys.argv[3]) if len(sys.argv) > 3 else 1
        resultado = leer_oferta_pdf(ruta, anio, gestion)
        print(resultado.resumen())
    else:
        ejecutar_prueba_ficticia()
