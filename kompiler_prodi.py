import streamlit as st
import pandas as pd
import os
import sqlite3
from io import BytesIO

# ==========================================
# 1. KONFIGURASI HALAMAN, DATABASE & FOLDER
# ==========================================
st.set_page_config(page_title="Kompiler Usulan Anggaran FIB", page_icon="🔐", layout="wide")

FILE_DB = "database_usulan_prodi.db"
FILE_CSV_LAMA = "database_usulan_prodi.csv" # Untuk auto-migrasi data lama
UPLOAD_DIR = "tor_uploads"

if not os.path.exists(UPLOAD_DIR):
    os.makedirs(UPLOAD_DIR)

# Fungsi Canggih untuk Auto-Migrasi & Load Data SQLite
def load_data():
    conn = sqlite3.connect(FILE_DB)
    
    # Mengecek apakah tabel 'usulan' sudah ada di dalam database
    cek_tabel = pd.read_sql("SELECT name FROM sqlite_master WHERE type='table' AND name='usulan'", conn)
    
    if cek_tabel.empty:
        # Jika database baru masih kosong, cek apakah ada file CSV yang lama
        if os.path.exists(FILE_CSV_LAMA):
            df = pd.read_csv(FILE_CSV_LAMA)
            # Menambal kolom baru jika data CSV lama belum punya
            if "Status" not in df.columns: df["Status"] = "Menunggu Review"
            if "Catatan_Fakultas" not in df.columns: df["Catatan_Fakultas"] = "-"
            if "File_TOR" not in df.columns: df["File_TOR"] = "-"
            
            # Pindahkan isi CSV ke dalam SQLite secara permanen
            df.to_sql("usulan", conn, if_exists="replace", index=False)
            conn.close()
            return df
        else:
            # Jika benar-benar baru pertama kali jalan
            df_kosong = pd.DataFrame(columns=[
                "Tanggal_Input", "Program_Studi", "Nama_Kegiatan", 
                "Rincian_Belanja", "Volume", "Satuan", "Harga_Satuan", 
                "Total_Usulan", "Prioritas", "Status", "Catatan_Fakultas", "File_TOR"
            ])
            df_kosong.to_sql("usulan", conn, if_exists="replace", index=False)
            conn.close()
            return df_kosong
    else:
        # Jika database sudah siap, langsung baca dari SQLite
        df = pd.read_sql("SELECT * FROM usulan", conn)
        conn.close()
        return df

# Fungsi menyimpan langsung ke SQLite
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
                else: st.error("Username/Password salah.")
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

    # --- TAB 1: DASHBOARD PRODI ---
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
        kegiatan_tanpa_tor = my_data[my_data["File_TOR"] == "-"]["Nama_Kegiatan"].unique()
        if len(kegiatan_tanpa_tor) > 0:
            insights.append(f"❌ **Lengkapi Dokumen:** Ada {len(kegiatan_tanpa_tor)} kegiatan yang belum memiliki TOR/KAK. Segera upload di menu Monitoring.")
        
        kegiatan_revisi = my_data[my_data["Status"] == "Perlu Revisi"]["Nama_Kegiatan"].unique()
        if len(kegiatan_revisi) > 0:
            insights.append(f"⚠️ **Tindak Lanjut Revisi:** Fakultas meminta perbaikan pada {len(kegiatan_revisi)} kegiatan. Cek catatan Fakultas.")
            
        insights.append(f"ℹ️ **Saran SBM 2026:** Pastikan seluruh Honorarium dan Uang Saku mengacu pada standar PMK Standar Biaya Masukan 2026 wilayah Kalimantan Timur.")

        if not insights:
            st.success("✅ Seluruh usulan Anda sudah lengkap dan sedang dalam proses review.")
        else:
            for item in insights: st.write(item)

        st.markdown("---")
        st.markdown("#### Daftar Kegiatan & Anggaran Terajukan")
        if not my_data.empty:
            rekap_keg = my_data.groupby(["Nama_Kegiatan", "Status"])["Total_Usulan"].sum().reset_index()
            rekap_keg.columns = ["Nama Kegiatan", "Status Saat Ini", "Total Anggaran (Rp)"]
            st.table(rekap_keg.style.format({"Total Anggaran (Rp)": "{:,.0f}"}))
        else:
            st.info("Belum ada data kegiatan.")

    # --- TAB 2: INPUT BARU ---
    with tab_baru:
        with st.form("form_input", clear_on_submit=True):
            st.markdown("### 1️⃣ Informasi Utama")
            c1, c2 = st.columns([2, 1])
            nama_keg = c1.text_input("Nama Kegiatan Utama")
            prio = c2.selectbox("Prioritas", ["Tinggi", "Sedang", "Rendah"])
            st.markdown("### 📄 Dokumen Pendukung")
            file_tor = st.file_uploader("Upload TOR/KAK (Opsional, PDF, Maks. 5MB)", type=["pdf"])
            st.markdown("### 2️⃣ Rincian RAB")
            template = pd.DataFrame([{"Rincian Belanja": "", "Volume": 0, "Satuan": "Orang", "Harga Satuan": 0}])
            edited = st.data_editor(template, num_rows="dynamic", use_container_width=True, hide_index=True, column_config={
                "Satuan": st.column_config.SelectboxColumn("Satuan", options=["Unit", "Orang", "Hari", "Bulan", "Tahun", "Jam", "Paket", "Stel", "Kegiatan"])
            })
            if st.form_submit_button("Kirim Usulan"):
                valid = edited[edited["Rincian Belanja"].str.strip() != ""]
                if not nama_keg.strip() or valid.empty: st.error("Lengkapi data!")
                else:
                    path_tor = "-"
                    if file_tor is not None and file_tor.size <= 5*1024*1024:
                        safe_name = "".join([c for c in nama_keg if c.isalnum()]).rstrip()
                        path_tor = os.path.join(UPLOAD_DIR, f"TOR_{st.session_state['username']}_{safe_name}.pdf")
                        with open(path_tor, "wb") as f: f.write(file_tor.getbuffer())
                    
                    new_entries = []
                    tgl = pd.Timestamp.now().strftime("%Y-%m-%d %H:%M")
                    for _, r in valid.iterrows():
                        new_entries.append({
                            "Tanggal_Input": tgl, "Program_Studi": st.session_state["nama_user"], "Nama_Kegiatan": nama_keg,
                            "Rincian_Belanja": r["Rincian Belanja"], "Volume": r["Volume"], "Satuan": r["Satuan"],
                            "Harga_Satuan": r["Harga Satuan"], "Total_Usulan": r["Volume"] * r["Harga Satuan"],
                            "Prioritas": prio, "Status": "Menunggu Review", "Catatan_Fakultas": "-", "File_TOR": path_tor
                        })
                    df_usulan = pd.concat([df_usulan, pd.DataFrame(new_entries)], ignore_index=True)
                    save_data(df_usulan)
                    st.success("Usulan terkirim!"); st.rerun()

    # --- TAB 3: MONITORING & REVISI ---
    with tab_riwayat:
        st.markdown("### 📜 Monitoring & Update Dokumen")
        my_data = df_usulan[df_usulan["Program_Studi"] == st.session_state["nama_user"]]
        if my_data.empty: st.info("Belum ada riwayat usulan.")
        else:
            sel_keg = st.selectbox("Pilih Kegiatan:", my_data["Nama_Kegiatan"].unique())
            df_curr = my_data[my_data["Nama_Kegiatan"] == sel_keg].copy()
            status_keg = df_curr["Status"].iloc[0]
            catatan_keg = df_curr["Catatan_Fakultas"].iloc[0]
            
            st.info(f"**Status:** {status_keg} | **Catatan:** {catatan_keg}")
            
            if status_keg == "Perlu Revisi":
                st.warning("Silakan perbaiki rincian biaya di bawah ini.")
                df_to_edit = df_curr[["Rincian_Belanja", "Volume", "Satuan", "Harga_Satuan"]]
                rev_ed = st.data_editor(df_to_edit, num_rows="dynamic", use_container_width=True, hide_index=True, column_config={
                    "Satuan": st.column_config.SelectboxColumn("Satuan", options=["Unit", "Orang", "Hari", "Bulan", "Tahun", "Jam", "Paket", "Stel", "Kegiatan"])
                })
                if st.button("Kirim Ulang Revisi"):
                    df_usulan = df_usulan[~((df_usulan["Program_Studi"]==st.session_state["nama_user"]) & (df_usulan["Nama_Kegiatan"]==sel_keg))]
                    
                    rev_entries = []
                    tgl_rev = pd.Timestamp.now().strftime("%Y-%m-%d %H:%M")
                    for _, r in rev_ed.iterrows():
                        rev_entries.append({
                            "Tanggal_Input": tgl_rev, "Program_Studi": st.session_state["nama_user"], "Nama_Kegiatan": sel_keg,
                            "Rincian_Belanja": r["Rincian_Belanja"], "Volume": r["Volume"], "Satuan": r["Satuan"],
                            "Harga_Satuan": r["Harga_Satuan"], "Total_Usulan": r["Volume"] * r["Harga_Satuan"],
                            "Prioritas": df_curr["Prioritas"].iloc[0], "Status": "Menunggu Review", "Catatan_Fakultas": f"Revisi: {catatan_keg}",
                            "File_TOR": df_curr["File_TOR"].iloc[0]
                        })
                    df_usulan = pd.concat([df_usulan, pd.DataFrame(rev_entries)], ignore_index=True)
                    save_data(df_usulan)
                    st.success("Berhasil diupdate!"); st.rerun()
            else:
                df_view = df_curr[["Rincian_Belanja", "Volume", "Satuan", "Harga_Satuan", "Total_Usulan"]]
                st.table(df_view.style.format({"Harga_Satuan": "{:,.0f}", "Total_Usulan": "{:,.0f}"}))
            
            with st.expander("📄 Update / Susulan Dokumen TOR"):
                new_tor = st.file_uploader("Upload PDF (Maks 5MB)", type=["pdf"], key=f"up_{sel_keg}")
                if st.button("Simpan Dokumen", key=f"btn_{sel_keg}"):
                    if new_tor:
                        safe_name = "".join([c for c in sel_keg if c.isalnum()]).rstrip()
                        path = os.path.join(UPLOAD_DIR, f"TOR_UPD_{st.session_state['username']}_{safe_name}.pdf")
                        with open(path, "wb") as f: f.write(new_tor.getbuffer())
                        df_usulan.loc[(df_usulan["Program_Studi"]==st.session_state["nama_user"]) & (df_usulan["Nama_Kegiatan"]==sel_keg), "File_TOR"] = path
                        save_data(df_usulan); st.success("TOR Terupdate!"); st.rerun()

# ==========================================
# 5B. TAMPILAN ADMIN
# ==========================================
elif st.session_state["role"] == "admin":
    st.title("📊 Dashboard Monitoring & Review")
    st.info("Gunakan tab di bawah untuk meninjau usulan dari setiap Program Studi.")
    
    if df_usulan.empty: 
        st.warning("Data kosong.")
    else:
        tab_rev, tab_hapus, tab_ins = st.tabs(["📋 Review & Analisis", "🗑️ Manajemen Data", "🤖 Insight Fakultas"])
        
        # --- TAB 1: REVIEW ---
        with tab_rev:
            prodi_sel = st.selectbox("Pilih Prodi:", sorted(df_usulan["Program_Studi"].unique()))
            df_p = df_usulan[df_usulan["Program_Studi"] == prodi_sel]
            for k in df_p["Nama_Kegiatan"].unique():
                df_k = df_p[df_p["Nama_Kegiatan"] == k].copy()
                with st.expander(f"{k.upper()} | Rp {df_k['Total_Usulan'].sum():,.0f} | Status: {df_k['Status'].iloc[0]}"):
                    path = df_k["File_TOR"].iloc[0]
                    if path != "-" and os.path.exists(path):
                        with open(path, "rb") as f:
                            st.download_button("📥 Download TOR", f, file_name=os.path.basename(path), key=f"dl_{k}")
                    else: st.caption("TOR belum diunggah.")
                    
                    c1, c2 = st.columns([1, 2])
                    n_s = c1.selectbox("Status:", ["Menunggu Review", "Disetujui", "Perlu Revisi", "Ditolak"], index=["Menunggu Review", "Disetujui", "Perlu Revisi", "Ditolak"].index(df_k["Status"].iloc[0]), key=f"s_{k}")
                    n_n = c2.text_area("Catatan:", value=df_k["Catatan_Fakultas"].iloc[0], key=f"n_{k}")
                    if st.button("Simpan Hasil Review", key=f"b_{k}"):
                        df_usulan.loc[(df_usulan["Program_Studi"]==prodi_sel) & (df_usulan["Nama_Kegiatan"]==k), ["Status", "Catatan_Fakultas"]] = [n_s, n_n]
                        save_data(df_usulan); st.success("Tersimpan!"); st.rerun()
                    st.dataframe(df_k[["Rincian_Belanja", "Volume", "Satuan", "Harga_Satuan", "Total_Usulan"]], hide_index=True)

        # --- TAB 2: MANAJEMEN DATA ---
        with tab_hapus:
            st.subheader("🗑️ Hapus Data Rincian")
            opsi_hapus = {idx: f"[{row['Program_Studi']}] {row['Nama_Kegiatan']} ➡️ {row['Rincian_Belanja']}" for idx, row in df_usulan.iterrows()}
            sel_h = st.selectbox("Pilih Rincian:", options=list(opsi_hapus.keys()), format_func=lambda x: opsi_hapus[x])
            if st.button("🚨 Hapus Permanen", type="primary"):
                df_usulan = df_usulan.drop(index=sel_h).reset_index(drop=True)
                save_data(df_usulan); st.success("Terhapus!"); st.rerun()

        # --- TAB 3: INSIGHT ADMIN ---
        with tab_ins:
            st.subheader("🤖 Analisis & Komparasi Otomatis")
            tot_anggaran = df_usulan['Total_Usulan'].sum()
            
            if tot_anggaran > 0:
                prodi_max = df_usulan.groupby('Program_Studi')['Total_Usulan'].sum().idxmax()
                val_max = df_usulan.groupby('Program_Studi')['Total_Usulan'].sum().max()
                
                st.info(f"""
                💡 **Ringkasan Pimpinan:**
                Total usulan masuk mencapai **Rp {tot_anggaran:,.0f}**.
                
                * 📊 **Prodi Terbesar:** **{prodi_max}** mendominasi usulan sebesar **Rp {val_max:,.0f}**.
                * ⏳ **Progres Review:** Terdapat {df_usulan['Status'].value_counts().get('Menunggu Review', 0)} rincian yang masih Menunggu Review, dan {df_usulan['Status'].value_counts().get('Disetujui', 0)} rincian telah Disetujui.
                """.replace(',', '.'))
                
                st.markdown("### 📊 Visualisasi Perbandingan Prodi")
                rekap_prodi = df_usulan.groupby("Program_Studi")["Total_Usulan"].sum().reset_index()
                st.bar_chart(rekap_prodi.set_index("Program_Studi")["Total_Usulan"])
            else:
                st.info("Belum ada data nilai anggaran untuk dianalisis.")
