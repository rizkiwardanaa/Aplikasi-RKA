import streamlit as st
import pandas as pd
import os
from io import BytesIO

# ==========================================
# 1. KONFIGURASI HALAMAN & DATABASE
# ==========================================
st.set_page_config(page_title="Kompiler Usulan Anggaran FIB", page_icon="🔐", layout="wide")

FILE_DATABASE = "database_usulan_prodi.csv"

def load_data():
    if os.path.exists(FILE_DATABASE):
        df = pd.read_csv(FILE_DATABASE)
        if "Status" not in df.columns: df["Status"] = "Menunggu Review"
        if "Catatan_Fakultas" not in df.columns: df["Catatan_Fakultas"] = "-"
        return df
    else:
        return pd.DataFrame(columns=[
            "Tanggal_Input", "Program_Studi", "Nama_Kegiatan", 
            "Rincian_Belanja", "Volume", "Satuan", "Harga_Satuan", 
            "Total_Usulan", "Prioritas", "Status", "Catatan_Fakultas"
        ])

def save_data(df):
    df.to_csv(FILE_DATABASE, index=False)

df_usulan = load_data()

# ==========================================
# 2. DATABASE USER & PASSWORD (HARDCODED)
# ==========================================
# Ini adalah daftar username, password, dan hak akses.
USER_CREDENTIALS = {
    "admin": {"password": "adminfib", "role": "admin", "nama_tampil": "Fakultas Ilmu Budaya (Admin)"},
    "sasindo": {"password": "123", "role": "prodi", "nama_tampil": "Sastra Indonesia"},
    "sasing": {"password": "123", "role": "prodi", "nama_tampil": "Sastra Inggris"},
    "etno": {"password": "123", "role": "prodi", "nama_tampil": "Etnomusikologi"},
    "tari": {"password": "123", "role": "prodi", "nama_tampil": "Tari"},
    "kajian": {"password": "123", "role": "prodi", "nama_tampil": "Kajian Budaya (S2)"}
}

# Inisialisasi Session State untuk Login
if "logged_in" not in st.session_state:
    st.session_state["logged_in"] = False
    st.session_state["role"] = None
    st.session_state["nama_user"] = None
    st.session_state["username"] = None

# ==========================================
# 3. HALAMAN LOGIN
# ==========================================
if not st.session_state["logged_in"]:
    # Mengatur tampilan agar form login ada di tengah
    col_kiri, col_tengah, col_kanan = st.columns([1, 2, 1])
    
    with col_tengah:
        st.title("🔐 Login Sistem RKA")
        st.subheader("Fakultas Ilmu Budaya - Unmul")
        st.info("Silakan masukkan Username dan Password Anda.")
        
        with st.form("form_login"):
            input_user = st.text_input("Username")
            input_pass = st.text_input("Password", type="password")
            btn_login = st.form_submit_button("Masuk", type="primary")
            
            if btn_login:
                if input_user in USER_CREDENTIALS and USER_CREDENTIALS[input_user]["password"] == input_pass:
                    # Jika benar, simpan data ke memori aplikasi
                    st.session_state["logged_in"] = True
                    st.session_state["role"] = USER_CREDENTIALS[input_user]["role"]
                    st.session_state["nama_user"] = USER_CREDENTIALS[input_user]["nama_tampil"]
                    st.session_state["username"] = input_user
                    st.rerun() # Refresh halaman secara otomatis
                else:
                    st.error("Username atau Password salah! Silakan coba lagi.")
    
    # Hentikan eksekusi kode di bawahnya jika belum login
    st.stop()

# ==========================================
# 4. SIDEBAR (SETELAH LOGIN)
# ==========================================
with st.sidebar:
    st.header("Sistem Perencanaan")
    st.markdown(f"👤 **Masuk sebagai:**\n\n*{st.session_state['nama_user']}*")
    st.markdown("---")
    
    # Tombol Logout
    if st.button("🚪 Keluar / Logout", type="primary"):
        st.session_state["logged_in"] = False
        st.session_state["role"] = None
        st.session_state["nama_user"] = None
        st.session_state["username"] = None
        st.rerun()
        
    st.markdown("---")
    if st.session_state["role"] == "admin":
        st.info("Mode: Administrator Fakultas")
    else:
        st.info("Mode: Program Studi")

# ==========================================
# 5A. TAMPILAN PRODI (FORM USULAN)
# ==========================================
if st.session_state["role"] == "prodi":
    st.title("📤 Formulir Usulan Kegiatan")
    st.subheader(f"Unit: {st.session_state['nama_user']}")
    
    with st.form("form_usulan", clear_on_submit=True):
        st.markdown("### 1️⃣ Informasi Utama Kegiatan")
        col1, col2, col3 = st.columns([1, 2, 1])
        with col1:
            # Dropdown Prodi dihapus! Diganti teks yang terkunci otomatis sesuai nama user yang login
            prodi = st.text_input("Program Studi / Unit:", value=st.session_state["nama_user"], disabled=True)
        with col2:
            nama_kegiatan = st.text_input("Nama Kegiatan Utama")
        with col3:
            prioritas = st.selectbox("Prioritas:", ["Tinggi", "Sedang", "Rendah"])
            
        st.markdown("---")
        st.markdown("### 2️⃣ Rincian RAB")
        
        df_template = pd.DataFrame([{"Rincian Belanja": "", "Volume": 0, "Satuan": "Orang", "Harga Satuan": 0}])
        edited_df = st.data_editor(
            df_template, num_rows="dynamic", use_container_width=True, hide_index=True,
            column_config={
                "Rincian Belanja": st.column_config.TextColumn("Rincian Belanja", required=True, width="large"),
                "Volume": st.column_config.NumberColumn("Volume", min_value=0, required=True),
                "Satuan": st.column_config.SelectboxColumn("Satuan", options=["Unit", "Orang", "Hari", "Bulan", "Tahun", "Jam", "Paket", "Stel", "Kegiatan"], required=True),
                "Harga Satuan": st.column_config.NumberColumn("Harga Satuan (Rp)", min_value=0, required=True)
            }
        )
        
        submit = st.form_submit_button("Kirim Usulan ke Fakultas")
        
        if submit:
            valid_rows = edited_df[edited_df["Rincian Belanja"].str.strip() != ""]
            if not nama_kegiatan.strip() or valid_rows.empty:
                st.error("Nama Kegiatan dan rincian belanja wajib diisi!")
            else:
                data_list = []
                tgl = pd.Timestamp.now().strftime("%Y-%m-%d %H:%M")
                for _, row in valid_rows.iterrows():
                    tot = row["Volume"] * row["Harga Satuan"]
                    data_list.append({
                        "Tanggal_Input": tgl, "Program_Studi": prodi, "Nama_Kegiatan": nama_kegiatan,
                        "Rincian_Belanja": row["Rincian Belanja"], "Volume": row["Volume"],
                        "Satuan": row["Satuan"], "Harga_Satuan": row["Harga Satuan"],
                        "Total_Usulan": tot, "Prioritas": prioritas,
                        "Status": "Menunggu Review", "Catatan_Fakultas": "-"
                    })
                df_usulan = pd.concat([df_usulan, pd.DataFrame(data_list)], ignore_index=True)
                save_data(df_usulan)
                st.success(f"Usulan '{nama_kegiatan}' berhasil dikirim!")

# ==========================================
# 5B. TAMPILAN ADMIN (DASHBOARD FAKULTAS)
# ==========================================
elif st.session_state["role"] == "admin":
    st.title("📊 Dashboard Monitoring & Review")
    
    if df_usulan.empty:
        st.warning("Belum ada data usulan masuk dari Prodi.")
    else:
        c1, c2, c3 = st.columns(3)
        c1.metric("Total Dana Diusulkan", f"Rp {df_usulan['Total_Usulan'].sum():,.0f}".replace(',', '.'))
        c2.metric("Kegiatan Menunggu Review", len(df_usulan[df_usulan["Status"] == "Menunggu Review"]["Nama_Kegiatan"].unique()))
        c3.metric("Prodi Berpartisipasi", df_usulan["Program_Studi"].nunique())

        st.markdown("---")
        
        tab1, tab2, tab3 = st.tabs(["📋 Review Per Prodi", "🗑️ Manajemen Data (Hapus)", "🤖 Insight Pintar"])
        
        # --- TAB 1: REVIEW DATA ---
        with tab1:
            prodi_list = sorted(df_usulan["Program_Studi"].unique())
            selected_prodi = st.selectbox("Pilih Prodi untuk Review:", prodi_list)
            df_prodi = df_usulan[df_usulan["Program_Studi"] == selected_prodi]
            kegiatan_list = df_prodi["Nama_Kegiatan"].unique()

            st.write(f"Daftar Kegiatan dari **{selected_prodi}**:")

            for keg in kegiatan_list:
                df_keg = df_prodi[df_prodi["Nama_Kegiatan"] == keg].copy()
                total_keg = df_keg["Total_Usulan"].sum()
                status_saat_ini = df_keg["Status"].iloc[0]
                catatan_saat_ini = df_keg["Catatan_Fakultas"].iloc[0]
                
                status_icon = "⏳"
                if status_saat_ini == "Disetujui": status_icon = "✅"
                elif status_saat_ini == "Perlu Revisi": status_icon = "⚠️"
                elif status_saat_ini == "Ditolak": status_icon = "❌"
                
                with st.expander(f"{status_icon} {keg.upper()} | Rp {total_keg:,.0f} | Status: {status_saat_ini}".replace(',', '.')):
                    
                    col_stat, col_note = st.columns([1, 2])
                    with col_stat:
                        new_status = st.selectbox("Update Status:", ["Menunggu Review", "Disetujui", "Perlu Revisi", "Ditolak"], index=["Menunggu Review", "Disetujui", "Perlu Revisi", "Ditolak"].index(status_saat_ini), key=f"stat_{selected_prodi}_{keg}")
                    with col_note:
                        new_note = st.text_area("Catatan/Alasan:", value=catatan_saat_ini, key=f"note_{selected_prodi}_{keg}", height=70)
                    
                    if st.button("Update Status", key=f"btn_update_{keg}"):
                        mask = (df_usulan["Program_Studi"] == selected_prodi) & (df_usulan["Nama_Kegiatan"] == keg)
                        df_usulan.loc[mask, "Status"] = new_status
                        df_usulan.loc[mask, "Catatan_Fakultas"] = new_note
                        save_data(df_usulan)
                        st.success("Status diperbarui!")
                        st.rerun()

                    st.markdown("#### 📋 Rincian Belanja")
                    df_keg["Hapus"] = False
                    df_display = df_keg[["Hapus", "Rincian_Belanja", "Volume", "Satuan", "Harga_Satuan", "Total_Usulan"]]
                    edited_df = st.data_editor(df_display, column_config={"Hapus": st.column_config.CheckboxColumn("Hapus?", default=False), "Rincian_Belanja": st.column_config.TextColumn("Rincian Belanja", disabled=True), "Total_Usulan": st.column_config.NumberColumn("Subtotal (Rp)", format="Rp %d")}, hide_index=True, use_container_width=True, key=f"editor_{selected_prodi}_{keg}")
                    
                    if st.button("✂️ Hapus Rincian Tercentang", key=f"del_checked_{keg}"):
                        indices_to_drop = edited_df[edited_df["Hapus"] == True].index
                        if len(indices_to_drop) > 0:
                            df_usulan = df_usulan.drop(index=indices_to_drop)
                            save_data(df_usulan)
                            st.success("Rincian dihapus.")
                            st.rerun()

            st.markdown("---")
            def to_excel(df_to_save):
                output = BytesIO()
                with pd.ExcelWriter(output, engine='openpyxl') as writer:
                    df_to_save.to_excel(writer, index=False, sheet_name='Kompilasi_Review')
                return output.getvalue()
            st.download_button("📥 Ekspor Data (Excel)", data=to_excel(df_usulan), file_name="Rekap_Anggaran_2026.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

        # --- TAB 2 & 3 (HAPUS & INSIGHT) ---
        with tab2:
            st.subheader("🗑️ Hapus Data Keseluruhan")
            opsi_hapus = {idx: f"[{row['Program_Studi']}] {row['Nama_Kegiatan']} ➡️ {row['Rincian_Belanja']} | Rp {row['Total_Usulan']:,.0f}".replace(',', '.') for idx, row in df_usulan.iterrows()}
            pilih_hapus = st.selectbox("Pilih Rincian:", options=list(opsi_hapus.keys()), format_func=lambda x: opsi_hapus[x])
            if st.button("🚨 Hapus Data", type="primary"):
                df_usulan = df_usulan.drop(index=pilih_hapus).reset_index(drop=True)
                save_data(df_usulan)
                st.success("Data terhapus!")
                st.rerun()

        with tab3:
            st.subheader("🤖 Analisis Komparasi Otomatis")
            tot_anggaran = df_usulan['Total_Usulan'].sum()
            prodi_max = df_usulan.groupby('Program_Studi')['Total_Usulan'].sum().idxmax()
            val_max = df_usulan.groupby('Program_Studi')['Total_Usulan'].sum().max()
            
            st.info(f"""
            Total usulan masuk mencapai **Rp {tot_anggaran:,.0f}**.
            * 📊 **Prodi Terbesar:** **{prodi_max}** (Rp {val_max:,.0f}).
            * ⏳ **Status:** {df_usulan['Status'].value_counts().get('Menunggu Review', 0)} rincian Menunggu Review.
            """.replace(',', '.'))
            
            rekap_prodi = df_usulan.groupby("Program_Studi")["Total_Usulan"].sum().reset_index()
            st.bar_chart(rekap_prodi.set_index("Program_Studi")["Total_Usulan"])
