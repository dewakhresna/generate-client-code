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
    # Konfigurasi dasar tampilan halaman web Streamlit
    st.set_page_config(
        page_title="WhatsApp Chat Client Code Matcher",
        page_icon="🏥",
        layout="wide",
        initial_sidebar_state="collapsed"
    )

    # Render antarmuka pengguna
    ui.render_ui()


if __name__ == "__main__":
    main()
