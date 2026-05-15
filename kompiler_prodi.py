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

# Membuat folder otomatis untuk menyimpan file PDF jika belum ada
if not os.path.exists(UPLOAD_DIR):
    os.makedirs(UPLOAD_DIR)

def load_data():
    if os.path.exists(FILE_DATABASE):
        df = pd.read_csv(FILE_DATABASE)
        # Menambahkan kolom baru secara otomatis untuk database lama
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
# 2. DATABASE USER (HARDCODED)
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
    tab_baru, tab_riwayat = st.tabs(["📤 Buat Usulan Baru", "📜 Monitoring & Revisi"])

    # --- TAB: INPUT BARU ---
    with tab_baru:
        with st.form("form_input", clear_on_submit=True):
            st.markdown("### 1️⃣ Informasi Utama")
            c1, c2 = st.columns([2, 1])
            nama_keg = c1.text_input("Nama Kegiatan Utama")
            prio = c2.selectbox("Prioritas", ["Tinggi", "Sedang", "Rendah"])
            
            # --- FITUR UPLOAD TOR ---
            st.markdown("### 📄 Dokumen Pendukung")
            file_tor = st.file_uploader("Upload Dokumen TOR/KAK (Opsional, PDF, Maks. 5MB)", type=["pdf"])
            
            st.markdown("### 2️⃣ Rincian RAB")
            template = pd.DataFrame([{"Rincian Belanja": "", "Volume": 0, "Satuan": "Orang", "Harga Satuan": 0}])
            edited = st.data_editor(template, num_rows="dynamic", use_container_width=True, hide_index=True, column_config={
                "Satuan": st.column_config.SelectboxColumn("Satuan", options=["Unit", "Orang", "Hari", "Bulan", "Tahun", "Jam", "Paket", "Stel", "Kegiatan"])
            })
            
            if st.form_submit_button("Kirim Usulan"):
                valid = edited[edited["Rincian Belanja"].str.strip() != ""]
                if not nama_keg.strip() or valid.empty: 
                    st.error("Nama Kegiatan dan minimal 1 Rincian Belanja wajib diisi!")
                else:
                    path_tor = "-"
                    is_valid = True
                    
                    # Logika Penyimpanan File TOR
                    if file_tor is not None:
                        if file_tor.size > 5 * 1024 * 1024:
                            st.error("Gagal! Ukuran file TOR melebihi 5MB.")
                            is_valid = False
                        else:
                            # Membersihkan nama file agar aman disimpan di Windows
                            safe_keg_name = "".join([c for c in nama_keg if c.isalpha() or c.isdigit()]).rstrip()
                            file_name = f"TOR_{st.session_state['username']}_{safe_keg_name}.pdf"
                            path_tor = os.path.join(UPLOAD_DIR, file_name)
                            with open(path_tor, "wb") as f:
                                f.write(file_tor.getbuffer())

                    if is_valid:
                        new_entries = []
                        tgl = pd.Timestamp.now().strftime("%Y-%m-%d %H:%M")
                        for _, r in valid.iterrows():
                            new_entries.append({
                                "Tanggal_Input": tgl, "Program_Studi": st.session_state["nama_user"], "Nama_Kegiatan": nama_keg,
                                "Rincian_Belanja": r["Rincian Belanja"], "Volume": r["Volume"], "Satuan": r["Satuan"],
                                "Harga_Satuan": r["Harga Satuan"], "Total_Usulan": r["Volume"] * r["Harga Satuan"],
                                "Prioritas": prio, "Status": "Menunggu Review", "Catatan_Fakultas": "-",
                                "File_TOR": path_tor
                            })
                        df_usulan = pd.concat([df_usulan, pd.DataFrame(new_entries)], ignore_index=True)
                        save_data(df_usulan)
                        st.success("Usulan dan TOR berhasil terkirim!"); st.rerun()

    # --- TAB: MONITORING & REVISI ---
    with tab_riwayat:
        st.markdown("### 📜 Daftar Usulan Anda")
        my_data = df_usulan[df_usulan["Program_Studi"] == st.session_state["nama_user"]]
        
        if my_data.empty: st.info("Belum ada riwayat usulan.")
        else:
            my_kegiatan = my_data["Nama_Kegiatan"].unique()
            sel_keg = st.selectbox("Pilih Kegiatan untuk melihat detail/revisi:", my_kegiatan)
            
            df_curr = my_data[my_data["Nama_Kegiatan"] == sel_keg].copy()
            status_keg = df_curr["Status"].iloc[0]
            catatan_keg = df_curr["Catatan_Fakultas"].iloc[0]
            tor_saat_ini = df_curr["File_TOR"].iloc[0]
            
            col_s1, col_s2 = st.columns(2)
            col_s1.info(f"**Status Saat Ini:** {status_keg}")
            col_s2.warning(f"**Catatan Fakultas:** {catatan_keg}")

            st.markdown("---")
            if status_keg == "Perlu Revisi":
                st.warning("⚠️ **Mode Revisi Aktif:** Perbaiki rincian atau upload ulang TOR jika diminta.")
                
                # Uploader opsional untuk menimpa TOR lama saat revisi
                file_tor_revisi = st.file_uploader("📄 Upload TOR Pengganti (Opsional, PDF, Maks. 5MB)", type=["pdf"], key="tor_rev")
                if tor_saat_ini != "-":
                    st.caption("📝 *Anda sudah memiliki TOR untuk kegiatan ini. Abaikan kotak di atas jika TOR tidak perlu diubah.*")

                df_to_edit = df_curr[["Rincian_Belanja", "Volume", "Satuan", "Harga_Satuan"]]
                revisi_editor = st.data_editor(df_to_edit, num_rows="dynamic", use_container_width=True, hide_index=True, key="rev_ed", column_config={
                    "Satuan": st.column_config.SelectboxColumn("Satuan", options=["Unit", "Orang", "Hari", "Bulan", "Tahun", "Jam", "Paket", "Stel", "Kegiatan"])
                })
                
                if st.button("🚀 Kirim Ulang Perbaikan"):
                    path_tor_baru = tor_saat_ini # Default gunakan TOR lama
                    is_valid_rev = True
                    
                    if file_tor_revisi is not None:
                        if file_tor_revisi.size > 5 * 1024 * 1024:
                            st.error("Gagal! Ukuran file TOR pengganti melebihi 5MB.")
                            is_valid_rev = False
                        else:
                            safe_keg_name = "".join([c for c in sel_keg if c.isalpha() or c.isdigit()]).rstrip()
                            file_name = f"TOR_REV_{st.session_state['username']}_{safe_keg_name}.pdf"
                            path_tor_baru = os.path.join(UPLOAD_DIR, file_name)
                            with open(path_tor_baru, "wb") as f:
                                f.write(file_tor_revisi.getbuffer())

                    if is_valid_rev:
                        # Hapus data lama & Simpan data baru
                        df_usulan = df_usulan[~((df_usulan["Program_Studi"] == st.session_state["nama_user"]) & (df_usulan["Nama_Kegiatan"] == sel_keg))]
                        
                        rev_entries = []
                        tgl_rev = pd.Timestamp.now().strftime("%Y-%m-%d %H:%M")
                        for _, r in revisi_editor.iterrows():
                            rev_entries.append({
                                "Tanggal_Input": tgl_rev, "Program_Studi": st.session_state["nama_user"], "Nama_Kegiatan": sel_keg,
                                "Rincian_Belanja": r["Rincian_Belanja"], "Volume": r["Volume"], "Satuan": r["Satuan"],
                                "Harga_Satuan": r["Harga_Satuan"], "Total_Usulan": r["Volume"] * r["Harga_Satuan"],
                                "Prioritas": df_curr["Prioritas"].iloc[0], "Status": "Menunggu Review", "Catatan_Fakultas": f"Revisi: {catatan_keg}",
                                "File_TOR": path_tor_baru
                            })
                        df_usulan = pd.concat([df_usulan, pd.DataFrame(rev_entries)], ignore_index=True)
                        save_data(df_usulan)
                        st.success("Revisi berhasil dikirim!"); st.rerun()
            else:
                df_view = df_curr[["Rincian_Belanja", "Volume", "Satuan", "Harga_Satuan", "Total_Usulan"]]
                st.table(df_view.style.format({"Harga_Satuan": "{:,.0f}", "Total_Usulan": "{:,.0f}"}))

# ==========================================
# 5B. TAMPILAN ADMIN
# ==========================================
elif st.session_state["role"] == "admin":
    st.title("📊 Dashboard Monitoring & Review")
    if df_usulan.empty: st.warning("Data kosong.")
    else:
        tab1, tab2, tab3 = st.tabs(["📋 Review & Analisis", "🗑️ Manajemen Data", "🤖 Insight"])
        with tab1:
            prodi_sel = st.selectbox("Pilih Prodi:", sorted(df_usulan["Program_Studi"].unique()))
            df_p = df_usulan[df_usulan["Program_Studi"] == prodi_sel]
            for k in df_p["Nama_Kegiatan"].unique():
                df_k = df_p[df_p["Nama_Kegiatan"] == k].copy()
                with st.expander(f"{k.upper()} | Rp {df_k['Total_Usulan'].sum():,.0f} | Status: {df_k['Status'].iloc[0]}"):
                    
                    # --- MENAMPILKAN TOMBOL DOWNLOAD TOR JIKA ADA ---
                    tor_path = df_k["File_TOR"].iloc[0]
                    if tor_path != "-" and os.path.exists(tor_path):
                        with open(tor_path, "rb") as f:
                            st.download_button(
                                label="📥 Download Dokumen TOR",
                                data=f,
                                file_name=os.path.basename(tor_path),
                                mime="application/pdf",
                                key=f"dl_tor_{prodi_sel}_{k}"
                            )
                    else:
                        st.caption("*(Tidak ada dokumen TOR yang dilampirkan untuk kegiatan ini)*")
                    
                    st.markdown("---")
                    
                    c_st, c_nt = st.columns([1, 2])
                    n_stat = c_st.selectbox("Status:", ["Menunggu Review", "Disetujui", "Perlu Revisi", "Ditolak"], index=["Menunggu Review", "Disetujui", "Perlu Revisi", "Ditolak"].index(df_k["Status"].iloc[0]), key=f"s_{k}")
                    n_note = c_nt.text_area("Catatan:", value=df_k["Catatan_Fakultas"].iloc[0], key=f"n_{k}")
                    if st.button("Simpan Review", key=f"b_{k}"):
                        mask = (df_usulan["Program_Studi"] == prodi_sel) & (df_usulan["Nama_Kegiatan"] == k)
                        df_usulan.loc[mask, ["Status", "Catatan_Fakultas"]] = [n_stat, n_note]
                        save_data(df_usulan); st.success("Updated!"); st.rerun()
                    
                    st.dataframe(df_k[["Rincian_Belanja", "Volume", "Satuan", "Harga_Satuan", "Total_Usulan"]], hide_index=True)
                    
        # Tab 2 & 3 tetap sama
        with tab2:
            st.subheader("🗑️ Hapus Data")
            opsi_hapus = {idx: f"[{row['Program_Studi']}] {row['Nama_Kegiatan']} ➡️ {row['Rincian_Belanja']}" for idx, row in df_usulan.iterrows()}
            sel_h = st.selectbox("Pilih Rincian:", options=list(opsi_hapus.keys()), format_func=lambda x: opsi_hapus[x])
            if st.button("🚨 Hapus Permanen", type="primary"):
                # Opsi: Jika ingin membersihkan file TOR yang tidak terpakai, bisa ditambahkan kode os.remove() di sini
                df_usulan = df_usulan.drop(index=sel_h).reset_index(drop=True)
                save_data(df_usulan); st.success("Terhapus!"); st.rerun()
        with tab3:
            st.info(f"Total Usulan: Rp {df_usulan['Total_Usulan'].sum():,.0f}".replace(',', '.'))
            st.bar_chart(df_usulan.groupby("Program_Studi")["Total_Usulan"].sum())
