import streamlit as st
import pandas as pd
import re
from datetime import datetime
from sqlalchemy import create_engine
import io

try:
    import pdfplumber
except ImportError:
    st.error("⚠️ Pustaka pdfplumber belum terinstal. Pastikan file requirements.txt sudah di-update dan tunggu server Streamlit selesai proses 'Rebooting'.")

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

# --- MESIN PISAU PYTHON (PDFPLUMBER SUPER PARSER) ---
def parse_pdf_rkakl(file_bytes):
    text = ""
    # pdfplumber membuka file byte dan menjaga struktur jarak (spasi) antar kolom
    with pdfplumber.open(file_bytes) as pdf:
        for page in pdf.pages:
            # x_tolerance=2 memastikan teks yang terpisah kolom akan diberi spasi
            page_text = page.extract_text(x_tolerance=2)
            if page_text:
                text += page_text + "\n"

    lines = text.split('\n')
    extracted_data = []
    debug_logs = []
    
    curr_keg_name = "Kegiatan Default"
    curr_akun_code = "000000"
    curr_akun_name = "Akun Tidak Dikenal"
    buffer_text = ""

    def process_buffer(b_text, keg, a_code, a_name):
        # 1. Bersihkan sisa teks BOPTN/PNBP di ekor agar angka tidak terhalang
        clean_text = re.sub(r'\b(BOPTN|PNBP)\b', '', b_text, flags=re.IGNORECASE).strip()

        # 2. Pola Cerdas: Cari 3 deret angka berurutan di mana saja pada ujung kalimat
        num_pattern = r'((?:\d{1,3}(?:[.,]\d{3})*|\d+))'
        pattern = rf'(.*?)\s+{num_pattern}\s+{num_pattern}\s+{num_pattern}\s*$'
        match = re.search(pattern, clean_text)
        
        if not match: 
            debug_logs.append(f"❌ GAGAL (Tidak Ditemukan 3 Angka): {clean_text}")
            return None
            
        uraian_full = match.group(1).strip()
        vol_str = match.group(2).replace(',', '').replace('.', '')
        hrg_str = match.group(3).replace(',', '').replace('.', '')
        tot_str = match.group(4).replace(',', '').replace('.', '')

        if not (vol_str.isdigit() and hrg_str.isdigit() and tot_str.isdigit()):
            debug_logs.append(f"❌ GAGAL (Format Angka Invalid): {vol_str} | {hrg_str} | {tot_str}")
            return None
            
        total = int(tot_str)
        harga = int(hrg_str)
        
        # 3. Potong buang Grup Belanja (sebelum tanda titik dua)
        if ":" in uraian_full:
            uraian_full = uraian_full.split(":", 1)[1].strip()

        # 4. Tarik teks satuan dalam [...] meskipun kurung tutupnya hilang di PDF
        satuan_teks = ""
        match_sat = re.search(r"\[(.*?)(?:\]|$)", uraian_full)
        if match_sat:
            satuan_teks = re.sub(r'\bFIB\b', '', match_sat.group(1)).strip()
            uraian_full = re.sub(r"\[.*?(?:\]|$)", "", uraian_full).strip()

        uraian_full = re.sub(r'\bFIB\b', '', uraian_full).strip("- ")

        # 5. Pecah Satuan dengan pendeteksi huruf 'x'
        v1, s1, v2, s2 = 1, "Unit", 1, "-"
        if satuan_teks:
            if " x " in satuan_teks.lower() or " X " in satuan_teks:
                parts = re.split(r"(?i)\s+x\s+", satuan_teks)
                
                p1 = parts[0].strip().split(maxsplit=1)
                if len(p1) >= 1 and p1[0].isdigit(): v1 = int(p1[0])
                if len(p1) == 2: s1 = p1[1].title()
                elif len(p1) == 1: s1 = "Layanan"
                
                p2 = parts[1].strip().split(maxsplit=1)
                if len(p2) >= 1 and p2[0].isdigit(): v2 = int(p2[0])
                if len(p2) == 2: s2 = p2[1].title()
                elif len(p2) == 1: s2 = "Layanan"
            else:
                p1 = satuan_teks.strip().split(maxsplit=1)
                if len(p1) >= 1 and p1[0].isdigit(): v1 = int(p1[0])
                if len(p1) == 2: s1 = p1[1].title()
                elif len(p1) == 1: s1 = "Layanan"

        debug_logs.append(f"✅ SUKSES: {uraian_full} || {v1} {s1} x {v2} {s2} || Rp{harga} || Rp{total}")
        return {
            "Kegiatan": keg, "Akun_Code": a_code, "Akun_Name": a_name,
            "Uraian": uraian_full, "Vol_1": v1, "Sat_1": s1, "Vol_2": v2, "Sat_2": s2,
            "Harga_Satuan": harga, "Total_Biaya": total
        }

    for line in lines:
        line = line.strip()
        if not line: continue

        # Deteksi Header Akun
        match_akun = re.match(r"^(\d{6})\s+(.*)", line)
        if match_akun:
            curr_akun_code = match_akun.group(1)
            curr_akun_name = re.sub(r"[\d\.,]+\s*(BOPTN|PNBP)?$", "", match_akun.group(2)).strip()
            continue
            
        # Deteksi Header Kegiatan
        match_keg = re.match(r"^(\d{4})\s+(.*)", line)
        if match_keg:
            if not match_keg.group(2).lower().startswith("penyediaan"):
                curr_keg_name = re.sub(r"[\d\.,]+\s*$", "", match_keg.group(2)).strip()
            continue

        if line.startswith("-"):
            if buffer_text:
                res = process_buffer(buffer_text, curr_keg_name, curr_akun_code, curr_akun_name)
                if res: extracted_data.append(res)
            buffer_text = line
        elif buffer_text and not re.match(r"^(\d{6}|\d{4}|[A-Z]|\d{3})\b", line):
            buffer_text += " " + line
            
    if buffer_text:
        res = process_buffer(buffer_text, curr_keg_name, curr_akun_code, curr_akun_name)
        if res: extracted_data.append(res)

    return pd.DataFrame(extracted_data), debug_logs

# --- TAMPILAN ANTARMUKA (UI) ---
def show_page():
    st.title("📥 Mesin Ekstraksi RKAKL Otomatis")
    st.caption("Unggah PDF RKAKL dari sistem Universitas. Sistem menggunakan pdfplumber untuk memecah dan menyusunnya menjadi database RAB.")

    if 'ekstrak_result' not in st.session_state:
        st.session_state.ekstrak_result = pd.DataFrame()
    if 'ekstrak_log' not in st.session_state:
        st.session_state.ekstrak_log = []

    with st.container(border=True):
        st.subheader("1. Setup Target Injeksi")
        col1, col2, col3 = st.columns(3)
        thn_target = col1.text_input("Tahun Anggaran", value=str(datetime.now().year + 1))
        ver_target = col2.selectbox("Versi RKA", ["Indikatif", "Definitif", "Revisi 1", "Revisi 2"])
        sumber_dana = col3.radio("Sumber Dana", ["BOPTN", "PNBP"], horizontal=True)

        file_pdf = st.file_uploader("2. Unggah Dokumen PDF RKAKL", type=['pdf'])
        
        if st.button("🚀 Ekstrak Dokumen Sekarang", type="primary"):
            if file_pdf:
                with st.spinner("Menganalisis hirarki dan menjahit teks dengan pdfplumber..."):
                    df_hasil, log_debug = parse_pdf_rkakl(file_pdf)
                    st.session_state.ekstrak_log = log_debug
                    
                    if not df_hasil.empty:
                        st.session_state.ekstrak_result = df_hasil
                        st.success(f"Berhasil mengekstrak {len(df_hasil)} baris rincian belanja!")
                    else:
                        st.error("❌ Gagal mengekstrak rincian belanja. Silakan cek 'Log Debug Mesin' di bawah untuk melihat penyebabnya.")
            else:
                st.error("Harap unggah file PDF terlebih dahulu.")

    if st.session_state.ekstrak_log:
        with st.expander("🛠️ Log Debug Mesin (Untuk Analisis Error)"):
            for log in st.session_state.ekstrak_log:
                if log.startswith("✅"): st.success(log)
                else: st.warning(log)

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
                    new_id = f"RAB-EXT-{datetime.now().strftime('%Y%m%d%H%M%S%f')}"
                    
                    df_keg_details = df_edit[df_edit['Kegiatan'] == keg_name].copy()
                    total_alokasi = df_keg_details['Total_Biaya'].sum()
                    
                    new_utama = pd.DataFrame([{
                        "ID_RAB": new_id, "Tanggal": datetime.now().strftime('%Y-%m-%d %H:%M'), 
                        "Tahun": thn_target, "Tgl_Cetak": datetime.now().strftime('%Y-%m-%d'),
                        "Sumber_Dana": sumber_dana, "KRO": "-", "RO": "-", "Komponen": "-", "Sub_Komponen": "-",
                        "Kegiatan": keg_name, "Sasaran": "-", "Volume": 1, "Satuan": "Layanan", "Alokasi": total_alokasi,
                        "Jabatan": "Dekan", "Nama_Pejabat": "-", "NIP_Pejabat": "-",
                        "Versi_RAB": ver_target, "Is_Active": 1
                    }])
                    df_rab_utama = pd.concat([df_rab_utama, new_utama], ignore_index=True)
                    
                    df_keg_details['ID_RAB'] = new_id
                    df_keg_details['Akun_Belanja'] = df_keg_details['Akun_Code'] + " - " + df_keg_details['Akun_Name']
                    new_detail = df_keg_details[['ID_RAB', 'Akun_Belanja', 'Uraian', 'Vol_1', 'Sat_1', 'Vol_2', 'Sat_2', 'Harga_Satuan', 'Total_Biaya']]
                    df_rab_detail = pd.concat([df_rab_detail, new_detail], ignore_index=True)
                
                save_table(df_rab_utama, "rab_utama")
                save_table(df_rab_detail, "rab_detail")
                
                st.session_state.ekstrak_result = pd.DataFrame() 
                st.success("🎉 Seluruh data RKAKL berhasil diinjeksi ke dalam sistem RAB Anda!")
                st.rerun()
