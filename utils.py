import streamlit as st
import pandas as pd
from datetime import datetime
from sqlalchemy import create_engine

# =====================================================================
# KONEKSI KE CLOUD DATABASE (SATU PINTU)
# =====================================================================
@st.cache_resource
def get_engine():
    return create_engine(st.secrets["DB_URL"], pool_size=10, max_overflow=20)

engine = get_engine()

# =====================================================================
# FUNGSI OTENTIKASI & SUPER ADMIN
# =====================================================================
def init_users_table():
    """Membuat tabel user jika belum ada dan menyuntikkan data bawaan"""
    try:
        with engine.connect() as conn:
            df = pd.read_sql("SELECT * FROM rab_users", conn)
            if df.empty: raise ValueError("Tabel kosong")
            return df
    except Exception:
        # Menyuntikkan data awal (Seeding)
        default_users = [
            {"Username": "admin", "Password": "adminfib", "Role": "admin", "Nama_Tampil": "Fakultas Ilmu Budaya (Admin)", "Akses_Menu": "kompiler,rab,tor,ekstrak,users"},
            {"Username": "sasindo", "Password": "123", "Role": "prodi", "Nama_Tampil": "Sastra Indonesia", "Akses_Menu": "kompiler"},
            {"Username": "sasing", "Password": "123", "Role": "prodi", "Nama_Tampil": "Sastra Inggris", "Akses_Menu": "kompiler"},
            {"Username": "etno", "Password": "123", "Role": "prodi", "Nama_Tampil": "Etnomusikologi", "Akses_Menu": "kompiler"},
            {"Username": "tari", "Password": "123", "Role": "prodi", "Nama_Tampil": "Tari", "Akses_Menu": "kompiler"},
            {"Username": "kajian", "Password": "123", "Role": "prodi", "Nama_Tampil": "Kajian Budaya (S2)", "Akses_Menu": "kompiler"},
            {"Username": "p2mf", "Password": "123", "Role": "prodi", "Nama_Tampil": "Pusat Penjaminan Mutu", "Akses_Menu": "kompiler"}
        ]
        df_users = pd.DataFrame(default_users)
        with engine.begin() as conn:
            df_users.to_sql("rab_users", conn, if_exists="replace", index=False)
        return df_users

def authenticate_user(username, password):
    """Mencocokkan data login dengan database"""
    df_users = init_users_table()
    user = df_users[(df_users["Username"] == username) & (df_users["Password"] == password)]
    if not user.empty:
        return user.iloc[0].to_dict()
    return None

# =====================================================================
# FUNGSI CCTV & DATABASE GLOBAL
# =====================================================================
def log_audit(aksi, detail):
    try:
        user = st.session_state.get("nama_user", "Sistem/Unknown")
        waktu = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        df_log = pd.DataFrame([{"Waktu": waktu, "User": user, "Aksi": aksi, "Detail": detail}])
        with engine.begin() as conn:
            df_log.to_sql("rab_logs", conn, if_exists="append", index=False)
    except Exception: pass

@st.cache_data(ttl=300)
def get_available_years():
    try:
        with engine.connect() as conn:
            df = pd.read_sql('SELECT DISTINCT "Tahun" FROM rab_utama', conn)
            if not df.empty:
                years = df['Tahun'].astype(str).tolist()
                return sorted(list(set(years + [str(datetime.now().year + 1)])), reverse=True)
    except Exception: pass
    return [str(datetime.now().year + 1)]

@st.cache_data(ttl=300)
def load_table(table_name, default_cols, where_clause=""):
    for attempt in range(2):
        try:
            with engine.connect() as conn:
                df = pd.read_sql(f"SELECT * FROM {table_name} {where_clause}", conn)
                
            for col in default_cols:
                if col not in df.columns:
                    if "Vol" in col or "Harga" in col or "Total" in col: df[col] = 1 if "Vol" in col else 0
                    elif col == "Tahun": df[col] = str(datetime.now().year + 1)
                    elif col == "Sumber_Dana": df[col] = "BOPTN"
                    elif col == "Sub_Komponen" and table_name == "rab_m_akun": df[col] = "-"
                    elif col == "Versi_RAB": df[col] = "Indikatif"
                    elif col == "Is_Active": df[col] = 1
                    else: df[col] = "-"
                    
            if "Is_Active" in df.columns:
                df["Is_Active"] = pd.to_numeric(df["Is_Active"], errors='coerce').fillna(1).astype(int)
            return df
            
        except Exception as e:
            err_str = str(e).lower()
            if "does not exist" in err_str or "not found" in err_str or "relation" in err_str:
                df = pd.DataFrame(columns=default_cols)
                try:
                    with engine.begin() as conn: df.to_sql(table_name, conn, if_exists="append", index=False)
                except: pass
                return df
            if attempt == 1: 
                st.cache_data.clear() 
                st.error(f"Sistem sedang sibuk. Koneksi ke {table_name} terputus.")
                st.stop()

def save_table(df, table_name):
    try:
        with engine.begin() as conn: df.to_sql(table_name, conn, if_exists="replace", index=False)
        st.cache_data.clear()
        return True
    except Exception as e:
        st.error(f"🚨 Gagal menyimpan {table_name}: {e}")
        return False

def update_rab_tahun(df_u_part, df_d_part, tahun):
    try:
        try:
            with engine.connect() as conn:
                df_u_sisa = pd.read_sql(f"SELECT * FROM rab_utama WHERE \"Tahun\" != '{tahun}'", conn)
                df_d_sisa = pd.read_sql(f"SELECT * FROM rab_detail WHERE \"ID_RAB\" NOT IN (SELECT \"ID_RAB\" FROM rab_utama WHERE \"Tahun\" = '{tahun}')", conn)
        except Exception:
            df_u_sisa, df_d_sisa = pd.DataFrame(), pd.DataFrame()
            
        df_u_final = pd.concat([df_u_sisa, df_u_part], ignore_index=True)
        df_d_final = pd.concat([df_d_sisa, df_d_part], ignore_index=True)
        
        with engine.begin() as conn:
            df_u_final.to_sql("rab_utama", conn, if_exists="replace", index=False)
            df_d_final.to_sql("rab_detail", conn, if_exists="replace", index=False)
            
        st.cache_data.clear()
        return True
    except Exception as e:
        st.error(f"🚨 Gagal menyimpan data RKA tahun {tahun}: {e}")
        return False

# =====================================================================
# FUNGSI FORMATTING (FORMATTER UTILS)
# =====================================================================
def format_rupiah(x):
    try: return f"{float(x):,.0f}".replace(',', '.')
    except (ValueError, TypeError): return x

def format_tgl_indo(tgl_str):
    if not tgl_str: return ""
    try:
        tgl_clean = str(tgl_str)[:10]
        dt = datetime.strptime(tgl_clean, "%Y-%m-%d")
        bulan_indo = ["", "Januari", "Februari", "Maret", "April", "Mei", "Juni", 
                      "Juli", "Agustus", "September", "Oktober", "November", "Desember"]
        return f"{dt.day} {bulan_indo[dt.month]} {dt.year}"
    except: return str(tgl_str)[:10]

def split_kode(teks):
    s = str(teks).strip()
    if " - " in s: return s.split(" - ", 1)[0].strip(), s.split(" - ", 1)[1].strip()
    parts = s.split(" ", 1)
    if len(parts) == 2:
        first_part = parts[0].strip()
        if any(c.isdigit() for c in first_part) or len(first_part) <= 8 or "." in first_part:
            return first_part, parts[1].strip()
    if any(c.isdigit() for c in s) or len(s) <= 8 or "." in s: return s, ""
    return "", s

def get_vol_sat_combined(v1, s1, v2, s2):
    v1_str = str(v1).replace(".0", "") if pd.notna(v1) else "0"
    s1_str = str(s1).strip() if pd.notna(s1) else ""
    v2_str = str(v2).replace(".0", "") if pd.notna(v2) else "0"
    s2_str = str(s2).strip() if pd.notna(s2) else ""
    if s2_str in ["", "-"] or v2_str == "0" or v2_str == "": return f"{v1_str} {s1_str}"
    return f"{v1_str} {s1_str} x {v2_str} {s2_str}"
