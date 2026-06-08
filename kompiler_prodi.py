import streamlit as st

# ==========================================
# KONFIGURASI HALAMAN UTAMA (Harus Paling Atas)
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

# --- HALAMAN LOGIN ---
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
# MULTIPAGE ROUTING & NAVIGATION (LAZY LOADING)
# ==========================================
# Mendefinisikan halaman fisik tanpa memuatnya ke memori (Sangat hemat RAM)
page_kompiler = st.Page("modul_kompiler.py", title="1. Dashboard Kompiler Usulan", icon="📊")
page_rab = st.Page("modul_rab.py", title="2. Pengolah Dokumen RAB", icon="📝")
page_tor = st.Page("modul_tor.py", title="3. Generator TOR Otomatis", icon="🤖")
page_ekstrak = st.Page("modul_ekstrak_rkakl.py", title="4. Ekstrak RKAKL Universitas", icon="📥")

# Mengatur Sidebar (Logout & Identitas)
with st.sidebar:
    st.header("Sistem Perencanaan")
    st.markdown(f"👤 **{st.session_state['nama_user']}**")
    st.markdown("---")
    if st.button("🚪 Logout", type="primary"):
        st.session_state.clear()
        st.rerun()

# Memisahkan Hak Akses (Role-Based Access Control)
if st.session_state["role"] == "admin":
    # Admin melihat semua menu
    pg = st.navigation([page_kompiler, page_rab, page_tor, page_ekstrak])
else:
    # Prodi hanya melihat dashboard kompiler
    pg = st.navigation([page_kompiler])

# Menjalankan halaman yang di-klik pengguna
pg.run()
