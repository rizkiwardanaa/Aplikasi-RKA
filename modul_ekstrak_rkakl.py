import streamlit as st
import pandas as pd
import re
from datetime import datetime
from sqlalchemy import create_engine
import io

try:
    import PyPDF2
except ImportError:
    st.error("⚠️ Pustaka PyPDF2 belum terinstal. Silakan buka terminal/CMD dan ketik: pip install PyPDF2")

# --- KONEKSI DATABASE ---
DB_URL = st.secrets["DB_URL"]
engine = create_engine(DB_URL, pool_size=5, max_overflow=10)

def load_table(table_name):
    try:
        return pd.read_sql(f"SELECT * FROM {table_name}", engine)
    except:
        return pd.DataFrame()

def save_table(df, table_name):
    with engine.connect() as conn:
        df.to_sql(table_name, conn, if_exists="replace", index=False)
    st.cache_data.clear()

# --- MESIN PISAU PYTHON (PARSER) ---
def parse_pdf_rkakl(file_bytes):
    reader = PyPDF2.PdfReader(file_bytes)
    text = ""
    for page in reader.pages:
        text += page.extract_text() + "\n"

    lines = text.split('\n')
    extracted_data = []
    
    # State Memory (Ingatan Mesin)
    curr_keg_name, curr_akun_code, curr_akun_name = "", "", ""
    buffer_text = ""

    def process_buffer(b_text, keg, a_code, a_name):
        tokens = b_text.split()
        if len(tokens) < 4: return None

        # Ekstrak 3 Angka Terakhir (Volume, Harga, Total)
        tot_str = tokens[-1].replace(',', '').replace('.', '')
        hrg_str = tokens[-2].replace(',', '').replace('.', '')
        vol_str = tokens[-3].replace(',', '').replace('.', '')

        if tot_str.isdigit() and hrg_str.isdigit() and vol_str.isdigit():
            uraian_full = " ".join(tokens[:-3])
            total = int(tot_str)
            harga = int(hrg_str)
        else:
            return None # Bukan baris rincian yang valid

        # Pisau 1: Buang Grup Belanja (sebelum tanda :)
        if ":" in uraian_full:
            uraian_full = uraian_full.split(":", 1)[1].strip()

        # Pisau 2: Tarik Satuan dalam [...]
        satuan_teks = ""
        match = re.search(r"\[(.*?)\]", uraian_full)
        if match:
            satuan_teks = match.group(1)
            uraian_full = re.sub(r"\[.*?\]", "", uraian_full).strip()

        uraian_full = uraian_full.strip("- ").replace("FIB", "").strip()

        # Pisau 3: Pecah Volume & Satuan (mencari tanda 'x')
        v1, s1, v2, s2 = 1, "Unit", 1, "-"
        if " x " in satuan_teks.lower() or " X " in satuan_teks:
            parts = re.split(r"(?i)\s+x\s+", satuan_teks)
            p1 = parts[0].strip().split(maxsplit=1)
            if len(p1) == 2 and p1[0].isdigit(): v1, s1 = int(p1[0]), p1[1].title()
            p2 = parts[1].strip().split(maxsplit=1)
            if len(p2) == 2 and p2[0].isdigit(): v2, s2 = int(p2[0]), p2[1].title()
        else:
            p1 = satuan_teks.strip().split(maxsplit=1)
            if len(p1) == 2 and p1[0].isdigit(): v1, s1 = int(p1[0]), p1[1].title()

        return {
            "Kegiatan": keg, "Akun_Code": a_code, "Akun_Name": a_name,
            "Uraian": uraian_full, "Vol_1": v1, "Sat_1": s1, "Vol_2": v2, "Sat_2": s2,
            "Harga_Satuan": harga, "Total_Biaya": total
        }

    for line in lines:
        line = line.strip()
        if not line: continue

        # Deteksi Header/Hirarki
        tokens = line.split(maxsplit=1)
        kode = tokens[0]
        desc = tokens[1] if len(tokens) > 1 else ""

        if re.match(r"^\d{6}$", kode):  # Deteksi Akun (Cth: 524119)
            curr_akun_code = kode
            curr_akun_name = re.sub(r"[\d\.,]+\s*(BOPTN|PNBP)?$", "", desc).strip()
            continue
        elif re.match(r"^\d{4}$", kode):  # Deteksi Kegiatan (Cth: 0089)
            if not desc.lower().startswith("penyediaan"): 
                curr_keg_name = re.sub(r"[\d\.,]+\s*$", "", desc).strip()
            continue
            
        # Deteksi Baris Rincian Belanja (Diawali '-')
        if line.startswith("-"):
            if buffer_text:
                res = process_buffer(buffer_text, curr_keg_name, curr_akun_code, curr_akun_name)
                if res: extracted_data.append(res)
            buffer_text = line
        elif buffer_text and not re.match(r"^(\d{6}|\d{4}|[A-Z]|\d{3})\b", line):
            # Teks turun baris (Text Wrapping) -> Jahit!
            buffer_text += " " + line
            
    # Proses buffer terakhir
    if buffer_text:
        res = process_buffer(buffer_text, curr_keg_name, curr_akun_code, curr_akun_name)
        if res: extracted_data.append(res)

    return pd.DataFrame(extracted_data)


# --- TAMPILAN ANTARMUKA (UI) ---
def show_page():
    st.title("📥 Mesin Ekstraksi RKAKL Otomatis")
    st.caption("Unggah PDF RKAKL dari sistem Universitas. Sistem akan membaca, memecah, dan menyusunnya menjadi database RAB dalam 2 detik.")

    if 'ekstrak_result' not in st.session_state:
        st.session_state.ekstrak_result = pd.DataFrame()

    with st.container(border=True):
        st.subheader("1. Setup Target Injeksi")
        col1, col2, col3 = st.columns(3)
        thn_target = col1.text_input("Tahun Anggaran", value=str(datetime.now().year + 1))
        ver_target = col2.selectbox("Versi RKA", ["Indikatif", "Definitif", "Revisi 1", "Revisi 2"])
        sumber_dana = col3.radio("Sumber Dana", ["BOPTN", "PNBP"], horizontal=True)

        file_pdf = st.file_uploader("2. Unggah Dokumen PDF RKAKL", type=['pdf'])
        
        if st.button("🚀 Ekstrak Dokumen Sekarang", type="primary"):
            if file_pdf:
                with st.spinner("Menganalisis hirarki dan menjahit teks..."):
                    df_hasil = parse_pdf_rkakl(file_pdf)
                    if not df_hasil.empty:
                        st.session_state.ekstrak_result = df_hasil
                        st.success(f"Berhasil mengekstrak {len(df_hasil)} baris rincian belanja!")
                    else:
                        st.error("Gagal mengekstrak. Pastikan format PDF sesuai dengan standar RKA.")
            else:
                st.error("Harap unggah file PDF terlebih dahulu.")

    if not st.session_state.ekstrak_result.empty:
        st.markdown("---")
        st.subheader("3. Ruang Karantina (Preview Data)")
        st.info("Silakan periksa hasil bacaan mesin di bawah ini. Anda bisa mengedit teksnya langsung jika ada kesalahan baca (typo) sebelum disimpan permanen.")
        
        df_edit = st.data_editor(st.session_state.ekstrak_result, num_rows="dynamic", use_container_width=True, height=400)

        if st.button("💾 Konfirmasi & Simpan Permanen ke Database", type="primary", use_container_width=True):
            with st.spinner("Menyuntikkan data ke server..."):
                # 1. AUTO-HEAL MASTER AKUN
                df_m_akun = load_table("rab_m_akun")
                akun_unik = df_edit[['Akun_Code', 'Akun_Name']].drop_duplicates()
                akun_baru_list = []
                for _, row in akun_unik.iterrows():
                    if df_m_akun.empty or row['Akun_Code'] not in df_m_akun['Account_Code'].values:
                        akun_baru_list.append({
                            "Sub_Komponen": "-", "Account_Code": row['Akun_Code'], 
                            "Account_Name": row['Akun_Name'], "Sumber_Dana": sumber_dana
                        })
                if akun_baru_list:
                    df_m_akun = pd.concat([df_m_akun, pd.DataFrame(akun_baru_list)], ignore_index=True)
                    save_table(df_m_akun, "rab_m_akun")
                    st.toast(f"Auto-Heal: {len(akun_baru_list)} Akun baru otomatis ditambahkan ke Master!")

                # 2. INJEKSI KE RAB_UTAMA & RAB_DETAIL
                df_rab_utama = load_table("rab_utama")
                df_rab_detail = load_table("rab_detail")
                
                kegiatan_unik = df_edit['Kegiatan'].unique()
                for keg_name in kegiatan_unik:
                    # Generate ID unik untuk setiap kegiatan
                    new_id = f"RAB-EXT-{datetime.now().strftime('%Y%m%d%H%M%S%f')}"
                    
                    df_keg_details = df_edit[df_edit['Kegiatan'] == keg_name].copy()
                    total_alokasi = df_keg_details['Total_Biaya'].sum()
                    
                    # Entry ke RAB Utama
                    new_utama = pd.DataFrame([{
                        "ID_RAB": new_id, "Tanggal": datetime.now().strftime('%Y-%m-%d %H:%M'), 
                        "Tahun": thn_target, "Tgl_Cetak": datetime.now().strftime('%Y-%m-%d'),
                        "Sumber_Dana": sumber_dana, "KRO": "-", "RO": "-", "Komponen": "-", "Sub_Komponen": "-",
                        "Kegiatan": keg_name, "Sasaran": "-", "Volume": 1, "Satuan": "Layanan", "Alokasi": total_alokasi,
                        "Jabatan": "Dekan", "Nama_Pejabat": "-", "NIP_Pejabat": "-",
                        "Versi_RAB": ver_target, "Is_Active": 1
                    }])
                    df_rab_utama = pd.concat([df_rab_utama, new_utama], ignore_index=True)
                    
                    # Entry ke RAB Detail
                    df_keg_details['ID_RAB'] = new_id
                    df_keg_details['Akun_Belanja'] = df_keg_details['Akun_Code'] + " - " + df_keg_details['Akun_Name']
                    new_detail = df_keg_details[['ID_RAB', 'Akun_Belanja', 'Uraian', 'Vol_1', 'Sat_1', 'Vol_2', 'Sat_2', 'Harga_Satuan', 'Total_Biaya']]
                    df_rab_detail = pd.concat([df_rab_detail, new_detail], ignore_index=True)
                
                save_table(df_rab_utama, "rab_utama")
                save_table(df_rab_detail, "rab_detail")
                
                st.session_state.ekstrak_result = pd.DataFrame() # Bersihkan karantina
                st.success("🎉 Seluruh data RKAKL berhasil diinjeksi ke dalam sistem RAB Anda!")
                st.rerun()
