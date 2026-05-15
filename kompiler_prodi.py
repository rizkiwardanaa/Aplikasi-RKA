import streamlit as st
import pandas as pd
import os
import sqlite3
from io import BytesIO

# ==========================================
# 1. KONFIGURASI HALAMAN & LOKASI DATABASE
# ==========================================
st.set_page_config(page_title="Kompiler Usulan Anggaran FIB", page_icon="📝", layout="wide")

# Path folder sesuai permintaan
BASE_DIR = r"C:\Users\rizki\OneDrive\Documents\Project Python\Dashboard Anggaran"
FILE_DB = os.path.join(BASE_DIR, "database_usulan_prodi.db")
FILE_CSV_LAMA = os.path.join(BASE_DIR, "database_usulan_prodi.csv") # <-- INI PERBAIKANNYA
UPLOAD_DIR = os.path.join(BASE_DIR, "tor_uploads")

# Pastikan folder database dan upload tersedia
if not os.path.exists(BASE_DIR):
    os.makedirs(BASE_DIR)
if not os.path.exists(UPLOAD_DIR):
    os.makedirs(UPLOAD_DIR)

def load_data():
    conn = sqlite3.connect(FILE_DB)
    cek_tabel = pd.read_sql("SELECT name FROM sqlite_master WHERE type='table' AND name='usulan'", conn)
    
    if cek_tabel.empty:
        if os.path.exists(FILE_CSV_LAMA):
            df = pd.read_csv(FILE_CSV_LAMA)
            if "Status" not in df.columns: df["Status"] = "Menunggu Review"
            if "Catatan_Fakultas" not in df.columns: df["Catatan_Fakultas"] = "-"
            if "File_TOR" not in df.columns: df["File_TOR"] = "-"
            df.to_sql("usulan", conn, if_exists="replace", index=False)
            conn.close()
            return df
        else:
            df_kosong = pd.DataFrame(columns=[
                "Tanggal_Input", "Program_Studi", "Nama_Kegiatan", 
                "Rincian_Belanja", "Volume", "Satuan", "Harga_Satuan", 
                "Total_Usulan", "Prioritas", "Status", "Catatan_Fakultas", "File_TOR"
            ])
            df_kosong.to_sql("usulan", conn, if_exists="replace", index=False)
            conn.close()
            return df_kosong
    else:
        df = pd.read_sql("SELECT * FROM usulan", conn)
        conn.close()
        return df

def save_data(df):
    conn = sqlite3.connect(FILE_DB)
    df.to_sql("usulan", conn, if_exists="replace", index=False)
    conn.close()

df_usulan = load_data()

# ==========================================
# 2. DATABASE USER
# ==========================================
USER_CREDENTIALS = {
    "admin": {"password": "adminfib", "role": "admin", "nama_tampil": "Fakultas Ilmu Budaya (Admin)"},
    "sasindo": {"password": "123", "role": "prodi", "nama_tampil": "Sastra Indonesia"},
    "sasing": {"password": "123", "role": "prodi", "nama_tampil": "Sastra Inggris"},
    "etno": {"password": "123", "role": "prodi", "nama_tampil": "Etnomusikologi"},
    "tari": {"password": "123", "role": "prodi", "nama_tampil": "Tari"},
    "kajian": {"password": "123", "role": "prodi", "nama_tampil": "Kajian Budaya (S2)"}
}

if "logged_in" not in st.session_state:
    st.session_state.update({"logged_in": False, "role": None, "nama_user": None, "username": None})

# ==========================================
# 3. HALAMAN LOGIN
# ==========================================
if not st.session_state["logged_in"]:
    _, col_tengah, _ = st.columns([1, 2, 1])
    with col_tengah:
        st.title("🔐 Login Sistem RKA")
        st.subheader("Fakultas Ilmu Budaya - Unmul")
        with st.form("form_login"):
            u, p = st.text_input("Username"), st.text_input("Password", type="password")
            if st.form_submit_button("Masuk", type="primary"):
                if u in USER_CREDENTIALS and USER_CREDENTIALS[u]["password"] == p:
                    st.session_state.update({"logged_in": True, "role": USER_CREDENTIALS[u]["role"], "nama_user": USER_CREDENTIALS[u]["nama_tampil"], "username": u})
                    st.rerun()
                else: st.error("Username atau Password salah.")
    st.stop()

# ==========================================
# 4. SIDEBAR
# ==========================================
with st.sidebar:
    st.header("Sistem Perencanaan")
    st.markdown(f"👤 **{st.session_state['nama_user']}**")
    if st.button("🚪 Logout", type="primary"):
        st.session_state.update({"logged_in": False, "role": None, "nama_user": None, "username": None})
        st.rerun()

# ==========================================
# 5A. TAMPILAN PRODI
# ==========================================
if st.session_state["role"] == "prodi":
    st.title(f"📍 Panel Usulan: {st.session_state['nama_user']}")
    tab_dash, tab_baru, tab_riwayat = st.tabs(["📊 Dashboard Prodi", "📤 Buat Usulan Baru", "📜 Monitoring & Revisi"])

    with tab_dash:
        my_data = df_usulan[df_usulan["Program_Studi"] == st.session_state["nama_user"]]
        col1, col2, col3 = st.columns(3)
        total_pengajuan = my_data["Total_Usulan"].sum()
        col1.metric("Total Anggaran Diajukan", f"Rp {total_pengajuan:,.0f}".replace(',', '.'))
        col2.metric("Jumlah Kegiatan", my_data["Nama_Kegiatan"].nunique())
        col3.metric("Usulan Disetujui", len(my_data[my_data["Status"] == "Disetujui"]["Nama_Kegiatan"].unique()))
        
        st.markdown("---")
        st.markdown("### 🤖 Insight & Langkah Selanjutnya")
        insights = []
        keg_tanpa_tor = my_data[my_data["File_TOR"] == "-"]["Nama_Kegiatan"].unique()
        if len(keg_tanpa_tor) > 0:
            insights.append(f"❌ **Lengkapi Dokumen:** Ada {len(keg_tanpa_tor)} kegiatan belum memiliki TOR. Upload di menu Monitoring.")
        keg_rev = my_data[my_data["Status"] == "Perlu Revisi"]["Nama_Kegiatan"].unique()
        if len(keg_rev) > 0:
            insights.append(f"⚠️ **Tindak Lanjut Revisi:** Ada {len(keg_rev)} kegiatan perlu perbaikan.")
        insights.append("ℹ️ **Saran SBM 2026:** Gunakan tarif Kalimantan Timur sesuai PMK Standar Biaya Masukan 2026.")
        for item in insights: st.write(item)

    with tab_baru:
        with st.form("form_input", clear_on_submit=True):
            nama_keg = st.text_input("Nama Kegiatan Utama")
            file_tor = st.file_uploader("Upload TOR (PDF, Maks 5MB)", type=["pdf"])
            template = pd.DataFrame([{"Rincian Belanja": "", "Volume": 0, "Satuan": "Orang", "Harga Satuan": 0}])
            edited = st.data_editor(template, num_rows="dynamic", use_container_width=True, hide_index=True, column_config={
                "Satuan": st.column_config.SelectboxColumn("Satuan", options=["Unit", "Orang", "Hari", "Bulan", "Tahun", "Jam", "Paket", "Stel", "Kegiatan"])
            })
            if st.form_submit_button("Kirim Usulan"):
                valid = edited[edited["Rincian Belanja"].str.strip() != ""]
                if nama_keg and not valid.empty:
                    path_tor = "-"
                    if file_tor:
                        path_tor = os.path.join(UPLOAD_DIR, f"TOR_{st.session_state['username']}_{nama_keg[:10]}.pdf")
                        with open(path_tor, "wb") as f: f.write(file_tor.getbuffer())
                    new_data = pd.DataFrame([{
                        "Tanggal_Input": pd.Timestamp.now().strftime("%Y-%m-%d %H:%M"), 
                        "Program_Studi": st.session_state["nama_user"], "Nama_Kegiatan": nama_keg,
                        "Rincian_Belanja": r["Rincian Belanja"], "Volume": r["Volume"], "Satuan": r["Satuan"],
                        "Harga_Satuan": r["Harga Satuan"], "Total_Usulan": r["Volume"] * r["Harga_Satuan"],
                        "Prioritas": "Sedang", "Status": "Menunggu Review", "Catatan_Fakultas": "-", "File_TOR": path_tor
                    } for _, r in valid.iterrows()])
                    df_usulan = pd.concat([df_usulan, new_data], ignore_index=True)
                    save_data(df_usulan); st.success("Terkirim!"); st.rerun()

    with tab_riwayat:
        my_data = df_usulan[df_usulan["Program_Studi"] == st.session_state["nama_user"]]
        if not my_data.empty:
            sel_keg = st.selectbox("Pilih Kegiatan:", my_data["Nama_Kegiatan"].unique())
            df_curr = my_data[my_data["Nama_Kegiatan"] == sel_keg]
            st.info(f"Status: {df_curr['Status'].iloc[0]} | Catatan: {df_curr['Catatan_Fakultas'].iloc[0]}")
            st.table(df_curr[["Rincian_Belanja", "Volume", "Satuan", "Harga_Satuan", "Total_Usulan"]].style.format({"Total_Usulan": "{:,.0f}"}))

# ==========================================
# 5B. TAMPILAN ADMIN (FAKULTAS)
# ==========================================
elif st.session_state["role"] == "admin":
    st.title("📊 Dashboard Monitoring & Review")
    
    if df_usulan.empty: 
        st.warning("Data kosong.")
    else:
        tab_rev, tab_hapus, tab_ins = st.tabs(["📋 Review & Analisis", "🗑️ Manajemen Data", "🤖 Insight Fakultas"])
        
        with tab_rev:
            # BAGIAN 1: REKAPITULASI SELURUH PRODI
            st.subheader("🏙️ Rekapitulasi Anggaran Per Prodi")
            rekap_semua = df_usulan.groupby("Program_Studi")["Total_Usulan"].sum().reset_index()
            rekap_semua.columns = ["Program Studi", "Total Usulan (Rp)"]
            st.table(rekap_semua.style.format({"Total Usulan (Rp)": "{:,.0f}"}))

            st.markdown("---")
            
            # BAGIAN 2: DRILL-DOWN DETAIL PER PRODI
            st.subheader("🔍 Detail Kegiatan Per Prodi")
            prodi_sel = st.selectbox("Pilih Prodi untuk melihat daftar kegiatan:", sorted(df_usulan["Program_Studi"].unique()))
            
            df_p = df_usulan[df_usulan["Program_Studi"] == prodi_sel]
            
            # Rekap Kegiatan dalam Prodi terpilih
            rekap_keg_prodi = df_p.groupby("Nama_Kegiatan")["Total_Usulan"].sum().reset_index()
            st.write(f"Berikut adalah daftar kegiatan dari **{prodi_sel}**:")
            
            for k in rekap_keg_prodi["Nama_Kegiatan"]:
                df_k = df_p[df_p["Nama_Kegiatan"] == k].copy()
                total_keg_val = df_k["Total_Usulan"].sum()
                
                with st.expander(f"📌 {k.upper()} | Total Usulan: Rp {total_keg_val:,.0f} | Status: {df_k['Status'].iloc[0]}".replace(',', '.')):
                    path = df_k["File_TOR"].iloc[0]
                    if path != "-" and os.path.exists(path):
                        with open(path, "rb") as f:
                            st.download_button("📥 Download TOR", f, file_name=os.path.basename(path), key=f"dl_{prodi_sel}_{k}")
                    
                    c1, c2 = st.columns([1, 2])
                    n_s = c1.selectbox("Update Status:", ["Menunggu Review", "Disetujui", "Perlu Revisi", "Ditolak"], 
                                     index=["Menunggu Review", "Disetujui", "Perlu Revisi", "Ditolak"].index(df_k["Status"].iloc[0]), key=f"s_{prodi_sel}_{k}")
                    n_n = c2.text_area("Catatan Fakultas:", value=df_k["Catatan_Fakultas"].iloc[0], key=f"n_{prodi_sel}_{k}")
                    
                    if st.button("Simpan Hasil Review", key=f"b_{prodi_sel}_{k}"):
                        df_usulan.loc[(df_usulan["Program_Studi"]==prodi_sel) & (df_usulan["Nama_Kegiatan"]==k), ["Status", "Catatan_Fakultas"]] = [n_s, n_n]
                        save_data(df_usulan); st.success(f"Status '{k}' diperbarui!"); st.rerun()
                    
                    st.dataframe(df_k[["Rincian_Belanja", "Volume", "Satuan", "Harga_Satuan", "Total_Usulan"]], hide_index=True)

            # Ekspor Data
            st.markdown("---")
            st.download_button("📥 Download Excel Rekapitulasi", data=df_usulan.to_csv(index=False).encode('utf-8'), file_name="Rekap_FIB_2026.csv", mime="text/csv")

        with tab_hapus:
            st.subheader("🗑️ Hapus Data Rincian")
            opsi_hapus = {idx: f"[{row['Program_Studi']}] {row['Nama_Kegiatan']} - {row['Rincian_Belanja']}" for idx, row in df_usulan.iterrows()}
            sel_h = st.selectbox("Pilih data rincian belanja:", options=list(opsi_hapus.keys()), format_func=lambda x: opsi_hapus[x])
            if st.button("🚨 Hapus Permanen", type="primary"):
                df_usulan = df_usulan.drop(index=sel_h).reset_index(drop=True)
                save_data(df_usulan); st.success("Data berhasil dihapus!"); st.rerun()

        with tab_ins:
            st.subheader("🤖 Analisis & Insight Pintar")
            tot = df_usulan['Total_Usulan'].sum()
            
            if tot > 0:
                prodi_max = df_usulan.groupby('Program_Studi')['Total_Usulan'].sum().idxmax()
                val_max = df_usulan.groupby('Program_Studi')['Total_Usulan'].sum().max()
                keg_mahal = df_usulan.groupby('Nama_Kegiatan')['Total_Usulan'].sum().idxmax()
                val_keg_mahal = df_usulan.groupby('Nama_Kegiatan')['Total_Usulan'].sum().max()

                # SMART INSIGHT (TEXT BASED)
                st.info(f"""
                💡 **Ringkasan Eksekutif AI:**
                Total anggaran yang diajukan saat ini adalah **Rp {tot:,.0f}**.
                
                * 📊 **Prodi Terbesar:** Saat ini **{prodi_max}** merupakan unit pengusul tertinggi dengan nilai **Rp {val_max:,.0f}**.
                * 💎 **Kegiatan Prioritas Tinggi:** Kegiatan **"{keg_mahal}"** adalah pengajuan tunggal terbesar senilai **Rp {val_keg_mahal:,.0f}**.
                * ⏳ **Review:** Masih ada {df_usulan['Status'].value_counts().get('Menunggu Review', 0)} rincian yang belum diproses.
                """.replace(',', '.'))
                
                # GRAFIK VISUAL
                st.markdown("### 📊 Perbandingan Anggaran antar Prodi")
                rekap_ins = df_usulan.groupby("Program_Studi")["Total_Usulan"].sum().reset_index()
                st.bar_chart(rekap_ins.set_index("Program_Studi")["Total_Usulan"])
            else:
                st.info("Data belum tersedia untuk analisis.")
