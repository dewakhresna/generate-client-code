# -*- coding: utf-8 -*-
"""
ui.py
Modul antarmuka pengguna (User Interface) berbasis Streamlit.
Menyediakan tata letak single page:
- Pilihan Region Client (SHEET_NAME)
- Area input CHAT_DATA
- Tombol Kirim
- Panel hasil dengan tombol Copy, Extract TXT, Extract Excel, dan Text Area yang dapat diedit langsung.
"""

import json
import streamlit as st
import streamlit.components.v1 as components
import logic


@st.cache_data(ttl=300, show_spinner=False)
def get_cached_sheets(spreadsheet_id: str):
    """Cache daftar tab sheet selama 5 menit."""
    return logic.fetch_available_sheets(spreadsheet_id)


@st.cache_data(ttl=300, show_spinner=False)
def get_cached_master(spreadsheet_id: str, sheet_name: str):
    """Cache master data rumah sakit per sheet selama 5 menit."""
    return logic.load_hospital_master(spreadsheet_id, sheet_name)


def render_copy_button(text_to_copy: str, label: str = "📋 Copy ke Clipboard") -> None:
    """
    Menampilkan tombol Copy kustom yang menyalin teks ke clipboard secara instan
    menggunakan JavaScript Navigator Clipboard API dengan JSON serialization yang aman.
    """
    text_json = json.dumps(text_to_copy)
    
    copy_html = f"""
    <div style="margin-bottom: 8px;">
        <button id="copy-btn" onclick="copyContent()" style="
            background-color: #10B981;
            color: white;
            border: none;
            border-radius: 6px;
            padding: 8px 16px;
            font-size: 14px;
            font-weight: 600;
            cursor: pointer;
            display: inline-flex;
            align-items: center;
            gap: 6px;
            box-shadow: 0 1px 2px rgba(0,0,0,0.05);
            transition: all 0.2s ease;
        ">
            <span>📋</span> <span id="btn-text">{label}</span>
        </button>
    </div>
    <script>
    function copyContent() {{
        const text = {text_json};
        navigator.clipboard.writeText(text).then(() => {{
            const btnText = document.getElementById("btn-text");
            const original = btnText.innerText;
            btnText.innerText = "✅ Tersalin!";
            document.getElementById("copy-btn").style.backgroundColor = "#059669";
            setTimeout(() => {{
                btnText.innerText = original;
                document.getElementById("copy-btn").style.backgroundColor = "#10B981";
            }}, 2000);
        }}).catch(err => {{
            alert("Gagal menyalin: " + err);
        }});
    }}
    </script>
    """
    components.html(copy_html, height=52)


def render_ui() -> None:
    """Fungsi utama untuk merender antarmuka pengguna Streamlit."""
    
    # Custom CSS untuk tampilan yang bersih dan modern
    st.markdown("""
    <style>
    .main-title {
        font-size: 1.8rem;
        font-weight: 700;
        color: #1E293B;
        margin-bottom: 0.2rem;
    }
    .sub-title {
        color: #64748B;
        font-size: 0.95rem;
        margin-bottom: 1.5rem;
    }
    .metric-card {
        background-color: #F8FAFC;
        border: 1px solid #E2E8F0;
        border-radius: 8px;
        padding: 12px;
        text-align: center;
    }
    .stTextArea textarea {
        font-family: 'Consolas', 'Courier New', monospace;
        font-size: 13.5px;
    }
    </style>
    """, unsafe_allow_html=True)

    st.markdown('<div class="main-title">🏥 WhatsApp Chat Hospital Code Matcher</div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="sub-title">Sistem otomatisasi penyisipan kode klien rumah sakit / klinik dari WhatsApp chat ke format berlabel.</div>',
        unsafe_allow_html=True
    )

    # Inisialisasi Session State jika belum ada
    if "process_result" not in st.session_state:
        st.session_state["process_result"] = None
    if "edited_chat_output" not in st.session_state:
        st.session_state["edited_chat_output"] = ""
    if "last_processed_region" not in st.session_state:
        st.session_state["last_processed_region"] = ""

    # ============================================================
    # 1. FORMULIR INPUT
    # ============================================================
    with st.container():
        col_region, col_refresh = st.columns([4, 1])

        with col_region:
            # Ambil sheet names yang tersedia (dengan caching bawaan / fallback)
            available_sheets = get_cached_sheets(logic.DEFAULT_SPREADSHEET_ID)
            
            # Opsi dropdown dengan tambahan opsi manual
            sheet_options = available_sheets.copy()
            custom_option_label = "✏️ Ketik Nama Sheet Lainnya..."
            sheet_options.append(custom_option_label)

            default_idx = 0
            if logic.DEFAULT_SHEET_NAME in sheet_options:
                default_idx = sheet_options.index(logic.DEFAULT_SHEET_NAME)

            selected_sheet_choice = st.selectbox(
                "Pilih Region Client (SHEET_NAME):",
                options=sheet_options,
                index=default_idx,
                help="Pilih tab sheet pada Google Spreadsheet yang memuat master data wilayah ini."
            )

            # Jika memilih custom input
            if selected_sheet_choice == custom_option_label:
                final_sheet_name = st.text_input(
                    "Masukkan Nama Sheet Manual:",
                    value="CLIENT JONGGOL",
                    placeholder="Contoh: CLIENT JONGGOL"
                )
            else:
                final_sheet_name = selected_sheet_choice

        with col_refresh:
            st.write("")
            st.write("")
            if st.button("🔄 Muat Ulang Sheet", help="Segarkan daftar tab dari Google Spreadsheet"):
                st.cache_data.clear()
                st.rerun()

        # Input Area CHAT_DATA
        chat_input = st.text_area(
            "Teks Chat (CHAT_DATA):",
            height=200,
            placeholder=(
                "Tempel teks chat WhatsApp Anda di sini...\n"
                "Contoh:\n"
                "*JONGGOL*\n"
                "RS Permata Jonggol: Pasien 5\n"
                "RS Hermina Mekarsari..."
            ),
            help="Tempelkan percakapan chat lengkap dengan baris pertama berupa nama wilayah."
        )

        col_btn, _ = st.columns([2, 5])
        with col_btn:
            submit_clicked = st.button("🚀 Kirim / Proses Data", type="primary", use_container_width=True)

    # ============================================================
    # 2. LOGIKA PEMROSESAN SAAT TOMBOL KIRIM DIKLIK
    # ============================================================
    if submit_clicked:
        if not chat_input.strip():
            st.warning("⚠️ Silakan isi CHAT_DATA terlebih dahulu sebelum memproses.")
        else:
            with st.spinner(f"Membaca master data sheet '{final_sheet_name}' & mencocokkan kode..."):
                hospital_master, error_msg = get_cached_master(
                    spreadsheet_id=logic.DEFAULT_SPREADSHEET_ID,
                    sheet_name=final_sheet_name
                )

                if error_msg:
                    st.error(f"❌ {error_msg}")
                elif not hospital_master:
                    st.warning("⚠️ Data master rumah sakit kosong atau tidak ditemukan.")
                else:
                    try:
                        result = logic.process_chat(chat_input, hospital_master)
                        st.session_state["process_result"] = result
                        st.session_state["edited_chat_output"] = result["updated_text"]
                        st.session_state["last_processed_region"] = result["region_name"]
                        st.success(f"✅ Pemrosesan berhasil! {result['summary']['matched_lines']} fasilitas berhasil diberi kode.")
                    except Exception as e:
                        st.error(f"❌ Gagal memproses chat: {e}")

    # ============================================================
    # 3. TAMPILAN HASIL (JIKA SUDAH DIPROSES)
    # ============================================================
    result = st.session_state.get("process_result")
    if result:
        st.markdown("---")
        st.subheader("📋 Hasil CHAT_DATA dengan Kode Client")

        # --------------------------------------------------------
        # BARIS ATAS: TOMBOL COPY & TOMBOL EKSTRAKSI (TXT / EXCEL)
        # --------------------------------------------------------
        top_bar_col1, top_bar_col2, top_bar_col3 = st.columns([1.5, 1.2, 1.2])

        # Ambil teks terbaru yang mungkin sudah diedit pengguna
        current_text = st.session_state.get("edited_chat_output", result["updated_text"])
        region_slug = st.session_state.get("last_processed_region", "CHAT")

        with top_bar_col1:
            render_copy_button(current_text, label="Copy ke Clipboard")

        with top_bar_col2:
            txt_data = logic.generate_txt_export(current_text)
            st.download_button(
                label="📄 Extract ke TXT",
                data=txt_data,
                file_name=f"{region_slug}_dengan_kode.txt",
                mime="text/plain",
                use_container_width=True,
                help="Unduh hasil chat yang tertera saat ini dalam berkas teks (.txt)"
            )

        with top_bar_col3:
            excel_bytes, excel_err = logic.generate_excel_export(result)
            if excel_bytes:
                st.download_button(
                    label="📊 Extract ke Excel",
                    data=excel_bytes,
                    file_name=f"{region_slug}_laporan_lengkap.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    use_container_width=True,
                    help="Unduh data terstruktur hasil kode, fasilitas tidak cocok, dan ambigu dalam berkas Excel (.xlsx)"
                )
            else:
                st.button(
                    "📊 Extract ke Excel (Belum Tersedia)",
                    disabled=True,
                    use_container_width=True,
                    help=f"Perlu memasang paket openpyxl (`pip install openpyxl`). Pesan: {excel_err}"
                )

        # --------------------------------------------------------
        # TEXT AREA HASIL YANG DAPAT DIEDIT LANGSUNG
        # --------------------------------------------------------
        edited_text = st.text_area(
            "Hasil Chat (Dapat diedit langsung di bawah ini):",
            value=st.session_state["edited_chat_output"],
            height=320,
            key="chat_result_editor",
            help="Anda dapat mengubah atau menyempurnakan teks ini secara langsung. Tombol copy dan unduh TXT akan mengikuti perubahan Anda.",
            on_change=lambda: st.session_state.update({
                "edited_chat_output": st.session_state.get("chat_result_editor", "")
            })
        )
        # Pastikan session state sinkron dengan perubahan pengguna
        st.session_state["edited_chat_output"] = edited_text

        # --------------------------------------------------------
        # RINGKASAN METRIK & DETAIL DIAGNOSTIK
        # --------------------------------------------------------
        summary = result["summary"]
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Total Baris", summary["total_lines"])
        m2.metric("Baris Cocok", summary["matched_lines"])
        m3.metric("Fasilitas Belum Cocok", summary["unmatched_facilities"])
        m4.metric("Kecocokan Ambigu", summary["ambiguous_matches"])

        # Tab Rincian untuk Unmatched & Ambiguous
        tab_unmatched, tab_ambiguous, tab_raw_report = st.tabs([
            f"Fasilitas Belum Terdaftar ({summary['unmatched_facilities']})",
            f"Kecocokan Ambigu ({summary['ambiguous_matches']})",
            "Laporan Teks Lengkap"
        ])

        with tab_unmatched:
            if result["unmatched"]:
                st.info("Daftar baris yang terindikasi fasilitas kesehatan (RS/Klinik/Lab), namun belum ada di master data:")
                for item in result["unmatched"]:
                    st.markdown(f"- **Baris {item['line_number']}**: `{item['hospital']}`")
            else:
                st.success("Semua baris fasilitas berhasil dicocokkan! Tidak ada fasilitas yang belum terdaftar.")

        with tab_ambiguous:
            if result["ambiguous"]:
                st.warning("Daftar fasilitas yang memiliki lebih dari satu kemungkinan kode unik:")
                for item in result["ambiguous"]:
                    with st.expander(f"Baris {item['line_number']}: {item['hospital']}"):
                        for m in item["matches"]:
                            st.write(f"- Alias: **{m['alias']}** ➔ Kode: `{m['code']}` ({m.get('name', '')})")
            else:
                st.success("Tidak ada kecocokan yang ambigu.")

        with tab_raw_report:
            report_text = logic.generate_review_report_txt(result["unmatched"], result["ambiguous"])
            st.text_area("Laporan Diagnostik:", value=report_text, height=180, disabled=True)
            st.download_button(
                label="📥 Unduh Laporan Review (.txt)",
                data=report_text,
                file_name=f"{region_slug}_rumah_sakit_tidak_ditemukan.txt",
                mime="text/plain"
            )
