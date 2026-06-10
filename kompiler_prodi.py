import streamlit as st
from utils import authenticate_user

# ==========================================
# KONFIGURASI HALAMAN UTAMA
# ==========================================
st.set_page_config(page_title="Sistem Perencanaan FIB", page_icon="📝", layout="wide")

if "logged_in" not in st.session_state:
    st.session_state.update({
        "logged_in": False, 
        "role": None, 
        "nama_user": None, 
        "username": None, 
        "akses_menu": ""
    })

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
                user_data = authenticate_user(u, p)
                if user_data:
                    st.session_state.update({
                        "logged_in": True, 
                        "role": user_data["Role"], 
                        "nama_user": user_data["Nama_Tampil"], 
                        "username": user_data["Username"],
                        "akses_menu": user_data.get("Akses_Menu", "")
                    })
                    st.rerun()
                else:
                    st.error("Username atau Password salah.")
    st.stop()

# ==========================================
# NAVBAR BERJENJANG & HAK AKSES GRANULAR
# ==========================================
page_kompiler = st.Page("modul_utama/modul_kompiler.py", title="Dashboard Monitoring", icon="📊")

page_rab_master  = st.Page("modul_rab/rab_master.py", title="1. Master Data", icon="🗂️")
page_rab_buat    = st.Page("modul_rab/rab_buat.py", title="2. Buat / Edit RAB", icon="📝")
page_rab_arsip   = st.Page("modul_rab/rab_arsip.py", title="3. Arsip & Versi", icon="📂")
page_rab_rkakl   = st.Page("modul_rab/rab_rkakl.py", title="4. Rekap RKAKL", icon="📊")
page_rab_matrik  = st.Page("modul_rab/rab_matrik.py", title="5. Matrik Perubahan", icon="⚖️")
page_rab_warroom = st.Page("modul_rab/rab_warroom.py", title="6. Rapat Revisi", icon="🛠️")

page_tor     = st.Page("modul_ekstra/modul_tor.py", title="Generator TOR", icon="🤖")
page_ekstrak = st.Page("modul_ekstra/modul_ekstrak_rkakl.py", title="Ekstrak RKAKL PDF", icon="📥")
page_surat   = st.Page("modul_ekstra/modul_surat.py", title="Pengolah Surat", icon="✉️")

page_users = st.Page("modul_utama/manajemen_user.py", title="Manajemen Pengguna", icon="👥")

with st.sidebar:
    st.header("Sistem Perencanaan")
    st.markdown(f"👤 **{st.session_state['nama_user']}**")
    st.markdown("---")
    if st.button("🚪 Logout", type="primary", use_container_width=True):
        st.session_state.clear()
        st.rerun()

akses_list = st.session_state["akses_menu"].split(",")

# Mengakomodasi format lama jika masih ada yang pakai kata "rab" saja
if "rab" in akses_list:
    akses_list.extend(["rab_master", "rab_buat", "rab_arsip", "rab_rkakl", "rab_matrik", "rab_warroom"])

nav_dict = {}

# 1. Papan Kendali (Kompiler)
if "kompiler" in akses_list:
    nav_dict["PAPAN KENDALI"] = [page_kompiler]
    
# 2. Modul Anggaran (Check satu per satu tabnya)
rab_pages = []
if "rab_master" in akses_list: rab_pages.append(page_rab_master)
if "rab_buat" in akses_list: rab_pages.append(page_rab_buat)
if "rab_arsip" in akses_list: rab_pages.append(page_rab_arsip)
if "rab_rkakl" in akses_list: rab_pages.append(page_rab_rkakl)
if "rab_matrik" in akses_list: rab_pages.append(page_rab_matrik)
if "rab_warroom" in akses_list: rab_pages.append(page_rab_warroom)

if rab_pages:
    nav_dict["MODUL ANGGARAN (RAB)"] = rab_pages
    
# 3. Modul Ekstra
ekstra_pages = []
if "tor" in akses_list: ekstra_pages.append(page_tor)
if "ekstrak" in akses_list: ekstra_pages.append(page_ekstrak)
if "surat" in akses_list: ekstra_pages.append(page_surat)

if ekstra_pages:
    nav_dict["MODUL EKSTRA"] = ekstra_pages
    
# 4. Pengaturan Super Admin
if "users" in akses_list and st.session_state["role"] == "admin":
    nav_dict["PENGATURAN SUPER ADMIN"] = [page_users]

# Fail-safe jika tidak ada akses satupun
if not nav_dict:
    nav_dict["Akses Terbatas"] = [st.Page("modul_utama/modul_kompiler.py", title="Akses Ditolak", icon="🔒")]

pg = st.navigation(nav_dict)
pg.run()
