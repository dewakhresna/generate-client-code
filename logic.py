"""
logic.py
Modul logika pemrosesan chat, normalisasi teks, pengambilan data Google Sheets,
dan algoritma pencocokan kode rumah sakit/fasilitas kesehatan.
"""

import io
import os
import re
import unicodedata
import urllib.request
import pandas as pd
import streamlit as st
from typing import Dict, List, Optional, Tuple, Any
from dotenv import load_dotenv

load_dotenv()

def get_config(key: str, default: str = "") -> str:
  # Cek apakah st.secrets tersedia dan memiliki secret key
  try:
    if hasattr(st, "secrets") and key in st.secrets:
      return st.secrets[key]
  except Exception:
    pass

  # Jika tidak ada di secrets, ambil dari environment variable (.env / os)
  val = os.getenv(key)
  if val is not None:
    return val

  return default

# ============================================================
# KONFIGURASI DEFAULT GOOGLE SHEETS
# ============================================================
DEFAULT_SPREADSHEET_ID = os.getenv("DEFAULT_SPREADSHEET_ID", "")
DEFAULT_SHEET_NAME = os.getenv("DEFAULT_SHEET_NAME", "Sheet1")

FACILITY_PATTERN = re.compile(
    r"^(RS|RUMAH SAKIT|RSGM|RSIA|RSUD|RSU|RSI|RSJ|RSK|"
    r"RSAU|KLINIK|PUSKESMAS|PKM|HERMINA|SILOAM|PRODIA|"
    r"LAB|PMI|UDD|ERHA|SKIN|JEC|SMEC|HELSA|ALIA|"
    r"RAHO|PERISAI|STIKES)",
    re.IGNORECASE
)


def get_export_url(spreadsheet_id: str = DEFAULT_SPREADSHEET_ID) -> str:
    """Mengembalikan URL ekspor file Excel dari Google Spreadsheet."""
    return f"https://docs.google.com/spreadsheets/d/{spreadsheet_id}/export?format=xlsx"


def normalize_text(text: Any) -> str:
    if text is None:
        return ""
    
    text = str(text)
    
    # 1. Konversi font Unicode khusus ke karakter standar
    text = unicodedata.normalize("NFKC", text)
    
    # 2. Ubah ke ASCII dan Uppercase
    text = text.encode("ascii", "ignore").decode("ascii")
    text = text.upper()
    
    # 3. Hapus penomoran awal (misal: "1.", "2)", "1-") HANYA UNTUK PROSES MATCHING
    text = re.sub(r"^\d+[\.\)]\s*", "", text)
    
    # 4. Hapus simbol bullet atau strip di awal baris
    text = re.sub(r"^[-•]\s*", "", text)
    
    # 5. Bersihkan tanda baca dan spasi berlebih
    text = re.sub(r"[^A-Z0-9]+", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    
    return text

def fetch_available_sheets(spreadsheet_id: str = DEFAULT_SPREADSHEET_ID) -> List[str]:
    """
    Mengambil daftar nama tab (sheet) yang tersedia dari Google Sheets.
    Jika terjadi kendala koneksi atau ketergantungan excel belum terpasang,
    mengembalikan daftar default.
    """
    url = get_export_url(spreadsheet_id)
    try:
        req = urllib.request.Request(
            url,
            headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
        )
        with urllib.request.urlopen(req, timeout=12) as response:
            content = response.read()
            excel_file = pd.ExcelFile(io.BytesIO(content))
            sheet_names = excel_file.sheet_names
            if sheet_names:
                return sheet_names
    except Exception:
        pass
    
    # Fallback default sheet names jika offline atau parsing belum tersedia
    return [
        "CLIENT JONGGOL",
        "CLIENT BOGOR",
        "CLIENT DEPOK",
        "CLIENT BEKASI",
        "CLIENT JAKARTA"
    ]


def load_hospital_master(
    spreadsheet_id: str = DEFAULT_SPREADSHEET_ID,
    sheet_name: str = DEFAULT_SHEET_NAME
) -> Tuple[List[Dict[str, str]], Optional[str]]:
    """
    Membaca data master rumah sakit dari Google Sheets pada sheet tertentu.
    Mengembalikan tuple (hospital_master, error_message).
    """
    url = get_export_url(spreadsheet_id)
    try:
        req = urllib.request.Request(
            url,
            headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
        )
        with urllib.request.urlopen(req, timeout=15) as response:
            content = response.read()
            master_df = pd.read_excel(
                io.BytesIO(content),
                sheet_name=sheet_name,
                dtype=str
            )
    except Exception as e:
        error_msg = (
            f"Gagal membaca Google Sheets pada sheet '{sheet_name}'. "
            f"Pastikan ID & Nama Sheet benar, serta akses link sudah diset "
            f"'Anyone with the link can view'. Detail: {e}"
        )
        return [], error_msg

    required_columns = ["Kode Unik", "Nama Resmi", "Alias"]
    for col in required_columns:
        if col not in master_df.columns:
            return [], f"Kolom wajib tidak ditemukan pada sheet: '{col}'"

    # Hapus baris tanpa Kode Unik atau Alias
    master_df = master_df.dropna(subset=["Kode Unik", "Alias"])

    hospital_master: List[Dict[str, str]] = []

    for _, row in master_df.iterrows():
        code = str(row["Kode Unik"]).strip()
        official_name = str(row["Nama Resmi"]).strip()
        aliases = str(row["Alias"]).split(",")

        for alias in aliases:
            alias = alias.strip()
            normalized_alias = normalize_text(alias)
            if not normalized_alias:
                continue
            hospital_master.append({
                "alias": alias,
                "normalized_alias": normalized_alias,
                "code": code,
                "name": official_name
            })

    # Urutkan berdasarkan panjang alias ternormalisasi secara menurun
    # agar pencocokan nama yang lebih spesifik diprioritaskan
    hospital_master.sort(
        key=lambda x: len(x["normalized_alias"]),
        reverse=True
    )

    return hospital_master, None


def find_hospital_match(line: str, hospital_master: List[Dict[str, str]]) -> Optional[Dict[str, Any]]:
    """
    Mencocokkan baris teks dengan master rumah sakit.
    Memeriksa kecocokan kata utuh dan menangani kondisi ambigu.
    """
    normalized_line = normalize_text(line)
    matches = []

    for hospital in hospital_master:
        alias = hospital["normalized_alias"]
        # Match complete words only
        pattern = r"(?<![A-Z0-9])" + re.escape(alias) + r"(?![A-Z0-9])"

        if re.search(pattern, normalized_line):
            matches.append(hospital)

    if not matches:
        return None

    # Cari alias yang terpanjang
    longest_length = len(matches[0]["normalized_alias"])
    best_matches = [
        item for item in matches
        if len(item["normalized_alias"]) == longest_length
    ]

    # Cek apakah alias terpanjang memiliki kode unik yang berbeda
    unique_codes = {item["code"] for item in best_matches}
    if len(unique_codes) > 1:
        return {
            "status": "AMBIGUOUS",
            "matches": best_matches
        }

    return {
        "status": "MATCHED",
        "match": best_matches[0]
    }


def add_hospital_code(line: str, hospital_master: List[Dict[str, str]]) -> Tuple[str, Optional[Dict[str, Any]]]:
    """
    Menyisipkan kode rumah sakit ke dalam baris chat dengan mempertahankan prefix
    (spasi awalan, bullet points, penanda bold WhatsApp).
    """
    result = find_hospital_match(line, hospital_master)

    if result is None:
        return line, None

    if result["status"] == "AMBIGUOUS":
        return line, result

    hospital = result["match"]
    code = hospital["code"]

    # Hindari duplikasi jika kode sudah ada pada baris
    if f"[{code}]" in line:
        return line, {
            "status": "ALREADY_CODED",
            "code": code
        }

    # Pertahankan prefix (spasi, bullet, tanda bintang bold)
    prefix_match = re.match(r"^(\s*(?:[-•]\s*)?(?:\*\s*)?)", line)
    prefix = prefix_match.group(1) if prefix_match else ""
    remaining = line[len(prefix):]

    updated_line = f"{prefix}[{code}] {remaining}"

    return updated_line, {
        "status": "MATCHED",
        "code": code,
        "alias": hospital["alias"],
        "name": hospital["name"]
    }


def is_facility_line(line: str) -> bool:
    """Mengecek apakah suatu baris terindikasi sebagai nama fasilitas kesehatan."""
    normalized_line = normalize_text(line)
    return bool(FACILITY_PATTERN.search(normalized_line))


def process_chat(chat_data: str, hospital_master: List[Dict[str, str]]) -> Dict[str, Any]:
    """
    Memproses keseluruhan teks chat:
    1. Mengidentifikasi nama region dari baris pertama.
    2. Menambahkan kode ke setiap baris.
    3. Mengelompokkan hasil pencocokan (Matched, Unmatched, Ambiguous).
    """
    if not chat_data or not chat_data.strip():
        raise ValueError("Teks chat kosong. Silakan masukkan data chat terlebih dahulu.")

    original_lines = [line + "\n" for line in chat_data.splitlines()]

    # Baris pertama non-kosong sebagai nama wilayah
    first_line = next(
        (line.strip() for line in original_lines if line.strip()),
        None
    )
    if first_line:
        region_name = normalize_text(first_line).replace(" ", "_")[:80]
    else:
        region_name = "CHAT_REGION"

    updated_lines: List[str] = []
    matched_hospitals: List[Dict[str, Any]] = []
    unmatched_hospitals: List[Dict[str, Any]] = []
    ambiguous_hospitals: List[Dict[str, Any]] = []

    for line_number, line in enumerate(original_lines, start=1):
        updated_line, result = add_hospital_code(line, hospital_master)
        updated_lines.append(updated_line)

        if result:
            if result["status"] == "MATCHED":
                matched_hospitals.append({
                    "line_number": line_number,
                    "original": line.strip(),
                    "updated": updated_line.strip(),
                    "code": result["code"],
                    "alias": result["alias"],
                    "name": result["name"]
                })
            elif result["status"] == "AMBIGUOUS":
                ambiguous_hospitals.append({
                    "line_number": line_number,
                    "hospital": line.strip(),
                    "matches": result["matches"]
                })
        elif line.strip() and is_facility_line(line):
            unmatched_hospitals.append({
                "line_number": line_number,
                "hospital": line.strip()
            })

    unique_matched_aliases = {item["alias"] for item in matched_hospitals}

    return {
        "region_name": region_name,
        "original_lines": original_lines,
        "updated_lines": updated_lines,
        "updated_text": "".join(updated_lines),
        "matched": matched_hospitals,
        "unmatched": unmatched_hospitals,
        "ambiguous": ambiguous_hospitals,
        "summary": {
            "total_lines": len(original_lines),
            "matched_lines": len(matched_hospitals),
            "unmatched_facilities": len(unmatched_hospitals),
            "ambiguous_matches": len(ambiguous_hospitals),
            "unique_aliases": len(unique_matched_aliases),
        }
    }


def generate_txt_export(updated_text: str) -> str:
    """Mengembalikan teks terformat untuk unduhan TXT."""
    return updated_text


def generate_review_report_txt(
    unmatched: List[Dict[str, Any]],
    ambiguous: List[Dict[str, Any]]
) -> str:
    """Membuat laporan teks untuk rumah sakit yang belum ditemukan atau ambigu."""
    lines = [
        "UNMATCHED HOSPITALS / FACILITIES",
        "=" * 70,
        ""
    ]
    for item in unmatched:
        lines.append(f"Line {item['line_number']}: {item['hospital']}")

    lines.extend([
        "",
        "AMBIGUOUS MATCHES",
        "=" * 70,
        ""
    ])
    for item in ambiguous:
        lines.append(f"Line {item['line_number']}: {item['hospital']}")
        for m in item["matches"]:
            lines.append(f"    Alias: {m['alias']}")
            lines.append(f"    Code : {m['code']}")

    return "\n".join(lines)


def generate_excel_export(process_result: Dict[str, Any]) -> Tuple[Optional[bytes], Optional[str]]:
    """
    Membuat file Excel terstruktur dalam bentuk byte buffer in-memory.
    Menghasilkan multiple sheets:
    - Sheet 1: Hasil Chat Terkode
    - Sheet 2: Fasilitas Belum Terdaftar (Unmatched)
    - Sheet 3: Kecocokan Ambigu (Ambiguous)
    """
    try:
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine="openpyxl") as writer:
            # Sheet 1: Ringkasan & Hasil Chat
            lines_data = []
            matched_by_line = {m["line_number"]: m for m in process_result["matched"]}

            for idx, line in enumerate(process_result["original_lines"], start=1):
                match_info = matched_by_line.get(idx)
                lines_data.append({
                    "Baris": idx,
                    "Chat Asli": line.strip(),
                    "Chat Berkode": process_result["updated_lines"][idx - 1].strip(),
                    "Status": "MATCHED" if match_info else "TIDAK BERUBAH",
                    "Kode Unik": match_info["code"] if match_info else "",
                    "Nama Resmi RS": match_info["name"] if match_info else "",
                    "Alias Cocok": match_info["alias"] if match_info else ""
                })

            df_chat = pd.DataFrame(lines_data)
            df_chat.to_excel(writer, sheet_name="Hasil Chat", index=False)

            # Sheet 2: Unmatched
            if process_result["unmatched"]:
                df_unmatched = pd.DataFrame([
                    {"Baris": u["line_number"], "Teks Fasilitas": u["hospital"]}
                    for u in process_result["unmatched"]
                ])
                df_unmatched.to_excel(writer, sheet_name="Fasilitas Belum Cocok", index=False)

            # Sheet 3: Ambiguous
            if process_result["ambiguous"]:
                amb_rows = []
                for a in process_result["ambiguous"]:
                    for m in a["matches"]:
                        amb_rows.append({
                            "Baris": a["line_number"],
                            "Teks Baris": a["hospital"],
                            "Alias Ditemukan": m.get("alias", ""),
                            "Kode Unik": m.get("code", ""),
                            "Nama Resmi": m.get("name", "")
                        })
                df_ambiguous = pd.DataFrame(amb_rows)
                df_ambiguous.to_excel(writer, sheet_name="Kecocokan Ambigu", index=False)

        return output.getvalue(), None
    except Exception as e:
        return None, str(e)
