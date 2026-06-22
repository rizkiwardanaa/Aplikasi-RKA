import streamlit as st
import pandas as pd
import re
from datetime import datetime
from utils import load_table, save_table, update_rab_tahun, log_audit, format_rupiah

try:
    import pdfplumber
except ImportError:
    st.error("⚠️ Pustaka pdfplumber belum terinstal. Pastikan file requirements.txt sudah di-update.")

# --- FUNGSI PEMISAH KODE UNTUK SINKRONISASI MASTER ---
def split_kd(teks):
    s = str(teks).strip()
    if " - " in s:
        return s.split(" - ", 1)[0].strip()
    if re.match(r"^[A-Z]\.\s+", s):
        return s.split(".", 1)[0].strip()
    if re.match(r"^[A-Z]\s+", s):
        return s.split(" ", 1)[0].strip()
    return s

# --- FUNGSI VERIFIKASI MATEMATIKA (V * H = T) ---
def extract_vht(text):
    tokens = text.split()
    for i in reversed(range(len(tokens) - 2)):
        t1 = tokens[i].replace(',', '').replace('.', '')
        t2 = tokens[i+1].replace(',', '').replace('.', '')
        t3 = tokens[i+2].replace(',', '').replace('.', '')
        
        if t1.isdigit() and t2.isdigit() and t3.isdigit():
            v, h, t = int(t1), int(t2), int(t3)
            if v * h == t and t > 0:
                return v, h, t, f"{tokens[i]} {tokens[i+1]} {tokens[i+2]}"
                
    return None, None, None, None

# --- MESIN PISAU PYTHON (LEAK-PROOF PARSER) ---
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
    
    # State Memory untuk Hirarki
    curr_kro = "-"
    curr_ro = "-"
    curr_komp = "-"
    curr_subkomp = "-"
    curr_keg_name = "Kegiatan Default"
    curr_akun_code = "000000"
    curr_akun_name = "Akun Tidak Dikenal"
    
    buffer_text = ""

    def process_buffer(b_text, kro, ro, komp, sub, keg, a_code, a_name):
        garbage_phrases = [
            r"KODE\s+PROGRAM/KEGIATAN.*?(?=\s|$)", r"KOMPONEN/SUBKOMP.*?(?=\s|$)",
            r"VOLUME\s+HARGA\s+SATUAN.*?(?=\s|$)", r"TAHUN\s+SUMBER", r"TARGET",
            r"\(\d\)\s*\(\d\)\s*\(\d\)\s*\(\d\)\s*\(\d\)\s*\(\d\)", r"TOTAL\s+[\d\.,]+",
            r"Samarinda,\s+\d+\s+[A-Za-z]+\s+\d+", r"Dekan,?", r"Prof\.\s+Dr\..*", r"NIP\.\s*[\d-]+",
            r"\bM\.Hum\.?", r"\bS\.S\.,?", r"\bPh\.D\.?", r"\bM\.Kom\.?", r"\bS\.Kom\.?", 
            r"\bS\.E\.,?", r"\bM\.E\.?", r"\bM\.Si\.?", r"\bS\.Si\.,?", r"\bM\.A\.?"
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
        uraian_full = re.sub(r'\s+', ' ', clean_text).strip()
        
        uraian_full = uraian_full.replace("[]", "").replace("[-]", "").replace("[ - ]", "")
        uraian_full = re.sub(r'^[-—*•>\uf0b7\s]+', '', uraian_full).strip()
        
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

        uraian_full = re.sub(r'\bFIB\b', '', uraian_full, flags=re.IGNORECASE)
        uraian_full = uraian_full.strip(" -:")
        
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
                
        if v1 * v2 != vol: v1, v2, s2 = vol, 1, "-"

        debug_logs.append(f"✅ SUKSES: {uraian_full} | Vol: {satuan_teks}")
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

        if "|" in line or "JAM]" in line: continue

        if re.match(r"^(KODE|PROGRAM/KEGIATAN|KOMPONEN|VOLUME|\(\d\)|TOTAL|Samarinda|Dekan|Prof\.|NIP\.)", line, re.IGNORECASE):
            continue

        match_kode = re.match(r"^([^\s]+)\s+(.*)", line)
        if match_kode:
            kode = match_kode.group(1)
            desc = re.sub(r"[\d\.,]+\s*(BOPTN|PNBP|BLU)?$", "", match_kode.group(2), flags=re.IGNORECASE).strip()
            
            if re.match(r"^[A-Z]\.$", kode):
                kode = kode[0]

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
                    curr_akun_code = kode; curr_akun_name = desc
                elif re.match(r"^\d{4}$", kode):
                    if not desc.lower().startswith("penyediaan") and kode not in ["7729", "7730"]: 
                        curr_keg_name = desc
                elif re.match(r"^\d{3}$", kode):
                    curr_komp = f"{kode} - {desc}"
                    curr_subkomp = "-"
                elif re.match(r"^[A-Z]$", kode):
                    curr_subkomp = f"{kode} - {desc}"
                elif re.match(r"^\d{4}\.[A-Z0-9]{1,3}$", kode):
                    curr_kro = f"{kode} - {desc}"
                    curr_ro = "-"
                    curr_komp = "-"
                    curr_subkomp = "-"
                elif re.match(r"^\d{4}\.[A-Z0-9]{1,3}\.\d{1,3}$", kode):
                    curr_ro = f"{kode} - {desc}"
                    curr_komp = "-"
                    curr_subkomp = "-"
                continue

        if re.match(r"^([-—*•>]|\uf0b7|\[\]|\[-\])", line):
            flush_buffer() 
            buffer_text = line
        elif line.startswith("["): 
            if buffer_text:
                buffer_text += " " + line
            else:
                buffer_text = line
        elif buffer_text:
            buffer_text += " " + line
        else:
            buffer_text = line
            
    flush_buffer() 

    df_hasil = pd.DataFrame(extracted_data)
    if not df_hasil.empty:
        df_hasil = df_hasil.drop_duplicates(subset=['Kegiatan', 'Akun_Code', 'Uraian', 'Total_Biaya'], keep='first').reset_index(drop=True)

    return df_hasil, debug_logs

# --- TAMPILAN ANTARMUKA (UI) ---
def show_page():
    st.title("📥 Mesin Ekstraksi RKAKL Otomatis")
    st.caption("Unggah PDF RKAKL dari sistem Universitas. (Mode Aman: Master Lock tanpa Auto-Heal).")

    if 'ekstrak_result' not in st.session_state:
        st.session_state.ekstrak_result = pd.DataFrame()
    if 'ekstrak_log' not in st.session_state:
        st.session_state.ekstrak_log = []

    with st.container(border=True):
        st.subheader("1. Setup Target Injeksi")
        col1, col2, col3 = st.columns(3)
        thn_target = col1.text_input("Tahun Anggaran", value=str(datetime.now().year + 1))
        ver_target = col2.selectbox("Versi RKA", ["Transisi","Indikatif", "Definitif", "Revisi 1", "Revisi 2", "Revisi 3", "Revisi 4", "Revisi 5", "Revisi 6", "Revisi 7", "Revisi 8", "Revisi 9", "Revisi 10","Revisi 11","Revisi 12","Revisi 13"])
        sumber_dana = col3.radio("Sumber Dana", ["BOPTN", "PNBP"], horizontal=True)

        file_pdf = st.file_uploader("2. Unggah Dokumen PDF RKAKL", type=['pdf'])
        
        if st.button("🚀 Ekstrak Dokumen Sekarang", type="primary"):
            if file_pdf:
                with st.spinner("Menganalisis & Menyinkronkan Hierarki dengan Master..."):
                    df_hasil, log_debug = parse_pdf_rkakl(file_pdf)
                    st.session_state.ekstrak_log = log_debug
                    
                    if not df_hasil.empty:
                        # --- PENYELARASAN MUTLAK KE MASTER (TANPA MENGUBAH MASTER) ---
                        df_m_kro = load_table("rab_m_kro", ["KRO", "Sumber_Dana"])
                        df_m_ro = load_table("rab_m_ro", ["KRO", "RO", "Sumber_Dana"])
                        df_m_komp = load_table("rab_m_komp", ["RO", "Komponen", "Sumber_Dana"])
                        df_m_sub = load_table("rab_m_subkomp", ["Komponen", "Sub_Komponen", "Sumber_Dana"])
                        df_m_akun = load_table("rab_m_akun", ["Sub_Komponen", "Account_Code", "Account_Name", "Sumber_Dana"])

                        def get_master_val(kode, original_val, df_m, col, parent_col=None, parent_val=None, sd="BOPTN"):
                            if kode == "-" or df_m.empty or col not in df_m.columns: return original_val
                            mask = df_m['Sumber_Dana'] == sd
                            if parent_col and parent_val and parent_val != "-":
                                mask = mask & (df_m[parent_col] == parent_val)
                            filtered_df = df_m[mask]
                            for _, row in filtered_df.iterrows():
                                if split_kd(row[col]) == kode:
                                    return row[col] # Memaksa teks PDF mengikuti Nama di Master!
                            return original_val

                        for idx, r in df_hasil.iterrows():
                            kro_code = split_kd(r['KRO'])
                            ro_code = split_kd(r['RO'])
                            komp_code = split_kd(r['Komponen'])
                            sub_code = split_kd(r['Sub_Komponen'])
                            
                            m_kro = get_master_val(kro_code, r['KRO'], df_m_kro, 'KRO', sd=sumber_dana)
                            m_ro = get_master_val(ro_code, r['RO'], df_m_ro, 'RO', 'KRO', m_kro, sd=sumber_dana)
                            m_komp = get_master_val(komp_code, r['Komponen'], df_m_komp, 'Komponen', 'RO', m_ro, sd=sumber_dana)
                            m_sub = get_master_val(sub_code, r['Sub_Komponen'], df_m_sub, 'Sub_Komponen', 'Komponen', m_komp, sd=sumber_dana)
                            
                            m_akun_name = r['Akun_Name']
                            if r['Akun_Code'] != "-" and not df_m_akun.empty:
                                mask_a = (df_m_akun['Sumber_Dana'] == sumber_dana) & (df_m_akun['Account_Code'] == r['Akun_Code']) & (df_m_akun['Sub_Komponen'] == m_sub)
                                match_a = df_m_akun[mask_a]
                                if not match_a.empty:
                                    m_akun_name = match_a['Account_Name'].iloc[0]

                            df_hasil.at[idx, 'KRO'] = m_kro
                            df_hasil.at[idx, 'RO'] = m_ro
                            df_hasil.at[idx, 'Komponen'] = m_komp
                            df_hasil.at[idx, 'Sub_Komponen'] = m_sub
                            df_hasil.at[idx, 'Akun_Name'] = m_akun_name

                        st.session_state.ekstrak_result = df_hasil
                        st.success(f"Berhasil mengekstrak {len(df_hasil)} baris rincian belanja bersih! Total Ekstraksi: Rp {format_rupiah(df_hasil['Total_Biaya'].sum())}")
                    else:
                        st.error("❌ Gagal mengekstrak rincian belanja.")
            else:
                st.error("Harap unggah file PDF terlebih dahulu.")

    if st.session_state.ekstrak_log:
        with st.expander("🛠️ Log Debug Mesin"):
            for log in st.session_state.ekstrak_log:
                if log.startswith("✅"): st.success(log)
                else: st.warning(log)

    if not st.session_state.ekstrak_result.empty:
        st.markdown("---")
        st.subheader("3. Ruang Karantina (Preview Data)")
        st.info("Sistem HANYA mengekstrak. Teks anomali/cacat dari Sirena telah dikoreksi otomatis mengikuti Master Anda. Master Database Anda 100% terkunci dan tidak akan ditimpa.")
        
        cols_order = ['KRO', 'RO', 'Komponen', 'Sub_Komponen', 'Kegiatan', 'Akun_Code', 'Akun_Name', 'Uraian', 'Vol_1', 'Sat_1', 'Vol_2', 'Sat_2', 'Harga_Satuan', 'Total_Biaya']
        df_display = st.session_state.ekstrak_result[cols_order]
        df_edit = st.data_editor(df_display, num_rows="dynamic", use_container_width=True, height=400)

        if st.button("💾 Konfirmasi & Simpan Permanen ke Tabel Kegiatan", type="primary", use_container_width=True):
            with st.spinner("Menyuntikkan data murni ke tabel Kegiatan..."):
                
                df_rab_utama = load_table("rab_utama", ["ID_RAB", "Tanggal", "Tahun", "Tgl_Cetak", "Sumber_Dana", "KRO", "RO", "Komponen", "Sub_Komponen", "Kegiatan", "Sasaran", "Volume", "Satuan", "Alokasi", "Jabatan", "Nama_Pejabat", "NIP_Pejabat", "Versi_RAB", "Is_Active", "Catatan"], f"WHERE \"Tahun\" = '{thn_target}'")
                
                if not df_rab_utama.empty:
                    ids = tuple(df_rab_utama['ID_RAB'].tolist())
                    where_det = f"WHERE \"ID_RAB\" = '{ids[0]}'" if len(ids) == 1 else f"WHERE \"ID_RAB\" IN {ids}"
                    df_rab_detail = load_table("rab_detail", ["ID_RAB", "Akun_Belanja", "Uraian", "Vol_1", "Sat_1", "Vol_2", "Sat_2", "Harga_Satuan", "Total_Biaya"], where_det)
                else:
                    df_rab_detail = pd.DataFrame(columns=["ID_RAB", "Akun_Belanja", "Uraian", "Vol_1", "Sat_1", "Vol_2", "Sat_2", "Harga_Satuan", "Total_Biaya"])
                
                active_vs = df_rab_utama[(df_rab_utama['Is_Active'] == 1)]['Versi_RAB'].unique()
                is_act = 1 if len(active_vs) == 0 or ver_target in active_vs else 0

                kegiatan_unik = df_edit['Kegiatan'].unique()
                for i, keg_name in enumerate(kegiatan_unik):
                    new_id = f"RAB-EXT-{datetime.now().strftime('%Y%m%d%H%M%S%f')}-{i}"
                    
                    df_keg_details = df_edit[df_edit['Kegiatan'] == keg_name].copy()
                    total_alokasi = df_keg_details['Total_Biaya'].sum()
                    
                    new_utama = pd.DataFrame([{
                        "ID_RAB": new_id, "Tanggal": datetime.now().strftime('%Y-%m-%d %H:%M'), 
                        "Tahun": thn_target, "Tgl_Cetak": datetime.now().strftime('%Y-%m-%d'),
                        "Sumber_Dana": sumber_dana, "KRO": df_keg_details['KRO'].iloc[0], "RO": df_keg_details['RO'].iloc[0], 
                        "Komponen": df_keg_details['Komponen'].iloc[0], "Sub_Komponen": df_keg_details['Sub_Komponen'].iloc[0],
                        "Kegiatan": keg_name, "Sasaran": "-", "Volume": 1, "Satuan": "Layanan", "Alokasi": total_alokasi,
                        "Jabatan": "Dekan", "Nama_Pejabat": "-", "NIP_Pejabat": "-",
                        "Versi_RAB": ver_target, "Is_Active": is_act, "Catatan": "-"
                    }])
                    df_rab_utama = pd.concat([df_rab_utama, new_utama], ignore_index=True)
                    
                    df_keg_details['ID_RAB'] = new_id
                    df_keg_details['Akun_Belanja'] = df_keg_details['Akun_Code'] + " - " + df_keg_details['Akun_Name']
                    new_detail = df_keg_details[['ID_RAB', 'Akun_Belanja', 'Uraian', 'Vol_1', 'Sat_1', 'Vol_2', 'Sat_2', 'Harga_Satuan', 'Total_Biaya']]
                    df_rab_detail = pd.concat([df_rab_detail, new_detail], ignore_index=True)
                
                save_success = update_rab_tahun(df_rab_utama, df_rab_detail, thn_target)
                if save_success:
                    log_audit("EKSTRAK PDF", f"Injeksi murni RKAKL {sumber_dana} tahun {thn_target} (Versi: {ver_target}). Total: Rp {format_rupiah(df_edit['Total_Biaya'].sum())}")
                    st.session_state.ekstrak_result = pd.DataFrame() 
                    st.success("🎉 Dokumen RKAKL berhasil diinjeksi! Data masuk murni tanpa mengubah Data Master Anda sedikit pun.")
                    st.rerun()

show_page()
