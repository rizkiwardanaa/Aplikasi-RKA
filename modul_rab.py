import streamlit as st
import pandas as pd
import os
from io import BytesIO
from datetime import datetime
from sqlalchemy import create_engine # Pengganti sqlite3

# --- KONEKSI KE CLOUD DATABASE ---
DB_URL = st.secrets["DB_URL"]
engine = create_engine(DB_URL)

# --- FUNGSI DATABASE MASTER RAB (DITAMBAH SUMBER DANA) ---
def load_table(table_name, default_cols):
    conn = engine.connect() # Menggunakan koneksi engine
    try:
        # Membaca dari PostgreSQL
        df = pd.read_sql(f"SELECT * FROM {table_name}", engine)
        for col in default_cols:
            if col not in df.columns:
                if "Vol" in col or "Harga" in col or "Total" in col: df[col] = 1 if "Vol" in col else 0
                elif col == "Tahun": df[col] = "2027"
                elif col == "Sumber_Dana": df[col] = "BOPTN"
                elif col == "Sub_Komponen" and table_name == "rab_m_akun": df[col] = "-"
                else: df[col] = "-"
    except:
        df = pd.DataFrame(columns=default_cols)
        df.to_sql(table_name, engine, index=False)
    return df

def save_table(df, table_name):
    df.to_sql(table_name, engine, if_exists="replace", index=False)

# ... (KODE KE BAWAHNYA TETAP SAMA PERSIS, DIMULAI DARI def format_rupiah(x): ) ...

def format_rupiah(x):
    """
    Fungsi untuk mengubah angka menjadi format Rupiah (pemisah ribuan dengan titik).
    Contoh: 1500000 menjadi 1.500.000
    """
    try: return f"{float(x):,.0f}".replace(',', '.')
    except (ValueError, TypeError): return x

def split_kode(teks):
    """
    Fungsi untuk memisahkan kode angka dan narasi (teks uraian).
    Contoh: "051 - Penelitian" akan dipisah menjadi "051" dan "Penelitian".
    """
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
    """
    Fungsi untuk menggabungkan dua pasang Volume dan Satuan menjadi satu teks.
    Jika Vol 2 kosong, hanya akan menampilkan "Vol 1 Satuan 1".
    Jika ada keduanya, menampilkan "Vol 1 Sat 1 x Vol 2 Sat 2".
    """
    v1_str = str(v1).replace(".0", "") if pd.notna(v1) else "0"
    s1_str = str(s1).strip() if pd.notna(s1) else ""
    v2_str = str(v2).replace(".0", "") if pd.notna(v2) else "0"
    s2_str = str(s2).strip() if pd.notna(s2) else ""
    if s2_str in ["", "-"] or v2_str == "0" or v2_str == "":
        return f"{v1_str} {s1_str}"
    return f"{v1_str} {s1_str} x {v2_str} {s2_str}"


# =====================================================================
# FUNGSI TAMPILAN HALAMAN UTAMA (SHOW PAGE)
# =====================================================================

def show_page():
    """
    Fungsi utama yang merender seluruh halaman 'Pengolah Dokumen RAB'.
    Berisi 3 Tab: Master Database, Buat RAB, dan Daftar Tersimpan.
    """
    # 1. Memuat seluruh tabel master dari database
    df_m_kro = load_table("rab_m_kro", ["KRO", "Sumber_Dana"])
    df_m_ro = load_table("rab_m_ro", ["KRO", "RO", "Sumber_Dana"])
    df_m_komp = load_table("rab_m_komp", ["RO", "Komponen", "Sumber_Dana"])
    df_m_subkomp = load_table("rab_m_subkomp", ["Komponen", "Sub_Komponen", "Sumber_Dana"])
    df_m_akun = load_table("rab_m_akun", ["Sub_Komponen", "Account_Code", "Account_Name", "Sumber_Dana"]) 
    df_m_pejabat = load_table("rab_m_pejabat", ["Jabatan", "Nama", "NIP"])

    # 2. Memuat tabel transaksi (Header dan Detail RAB)
    df_rab_utama = load_table("rab_utama", ["ID_RAB", "Tanggal", "Tahun", "Tgl_Cetak", "Sumber_Dana", "KRO", "RO", "Komponen", "Sub_Komponen", "Kegiatan", "Sasaran", "Volume", "Satuan", "Alokasi", "Jabatan", "Nama_Pejabat", "NIP_Pejabat"])
    df_rab_detail = load_table("rab_detail", ["ID_RAB", "Akun_Belanja", "Uraian", "Vol_1", "Sat_1", "Vol_2", "Sat_2", "Harga_Satuan", "Total_Biaya"])

    st.title("📄 Pengolah Dokumen RAB Universitas")
    st.caption("Sistem Manajemen & Generator RAB Berjenjang dengan Pemisahan Kode Otomatis & Sumber Dana.")

    tab_master, tab_buat, tab_daftar = st.tabs(["🗂️ Master Database", "📝 Buat RAB Baru", "📂 Daftar RAB Tersimpan"])

    # -----------------------------------------------------------------
    # TAB 1: MASTER DATABASE
    # -----------------------------------------------------------------
    with tab_master:
        st.info("💡 Input Master Data. Format bebas, mesin otomatis memisahkan teks sebelum tanda strip '-' ke kolom Kode Excel.")
        
        # --- BLOK 1: RESTORE DATA STANDAR ---
        with st.expander("⚡ Restore Database Master FIB (Otomatis)", expanded=False):
            st.warning("Klik tombol di bawah ini untuk memulihkan seluruh data standar KRO, RO, Komponen, dan 50+ Akun Belanja (Telah Terbagi BOPTN & PNBP).")
            if st.button("🚀 Restore Data Standar FIB", type="primary"):

                # MASTER KRO
                df_kro_baru = pd.DataFrame([
                    {"KRO": "7729.BEI - Bantuan Lembaga", "Sumber_Dana": "BOPTN"},
                    {"KRO": "7730.CAA - Sarana Bidang Pendidikan", "Sumber_Dana": "PNBP"},
                    {"KRO": "7730.CBJ - Prasarana Bidang Pendidikan Tinggi", "Sumber_Dana": "PNBP"},
                    {"KRO": "7730.DBA - Pendidikan Tinggi", "Sumber_Dana": "PNBP"}
                ])
                save_table(df_kro_baru, "rab_m_kro")
            
                # MASTER RO
                df_ro_baru = pd.DataFrame([
                    # ===== BOPTN =====
                    {"KRO": "7729.BEI - Bantuan Lembaga", "RO": "7729.BEI.001 - PT Penerima Bantuan Dukungan Operasional", "Sumber_Dana": "BOPTN"},
                    {"KRO": "7729.BEI - Bantuan Lembaga", "RO": "7729.BEI.002 - PT Penerima Bantuan Pembelajaran", "Sumber_Dana": "BOPTN"},
                    {"KRO": "7729.BEI - Bantuan Lembaga", "RO": "7729.BEI.004 - PT Penerima Bantuan Sarana dan Prasarana Pembelajaran", "Sumber_Dana": "BOPTN"},
                    # ===== PNBP =====
                    {"KRO": "7730.CAA - Sarana Bidang Pendidikan", "RO": "7730.CAA.001 - Sarana Pendukung Pembelajaran", "Sumber_Dana": "PNBP"},
                    {"KRO": "7730.CAA - Sarana Bidang Pendidikan", "RO": "7730.CAA.002 - Sarana Pendukung Perkantoran", "Sumber_Dana": "PNBP"},
                    {"KRO": "7730.CBJ - Prasarana Bidang Pendidikan Tinggi", "RO": "7730.CBJ.001 - Prasarana Pendukung Pembelajaran", "Sumber_Dana": "PNBP"},
                    {"KRO": "7730.CBJ - Prasarana Bidang Pendidikan Tinggi", "RO": "7730.CBJ.002 - Prasarana Pendukung Perkantoran", "Sumber_Dana": "PNBP"},
                    {"KRO": "7730.DBA - Pendidikan Tinggi", "RO": "7730.DBA.001 - Layanan Pendidikan", "Sumber_Dana": "PNBP"},
                    {"KRO": "7730.DBA - Pendidikan Tinggi", "RO": "7730.DBA.002 - Dukungan Operasional Pembelajaran", "Sumber_Dana": "PNBP"},
                    {"KRO": "7730.DBA - Pendidikan Tinggi", "RO": "7730.DBA.003 - Penelitian dan Pengabdian Masyarakat", "Sumber_Dana": "PNBP"},
                    {"KRO": "7730.DBA - Pendidikan Tinggi", "RO": "7730.DBA.004 - Pengabdian Kepada Masyarakat", "Sumber_Dana": "PNBP"}
                ])
                save_table(df_ro_baru, "rab_m_ro")
            
                # MASTER KOMPONEN
                df_komp_baru = pd.DataFrame([
                    # ===== BOPTN =====
                    {"RO": "7729.BEI.001 - PT Penerima Bantuan Dukungan Operasional", "Komponen": "004 - Dukungan Operasional Penyelenggaraan Pendidikan", "Sumber_Dana": "BOPTN"},
                    {"RO": "7729.BEI.002 - PT Penerima Bantuan Pembelajaran", "Komponen": "004 - Dukungan Operasional Penyelenggaraan Pendidikan", "Sumber_Dana": "BOPTN"},
                    {"RO": "7729.BEI.004 - PT Penerima Bantuan Sarana dan Prasarana Pembelajaran", "Komponen": "004 - Dukungan Operasional Penyelenggaraan Pendidikan", "Sumber_Dana": "BOPTN"},
                    # ===== PNBP =====
                    {"RO": "7730.CAA.001 - Sarana Pendukung Pembelajaran", "Komponen": "051 - Pengadaan Sarana Pendukung Pembelajaran", "Sumber_Dana": "PNBP"},
                    {"RO": "7730.CAA.002 - Sarana Pendukung Perkantoran", "Komponen": "051 - Sarana Pendukung Perkantoran", "Sumber_Dana": "PNBP"},
                    {"RO": "7730.CBJ.001 - Prasarana Pendukung Pembelajaran", "Komponen": "051 - Pengadaan Prasarana Pendukung Pembelajaran", "Sumber_Dana": "PNBP"},
                    {"RO": "7730.CBJ.002 - Prasarana Pendukung Perkantoran", "Komponen": "051 - Pengadaan Prasarana Pendukung Perkantoran", "Sumber_Dana": "PNBP"},
                    {"RO": "7730.DBA.001 - Layanan Pendidikan", "Komponen": "051 - Pemeliharaan Sarana dan Prasarana Pembelajaran", "Sumber_Dana": "PNBP"},
                    {"RO": "7730.DBA.001 - Layanan Pendidikan", "Komponen": "052 - Pemeliharaan Sarana dan Prasarana Perkantoran", "Sumber_Dana": "PNBP"},
                    {"RO": "7730.DBA.001 - Layanan Pendidikan", "Komponen": "053 - Penyelenggaraan Layanan Pendidikan Perguruan Tinggi", "Sumber_Dana": "PNBP"},
                    {"RO": "7730.DBA.002 - Dukungan Operasional Pembelajaran", "Komponen": "051 - Penyelenggaraan Dukungan Operasional Pembelajaran", "Sumber_Dana": "PNBP"},
                    {"RO": "7730.DBA.002 - Dukungan Operasional Pembelajaran", "Komponen": "053 - Pelaksanaan Layanan Pengembangan Sistem Tata Kelola", "Sumber_Dana": "PNBP"},
                    {"RO": "7730.DBA.003 - Penelitian dan Pengabdian Masyarakat", "Komponen": "051 - Penelitian", "Sumber_Dana": "PNBP"},
                    {"RO": "7730.DBA.003 - Penelitian dan Pengabdian Masyarakat", "Komponen": "052 - Pengabdian Kepada Masyarakat", "Sumber_Dana": "PNBP"}
                ])
                save_table(df_komp_baru, "rab_m_komp")

                # MASTER AKUN BELANJA
                akun_standar = [
                    {"Account_Code": "521111", "Account_Name": "Belanja Keperluan Perkantoran"},
                    {"Account_Code": "521115", "Account_Name": "Belanja Honor Operasional Satuan Kerja"},
                    {"Account_Code": "521119", "Account_Name": "Belanja Barang Operasional Lainnya"},
                    {"Account_Code": "521211", "Account_Name": "Belanja Bahan"},
                    {"Account_Code": "521219", "Account_Name": "Belanja Barang Non Operasional Lainnya"},
                    {"Account_Code": "522131", "Account_Name": "Belanja Jasa Konsultan"},
                    {"Account_Code": "522141", "Account_Name": "Belanja Sewa"},
                    {"Account_Code": "522151", "Account_Name": "Belanja Jasa Profesi"},
                    {"Account_Code": "523121", "Account_Name": "Belanja Biaya Pemeliharaan Peralatan dan Mesin"},
                    {"Account_Code": "524111", "Account_Name": "Belanja Perjalanan Dinas Biasa"},
                    {"Account_Code": "524114", "Account_Name": "Belanja Perjalanan Dinas Paket Meeting Dalam Kota"},
                    {"Account_Code": "524119", "Account_Name": "Belanja Perjalanan Dinas Paket Luar Kota"},
                    {"Account_Code": "525112", "Account_Name": "Belanja Barang"},
                    {"Account_Code": "525113", "Account_Name": "Belanja Jasa"},
                    {"Account_Code": "525115", "Account_Name": "Belanja Perjalanan Dinas"},
                    {"Account_Code": "525162", "Account_Name": "Belanja Peralatan dan Mesin Ekstrakomptabel BLU"},
                    {"Account_Code": "532111", "Account_Name": "Belanja Modal Peralatan dan Mesin"},
                    {"Account_Code": "537112", "Account_Name": "Belanja Modal Peralatan dan Mesin - BLU"}
                ]
                
                df_akun_boptn = pd.DataFrame(akun_standar); df_akun_boptn["Sumber_Dana"] = "BOPTN"; df_akun_boptn["Sub_Komponen"] = "-"
                df_akun_pnbp = pd.DataFrame(akun_standar); df_akun_pnbp["Sumber_Dana"] = "PNBP"; df_akun_pnbp["Sub_Komponen"] = "-"
                df_akun_gabung = pd.concat([df_akun_boptn, df_akun_pnbp], ignore_index=True)
                save_table(df_akun_gabung, "rab_m_akun")
                
                st.success("🎉 BOOM! Seluruh Data Master FIB (BOPTN & PNBP) berhasil dipulihkan secara otomatis!"); st.rerun()

        # --- BLOK 2: IMPORT & EXPORT EXCEL ---
        with st.expander("💾 Import & Export Data Master (Excel)", expanded=False):
            st.info("Gunakan fitur ini untuk mem-backup seluruh data master ke Excel, atau memulihkan data master dari file Excel.")
            c_eks, c_imp = st.columns(2)
            
            # FITUR EXPORT
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
            
            # FITUR IMPORT
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
                    else:
                        st.warning("⚠️ Pilih file Excel terlebih dahulu!")

        # --- BLOK 3: EDITOR DATA MASTER MANUAL ---
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
            
            # Editor akun kini ditambahkan mapping ke "Sub_Komponen"
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
            st.subheader("1. Klasifikasi Output RAB")
            
            # --- FILTER HIERARKI MENGGUNAKAN CASCADE (BERJENJANG) ---
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

            st.markdown("---")
            st.subheader("2. Informasi Utama Kegiatan")
            col_u1, col_u2 = st.columns(2)
            rab_kegiatan = col_u1.text_input("Nama Kegiatan", placeholder="Contoh: Pemeliharaan Alat Operasional Pendukung TIK")
            
            # Mengisi Sasaran Kegiatan secara otomatis dari narasi KRO
            _, kro_narasi = split_kode(pilih_kro) if pilih_kro else ("", "")
            kro_narasi_bersih = kro_narasi.strip("() ")
            default_sasaran = f"Peningkatan {kro_narasi_bersih}" if kro_narasi_bersih else ""
            
            rab_sasaran = col_u2.text_input("Sasaran Kegiatan", value=default_sasaran)
            rab_vol = col_u1.number_input("Volume Target", value=1, min_value=1)
            rab_satuan = col_u2.text_input("Satuan Ukur", placeholder="Contoh: Layanan / Bulan")
            rab_tahun = col_u1.text_input("Tahun Anggaran", value="2027")

            st.markdown("---")
            st.subheader("3. Rincian Belanja (Pengali Volume & Satuan)")
            
            # --- FILTER AKUN BERDASARKAN SUB-KOMPONEN YANG DIPILIH ---
            df_akun_f = df_m_akun[(df_m_akun['Sumber_Dana'] == sumber_buat) & (df_m_akun['Sub_Komponen'] == pilih_subkomp)]
            opsi_akun = [f"{row['Account_Code']} - {row['Account_Name']}" for _, row in df_akun_f.iterrows()]
            
            if not opsi_akun:
                st.warning(f"⚠️ Belum ada Akun Belanja yang terhubung ke Sub-Komponen '{pilih_subkomp}'. Silakan petakan di tab Master Database.")
                opsi_akun = ["- Tidak ada akun terpetakan -"]
            
            template_detail = pd.DataFrame([{"Akun Belanja": opsi_akun[0], "Uraian Belanja": "", "Vol 1": 1, "Sat 1": "Unit", "Vol 2": 1, "Sat 2": "-", "Harga Satuan": 0}])
            
            # Grid Input Data Belanja
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

            # Menghitung otomatis Total Biaya per item
            df_input_detail["Vol_1_Num"] = pd.to_numeric(df_input_detail["Vol 1"]).fillna(1)
            df_input_detail["Vol_2_Num"] = pd.to_numeric(df_input_detail["Vol 2"]).fillna(1)
            df_input_detail.loc[df_input_detail["Vol_2_Num"] == 0, "Vol_2_Num"] = 1 # Hindari kali 0
            df_input_detail["Harga_Num"] = pd.to_numeric(df_input_detail["Harga Satuan"]).fillna(0)
            
            total_rab_live = (df_input_detail["Vol_1_Num"] * df_input_detail["Vol_2_Num"] * df_input_detail["Harga_Num"]).sum()
            
            st.markdown("#### 💰 Akumulasi Anggaran Alokasi Dana")
            st.metric(f"Total Alokasi Dana ({sumber_buat})", f"Rp {format_rupiah(total_rab_live)}")
            rab_alokasi = total_rab_live

            st.markdown("---")
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
                    # Logic Simpan Tabel Utama
                    id_rab_baru = f"RAB-{datetime.now().strftime('%Y%m%d%H%M%S')}"
                    tgl_sekarang = datetime.now().strftime('%Y-%m-%d %H:%M')
                    dt_pjb = df_m_pejabat.loc[pilih_pejabat]
                    
                    new_utama = pd.DataFrame([{
                        "ID_RAB": id_rab_baru, "Tanggal": tgl_sekarang, "Tahun": str(rab_tahun), "Tgl_Cetak": str(tgl_cetak),
                        "Sumber_Dana": sumber_buat, "KRO": pilih_kro, "RO": pilih_ro, "Komponen": pilih_komp, "Sub_Komponen": pilih_subkomp,
                        "Kegiatan": rab_kegiatan, "Sasaran": rab_sasaran, "Volume": rab_vol, "Satuan": rab_satuan, "Alokasi": rab_alokasi,
                        "Jabatan": dt_pjb['Jabatan'], "Nama_Pejabat": dt_pjb['Nama'], "NIP_Pejabat": dt_pjb['NIP']
                    }])
                    df_rab_utama = pd.concat([df_rab_utama, new_utama], ignore_index=True)
                    save_table(df_rab_utama, "rab_utama")
                    
                    # Logic Simpan Tabel Detail Belanja
                    valid_detail["ID_RAB"] = id_rab_baru
                    valid_detail["Total_Biaya"] = valid_detail["Vol_1_Num"] * valid_detail["Vol_2_Num"] * valid_detail["Harga_Num"]
                    valid_detail.rename(columns={"Akun Belanja": "Akun_Belanja", "Uraian Belanja": "Uraian", "Vol 1":"Vol_1", "Sat 1":"Sat_1", "Vol 2":"Vol_2", "Sat 2":"Sat_2", "Harga Satuan": "Harga_Satuan"}, inplace=True)
                    
                    df_rab_detail = pd.concat([df_rab_detail, valid_detail[["ID_RAB", "Akun_Belanja", "Uraian", "Vol_1", "Sat_1", "Vol_2", "Sat_2", "Harga_Satuan", "Total_Biaya"]]], ignore_index=True)
                    save_table(df_rab_detail, "rab_detail")
                    st.success(f"✅ RAB Resmi '{rab_kegiatan}' Berhasil Terbit!"); st.rerun()

    # -----------------------------------------------------------------
    # TAB 3: DAFTAR RAB TERSIMPAN & EXPORT (PDF/EXCEL)
    # -----------------------------------------------------------------
    with tab_daftar:
        if df_rab_utama.empty: st.info("Belum ada dokumen RAB yang tersimpan.")
        else:
            st.subheader("Arsip Dokumen RAB")
            opsi_arsip = {row['ID_RAB']: f"[{row['Sumber_Dana']}] {row['Kegiatan']} ({row['Tahun']})" for _, row in df_rab_utama.iterrows()}
            pilih_arsip = st.selectbox("Pilih RAB yang ingin dilihat/diunduh:", options=list(opsi_arsip.keys()), format_func=lambda x: opsi_arsip[x])
            
            head_terpilih = df_rab_utama[df_rab_utama["ID_RAB"] == pilih_arsip]
            detail_terpilih = df_rab_detail[df_rab_detail["ID_RAB"] == pilih_arsip]
            
            s_dana = head_terpilih.get('Sumber_Dana', pd.Series(['BOPTN'])).iloc[0]
            tahun_rab = head_terpilih.get('Tahun', pd.Series(['2027'])).iloc[0]

            df_view = detail_terpilih.copy()
            df_view['Kode Akun'] = df_view['Akun_Belanja'].apply(lambda x: split_kode(x)[0])
            df_view['Nama Akun Belanja'] = df_view['Akun_Belanja'].apply(lambda x: split_kode(x)[1])
            df_view['Volume & Satuan'] = df_view.apply(lambda r: get_vol_sat_combined(r['Vol_1'], r['Sat_1'], r['Vol_2'], r['Sat_2']), axis=1)
            
            st.markdown(f"**Klasifikasi Dokumen:** {head_terpilih['KRO'].iloc[0]} ➔ {head_terpilih['RO'].iloc[0]}")
            st.markdown(f"**Total Anggaran Terakumulasi ({s_dana}):** Rp {format_rupiah(detail_terpilih['Total_Biaya'].sum())}")
            
            st.dataframe(df_view[["Kode Akun", "Nama Akun Belanja", "Uraian", "Volume & Satuan", "Harga_Satuan", "Total_Biaya"]].style.format({"Harga_Satuan": format_rupiah, "Total_Biaya": format_rupiah}), hide_index=True, use_container_width=True)
            
            # --- MESIN CETAK EXCEL (FIT TO 1 PAGE, COMPACT ROWS) ---
            def export_excel_rab(df_header, df_items):
                import openpyxl
                from openpyxl.styles import Font, Alignment, Border, Side
                wb = openpyxl.Workbook(); ws = wb.active; ws.title = "RAB Export"
                
                ws.column_dimensions['A'].width = 15 # Kode
                ws.column_dimensions['B'].width = 45 # Uraian
                ws.column_dimensions['C'].width = 25 # Volume & Satuan
                ws.column_dimensions['D'].width = 16 # Harga
                ws.column_dimensions['E'].width = 16 # Total
                
                ws.sheet_properties.pageSetUpPr.fitToPage = True
                ws.page_setup.fitToHeight = 1
                ws.page_setup.fitToWidth = 1
                
                font_bold = Font(bold=True); font_header = Font(bold=True, size=11); align_center = Alignment(horizontal="center", vertical="center")
                border_all = Border(left=Side(style='thin'), right=Side(style='thin'), top=Side(style='thin'), bottom=Side(style='thin'))

                ws.merge_cells('A1:E1')
                t_rab = df_header.get('Tahun', pd.Series(['2027'])).iloc[0]
                ws['A1'] = f"RINCIAN ANGGARAN BIAYA (RAB) FAKULTAS ILMU BUDAYA\nTAHUN ANGGARAN {t_rab}"
                ws['A1'].alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
                ws['A1'].font = font_header
                ws.row_dimensions[1].height = 40

                meta_rows = [
                    ("Kementerian/ Lembaga:", "(023) KEMENTERIAN PENDIDIKAN TINGGI, SAINS DAN TEKNOLOGI"), 
                    ("Unit Eselon II/ Satker:", "(17) Dirjen Diktiristek / (677524) UNIVERSITAS MULAWARMAN"),
                    ("Sumber Dana:", df_header.get('Sumber_Dana', pd.Series(['BOPTN'])).iloc[0]),
                    ("Kegiatan:", df_header['Kegiatan'].iloc[0]), ("Sasaran Kegiatan:", df_header['Sasaran'].iloc[0]), 
                    ("Klasifikasi Rincian Output:", df_header['KRO'].iloc[0]),
                    ("Volume:", df_header['Volume'].iloc[0]), ("Satuan Ukur:", df_header['Satuan'].iloc[0]), 
                    ("Alokasi Dana (Total Belanja):", f"Rp. {df_items['Total_Biaya'].sum():,.0f}".replace(',','.'))
                ]
                rp = 2
                for label, val in meta_rows:
                    ws.cell(row=rp, column=1, value=label).font = font_bold
                    ws.cell(row=rp, column=2, value=val)
                    ws.merge_cells(start_row=rp, start_column=2, end_row=rp, end_column=5)
                    rp += 1

                rp += 1
                for col_idx, text in enumerate(["Kode", "Rincian Belanja", "Volume & Satuan", "Harga Satuan", "Jumlah Biaya"], start=1):
                    cell = ws.cell(row=rp, column=col_idx, value=text); cell.font = font_bold; cell.alignment = align_center; cell.border = border_all
                rp += 1

                # Fungsi Cetak Hierarki ke Baris Excel
                def print_row(kode, urai, vol, hrg, tot, is_bold=False):
                    nonlocal rp
                    ws.cell(row=rp, column=1, value=kode).border = border_all
                    ws.cell(row=rp, column=2, value=urai).border = border_all
                    ws.cell(row=rp, column=3, value=vol).border = border_all
                    ws.cell(row=rp, column=4, value=hrg).border = border_all
                    if hrg != "": ws.cell(row=rp, column=4).number_format = '#,##0'
                    ws.cell(row=rp, column=5, value=tot).border = border_all; ws.cell(row=rp, column=5).number_format = '#,##0'
                    if is_bold: 
                        for col in range(1,6): ws.cell(row=rp, column=col).font = Font(bold=True)
                    rp += 1

                total_seluruh = df_items["Total_Biaya"].sum()
                for head_col, indent in [('RO', ""), ('Komponen', "  "), ('Sub_Komponen', "    ")]:
                    if df_header[head_col].iloc[0] and str(df_header[head_col].iloc[0]).strip() not in ["", "-", "Tidak Ada Sub-Komponen"]:
                        k_val, u_val = split_kode(df_header[head_col].iloc[0])
                        if "." in k_val and len(k_val.split(".")) == 2 and len(k_val.split(".")[0]) == 3:
                            k1, k2 = k_val.split(".")
                            print_row(k1, f"{indent}{u_val}", "", "", total_seluruh, True)
                            print_row(k2, f"{indent}", "", "", total_seluruh, True)
                        else:
                            print_row(k_val, f"{indent}{u_val}", "", "", total_seluruh, True)

                for akun, group in df_items.groupby("Akun_Belanja"):
                    k_ak, u_ak = split_kode(akun)
                    print_row(k_ak, f"      {u_ak}", "", "", group['Total_Biaya'].sum(), True)
                    for _, r in group.iterrows():
                        v_sat = get_vol_sat_combined(r['Vol_1'], r['Sat_1'], r['Vol_2'], r['Sat_2'])
                        print_row("", f"        - {r['Uraian']}", v_sat, r['Harga_Satuan'], r['Total_Biaya'])
                        
                rp += 2
                bulan_indo = ["Januari", "Februari", "Maret", "April", "Mei", "Juni", "Juli", "Agustus", "September", "Oktober", "November", "Desember"]
                try: 
                    tobj = datetime.strptime(df_header['Tgl_Cetak'].iloc[0], "%Y-%m-%d")
                    tgl_str = f"Samarinda, {tobj.day} {bulan_indo[tobj.month-1]} {tobj.year}"
                except: tgl_str = f"Samarinda, {df_header['Tgl_Cetak'].iloc[0]}"
                
                ws.cell(row=rp, column=4, value=tgl_str)
                ws.cell(row=rp+1, column=4, value=df_header['Jabatan'].iloc[0])
                ws.cell(row=rp+5, column=4, value=df_header['Nama_Pejabat'].iloc[0]).font = Font(underline="single", bold=True)
                ws.cell(row=rp+6, column=4, value=f"NIP. {df_header['NIP_Pejabat'].iloc[0]}")

                output = BytesIO(); wb.save(output)
                return output.getvalue()

            # --- MESIN CETAK PDF (AUTO-SCALE LANDSCAPE/PORTRAIT, COMPACT ROWS) ---
            def export_pdf_rab(df_header, df_items, orientasi):
                total_seluruh = df_items["Total_Biaya"].sum()
                t_rab = df_header.get('Tahun', pd.Series(['2027'])).iloc[0]
                s_dana = df_header.get('Sumber_Dana', pd.Series(['BOPTN'])).iloc[0]
                
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
                        if "." in k and len(k.split(".")) == 2 and len(k.split(".")[0]) == 3:
                            k1, k2 = k.split(".")
                            html += f"<tr><td class='bold'>{k1}</td><td class='bold'>{indent}{u}</td><td></td><td></td><td class='bold text-right'>{format_rupiah(total_seluruh)}</td></tr>"
                            html += f"<tr><td class='bold'>{k2}</td><td class='bold'>{indent}</td><td></td><td></td><td class='bold text-right'>{format_rupiah(total_seluruh)}</td></tr>"
                        else:
                            html += f"<tr><td class='bold'>{k}</td><td class='bold'>{indent}{u}</td><td></td><td></td><td class='bold text-right'>{format_rupiah(total_seluruh)}</td></tr>"
                
                for akun, group_akun in df_items.groupby("Akun_Belanja"):
                    k_ak, u_ak = split_kode(akun)
                    html += f"<tr><td class='bold'>{k_ak}</td><td class='bold'>      {u_ak}</td><td></td><td></td><td class='bold text-right'>{format_rupiah(group_akun['Total_Biaya'].sum())}</td></tr>"
                    for _, r in group_akun.iterrows():
                        v_sat_str = get_vol_sat_combined(r['Vol_1'], r['Sat_1'], r['Vol_2'], r['Sat_2'])
                        html += f"<tr><td></td><td>        - {r['Uraian']}</td><td class='text-center'>{v_sat_str}</td><td class='text-right'>{format_rupiah(r['Harga_Satuan'])}</td><td class='text-right'>{format_rupiah(r['Total_Biaya'])}</td></tr>"
                
                html += f"""</table>
                <div class="ttd-box">
                    {tgl_str}<br>{df_header['Jabatan'].iloc[0]}<br><br><br><br><br>
                    <b><u>{df_header['Nama_Pejabat'].iloc[0]}</u></b><br>NIP. {df_header['NIP_Pejabat'].iloc[0]}
                </div>
                </body></html>"""
                return html

            st.markdown("#### 🖨️ Cetak & Unduh Dokumen RAB")
            orientasi_pdf = st.radio("Pilih Orientasi PDF:", ["Landscape", "Portrait"], horizontal=True)

            col_x1, col_x2 = st.columns([1, 4])
            with col_x1:
                st.download_button("📥 Download Excel Resmi", data=export_excel_rab(head_terpilih, detail_terpilih), file_name=f"RAB_{s_dana}_{tahun_rab}_{pilih_arsip}.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", type="primary")
                st.download_button("📑 PDF: Cetak RAB (Web)", data=export_pdf_rab(head_terpilih, detail_terpilih, orientasi_pdf).encode('utf-8'), file_name=f"Cetak_RAB_{s_dana}_{tahun_rab}_{pilih_arsip}.html", mime="text/html", help="Tekan Ctrl+P di browser lalu pilih opsi 'Fit to Page'.")
            with col_x2:
                if st.button("🗑️ Hapus Dokumen Ini"):
                    df_rab_utama = df_rab_utama[df_rab_utama["ID_RAB"] != pilih_arsip]
                    df_rab_detail = df_rab_detail[df_rab_detail["ID_RAB"] != pilih_arsip]
                    save_table(df_rab_utama, "rab_utama"); save_table(df_rab_detail, "rab_detail")
                    st.success("Terhapus!"); st.rerun()
