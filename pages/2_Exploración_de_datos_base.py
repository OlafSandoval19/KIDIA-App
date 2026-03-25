import streamlit as st
import pandas as pd
from pathlib import Path
from datetime import datetime
import re
import gc
import plotly.express as px
import plotly.graph_objects as go

from kidia.state import init_state
from kidia.auth import logout
from kidia.ui import render_kidia_header

# =========================
# 0) CONFIG DE PÁGINA
# =========================
st.set_page_config(page_title="KIDIA | Exploración de datos base", layout="wide")
init_state()

if not st.session_state.get("authenticated", False):
    st.switch_page("app.py")

render_kidia_header()

# =========================
# CSS / SIDEBAR / TABS
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

    button[data-baseweb="tab"] p {
        font-size: 1.12rem !important;
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

    .data-title {
        margin-top: 0rem !important;
        margin-bottom: 0.3rem !important;
    }

    .data-subtitle {
        text-align: center;
        font-size: 1.7rem;
        font-weight: 600;
        color: #374151;
        margin-top: 0;
        margin-bottom: 1.8rem;
        letter-spacing: 0.4px;
        line-height: 1.4;
    }

    .patient-section {
        width: 100% !important;
        padding: 0.25rem 0 0.4rem 0 !important;
        margin-bottom: 0.8rem !important;
    }
</style>
""", unsafe_allow_html=True)

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
# 1) TÍTULO Y SUBTÍTULO
# =========================
st.markdown("""
<h2 class="data-title" style='text-align:center;'>
    🗃️🧾 Exploración de datos base 🧾📊
</h2>
<p class="data-subtitle">
    Selecciona un paciente, importa archivos CSV y explora la estructura, visualización y estadísticas del dataset.
</p>
""", unsafe_allow_html=True)

# =========================
# 1.1) SELECCIÓN DE PACIENTE
# =========================
try:
    BASE_DIR = Path(__file__).resolve().parents[1]
except Exception:
    BASE_DIR = Path.cwd()

PATIENTS_CSV = BASE_DIR / "data" / "patients.csv"

if PATIENTS_CSV.exists():
    patients_df = pd.read_csv(PATIENTS_CSV, dtype=str)
else:
    patients_df = pd.DataFrame(columns=["ID", "Nombre"])

if patients_df.empty:
    st.warning("No hay pacientes registrados todavía. Primero registra un paciente en Gestión de pacientes.")
    st.stop()

patients_df = patients_df.fillna("").copy()

st.markdown('<div class="patient-section">', unsafe_allow_html=True)

st.markdown("### 👤 Selección de paciente")

f1, f2 = st.columns(2)

with f1:
    use_patient_id_filter = st.checkbox("Buscar por ID", key="use_patient_id_filter")
    patient_id_filter = st.text_input(
        "Filtrar por ID",
        placeholder="Ejemplo: CHILD_001",
        key="patient_id_filter",
        disabled=not use_patient_id_filter
    )

with f2:
    use_patient_name_filter = st.checkbox("Buscar por Nombre", key="use_patient_name_filter")
    patient_name_filter = st.text_input(
        "Filtrar por Nombre",
        placeholder="Ejemplo: Niño 1",
        key="patient_name_filter",
        disabled=not use_patient_name_filter
    )

patients_filtered = patients_df.copy()

if use_patient_id_filter and patient_id_filter.strip():
    term_id = patient_id_filter.strip().lower()
    patients_filtered = patients_filtered[
        patients_filtered["ID"].astype(str).str.lower().str.contains(term_id, na=False)
    ]

if use_patient_name_filter and patient_name_filter.strip():
    term_name = patient_name_filter.strip().lower()
    patients_filtered = patients_filtered[
        patients_filtered["Nombre"].astype(str).str.lower().str.contains(term_name, na=False)
    ]

patients_filtered = patients_filtered.reset_index(drop=True)

st.caption(f"Pacientes encontrados: {len(patients_filtered)}")

if patients_filtered.empty:
    st.warning("No se encontraron pacientes con los filtros seleccionados.")
    st.markdown('</div>', unsafe_allow_html=True)
    st.stop()

patients_filtered["label"] = (
    patients_filtered["Nombre"].astype(str) +
    " (ID " +
    patients_filtered["ID"].astype(str) +
    ")"
)

selected_label = st.selectbox(
    "Selecciona el paciente",
    patients_filtered["label"].tolist(),
    key="selected_patient_data_page"
)

st.markdown('</div>', unsafe_allow_html=True)

row = patients_filtered.loc[patients_filtered["label"] == selected_label].iloc[0]
pid = str(row["ID"])
nombre = str(row["Nombre"])

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
            🟢 Paciente seleccionado: {nombre} <span style="font-weight:600; opacity:0.9;">(ID {pid})</span>
        </div>
        <div style="margin-top: 6px; font-size: 15px; opacity: 0.85;">
            Paciente listo para carga y análisis de datos.
        </div>
    </div>
    """,
    unsafe_allow_html=True,
)

# =========================
# 2) RUTAS
# =========================
DATA_ROOT = BASE_DIR / "data" / "uploads"
DATA_ROOT.mkdir(parents=True, exist_ok=True)

UPLOAD_DIR = DATA_ROOT / f"patient_{pid}"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

TRASH_DIR = UPLOAD_DIR / "_trash"
TRASH_DIR.mkdir(parents=True, exist_ok=True)

def _is_inside(child: Path, parent: Path) -> bool:
    try:
        child.resolve().relative_to(parent.resolve())
        return True
    except Exception:
        return False

# =========================
# 2.1) HELPERS
# =========================
def delete_or_quarantine(path: Path, upload_dir: Path):
    try:
        gc.collect()
        path.unlink()
        return True, "Archivo eliminado."
    except PermissionError:
        try:
            trash = upload_dir / "_trash"
            trash.mkdir(parents=True, exist_ok=True)
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            moved = trash / f"{path.stem}.{ts}{path.suffix}"
            path.rename(moved)
            return True, "El archivo estaba en uso. Lo moví a _trash."
        except Exception as e2:
            return False, f"No pude borrar ni aislar el archivo: {e2}"
    except Exception as e:
        return False, f"No pude eliminar: {e}"

def read_csv_robust(path: Path) -> pd.DataFrame:
    for enc in (None, "utf-8", "latin-1"):
        for sep in (",", ";", "\t"):
            try:
                df_try = pd.read_csv(path, encoding=enc, sep=sep)
                if df_try.shape[1] >= 2:
                    return df_try
            except Exception:
                pass
    return pd.read_csv(path)

def to_numeric_col(df_in: pd.DataFrame, col: str | None) -> pd.Series:
    if col is None or col not in df_in.columns:
        return pd.Series(dtype=float)
    return pd.to_numeric(df_in[col], errors="coerce")

def format_number(x, decimals=2):
    try:
        if pd.isna(x):
            return "N/A"
        return f"{x:,.{decimals}f}"
    except Exception:
        return "N/A"

def normalize_label(s: str) -> str:
    return str(s).strip().lower().replace(" ", "")

def find_exactish_column(df_in: pd.DataFrame, candidates: list[str]):
    norm_cols = {normalize_label(c): c for c in df_in.columns}
    for cand in candidates:
        key = normalize_label(cand)
        if key in norm_cols:
            return norm_cols[key]
    return None

def parse_datetime_series(series: pd.Series) -> pd.Series:
    s = series.astype(str).str.strip()

    parsed = pd.to_datetime(s, format="%Y-%m-%d %H:%M:%S", errors="coerce")
    if parsed.notna().mean() > 0.8:
        return parsed

    parsed = pd.to_datetime(s, format="%Y-%m-%d %H:%M", errors="coerce")
    if parsed.notna().mean() > 0.8:
        return parsed

    parsed = pd.to_datetime(s, format="%d/%m/%Y %H:%M:%S", errors="coerce")
    if parsed.notna().mean() > 0.8:
        return parsed

    parsed = pd.to_datetime(s, format="%d/%m/%Y %H:%M", errors="coerce")
    if parsed.notna().mean() > 0.8:
        return parsed

    parsed = pd.to_datetime(s, format="%d/%m/%Y", errors="coerce")
    if parsed.notna().mean() > 0.8:
        return parsed

    return pd.to_datetime(s, errors="coerce", infer_datetime_format=True)

# =========================
# 2.2) ESTADO DE ARCHIVOS
# =========================
selector_ver_key = f"file_selector_ver_{pid}"
selected_key = f"selected_dataset_path_{pid}"
confirm_key = f"confirm_delete_file_{pid}"
confirm_name_key = f"confirm_delete_file_name_{pid}"

if selector_ver_key not in st.session_state:
    st.session_state[selector_ver_key] = 0
if confirm_key not in st.session_state:
    st.session_state[confirm_key] = False
if confirm_name_key not in st.session_state:
    st.session_state[confirm_name_key] = None

# =========================
# 2.3) CARGA DEL CSV ACTIVO
# =========================
selected_path = None
files_all = list(UPLOAD_DIR.glob("*.csv"))
files_all = [p for p in files_all if p.parent == UPLOAD_DIR and not p.name.endswith(".locked")]
files_all = sorted(files_all, key=lambda p: p.stat().st_mtime, reverse=True)

current_selected = st.session_state.get(selected_key)
if current_selected:
    selected_path = Path(current_selected)
elif files_all:
    selected_path = files_all[0]
    st.session_state[selected_key] = str(selected_path)

df = None
load_error = None

if selected_path is not None and selected_path.exists():
    try:
        df = read_csv_robust(selected_path)
    except Exception as e:
        df = None
        load_error = str(e)

# =========================
# 3) TABS
# =========================
tab1, tab2, tab3, tab4 = st.tabs([
    "📥 Importar archivos",
    "👁️ Visualización del histórico",
    "📊 Análisis estadístico",
    "🧾 Resumen estadístico"
])

# =========================
# TAB 1: IMPORTAR ARCHIVOS
# =========================
with tab1:
    st.subheader("Importar archivo CSV")

    f = st.file_uploader("Selecciona archivo (.csv)", type=["csv"], key=f"uploader_{pid}")
    save_btn = st.button("Guardar archivo", disabled=(f is None), key=f"save_btn_{pid}")

    if save_btn and f is not None:
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        clean_name = re.sub(r"[^A-Za-z0-9._-]+", "_", f.name)
        out_path = UPLOAD_DIR / f"{ts}_{clean_name}"
        out_path.write_bytes(f.getbuffer())
        st.success(f"Guardado: {out_path.name}")
        st.session_state[selected_key] = str(out_path)
        st.session_state[selector_ver_key] = st.session_state.get(selector_ver_key, 0) + 1
        st.rerun()

    st.divider()
    st.subheader("Historial de archivos del paciente")

    files = list(UPLOAD_DIR.glob("*.csv"))
    files = [p for p in files if p.parent == UPLOAD_DIR]
    files = [p for p in files if not p.name.endswith(".locked")]
    files = sorted(files, key=lambda p: p.stat().st_mtime, reverse=True)

    if not files:
        st.info("Este paciente aún no tiene archivos cargados. Sube uno arriba.")
    else:
        active_path_pid = st.session_state.get(selected_key)
        active_name_pid = Path(active_path_pid).name if active_path_pid else None

        file_names = [x.name for x in files]
        default_idx = file_names.index(active_name_pid) if active_name_pid in file_names else 0

        selected_name = st.selectbox(
            "Selecciona un archivo CSV",
            file_names,
            index=default_idx,
            key=f"file_select_{pid}_{st.session_state[selector_ver_key]}",
        )
        selected_path_tab1 = UPLOAD_DIR / selected_name

        if not _is_inside(selected_path_tab1, UPLOAD_DIR):
            st.error("Selección inválida: el archivo no pertenece al paciente seleccionado.")
            st.stop()

        st.session_state[selected_key] = str(selected_path_tab1)

        st.markdown("### 👁️ Previsualización del dataset")
        if df is not None:
            st.dataframe(df.head(40), use_container_width=True)
        elif load_error:
            st.error(f"No se pudo cargar el archivo CSV activo: {load_error}")
        else:
            st.info("No se pudo cargar el archivo CSV activo.")

    st.divider()
    st.subheader("Resumen del archivo cargado")

    if df is None:
        if load_error:
            st.error(f"No hay un archivo CSV activo para visualizar. Error: {load_error}")
        else:
            st.info("No hay un archivo CSV activo para visualizar.")
    else:
        c1, c2, c3 = st.columns(3)
        c1.metric("Filas", f"{len(df):,}")
        c2.metric("Columnas", f"{df.shape[1]}")
        c3.metric("Archivo activo", selected_path.name if selected_path is not None else "N/A")






        st.markdown("### Eliminar archivo del historial")

        if not st.session_state[confirm_key]:
            if st.button("Eliminar archivo seleccionado", type="primary", key=f"del_btn_{pid}"):
                st.session_state[confirm_key] = True
                st.session_state[confirm_name_key] = selected_path_tab1.name
                st.rerun()
        else:
            st.warning(
                f"¿Seguro que deseas eliminar **{st.session_state[confirm_name_key]}**? "
                "Esta acción no se puede deshacer."
            )
            c1, c2 = st.columns(2)

            with c1:
                if st.button("Confirmar eliminación", type="primary", key=f"confirm_del_{pid}"):
                    file_to_delete = UPLOAD_DIR / st.session_state[confirm_name_key]

                    if not file_to_delete.exists():
                        st.info("El archivo ya no existe.")
                    else:
                        ok, msg = delete_or_quarantine(file_to_delete, UPLOAD_DIR)
                        if ok:
                            st.success(msg)
                        else:
                            st.error(msg)

                    current_selected_after = st.session_state.get(selected_key)
                    if current_selected_after and Path(current_selected_after).name == file_to_delete.name:
                        st.session_state[selected_key] = None

                    st.session_state[confirm_key] = False
                    st.session_state[confirm_name_key] = None
                    st.session_state[selector_ver_key] += 1
                    st.rerun()

            with c2:
                if st.button("Cancelar", key=f"cancel_del_{pid}"):
                    st.session_state[confirm_key] = False
                    st.session_state[confirm_name_key] = None
                    st.rerun()

    with st.expander("🗑️ Papelera (_trash)"):
            trash_files = sorted(TRASH_DIR.glob("*"), key=lambda p: p.stat().st_mtime, reverse=True)
            if not trash_files:
                st.caption("La papelera está vacía.")
            else:
                st.write("Archivos en _trash:")
                st.dataframe(
                    pd.DataFrame({"archivo": [p.name for p in trash_files]}),
                    use_container_width=True
                )

                if st.button("Vaciar papelera", type="primary", key=f"empty_trash_{pid}"):
                    ok_all = True
                    msgs = []
                    for p in trash_files:
                        try:
                            gc.collect()
                            p.unlink()
                        except Exception as e:
                            ok_all = False
                            msgs.append(f"{p.name}: {e}")
                    if ok_all:
                        st.success("Papelera vaciada.")
                    else:
                        st.warning("No se pudieron borrar algunos archivos.")
                        st.code("\n".join(msgs))

                    st.session_state[selector_ver_key] += 1
                    st.rerun()


# =========================
# TAB 2: VISUALIZACIÓN DEL HISTÓRICO
# =========================
with tab2:
    st.subheader("Visualización del histórico")

    if df is None:
        if load_error:
            st.error(f"No hay un archivo CSV activo para visualizar. Error: {load_error}")
        else:
            st.info("No hay un archivo CSV activo para visualizar.")
    else:
        time_col = find_exactish_column(df, ["datetime"])
        id_col = find_exactish_column(df, ["id"])

        glucose_col = find_exactish_column(df, [
            "glucosa (mg/dL)", "glucosa (mg/dl)", "glucosa(mg/dL)", "glucosa(mg/dl)"
        ])
        carbs_col = find_exactish_column(df, [
            "ingesta_total_CHO (mg)", "ingesta_total_cho (mg)", "ingesta total cho (mg)"
        ])
        bolus_col = find_exactish_column(df, [
            "insulina_bolo (U)", "insulina_bolo (u)", "insulina bolo (U)", "insulina bolo (u)"
        ])

        st.markdown("### 🧾 Estructura y significado de variables")

        column_meanings = {
            "datetime": "Marca temporal del registro.",
            "id": "Identificador del protocolo o serie dentro del dataset.",
            "glucosa (mg/dL)": "Valor de glucosa medido en mg/dL.",
            "glucosa (mg/dl)": "Valor de glucosa medido en mg/dL.",
            "glucosa(mg/dL)": "Valor de glucosa medido en mg/dL.",
            "glucosa(mg/dl)": "Valor de glucosa medido en mg/dL.",
            "ingesta_CHO (mg)": "Evento de ingesta de carbohidratos en mg.",
            "ingesta_total_CHO (mg)": "Cantidad total de carbohidratos ingeridos en mg.",
            "ingesta_total_cho (mg)": "Cantidad total de carbohidratos ingeridos en mg.",
            "ingesta total cho (mg)": "Cantidad total de carbohidratos ingeridos en mg.",
            "insulina_bolo (U)": "Dosis de insulina bolo en unidades.",
            "insulina_bolo (u)": "Dosis de insulina bolo en unidades.",
            "insulina bolo (U)": "Dosis de insulina bolo en unidades.",
            "insulina bolo (u)": "Dosis de insulina bolo en unidades.",
            "absorcion_total": "Variable de absorción total del modelo/simulador.",
            "absorcion_intestino": "Absorción intestinal asociada al proceso digestivo."
        }

        structure_rows = []
        for col in df.columns:
            structure_rows.append({
                "Columna": col,
                "Tipo de dato": str(df[col].dtype),
                "Significado": column_meanings.get(
                    col,
                    "Variable del dataset sin descripción específica definida."
                )
            })

        structure_df = pd.DataFrame(structure_rows)
        st.dataframe(structure_df, use_container_width=True, hide_index=True)

        dataset_ids = []
        if id_col is not None and id_col in df.columns:
            dataset_ids = df[id_col].dropna().astype(str).str.strip()
            dataset_ids = dataset_ids[dataset_ids != ""].unique().tolist()

        if dataset_ids:
            ids_preview = ", ".join(dataset_ids[:10])
            if len(dataset_ids) > 10:
                ids_preview += f" ... (+{len(dataset_ids) - 10} más)"

            st.markdown(
                f"""
                <div style="
                    padding: 12px 16px;
                    border-radius: 12px;
                    background: rgba(52, 152, 219, 0.10);
                    border: 1px solid rgba(52, 152, 219, 0.30);
                    margin-bottom: 14px;
                ">
                    <b>IDs detectados en el dataset ({len(dataset_ids)}):</b> {ids_preview}
                </div>
                """,
                unsafe_allow_html=True,
            )

        df_plot = df.copy()

        if time_col is not None and time_col in df_plot.columns:
            df_plot[time_col] = parse_datetime_series(df_plot[time_col])
            df_plot = df_plot.dropna(subset=[time_col])
            sort_cols = [time_col]
            if id_col is not None and id_col in df_plot.columns:
                sort_cols = [id_col, time_col]
            df_plot = df_plot.sort_values(by=sort_cols).reset_index(drop=True)
        else:
            df_plot = df_plot.reset_index(drop=True)

        st.markdown("### Series principales")

        if dataset_ids:
            mode_plot = st.radio(
                "Modo de visualización",
                ["Todos los protocolos", "Un protocolo específico"],
                horizontal=True,
                key="plot_mode_protocols"
            )
        else:
            mode_plot = "Todos los protocolos"

        df_series = df_plot.copy()

        if dataset_ids and id_col is not None and id_col in df_plot.columns:
            if mode_plot == "Un protocolo específico":
                selected_plot_id = st.selectbox(
                    "Selecciona un ID para visualizar",
                    dataset_ids,
                    key="selected_plot_id"
                )
                df_series = df_plot[
                    df_plot[id_col].astype(str).str.strip() == selected_plot_id
                ].copy()
                st.caption(f"Mostrando series del ID: {selected_plot_id}")
            else:
                st.caption("Mostrando todos los protocolos con colores diferentes.")

        if glucose_col is not None and glucose_col in df_series.columns:
            df_series["__glucose__"] = pd.to_numeric(df_series[glucose_col], errors="coerce")

        if carbs_col is not None and carbs_col in df_series.columns:
            df_series["__carbs__"] = pd.to_numeric(df_series[carbs_col], errors="coerce")

        if bolus_col is not None and bolus_col in df_series.columns:
            df_series["__bolus__"] = pd.to_numeric(df_series[bolus_col], errors="coerce")

        if time_col is None or time_col not in df_series.columns:
            df_series["__time__"] = range(len(df_series))
            x_col = "__time__"
            x_title = "Índice"
        else:
            x_col = time_col
            x_title = "Tiempo"

        if glucose_col is not None and glucose_col in df_series.columns:
            df_g = df_series.dropna(subset=["__glucose__"]).copy()

            if not df_g.empty:
                fig_g = go.Figure()

                if (
                    dataset_ids
                    and id_col is not None
                    and id_col in df_g.columns
                    and mode_plot == "Todos los protocolos"
                ):
                    ids_to_plot = df_g[id_col].dropna().astype(str).str.strip().unique().tolist()

                    for pid_plot in ids_to_plot:
                        df_pid = df_g[df_g[id_col].astype(str).str.strip() == pid_plot].copy()
                        fig_g.add_trace(go.Scatter(
                            x=df_pid[x_col],
                            y=df_pid["__glucose__"],
                            mode="lines",
                            name=f"{pid_plot}"
                        ))
                else:
                    fig_g.add_trace(go.Scatter(
                        x=df_g[x_col],
                        y=df_g["__glucose__"],
                        mode="lines",
                        name="Glucosa (mg/dL)"
                    ))

                fig_g.update_layout(
                    title="Glucosa en el tiempo",
                    xaxis_title=x_title,
                    yaxis_title="Glucosa (mg/dL)",
                    height=460
                )
                st.plotly_chart(fig_g, use_container_width=True)
            else:
                st.info("No hay datos válidos de glucosa para graficar.")

        c4, c5 = st.columns(2)

        with c4:
            if carbs_col is not None and carbs_col in df_series.columns:
                df_c = df_series.dropna(subset=["__carbs__"]).copy()
                df_c = df_c[df_c["__carbs__"] > 0]

                if not df_c.empty:
                    fig_c = go.Figure()

                    if (
                        dataset_ids
                        and id_col is not None
                        and id_col in df_c.columns
                        and mode_plot == "Todos los protocolos"
                    ):
                        ids_to_plot = df_c[id_col].dropna().astype(str).str.strip().unique().tolist()

                        for pid_plot in ids_to_plot:
                            df_pid = df_c[df_c[id_col].astype(str).str.strip() == pid_plot].copy()
                            fig_c.add_trace(go.Scatter(
                                x=df_pid[x_col],
                                y=df_pid["__carbs__"],
                                mode="markers",
                                name=f"{pid_plot}"
                            ))
                    else:
                        fig_c.add_trace(go.Scatter(
                            x=df_c[x_col],
                            y=df_c["__carbs__"],
                            mode="markers",
                            name="Ingesta total CHO (mg)"
                        ))

                    fig_c.update_layout(
                        title="Ingesta total CHO",
                        xaxis_title=x_title,
                        yaxis_title="CHO (mg)",
                        height=360
                    )
                    st.plotly_chart(fig_c, use_container_width=True)
                else:
                    st.info("No hay eventos de CHO > 0 para graficar.")

        with c5:
            if bolus_col is not None and bolus_col in df_series.columns:
                df_b = df_series.dropna(subset=["__bolus__"]).copy()
                df_b = df_b[df_b["__bolus__"] > 0]

                if not df_b.empty:
                    fig_b = go.Figure()

                    if (
                        dataset_ids
                        and id_col is not None
                        and id_col in df_b.columns
                        and mode_plot == "Todos los protocolos"
                    ):
                        ids_to_plot = df_b[id_col].dropna().astype(str).str.strip().unique().tolist()

                        for pid_plot in ids_to_plot:
                            df_pid = df_b[df_b[id_col].astype(str).str.strip() == pid_plot].copy()
                            fig_b.add_trace(go.Scatter(
                                x=df_pid[x_col],
                                y=df_pid["__bolus__"],
                                mode="markers",
                                name=f"{pid_plot}"
                            ))
                    else:
                        fig_b.add_trace(go.Scatter(
                            x=df_b[x_col],
                            y=df_b["__bolus__"],
                            mode="markers",
                            name="Insulina bolo (U)"
                        ))

                    fig_b.update_layout(
                        title="Insulina bolo",
                        xaxis_title=x_title,
                        yaxis_title="Insulina bolo (U)",
                        height=360
                    )
                    st.plotly_chart(fig_b, use_container_width=True)
                else:
                    st.info("No hay eventos de insulina bolo > 0 para graficar.")

# =========================
# TAB 3: ANÁLISIS ESTADÍSTICO
# =========================
with tab3:
    st.subheader("Análisis estadístico")

    if df is None:
        if load_error:
            st.error(f"No hay un archivo CSV activo para analizar. Error: {load_error}")
        else:
            st.info("No hay un archivo CSV activo para analizar.")
    else:
        time_col = find_exactish_column(df, ["datetime"])
        glucose_col = find_exactish_column(df, [
            "glucosa (mg/dL)", "glucosa (mg/dl)", "glucosa(mg/dL)", "glucosa(mg/dl)"
        ])
        carbs_col = find_exactish_column(df, [
            "ingesta_total_CHO (mg)", "ingesta_total_cho (mg)", "ingesta total cho (mg)"
        ])
        bolus_col = find_exactish_column(df, [
            "insulina_bolo (U)", "insulina_bolo (u)", "insulina bolo (U)", "insulina bolo (u)"
        ])

        df_plot = df.copy()
        if time_col is not None and time_col in df_plot.columns:
            df_plot[time_col] = parse_datetime_series(df_plot[time_col])
            df_plot = df_plot.dropna(subset=[time_col])
            df_plot = df_plot.sort_values(by=time_col).reset_index(drop=True)

        glucose = to_numeric_col(df_plot, glucose_col)
        carbs = to_numeric_col(df_plot, carbs_col)
        bolus = to_numeric_col(df_plot, bolus_col)

        m1, m2, m3 = st.columns(3)

        with m1:
            st.markdown("#### Glucosa (mg/dL)")
            st.metric("Promedio", format_number(glucose.mean()))
            st.metric("Mínimo", format_number(glucose.min()))
            st.metric("Máximo", format_number(glucose.max()))

        with m2:
            st.markdown("#### Ingesta total CHO (mg)")
            st.metric("Promedio", format_number(carbs.mean()))
            st.metric("Máximo", format_number(carbs.max()))
            st.metric("Total", format_number(carbs.sum()))

        with m3:
            st.markdown("#### Insulina bolo (U)")
            st.metric("Promedio", format_number(bolus.mean()))
            st.metric("Máximo", format_number(bolus.max()))
            st.metric("Total", format_number(bolus.sum()))

        st.markdown("### Distribuciones")
        h1, h2, h3 = st.columns(3)

        glucose_hist = glucose.dropna()
        carbs_hist = carbs.dropna()
        bolus_hist = bolus.dropna()

        carbs_events = carbs_hist[carbs_hist > 0]
        bolus_events = bolus_hist[bolus_hist > 0]

        with h1:
            if len(glucose_hist) > 0:
                fig_hg = px.histogram(
                    x=glucose_hist,
                    nbins=40,
                    title="Histograma de glucosa"
                )
                fig_hg.update_layout(
                    xaxis_title="Glucosa (mg/dL)",
                    yaxis_title="Frecuencia",
                    height=320
                )
                st.plotly_chart(fig_hg, use_container_width=True)
            else:
                st.info("No hay datos de glucosa para graficar.")

        with h2:
            if len(carbs_events) > 0:
                fig_hc = px.histogram(
                    x=carbs_events,
                    nbins=40,
                    title="Histograma de CHO (solo eventos > 0)"
                )
                fig_hc.update_layout(
                    xaxis_title="CHO (mg)",
                    yaxis_title="Frecuencia",
                    height=320
                )
                st.plotly_chart(fig_hc, use_container_width=True)
            else:
                st.info("No hay eventos de CHO > 0 para graficar.")

        with h3:
            if len(bolus_events) > 0:
                fig_hb = px.histogram(
                    x=bolus_events,
                    nbins=40,
                    title="Histograma de insulina bolo (solo eventos > 0)"
                )
                fig_hb.update_layout(
                    xaxis_title="Insulina bolo (U)",
                    yaxis_title="Frecuencia",
                    height=320
                )
                st.plotly_chart(fig_hb, use_container_width=True)
            else:
                st.info("No hay eventos de insulina bolo > 0 para graficar.")

        st.markdown("### Correlación en eventos de ingesta")

        corr_events = pd.DataFrame({
            "Glucosa (mg/dL)": glucose,
            "Ingesta total CHO (mg)": carbs,
            "Insulina bolo (U)": bolus,
        })

        corr_events = corr_events[
            (corr_events["Ingesta total CHO (mg)"] > 0) |
            (corr_events["Insulina bolo (U)"] > 0)
        ].dropna(how="all", axis=1)

        if corr_events.shape[1] >= 2 and len(corr_events) > 2:
            ce1, ce2 = st.columns(2)

            with ce1:
                corr_p_events = corr_events.corr(method="pearson", numeric_only=True)
                fig_corr_p_events = px.imshow(
                    corr_p_events,
                    text_auto=".2f",
                    aspect="auto",
                    title="Pearson (solo eventos no-cero)"
                )
                fig_corr_p_events.update_layout(height=420)
                st.plotly_chart(fig_corr_p_events, use_container_width=True)

            with ce2:
                corr_s_events = corr_events.corr(method="spearman", numeric_only=True)
                fig_corr_s_events = px.imshow(
                    corr_s_events,
                    text_auto=".2f",
                    aspect="auto",
                    title="Spearman (solo eventos no-cero)"
                )
                fig_corr_s_events.update_layout(height=420)
                st.plotly_chart(fig_corr_s_events, use_container_width=True)
        else:
            st.info("No hay suficientes eventos no-cero para calcular correlaciones útiles.")

# =========================
# TAB 4: RESUMEN ESTADÍSTICO
# =========================
with tab4:
    st.subheader("Resumen estadístico")

    if df is None:
        if load_error:
            st.error(f"No hay un archivo CSV activo para resumir. Error: {load_error}")
        else:
            st.info("No hay un archivo CSV activo para resumir.")
    else:
        glucose_col = find_exactish_column(df, [
            "glucosa (mg/dL)", "glucosa (mg/dl)", "glucosa(mg/dL)", "glucosa(mg/dl)"
        ])
        carbs_col = find_exactish_column(df, [
            "ingesta_total_CHO (mg)", "ingesta_total_cho (mg)", "ingesta total cho (mg)"
        ])
        bolus_col = find_exactish_column(df, [
            "insulina_bolo (U)", "insulina_bolo (u)", "insulina bolo (U)", "insulina bolo (u)"
        ])

        glucose = to_numeric_col(df, glucose_col)
        carbs = to_numeric_col(df, carbs_col)
        bolus = to_numeric_col(df, bolus_col)

        stats_df = pd.DataFrame({
            "Glucosa (mg/dL)": glucose,
            "Ingesta total CHO (mg)": carbs,
            "Insulina bolo (U)": bolus,
        }).describe().T

        st.dataframe(stats_df, use_container_width=True)