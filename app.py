import streamlit as st
from kidia.state import init_state
from kidia.auth import login

import base64
from pathlib import Path

def img_to_base64(path):
    img_bytes = Path(path).read_bytes()
    return base64.b64encode(img_bytes).decode()

# -------------------------------------------------
# CONFIGURACIÓN
# -------------------------------------------------
st.set_page_config(
    page_title="KIDIA – Acceso",
    layout="centered"
)

init_state()

# -------------------------------------------------
# FONDO Blanco (LOGIN)
# -------------------------------------------------
st.markdown(
    """
    <style>
    /* Fondo general */
    body {
        background-color: #FFFFFF;
    }

    /* Fondo real de Streamlit */
    [data-testid="stAppViewContainer"] {
        background-color: #FFFFFF;
    }

    /* Contenedor principal */
    .block-container {
        background-color: transparent;
    }
    </style>
    """,
    unsafe_allow_html=True
)

# -------------------------------------------------
# FORMULARIO LOGIN BOX 
# -------------------------------------------------
st.markdown(
    """
    <style>
    /* Caja del formulario */
    div[data-testid="stForm"] {
        background-color: #F5F8FF;
        padding: 1.2rem 1.4rem;   /* ⬅ MENOS padding */
        border-radius: 12px;
        box-shadow: 0px 6px 18px rgba(0, 0, 0, 0.08);
        max-width: 360px;        /* ⬅ CONTROLA EL ANCHO */
        margin: 0 auto;          /* ⬅ CENTRADO PERFECTO */
    }

    /* Inputs más compactos */
    input {
        background-color: #FFFFFF !important;
        padding: 0.45rem !important;
    }

    /* Botón */
    button {
        width: 100%;
        padding: 0.45rem;
        border-radius: 10px;
    }
    </style>
    """,
    unsafe_allow_html=True
)


# -------------------------------------------------
# OCULTAR SIDEBAR Y SCROLL EN LOGIN
# -------------------------------------------------
st.markdown(
    """
    <style>
    html, body {
        overflow: hidden !important;
        height: 100%;
    }

    section.main > div {
        overflow: hidden !important;
    }

    .block-container {
        padding-top: 2rem;
        padding-bottom: 0rem;
        overflow: hidden !important;
    }

    [data-testid="stSidebar"] {
        display: none;
    }
    </style>
    """,
    unsafe_allow_html=True
)

# -------------------------------------------------
# LOGO PRINCIPAL (KIDIA)
# -------------------------------------------------
logo_left, logo_center, logo_right = st.columns([1, 1.5, 0.4])

with logo_center:
    st.image("assets/logo_kidia.png", width=200)

st.markdown("<br>", unsafe_allow_html=True)

# -------------------------------------------------
# LOGIN
# -------------------------------------------------
form_left, form_center, form_right = st.columns([1, 1.5, 1])

with form_center:
    st.markdown(
        "<h4 style='text-align:center;'>🔐 KIDIA – Acceso</h4>",
        unsafe_allow_html=True
    )

    st.markdown("<br>", unsafe_allow_html=True)

    with st.form("login_form"):
        username = st.text_input("Usuario")
        password = st.text_input("Contraseña", type="password")
        submitted = st.form_submit_button("Ingresar")

        if submitted:
            if login(username, password):
                st.success("Acceso concedido")
                st.switch_page("pages/1_Gestión_de_pacientes.py")
            else:
                st.error("Usuario o contraseña incorrectos")

itcg_b64 = img_to_base64("assets/ITCG.jpg")
tecnm_b64 = img_to_base64("assets/Logo-TecNM.png")

# -------------------------------------------------
# LOGOS INSTITUCIONALES (INFERIOR)
# -------------------------------------------------
st.markdown(
    f"""
    <style>
    .login-footer {{
        position: fixed;
        bottom: 20px;
        left: 0;
        width: 100%;
        display: flex;
        justify-content: space-between;
        padding-left: 80px;
        padding-right: 80px;
        pointer-events: none;
        z-index: 100;
    }}
    .login-footer img {{
        height: 85px;
        opacity: 0.95;
    }}
    </style>

    <div class="login-footer">
        <img src="data:image/png;base64,{itcg_b64}">
        <img src="data:image/png;base64,{tecnm_b64}">
    </div>
    """,
    unsafe_allow_html=True
)


