import streamlit as st
import pandas as pd
import re
from datetime import datetime
from sqlalchemy import create_engine
import io

try:
    import pdfplumber
except ImportError:
    st.error("⚠️ Pustaka pdfplumber belum terinstal. Pastikan file requirements.txt sudah di-update.")

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

# --- FUNGSI VERIFIKASI MATEMATIKA (V * H = T) ---
def extract_vht(text):
    tokens = text.split()
    for i in range(len(tokens) - 2):
        t1 = tokens[i].replace(',', '').replace('.', '')
        t2 = tokens[i+1].replace(',', '').replace('.', '')
        t3 = tokens[i+2].replace(',', '').replace('.', '')
        
        if t1.isdigit() and t2.isdigit() and t3.isdigit():
            v, h, t = int(t1), int(t2), int(t3)
            if v * h == t and t > 0:
                return v, h, t, f"{tokens[i]} {tokens[i+1]} {tokens[i+2]}"
                
    for i in reversed(range(len(tokens) - 2)):
        t1 = tokens[i].replace(',', '').replace('.', '')
        t2 = tokens[i+1].replace(',', '').replace('.', '')
        t3 = tokens[i+2].replace(',', '').replace('.', '')
        
        if t1.isdigit() and t2.isdigit() and t3.isdigit():
            return int(t1), int(t2), int(t3), f"{tokens[i]} {tokens[i+1]} {tokens[i+2]}"
            
    return None, None, None, None

# --- MESIN PISAU PYTHON ---
def parse_pdf_rkakl(file_bytes):
    text = ""
    with pdfplumber.open(file_bytes) as pdf:
        for page in pdf.pages:
            page_text = page.extract_text(x_tolerance=2)
            if page_text:
                text += page_text + "\n"

    lines = text.split('\n')
    extracted_data = []
    debug_logs = []
    
    curr_kro, curr_ro, curr_komp, curr_subkomp = "-", "-", "-", "-"
    curr_keg_name, curr_akun_code, curr_akun_name = "Kegiatan Default", "000000", "Akun Tidak Dikenal"
    
    buffer_text = ""

    def process_buffer(b_text, kro, ro, komp, sub, keg, a_code, a_name):
        garbage_phrases = [
            r"KODE\s+PROGRAM/KEGIATAN.*?(?=\s|$)", r"KOMPONEN/SUBKOMP.*?(?=\s|$)",
            r"VOLUME\s+HARGA\s+SATUAN.*?(?=\s|$)", r"TAHUN\s+SUMBER", r"TARGET",
            r"\(\d\)\s*\(\d\)\s*\(\d\)\s*\(\d\)\s*\(\d\)\s*\(\d\)", r"TOTAL\s+[\d\.,]+",
            r"Samarinda,\s+\d+\s+[A-Za-z]+\s+\d+", r"Dekan,", r"Prof\.\s+Dr\..*", r"NIP\.\s*[\d-]+"
        ]
        for g in garbage_phrases:
            b_text = re.sub(g, "", b_text, flags=re.IGNORECASE)

        clean_text = re.sub(r'\b(BOPTN|PNBP|BLU)\b', '', b_text, flags=re.IGNORECASE)
        clean_text = re.sub(r'\s+', ' ', clean_text).strip()
        
        vol, hrg, tot, matched_str = extract_vht(clean_text)
        
        if vol is None:
            if clean_text: debug_logs.append(f"❌ GAGAL (Tdk Ditemukan Angka): {clean_text}")
            return None
            
        clean_text = clean_text.replace(matched_str, " ")
        clean_text = re.sub(r'\s+', ' ', clean_text).strip()
        
        uraian_full = clean_text
        if ":" in uraian_full:
            uraian_full = uraian_full.split(":", 1)[1].strip()

        satuan_teks = ""
        match_sat = re.search(r"\[(.*?)\]", uraian_full)
        if match_sat:
            satuan_teks = match_sat.group(1)
            uraian_full = uraian_full.replace(f"[{satuan_teks}]", "")
        else:
            match_sat_open = re.search(r"\[(.*)", uraian_full)
            if match_sat_open:
                satuan_teks = match_sat_open.group(1)
                uraian_full = uraian_full.split("[")[0]

        uraian_full = re.sub(r'\bFIB\b', '', uraian_full, flags=re.IGNORECASE).strip(" -[]")
        satuan_teks = re.sub(r'\bFIB\b', '', satuan_teks, flags=re.IGNORECASE).strip(" -[]")

        v1, s1, v2, s2 = vol, "Layanan", 1, "-"
        if satuan_teks:
            if " x " in satuan_teks.lower() or " X " in satuan_teks:
                parts = re.split(r"(?i)\s+x\s+", satuan_teks)
                p1 = parts[0].strip().split(maxsplit=1)
                if len(p1) >= 1 and p1[0].isdigit(): v1 = int(p1[0])
                if len(p1) == 2: s1 = p1[1].title()
                
                p2 = parts[1].strip().split(maxsplit=1)
                if len(p2) >= 1 and p2[0].isdigit(): v2 = int(p2[0])
                if len(p2) == 2: s2 = p2[1].title()
            else:
                p1 = satuan_teks.strip().split(maxsplit=1)
                if len(p1) >= 1 and p1[0].isdigit(): v1 = int(p1[0])
                if len(p1) == 2: s1 = p1[1].title()
                
        if v1 * v2 != vol: 
            v1, v2, s2 = vol, 1, "-"

        debug_logs.append(f"✅ SUKSES: {uraian_full}")
        return {
            "KRO": kro, "RO": ro, "Komponen": komp, "Sub_Komponen": sub,
            "Kegiatan": keg, "Akun_Code": a_code, "Akun_Name": a_name,
            "Uraian": uraian_full, "Vol_1": v1, "Sat_1": s1, "Vol_2": v2, "Sat_2": s2,
            "Harga_Satuan": hrg, "Total_Biaya": tot
        }

    def flush_buffer():
        nonlocal buffer_text
        if buffer_text:
            res = process_buffer(buffer_text, curr_kro, curr_ro, curr_komp, curr_subkomp, curr_keg_name, curr_akun_code, curr_akun_name)
            if res: extracted_data.append(res)
            buffer_text = ""

    for line in lines:
        line = line.strip()
        if not line: continue

        if re.match(r"^(KODE|PROGRAM/KEGIATAN|KOMPONEN|VOLUME|\(\d\)|TOTAL|Samarinda|Dekan|Prof\.|NIP\.)", line, re.IGNORECASE):
            continue

        match_kode = re.match(r"^([^\s]+)\s+(.*)", line)
        if match_kode:
            kode = match_kode.group(1)
            desc = re.sub(r"[\d\.,]+\s*(BOPTN|PNBP)?$", "", match_kode.group(2)).strip()
            
            is_valid_kode = False
            if re.match(r"^\d{6}$", kode): is_valid_kode = True
            elif re.match(r"^\d{4}$", kode): is_valid_kode = True
            elif re.match(r"^\d{3}$", kode): is_valid_kode = True
            elif re.match(r"^[A-Z]$", kode): is_valid_kode = True
            elif re.match(r"^\d{4}\.[A-Z0-9]{1,3}$", kode): is_valid_kode = True
            elif re.match(r"^\d{4}\.[A-Z0-9]{1,3}\.\d{1,3}$", kode): is_valid_kode = True

            if is_valid_kode:
                flush_buffer() 
                if re.match(r"^\d{6}$", kode):
                    curr_akun_code = kode
                    curr_akun_name = desc
                elif re.match(r"^\d{4}$", kode):
                    if not desc.lower().startswith("penyediaan"):
                        curr_keg_name = desc
                elif re.match(r"^\d{3}$", kode):
                    curr_komp = f"{kode} - {desc}"
                elif re.match(r"^[A-Z]$", kode):
                    curr_subkomp = f"{kode} - {desc}"
                elif re.match(r"^\d{4}\.[A-Z0-9]{1,3}$", kode):
                    curr_kro = f"{kode} - {desc}"
                elif re.match(r"^\d{4}\.[A-Z0-9]{1,3}\.\d{1,3}$", kode):
                    curr_ro = f"{kode} - {desc}"
                continue

        if line.startswith("-"):
            flush_buffer() 
            buffer_text = line
        elif buffer_text:
            buffer_text += " " + line
            
    flush_buffer() 

    df_hasil = pd.DataFrame(extracted_data)
    if not df_hasil.empty:
        df_hasil = df_hasil.drop_duplicates(subset=['Kegiatan', 'Akun_Code', 'Uraian', 'Total_Biaya'], keep='first').reset_index(drop=True)

    return df_hasil, debug_logs

# --- TAMPILAN ANTARMUKA (UI) ---
def show_page():
    st.title("📥 Mesin Ekstraksi RKAKL Otomatis")
    st.caption("Unggah PDF RKAKL dari sistem Universitas. Sistem ini dilengkapi fitur Anti-Bocor Halaman dan Vakum Duplikat.")

    if 'ekstrak_result' not in st.session_state:
        st.session_state.ekstrak_result = pd.DataFrame()
    if 'ekstrak_log' not in st.session_state:
        st.session_state.ekstrak_log = []

    with st.container(border=True):
        st.subheader("1. Setup Target Injeksi")
        col1, col2, col3 = st.columns(3)
        thn_target = col1.text_input("Tahun Anggaran", value=str(datetime.now().year + 1))
        ver_target = col2.selectbox("Versi RKA", ["Transisi","Indikatif", "Definitif", "Revisi 1", "Revisi 2", "Revisi 3"])
        sumber_dana = col3.radio("Sumber Dana", ["BOPTN", "PNBP"], horizontal=True)

        file_pdf = st.file_uploader("2. Unggah Dokumen PDF RKAKL", type=['pdf'])
        
        if st.button("🚀 Ekstrak Dokumen Sekarang", type="primary"):
            if file_pdf:
                with st.spinner("Menganalisis hirarki, mencegah kebocoran, & memverifikasi matematika teks..."):
                    df_hasil, log_debug = parse_pdf_rkakl(file_pdf)
                    st.session_state.ekstrak_log = log_debug
                    
                    if not df_hasil.empty:
                        st.session_state.ekstrak_result = df_hasil
                        st.success(f"Berhasil mengekstrak {len(df_hasil)} baris rincian belanja bersih tanpa duplikat!")
                    else:
                        st.error("❌ Gagal mengekstrak rincian belanja. Cek Log Debug Mesin.")
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
        st.info("Periksa hasil bacaan mesin di bawah ini. Tidak akan ada lagi rincian yang terduplikasi secara gaib.")
        
        cols_order = ['KRO', 'RO', 'Komponen', 'Sub_Komponen', 'Kegiatan', 'Akun_Code', 'Akun_Name', 'Uraian', 'Vol_1', 'Sat_1', 'Vol_2', 'Sat_2', 'Harga_Satuan', 'Total_Biaya']
        df_display = st.session_state.ekstrak_result[cols_order]
        
        df_edit = st.data_editor(df_display, num_rows="dynamic", use_container_width=True, height=400)

        if st.button("💾 Konfirmasi & Simpan Permanen ke Database", type="primary", use_container_width=True):
            with st.spinner("Menyuntikkan data & Melakukan Auto-Heal Master..."):
                df_m_kro = load_table("rab_m_kro")
                df_m_ro = load_table("rab_m_ro")
                df_m_komp = load_table("rab_m_komp")
                df_m_sub = load_table("rab_m_subkomp")
                df_m_akun = load_table("rab_m_akun")
                
                for kro_val in df_edit['KRO'].unique():
                    if kro_val != "-" and (df_m_kro.empty or kro_val not in df_m_kro['KRO'].values):
                        df_m_kro = pd.concat([df_m_kro, pd.DataFrame([{"KRO": kro_val, "Sumber_Dana": sumber_dana}])], ignore_index=True)
                save_table(df_m_kro, "rab_m_kro")
                
                ro_unik = df_edit[['KRO', 'RO']].drop_duplicates()
                for _, r in ro_unik.iterrows():
                    if r['RO'] != "-" and (df_m_ro.empty or r['RO'] not in df_m_ro['RO'].values):
                        df_m_ro = pd.concat([df_m_ro, pd.DataFrame([{"KRO": r['KRO'], "RO": r['RO'], "Sumber_Dana": sumber_dana}])], ignore_index=True)
                save_table(df_m_ro, "rab_m_ro")

                komp_unik = df_edit[['RO', 'Komponen']].drop_duplicates()
                for _, r in komp_unik.iterrows():
                    if r['Komponen'] != "-" and (df_m_komp.empty or r['Komponen'] not in df_m_komp['Komponen'].values):
                        df_m_komp = pd.concat([df_m_komp, pd.DataFrame([{"RO": r['RO'], "Komponen": r['Komponen'], "Sumber_Dana": sumber_dana}])], ignore_index=True)
                save_table(df_m_komp, "rab_m_komp")

                sub_unik = df_edit[['Komponen', 'Sub_Komponen']].drop_duplicates()
                for _, r in sub_unik.iterrows():
                    if r['Sub_Komponen'] != "-" and (df_m_sub.empty or r['Sub_Komponen'] not in df_m_sub['Sub_Komponen'].values):
                        df_m_sub = pd.concat([df_m_sub, pd.DataFrame([{"Komponen": r['Komponen'], "Sub_Komponen": r['Sub_Komponen'], "Sumber_Dana": sumber_dana}])], ignore_index=True)
                save_table(df_m_sub, "rab_m_subkomp")

                akun_unik = df_edit[['Sub_Komponen', 'Akun_Code', 'Akun_Name']].drop_duplicates()
                akun_baru_list = []
                for _, row in akun_unik.iterrows():
                    if df_m_akun.empty or row['Akun_Code'] not in df_m_akun['Account_Code'].values:
                        akun_baru_list.append({
                            "Sub_Komponen": row['Sub_Komponen'], "Account_Code": row['Akun_Code'], 
                            "Account_Name": row['Akun_Name'], "Sumber_Dana": sumber_dana
                        })
                if akun_baru_list:
                    df_m_akun = pd.concat([df_m_akun, pd.DataFrame(akun_baru_list)], ignore_index=True)
                    save_table(df_m_akun, "rab_m_akun")

                df_rab_utama = load_table("rab_utama")
                df_rab_detail = load_table("rab_detail")
                
                # Cek versi aktif yang sudah ada agar tidak menimpa ganda
                active_vs = df_rab_utama[(df_rab_utama['Tahun'] == thn_target) & (df_rab_utama['Is_Active'] == 1)]['Versi_RAB'].unique()
                is_act = 1 if len(active_vs) == 0 or ver_target in active_vs else 0

                kegiatan_unik = df_edit['Kegiatan'].unique()
                for i, keg_name in enumerate(kegiatan_unik):
                    new_id = f"RAB-EXT-{datetime.now().strftime('%Y%m%d%H%M%S%f')}-{i}"
                    
                    df_keg_details = df_edit[df_edit['Kegiatan'] == keg_name].copy()
                    total_alokasi = df_keg_details['Total_Biaya'].sum()
                    
                    kro_v = df_keg_details['KRO'].iloc[0]
                    ro_v = df_keg_details['RO'].iloc[0]
                    komp_v = df_keg_details['Komponen'].iloc[0]
                    sub_v = df_keg_details['Sub_Komponen'].iloc[0]
                    
                    new_utama = pd.DataFrame([{
                        "ID_RAB": new_id, "Tanggal": datetime.now().strftime('%Y-%m-%d %H:%M'), 
                        "Tahun": thn_target, "Tgl_Cetak": datetime.now().strftime('%Y-%m-%d'),
                        "Sumber_Dana": sumber_dana, "KRO": kro_v, "RO": ro_v, "Komponen": komp_v, "Sub_Komponen": sub_v,
                        "Kegiatan": keg_name, "Sasaran": "-", "Volume": 1, "Satuan": "Layanan", "Alokasi": total_alokasi,
                        "Jabatan": "Dekan", "Nama_Pejabat": "-", "NIP_Pejabat": "-",
                        "Versi_RAB": ver_target, "Is_Active": is_act # LOGIKA AKTIF DIPERBAIKI DI SINI
                    }])
                    df_rab_utama = pd.concat([df_rab_utama, new_utama], ignore_index=True)
                    
                    df_keg_details['ID_RAB'] = new_id
                    df_keg_details['Akun_Belanja'] = df_keg_details['Akun_Code'] + " - " + df_keg_details['Akun_Name']
                    new_detail = df_keg_details[['ID_RAB', 'Akun_Belanja', 'Uraian', 'Vol_1', 'Sat_1', 'Vol_2', 'Sat_2', 'Harga_Satuan', 'Total_Biaya']]
                    df_rab_detail = pd.concat([df_rab_detail, new_detail], ignore_index=True)
                
                save_table(df_rab_utama, "rab_utama")
                save_table(df_rab_detail, "rab_detail")
                
                st.session_state.ekstrak_result = pd.DataFrame() 
                st.success("🎉 Dokumen RKAKL berhasil diinjeksi bersih tanpa merusak status aktif!")
                st.rerun()
