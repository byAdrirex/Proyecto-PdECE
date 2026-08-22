"""Export immutable, browser-safe fixtures from the legacy academic loaders.

This script is a build-time bridge only.  The frontend never imports Python or
source documents at runtime.  In particular, the Kardex export contains no
names, identifiers, raw PDF text, pages, or marks: only SIS codes and the
minimal attempt status fields needed for parity tests.
"""

from __future__ import annotations

import json
import math
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
MODULOS = ROOT / "modulos"
DATA = ROOT / "datos"
OUTPUT = ROOT / "frontend" / "src" / "data"

sys.path.insert(0, str(MODULOS))

from importador_kardex import (  # noqa: E402
    configurar_gestion,
    crear_kardex,
    cargar_desde_dataframe,
    determinar_estado_materia,
)
from lector_kardex_pdf import leer_kardex_pdf  # noqa: E402
from lector_oferta_pdf import leer_oferta_pdf  # noqa: E402
from objetivos import cargar_objetivos  # noqa: E402
from prerrequisitos import cargar_materias, construir_mapa_prerequisitos  # noqa: E402


def primitive(value: Any) -> Any:
    """Convert pandas/numpy values to stable JSON primitives."""
    if value is None:
        return None
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, bool):
        return value
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        if math.isnan(value):
            return None
        return int(value) if value.is_integer() else value
    try:
        if math.isnan(value):
            return None
    except (TypeError, ValueError):
        pass
    return str(value).strip()


def write_json(name: str, payload: dict[str, Any]) -> None:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    (OUTPUT / name).write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def export_catalog() -> tuple[dict[str, Any], dict[str, Any]]:
    dataframe = cargar_materias()
    prerequisite_map = construir_mapa_prerequisitos(dataframe)
    dependents: dict[str, list[str]] = defaultdict(list)
    subjects: list[dict[str, Any]] = []

    for _, row in dataframe.iterrows():
        code = str(row["Codigo SIS"])
        prerequisites = list(prerequisite_map[code]["prerrequisitos"])
        for prerequisite in prerequisites:
            dependents[prerequisite].append(code)
        subjects.append({
            "code": code,
            "name": primitive(row["Materia"]),
            "level": primitive(row["Nivel"]),
            "area": primitive(row["Area"]),
            "credits": primitive(row["Creditos"]),
            "hours": primitive(row["Horas"]),
            "abbreviation": primitive(row["Sigla"]),
            "type": primitive(row["Tipo"]),
            "prerequisites": prerequisites,
        })

    for subject in subjects:
        subject["dependents"] = sorted(dependents[subject["code"]])

    subjects.sort(key=lambda subject: subject["code"])
    catalog = {
        "subjects": subjects,
        "levels": sorted({subject["level"] for subject in subjects if subject["level"]}),
        "areas": sorted({subject["area"] for subject in subjects if subject["area"]}),
        "edges": [
            {"from": prerequisite, "to": subject["code"]}
            for subject in subjects
            for prerequisite in subject["prerequisites"]
        ],
    }
    return catalog, prerequisite_map


def export_objectives() -> dict[str, Any]:
    data = cargar_objetivos()

    def trajectories(kind: str, table: str, relation: str, identifier: str) -> list[dict[str, Any]]:
        items = []
        for _, row in data[table].iterrows():
            objective_id = str(row[identifier])
            codes = data[relation].loc[
                data[relation][identifier] == row[identifier], "Codigo SIS"
            ].tolist()
            items.append({
                "id": objective_id,
                "kind": kind,
                "name": primitive(row["Nombre"]),
                "subjectCodes": [str(code) for code in codes],
            })
        return items

    mentions = trajectories("mention", "menciones", "materia_mencion", "ID Mencion")
    technicians = trajectories("technician", "tecnicos", "materia_tecnico", "ID Tecnico")
    substitutions = [
        {
            "mentionId": str(row["ID Mencion"]),
            "original": str(row["SIS Materia Original"]),
            "replacement": str(row["SIS Materia Sustituta"]),
        }
        for _, row in data["sustituciones"].iterrows()
    ]
    return {
        "trajectories": mentions + technicians,
        "mentions": mentions,
        "technicians": technicians,
        "substitutions": substitutions,
        "licenciaturaElectiveRequirement": 8,
    }


def clean_group(group: dict[str, Any]) -> dict[str, Any]:
    def schedule(block: dict[str, Any]) -> dict[str, Any]:
        return {
            "day": primitive(block.get("dia")),
            "start": primitive(block.get("hora_inicio")),
            "end": primitive(block.get("hora_fin")),
            "room": primitive(block.get("aula")),
        }

    return {
        "code": str(group["codigo_sis"]),
        "name": primitive(group.get("nombre")),
        "level": primitive(group.get("nivel")),
        "group": primitive(group.get("grupo")),
        "instructor": primitive(group.get("docente")),
        "schedule": [schedule(block) for block in group.get("horarios", [])],
        "auxiliaries": [
            {
                "name": primitive(auxiliary.get("nombre")),
                "schedule": [schedule(block) for block in auxiliary.get("horarios", [])],
            }
            for auxiliary in group.get("auxiliares", [])
        ],
    }


def export_offer() -> dict[str, Any]:
    result = leer_oferta_pdf(DATA / "Oferta ECO - 2-2026.pdf", 2026, 2)
    groups = [clean_group(group) for group in result.grupos]
    groups_by_subject: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for group in groups:
        groups_by_subject[group["code"]].append(group)
    return {
        "year": result.anio,
        "term": result.gestion,
        "termType": result.tipo_periodo,
        "totalSubjects": result.materias_unicas,
        "totalGroups": result.total_grupos,
        "groups": groups,
        "groupsBySubject": dict(sorted(groups_by_subject.items())),
    }


def find_reference_kardex() -> Path:
    candidates = sorted(DATA.glob("*.pdf"))
    candidate = next((path for path in candidates if "web" in path.stem.lower()), None)
    if candidate is None:
        raise FileNotFoundError("Reference Kardex PDF was not found in datos/.")
    return candidate


def export_kardex(prerequisite_map: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    dataframe, errors = leer_kardex_pdf(find_reference_kardex())
    if dataframe is None:
        raise RuntimeError(f"Unable to parse reference Kardex: {errors}")

    kardex = crear_kardex()
    configurar_gestion(kardex, anio=2026, gestion=2)
    normalized = dataframe.rename(columns={"codigo": "Codigo SIS", "gestion": "Gestion"})
    cargar_desde_dataframe(normalized, kardex, cargar_materias())

    subjects = []
    statuses = {}
    for code in sorted(kardex["intentos"]):
        if code not in prerequisite_map:
            continue
        attempts = kardex["intentos"][code]
        # Deliberately omit year, term, grades, modality, and all raw PDF fields.
        subjects.append({
            "code": code,
            "attempts": [{"result": attempt.get("rfin")} for attempt in attempts],
        })
        statuses[code] = determinar_estado_materia(code, kardex)["estado"]

    approved = sum(status == "APROBADA" for status in statuses.values())
    return {
        "subjects": subjects,
        "approved": approved,
        "subjectCount": len(subjects),
    }, statuses


def export_golden_results(
    offer: dict[str, Any], kardex: dict[str, Any], statuses: dict[str, str]
) -> dict[str, Any]:
    representative_codes = ["1304001", "1304003", "1304022", "1304026", "1304134", "TI01"]
    return {
        "kardex": {
            "approved": kardex["approved"],
            "subjects": kardex["subjectCount"],
        },
        "offer": {
            "subjects": offer["totalSubjects"],
            "groups": offer["totalGroups"],
        },
        "representativeSubjects": {
            code: {
                "kardexStatus": statuses.get(code, "SIN_HISTORIAL"),
                "offered": code in offer["groupsBySubject"],
                "groupCount": len(offer["groupsBySubject"].get(code, [])),
            }
            for code in representative_codes
        },
        "notOffered": ["TI01", "TI02", "TI03", "TI04", "1304140", "1304162"],
    }


def main() -> None:
    catalog, prerequisite_map = export_catalog()
    objectives = export_objectives()
    offer = export_offer()
    golden_kardex, statuses = export_kardex(prerequisite_map)
    golden_results = export_golden_results(offer, golden_kardex, statuses)

    write_json("catalog.json", catalog)
    write_json("objectives.json", objectives)
    write_json("offer.json", offer)
    write_json("golden-kardex.json", golden_kardex)
    write_json("golden-results.json", golden_results)
    print(f"Exported fixtures to {OUTPUT}")


if __name__ == "__main__":
    main()
