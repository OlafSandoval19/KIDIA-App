import streamlit as st
import pandas as pd

def init_state():
    # Auth
    if "authenticated" not in st.session_state:
        st.session_state.authenticated = False
    if "user" not in st.session_state:
        st.session_state.user = ""
    if "role" not in st.session_state:
        st.session_state.role = "user"

    # Pacientes (tabla)
    if "patients" not in st.session_state:
        st.session_state.patients = pd.DataFrame(
            columns=["ID", "Nombre", "Edad", "Sexo", "Tutor"]
        )

    # Paciente activo
    if "active_patient" not in st.session_state:
        st.session_state.active_patient = None
    if "patient_id" not in st.session_state:
        st.session_state.patient_id = None
    if "patient_info" not in st.session_state:
        st.session_state.patient_info = None

    # Archivo activo (CSV/XLSX)
    if "active_data_path" not in st.session_state:
        st.session_state.active_data_path = None

