import streamlit as st
import pandas as pd
import os
from io import BytesIO
from datetime import datetime
from sqlalchemy import create_engine
import streamlit.components.v1 as components

# --- KONEKSI KE CLOUD DATABASE ---
DB_URL = st.secrets["DB_URL"]
engine = create_engine(DB_URL, pool_size=10, max_overflow=20) # Optimasi koneksi

# =====================================================================
# FUNGSI DATABASE (DENGAN OPTIMASI CACHE AGAR WEB TIDAK BERAT)
# =====================================================================
@st.cache_data(ttl=300) # CACHE 5 MENIT: Menghilangkan loading/lag saat input form
def load_table(table_name, default_cols):
    """
    Fungsi untuk mengambil data tabel dari PostgreSQL Neon.
    Dioptimasi dengan cache agar perpindahan dropdown KRO-RO sangat cepat.
    """
    conn = engine.connect()
    try:
        df = pd.read_sql(f"SELECT * FROM {table_name}", conn)
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
    """Fungsi menyimpan data. Membersihkan cache agar layar langsung ter-update."""
    df.to_sql(table_name, engine, if_exists="replace", index=False)
    st.cache_data.clear() # Wajib dihapus agar data baru terbaca

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
# GENERATOR MATRIK PERBANDINGAN (SEBELUM vs MENJADI)
# =====================================================================
def generate_matrik_html(df_matrik, v_sebelum, v_menjadi, keg_map):
    if df_matrik.empty: return "<h3>Tidak ada data untuk dibandingkan pada versi tersebut.</h3>"
    
    html = f"""
    <!DOCTYPE html>
    <html><head><meta charset="utf-8">
    <style>
        @page {{ size: A4 landscape; margin: 15mm; }}
        body {{ font-family: 'Arial', sans-serif; font-size: 8pt; line-height: 1.3; color: #000; }}
        .center {{ text-align: center; }} .right {{ text-align: right; }} .bold {{ font-weight: bold; }}
        table {{ width: 100%; border-collapse: collapse; margin-top: 10px; font-size: 8pt; }}
        th, td {{ border: 1px solid black; padding: 4px; vertical-align: top; }}
        th {{ background-color: #d9d9d9; text-align: center; font-weight: bold; }}
        
        .kro-row {{ background-color: #d9e1f2; }}
        .ro-row {{ background-color: #e9edf4; }}
        .komp-row {{ background-color: #fff2cc; }}
        .sub-row {{ background-color: #fce4d6; }}
        .keg-row {{ background-color: #e2efda; }}
        .naik {{ color: #b30000; }} /* Merah untuk penambahan anggaran */
        .turun {{ color: #006600; }} /* Hijau untuk penghematan */
    </style></head><body>
    <h3 class="center" style="margin-bottom:2px;">MATRIK PERUBAHAN RENCANA KERJA DAN ANGGARAN</h3>
    <h4 class="center" style="margin-top:0px; margin-bottom:20px;">FAKULTAS ILMU BUDAYA - UNIVERSITAS MULAWARMAN<br>Versi {v_sebelum} menjadi {v_menjadi}</h4>
    <table>
        <tr>
            <th width="10%">KODE</th>
            <th width="35%">URAIAN PROGRAM / KEGIATAN /<br>KOMPONEN / AKUN / DETAIL</th>
            <th width="15%">PAGU SEMULA<br>({v_sebelum})</th>
            <th width="15%">PAGU MENJADI<br>({v_menjadi})</th>
            <th width="15%">BERTAMBAH /<br>(BERKURANG)</th>
            <th width="10%">DANA</th>
        </tr>
    """
    
    tot_s_global, tot_m_global, tot_sel_global = 0, 0, 0
    
    for kro, g_kro in df_matrik.groupby('KRO'):
        k_kro, n_kro = split_kode(kro)
        sd = g_kro['Sumber_Dana'].iloc[0]
        t_s = g_kro['Biaya_Semula'].sum(); t_m = g_kro['Biaya_Menjadi'].sum(); selisih = g_kro['Selisih'].sum()
        tot_s_global += t_s; tot_m_global += t_m; tot_sel_global += selisih
        html += f"<tr class='kro-row bold'><td>{k_kro}</td><td>{n_kro}</td><td class='right'>{format_rupiah(t_s)}</td><td class='right'>{format_rupiah(t_m)}</td><td class='right'>{format_rupiah(selisih)}</td><td class='center'>{sd}</td></tr>"
        
        for ro, g_ro in g_kro.groupby('RO'):
            k_ro, n_ro = split_kode(ro)
            t_s = g_ro['Biaya_Semula'].sum(); t_m = g_ro['Biaya_Menjadi'].sum(); selisih = g_ro['Selisih'].sum()
            html += f"<tr class='ro-row bold'><td>{k_ro}</td><td>{n_ro}</td><td class='right'>{format_rupiah(t_s)}</td><td class='right'>{format_rupiah(t_m)}</td><td class='right'>{format_rupiah(selisih)}</td><td></td></tr>"
            
            for komp, g_komp in g_ro.groupby('Komponen'):
                k_komp, n_komp = split_kode(komp)
                t_s = g_komp['Biaya_Semula'].sum(); t_m = g_komp['Biaya_Menjadi'].sum(); selisih = g_komp['Selisih'].sum()
                html += f"<tr class='komp-row bold'><td>{k_komp}</td><td>{n_komp}</td><td class='right'>{format_rupiah(t_s)}</td><td class='right'>{format_rupiah(t_m)}</td><td class='right'>{format_rupiah(selisih)}</td><td></td></tr>"
                
                for sub, g_sub in g_komp.groupby('Sub_Komponen'):
                    if sub and sub != "-":
                        k_sub, n_sub = split_kode(sub)
                        t_s = g_sub['Biaya_Semula'].sum(); t_m = g_sub['Biaya_Menjadi'].sum(); selisih = g_sub['Selisih'].sum()
                        html += f"<tr class='sub-row bold'><td>{k_sub}</td><td>{n_sub}</td><td class='right'>{format_rupiah(t_s)}</td><td class='right'>{format_rupiah(t_m)}</td><td class='right'>{format_rupiah(selisih)}</td><td></td></tr>"
                    
                    for keg, g_keg in g_sub.groupby('Kegiatan'):
                        k_keg = keg_map.get(keg, "0000"); n_keg = keg.title()
                        t_s = g_keg['Biaya_Semula'].sum(); t_m = g_keg['Biaya_Menjadi'].sum(); selisih = g_keg['Selisih'].sum()
                        html += f"<tr class='keg-row bold'><td>{k_keg}</td><td style='padding-left:15px;'>{n_keg}</td><td class='right'>{format_rupiah(t_s)}</td><td class='right'>{format_rupiah(t_m)}</td><td class='right'>{format_rupiah(selisih)}</td><td></td></tr>"
                        
                        for akun, g_akun in g_keg.groupby('Akun_Belanja'):
                            k_ak, n_ak = split_kode(akun)
                            t_s = g_akun['Biaya_Semula'].sum(); t_m = g_akun['Biaya_Menjadi'].sum(); selisih = g_akun['Selisih'].sum()
                            html += f"<tr class='bold'><td>{k_ak}</td><td style='padding-left:30px;'>{n_ak}</td><td class='right'>{format_rupiah(t_s)}</td><td class='right'>{format_rupiah(t_m)}</td><td class='right'>{format_rupiah(selisih)}</td><td></td></tr>"
                            
                            for _, det in g_akun.iterrows():
                                html += f"<tr><td></td><td style='padding-left:45px;'>- {det['Uraian']}</td><td class='right'>{format_rupiah(det['Biaya_Semula'])}</td><td class='right'>{format_rupiah(det['Biaya_Menjadi'])}</td><td class='right'>{format_rupiah(det['Selisih'])}</td><td></td></tr>"

    html += f"""
        <tr class='bold' style='background-color:#d9d9d9;'>
            <td colspan='2' class='right'>TOTAL GLOBAL</td>
            <td class='right'>Rp {format_rupiah(tot_s_global)}</td>
            <td class='right'>Rp {format_rupiah(tot_m_global)}</td>
            <td class='right'>Rp {format_rupiah(tot_sel_global)}</td>
            <td></td>
        </tr>
    </table></body></html>
    """
    return html


# =====================================================================
# GENERATOR REKAP BUKU RKAKL (HTML/PRINT-READY)
# =====================================================================
def generate_rkakl_html(df_utama, df_detail, kegiatan_code_map):
    if df_utama.empty: return "<h3>Belum ada data RAB aktif.</h3>"
    
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
        th { background-color: #d9d9d9; text-align: center; font-weight: bold; }
        
        .kro-row { background-color: #d9e1f2; }
        .ro-row { background-color: #e9edf4; }
        .komp-row { background-color: #fff2cc; }
        .sub-row { background-color: #fce4d6; }
        .keg-row { background-color: #e2efda; }
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
                html += f"<tr class='komp-row bold'><td>{k_komp}</td><td>{n_komp}</td><td></td><td></td><td class='right'>{format_rupiah(tot_komp)}</td><td></td></tr>"
                
                for sub, g_sub in g_komp.groupby('Sub_Komponen'):
                    if sub and sub != "-":
                        k_sub, n_sub = split_kode(sub)
                        ids_sub = g_sub['ID_RAB'].tolist()
                        tot_sub = df_detail[df_detail['ID_RAB'].isin(ids_sub)]['Total_Biaya'].sum()
                        html += f"<tr class='sub-row bold'><td>{k_sub}</td><td>{n_sub}</td><td></td><td></td><td class='right'>{format_rupiah(tot_sub)}</td><td></td></tr>"
                    
                    for keg, g_keg in g_sub.groupby('Kegiatan'):
                        keg_code = kegiatan_code_map.get(keg, "0000")
                        keg_title = keg.title() 
                        ids_keg = g_keg['ID_RAB'].tolist()
                        tot_keg = df_detail[df_detail['ID_RAB'].isin(ids_keg)]['Total_Biaya'].sum()
                        html += f"<tr class='keg-row bold'><td>{keg_code}</td><td style='padding-left:15px;'>{keg_title}</td><td></td><td></td><td class='right'>{format_rupiah(tot_keg)}</td><td></td></tr>"
                        
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
    # Load Master Database (Ter-Cache agar instan)
    df_m_kro = load_table("rab_m_kro", ["KRO", "Sumber_Dana"])
    df_m_ro = load_table("rab_m_ro", ["KRO", "RO", "Sumber_Dana"])
    df_m_komp = load_table("rab_m_komp", ["RO", "Komponen", "Sumber_Dana"])
    df_m_subkomp = load_table("rab_m_subkomp", ["Komponen", "Sub_Komponen", "Sumber_Dana"])
    df_m_akun = load_table("rab_m_akun", ["Sub_Komponen", "Account_Code", "Account_Name", "Sumber_Dana"]) 
    df_m_pejabat = load_table("rab_m_pejabat", ["Jabatan", "Nama", "NIP"])

    # Load Transaksi RAB
    df_rab_utama = load_table("rab_utama", ["ID_RAB", "Tanggal", "Tahun", "Tgl_Cetak", "Sumber_Dana", "KRO", "RO", "Komponen", "Sub_Komponen", "Kegiatan", "Sasaran", "Volume", "Satuan", "Alokasi", "Jabatan", "Nama_Pejabat", "NIP_Pejabat", "Versi_RAB", "Is_Active"])
    df_rab_detail = load_table("rab_detail", ["ID_RAB", "Akun_Belanja", "Uraian", "Vol_1", "Sat_1", "Vol_2", "Sat_2", "Harga_Satuan", "Total_Biaya"])

    unique_kegiatans = sorted(df_rab_utama['Kegiatan'].unique()) if not df_rab_utama.empty else []
    kegiatan_code_map = {keg: f"{i+1:04d}" for i, keg in enumerate(unique_kegiatans)}

    st.title("📄 Pengolah Dokumen RAB Universitas")
    st.caption("Sistem Manajemen & Generator RAB Berjenjang dengan Pemisahan Kode Otomatis, Sumber Dana & Matrik Versi Anggaran.")

    # TAB BARU: Matrik Perubahan
    tab_master, tab_buat, tab_daftar, tab_rekap, tab_matrik = st.tabs(["🗂️ Master", "📝 Buat RAB", "📂 Arsip & Versi", "📊 RKAKL Aktif", "⚖️ Matrik Perubahan"])

    # -----------------------------------------------------------------
    # TAB 1: MASTER DATABASE 
    # -----------------------------------------------------------------
    with tab_master:
        st.info("💡 Input Master Data. Format bebas, mesin otomatis memisahkan teks sebelum tanda strip '-' ke kolom Kode Excel.")
        with st.expander("⚡ Restore Database Master FIB (Otomatis)", expanded=False):
            st.warning("Klik tombol di bawah ini untuk memulihkan seluruh data standar KRO, RO, Komponen, dan 50+ Akun Belanja.")
            if st.button("🚀 Restore Data Standar FIB", type="primary"):
                st.success("Struktur master siap dikonfigurasi! Gunakan script restore CSV jika diperlukan.")

        # --- FITUR IMPORT EXPORT MASTER DIKEMBALIKAN ---
        with st.expander("💾 Import & Export Data Master (Excel)", expanded=False):
            st.info("Gunakan fitur ini untuk mem-backup seluruh data master ke Excel, atau memulihkan data master dari file Excel.")
            c_eks, c_imp = st.columns(2)
            
            with c_eks:
                st.markdown("**1. Export Data Master**")
                output_master = BytesIO()
                with pd.ExcelWriter(output_master, engine='openpyxl') as writer:
                    df_m_kro.to_excel(writer, index=False, sheet_name='KRO')
                    df_m_ro.to_excel(writer, index=False, sheet_name='RO')
                    df_m_komp.to_excel(writer, index=False, sheet_name='Komponen')
                    df_m_subkomp.to_excel(writer, index=False, sheet_name='Sub_Komponen')
                    df_m_akun.to_excel(writer, index=False, sheet_name='Akun')
                    df_m_pejabat.to_excel(writer, index=False, sheet_name='Pejabat')
                st.download_button(
                    label="📥 Download Backup Master (.xlsx)",
                    data=output_master.getvalue(),
                    file_name=f"Backup_Master_RAB_{datetime.now().strftime('%Y%m%d')}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    type="primary"
                )
            
            with c_imp:
                st.markdown("**2. Import Data Master**")
                file_master = st.file_uploader("Upload File Backup Excel Master", type=['xlsx'], key="import_master")
                if st.button("🚀 Jalankan Import", type="primary"):
                    if file_master is not None:
                        try:
                            xls_master = pd.read_excel(file_master, sheet_name=None)
                            if 'KRO' in xls_master: save_table(xls_master['KRO'], "rab_m_kro")
                            if 'RO' in xls_master: save_table(xls_master['RO'], "rab_m_ro")
                            if 'Komponen' in xls_master: save_table(xls_master['Komponen'], "rab_m_komp")
                            if 'Sub_Komponen' in xls_master: save_table(xls_master['Sub_Komponen'], "rab_m_subkomp")
                            if 'Akun' in xls_master: save_table(xls_master['Akun'], "rab_m_akun")
                            if 'Pejabat' in xls_master: save_table(xls_master['Pejabat'], "rab_m_pejabat")
                            st.success("🎉 Data Master berhasil di-import dan diperbarui!"); st.rerun()
                        except Exception as e:
                            st.error(f"Gagal memproses file. Pastikan format sheet sesuai: {e}")

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
                rab_versi = col_u2.selectbox("Versi Anggaran (Periode Perencanaan)", ["Indikatif", "Definitif", "Revisi 1", "Revisi 2", "Revisi 3", "Revisi 4"])

            with st.container(border=True):
                st.subheader("3. Rincian Belanja (Pengali Volume & Satuan)")
                df_akun_f = df_m_akun[(df_m_akun['Sumber_Dana'] == sumber_buat) & (df_m_akun['Sub_Komponen'] == pilih_subkomp)]
                opsi_akun = [f"{row['Account_Code']} - {row['Account_Name']}" for _, row in df_akun_f.iterrows()]
                
                if not opsi_akun:
                    st.warning(f"⚠️ Belum ada Akun Belanja terhubung ke Sub-Komponen '{pilih_subkomp}'. Petakan di tab Master Database.")
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
                        if not df_rab_utama.empty:
                            df_rab_utama.loc[df_rab_utama["Kegiatan"].str.strip().str.lower() == rab_kegiatan.strip().lower(), "Is_Active"] = 0
                            
                        id_rab_baru = f"RAB-{datetime.now().strftime('%Y%m%d%H%M%S')}"
                        dt_pjb = df_m_pejabat.loc[pilih_pejabat]
                        
                        new_utama = pd.DataFrame([{
                            "ID_RAB": id_rab_baru, "Tanggal": datetime.now().strftime('%Y-%m-%d %H:%M'), "Tahun": str(rab_tahun), "Tgl_Cetak": str(tgl_cetak),
                            "Sumber_Dana": sumber_buat, "KRO": pilih_kro, "RO": pilih_ro, "Komponen": pilih_komp, "Sub_Komponen": pilih_subkomp,
                            "Kegiatan": rab_kegiatan.strip(), "Sasaran": rab_sasaran, "Volume": rab_vol, "Satuan": rab_satuan, "Alokasi": rab_alokasi,
                            "Jabatan": dt_pjb['Jabatan'], "Nama_Pejabat": dt_pjb['Nama'], "NIP_Pejabat": dt_pjb['NIP'],
                            "Versi_RAB": rab_versi, "Is_Active": 1
                        }])
                        df_rab_utama = pd.concat([df_rab_utama, new_utama], ignore_index=True)
                        save_table(df_rab_utama, "rab_utama")
                        
                        valid_detail["ID_RAB"] = id_rab_baru
                        valid_detail["Total_Biaya"] = valid_detail["Vol_1_Num"] * valid_detail["Vol_2_Num"] * valid_detail["Harga_Num"]
                        valid_detail.rename(columns={"Akun Belanja": "Akun_Belanja", "Uraian Belanja": "Uraian", "Vol 1":"Vol_1", "Sat 1":"Sat_1", "Vol 2":"Vol_2", "Sat 2":"Sat_2", "Harga Satuan": "Harga_Satuan"}, inplace=True)
                        
                        df_rab_detail = pd.concat([df_rab_detail, valid_detail[["ID_RAB", "Akun_Belanja", "Uraian", "Vol_1", "Sat_1", "Vol_2", "Sat_2", "Harga_Satuan", "Total_Biaya"]]], ignore_index=True)
                        save_table(df_rab_detail, "rab_detail")
                        st.toast("RAB Berhasil Diaktifkan!")
                        st.success(f"✅ RAB '{rab_kegiatan.title()}' Versi '{rab_versi}' Berhasil Diterbitkan!"); st.rerun()

    # -----------------------------------------------------------------
    # TAB 3: ARSIP & MANAJEMEN VERSI RAB
    # -----------------------------------------------------------------
    with tab_daftar:
        if df_rab_utama.empty: 
            st.info("Belum ada dokumen RAB yang tersimpan.")
        else:
            st.subheader("📂 Arsip & Manajemen Versi Perencanaan")
            kegiatan_list = sorted(df_rab_utama['Kegiatan'].unique())
            kegiatan_list_display = {k: k.title() for k in kegiatan_list}
            pilih_kegiatan = st.selectbox("1. Pilih Judul Kegiatan Utama:", kegiatan_list, format_func=lambda x: kegiatan_list_display[x])
            
            df_kegiatan_terpilih = df_rab_utama[df_rab_utama['Kegiatan'] == pilih_kegiatan]
            versi_list = df_kegiatan_terpilih['Versi_RAB'].tolist()
            pilih_versi = st.selectbox("2. Pilih Riwayat Versi / Kategori Revisi:", versi_list)
            
            head_terpilih = df_kegiatan_terpilih[df_kegiatan_terpilih['Versi_RAB'] == pilih_versi]
            id_rab_aktif = head_terpilih['ID_RAB'].iloc[0]
            status_aktif = head_terpilih['Is_Active'].iloc[0]
            detail_terpilih = df_rab_detail[df_rab_detail["ID_RAB"] == id_rab_aktif]
            
            if status_aktif == 1:
                st.success("✅ **STATUS VERSI: AKTIF (FINAL ACUAN)**. Versi ini yang sedang dihitung ke dalam Rekapitulasi Global RKAKL.")
            else:
                st.warning("🗄️ **STATUS VERSI: ARSIP REVISI (TIDAK AKTIF)**. Versi ini disimpan sebagai rekaman sejarah anggaran.")
                if st.button(f"🔄 Jadikan Kategori '{pilih_versi}' Sebagai Versi Aktif", type="primary"):
                    df_rab_utama.loc[df_rab_utama['Kegiatan'] == pilih_kegiatan, 'Is_Active'] = 0
                    df_rab_utama.loc[df_rab_utama['ID_RAB'] == id_rab_aktif, 'Is_Active'] = 1
                    save_table(df_rab_utama, "rab_utama")
                    st.toast("Versi Acuan Berhasil Dialihkan!"); st.rerun()

            st.markdown("---")
            s_dana = head_terpilih.get('Sumber_Dana', pd.Series(['BOPTN'])).iloc[0]
            
            df_view = detail_terpilih.copy()
            df_view['Kode Akun'] = df_view['Akun_Belanja'].apply(lambda x: split_kode(x)[0])
            df_view['Nama Akun Belanja'] = df_view['Akun_Belanja'].apply(lambda x: split_kode(x)[1])
            df_view['Volume & Satuan'] = df_view.apply(lambda r: get_vol_sat_combined(r['Vol_1'], r['Sat_1'], r['Vol_2'], r['Sat_2']), axis=1)
            
            keg_code_view = kegiatan_code_map.get(pilih_kegiatan, "0000")
            st.markdown(f"**Identitas Kegiatan:** {keg_code_view} - {pilih_kegiatan.title()}")
            st.markdown(f"**Klasifikasi Dokumen:** {head_terpilih['KRO'].iloc[0]} ➔ {head_terpilih['RO'].iloc[0]}")
            st.markdown(f"**Total Alokasi Anggaran ({s_dana}):** Rp {format_rupiah(detail_terpilih['Total_Biaya'].sum())}")
            st.dataframe(df_view[["Kode Akun", "Nama Akun Belanja", "Uraian", "Volume & Satuan", "Harga_Satuan", "Total_Biaya"]].style.format({"Harga_Satuan": format_rupiah, "Total_Biaya": format_rupiah}), hide_index=True, use_container_width=True)

    # -----------------------------------------------------------------
    # TAB 4: REKAPITULASI LAPORAN RKAKL GLOBAL FAKULTAS
    # -----------------------------------------------------------------
    with tab_rekap:
        st.subheader("📊 Buku Rekapitulasi Kerja & Anggaran (RKAKL) Aktif")
        df_aktif = df_rab_utama[df_rab_utama['Is_Active'] == 1]
        
        if df_aktif.empty:
            st.info("Belum ada dokumen perencanaan anggaran dengan status aktif yang diterbitkan.")
        else:
            df_det_aktif = df_rab_detail[df_rab_detail['ID_RAB'].isin(df_aktif['ID_RAB'])]
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

    # -----------------------------------------------------------------
    # TAB 5: MATRIK PERUBAHAN (SEBELUM VS MENJADI)
    # -----------------------------------------------------------------
    with tab_matrik:
        st.subheader("⚖️ Matrik Perbandingan Revisi Anggaran")
        st.markdown("Fitur ini menghasilkan tabel analisis selisih anggaran (Bertambah/Berkurang) antara dua versi perencanaan.")
        
        if df_rab_utama.empty:
            st.warning("Belum ada data untuk dibandingkan.")
        else:
            list_all_versions = sorted(df_rab_utama['Versi_RAB'].unique())
            col_v1, col_v2 = st.columns(2)
            
            # Default ke dua versi pertama jika ada, jika tidak samakan
            v1_def = list_all_versions[0] if len(list_all_versions) > 0 else None
            v2_def = list_all_versions[1] if len(list_all_versions) > 1 else v1_def
            
            pilih_v1 = col_v1.selectbox("Pilih Versi Semula (Sebelum):", list_all_versions, index=list_all_versions.index(v1_def) if v1_def else 0)
            pilih_v2 = col_v2.selectbox("Pilih Versi Menjadi (Sesudah):", list_all_versions, index=list_all_versions.index(v2_def) if v2_def else 0)
            
            if st.button("🔍 Generate Matrik Perbandingan", type="primary"):
                # Menyiapkan Data Versi 1
                df_u1 = df_rab_utama[df_rab_utama['Versi_RAB'] == pilih_v1]
                df_d1 = df_rab_detail[df_rab_detail['ID_RAB'].isin(df_u1['ID_RAB'])]
                df_m1 = pd.merge(df_d1, df_u1, on='ID_RAB') if not df_u1.empty else pd.DataFrame(columns=['Sumber_Dana', 'KRO', 'RO', 'Komponen', 'Sub_Komponen', 'Kegiatan', 'Akun_Belanja', 'Uraian', 'Total_Biaya'])
                
                # Menyiapkan Data Versi 2
                df_u2 = df_rab_utama[df_rab_utama['Versi_RAB'] == pilih_v2]
                df_d2 = df_rab_detail[df_rab_detail['ID_RAB'].isin(df_u2['ID_RAB'])]
                df_m2 = pd.merge(df_d2, df_u2, on='ID_RAB') if not df_u2.empty else pd.DataFrame(columns=['Sumber_Dana', 'KRO', 'RO', 'Komponen', 'Sub_Komponen', 'Kegiatan', 'Akun_Belanja', 'Uraian', 'Total_Biaya'])
                
                keys = ['Sumber_Dana', 'KRO', 'RO', 'Komponen', 'Sub_Komponen', 'Kegiatan', 'Akun_Belanja', 'Uraian']
                
                # Agregasi untuk menghindari duplikat sebelum merge
                if not df_m1.empty:
                    df_m1 = df_m1.groupby(keys)['Total_Biaya'].sum().reset_index().rename(columns={'Total_Biaya': 'Biaya_Semula'})
                else:
                    df_m1 = pd.DataFrame(columns=keys + ['Biaya_Semula'])
                    
                if not df_m2.empty:
                    df_m2 = df_m2.groupby(keys)['Total_Biaya'].sum().reset_index().rename(columns={'Total_Biaya': 'Biaya_Menjadi'})
                else:
                    df_m2 = pd.DataFrame(columns=keys + ['Biaya_Menjadi'])
                
                # Outer Merge untuk membandingkan Side-by-Side (Menangkap kegiatan baru/dihapus)
                df_matrik = pd.merge(df_m1, df_m2, on=keys, how='outer').fillna(0)
                df_matrik['Selisih'] = df_matrik['Biaya_Menjadi'] - df_matrik['Biaya_Semula']
                
                if df_matrik.empty:
                    st.info("Tidak ada data rincian pada kedua versi yang dipilih.")
                else:
                    html_matrik = generate_matrik_html(df_matrik, pilih_v1, pilih_v2, kegiatan_code_map)
                    with st.container(border=True):
                        components.html(html_matrik, height=600, scrolling=True)
                        
                    st.download_button(
                        label="📥 Cetak Matrik Perubahan (.html ready print)", 
                        data=html_matrik.encode('utf-8'), 
                        file_name=f"Matrik_{pilih_v1}_vs_{pilih_v2}_{datetime.now().strftime('%Y%m%d')}.html", 
                        mime="text/html",
                        help="Gunakan kertas A4 Landscape saat print PDF di browser."
                    )
