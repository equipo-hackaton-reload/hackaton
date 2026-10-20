"""Carga del kit de reload (`data/kit/02_Datos/<caso>/`) a modelos del dominio.

Cada `load_*` solo lee un CSV local (UTF-8 con BOM) y delega en su `*_from_frame`, que es puro:
recibe un DataFrame y devuelve modelos. Los nombres de columna son los del diccionario de datos.
"""

import re
from collections.abc import Iterable
from pathlib import Path
from typing import Any, cast

import pandas as pd
from pydantic import BaseModel, ValidationError

from posiq.domain.schemas import (
    Brand,
    Evaluation,
    FaseEmbudo,
    PromptInstance,
    PromptTemplate,
    Rol,
    Run,
    Source,
)
from posiq.domain.text import fold, slugify

MARCAS_COLS = ["Marca", "Nivel", "Rol", "Dominio_propio", "Alias"]
BANCO_COLS = [
    "Prompt_ID",
    "Familia",
    "Intención",
    "Prioridad",
    "Uso",
    "Instanciación",
    "Prompt (plantilla)",
]
EJECUCIONES_COLS = [
    "Ejecucion_ID",
    "Prompt_ID",
    "Prompt ejecutado",
    "Motor",
    "Repetición",
    "Marcas a evaluar",
    "Respuesta completa",
    "Fuentes citadas",
    "Fecha/hora",
]
FUENTES_COLS = ["Dominio", "Tipo_de_fuente", "Calidad_de_fuente_0_1"]
MUESTRA_COLS = [
    "Marca",
    "Aparece (1/0)",
    "Posición",
    "Tipo de mención",
    "Fuerza recomendación (-1 a 3)",
    "Sentimiento",
    "Tipo de fuente",
    "Ejecucion_ID",
]

FASES: dict[str, FaseEmbudo] = {
    "descubrimiento": "descubrimiento",
    "comparacion": "comparacion",
    "validacion": "validacion",
    "decision": "decision",
}
PLACEHOLDERS = {"[MARCA_A]": "marca_a", "[MARCA_B]": "marca_b", "[CIUDAD]": "ciudad"}


class KitFormatError(ValueError):
    """El fichero del kit no tiene el formato del diccionario de datos."""


# --- Utilidades -----------------------------------------------------------------------------------


def read_kit_csv(path: str | Path) -> pd.DataFrame:
    """Lee un CSV del kit como texto (sin inferir tipos) con `utf-8-sig`."""
    return pd.read_csv(path, encoding="utf-8-sig", dtype=str, keep_default_na=False)


def _require(df: pd.DataFrame, cols: Iterable[str], fichero: str) -> None:
    faltan = [c for c in cols if c not in df.columns]
    if faltan:
        raise KitFormatError(f"{fichero}: faltan columnas {faltan}; hay {list(df.columns)}")


def _rows(df: pd.DataFrame) -> list[dict[str, str]]:
    return cast(list[dict[str, str]], df.to_dict(orient="records"))


def _split(value: str, sep: str) -> list[str]:
    return [v.strip() for v in value.split(sep) if v.strip()]


def _build[M: BaseModel](model: type[M], data: dict[str, Any], fichero: str, fila: int) -> M:
    try:
        return model.model_validate(data)
    except ValidationError as exc:
        raise KitFormatError(f"{fichero} fila {fila + 2}: {exc}") from exc


def _brand_index(brands: list[Brand]) -> dict[str, str]:
    """Nombre o alias normalizado → brand_id."""
    index: dict[str, str] = {}
    for b in brands:
        for name in [b.nombre, *b.aliases]:
            index[fold(name)] = b.id
    return index


def _resolve(name: str, index: dict[str, str], fichero: str, fila: int) -> str:
    try:
        return index[fold(name.strip())]
    except KeyError:
        raise KitFormatError(f"{fichero} fila {fila + 2}: marca desconocida «{name}»") from None


def _fase(value: str, fichero: str, fila: int) -> FaseEmbudo:
    try:
        return FASES[fold(value.strip())]
    except KeyError:
        raise KitFormatError(
            f"{fichero} fila {fila + 2}: intención desconocida «{value}»"
        ) from None


# --- marcas.csv -----------------------------------------------------------------------------------


def _rol(nivel: str, rol: str) -> Rol:
    if nivel == "foco":
        return "foco"
    return "lider" if "lider real" in fold(rol) else "contexto"


def brands_from_frame(df: pd.DataFrame) -> list[Brand]:
    _require(df, MARCAS_COLS, "marcas.csv")
    return [
        _build(
            Brand,
            {
                "id": slugify(r["Marca"]),
                "nombre": r["Marca"].strip(),
                "aliases": _split(r["Alias"], "|"),
                "rol": _rol(r["Nivel"].strip(), r["Rol"]),
                "dominio": r["Dominio_propio"].strip() or None,
                "rol_detalle": r["Rol"].strip(),
            },
            "marcas.csv",
            i,
        )
        for i, r in enumerate(_rows(df))
    ]


def load_brands(path: str | Path) -> list[Brand]:
    return brands_from_frame(read_kit_csv(path))


# --- banco_prompts.csv ----------------------------------------------------------------------------


def prompt_bank_from_frame(df: pd.DataFrame) -> list[PromptTemplate]:
    _require(df, BANCO_COLS, "banco_prompts.csv")
    return [
        _build(
            PromptTemplate,
            {
                "id": r["Prompt_ID"].strip(),
                "familia": r["Familia"].strip(),
                "fase_embudo": _fase(r["Intención"], "banco_prompts.csv", i),
                "instanciacion": r["Instanciación"].strip(),
                "texto": r["Prompt (plantilla)"],
                "prioridad": r["Prioridad"].strip(),
                "uso": r["Uso"].strip(),
            },
            "banco_prompts.csv",
            i,
        )
        for i, r in enumerate(_rows(df))
    ]


def load_prompt_bank(path: str | Path) -> list[PromptTemplate]:
    return prompt_bank_from_frame(read_kit_csv(path))


# --- fuentes_catalogo.csv -------------------------------------------------------------------------


def sources_from_frame(df: pd.DataFrame) -> list[Source]:
    _require(df, FUENTES_COLS, "fuentes_catalogo.csv")
    return [
        _build(
            Source,
            {
                "dominio": r["Dominio"].strip(),
                "tipo": r["Tipo_de_fuente"].strip(),
                "calidad": float(r["Calidad_de_fuente_0_1"]),
            },
            "fuentes_catalogo.csv",
            i,
        )
        for i, r in enumerate(_rows(df))
    ]


def load_sources(path: str | Path) -> list[Source]:
    return sources_from_frame(read_kit_csv(path))


# --- ejecuciones.csv ------------------------------------------------------------------------------


def _instance_ids(df: pd.DataFrame) -> dict[tuple[str, str], str]:
    """(Prompt_ID, Prompt ejecutado) → id de instancia `<Prompt_ID>-NN`, en orden de aparición."""
    ids: dict[tuple[str, str], str] = {}
    per_template: dict[str, int] = {}
    for r in _rows(df):
        key = (r["Prompt_ID"].strip(), r["Prompt ejecutado"].strip())
        if key not in ids:
            per_template[key[0]] = per_template.get(key[0], 0) + 1
            ids[key] = f"{key[0]}-{per_template[key[0]]:02d}"
    return ids


def _fill_pattern(template: str) -> re.Pattern[str]:
    pattern = re.escape(template.strip())
    for placeholder, group in PLACEHOLDERS.items():
        pattern = pattern.replace(re.escape(placeholder), f"(?P<{group}>.+?)")
    return re.compile(f"^{pattern}$", re.DOTALL)


def prompt_instances_from_frame(
    df: pd.DataFrame, templates: list[PromptTemplate], brands: list[Brand]
) -> list[PromptInstance]:
    """Instancias únicas de `ejecuciones.csv`; extrae ciudad y marcas nombradas de la plantilla.

    `marca_nombrada` y `marca_nombrada_b` son ids de marca. `perfil` queda vacío: el kit no lo trae.
    """
    _require(df, EJECUCIONES_COLS, "ejecuciones.csv")
    by_id = {t.id: t for t in templates}
    index = _brand_index(brands)
    instances: list[PromptInstance] = []
    for i, ((template_id, texto), instance_id) in enumerate(_instance_ids(df).items()):
        tpl = by_id.get(template_id)
        if tpl is None:
            raise KitFormatError(f"ejecuciones.csv: Prompt_ID «{template_id}» no está en el banco")
        match = _fill_pattern(tpl.texto).match(texto)
        if match is None:
            raise KitFormatError(f"ejecuciones.csv: «{texto}» no encaja con la plantilla {tpl.id}")
        groups = match.groupdict()
        marcas = {
            k: _resolve(v, index, "ejecuciones.csv", i)
            for k, v in groups.items()
            if k.startswith("marca_")
        }
        instances.append(
            _build(
                PromptInstance,
                {
                    "id": instance_id,
                    "template_id": tpl.id,
                    "familia": tpl.familia,
                    "fase_embudo": tpl.fase_embudo,
                    "instanciacion": tpl.instanciacion,
                    "ciudad": groups.get("ciudad"),
                    "texto": texto,
                    "marca_nombrada": marcas.get("marca_a"),
                    "marca_nombrada_b": marcas.get("marca_b"),
                    "prioridad": tpl.prioridad,
                },
                "ejecuciones.csv",
                i,
            )
        )
    return instances


def runs_from_frame(df: pd.DataFrame, brands: list[Brand], sources: list[Source]) -> list[Run]:
    """Una `Run` por fila. Un dominio fuera del catálogo se conserva con tipo y calidad None."""
    _require(df, EJECUCIONES_COLS, "ejecuciones.csv")
    index = _brand_index(brands)
    catalog = {s.dominio: s for s in sources}
    instance_ids = _instance_ids(df)
    runs: list[Run] = []
    for i, r in enumerate(_rows(df)):
        dominios = _split(r["Fuentes citadas"], ",")
        runs.append(
            _build(
                Run,
                {
                    "id": r["Ejecucion_ID"].strip(),
                    "prompt_id": instance_ids[
                        (r["Prompt_ID"].strip(), r["Prompt ejecutado"].strip())
                    ],
                    "motor": r["Motor"].strip(),
                    "repeticion": int(r["Repetición"]),
                    "fecha": r["Fecha/hora"].strip(),
                    "texto_respuesta": r["Respuesta completa"],
                    "fuentes": [catalog.get(d, Source(dominio=d)) for d in dominios],
                    "marcas_a_evaluar": [
                        _resolve(m, index, "ejecuciones.csv", i)
                        for m in _split(r["Marcas a evaluar"], "|")
                    ],
                },
                "ejecuciones.csv",
                i,
            )
        )
    return runs


def load_prompt_instances(
    path: str | Path, templates: list[PromptTemplate], brands: list[Brand]
) -> list[PromptInstance]:
    return prompt_instances_from_frame(read_kit_csv(path), templates, brands)


def load_runs(path: str | Path, brands: list[Brand], sources: list[Source]) -> list[Run]:
    return runs_from_frame(read_kit_csv(path), brands, sources)


# --- muestra_evaluada.csv -------------------------------------------------------------------------


def evaluated_sample_from_frame(df: pd.DataFrame, brands: list[Brand]) -> list[Evaluation]:
    """Etiquetas humanas de la muestra como `Evaluation` (origen `humano`, confianza 1)."""
    _require(df, MUESTRA_COLS, "muestra_evaluada.csv")
    index = _brand_index(brands)
    evaluations: list[Evaluation] = []
    for i, r in enumerate(_rows(df)):
        run_id = r["Ejecucion_ID"].strip()
        brand_id = _resolve(r["Marca"], index, "muestra_evaluada.csv", i)
        tipo_fuente = r["Tipo de fuente"].strip() or None
        evaluations.append(
            _build(
                Evaluation,
                {
                    "id": f"{run_id}:{brand_id}",
                    "run_id": run_id,
                    "brand_id": brand_id,
                    "aparece": r["Aparece (1/0)"].strip() == "1",
                    "posicion": int(float(r["Posición"])) if r["Posición"].strip() else None,
                    "tipo_mencion": r["Tipo de mención"].strip() or None,
                    "fuerza": int(r["Fuerza recomendación (-1 a 3)"]),
                    "sentimiento": r["Sentimiento"].strip() or None,
                    "tipo_fuente": tipo_fuente,
                    "apoyada_en_fuente": tipo_fuente not in (None, "Sin fuente"),
                    "confianza": 1.0,
                    "origen": "humano",
                },
                "muestra_evaluada.csv",
                i,
            )
        )
    return evaluations


def load_evaluated_sample(path: str | Path, brands: list[Brand]) -> list[Evaluation]:
    return evaluated_sample_from_frame(read_kit_csv(path), brands)
