import streamlit as st

USERS = {
    "admin": {
        "password": "admin123",
        "role": "admin"
    },
    "doctor": {
        "password": "doc123",
        "role": "clinician"
    }
}

def login(username, password):
    if username in USERS and USERS[username]["password"] == password:
        st.session_state.authenticated = True
        st.session_state.user = username
        st.session_state.role = USERS[username]["role"]
        return True
    return False

def logout():
    st.session_state.authenticated = False
    st.session_state.user = None
    st.session_state.role = None
