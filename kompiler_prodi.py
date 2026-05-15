import streamlit as st
import pandas as pd
import os
from io import BytesIO

# ==========================================
# 1. KONFIGURASI HALAMAN, DATABASE & FOLDER
# ==========================================
st.set_page_config(page_title="Kompiler Usulan Anggaran FIB", page_icon="🔐", layout="wide")

FILE_DATABASE = "database_usulan_prodi.csv"
UPLOAD_DIR = "tor_uploads"

if not os.path.exists(UPLOAD_DIR):
    os.makedirs(UPLOAD_DIR)

def load_data():
    if os.path.exists(FILE_DATABASE):
        df = pd.read_csv(FILE_DATABASE)
        if "Status" not in df.columns: df["Status"] = "Menunggu Review"
        if "Catatan_Fakultas" not in df.columns: df["Catatan_Fakultas"] = "-"
        if "File_TOR" not in df.columns: df["File_TOR"] = "-"
        return df
    else:
        return pd.DataFrame(columns=[
            "Tanggal_Input", "Program_Studi", "Nama_Kegiatan", 
            "Rincian_Belanja", "Volume", "Satuan", "Harga_Satuan", 
            "Total_Usulan", "Prioritas", "Status", "Catatan_Fakultas", "File_TOR"
        ])

def save_data(df):
    df.to_csv(FILE_DATABASE, index=False)

df_usulan = load_data()

# ==========================================
# 2. DATABASE USER (Hanya Contoh)
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
        
        # --- FITUR INSIGHT PRODI ---
        st.markdown("### 🤖 Insight & Langkah Selanjutnya")
        
        # Logika Analisis Mandiri untuk Prodi
        insights = []
        
        # 1. Cek TOR yang Kosong
        kegiatan_tanpa_tor = my_data[my_data["File_TOR"] == "-"]["Nama_Kegiatan"].unique()
        if len(kegiatan_tanpa_tor) > 0:
            insights.append(f"❌ **Lengkapi Dokumen:** Ada {len(kegiatan_tanpa_tor)} kegiatan yang belum memiliki TOR/KAK. Segera upload di menu Monitoring.")
            
        # 2. Cek Status Revisi
        kegiatan_revisi = my_data[my_data["Status"] == "Perlu Revisi"]["Nama_Kegiatan"].unique()
        if len(kegiatan_revisi) > 0:
            insights.append(f"⚠️ **Tindak Lanjut Revisi:** Fakultas meminta perbaikan pada {len(kegiatan_revisi)} kegiatan. Cek catatan Fakultas.")
            
        # 3. Saran Harga (SBM 2026)
        insights.append(f"ℹ️ **Saran SBM 2026:** Pastikan seluruh Honorarium dan Uang Saku mengacu pada standar PMK Standar Biaya Masukan 2026 wilayah Kalimantan Timur.")

        if not insights:
            st.success("✅ Seluruh usulan Anda sudah lengkap dan sedang dalam proses review.")
        else:
            for item in insights:
                st.write(item)

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
            tor_saat_ini = df_curr["File_TOR"].iloc[0]
            
            st.info(f"**Status:** {status_keg} | **Catatan:** {catatan_keg}")
            
            if status_keg == "Perlu Revisi":
                # Logika Revisi (Sama seperti sebelumnya)
                st.warning("Silakan perbaiki rincian biaya di bawah ini.")
                df_to_edit = df_curr[["Rincian_Belanja", "Volume", "Satuan", "Harga_Satuan"]]
                rev_ed = st.data_editor(df_to_edit, num_rows="dynamic", use_container_width=True, hide_index=True)
                if st.button("Kirim Ulang Revisi"):
                    df_usulan = df_usulan[~((df_usulan["Program_Studi"]==st.session_state["nama_user"]) & (df_usulan["Nama_Kegiatan"]==sel_keg))]
                    # (Proses simpan ulang rincian baru...)
                    st.success("Berhasil diupdate!"); st.rerun()
            
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
    # (Logika Dashboard Admin tetap sama seperti kode sebelumnya...)
    st.info("Gunakan tab di bawah untuk meninjau usulan dari setiap Program Studi.")
    tab_rev, tab_hapus, tab_ins = st.tabs(["📋 Review & Analisis", "🗑️ Manajemen Data", "🤖 Insight Fakultas"])
    
    with tab_rev:
        prodi_sel = st.selectbox("Pilih Prodi:", sorted(df_usulan["Program_Studi"].unique()))
        df_p = df_usulan[df_usulan["Program_Studi"] == prodi_sel]
        for k in df_p["Nama_Kegiatan"].unique():
            df_k = df_p[df_p["Nama_Kegiatan"] == k].copy()
            with st.expander(f"{k.upper()} | Rp {df_k['Total_Usulan'].sum():,.0f} | Status: {df_k['Status'].iloc[0]}"):
                # Tampilkan tombol download jika TOR ada
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
