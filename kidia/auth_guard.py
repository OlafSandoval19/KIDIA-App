import streamlit as st

def require_login():
    if not st.session_state.get("authenticated", False):
        st.warning("Debes iniciar sesión")
        st.switch_page("app.py")
