import re
import unicodedata
import pandas as pd

# Columnas estándar internas de KIDIA
STANDARD = {
    "time": ["datetime", "timestamp", "time", "date"],
    "glucose": ["glucose", "glucosa", "historialdeglucosa", "historialglucosa"],
    "carbs": ["carbs", "cho", "ingesta", "ingestacho", "ingestatotalcho", "carbohidratos"],
    "bolus": ["bolus", "insulinabolo", "insulina_bolo", "insulinabolo(u)", "bolo"],
    "basal": ["basal", "insulinabasal", "basalinsulin"],
    "iob": ["iob", "insulinaactiva", "insulinaactiva_iob", "insulinaactiva"],
}

# sinónimos MUY comunes (FreeStyle + tus datasets)
ALIASES = {
    # tiempo
    "marca de hora del dispositivo": "time",
    "marca de hora del sensor": "time",
    "marca de hora": "time",
    "datetime": "time",
    "timestamp": "time",
    "time": "time",
    "date": "time",

    # glucosa
    "glucosa (mg/dl)": "glucose",
    "glucosa mg/dl": "glucose",
    "historial de glucosa mg/dl": "glucose",
    "historial de glucosa": "glucose",
    "glucose": "glucose",

    # cho / carbs
    "ingesta_cho (mg)": "carbs",
    "ingesta_total_cho (mg)": "carbs",
    "carbs": "carbs",
    "cho": "carbs",

    # insulina
    "insulina_bolo (u)": "bolus",
    "bolo": "bolus",
    "bolus": "bolus",

    "insulina_activa_iob (u)": "iob",
    "iob": "iob",
}

def _norm(s: str) -> str:
    """Minúsculas, sin acentos, sin símbolos raros, colapsa espacios."""
    s = s.strip().lower()
    s = "".join(ch for ch in unicodedata.normalize("NFKD", s) if not unicodedata.combining(ch))
    s = re.sub(r"[^\w\s]", " ", s)      # quita símbolos ((), /, etc)
    s = re.sub(r"\s+", " ", s).strip()  # espacios
    return s

def standardize_columns(df: pd.DataFrame):
    """
    Renombra columnas hacia el esquema estándar:
    time, glucose, carbs, bolus, basal, iob
    Devuelve: df_renamed, report(dict)
    """
    original_cols = list(df.columns)
    norm_cols = [_norm(c) for c in original_cols]

    rename_map = {}

    # 1) Primero por ALIASES exactos normalizados
    for orig, n in zip(original_cols, norm_cols):
        if n in { _norm(k): v for k,v in ALIASES.items() }:
            # buscar el key original equivalente
            for k, v in ALIASES.items():
                if _norm(k) == n:
                    rename_map[orig] = v
                    break

    # 2) Luego por búsqueda “contiene” con STANDARD (heurística)
    for orig, n in zip(original_cols, norm_cols):
        if orig in rename_map:
            continue
        for target, keys in STANDARD.items():
            for k in keys:
                if k in n.replace(" ", "") or k in n:
                    # OJO: time/glucose deben ser únicos. Si ya existe, no sobrescribas.
                    if target in rename_map.values():
                        continue
                    rename_map[orig] = target
                    break
            if orig in rename_map:
                break

    df2 = df.rename(columns=rename_map).copy()

    report = {
        "original_cols": original_cols,
        "normalized_cols": norm_cols,
        "rename_map": rename_map,
        "final_cols": list(df2.columns),
        "has_time": "time" in df2.columns,
        "has_glucose": "glucose" in df2.columns,
        "extras": [c for c in df2.columns if c not in ["time","glucose","carbs","bolus","basal","iob"]],
    }
    return df2, report

def detect_mode(df_std: pd.DataFrame):
    """
    Devuelve:
      mode: 'univariate' o 'multivariate'
      features: lista de features extra detectadas
    """
    has_glucose = "glucose" in df_std.columns
    if not has_glucose:
        return "unknown", []

    candidates = [c for c in ["carbs","bolus","basal","iob"] if c in df_std.columns]
    mode = "multivariate" if len(candidates) > 0 else "univariate"
    return mode, candidates
