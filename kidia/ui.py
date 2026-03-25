# kidia/ui.py
from __future__ import annotations
from pathlib import Path
import streamlit as st

def render_kidia_header(
    title: str = "KIDIA",
    subtitle: str = "Sistema de apoyo para monitoreo y análisis glucémico en DMT1",
    logo_path: str | Path = Path("assets") / "logo_kidia.png",
):
    LOGO_W = 220
    ICON_SIZE = 40

    st.markdown(
        """
        <div style="margin-top: 8px; margin-bottom: 8px;"></div>
        """,
        unsafe_allow_html=True
    )

    c1, c2 = st.columns([6, 2], vertical_alignment="center")

    with c1:
        st.markdown(
            f"""
            <div style="display:flex; align-items:center; gap:10px; margin-bottom:4px;">
              <span style="font-size:{ICON_SIZE}px;">📊</span>
              <span style="font-size:{ICON_SIZE}px;">🧠</span>
              <span style="font-size:{ICON_SIZE}px;">📈</span>
              <span style="font-weight:800; font-size:60px; margin-left:6px;">{title}</span>
            </div>
            <div style="font-size:28px; font-weight:600; margin-top:6px;">
              {subtitle}
            </div>
            """,
            unsafe_allow_html=True
        )

    with c2:
        lp = Path(logo_path)
        if lp.exists():
            st.markdown("<div style='margin-top: 20px;'></div>", unsafe_allow_html=True)
            st.image(str(lp), width=LOGO_W)

    st.divider()