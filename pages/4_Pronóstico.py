import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from datetime import datetime, timedelta
from pathlib import Path
import io
import joblib
import json
import pickle

from kidia.state import init_state
from kidia.auth import logout
from kidia.ui import render_kidia_header

# =========================
# 0) CONFIG DE PÁGINA
# =========================
st.set_page_config(page_title="KIDIA | Pronóstico", layout="wide")
init_state()

if not st.session_state.get("authenticated", False):
    st.switch_page("app.py")

render_kidia_header()

# =========================
# CSS / ESTILOS
# =========================
st.markdown("""
<style>
    [data-testid="stSidebarNav"] ul li:first-child {
        display: none;
    }

    [data-testid="stSidebarNav"]::before {
        content: "Menú principal";
        display: block;
        font-size: 1.35rem;
        font-weight: 700;
        color: #1f2a44;
        margin: 0.5rem 0 1rem 0.3rem;
        padding-top: 0.5rem;
    }

    .sidebar-bottom-space {
        height: 55vh;
    }

    .block-container {
        max-width: 100% !important;
        padding-left: 2rem !important;
        padding-right: 2rem !important;
        padding-top: 1.2rem !important;
    }

    .data-title {
        margin-top: 0rem !important;
        margin-bottom: 0.3rem !important;
        text-align: center;
        font-size: 2.1rem;
        font-weight: 800;
        color: #1f2a44;
    }

    .data-subtitle {
        text-align: center;
        font-size: 1.05rem;
        font-weight: 600;
        color: #374151;
        margin-top: 0;
        margin-bottom: 1.5rem;
        letter-spacing: 0.2px;
        line-height: 1.4;
    }

    .patient-section {
        width: 100% !important;
        padding: 0.25rem 0 0.4rem 0 !important;
        margin-bottom: 0.8rem !important;
    }

    button[data-baseweb="tab"] p {
        font-size: 1.08rem !important;
        font-weight: 800 !important;
    }

    button[data-baseweb="tab"] {
        padding: 14px 18px !important;
        height: auto !important;
        flex: 1 1 0% !important;
        justify-content: center !important;
    }

    div[data-testid="stTabs"] [role="tablist"] {
        display: flex !important;
        width: 100% !important;
        justify-content: stretch !important;
        gap: 10px !important;
    }

    div[data-testid="stTabs"] [role="tab"] {
        flex: 1 1 0% !important;
    }

    button[data-baseweb="tab"][aria-selected="true"] {
        border-bottom: 3px solid #ef4444 !important;
    }
</style>
""", unsafe_allow_html=True)

# =========================
# SIDEBAR LIMPIO
# =========================
with st.sidebar:
    st.markdown('<div class="sidebar-bottom-space"></div>', unsafe_allow_html=True)

    if "confirm_logout" not in st.session_state:
        st.session_state.confirm_logout = False

    if not st.session_state.confirm_logout:
        if st.button("Cerrar sesión", use_container_width=True):
            st.session_state.confirm_logout = True
            st.rerun()
    else:
        st.warning("¿Seguro que deseas cerrar sesión?")

        c1, c2 = st.columns(2)
        with c1:
            if st.button("Sí, salir", use_container_width=True):
                st.session_state.confirm_logout = False
                logout()
                st.switch_page("app.py")

        with c2:
            if st.button("Cancelar", use_container_width=True):
                st.session_state.confirm_logout = False
                st.rerun()

# =========================
# 1) HELPERS PACIENTES / RUTAS
# =========================
try:
    BASE_DIR = Path(__file__).resolve().parents[1]
except Exception:
    BASE_DIR = Path.cwd()

BASE_UPLOADS = BASE_DIR / "data" / "uploads"
PATIENTS_CSV = BASE_DIR / "data" / "patients.csv"
MODELS_ROOT = BASE_DIR / "models"
XGB_ROOT = MODELS_ROOT / "XGBoost"
LSTM_ROOT = MODELS_ROOT / "LSTM"

RED_EVENT = "#e53935"
BLUE_PRED = "#1565c0"


def load_patients_master(csv_path: Path) -> pd.DataFrame:
    if not csv_path.exists():
        return pd.DataFrame(columns=["ID", "Nombre"])

    for enc in ["utf-8", "latin-1", "cp1252"]:
        try:
            df = pd.read_csv(csv_path, encoding=enc)
            df.columns = [c.strip() for c in df.columns]

            if "ID" not in df.columns:
                df["ID"] = ""
            if "Nombre" not in df.columns:
                df["Nombre"] = ""

            df["ID"] = df["ID"].astype(str).str.strip()
            df["Nombre"] = df["Nombre"].astype(str).str.strip()
            df = df[(df["ID"] != "")].copy()
            return df
        except Exception:
            continue

    return pd.DataFrame(columns=["ID", "Nombre"])


def get_registered_patients(base_path: Path, patients_csv_path: Path):
    patients = []
    df_master = load_patients_master(patients_csv_path)

    name_map = {}
    if not df_master.empty:
        name_map = dict(zip(df_master["ID"], df_master["Nombre"]))

    if not base_path.exists():
        return patients

    for folder in sorted(base_path.iterdir()):
        if folder.is_dir():
            folder_name = folder.name

            if folder_name.startswith("patient_"):
                patient_id = folder_name.replace("patient_", "").strip()
            else:
                patient_id = folder.name.strip()

            patient_name = name_map.get(patient_id, patient_id)

            patients.append({
                "folder_name": folder_name,
                "patient_id": patient_id,
                "patient_name": patient_name,
                "folder_path": str(folder),
            })

    return patients


def patient_label(p):
    return f"{p['patient_name']} ({p['patient_id']})"


def normalize_child_id(patient_id: str) -> str:
    text = str(patient_id).strip().lower()
    digits = "".join(ch for ch in text if ch.isdigit())
    if digits:
        return f"child{int(digits):02d}"
    return text


def confidence_label(conf: float) -> str:
    if conf >= 90:
        return "Alta"
    if conf >= 75:
        return "Media"
    return "Baja"


def infer_confidence_from_metrics(metrics: dict) -> float:
    if not isinstance(metrics, dict):
        return 0.0

    rec = metrics.get("recursive_1440") or metrics.get("rec_1440")
    if isinstance(rec, dict):
        if rec.get("R2") is not None:
            try:
                r2 = float(rec["R2"])
                return max(0.0, min(100.0, 50.0 + 50.0 * r2))
            except Exception:
                pass
        if rec.get("RMSE") is not None:
            try:
                rmse = float(rec["RMSE"])
                return max(0.0, min(100.0, 100.0 - (rmse / 2.5)))
            except Exception:
                pass

    t1 = metrics.get("t1") or metrics.get("metricas_t1") or metrics.get("metricas_test_globales_6h")
    if isinstance(t1, dict):
        if t1.get("R2") is not None:
            try:
                r2 = float(t1["R2"])
                return max(0.0, min(100.0, 50.0 + 50.0 * r2))
            except Exception:
                pass
        if t1.get("RMSE") is not None:
            try:
                rmse = float(t1["RMSE"])
                return max(0.0, min(100.0, 100.0 - (rmse / 2.5)))
            except Exception:
                pass

    return 0.0


def safe_float(v, default=np.inf):
    try:
        if v is None:
            return default
        return float(v)
    except Exception:
        return default


# =========================
# 2) CARGA DE MODELOS
# =========================
@st.cache_resource(show_spinner=False)
def load_xgb_artifacts(child_folder_name: str):
    model_dir = XGB_ROOT / child_folder_name
    model_path = model_dir / "model.pkl"
    features_path = model_dir / "features.pkl"
    config_path = model_dir / "config.pkl"

    if not (model_path.exists() and features_path.exists() and config_path.exists()):
        return None

    model = joblib.load(model_path)
    feature_cols = joblib.load(features_path)

    try:
        config = joblib.load(config_path)
    except Exception:
        with open(config_path, "rb") as f:
            config = pickle.load(f)

    return model, feature_cols, config, model_dir


@st.cache_resource(show_spinner=False)
def load_lstm_artifacts(child_folder_name: str):
    model_dir = LSTM_ROOT / child_folder_name
    model_path = model_dir / "model.keras"
    config_path = model_dir / "config_modelo.json"
    features_path = model_dir / "features.pkl"
    scaler_x_path = model_dir / "scaler_x.pkl"
    scaler_y_path = model_dir / "scaler_y.pkl"

    required = [model_path, config_path, features_path, scaler_x_path, scaler_y_path]
    if not all(p.exists() for p in required):
        return None

    try:
        from tensorflow.keras.models import load_model
    except Exception:
        return "tensorflow_missing"

    model = load_model(model_path)

    with open(config_path, "r", encoding="utf-8") as f:
        config = json.load(f)

    feature_cols = joblib.load(features_path)
    scaler_x = joblib.load(scaler_x_path)
    scaler_y = joblib.load(scaler_y_path)

    return model, feature_cols, config, scaler_x, scaler_y, model_dir


def extract_xgb_score(config: dict):
    if not isinstance(config, dict):
        return np.inf, {}

    rec_list = config.get("metricas_recursivas", [])
    rec_360 = None
    rec_1440 = None

    if isinstance(rec_list, list):
        for item in rec_list:
            h = int(item.get("horizonte_min", -1))
            if h == 360:
                rec_360 = item
            elif h == 1440:
                rec_1440 = item

    score = np.inf
    metrics_for_conf = {"metricas_t1": config.get("metricas_t1", {}), "recursive_1440": rec_1440}

    if isinstance(rec_360, dict) and rec_360.get("RMSE") is not None:
        score = safe_float(rec_360.get("RMSE"), np.inf)
    elif isinstance(rec_1440, dict) and rec_1440.get("RMSE") is not None:
        score = safe_float(rec_1440.get("RMSE"), np.inf)
    elif isinstance(config.get("metricas_t1"), dict):
        score = safe_float(config["metricas_t1"].get("RMSE"), np.inf)

    return score, metrics_for_conf


def extract_lstm_score(config: dict):
    if not isinstance(config, dict):
        return np.inf, {}

    global_6h = config.get("metricas_test_globales_6h", {})
    score = np.inf

    if isinstance(global_6h, dict):
        score = safe_float(global_6h.get("RMSE"), np.inf)

    metrics_for_conf = {
        "metricas_test_globales_6h": global_6h,
        "recursive_1440": None
    }
    return score, metrics_for_conf


def choose_best_model(child_id: str):
    xgb = load_xgb_artifacts(child_id)
    lstm = load_lstm_artifacts(child_id)

    candidates = []

    if xgb is not None:
        xgb_model, xgb_feature_cols, xgb_config, xgb_model_dir = xgb
        xgb_score, xgb_metrics = extract_xgb_score(xgb_config)
        candidates.append({
            "name": "xgboost",
            "score": xgb_score,
            "confidence_pct": infer_confidence_from_metrics(xgb_metrics),
            "artifacts": xgb,
            "status_text": f"Modelo XGBoost cargado desde: {xgb_model_dir}"
        })

    if lstm == "tensorflow_missing":
        pass
    elif lstm is not None:
        lstm_model, lstm_feature_cols, lstm_config, scaler_x, scaler_y, lstm_model_dir = lstm
        lstm_score, lstm_metrics = extract_lstm_score(lstm_config)
        candidates.append({
            "name": "lstm",
            "score": lstm_score,
            "confidence_pct": infer_confidence_from_metrics(lstm_metrics),
            "artifacts": lstm,
            "status_text": f"Modelo LSTM cargado desde: {lstm_model_dir}"
        })

    if not candidates:
        if lstm == "tensorflow_missing":
            return {
                "selected_model_type": "demo",
                "model_available": False,
                "confidence_pct": 0.0,
                "confidence_text": "Baja",
                "model_status_text": "TensorFlow no está instalado en este entorno para cargar LSTM."
            }
        return {
            "selected_model_type": "demo",
            "model_available": False,
            "confidence_pct": 0.0,
            "confidence_text": "Baja",
            "model_status_text": f"No se encontraron modelos válidos para {child_id}."
        }

    best = min(candidates, key=lambda x: x["score"])

    return {
        "selected_model_type": best["name"],
        "model_available": True,
        "confidence_pct": best["confidence_pct"],
        "confidence_text": confidence_label(best["confidence_pct"]),
        "model_status_text": best["status_text"],
        "artifacts": best["artifacts"],
        "selection_reason": f"Selección automática por menor RMSE histórico ({best['score']:.3f})."
    }


# =========================
# 3) TÍTULO
# =========================
st.markdown("""
<h2 class="data-title">
    📈 Pronóstico glucémico
</h2>
<p class="data-subtitle">
    Selecciona un paciente, utiliza la configuración manual registrada y genera el pronóstico del día siguiente.
</p>
""", unsafe_allow_html=True)

# =========================
# 4) SELECCIÓN DE PACIENTE
# =========================
patients = get_registered_patients(BASE_UPLOADS, PATIENTS_CSV)

if not patients:
    st.error("No se encontraron pacientes registrados en 'data/uploads'.")
    st.stop()

patients_df = pd.DataFrame(patients)

st.markdown('<div class="patient-section">', unsafe_allow_html=True)
st.markdown("### 👤 Selección de paciente")

f1, f2 = st.columns(2)

with f1:
    use_patient_id_filter = st.checkbox("Buscar por ID", key="forecast_use_patient_id_filter")
    patient_id_filter = st.text_input(
        "Filtrar por ID",
        placeholder="Ejemplo: CHILD_001",
        key="forecast_patient_id_filter",
        disabled=not use_patient_id_filter
    )

with f2:
    use_patient_name_filter = st.checkbox("Buscar por Nombre", key="forecast_use_patient_name_filter")
    patient_name_filter = st.text_input(
        "Filtrar por Nombre",
        placeholder="Ejemplo: Niño 1",
        key="forecast_patient_name_filter",
        disabled=not use_patient_name_filter
    )

patients_filtered = patients_df.copy()

if use_patient_id_filter and patient_id_filter.strip():
    term_id = patient_id_filter.strip().lower()
    patients_filtered = patients_filtered[
        patients_filtered["patient_id"].astype(str).str.lower().str.contains(term_id, na=False)
    ]

if use_patient_name_filter and patient_name_filter.strip():
    term_name = patient_name_filter.strip().lower()
    patients_filtered = patients_filtered[
        patients_filtered["patient_name"].astype(str).str.lower().str.contains(term_name, na=False)
    ]

patients_filtered = patients_filtered.reset_index(drop=True)

st.caption(f"Pacientes encontrados: {len(patients_filtered)}")

if patients_filtered.empty:
    st.warning("No se encontraron pacientes con los filtros seleccionados.")
    st.markdown('</div>', unsafe_allow_html=True)
    st.stop()

filtered_options = patients_filtered.to_dict(orient="records")

selected_patient = st.selectbox(
    "Selecciona el paciente para pronóstico",
    options=filtered_options,
    format_func=patient_label,
    key="forecast_selected_patient"
)

st.markdown('</div>', unsafe_allow_html=True)

pid = selected_patient["patient_id"]
nombre = selected_patient["patient_name"]
patient_folder = selected_patient["folder_path"]
child_id = normalize_child_id(pid)

st.markdown(
    f"""
    <div style="
        padding: 14px 16px;
        border-radius: 14px;
        background: rgba(46, 204, 113, 0.12);
        border: 1px solid rgba(46, 204, 113, 0.35);
        font-size: 18px;
        line-height: 1.35;
        margin-bottom: 14px;
    ">
        <div style="font-size: 20px; font-weight: 800;">
            🟢 Paciente activo: {nombre} <span style="font-weight:600; opacity:0.9;">(ID {pid})</span>
        </div>
        <div style="margin-top: 6px; font-size: 15px; opacity: 0.85;">
            Carpeta de modelo esperada: {child_id}
        </div>
    </div>
    """,
    unsafe_allow_html=True,
)

# =========================
# 5) CONFIGURACIÓN MANUAL
# =========================
manual_cfg = st.session_state.get("manual_prediction_config", {})
events = manual_cfg.get("events", []) if isinstance(manual_cfg, dict) else []

cfg_ok = (
    isinstance(manual_cfg, dict)
    and manual_cfg.get("patient_id") == pid
    and manual_cfg.get("current_glucose_mgdl") is not None
    and manual_cfg.get("horizon_minutes") is not None
)

if not cfg_ok:
    st.warning("No hay configuración manual completa para este paciente. Primero guarda los eventos en la página Ingestas.")
    st.stop()

patient_id_cfg = manual_cfg.get("patient_id")
patient_name_cfg = manual_cfg.get("patient_name", nombre)
reference_date = manual_cfg.get("reference_date")
start_time_str = manual_cfg.get("start_time", "00:00")
horizon_minutes = int(manual_cfg.get("horizon_minutes", 1440))
current_glucose = float(manual_cfg.get("current_glucose_mgdl", 120.0))

df_events = pd.DataFrame(events)
if not df_events.empty and "datetime" in df_events.columns:
    df_events["datetime"] = pd.to_datetime(df_events["datetime"], errors="coerce")
    df_events = df_events.sort_values("datetime").reset_index(drop=True)

# =========================
# 6) SELECCIÓN DE MODELO
# =========================
st.subheader("Modelo de pronóstico")

c_model_1, c_model_2, c_model_3 = st.columns([1.4, 1, 1])

with c_model_1:
    selected_model_type = st.selectbox(
        "Tipo de modelo",
        ["automatico", "xgboost", "lstm"],
        index=0,
        key="selected_forecast_model_type"
    )

xgb_artifacts = load_xgb_artifacts(child_id)
lstm_artifacts = load_lstm_artifacts(child_id)

model_available = False
confidence_pct = 0.0
confidence_text = "Baja"
model_status_text = ""
selection_reason = ""

if selected_model_type == "automatico":
    auto_info = choose_best_model(child_id)
    model_available = auto_info["model_available"]
    confidence_pct = auto_info["confidence_pct"]
    confidence_text = auto_info["confidence_text"]
    model_status_text = auto_info["model_status_text"]
    selection_reason = auto_info.get("selection_reason", "")
    selected_model_type_effective = auto_info["selected_model_type"]

    if model_available and selected_model_type_effective == "xgboost":
        xgb_model, xgb_feature_cols, xgb_config, xgb_model_dir = auto_info["artifacts"]
    elif model_available and selected_model_type_effective == "lstm":
        lstm_model, lstm_feature_cols, lstm_config, scaler_x, scaler_y, lstm_model_dir = auto_info["artifacts"]

elif selected_model_type == "xgboost":
    selected_model_type_effective = "xgboost"
    if xgb_artifacts is not None:
        xgb_model, xgb_feature_cols, xgb_config, xgb_model_dir = xgb_artifacts
        model_available = True

        _, metrics_xgb = extract_xgb_score(xgb_config)
        confidence_pct = infer_confidence_from_metrics(metrics_xgb)
        confidence_text = confidence_label(confidence_pct)
        model_status_text = f"Modelo XGBoost cargado desde: {xgb_model_dir}"
    else:
        model_status_text = f"No se encontró el modelo XGBoost para {child_id}."

elif selected_model_type == "lstm":
    selected_model_type_effective = "lstm"
    if lstm_artifacts == "tensorflow_missing":
        model_status_text = "TensorFlow no está instalado en este entorno para cargar LSTM."
    elif lstm_artifacts is not None:
        lstm_model, lstm_feature_cols, lstm_config, scaler_x, scaler_y, lstm_model_dir = lstm_artifacts
        model_available = True

        _, metrics_lstm = extract_lstm_score(lstm_config)
        confidence_pct = infer_confidence_from_metrics(metrics_lstm)
        confidence_text = confidence_label(confidence_pct)
        model_status_text = f"Modelo LSTM cargado desde: {lstm_model_dir}"
    else:
        model_status_text = f"No se encontró el modelo LSTM para {child_id}."
else:
    selected_model_type_effective = "demo"

with c_model_2:
    st.metric("Confianza estimada", f"{confidence_pct:,.1f}%")

with c_model_3:
    st.metric("Nivel", confidence_text)

if model_available:
    st.success(model_status_text)
    if selection_reason:
        st.info(selection_reason)
else:
    st.warning(model_status_text)

# =========================
# 7) RESUMEN SUPERIOR
# =========================
st.subheader("Resumen de configuración")

c1, c2, c3, c4, c5 = st.columns(5)
with c1:
    st.metric("Paciente", str(patient_name_cfg))
with c2:
    st.metric("Glucosa inicial", f"{current_glucose:,.1f} mg/dL")
with c3:
    st.metric("Horizonte", f"{horizon_minutes} min")
with c4:
    st.metric("Eventos", int(len(df_events)))
with c5:
    st.metric("Hora inicial", str(start_time_str))

total_cho_g = 0.0
total_bolus_u = 0.0
if not df_events.empty:
    if "cho_mg" in df_events.columns:
        total_cho_g = df_events["cho_mg"].fillna(0).sum() / 1000.0
    if "bolus_u" in df_events.columns:
        total_bolus_u = df_events["bolus_u"].fillna(0).sum()

m1, m2, m3 = st.columns(3)
with m1:
    st.metric("Total CHO", f"{total_cho_g:,.2f} g")
with m2:
    st.metric("Total bolo", f"{total_bolus_u:,.2f} U")
with m3:
    st.metric("Fecha referencia", str(reference_date))

st.divider()

# =========================
# 8) EVENTOS USADOS
# =========================
st.subheader("Eventos utilizados para el pronóstico")

if df_events.empty:
    st.info("No hay eventos cargados.")
else:
    df_show = df_events.copy()
    if "datetime" in df_show.columns:
        df_show["datetime"] = pd.to_datetime(df_show["datetime"]).dt.strftime("%Y-%m-%d %H:%M")

    cols_to_show = [c for c in ["hora", "cho_valor", "cho_unidad", "bolus_u", "nota", "datetime"] if c in df_show.columns]
    st.dataframe(df_show[cols_to_show], use_container_width=True)

st.divider()

# =========================
# 9) HELPERS DE SIMULACIÓN
# =========================
def parse_start_datetime(reference_date_str: str, start_time_str: str) -> datetime:
    d = pd.to_datetime(reference_date_str).date()
    t = datetime.strptime(start_time_str, "%H:%M").time()
    return datetime.combine(d, t)


def build_minute_schedules(events_df: pd.DataFrame, start_dt: datetime, horizon_min: int):
    food_schedule = np.zeros(horizon_min, dtype=float)
    insulin_schedule = np.zeros(horizon_min, dtype=float)

    if events_df.empty:
        return food_schedule, insulin_schedule

    tmp = events_df.copy()
    if "datetime" in tmp.columns:
        tmp["datetime"] = pd.to_datetime(tmp["datetime"], errors="coerce")

    for _, row in tmp.iterrows():
        dt_event = row.get("datetime")
        if pd.isna(dt_event):
            continue

        delta_min = int(round((dt_event - start_dt).total_seconds() / 60.0))
        if 0 <= delta_min < horizon_min:
            food_schedule[delta_min] += float(row.get("cho_mg", 0.0) or 0.0)
            insulin_schedule[delta_min] += float(row.get("bolus_u", 0.0) or 0.0)

    return food_schedule, insulin_schedule


def build_demo_forecast(glucose0: float, events_df: pd.DataFrame, start_dt: datetime, horizon_min: int) -> pd.DataFrame:
    n_steps = horizon_min
    future_times = [start_dt + timedelta(minutes=i) for i in range(n_steps)]
    y = np.full(n_steps, float(glucose0), dtype=float)

    if not events_df.empty:
        tmp = events_df.copy()
        if "datetime" in tmp.columns:
            tmp["datetime"] = pd.to_datetime(tmp["datetime"], errors="coerce")

        for _, row in tmp.iterrows():
            if pd.isna(row.get("datetime")):
                continue

            cho_g = float(row.get("cho_mg", 0.0) or 0.0) / 1000.0
            bolus_u = float(row.get("bolus_u", 0.0) or 0.0)

            event_idx = int(round((row["datetime"] - start_dt).total_seconds() / 60.0))
            if event_idx < 0 or event_idx >= n_steps:
                continue

            cho_peak = cho_g * 1.8
            for k in range(event_idx, min(n_steps, event_idx + 180)):
                delay = k - event_idx
                cho_effect = cho_peak * np.exp(-((delay - 45) ** 2) / 1200.0)
                y[k] += cho_effect

            bolus_drop = bolus_u * 8.0
            for k in range(event_idx, min(n_steps, event_idx + 240)):
                delay = k - event_idx
                insulin_effect = bolus_drop * np.exp(-((delay - 60) ** 2) / 1800.0)
                y[k] -= insulin_effect

    y = pd.Series(y).rolling(window=5, min_periods=1, center=True).mean().values
    y = np.clip(y, 40, 400)

    return pd.DataFrame({
        "datetime_pred": future_times,
        "glucose_pred": y
    })


def build_xgb_feature_row(
    history_glucose,
    history_food,
    history_insulin,
    t_abs,
    feature_cols,
    lags_glucose,
    lags_food,
    lags_insulin,
    rolling_glucose,
    rolling_food,
    rolling_insulin
):
    row = {}

    hour = (t_abs % 1440) // 60
    row["hour"] = hour
    row["hour_sin"] = np.sin(2 * np.pi * hour / 24)
    row["hour_cos"] = np.cos(2 * np.pi * hour / 24)

    for lag in lags_glucose:
        row[f"glucose_lag_{lag}"] = history_glucose[-lag]

    for lag in lags_food:
        if lag == 0:
            row["food_now"] = history_food[-1]
        else:
            row[f"food_lag_{lag}"] = history_food[-lag]

    for lag in lags_insulin:
        if lag == 0:
            row["insulin_now"] = history_insulin[-1]
        else:
            row[f"insulin_lag_{lag}"] = history_insulin[-lag]

    for w in rolling_glucose:
        row[f"glucose_roll_mean_{w}"] = np.mean(history_glucose[-w:])

    for w in rolling_food:
        row[f"food_roll_sum_{w}"] = np.sum(history_food[-w:])

    for w in rolling_insulin:
        row[f"insulin_roll_sum_{w}"] = np.sum(history_insulin[-w:])

    return pd.DataFrame([row])[feature_cols]


def simulate_xgboost_1440(
    model,
    feature_cols,
    config,
    glucose0,
    start_dt,
    events_df,
    horizon_min
):
    lags_glucose = config["lags_glucose"]
    lags_food = config["lags_food"]
    lags_insulin = config["lags_insulin"]
    rolling_glucose = config["rolling_glucose"]
    rolling_food = config["rolling_food"]
    rolling_insulin = config["rolling_insulin"]

    warmup = max(max(lags_glucose), max(lags_food), max(lags_insulin), 60)

    history_glucose = [float(glucose0)] * warmup
    history_food = [0.0] * warmup
    history_insulin = [0.0] * warmup

    food_schedule, insulin_schedule = build_minute_schedules(events_df, start_dt, horizon_min)

    preds = []
    future_times = []

    for step in range(horizon_min):
        food_now = float(food_schedule[step])
        insulin_now = float(insulin_schedule[step])

        history_food.append(food_now)
        history_insulin.append(insulin_now)

        x_row = build_xgb_feature_row(
            history_glucose=history_glucose,
            history_food=history_food,
            history_insulin=history_insulin,
            t_abs=step,
            feature_cols=feature_cols,
            lags_glucose=lags_glucose,
            lags_food=lags_food,
            lags_insulin=lags_insulin,
            rolling_glucose=rolling_glucose,
            rolling_food=rolling_food,
            rolling_insulin=rolling_insulin
        )

        pred = model.predict(x_row)[0]
        pred = float(np.clip(pred, 40, 400))

        preds.append(pred)
        history_glucose.append(pred)
        future_times.append(start_dt + timedelta(minutes=step))

    preds = pd.Series(preds).rolling(window=5, min_periods=1, center=True).mean().values

    return pd.DataFrame({
        "datetime_pred": future_times,
        "glucose_pred": preds
    })


def make_lstm_feature_frame(glucose_arr, food_arr, insulin_arr, start_minute_index):
    n = len(glucose_arr)
    minute_idx = np.arange(start_minute_index, start_minute_index + n)
    hour = (minute_idx % 1440) // 60

    return pd.DataFrame({
        "glucosa (mg/dL)": glucose_arr,
        "ingesta_total_CHO (mg)": food_arr,
        "insulina_bolo (U)": insulin_arr,
        "hour_sin": np.sin(2 * np.pi * hour / 24),
        "hour_cos": np.cos(2 * np.pi * hour / 24)
    })


def smooth_block_join(prev_block, current_block, transition_len=30):
    if prev_block is None or len(prev_block) == 0 or len(current_block) == 0:
        return current_block

    current_block = current_block.copy()
    prev_last = float(prev_block[-1])
    curr_first = float(current_block[0])
    jump = curr_first - prev_last

    current_block = current_block - jump

    k = min(transition_len, len(current_block))
    if k > 1:
        weights = np.linspace(1.0, 0.0, k)
        current_block[:k] = current_block[:k] * (1 - weights) + (prev_last * weights)

    return np.clip(current_block, 40, 400)


def simulate_lstm_24h(
    model,
    feature_cols,
    config,
    scaler_x,
    scaler_y,
    glucose0,
    start_dt,
    events_df,
    horizon_min
):
    input_window = int(config.get("input_window", 360))
    output_window = int(config.get("output_window", 360))

    n_blocks = int(np.ceil(horizon_min / output_window))
    current_glucose_window = np.full(input_window, float(glucose0), dtype=float)

    total_future_needed = n_blocks * output_window
    food_future, insulin_future = build_minute_schedules(events_df, start_dt, total_future_needed)

    preds_all = []
    prev_block = None

    for b in range(n_blocks):
        block_start = b * output_window

        if block_start == 0:
            food_input = np.zeros(input_window, dtype=float)
            insulin_input = np.zeros(input_window, dtype=float)
        else:
            prev_start = max(0, block_start - input_window)
            food_prev = food_future[prev_start:block_start]
            insulin_prev = insulin_future[prev_start:block_start]

            food_input = np.zeros(input_window, dtype=float)
            insulin_input = np.zeros(input_window, dtype=float)

            food_input[-len(food_prev):] = food_prev
            insulin_input[-len(insulin_prev):] = insulin_prev

        x_df = make_lstm_feature_frame(
            glucose_arr=current_glucose_window,
            food_arr=food_input,
            insulin_arr=insulin_input,
            start_minute_index=block_start - input_window
        )

        x_df = x_df[feature_cols]
        x_scaled = scaler_x.transform(x_df)
        x_scaled = x_scaled.reshape(1, input_window, len(feature_cols))

        pred_scaled = model.predict(x_scaled, verbose=0)[0]
        pred_block = scaler_y.inverse_transform(pred_scaled.reshape(-1, 1)).flatten()
        pred_block = np.clip(pred_block, 40, 400)

        pred_block = smooth_block_join(prev_block, pred_block, transition_len=30)

        preds_all.append(pred_block)
        prev_block = pred_block.copy()
        current_glucose_window = pred_block.copy()

    pred_full = np.concatenate(preds_all)[:horizon_min]
    pred_full = pd.Series(pred_full).rolling(window=7, min_periods=1, center=True).mean().values
    pred_full = np.clip(pred_full, 40, 400)

    future_times = [start_dt + timedelta(minutes=i) for i in range(horizon_min)]

    return pd.DataFrame({
        "datetime_pred": future_times,
        "glucose_pred": pred_full
    })


# =========================
# 10) PREDICCIÓN
# =========================
st.subheader("Generación del pronóstico")

start_dt = parse_start_datetime(reference_date, start_time_str)

with st.spinner("Generando pronóstico..."):
    if not model_available:
        forecast_df = build_demo_forecast(
            glucose0=current_glucose,
            events_df=df_events,
            start_dt=start_dt,
            horizon_min=horizon_minutes
        )
        model_used_name = "Demo / Sin modelo disponible"
        model_used_type = "demo"

    elif selected_model_type_effective == "xgboost":
        forecast_df = simulate_xgboost_1440(
            model=xgb_model,
            feature_cols=xgb_feature_cols,
            config=xgb_config,
            glucose0=current_glucose,
            start_dt=start_dt,
            events_df=df_events,
            horizon_min=horizon_minutes
        )
        model_used_name = f"XGBoost - {child_id}"
        model_used_type = "xgboost"

    elif selected_model_type_effective == "lstm":
        forecast_df = simulate_lstm_24h(
            model=lstm_model,
            feature_cols=lstm_feature_cols,
            config=lstm_config,
            scaler_x=scaler_x,
            scaler_y=scaler_y,
            glucose0=current_glucose,
            start_dt=start_dt,
            events_df=df_events,
            horizon_min=horizon_minutes
        )
        model_used_name = f"LSTM - {child_id}"
        model_used_type = "lstm"

    else:
        forecast_df = build_demo_forecast(
            glucose0=current_glucose,
            events_df=df_events,
            start_dt=start_dt,
            horizon_min=horizon_minutes
        )
        model_used_name = "Demo"
        model_used_type = "demo"

# =========================
# 11) MÉTRICAS DE RESULTADO
# =========================
pred_min = float(forecast_df["glucose_pred"].min())
pred_max = float(forecast_df["glucose_pred"].max())
pred_mean = float(forecast_df["glucose_pred"].mean())
pred_final = float(forecast_df["glucose_pred"].iloc[-1])

k1, k2, k3, k4, k5 = st.columns(5)
with k1:
    st.metric("Glucosa mínima estimada", f"{pred_min:,.1f} mg/dL")
with k2:
    st.metric("Glucosa máxima estimada", f"{pred_max:,.1f} mg/dL")
with k3:
    st.metric("Promedio estimado", f"{pred_mean:,.1f} mg/dL")
with k4:
    st.metric("Valor final estimado", f"{pred_final:,.1f} mg/dL")
with k5:
    st.metric("Confianza estimada", f"{confidence_pct:,.1f}%")

msg = "Pronóstico en rango esperado."
if pred_min < 70:
    msg = "Posible riesgo de hipoglucemia en el horizonte pronosticado."
elif pred_max > 180:
    msg = "Posible riesgo de hiperglucemia en el horizonte pronosticado."

st.markdown(
    f"""
    <div style="
        padding: 12px 16px;
        border-radius: 12px;
        background: rgba(52, 152, 219, 0.08);
        border: 1px solid rgba(52, 152, 219, 0.25);
        margin-bottom: 14px;
    ">
        <b>Modelo utilizado:</b> {model_used_name}<br>
        <b>Tipo:</b> {model_used_type}<br>
        <b>Interpretación rápida:</b> {msg}<br>
        <b>Confianza estimada del pronóstico:</b> {confidence_pct:,.1f}% ({confidence_text})
    </div>
    """,
    unsafe_allow_html=True,
)

# =========================
# 12) GRÁFICA PRINCIPAL
# =========================
fig = go.Figure()

fig.add_hrect(y0=0, y1=70, fillcolor="rgba(255, 0, 0, 0.10)", line_width=0, layer="below")
fig.add_hrect(y0=70, y1=180, fillcolor="rgba(0, 200, 83, 0.10)", line_width=0, layer="below")
fig.add_hrect(y0=180, y1=400, fillcolor="rgba(255, 152, 0, 0.10)", line_width=0, layer="below")
fig.add_hline(y=70, opacity=0.6)
fig.add_hline(y=180, opacity=0.6)

fig.add_trace(go.Scatter(
    x=forecast_df["datetime_pred"],
    y=forecast_df["glucose_pred"],
    mode="lines",
    name="Pronóstico de glucosa",
    line=dict(color=BLUE_PRED, width=2.5)
))

if not df_events.empty and "datetime" in df_events.columns:
    events_plot = df_events.copy()
    events_plot["datetime"] = pd.to_datetime(events_plot["datetime"], errors="coerce")
    events_plot = events_plot.dropna(subset=["datetime"])

    if not events_plot.empty:
        hover_texts = []
        marker_sizes = []

        for _, r in events_plot.iterrows():
            cho_g = float(r.get("cho_mg", 0.0) or 0.0) / 1000.0
            bolus_u = float(r.get("bolus_u", 0.0) or 0.0)
            hover_texts.append(f"CHO: {cho_g:.1f} g<br>Bolo: {bolus_u:.1f} U")
            marker_sizes.append(9 if cho_g > 0 else 7)

        fig.add_trace(go.Scatter(
            x=events_plot["datetime"],
            y=[current_glucose] * len(events_plot),
            mode="markers",
            name="Ingestas / eventos",
            text=hover_texts,
            hovertemplate="%{x}<br>%{text}<extra></extra>",
            marker=dict(
                color=RED_EVENT,
                size=marker_sizes,
                line=dict(color="#b71c1c", width=1)
            )
        ))

fig.update_layout(
    title=f"Pronóstico de glucosa | Modelo: {model_used_name}",
    xaxis_title="Tiempo",
    yaxis_title="Glucosa estimada (mg/dL)",
    height=520,
    xaxis=dict(tickformat="%d-%m-%Y\n%H:%M"),
    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
)

st.plotly_chart(fig, use_container_width=True)

# =========================
# 13) TABLA Y EXPORTACIÓN CSV
# =========================
st.subheader("Resultados exportables")

forecast_export = forecast_df.copy()
forecast_export["patient_id"] = pid
forecast_export["patient_name"] = patient_name_cfg
forecast_export["model_used"] = model_used_name
forecast_export["model_type"] = model_used_type
forecast_export["confidence_pct"] = round(confidence_pct, 2)

with st.expander("Ver tabla del pronóstico"):
    df_show_export = forecast_export.copy()
    df_show_export["datetime_pred"] = pd.to_datetime(df_show_export["datetime_pred"]).dt.strftime("%Y-%m-%d %H:%M")
    st.dataframe(df_show_export, use_container_width=True)

csv_buffer = io.StringIO()
forecast_export.to_csv(csv_buffer, index=False)
csv_bytes = csv_buffer.getvalue().encode("utf-8")

st.download_button(
    label="📥 Descargar CSV del pronóstico",
    data=csv_bytes,
    file_name=f"forecast_{pid}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
    mime="text/csv",
    use_container_width=True
)

# =========================
# 14) BOTONES FINALES
# =========================
st.markdown("---")
b1, b2, b3 = st.columns(3)

with b1:
    if st.button("⬅ Volver a Ingestas", use_container_width=True):
        st.switch_page("pages/3_Ingestas.py")

with b2:
    if st.button("🔄 Recalcular pronóstico", use_container_width=True):
        st.rerun()

with b3:
    if st.button("📂 Volver a carga de datos", use_container_width=True):
        st.switch_page("pages/2_Carga_de_datos.py")