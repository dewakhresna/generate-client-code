# -*- coding: utf-8 -*-
"""
main.py
Titik masuk utama (entry point) untuk menjalankan aplikasi web Streamlit.
Jalankan aplikasi dengan perintah:
    streamlit run main.py
"""

import sys
import streamlit as st
import ui

def main():
    st.set_page_config(
        page_title="Check Client Code",
        page_icon="🏥",
        layout="wide",
        initial_sidebar_state="collapsed"
    )

    ui.render_ui()


if __name__ == "__main__":
    main()
