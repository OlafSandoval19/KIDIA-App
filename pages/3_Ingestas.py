import streamlit as st
import pandas as pd
from datetime import datetime, date, time
from pathlib import Path
import json

from kidia.state import init_state
from kidia.auth import logout
from kidia.ui import render_kidia_header

# =========================
# 0) CONFIG DE PÁGINA
# =========================
st.set_page_config(page_title="KIDIA | Ingestas manuales", layout="wide")
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
# HELPERS DE RUTA
# =========================
try:
    BASE_DIR = Path(__file__).resolve().parents[1]
except Exception:
    BASE_DIR = Path.cwd()

BASE_UPLOADS = BASE_DIR / "data" / "uploads"
PATIENTS_CSV = BASE_DIR / "data" / "patients.csv"
MANUAL_EVENTS_ROOT = BASE_DIR / "data" / "manual_events"
MANUAL_EVENTS_ROOT.mkdir(parents=True, exist_ok=True)

# =========================
# HELPERS DE PACIENTES
# =========================
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
            df = df[df["ID"] != ""].copy()
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
                patient_id = folder_name.strip()

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

# =========================
# HELPERS DE EVENTOS
# =========================
def get_manual_patient_dir(patient_id: str) -> Path:
    pdir = MANUAL_EVENTS_ROOT / f"patient_{patient_id}"
    pdir.mkdir(parents=True, exist_ok=True)
    return pdir


def get_events_csv_path(patient_id: str) -> Path:
    return get_manual_patient_dir(patient_id) / "eventos_manuales.csv"


def get_config_json_path(patient_id: str) -> Path:
    return get_manual_patient_dir(patient_id) / "config_pronostico.json"


def load_saved_events(patient_id: str):
    csv_path = get_events_csv_path(patient_id)
    if not csv_path.exists():
        return []

    try:
        df = pd.read_csv(csv_path)
        if df.empty:
            return []

        expected_cols = [
            "tipo", "fecha", "hora", "datetime",
            "cho_valor", "cho_unidad", "cho_mg",
            "bolus_u", "nota"
        ]
        for col in expected_cols:
            if col not in df.columns:
                df[col] = ""

        return df.to_dict(orient="records")
    except Exception:
        return []


def save_events_csv(patient_id: str, events: list):
    csv_path = get_events_csv_path(patient_id)

    ordered_cols = [
        "tipo", "fecha", "hora", "datetime",
        "cho_valor", "cho_unidad", "cho_mg",
        "bolus_u", "nota"
    ]

    if not events:
        pd.DataFrame(columns=ordered_cols).to_csv(csv_path, index=False, encoding="utf-8-sig")
        return csv_path

    df = pd.DataFrame(events).copy()
    for col in ordered_cols:
        if col not in df.columns:
            df[col] = ""

    df = df[ordered_cols]
    df.to_csv(csv_path, index=False, encoding="utf-8-sig")
    return csv_path


def save_prediction_config_json(patient_id: str, config: dict):
    json_path = get_config_json_path(patient_id)
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(config, f, ensure_ascii=False, indent=2)
    return json_path


def save_all_manual_data(patient_id: str, patient_name: str, patient_folder: str,
                         pred_date, start_time_value, glucose_now, entries: list):
    csv_path = save_events_csv(patient_id, entries)

    df_entries = pd.DataFrame(entries) if entries else pd.DataFrame()
    config_payload = {
        "patient_id": patient_id,
        "patient_name": patient_name,
        "patient_folder": patient_folder,
        "reference_date": str(pred_date),
        "start_time": start_time_value.strftime("%H:%M"),
        "horizon_minutes": 1440,
        "current_glucose_mgdl": float(glucose_now),
        "events_csv_path": str(csv_path),
        "events": df_entries.to_dict(orient="records") if not df_entries.empty else [],
    }

    json_path = save_prediction_config_json(patient_id, config_payload)
    st.session_state.manual_prediction_config = config_payload
    return csv_path, json_path, config_payload

def sync_manual_data_after_edit(patient_id: str, patient_name: str, patient_folder: str,
                                pred_date, start_time_value, glucose_now, entries: list):
    csv_path, json_path, config_payload = save_all_manual_data(
        patient_id=patient_id,
        patient_name=patient_name,
        patient_folder=patient_folder,
        pred_date=pred_date,
        start_time_value=start_time_value,
        glucose_now=glucose_now,
        entries=entries
    )
    st.session_state.manual_prediction_config = config_payload
    return csv_path, json_path

# =========================
# STATE LOCAL
# =========================
if "manual_entries_by_patient" not in st.session_state:
    st.session_state.manual_entries_by_patient = {}

if "manual_prediction_config" not in st.session_state:
    st.session_state.manual_prediction_config = {}

if "manual_loaded_patients" not in st.session_state:
    st.session_state.manual_loaded_patients = set()

# =========================
# TÍTULO
# =========================
st.markdown("""
<h2 class="data-title">
    💉 Ingestas manuales 🍽️
</h2>
<p class="data-subtitle">
    Selecciona un paciente, registra ingestas e insulina y explora los eventos capturados para el pronóstico.
</p>
""", unsafe_allow_html=True)

# =========================
# 1) PACIENTES REGISTRADOS
# =========================
patients = get_registered_patients(BASE_UPLOADS, PATIENTS_CSV)

if not patients:
    st.error("No se encontraron pacientes registrados en 'data/uploads'.")
    st.stop()

patients_df = pd.DataFrame(patients)

# =========================
# 2) SELECCIÓN DE PACIENTE
# =========================
st.markdown('<div class="patient-section">', unsafe_allow_html=True)
st.markdown("### 👤 Selección de paciente")

f1, f2 = st.columns(2)

with f1:
    use_patient_id_filter = st.checkbox("Buscar por ID", key="manual_use_patient_id_filter")
    patient_id_filter = st.text_input(
        "Filtrar por ID",
        placeholder="Ejemplo: CHILD_001",
        key="manual_patient_id_filter",
        disabled=not use_patient_id_filter
    )

with f2:
    use_patient_name_filter = st.checkbox("Buscar por Nombre", key="manual_use_patient_name_filter")
    patient_name_filter = st.text_input(
        "Filtrar por Nombre",
        placeholder="Ejemplo: Niño 1",
        key="manual_patient_name_filter",
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
    "Selecciona el paciente registrado",
    options=filtered_options,
    format_func=patient_label,
    key="manual_selected_registered_patient"
)

st.markdown('</div>', unsafe_allow_html=True)

patient_id = selected_patient["patient_id"]
patient_name = selected_patient["patient_name"]
patient_folder = selected_patient["folder_path"]
patient_key = str(patient_id)

# =========================
# CARGA AUTOMÁTICA DE EVENTOS GUARDADOS
# =========================
if patient_key not in st.session_state.manual_entries_by_patient:
    st.session_state.manual_entries_by_patient[patient_key] = []

if patient_key not in st.session_state.manual_loaded_patients:
    saved_events = load_saved_events(patient_key)
    st.session_state.manual_entries_by_patient[patient_key] = saved_events
    st.session_state.manual_loaded_patients.add(patient_key)

# =========================
# BOX DE PACIENTE ACTIVO
# =========================
events_csv_path = get_events_csv_path(patient_key)

st.markdown(
    f"""
    <div style="
        padding: 14px 16px;
        border-radius: 14px;
        background: rgba(46, 204, 113, 0.12);
        border: 1px solid rgba(46, 204, 113, 0.35);
        font-size: 18px;
        line-height: 1.35;
        margin-bottom: 18px;
    ">
        <div style="font-size: 20px; font-weight: 800;">
            🟢 Paciente activo: {patient_name} <span style="font-weight:600; opacity:0.9;">(ID {patient_id})</span>
        </div>
        <div style="margin-top: 6px; font-size: 15px; opacity: 0.85;">
            Paciente listo para registrar eventos manuales y configurar el pronóstico.
        </div>
        <div style="margin-top: 6px; font-size: 14px; opacity: 0.8;">
            Carpeta de guardado: {events_csv_path.parent}
        </div>
    </div>
    """,
    unsafe_allow_html=True,
)

# =========================
# 3) TABS
# =========================
tab1, tab2, tab3, tab4 = st.tabs([
    "👤 Paciente",
    "⚙️ Configuración",
    "📋 Eventos",
    "💾 Guardar eventos"
])

# =========================
# TAB 1: PACIENTE
# =========================
with tab1:
    st.subheader("Paciente registrado")
    st.info("El paciente se obtiene del registro en el apartado GESTIÓN DE PACIENTES.")

    c1, c2 = st.columns(2)
    with c1:
        st.write(f"**Nombre:** {patient_name}")
    with c2:
        st.write(f"**ID:** {patient_id}")

# =========================
# TAB 2: CONFIGURACIÓN
# =========================
with tab2:
    st.subheader("Configuración general de predicción")

    saved_config_path = get_config_json_path(patient_key)

    default_date = date.today()
    default_start_time = time(0, 0)
    default_glucose = 120.0

    if saved_config_path.exists():
        try:
            with open(saved_config_path, "r", encoding="utf-8") as f:
                cfg_saved = json.load(f)

            if "reference_date" in cfg_saved:
                default_date = datetime.strptime(cfg_saved["reference_date"], "%Y-%m-%d").date()

            if "start_time" in cfg_saved:
                default_start_time = datetime.strptime(cfg_saved["start_time"], "%H:%M").time()

            if "current_glucose_mgdl" in cfg_saved:
                default_glucose = float(cfg_saved["current_glucose_mgdl"])
        except Exception:
            pass

    c1, c2, c3, c4 = st.columns(4)

    with c1:
        pred_date = st.date_input(
            "Fecha de referencia",
            value=default_date,
            key=f"manual_pred_date_{patient_key}"
        )

    with c2:
        start_time_value = st.time_input(
            "Hora inicial de simulación",
            value=default_start_time,
            key=f"manual_start_time_{patient_key}"
        )

    with c3:
        horizon_minutes = 1440
        st.metric("Horizonte", f"{horizon_minutes} min")

    with c4:
        glucose_now = st.number_input(
            "Glucosa inicial (mg/dL)",
            min_value=0.0,
            max_value=600.0,
            value=float(default_glucose),
            step=1.0,
            key=f"manual_current_glucose_{patient_key}"
        )

# =========================
# TAB 3: EVENTOS
# =========================
with tab3:
    st.subheader("Gestión de eventos")
    st.markdown("### ➕ Agregar evento de comida + insulina")

    c1, c2, c3 = st.columns(3)

    with c1:
        meal_time = st.time_input(
            "Hora del evento",
            value=time(8, 0),
            key=f"meal_time_{patient_key}"
        )

    with c2:
        cho_amount = st.number_input(
            "Carbohidratos",
            min_value=0.0,
            max_value=1000.0,
            value=0.0,
            step=1.0,
            key=f"meal_cho_amount_{patient_key}"
        )

    with c3:
        cho_unit = st.selectbox(
            "Unidad CHO",
            ["g", "mg"],
            index=0,
            key=f"meal_cho_unit_{patient_key}"
        )

    c4, c5 = st.columns(2)

    with c4:
        bolus_amount = st.number_input(
            "Dosis de insulina (U)",
            min_value=0.0,
            max_value=100.0,
            value=0.0,
            step=0.1,
            key=f"meal_bolus_amount_{patient_key}"
        )

    with c5:
        meal_note = st.text_input(
            "Nota opcional",
            placeholder="Ej. desayuno, comida, colación, corrección...",
            key=f"meal_note_{patient_key}"
        )

    if st.button("➕ Agregar evento prandial", type="primary", use_container_width=True, key=f"add_event_{patient_key}"):
        if cho_amount <= 0 and bolus_amount <= 0:
            st.warning("Introduce al menos carbohidratos o una dosis de insulina.")
        else:
            event_dt = datetime.combine(pred_date, meal_time)
            cho_value_mg = cho_amount * 1000.0 if cho_unit == "g" else cho_amount

            st.session_state.manual_entries_by_patient[patient_key].append({
                "tipo": "Evento prandial",
                "fecha": pred_date.strftime("%Y-%m-%d"),
                "hora": meal_time.strftime("%H:%M"),
                "datetime": event_dt.strftime("%Y-%m-%d %H:%M:%S"),
                "cho_valor": float(cho_amount),
                "cho_unidad": cho_unit,
                "cho_mg": float(cho_value_mg) if cho_amount > 0 else 0.0,
                "bolus_u": float(bolus_amount),
                "nota": meal_note.strip(),
            })

            sync_manual_data_after_edit(
                patient_id=patient_key,
                patient_name=patient_name,
                patient_folder=patient_folder,
                pred_date=pred_date,
                start_time_value=start_time_value,
                glucose_now=glucose_now,
                entries=st.session_state.manual_entries_by_patient[patient_key]
            )

            st.success("Evento agregado y guardado correctamente.")
            st.rerun()

    st.divider()
    st.markdown("### 📋 Eventos capturados")

    entries = st.session_state.manual_entries_by_patient[patient_key]

    if not entries:
        st.info("Aún no has agregado eventos.")
    else:
        df_entries = pd.DataFrame(entries).copy()

        if "datetime" in df_entries.columns:
            df_entries["datetime"] = pd.to_datetime(df_entries["datetime"], errors="coerce")
            df_entries = df_entries.sort_values("datetime").reset_index(drop=True)
            df_entries["datetime"] = df_entries["datetime"].dt.strftime("%Y-%m-%d %H:%M")

        df_show = df_entries.copy()
        show_cols = [c for c in ["hora", "cho_valor", "cho_unidad", "bolus_u", "nota", "datetime"] if c in df_show.columns]
        st.dataframe(df_show[show_cols], use_container_width=True)

        e1, e2 = st.columns(2)

        with e1:
            idx_delete = st.selectbox(
                "Selecciona evento a eliminar",
                options=list(range(len(df_entries))),
                format_func=lambda i: (
                    f"{i} | {df_entries.loc[i, 'hora']} | "
                    f"CHO: {df_entries.loc[i, 'cho_valor']} {df_entries.loc[i, 'cho_unidad']} | "
                    f"Bolus: {df_entries.loc[i, 'bolus_u']} U"
                ),
                key=f"delete_manual_event_idx_{patient_key}"
            )

            if st.button("🗑️ Eliminar evento seleccionado", use_container_width=True, key=f"delete_one_{patient_key}"):
                st.session_state.manual_entries_by_patient[patient_key].pop(idx_delete)

                sync_manual_data_after_edit(
                    patient_id=patient_key,
                    patient_name=patient_name,
                    patient_folder=patient_folder,
                    pred_date=pred_date,
                    start_time_value=start_time_value,
                    glucose_now=glucose_now,
                    entries=st.session_state.manual_entries_by_patient[patient_key]
                )

                st.success("Evento eliminado y cambios guardados.")
                st.rerun()

        with e2:
            if st.button("🧹 Limpiar todos los eventos", use_container_width=True, key=f"delete_all_{patient_key}"):
                st.session_state.manual_entries_by_patient[patient_key] = []

                sync_manual_data_after_edit(
                    patient_id=patient_key,
                    patient_name=patient_name,
                    patient_folder=patient_folder,
                    pred_date=pred_date,
                    start_time_value=start_time_value,
                    glucose_now=glucose_now,
                    entries=[]
                )

                st.success("Todos los eventos fueron eliminados y cambios guardados.")
                st.rerun()

    st.divider()
    st.markdown("### 📊 Resumen")

    if entries:
        df_entries = pd.DataFrame(entries)
        total_cho_g = df_entries["cho_mg"].fillna(0).sum() / 1000.0 if "cho_mg" in df_entries.columns else 0.0
        total_bolus_u = df_entries["bolus_u"].fillna(0).sum() if "bolus_u" in df_entries.columns else 0.0

        r1, r2, r3, r4, r5 = st.columns(5)
        r1.metric("Eventos", int(len(df_entries)))
        r2.metric("Total CHO (g)", f"{total_cho_g:,.2f}")
        r3.metric("Total bolo (U)", f"{total_bolus_u:,.2f}")
        r4.metric("Glucosa inicial", f"{glucose_now:,.1f} mg/dL")
        r5.metric("Hora inicial", start_time_value.strftime("%H:%M"))
    else:
        st.info("Agrega al menos un evento para ver el resumen.")

# =========================
# TAB 4: GUARDAR / PRONÓSTICO
# =========================
with tab4:
    st.subheader("Guardar y continuar")

    entries = st.session_state.manual_entries_by_patient[patient_key]

    if not entries:
        st.info("No hay eventos para guardar todavía.")
    else:
        st.markdown(
            """
            <div style="
                padding: 12px 16px;
                border-radius: 12px;
                background: rgba(52, 152, 219, 0.08);
                border: 1px solid rgba(52, 152, 219, 0.25);
                margin-bottom: 14px;
            ">
                Las ingestas y la configuración se guardan en un solo paso.
            </div>
            """,
            unsafe_allow_html=True,
        )

    if st.button("💾 Guardar eventos", use_container_width=True, type="primary"):
        _, _, _ = save_all_manual_data(
            patient_id=patient_key,
            patient_name=patient_name,
            patient_folder=patient_folder,
            pred_date=pred_date,
            start_time_value=start_time_value,
            glucose_now=glucose_now,
            entries=entries
        )
        st.success("Eventos guardados correctamente.")

    st.markdown("---")

    left, center, right = st.columns([2, 3, 2])

    with center:
        if st.button("📈 Guardar e ir a Pronóstico", use_container_width=True, type="primary"):
            _, _, config_payload = save_all_manual_data(
                patient_id=patient_key,
                patient_name=patient_name,
                patient_folder=patient_folder,
                pred_date=pred_date,
                start_time_value=start_time_value,
                glucose_now=glucose_now,
                entries=entries
            )
            st.session_state.manual_prediction_config = config_payload
            st.switch_page("pages/4_Pronóstico.py")