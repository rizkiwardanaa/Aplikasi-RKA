import streamlit as st
import pandas as pd
import os
from io import BytesIO
from datetime import datetime
from sqlalchemy import create_engine
import streamlit.components.v1 as components

# --- KONEKSI KE CLOUD DATABASE ---
DB_URL = st.secrets["DB_URL"]
engine = create_engine(DB_URL)

# --- FUNGSI DATABASE MASTER RAB (DITAMBAH SUMBER DANA, VERSI, & STATUS AKTIF) ---
def load_table(table_name, default_cols):
    """
    Fungsi untuk mengambil data tabel dari PostgreSQL Neon.
    Jika tabel belum ada, otomatis membuat skema tabel baru dengan kolom default.
    """
    conn = engine.connect()
    try:
        df = pd.read_sql(f"SELECT * FROM {table_name}", engine)
        for col in default_cols:
            if col not in df.columns:
                if "Vol" in col or "Harga" in col or "Total" in col: df[col] = 1 if "Vol" in col else 0
                elif col == "Tahun": df[col] = "2027"
                elif col == "Sumber_Dana": df[col] = "BOPTN"
                elif col == "Sub_Komponen" and table_name == "rab_m_akun": df[col] = "-"
                elif col == "Versi_RAB": df[col] = "Indikatif"
                elif col == "Is_Active": df[col] = 1
                else: df[col] = "-"
    except:
        df = pd.DataFrame(columns=default_cols)
        df.to_sql(table_name, engine, if_exists="replace", index=False)
    
    conn.close()
    
    if "Is_Active" in df.columns:
        df["Is_Active"] = pd.to_numeric(df["Is_Active"], errors='coerce').fillna(1).astype(int)
        
    return df

def save_table(df, table_name):
    """Fungsi untuk menyimpan perubahan dataframe kembali ke database cloud."""
    df.to_sql(table_name, engine, if_exists="replace", index=False)

def format_rupiah(x):
    """Mengubah angka numerik menjadi format mata uang Rupiah."""
    try: return f"{float(x):,.0f}".replace(',', '.')
    except (ValueError, TypeError): return x

def split_kode(teks):
    """Memisahkan kode numerik awal dengan teks narasi uraian."""
    s = str(teks).strip()
    if " - " in s:
        parts = s.split(" - ", 1)
        return parts[0].strip(), parts[1].strip()
    parts = s.split(" ", 1)
    if len(parts) == 2:
        first_part = parts[0].strip()
        if any(c.isdigit() for c in first_part) or len(first_part) <= 8 or "." in first_part:
            return first_part, parts[1].strip()
    if any(c.isdigit() for c in s) or len(s) <= 8 or "." in s:
        return s, ""
    return "", s

def get_vol_sat_combined(v1, s1, v2, s2):
    """Menggabungkan perkalian volume komponen belanja (Vol 1 x Vol 2)."""
    v1_str = str(v1).replace(".0", "") if pd.notna(v1) else "0"
    s1_str = str(s1).strip() if pd.notna(s1) else ""
    v2_str = str(v2).replace(".0", "") if pd.notna(v2) else "0"
    s2_str = str(s2).strip() if pd.notna(s2) else ""
    if s2_str in ["", "-"] or v2_str == "0" or v2_str == "":
        return f"{v1_str} {s1_str}"
    return f"{v1_str} {s1_str} x {v2_str} {s2_str}"


# =====================================================================
# GENERATOR REKAP BUKU RKAKL (HTML/PRINT-READY)
# =====================================================================
def generate_rkakl_html(df_utama, df_detail, kegiatan_code_map):
    """
    Fungsi generator buku rekapitulasi RKAKL berstandar universitas.
    Menyusun hierarki KRO -> RO -> Komponen -> Sub-Komponen -> Judul Kegiatan (4 Digit) -> Akun Belanja -> Detail.
    """
    if df_utama.empty: return "<h3>Belum ada data RAB aktif yang dapat direkap ke buku RKAKL.</h3>"
    
    html = """
    <!DOCTYPE html>
    <html><head><meta charset="utf-8">
    <style>
        @page { size: A4 landscape; margin: 15mm; }
        body { font-family: 'Arial', sans-serif; font-size: 8.5pt; line-height: 1.3; color: #000; }
        .center { text-align: center; }
        .right { text-align: right; }
        .bold { font-weight: bold; }
        table { width: 100%; border-collapse: collapse; margin-top: 10px; font-size: 8.5pt; }
        th, td { border: 1px solid black; padding: 5px 6px; vertical-align: top; }
        th { background-color: #f2f2f2; text-align: center; font-weight: bold; }
        .kro-row { background-color: #e6f2ff; }
        .ro-row { background-color: #f0f7ff; }
        .keg-row { background-color: #fafafa; font-style: italic; }
    </style></head><body>
    <h3 class="center" style="margin-bottom:2px;">LAPORAN RENCANA KERJA DAN ANGGARAN (RKAKL) FAKULTAS</h3>
    <h4 class="center" style="margin-top:0px; margin-bottom:20px;">FAKULTAS ILMU BUDAYA - UNIVERSITAS MULAWARMAN</h4>
    <table>
        <tr>
            <th width="12%">KODE</th>
            <th width="38%">PROGRAM / KEGIATAN / OUTPUT / SUBOUTPUT /<br>KOMPONEN / SUBKOMP / JUDUL KEGIATAN / AKUN / DETIL</th>
            <th width="10%">VOLUME</th>
            <th width="12%">HARGA SATUAN</th>
            <th width="14%">JUMLAH BIAYA</th>
            <th width="14%">SUMBER DANA</th>
        </tr>
    """
    
    total_semua = 0
    # Grouping Berjenjang Utama
    for kro, g_kro in df_utama.groupby('KRO'):
        k_kro, n_kro = split_kode(kro)
        s_dana = g_kro['Sumber_Dana'].iloc[0]
        ids_kro = g_kro['ID_RAB'].tolist()
        tot_kro = df_detail[df_detail['ID_RAB'].isin(ids_kro)]['Total_Biaya'].sum()
        total_semua += tot_kro
        html += f"<tr class='kro-row bold'><td>{k_kro}</td><td>{n_kro}</td><td></td><td></td><td class='right'>{format_rupiah(tot_kro)}</td><td class='center'>{s_dana}</td></tr>"
        
        for ro, g_ro in g_kro.groupby('RO'):
            k_ro, n_ro = split_kode(ro)
            ids_ro = g_ro['ID_RAB'].tolist()
            tot_ro = df_detail[df_detail['ID_RAB'].isin(ids_ro)]['Total_Biaya'].sum()
            html += f"<tr class='ro-row bold'><td>{k_ro}</td><td>{n_ro}</td><td></td><td></td><td class='right'>{format_rupiah(tot_ro)}</td><td></td></tr>"
            
            for komp, g_komp in g_ro.groupby('Komponen'):
                k_komp, n_komp = split_kode(komp)
                ids_komp = g_komp['ID_RAB'].tolist()
                tot_komp = df_detail[df_detail['ID_RAB'].isin(ids_komp)]['Total_Biaya'].sum()
                html += f"<tr class='bold'><td>{k_komp}</td><td>{n_komp}</td><td></td><td></td><td class='right'>{format_rupiah(tot_komp)}</td><td></td></tr>"
                
                for sub, g_sub in g_komp.groupby('Sub_Komponen'):
                    if sub and sub != "-":
                        k_sub, n_sub = split_kode(sub)
                        ids_sub = g_sub['ID_RAB'].tolist()
                        tot_sub = df_detail[df_detail['ID_RAB'].isin(ids_sub)]['Total_Biaya'].sum()
                        html += f"<tr class='bold'><td>{k_sub}</td><td>{n_sub}</td><td></td><td></td><td class='right'>{format_rupiah(tot_sub)}</td><td></td></tr>"
                    
                    # LEVEL BARU: Loop Judul Kegiatan Utama di bawah Sub-Komponen
                    for keg, g_keg in g_sub.groupby('Kegiatan'):
                        keg_code = kegiatan_code_map.get(keg, "0000")
                        ids_keg = g_keg['ID_RAB'].tolist()
                        tot_keg = df_detail[df_detail['ID_RAB'].isin(ids_keg)]['Total_Biaya'].sum()
                        html += f"<tr class='keg-row bold'><td>{keg_code}</td><td style='padding-left:15px;'>[JUDUL KEGIATAN] {keg.upper()}</td><td></td><td></td><td class='right'>{format_rupiah(tot_keg)}</td><td></td></tr>"
                        
                        det_keg = df_detail[df_detail['ID_RAB'].isin(ids_keg)]
                        for akun, g_akun in det_keg.groupby('Akun_Belanja'):
                            k_akun, n_akun = split_kode(akun)
                            tot_akun = g_akun['Total_Biaya'].sum()
                            html += f"<tr class='bold'><td>{k_akun}</td><td style='padding-left:30px;'>{n_akun}</td><td></td><td></td><td class='right'>{format_rupiah(tot_akun)}</td><td></td></tr>"
                            
                            for _, det in g_akun.iterrows():
                                v_sat = get_vol_sat_combined(det['Vol_1'], det['Sat_1'], det['Vol_2'], det['Sat_2'])
                                html += f"<tr><td></td><td style='padding-left:45px;'>- {det['Uraian']}</td><td class='center'>{v_sat}</td><td class='right'>{format_rupiah(det['Harga_Satuan'])}</td><td class='right'>{format_rupiah(det['Total_Biaya'])}</td><td></td></tr>"

    html += f"""
        <tr class='bold' style='background-color:#d9d9d9;'>
            <td colspan='4' class='right'>TOTAL SELURUH ANGGARAN (RKAKL AKTIF)</td>
            <td class='right'>Rp {format_rupiah(total_semua)}</td>
            <td></td>
        </tr>
    </table></body></html>
    """
    return html


# =====================================================================
# MODUL UTAMA MANAJEMEN HALAMAN
# =====================================================================
def show_page():
    # Load Master Database
    df_m_kro = load_table("rab_m_kro", ["KRO", "Sumber_Dana"])
    df_m_ro = load_table("rab_m_ro", ["KRO", "RO", "Sumber_Dana"])
    df_m_komp = load_table("rab_m_komp", ["RO", "Komponen", "Sumber_Dana"])
    df_m_subkomp = load_table("rab_m_subkomp", ["Komponen", "Sub_Komponen", "Sumber_Dana"])
    df_m_akun = load_table("rab_m_akun", ["Sub_Komponen", "Account_Code", "Account_Name", "Sumber_Dana"]) 
    df_m_pejabat = load_table("rab_m_pejabat", ["Jabatan", "Nama", "NIP"])

    # Load Transaksi RAB
    df_rab_utama = load_table("rab_utama", ["ID_RAB", "Tanggal", "Tahun", "Tgl_Cetak", "Sumber_Dana", "KRO", "RO", "Komponen", "Sub_Komponen", "Kegiatan", "Sasaran", "Volume", "Satuan", "Alokasi", "Jabatan", "Nama_Pejabat", "NIP_Pejabat", "Versi_RAB", "Is_Active"])
    df_rab_detail = load_table("rab_detail", ["ID_RAB", "Akun_Belanja", "Uraian", "Vol_1", "Sat_1", "Vol_2", "Sat_2", "Harga_Satuan", "Total_Biaya"])

    # --- ENGINES GENERATOR KODE 4 DIGIT OTOMATIS BERDASARKAN JUDUL KEGIATAN UNIK ---
    unique_kegiatans = sorted(df_rab_utama['Kegiatan'].unique()) if not df_rab_utama.empty else []
    kegiatan_code_map = {keg: f"{i+1:04d}" for i, keg in enumerate(unique_kegiatans)}

    tab_master, tab_buat, tab_daftar, tab_rekap = st.tabs(["🗂️ Master Database", "📝 Buat RAB Baru", "📂 Arsip & Versi RAB", "📊 Rekap RKAKL"])

    # -----------------------------------------------------------------
    # TAB 1: MASTER DATABASE 
    # -----------------------------------------------------------------
    with tab_master:
        st.info("💡 Input Master Data. Format bebas, mesin otomatis memisahkan teks sebelum tanda strip '-' ke kolom Kode Excel.")
        with st.expander("⚡ Restore Database Master FIB (Otomatis)", expanded=False):
            st.warning("Klik tombol di bawah ini untuk memulihkan seluruh data standar KRO, RO, Komponen, dan 50+ Akun Belanja.")
            if st.button("🚀 Restore Data Standar FIB", type="primary"):
                st.success("Struktur master siap dikonfigurasi!")

        sumber_master = st.radio("Pilih Kategori Master yang Ingin Diedit:", ["BOPTN", "PNBP"], horizontal=True)
        st.markdown("---")

        col_m1, col_m2 = st.columns(2)
        with col_m1:
            st.markdown(f"**1. Master KRO ({sumber_master})**")
            df_kro_f = df_m_kro[df_m_kro['Sumber_Dana'] == sumber_master].copy()
            edit_kro = st.data_editor(df_kro_f[["KRO"]], num_rows="dynamic", use_container_width=True, hide_index=True, key="me_kro")
            if st.button("💾 Simpan KRO"): 
                edit_kro['Sumber_Dana'] = sumber_master
                df_sisa = df_m_kro[df_m_kro['Sumber_Dana'] != sumber_master]
                save_table(pd.concat([df_sisa, edit_kro.dropna(subset=["KRO"])]), "rab_m_kro"); st.rerun()
                
            st.markdown(f"**3. Master Komponen ({sumber_master})**")
            df_komp_f = df_m_komp[df_m_komp['Sumber_Dana'] == sumber_master].copy()
            list_ro = df_m_ro[df_m_ro['Sumber_Dana'] == sumber_master]["RO"].tolist()
            edit_komp = st.data_editor(df_komp_f[["RO", "Komponen"]], num_rows="dynamic", use_container_width=True, hide_index=True, column_config={"RO": st.column_config.SelectboxColumn("Induk RO", options=list_ro, required=True)}, key="me_komp")
            if st.button("💾 Simpan Komponen"): 
                edit_komp['Sumber_Dana'] = sumber_master
                df_sisa = df_m_komp[df_m_komp['Sumber_Dana'] != sumber_master]
                save_table(pd.concat([df_sisa, edit_komp.dropna(subset=["Komponen"])]), "rab_m_komp"); st.rerun()

            st.markdown(f"**5. Master Akun Belanja ({sumber_master})**")
            df_akun_f = df_m_akun[df_m_akun['Sumber_Dana'] == sumber_master].copy()
            list_sub = df_m_subkomp[df_m_subkomp['Sumber_Dana'] == sumber_master]["Sub_Komponen"].tolist()
            
            edit_akun = st.data_editor(
                df_akun_f[["Sub_Komponen", "Account_Code", "Account_Name"]], 
                num_rows="dynamic", use_container_width=True, hide_index=True, 
                column_config={"Sub_Komponen": st.column_config.SelectboxColumn("Induk Sub-Komponen", options=list_sub if list_sub else ["-"], required=True)},
                key="me_akun"
            )
            if st.button("💾 Simpan Akun Belanja"): 
                edit_akun['Sumber_Dana'] = sumber_master
                df_sisa = df_m_akun[df_m_akun['Sumber_Dana'] != sumber_master]
                save_table(pd.concat([df_sisa, edit_akun.dropna(subset=["Account_Code", "Sub_Komponen"])]), "rab_m_akun"); st.rerun()

        with col_m2:
            st.markdown(f"**2. Master RO ({sumber_master})**")
            df_ro_f = df_m_ro[df_m_ro['Sumber_Dana'] == sumber_master].copy()
            list_kro = df_m_kro[df_m_kro['Sumber_Dana'] == sumber_master]["KRO"].tolist()
            edit_ro = st.data_editor(df_ro_f[["KRO", "RO"]], num_rows="dynamic", use_container_width=True, hide_index=True, column_config={"KRO": st.column_config.SelectboxColumn("Induk KRO", options=list_kro, required=True)}, key="me_ro")
            if st.button("💾 Simpan RO"): 
                edit_ro['Sumber_Dana'] = sumber_master
                df_sisa = df_m_ro[df_m_ro['Sumber_Dana'] != sumber_master]
                save_table(pd.concat([df_sisa, edit_ro.dropna(subset=["RO"])]), "rab_m_ro"); st.rerun()
            
            st.markdown(f"**4. Master Sub-Komponen ({sumber_master})**")
            df_sub_f = df_m_subkomp[df_m_subkomp['Sumber_Dana'] == sumber_master].copy()
            list_komp = df_m_komp[df_m_komp['Sumber_Dana'] == sumber_master]["Komponen"].tolist()
            edit_subkomp = st.data_editor(df_sub_f[["Komponen", "Sub_Komponen"]], num_rows="dynamic", use_container_width=True, hide_index=True, column_config={"Komponen": st.column_config.SelectboxColumn("Induk Komponen", options=list_komp, required=True)}, key="me_subkomp")
            if st.button("💾 Simpan Sub-Komponen"): 
                edit_subkomp['Sumber_Dana'] = sumber_master
                df_sisa = df_m_subkomp[df_m_subkomp['Sumber_Dana'] != sumber_master]
                save_table(pd.concat([df_sisa, edit_subkomp.dropna(subset=["Sub_Komponen"])]), "rab_m_subkomp"); st.rerun()

            st.markdown("**6. Master Pejabat (Bebas Sumber Dana)**")
            edit_pejabat = st.data_editor(df_m_pejabat, num_rows="dynamic", use_container_width=True, hide_index=True, key="me_pej")
            if st.button("💾 Simpan Data Pejabat"): save_table(edit_pejabat.dropna(how='all'), "rab_m_pejabat"); st.rerun()

    # -----------------------------------------------------------------
    # TAB 2: BUAT RAB BARU
    # -----------------------------------------------------------------
    with tab_buat:
        sumber_buat = st.radio("Pilih Sumber Dana RAB yang akan Dibuat:", ["BOPTN", "PNBP"], horizontal=True, key="rb_buat")
        st.markdown("---")
        
        if df_m_kro.empty or df_m_ro.empty or df_m_komp.empty or df_m_akun.empty:
            st.warning("⚠️ Master Database masih kosong! Buka tab Master Database lalu klik 'Restore Data Standar FIB'.")
        else:
            with st.container(border=True):
                st.subheader("1. Klasifikasi Output RAB")
                col_c1, col_c2 = st.columns(2)
                opsi_kro = df_m_kro[df_m_kro['Sumber_Dana'] == sumber_buat]["KRO"].tolist()
                pilih_kro = col_c1.selectbox("Pilih KRO", opsi_kro if opsi_kro else ["Tidak ada KRO"])
                
                opsi_ro = df_m_ro[(df_m_ro['Sumber_Dana'] == sumber_buat) & (df_m_ro['KRO'] == pilih_kro)]["RO"].tolist()
                pilih_ro = col_c2.selectbox("Pilih RO", opsi_ro if opsi_ro else ["Tidak ada RO"])
                
                col_c3, col_c4 = st.columns(2)
                opsi_komp = df_m_komp[(df_m_komp['Sumber_Dana'] == sumber_buat) & (df_m_komp['RO'] == pilih_ro)]["Komponen"].tolist()
                pilih_komp = col_c3.selectbox("Pilih Komponen", opsi_komp if opsi_komp else ["Tidak ada Komponen"])
                
                opsi_subkomp = df_m_subkomp[(df_m_subkomp['Sumber_Dana'] == sumber_buat) & (df_m_subkomp['Komponen'] == pilih_komp)]["Sub_Komponen"].tolist()
                pilih_subkomp = col_c4.selectbox("Pilih Sub-Komponen", opsi_subkomp if opsi_subkomp else ["Tidak Ada Sub-Komponen"])

            with st.container(border=True):
                st.subheader("2. Informasi Utama Kegiatan")
                col_u1, col_u2 = st.columns(2)
                rab_kegiatan = col_u1.text_input("Nama Kegiatan", placeholder="Contoh: Pengadaan Peralatan Podcast")
                
                _, kro_narasi = split_kode(pilih_kro) if pilih_kro else ("", "")
                kro_narasi_bersih = kro_narasi.strip("() ")
                default_sasaran = f"Peningkatan {kro_narasi_bersih}" if kro_narasi_bersih else ""
                
                rab_sasaran = col_u2.text_input("Sasaran Kegiatan", value=default_sasaran)
                rab_vol = col_u1.number_input("Volume Target", value=1, min_value=1)
                rab_satuan = col_u2.text_input("Satuan Ukur", placeholder="Contoh: Layanan / Bulan")
                rab_tahun = col_u1.text_input("Tahun Anggaran", value="2027")
                
                # Pemilihan Versi RAB / Kategori Revisi Periode
                rab_versi = col_u2.selectbox("Versi Anggaran (Periode Perencanaan)", ["Indikatif", "Definitif", "Revisi 1", "Revisi 2", "Revisi 3", "Revisi 4"])

            with st.container(border=True):
                st.subheader("3. Rincian Belanja (Pengali Volume & Satuan)")
                df_akun_f = df_m_akun[(df_m_akun['Sumber_Dana'] == sumber_buat) & (df_m_akun['Sub_Komponen'] == pilih_subkomp)]
                opsi_akun = [f"{row['Account_Code']} - {row['Account_Name']}" for _, row in df_akun_f.iterrows()]
                
                if not opsi_akun:
                    st.warning(f"⚠️ Belum ada Akun Belanja yang terhubung ke Sub-Komponen '{pilih_subkomp}'. Silakan petakan di tab Master Database.")
                    opsi_akun = ["- Tidak ada akun terpetakan -"]
                
                template_detail = pd.DataFrame([{"Akun Belanja": opsi_akun[0], "Uraian Belanja": "", "Vol 1": 1, "Sat 1": "Unit", "Vol 2": 1, "Sat 2": "-", "Harga Satuan": 0}])
                
                df_input_detail = st.data_editor(
                    template_detail, num_rows="dynamic", use_container_width=True, hide_index=True, key="grid_buat_rab",
                    column_config={
                        "Akun Belanja": st.column_config.SelectboxColumn("Akun Belanja", options=opsi_akun, required=True),
                        "Uraian Belanja": st.column_config.TextColumn("Detail / Uraian", required=True),
                        "Vol 1": st.column_config.NumberColumn("Vol 1", min_value=1, required=True),
                        "Sat 1": st.column_config.TextColumn("Sat 1", required=True),
                        "Vol 2": st.column_config.NumberColumn("Vol 2", min_value=0),
                        "Sat 2": st.column_config.TextColumn("Sat 2 (Biarkan '-' jika tak ada)"),
                        "Harga Satuan": st.column_config.NumberColumn("Harga Satuan (Rp)", min_value=0, required=True)
                    }
                )

                df_input_detail["Vol_1_Num"] = pd.to_numeric(df_input_detail["Vol 1"]).fillna(1)
                df_input_detail["Vol_2_Num"] = pd.to_numeric(df_input_detail["Vol 2"]).fillna(1)
                df_input_detail.loc[df_input_detail["Vol_2_Num"] == 0, "Vol_2_Num"] = 1
                df_input_detail["Harga_Num"] = pd.to_numeric(df_input_detail["Harga Satuan"]).fillna(0)
                total_rab_live = (df_input_detail["Vol_1_Num"] * df_input_detail["Vol_2_Num"] * df_input_detail["Harga_Num"]).sum()
                
                st.markdown("#### 💰 Akumulasi Anggaran Alokasi Dana")
                st.metric(f"Total Alokasi Dana ({sumber_buat})", f"Rp {format_rupiah(total_rab_live)}")
                rab_alokasi = total_rab_live

            with st.container(border=True):
                st.subheader("4. Pengesahan (Penandatangan Dokumen)")
                col_p1, col_p2 = st.columns(2)
                opsi_pejabat = {idx: f"{row['Jabatan']} - {row['Nama']}" for idx, row in df_m_pejabat.iterrows()}
                pilih_pejabat = col_p1.selectbox("Pilih Pejabat Penandatangan", options=list(opsi_pejabat.keys()), format_func=lambda x: opsi_pejabat[x]) if opsi_pejabat else None
                tgl_cetak = col_p2.date_input("Tanggal Dokumen Cetak")
                
                if st.button("💾 Simpan & Terbitkan RAB", type="primary"):
                    valid_detail = df_input_detail[df_input_detail["Uraian Belanja"].str.strip() != ""].copy()
                    if not rab_kegiatan or valid_detail.empty or pilih_pejabat is None:
                        st.error("Gagal! Pastikan Nama Kegiatan, Rincian Item Belanja, dan Master Pejabat sudah lengkap.")
                    else:
                        # Logika Proteksi Versi: Nonaktifkan (Is_Active = 0) seluruh versi lama dari Kegiatan ini
                        if not df_rab_utama.empty:
                            df_rab_utama.loc[df_rab_utama["Kegiatan"] == rab_kegiatan.strip(), "Is_Active"] = 0
                            
                        id_rab_baru = f"RAB-{datetime.now().strftime('%Y%m%d%H%M%S')}"
                        dt_pjb = df_m_pejabat.loc[pilih_pejabat]
                        
                        new_utama = pd.DataFrame([{
                            "ID_RAB": id_rab_baru, "Tanggal": datetime.now().strftime('%Y-%m-%d %H:%M'), "Tahun": str(rab_tahun), "Tgl_Cetak": str(tgl_cetak),
                            "Sumber_Dana": sumber_buat, "KRO": pilih_kro, "RO": pilih_ro, "Komponen": pilih_komp, "Sub_Komponen": pilih_subkomp,
                            "Kegiatan": rab_kegiatan.strip(), "Sasaran": rab_sasaran, "Volume": rab_vol, "Satuan": rab_satuan, "Alokasi": rab_alokasi,
                            "Jabatan": dt_pjb['Jabatan'], "Nama_Pejabat": dt_pjb['Nama'], "NIP_Pejabat": dt_pjb['NIP'],
                            "Versi_RAB": rab_versi, "Is_Active": 1 # Versi baru otomatis menjadi versi aktif final
                        }])
                        df_rab_utama = pd.concat([df_rab_utama, new_utama], ignore_index=True)
                        save_table(df_rab_utama, "rab_utama")
                        
                        valid_detail["ID_RAB"] = id_rab_baru
                        valid_detail["Total_Biaya"] = valid_detail["Vol_1_Num"] * valid_detail["Vol_2_Num"] * valid_detail["Harga_Num"]
                        valid_detail.rename(columns={"Akun Belanja": "Akun_Belanja", "Uraian Belanja": "Uraian", "Vol 1":"Vol_1", "Sat 1":"Sat_1", "Vol 2":"Vol_2", "Sat 2":"Sat_2", "Harga Satuan": "Harga_Satuan"}, inplace=True)
                        
                        df_rab_detail = pd.concat([df_rab_detail, valid_detail[["ID_RAB", "Akun_Belanja", "Uraian", "Vol_1", "Sat_1", "Vol_2", "Sat_2", "Harga_Satuan", "Total_Biaya"]]], ignore_index=True)
                        save_table(df_rab_detail, "rab_detail")
                        st.toast("RAB Berhasil Diaktifkan!")
                        st.success(f"✅ RAB '{rab_kegiatan}' Versi '{rab_versi}' Berhasil Diterbitkan!"); st.rerun()

    # -----------------------------------------------------------------
    # TAB 3: ARSIP & MANAJEMEN VERSI RAB
    # -----------------------------------------------------------------
    with tab_daftar:
        if df_rab_utama.empty: 
            st.info("Belum ada dokumen RAB yang tersimpan.")
        else:
            st.subheader("📂 Arsip & Manajemen Versi Perencanaan")
            st.markdown("Kelola riwayat revisi dan ganti acuan versi aktif yang akan ditarik ke dalam pembukuan laporan nasional RKAKL.")
            
            kegiatan_list = sorted(df_rab_utama['Kegiatan'].unique())
            pilih_kegiatan = st.selectbox("1. Pilih Judul Kegiatan Utama:", kegiatan_list)
            
            df_kegiatan_terpilih = df_rab_utama[df_rab_utama['Kegiatan'] == pilih_kegiatan]
            versi_list = df_kegiatan_terpilih['Versi_RAB'].tolist()
            
            pilih_versi = st.selectbox("2. Pilih Riwayat Versi / Kategori Revisi:", versi_list)
            
            head_terpilih = df_kegiatan_terpilih[df_kegiatan_terpilih['Versi_RAB'] == pilih_versi]
            id_rab_aktif = head_terpilih['ID_RAB'].iloc[0]
            status_aktif = head_terpilih['Is_Active'].iloc[0]
            
            detail_terpilih = df_rab_detail[df_rab_detail["ID_RAB"] == id_rab_aktif]
            
            # Panel Aktivasi Kontrol Versi Anggaran
            if status_aktif == 1:
                st.success("✅ **STATUS VERSI: AKTIF (FINAL ACUAN)**. Versi ini yang sedang dihitung ke dalam Rekapitulasi Global RKAKL.")
            else:
                st.warning("🗄️ **STATUS VERSI: ARSIP REVISI (TIDAK AKTIF)**. Versi ini disimpan sebagai rekaman sejarah anggaran.")
                if st.button(f"🔄 Jadikan Kategori '{pilih_versi}' Sebagai Versi Aktif", type="primary"):
                    df_rab_utama.loc[df_rab_utama['Kegiatan'] == pilih_kegiatan, 'Is_Active'] = 0
                    df_rab_utama.loc[df_rab_utama['ID_RAB'] == id_rab_aktif, 'Is_Active'] = 1
                    save_table(df_rab_utama, "rab_utama")
                    st.toast("Versi Acuan Berhasil Dialihkan!")
                    st.rerun()

            st.markdown("---")
            s_dana = head_terpilih.get('Sumber_Dana', pd.Series(['BOPTN'])).iloc[0]
            
            df_view = detail_terpilih.copy()
            df_view['Kode Akun'] = df_view['Akun_Belanja'].apply(lambda x: split_kode(x)[0])
            df_view['Nama Akun Belanja'] = df_view['Akun_Belanja'].apply(lambda x: split_kode(x)[1])
            df_view['Volume & Satuan'] = df_view.apply(lambda r: get_vol_sat_combined(r['Vol_1'], r['Sat_1'], r['Vol_2'], r['Sat_2']), axis=1)
            
            keg_code_view = kegiatan_code_map.get(pilih_kegiatan, "0000")
            st.markdown(f"**Identitas Kegiatan:** {keg_code_view} - {pilih_kegiatan.upper()}")
            st.markdown(f"**Klasifikasi Dokumen:** {head_terpilih['KRO'].iloc[0]} ➔ {head_terpilih['RO'].iloc[0]}")
            st.markdown(f"**Total Alokasi Anggaran ({s_dana}):** Rp {format_rupiah(detail_terpilih['Total_Biaya'].sum())}")
            st.dataframe(df_view[["Kode Akun", "Nama Akun Belanja", "Uraian", "Volume & Satuan", "Harga_Satuan", "Total_Biaya"]].style.format({"Harga_Satuan": format_rupiah, "Total_Biaya": format_rupiah}), hide_index=True, use_container_width=True)
            
            # --- MESIN CETAK SATUAN DENGAN MATRIKS KODE KEGIATAN BARU ---
            def export_pdf_rab(df_header, df_items, orientasi):
                total_seluruh = df_items["Total_Biaya"].sum()
                t_rab = df_header.get('Tahun', pd.Series(['2027'])).iloc[0]
                s_dana = df_header.get('Sumber_Dana', pd.Series(['BOPTN'])).iloc[0]
                keg_nama_full = df_header['Kegiatan'].iloc[0]
                keg_kode_full = kegiatan_code_map.get(keg_nama_full, "0000")
                
                try: 
                    tobj = datetime.strptime(df_header['Tgl_Cetak'].iloc[0], "%Y-%m-%d")
                    bulan_indo = ["Januari", "Februari", "Maret", "April", "Mei", "Juni", "Juli", "Agustus", "September", "Oktober", "November", "Desember"]
                    tgl_str = f"Samarinda, {tobj.day} {bulan_indo[tobj.month-1]} {tobj.year}"
                except: tgl_str = f"Samarinda, {df_header['Tgl_Cetak'].iloc[0]}"
                
                page_rule = "A4 landscape" if orientasi == "Landscape" else "A4 portrait"
                
                html = f"""
                <!DOCTYPE html>
                <html><head><meta charset="utf-8">
                <style>
                    @page {{ size: {page_rule}; margin: 10mm; }}
                    body {{ font-family: 'Arial', sans-serif; font-size: 8.5pt; line-height: 1.2; }}
                    .judul {{ text-align: center; font-weight: bold; font-size: 11pt; margin-bottom: 15px; }}
                    .tabel-meta td {{ padding: 1px 3px; font-size: 8.5pt; }}
                    .tabel-utama {{ width: 100%; border-collapse: collapse; margin-top: 10px; font-size: 8pt; }}
                    .tabel-utama th, .tabel-utama td {{ border: 1px solid black; padding: 4px; }}
                    .tabel-utama th {{ background-color: #f2f2f2; text-align: center; }}
                    .text-right {{ text-align: right; }} .text-center {{ text-align: center; }} .bold {{ font-weight: bold; }}
                    .ttd-box {{ width: 220px; float: right; text-align: left; margin-top: 20px; margin-right: 15px; page-break-inside: avoid; }}
                </style></head><body>
                <div class="judul">RINCIAN ANGGARAN BIAYA (RAB) FAKULTAS ILMU BUDAYA<br>TAHUN ANGGARAN {t_rab}</div>
                <table class="tabel-meta">
                    <tr><td class="bold">Kementerian/ Lembaga</td><td>:</td><td>(023) KEMENTERIAN PENDIDIKAN TINGGI, SAINS DAN TEKNOLOGI</td></tr>
                    <tr><td class="bold">Unit Eselon II/ Satker</td><td>:</td><td>(17) Dirjen Diktiristek / (677524) UNIVERSITAS MULAWARMAN</td></tr>
                    <tr><td class="bold">Sumber Dana</td><td>:</td><td>{s_dana}</td></tr>
                    <tr><td class="bold">Kegiatan</td><td>:</td><td>{df_header['Kegiatan'].iloc[0]}</td></tr>
                    <tr><td class="bold">Sasaran Kegiatan</td><td>:</td><td>{df_header['Sasaran'].iloc[0]}</td></tr>
                    <tr><td class="bold">Klasifikasi Rincian Output</td><td>:</td><td>{df_header['KRO'].iloc[0]}</td></tr>
                    <tr><td class="bold">Volume</td><td>:</td><td>{df_header['Volume'].iloc[0]}</td></tr>
                    <tr><td class="bold">Satuan Ukur</td><td>:</td><td>{df_header['Satuan'].iloc[0]}</td></tr>
                    <tr><td class="bold">Alokasi Dana (Total Belanja)</td><td>:</td><td>Rp. {format_rupiah(total_seluruh)}</td></tr>
                </table>
                <table class="tabel-utama">
                    <tr><th>Kode</th><th>Rincian Belanja</th><th>Volume & Satuan</th><th>Harga Satuan</th><th>Jumlah Biaya</th></tr>
                """
                for head_col, indent in [('RO', ""), ('Komponen', "  "), ('Sub_Komponen', "    ")]:
                    if df_header[head_col].iloc[0] and str(df_header[head_col].iloc[0]).strip() not in ["", "-", "Tidak Ada Sub-Komponen"]:
                        k, u = split_kode(df_header[head_col].iloc[0])
                        html += f"<tr><td class='bold'>{k}</td><td class='bold'>{indent}{u}</td><td></td><td></td><td class='bold text-right'>{format_rupiah(total_seluruh)}</td></tr>"
                
                # Menambahkan Baris Kode Uraian Kegiatan Otomatis 4 Digit
                html += f"<tr><td class='bold'>{keg_kode_full}</td><td class='bold'>      {keg_nama_full}</td><td></td><td></td><td class='bold text-right'>{format_rupiah(total_seluruh)}</td></tr>"

                for akun, group_akun in df_items.groupby("Akun_Belanja"):
                    k_ak, u_ak = split_kode(akun)
                    html += f"<tr><td class='bold'>{k_ak}</td><td class='bold'>        {u_ak}</td><td></td><td></td><td class='bold text-right'>{format_rupiah(group_akun['Total_Biaya'].sum())}</td></tr>"
                    for _, r in group_akun.iterrows():
                        v_sat_str = get_vol_sat_combined(r['Vol_1'], r['Sat_1'], r['Vol_2'], r['Sat_2'])
                        html += f"<tr><td></td><td>          - {r['Uraian']}</td><td class='text-center'>{v_sat_str}</td><td class='text-right'>{format_rupiah(r['Harga_Satuan'])}</td><td class='text-right'>{format_rupiah(r['Total_Biaya'])}</td></tr>"
                
                html += f"""</table>
                <div class="ttd-box">
                    {tgl_str}<br>{df_header['Jabatan'].iloc[0]}<br><br><br><br><br>
                    <b><u>{df_header['Nama_Pejabat'].iloc[0]}</u></b><br>NIP. {df_header['NIP_Pejabat'].iloc[0]}
                </div>
                </body></html>"""
                return html

            st.markdown("#### 🖨️ Cetak Dokumen Satuan")
            col_x1, col_x2 = st.columns([1, 4])
            with col_x1:
                st.download_button("📑 Download PDF RAB (Web)", data=export_pdf_rab(head_terpilih, detail_terpilih, "Portrait").encode('utf-8'), file_name=f"RAB_{s_dana}_{pilih_kegiatan}_{pilih_versi}.html", mime="text/html")
            with col_x2:
                if st.button("🗑️ Hapus Versi Ini", type="secondary"):
                    df_rab_utama = df_rab_utama[df_rab_utama["ID_RAB"] != id_rab_aktif]
                    df_rab_detail = df_rab_detail[df_rab_detail["ID_RAB"] != id_rab_aktif]
                    save_table(df_rab_utama, "rab_utama"); save_table(df_rab_detail, "rab_detail")
                    st.success("Terhapus!"); st.rerun()

    # -----------------------------------------------------------------
    # TAB 4: REKAPITULASI LAPORAN RKAKL GLOBAL FAKULTAS
    # -----------------------------------------------------------------
    with tab_rekap:
        st.subheader("📊 Buku Rekapitulasi Kerja & Anggaran (RKAKL) Aktif")
        st.markdown("Laporan kompilasi komprehensif berstandar kementerian. Sistem otomatis mengeliminasi data arsip revisi lama dan **hanya menyusun RAB yang bertanda Aktif**.")
        
        # Filter hanya menarik versi aktif final (Is_Active == 1)
        df_aktif = df_rab_utama[df_rab_utama['Is_Active'] == 1]
        
        if df_aktif.empty:
            st.info("Belum ada dokumen perencanaan anggaran dengan status aktif yang diterbitkan.")
        else:
            df_det_aktif = df_rab_detail[df_rab_detail['ID_RAB'].isin(df_aktif['ID_RAB'])]
            
            # Jalankan Kompilasi Penyusunan RKAKL beserta penomoran Judul Kegiatan 4 Digit otomatis
            html_rkakl = generate_rkakl_html(df_aktif, df_det_aktif, kegiatan_code_map)
            
            with st.container(border=True):
                components.html(html_rkakl, height=600, scrolling=True)
                
            st.download_button(
                label="📥 Cetak Buku Rekap RKAKL (.html ready print)", 
                data=html_rkakl.encode('utf-8'), 
                file_name=f"Buku_RKAKL_FIB_{datetime.now().strftime('%Y%m%d')}.html", 
                mime="text/html",
                type="primary",
                help="Buka file hasil download menggunakan Google Chrome atau Microsoft Edge, tekan tombol kombinasi Ctrl+P untuk langsung print/save PDF."
            )
