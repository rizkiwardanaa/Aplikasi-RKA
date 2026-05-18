import streamlit as st
import pandas as pd
import os
import sqlite3
from io import BytesIO

# ==========================================
# 1. KONFIGURASI HALAMAN & LOKASI DATABASE
# ==========================================
st.set_page_config(page_title="Kompiler Usulan Anggaran FIB", page_icon="📝", layout="wide")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
FILE_DB = os.path.join(BASE_DIR, "database_usulan_prodi.db")
FILE_CSV_LAMA = os.path.join(BASE_DIR, "database_usulan_prodi.csv")
UPLOAD_DIR = os.path.join(BASE_DIR, "tor_uploads")

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

def format_rupiah(x):
    try:
        return f"{float(x):,.0f}".replace(',', '.')
    except (ValueError, TypeError):
        return x

# ==========================================
# 2. DATABASE USER
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
            u, p = st.text_input("Username"), st.text_input("Password", type="password")
            if st.form_submit_button("Masuk", type="primary"):
                if u in USER_CREDENTIALS and USER_CREDENTIALS[u]["password"] == p:
                    st.session_state.update({"logged_in": True, "role": USER_CREDENTIALS[u]["role"], "nama_user": USER_CREDENTIALS[u]["nama_tampil"], "username": u})
                    st.rerun()
                else: st.error("Username atau Password salah.")
    st.stop()

with st.sidebar:
    st.header("Sistem Perencanaan")
    st.markdown(f"👤 **{st.session_state['nama_user']}**")
    if st.button("🚪 Logout", type="primary"):
        st.session_state.update({"logged_in": False, "role": None, "nama_user": None, "username": None})
        st.rerun()

# ==========================================
# FUNGSI CETAK LAPORAN (HTML/PDF DENGAN LINK REKAYASA LOGO LATEST)
# ==========================================
def generate_html_report(df_prodi, nama_prodi, hidden=False):
    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
    <meta charset="utf-8">
    <style>
        @page {{ 
            size: A4; 
            margin: 15mm 20mm; 
            @bottom-right {{ content: "Halaman " counter(page) " dari " counter(pages); font-size: 9pt; color: #718096; font-family: 'Arial', sans-serif; }}
        }}
        *, *::before, *::after {{ box-sizing: border-box; }}
        body {{ font-family: 'Arial', sans-serif; color: #000; line-height: 1.4; margin: 0; padding: 0; font-size: 11pt; }}
        
        /* HEADER - KOP SURAT BERSIH */
        .kop-surat {{ 
            display: flex;
            align-items: center;
            justify-content: center;
            border-bottom: 4px solid #000; 
            padding-bottom: 8px; 
            margin-bottom: 25px; 
            position: relative;
        }}
        .kop-logo {{
            position: absolute;
            left: 0;
            top: 5px;
            width: 120px;
            height: auto;
        }}
        .kop-teks {{
            text-align: center;
            font-family: 'Times New Roman', Times, serif;
            flex-grow: 1;
            padding-left: 95px; /* Memberi ruang agar teks tidak tertabrak logo di kiri */
        }}
        .kop-teks h1 {{ font-size: 15pt; margin: 0; font-weight: normal; letter-spacing: 0.3px; }}
        .kop-teks h2 {{ font-size: 15pt; margin: 0; font-weight: normal; text-transform: uppercase; }}
        .kop-teks h3 {{ font-size: 17pt; margin: 0; font-weight: bold; text-transform: uppercase; }}
        .kop-teks p {{ font-size: 10.5pt; margin: 1px 0 0 0; font-family: 'Arial', sans-serif; }}
        
        /* KONTEN LAPORAN */
        .judul-laporan {{ text-align: center; margin-bottom: 25px; }}
        .judul-laporan h3 {{ font-size: 14pt; margin: 0 0 5px 0; text-transform: uppercase; }}
        .badge-prodi {{ display: inline-block; background-color: #f3f4f6; color: #111827; padding: 4px 12px; border-radius: 4px; font-weight: bold; border: 1px solid #d1d5db; }}
        
        .block-kegiatan {{ margin-bottom: 25px; page-break-inside: avoid; }}
        .header-kegiatan {{ background-color: #f3f4f6; border: 1px solid #000; padding: 8px 12px; font-weight: bold; }}
        .catatan-review {{ font-style: italic; color: #4b5563; font-size: 10pt; padding: 4px 12px; border-left: 1px solid #000; border-right: 1px solid #000; }}
        
        .tabel-rincian {{ width: 100%; border-collapse: collapse; border: 1px solid #000; }}
        .tabel-rincian th {{ border: 1px solid #000; padding: 6px; font-weight: bold; text-align: center; background-color: #f9fafb; }}
        .tabel-rincian td {{ border: 1px solid #000; padding: 6px; }}
        .text-right {{ text-align: right !important; }}
        .text-center {{ text-align: center !important; }}
        .total-row td {{ font-weight: bold; background-color: #f3f4f6 !important; }}
    </style>
    </head>
    <body>
        <div class="kop-surat">
            <img src="https://lh3.googleusercontent.com/d/13kT8UkeAomtnzXVMaVRi9KWrU2IceX4r" class="kop-logo" alt="Logo Unmul">
            <div class="kop-teks">
                <h1>KEMENTERIAN PENDIDIKAN TINGGI, SAINS,</h1>
                <h1>DAN TEKNOLOGI</h1>
                <h2>UNIVERSITAS MULAWARMAN</h2>
                <h3>FAKULTAS ILMU BUDAYA</h3>
                <p>Jl. Ki Hajar Dewantara, Kampus Gunung Kelua, Samarinda 75123</p>
                <p>Telepon (0541) 7809033</p>
                <p>Laman http://fib.unmul.ac.id &nbsp; Surel fib@unmul.ac.id</p>
            </div>
        </div>

        <div class="judul-laporan">
            <h3>Rekapitulasi Rincian Anggaran Tahun 2026</h3>
            <span class="badge-prodi">Program Studi: {nama_prodi}</span>
        </div>
    """
    
    rekap_keg_prodi = df_prodi.groupby("Nama_Kegiatan")["Total_Usulan"].sum().reset_index()
    for idx, row in rekap_keg_prodi.iterrows():
        keg = row["Nama_Kegiatan"]
        tot = row["Total_Usulan"]
        df_k = df_prodi[df_prodi["Nama_Kegiatan"] == keg]
        stat = df_k["Status"].iloc[0]
        cat = df_k["Catatan_Fakultas"].iloc[0]
        
        teks_tot = "Rp ***" if hidden else f"Rp {tot:,.0f}".replace(',', '.')
        
        html += f"""
        <div class="block-kegiatan">
            <div class="header-kegiatan">
                {idx+1}. {keg.upper()} &nbsp;|&nbsp; {teks_tot} &nbsp;|&nbsp; [{stat}]
            </div>
        """
        if cat != "-":
            html += f'<div class="catatan-review"><strong>Catatan Review:</strong> {cat}</div>'
            
        html += """
            <table class="tabel-rincian">
                <thead>
                    <tr>
                        <th style="width: 50%; text-align: left;">Rincian Belanja</th>
                        <th style="width: 10%;">Vol</th>
                        <th style="width: 15%;">Satuan</th>
        """
        if not hidden:
            html += """
                        <th style="width: 12%; text-align: right;">Harga Satuan</th>
                        <th style="width: 13%; text-align: right;">Total</th>
            """
        html += """
                    </tr>
                </thead>
                <tbody>
        """
        for _, r in df_k.iterrows():
            html += f"""
                    <tr>
                        <td>{r['Rincian_Belanja']}</td>
                        <td class="text-center">{r['Volume']}</td>
                        <td class="text-center">{r['Satuan']}</td>
            """
            if not hidden:
                html += f"""
                        <td class="text-right">{r['Harga_Satuan']:,.0f}</td>
                        <td class="text-right">{r['Total_Usulan']:,.0f}</td>
                """
            html += "</tr>"
            
        if not hidden:
            html += f"""
                    <tr class="total-row">
                        <td colspan="4" class="text-right">Total Usulan Anggaran Kegiatan</td>
                        <td class="text-right">{tot:,.0f}</td>
                    </tr>
            """
        html += """
                </tbody>
            </table>
        </div>
        """
    html += "</body></html>"
    return html.replace(',', '.')

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
        
        if not insights:
            st.success("✅ Seluruh usulan Anda sudah lengkap dan sedang dalam proses review.")
        else:
            for item in insights: st.write(item)

        st.markdown("---")
        st.markdown("### 📋 Daftar Kegiatan yang Sudah Diinput")
        if not my_data.empty:
            rekap_keg_prodi = my_data.groupby("Nama_Kegiatan")["Total_Usulan"].sum().reset_index()
            
            for k in rekap_keg_prodi["Nama_Kegiatan"]:
                df_k = my_data[my_data["Nama_Kegiatan"] == k].copy()
                total_keg_val = df_k["Total_Usulan"].sum()
                status_keg = df_k["Status"].iloc[0]
                catatan_keg = df_k["Catatan_Fakultas"].iloc[0]
                
                with st.expander(f"📌 {k.upper()} | Total: Rp {total_keg_val:,.0f} | Status: {status_keg}".replace(',', '.')):
                    if catatan_keg != "-":
                        st.warning(f"**Catatan Fakultas:** {catatan_keg}")
                    
                    if status_keg in ["Menunggu Review", "Perlu Revisi"]:
                        col_edit1, col_edit2 = st.columns([2, 1])
                        new_nama_keg = col_edit1.text_input("Nama Kegiatan:", value=k, key=f"edit_nama_{k}")
                        
                        prio_lama = df_k["Prioritas"].iloc[0] if "Prioritas" in df_k.columns else "Sedang"
                        if prio_lama not in ["Tinggi", "Sedang", "Rendah"]: prio_lama = "Sedang"
                        new_prio = col_edit2.selectbox("Prioritas:", ["Tinggi", "Sedang", "Rendah"], index=["Tinggi", "Sedang", "Rendah"].index(prio_lama), key=f"edit_prio_{k}")
                        
                        st.caption("💡 **Cara Edit/Tambah/Hapus Rincian:** Klik tabel untuk mengubah data. **Untuk menambah baris**, ketik di baris kosong paling bawah. Centang **'Hapus?'** untuk membuang baris rincian.")
                        
                        df_editable = df_k[["Rincian_Belanja", "Volume", "Satuan", "Harga_Satuan"]].reset_index(drop=True)
                        df_editable.insert(0, "Hapus", False)
                        
                        edited_keg_rows = st.data_editor(
                            df_editable, num_rows="dynamic", use_container_width=True, hide_index=True, key=f"prod_dash_ed_{k}",
                            column_config={
                                "Hapus": st.column_config.CheckboxColumn("Hapus?", default=False),
                                "Rincian_Belanja": st.column_config.TextColumn("Rincian Belanja", required=True),
                                "Volume": st.column_config.NumberColumn("Volume", min_value=0, required=True),
                                "Satuan": st.column_config.SelectboxColumn("Satuan", options=["Unit", "Orang", "Hari", "Bulan", "Tahun", "Jam", "Paket", "Stel", "Kegiatan"], required=True),
                                "Harga_Satuan": st.column_config.NumberColumn("Harga Satuan (Rp)", min_value=0, required=True)
                            }
                        )
                        
                        c_btn1, c_btn2 = st.columns([1, 4])
                        with c_btn1:
                            if st.button("💾 Simpan Perubahan", key=f"save_prod_dash_{k}"):
                                edited_keg_rows["Volume"] = pd.to_numeric(edited_keg_rows["Volume"]).fillna(0)
                                edited_keg_rows["Harga_Satuan"] = pd.to_numeric(edited_keg_rows["Harga_Satuan"]).fillna(0)
                                edited_keg_rows["Hapus"] = edited_keg_rows["Hapus"].fillna(False)
                                edited_keg_rows["Rincian_Belanja"] = edited_keg_rows["Rincian_Belanja"].fillna("")
                                
                                valid_edited = edited_keg_rows[(edited_keg_rows["Hapus"] == False) & (edited_keg_rows["Rincian_Belanja"].str.strip() != "")]
                                df_usulan = df_usulan[~((df_usulan["Program_Studi"] == st.session_state["nama_user"]) & (df_usulan["Nama_Kegiatan"] == k))]
                                
                                if not valid_edited.empty:
                                    tgl_up = pd.Timestamp.now().strftime("%Y-%m-%d %H:%M")
                                    updated_entries = pd.DataFrame([{
                                        "Tanggal_Input": tgl_up, "Program_Studi": st.session_state["nama_user"], "Nama_Kegiatan": new_nama_keg.strip(),
                                        "Rincian_Belanja": r["Rincian Belanja"], "Volume": r["Volume"], "Satuan": r["Satuan"],
                                        "Harga_Satuan": r["Harga_Satuan"], "Total_Usulan": r["Volume"] * r["Harga_Satuan"],
                                        "Prioritas": new_prio, "Status": "Menunggu Review", "Catatan_Fakultas": "-",
                                        "File_TOR": df_k["File_TOR"].iloc[0] if "File_TOR" in df_k.columns else "-"
                                    } for _, r in valid_edited.iterrows()])
                                    df_usulan = pd.concat([df_usulan, updated_entries], ignore_index=True)
                                    
                                save_data(df_usulan)
                                st.success("Perubahan usulan disimpan!")
                                st.rerun()
                                
                        with c_btn2:
                            if st.button("🚨 Hapus Seluruh Kegiatan", key=f"del_prod_dash_{k}", type="secondary"):
                                df_usulan = df_usulan[~((df_usulan["Program_Studi"] == st.session_state["nama_user"]) & (df_usulan["Nama_Kegiatan"] == k))]
                                save_data(df_usulan)
                                st.success("Seluruh kegiatan berhasil dihapus!")
                                st.rerun()
                    else:
                        st.info(f"🔒 Data tidak dapat diedit/dihapus karena telah menerima keputusan Fakultas (**{status_keg}**).")
                        st.dataframe(df_k[["Rincian_Belanja", "Volume", "Satuan", "Harga_Satuan", "Total_Usulan"]].style.format({
                            "Harga_Satuan": format_rupiah, "Total_Usulan": format_rupiah
                        }), hide_index=True, use_container_width=True)
        else:
            st.info("Belum ada kegiatan yang diusulkan. Silakan buat usulan baru di tab 'Buat Usulan Baru'.")

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
                        "Tanggal_Input": pd.Timestamp.now().strftime("%Y-%m-%d %H:%M"), "Program_Studi": st.session_state["nama_user"], "Nama_Kegiatan": nama_keg,
                        "Rincian_Belanja": r["Rincian Belanja"], "Volume": r["Volume"], "Satuan": r["Satuan"],
                        "Harga_Satuan": r["Harga Satuan"], "Total_Usulan": r["Volume"] * r["Harga Satuan"],
                        "Prioritas": "Sedang", "Status": "Menunggu Review", "Catatan_Fakultas": "-", "File_TOR": path_tor
                    } for _, r in valid.iterrows()])
                    df_usulan = pd.concat([df_usulan, new_data], ignore_index=True)
                    save_data(df_usulan); st.success("Terkirim!"); st.rerun()

    with tab_riwayat:
        my_data = df_usulan[df_usulan["Program_Studi"] == st.session_state["nama_user"]]
        if not my_data.empty:
            sel_keg = st.selectbox("Pilih Kegiatan untuk Direvisi/Update TOR:", my_data["Nama_Kegiatan"].unique())
            df_curr = my_data[my_data["Nama_Kegiatan"] == sel_keg]
            status_saat_ini = df_curr['Status'].iloc[0]
            st.info(f"Status: {status_saat_ini} | Catatan: {df_curr['Catatan_Fakultas'].iloc[0]}")
            
            if status_saat_ini in ["Menunggu Review", "Perlu Revisi"]:
                st.warning("⚠️ Silakan perbaiki rincian biaya di bawah ini (Centang 'Hapus?' untuk membuang rincian, atau tambah baris kosong di bawah) dan klik 'Kirim Ulang Revisi'.")
                
                df_to_edit = df_curr[["Rincian_Belanja", "Volume", "Satuan", "Harga_Satuan"]].reset_index(drop=True)
                df_to_edit.insert(0, "Hapus", False)
                
                rev_ed = st.data_editor(df_to_edit, num_rows="dynamic", use_container_width=True, hide_index=True, column_config={
                    "Hapus": st.column_config.CheckboxColumn("Hapus?", default=False),
                    "Satuan": st.column_config.SelectboxColumn("Satuan", options=["Unit", "Orang", "Hari", "Bulan", "Tahun", "Jam", "Paket", "Stel", "Kegiatan"])
                })
                if st.button("Kirim Ulang Revisi"):
                    rev_ed["Volume"] = pd.to_numeric(rev_ed["Volume"]).fillna(0)
                    rev_ed["Harga_Satuan"] = pd.to_numeric(rev_ed["Harga_Satuan"]).fillna(0)
                    rev_ed["Hapus"] = rev_ed["Hapus"].fillna(False)
                    rev_ed["Rincian_Belanja"] = rev_ed["Rincian_Belanja"].fillna("")
                    valid_rev = rev_ed[(rev_ed["Hapus"] == False) & (rev_ed["Rincian_Belanja"].str.strip() != "")]
                    
                    df_usulan = df_usulan[~((df_usulan["Program_Studi"]==st.session_state["nama_user"]) & (df_usulan["Nama_Kegiatan"]==sel_keg))]
                    
                    if not valid_rev.empty:
                        rev_entries = []
                        tgl_rev = pd.Timestamp.now().strftime("%Y-%m-%d %H:%M")
                        for _, r in valid_rev.iterrows():
                            rev_entries.append({
                                "Tanggal_Input": tgl_rev, "Program_Studi": st.session_state["nama_user"], "Nama_Kegiatan": sel_keg,
                                "Rincian_Belanja": r["Rincian_Belanja"], "Volume": r["Volume"], "Satuan": r["Satuan"],
                                "Harga_Satuan": r["Harga_Satuan"], "Total_Usulan": r["Volume"] * r["Harga_Satuan"],
                                "Prioritas": df_curr["Prioritas"].iloc[0], "Status": "Menunggu Review", "Catatan_Fakultas": f"Revisi: {df_curr['Catatan_Fakultas'].iloc[0]}",
                                "File_TOR": df_curr["File_TOR"].iloc[0]
                            })
                        df_usulan = pd.concat([df_usulan, pd.DataFrame(rev_entries)], ignore_index=True)
                        
                    save_data(df_usulan)
                    st.success("Revisi berhasil dikirim!"); st.rerun()
            else:
                st.info(f"🔒 Data tidak dapat diedit karena status saat ini: **{status_saat_ini}**.")
                st.table(df_curr[["Rincian_Belanja", "Volume", "Satuan", "Harga_Satuan", "Total_Usulan"]].style.format({
                    "Harga_Satuan": format_rupiah, "Total_Usulan": format_rupiah
                }))
            
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
# TAMPILAN ADMIN (FAKULTAS)
# ==========================================
elif st.session_state["role"] == "admin":
    st.title("📊 Dashboard Monitoring & Review")
    
    col_info, col_toggle = st.columns([3, 1])
    with col_info:
        st.info("Gunakan tab di bawah untuk meninjau usulan dari setiap Program Studi.")
    with col_toggle:
        sembunyikan_nilai = st.toggle("🙈 Sembunyikan Nominal Anggaran", value=False)
    
    if df_usulan.empty: 
        st.warning("Data kosong.")
    else:
        tab_rev, tab_hapus, tab_ins = st.tabs(["📋 Review & Analisis", "🗑️ Manajemen Data", "🤖 Insight Fakultas"])
        
        with tab_rev:
            st.subheader("🏙️ Rekapitulasi Anggaran Per Prodi")
            rekap_semua = df_usulan.groupby("Program_Studi")["Total_Usulan"].sum().reset_index()
            rekap_semua.columns = ["Program Studi", "Total Usulan (Rp)"]
            
            if sembunyikan_nilai:
                rekap_semua["Total Usulan (Rp)"] = "Rp ***"
                st.table(rekap_semua)
            else:
                st.table(rekap_semua.style.format({"Total Usulan (Rp)": format_rupiah}))

            st.markdown("---")
            
            st.subheader("🔍 Detail Kegiatan Per Prodi")
            prodi_sel = st.selectbox("Pilih Prodi untuk melihat daftar kegiatan:", sorted(df_usulan["Program_Studi"].unique()))
            df_p = df_usulan[df_usulan["Program_Studi"] == prodi_sel]
            
            rekap_keg_prodi = df_p.groupby("Nama_Kegiatan")["Total_Usulan"].sum().reset_index()
            st.write(f"Berikut adalah daftar kegiatan dari **{prodi_sel}**:")
            
            for k in rekap_keg_prodi["Nama_Kegiatan"]:
                df_k = df_p[df_p["Nama_Kegiatan"] == k].copy()
                total_keg_val = df_k["Total_Usulan"].sum()
                
                teks_nominal_expander = "Rp ***" if sembunyikan_nilai else f"Rp {total_keg_val:,.0f}".replace(',', '.')
                
                with st.expander(f"📌 {k.upper()} | Total Usulan: {teks_nominal_expander} | Status: {df_k['Status'].iloc[0]}"):
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
                    
                    if sembunyikan_nilai:
                        df_tampil = df_k[["Rincian_Belanja", "Volume", "Satuan"]].copy()
                        st.dataframe(df_tampil, hide_index=True, use_container_width=True)
                    else:
                        st.dataframe(df_k[["Rincian_Belanja", "Volume", "Satuan", "Harga_Satuan", "Total_Usulan"]].style.format({
                            "Harga_Satuan": format_rupiah, "Total_Usulan": format_rupiah
                        }), hide_index=True, use_container_width=True)

        with tab_hapus:
            st.subheader("🗑️ Hapus Data Rincian")
            opsi_hapus = {idx: f"[{row['Program_Studi']}] {row['Nama_Kegiatan']} - {row['Rincian_Belanja']}" for idx, row in df_usulan.iterrows()}
            sel_h = st.selectbox("Pilih data rincian belanja:", options=list(opsi_hapus.keys()), format_func=lambda x: opsi_hapus[x])
            if st.button("🚨 Hapus Permanen", type="primary"):
                df_usulan = df_usulan.drop(index=sel_h).reset_index(drop=True)
                save_data(df_usulan); st.success("Data berhasil dihapus!"); st.rerun()

        with tab_ins:
            st.subheader("🤖 Analisis & Insight Pintar")
            
            if sembunyikan_nilai:
                st.warning("⚠️ Insight angka dan grafik dinonaktifkan karena mode 'Sembunyikan Nominal Anggaran' sedang aktif.")
            else:
                tot = df_usulan['Total_Usulan'].sum()
                if tot > 0:
                    prodi_max = df_usulan.groupby('Program_Studi')['Total_Usulan'].sum().idxmax()
                    val_max = df_usulan.groupby('Program_Studi')['Total_Usulan'].sum().max()
                    keg_mahal = df_usulan.groupby('Nama_Kegiatan')['Total_Usulan'].sum().idxmax()
                    val_keg_mahal = df_usulan.groupby('Nama_Kegiatan')['Total_Usulan'].sum().max()

                    st.info(f"""
                    💡 **Ringkasan Eksekutif AI:**
                    Total anggaran yang diajukan saat ini adalah **Rp {tot:,.0f}**.
                    
                    * 📊 **Prodi Terbesar:** Saat ini **{prodi_max}** merupakan unit pengusul tertinggi dengan nilai **Rp {val_max:,.0f}**.
                    * 💎 **Kegiatan Prioritas Tinggi:** Kegiatan **"{keg_mahal}"** adalah pengajuan tunggal terbesar senilai **Rp {val_keg_mahal:,.0f}**.
                    * ⏳ **Review:** Masih ada {df_usulan['Status'].value_counts().get('Menunggu Review', 0)} rincian yang belum diproses.
                    """.replace(',', '.'))
                    
                    st.markdown("### 📊 Perbandingan Anggaran antar Prodi")
                    rekap_ins = df_usulan.groupby("Program_Studi")["Total_Usulan"].sum().reset_index()
                    st.bar_chart(rekap_ins.set_index("Program_Studi")["Total_Usulan"])
                    
                    st.markdown("### 📑 Rekapitulasi Rinci Per Program Studi")
                    st.caption("Tabel di bawah ini merangkum total anggaran, jumlah kegiatan, dan status review untuk masing-masing Program Studi.")
                    
                    status_pivot = pd.crosstab(df_usulan["Program_Studi"], df_usulan["Status"]).reset_index()
                    rekap_detail = df_usulan.groupby("Program_Studi").agg(
                        Total_Anggaran=("Total_Usulan", "sum"),
                        Jumlah_Kegiatan=("Nama_Kegiatan", "nunique")
                    ).reset_index()
                    
                    rekap_final = pd.merge(rekap_detail, status_pivot, on="Program_Studi", how="left").fillna(0)
                    
                    for stat in ["Menunggu Review", "Disetujui", "Perlu Revisi", "Ditolak"]:
                        if stat not in rekap_final.columns:
                            rekap_final[stat] = 0
                            
                    rekap_final.rename(columns={
                        "Program_Studi": "Program Studi", 
                        "Jumlah_Kegiatan": "Jml Kegiatan",
                        "Total_Anggaran": "Total Anggaran (Rp)"
                    }, inplace=True)
                    
                    kolom_tampil = ["Program Studi", "Jml Kegiatan", "Menunggu Review", "Disetujui", "Perlu Revisi", "Ditolak", "Total Anggaran (Rp)"]
                    
                    st.dataframe(
                        rekap_final[kolom_tampil].style.format({"Total Anggaran (Rp)": format_rupiah}),
                        hide_index=True,
                        use_container_width=True,
                        column_config={
                            "Jml Kegiatan": st.column_config.NumberColumn("Jml Kegiatan", format="%d"),
                            "Menunggu Review": st.column_config.NumberColumn("Menunggu Review", format="%d"),
                            "Disetujui": st.column_config.NumberColumn("Disetujui", format="%d"),
                            "Perlu Revisi": st.column_config.NumberColumn("Perlu Revisi", format="%d"),
                            "Ditolak": st.column_config.NumberColumn("Ditolak", format="%d")
                        }
                    )
                else:
                    st.info("Data belum tersedia untuk analisis.")

            def format_df_ke_hirarki(df_mentah, hidden=False):
                df_h = df_mentah.sort_values(by=["Program_Studi", "Nama_Kegiatan"]).copy()
                if not hidden:
                    df_h["Harga_Satuan"] = df_h["Harga_Satuan"].apply(lambda x: f"{x:,.0f}".replace(',', '.'))
                    df_h["Total_Usulan"] = df_h["Total_Usulan"].apply(lambda x: f"{x:,.0f}".replace(',', '.'))
                
                is_duplicate = df_h.duplicated(subset=["Program_Studi", "Nama_Kegiatan"])
                df_h.loc[is_duplicate, "Program_Studi"] = ""
                df_h.loc[is_duplicate, "Nama_Kegiatan"] = ""
                df_h.loc[is_duplicate, "Status"] = ""
                df_h.loc[is_duplicate, "Catatan_Fakultas"] = ""
                
                df_h = df_h[["Program_Studi", "Nama_Kegiatan", "Rincian_Belanja", "Volume", "Satuan", "Harga_Satuan", "Total_Usulan", "Status", "Catatan_Fakultas"]]
                df_h.rename(columns={
                    "Program_Studi": "Program Studi", "Nama_Kegiatan": "Nama Kegiatan", "Rincian_Belanja": "Rincian Belanja",
                    "Harga_Satuan": "Harga Satuan (Rp)", "Total_Usulan": "Total Rincian (Rp)", "Catatan_Fakultas": "Catatan Review"
                }, inplace=True)
                
                if hidden: df_h.drop(columns=["Harga Satuan (Rp)", "Total Rincian (Rp)"], inplace=True)
                return df_h

            def generate_excel(df_to_save, nama_sheet):
                output = BytesIO()
                with pd.ExcelWriter(output, engine='openpyxl') as writer:
                    df_to_save.to_excel(writer, index=False, sheet_name=nama_sheet)
                return output.getvalue()

            st.markdown("---")
            st.markdown("### 📄 Laporan Cetak Hirarki & PDF Print-Ready")
            st.caption("Lihat dan unduh laporan yang telah dikelompokkan secara visual. Tombol PDF HTML akan mengunduh format web yang siap di-print/disimpan sebagai PDF (Ctrl+P).")
            
            prodi_ins_sel = st.selectbox("Pilih Program Studi untuk dilihat:", sorted(df_usulan["Program_Studi"].unique()), key="ins_prodi_sel")
            df_ins_p = df_usulan[df_usulan["Program_Studi"] == prodi_ins_sel]
            
            if not df_ins_p.empty:
                df_hirarki_prodi = format_df_ke_hirarki(df_ins_p, hidden=sembunyikan_nilai)
                st.dataframe(df_hirarki_prodi, hide_index=True, use_container_width=True)
                
                col_dl1, col_dl2, col_dl3 = st.columns(3)
                
                with col_dl1:
                    excel_prodi = generate_excel(df_hirarki_prodi, nama_sheet=prodi_ins_sel[:30])
                    st.download_button("📥 Excel: Laporan Prodi", data=excel_prodi, file_name=f"Laporan_{prodi_ins_sel}_2026.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
                
                with col_dl2:
                    df_hirarki_semua = format_df_ke_hirarki(df_usulan, hidden=sembunyikan_nilai)
                    excel_semua = generate_excel(df_hirarki_semua, nama_sheet="Seluruh_Fakultas")
                    st.download_button("📥 Excel: Laporan Fakultas", data=excel_semua, file_name="Laporan_FIB_Seluruh_Prodi_2026.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
                
                with col_dl3:
                    html_pdf_ready = generate_html_report(df_ins_p, prodi_ins_sel, hidden=sembunyikan_nilai)
                    st.download_button("🖨️ PDF: Laporan Print (Web)", data=html_pdf_ready.encode('utf-8'), file_name=f"Laporan_Cetak_{prodi_ins_sel}.html", mime="text/html", help="Buka file ini di browser, lalu tekan Ctrl+P untuk menyimpannya sebagai PDF dengan desain rapih.")
            else:
                st.info(f"Belum ada data kegiatan untuk {prodi_ins_sel}.")
