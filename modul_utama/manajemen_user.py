import streamlit as st
import pandas as pd
from utils import engine, save_table, init_users_table, log_audit

st.title("👥 Manajemen Pengguna & Hak Akses")
st.caption("Panel eksklusif Super Admin untuk mengatur kredensial login dan menu navigasi.")

# Muat data user dari database
df_users = init_users_table()

# Membantu menerjemahkan kode menu ke nama yang mudah dibaca
MENU_OPTIONS = {
    "kompiler": "Dashboard Usulan (Kompiler)",
    "rab": "Pengolah Anggaran (Seluruh Tab RAB)",
    "tor": "Generator TOR AI",
    "ekstrak": "Ekstraktor RKAKL PDF",
    "users": "Panel Super Admin (Manajemen User)"
}

col_list, col_form = st.columns([1.5, 1])

with col_list:
    st.subheader("Daftar Pengguna Aktif")
    # Menampilkan tabel sederhana
    df_tampil = df_users[["Username", "Nama_Tampil", "Role"]].copy()
    st.dataframe(df_tampil, use_container_width=True, hide_index=True)
    
    st.markdown("---")
    st.subheader("🗑️ Hapus Pengguna")
    hapus_user = st.selectbox("Pilih Username yang akan dihapus:", df_users["Username"].tolist())
    if st.button("Hapus Akun", type="primary"):
        if hapus_user == "admin":
            st.error("Akun Super Admin utama tidak boleh dihapus!")
        else:
            df_users = df_users[df_users["Username"] != hapus_user]
            save_table(df_users, "rab_users")
            log_audit("HAPUS USER", f"Menghapus akun pengguna: {hapus_user}")
            st.success(f"Akun {hapus_user} berhasil dihapus."); st.rerun()

with col_form:
    st.subheader("➕ Tambah / Edit Pengguna")
    st.info("Ketik Username yang sudah ada untuk MENGEDIT. Ketik Username baru untuk MENAMBAH.")
    
    with st.form("form_user"):
        input_uname = st.text_input("Username (Tanpa Spasi, Huruf Kecil)")
        input_pass = st.text_input("Password", type="password")
        input_nama = st.text_input("Nama Tampil (Contoh: Sastra Jepang)")
        input_role = st.selectbox("Role Identitas", ["prodi", "admin","dekan","wakil dekan","kabag"])
        
        # Pilihan Akses Menu dengan Checkbox/Multiselect
        akses_pilihan = st.multiselect(
            "Izinkan Akses ke Modul Berikut:",
            options=list(MENU_OPTIONS.keys()),
            format_func=lambda x: MENU_OPTIONS[x],
            default=["kompiler"] # Default setiap prodi bisa buka dashboard
        )
        
        if st.form_submit_button("Simpan Data Pengguna", type="primary"):
            if not input_uname or not input_pass or not input_nama:
                st.error("Username, Password, dan Nama Tampil tidak boleh kosong!")
            elif " " in input_uname:
                st.error("Username tidak boleh mengandung spasi!")
            else:
                str_akses = ",".join(akses_pilihan)
                
                # Jika user sudah ada, update. Jika belum, tambah baru.
                if input_uname in df_users["Username"].values:
                    df_users.loc[df_users["Username"] == input_uname, ["Password", "Role", "Nama_Tampil", "Akses_Menu"]] = [input_pass, input_role, input_nama, str_akses]
                    pesan_log = "Mengubah data kredensial"
                else:
                    new_user = pd.DataFrame([{
                        "Username": input_uname, "Password": input_pass, 
                        "Role": input_role, "Nama_Tampil": input_nama, 
                        "Akses_Menu": str_akses
                    }])
                    df_users = pd.concat([df_users, new_user], ignore_index=True)
                    pesan_log = "Membuat akun baru"
                
                save_table(df_users, "rab_users")
                log_audit("MANAJEMEN USER", f"{pesan_log} untuk username: {input_uname}")
                st.success(f"Berhasil menyimpan akun {input_uname}!"); st.rerun()
