import streamlit as st
import modul_kompiler
import modul_rab
import modul_tor  # Tambahan impor modul TOR pintar

# ==========================================
# KONFIGURASI HALAMAN UTAMA
# ==========================================
st.set_page_config(page_title="Sistem Perencanaan FIB", page_icon="📝", layout="wide")

# ==========================================
# DATABASE USER & LOGIN
# ==========================================
USER_CREDENTIALS = {
    "admin": {"password": "adminfib", "role": "admin", "nama_tampil": "Fakultas Ilmu Budaya (Admin)"},
    "sasindo": {"password": "123", "role": "prodi", "nama_tampil": "Sastra Indonesia"},
    "sasing": {"password": "123", "role": "prodi", "nama_tampil": "Sastra Inggris"},
    "etno": {"password": "123", "role": "prodi", "nama_tampil": "Etnomusikologi"},
    "tari": {"password": "123", "role": "prodi", "nama_tampil": "Tari"},
    "kajian": {"password": "123", "role": "prodi", "nama_tampil": "Kajian Budaya (S2)"},
    "p2mf": {"password": "123", "role": "prodi", "nama_tampil": "Pusat Penjaminan Mutu Fakultas"}
}

if "logged_in" not in st.session_state:
    st.session_state.update({"logged_in": False, "role": None, "nama_user": None, "username": None})

if not st.session_state["logged_in"]:
    _, col_tengah, _ = st.columns([1, 2, 1])
    with col_tengah:
        st.title("🔐 Login Sistem RKA")
        st.subheader("Fakultas Ilmu Budaya - Unmul")
        with st.form("form_login"):
            u = st.text_input("Username")
            p = st.text_input("Password", type="password")
            if st.form_submit_button("Masuk", type="primary"):
                if u in USER_CREDENTIALS and USER_CREDENTIALS[u]["password"] == p:
                    st.session_state.update({"logged_in": True, "role": USER_CREDENTIALS[u]["role"], "nama_user": USER_CREDENTIALS[u]["nama_tampil"], "username": u})
                    st.rerun()
                else:
                    st.error("Username atau Password salah.")
    st.stop()

# ==========================================
# SIDEBAR & MENU NAVIGASI (DINAMIS PER ROLE)
# ==========================================
with st.sidebar:
    st.header("Sistem Perencanaan")
    st.markdown(f"👤 **{st.session_state['nama_user']}**")
    st.markdown("---")
    
    # Penyesuaian hak akses menu navigasi berdasarkan peran pengguna
    if st.session_state.get("role") == "admin":
        menu_options = [
            "1. Dashboard Kompiler Usulan", 
            "2. Pengolah Dokumen RAB", 
            "3. Generator TOR Otomatis"
        ]
    else:
        menu_options = [
            "1. Dashboard Kompiler Usulan"
        ]
        
    menu_pilihan = st.radio("📍 Navigasi Menu:", menu_options)
    st.markdown("---")
        
    if st.button("🚪 Logout", type="primary"):
        st.session_state.update({"logged_in": False, "role": None, "nama_user": None, "username": None})
        st.rerun()

# ==========================================
# ROUTING HALAMAN (MENGGUNAKAN VALIDASI TEXT)
# ==========================================
if "Dashboard Kompiler Usulan" in menu_pilihan:
    modul_kompiler.show_page()
elif "Pengolah Dokumen RAB" in menu_pilihan:
    modul_rab.show_page()
elif "Generator TOR Otomatis" in menu_pilihan:
    modul_tor.show_page()
