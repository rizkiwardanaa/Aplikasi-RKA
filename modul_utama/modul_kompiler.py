import streamlit as st
import pandas as pd
import os
from io import BytesIO
from sqlalchemy import create_engine

# Mengambil fungsi untuk menarik data RAB Aktif
from utils import load_table

# =====================================================================
# KONEKSI KE CLOUD DATABASE 
# =====================================================================
DB_URL = st.secrets["DB_URL"]
engine = create_engine(DB_URL, pool_size=10, max_overflow=20, pool_timeout=30)

UPLOAD_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "tor_uploads")
if not os.path.exists(UPLOAD_DIR): os.makedirs(UPLOAD_DIR)

# =====================================================================
# FUNGSI DATABASE KOMPILER PRODI 
# =====================================================================
@st.cache_data(ttl=300) 
def load_data():
    try:
        with engine.connect() as conn:
            df = pd.read_sql("SELECT * FROM usulan", conn)
            # Auto-Heal: Jika kolom Akomodasi_Anggaran belum ada di DB lama, buatkan otomatis
            if "Akomodasi_Anggaran" not in df.columns:
                df["Akomodasi_Anggaran"] = "- Belum Ditentukan -"
            return df
    except Exception as e:
        err_str = str(e).lower()
        if "does not exist" in err_str or "not found" in err_str or "relation" in err_str:
            df_kosong = pd.DataFrame(columns=["Tanggal_Input", "Program_Studi", "Nama_Kegiatan", "Rincian_Belanja", "Volume", "Satuan", "Harga_Satuan", "Total_Usulan", "Prioritas", "Status", "Catatan_Fakultas", "File_TOR", "Akomodasi_Anggaran"])
            with engine.begin() as conn: 
                df_kosong.to_sql("usulan", conn, if_exists="append", index=False)
            return df_kosong
        else:
            st.error(f"Koneksi database sedang sibuk. Error: {e}")
            return pd.DataFrame(columns=["Tanggal_Input", "Program_Studi", "Nama_Kegiatan", "Rincian_Belanja", "Volume", "Satuan", "Harga_Satuan", "Total_Usulan", "Prioritas", "Status", "Catatan_Fakultas", "File_TOR", "Akomodasi_Anggaran"])

def save_data(df):
    with engine.begin() as conn: 
        df.to_sql("usulan", conn, if_exists="replace", index=False)
    load_data.clear() 

def format_rupiah(x):
    try: return f"{float(x):,.0f}".replace(',', '.')
    except (ValueError, TypeError): return x

# =====================================================================
# FUNGSI CETAK LAPORAN 
# =====================================================================
def format_df_ke_hirarki(df_mentah, hidden=False):
    df_h = df_mentah.sort_values(by=["Program_Studi", "Nama_Kegiatan"]).copy()
    if not hidden:
        df_h["Harga_Satuan"] = df_h["Harga_Satuan"].apply(lambda x: format_rupiah(x))
        df_h["Total_Usulan"] = df_h["Total_Usulan"].apply(lambda x: format_rupiah(x))
    
    is_duplicate = df_h.duplicated(subset=["Program_Studi", "Nama_Kegiatan"])
    df_h.loc[is_duplicate, "Program_Studi"] = ""
    df_h.loc[is_duplicate, "Nama_Kegiatan"] = ""
    df_h.loc[is_duplicate, "Status"] = ""
    df_h.loc[is_duplicate, "Catatan_Fakultas"] = ""
    df_h.loc[is_duplicate, "Akomodasi_Anggaran"] = ""
    
    df_h = df_h[["Program_Studi", "Nama_Kegiatan", "Rincian_Belanja", "Volume", "Satuan", "Harga_Satuan", "Total_Usulan", "Status", "Akomodasi_Anggaran", "Catatan_Fakultas"]]
    df_h.rename(columns={"Program_Studi": "Program Studi", "Nama_Kegiatan": "Nama Kegiatan", "Rincian_Belanja": "Rincian Belanja", "Harga_Satuan": "Harga Satuan (Rp)", "Total_Usulan": "Total Rincian (Rp)", "Catatan_Fakultas": "Catatan Review"}, inplace=True)
    if hidden: df_h.drop(columns=["Harga Satuan (Rp)", "Total Rincian (Rp)"], inplace=True)
    return df_h

def generate_excel(df_to_save, nama_sheet):
    output = BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df_to_save.to_excel(writer, index=False, sheet_name=nama_sheet)
    return output.getvalue()


# =====================================================================
# FUNGSI UTAMA HALAMAN KOMPILER (RENDER UI)
# =====================================================================
def show_page():
    df_usulan = load_data().copy()
    role_user = st.session_state.get("role", "")
    
    # ----------------------------------------------------
    # TAMPILAN PRODI (PENGUSUL)
    # ----------------------------------------------------
    if role_user == "prodi":
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
            st.markdown("### 📋 Daftar Kegiatan yang Sudah Diinput")
            if not my_data.empty:
                rekap_keg_prodi = my_data.groupby("Nama_Kegiatan")["Total_Usulan"].sum().reset_index()
                for k in rekap_keg_prodi["Nama_Kegiatan"]:
                    df_k = my_data[my_data["Nama_Kegiatan"] == k].copy()
                    total_keg_val = df_k["Total_Usulan"].sum()
                    status_keg = df_k["Status"].iloc[0]
                    catatan_keg = df_k["Catatan_Fakultas"].iloc[0]
                    akomodasi_keg = df_k.get("Akomodasi_Anggaran", pd.Series(["- Belum Ditentukan -"])).iloc[0]
                    
                    with st.expander(f"📌 {k.upper()} | Total: Rp {total_keg_val:,.0f} | Status: {status_keg}".replace(',', '.')):
                        
                        # Info Mapping Anggaran untuk Prodi
                        if akomodasi_keg != "- Belum Ditentukan -":
                            st.info(f"**Tindak Lanjut Fakultas:** {akomodasi_keg}")
                            
                        if catatan_keg != "-": st.warning(f"**Catatan Fakultas:** {catatan_keg}")
                        
                        if status_keg in ["Menunggu Review", "Perlu Revisi"]:
                            col_edit1, col_edit2 = st.columns([2, 1])
                            new_nama_keg = col_edit1.text_input("Nama Kegiatan:", value=k, key=f"edit_nama_{k}")
                            prio_lama = df_k["Prioritas"].iloc[0] if "Prioritas" in df_k.columns else "Sedang"
                            if prio_lama not in ["Tinggi", "Sedang", "Rendah"]: prio_lama = "Sedang"
                            new_prio = col_edit2.selectbox("Prioritas:", ["Tinggi", "Sedang", "Rendah"], index=["Tinggi", "Sedang", "Rendah"].index(prio_lama), key=f"edit_prio_{k}")
                            
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
                                            "File_TOR": df_k["File_TOR"].iloc[0] if "File_TOR" in df_k.columns else "-",
                                            "Akomodasi_Anggaran": "- Belum Ditentukan -"
                                        } for _, r in valid_edited.iterrows()])
                                        df_usulan = pd.concat([df_usulan, updated_entries], ignore_index=True)
                                    save_data(df_usulan); st.success("Tersimpan!"); st.rerun()
                            with c_btn2:
                                if st.button("🚨 Hapus Kegiatan", key=f"del_prod_dash_{k}", type="secondary"):
                                    df_usulan = df_usulan[~((df_usulan["Program_Studi"] == st.session_state["nama_user"]) & (df_usulan["Nama_Kegiatan"] == k))]
                                    save_data(df_usulan); st.success("Dihapus!"); st.rerun()
                        else:
                            st.info(f"🔒 Data tidak dapat diedit karena telah menerima keputusan Fakultas (**{status_keg}**).")
                            st.dataframe(df_k[["Rincian_Belanja", "Volume", "Satuan", "Harga_Satuan", "Total_Usulan"]].style.format({"Harga_Satuan": format_rupiah, "Total_Usulan": format_rupiah}), hide_index=True, use_container_width=True)
            else:
                st.info("Belum ada kegiatan yang diusulkan. Silakan buat usulan baru di tab 'Buat Usulan Baru'.")

        with tab_baru:
            with st.form("form_input", clear_on_submit=True):
                nama_keg = st.text_input("Nama Kegiatan Utama")
                file_tor = st.file_uploader("Upload TOR (PDF, Maks 5MB)", type=["pdf"])
                template = pd.DataFrame([{"Rincian Belanja": "", "Volume": 0, "Satuan": "Orang", "Harga Satuan": 0}])
                edited = st.data_editor(template, num_rows="dynamic", use_container_width=True, hide_index=True, column_config={"Satuan": st.column_config.SelectboxColumn("Satuan", options=["Unit", "Orang", "Hari", "Bulan", "Tahun", "Jam", "Paket", "Stel", "Kegiatan"])})
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
                            "Prioritas": "Sedang", "Status": "Menunggu Review", "Catatan_Fakultas": "-", 
                            "File_TOR": path_tor, "Akomodasi_Anggaran": "- Belum Ditentukan -"
                        } for _, r in valid.iterrows()])
                        df_usulan = pd.concat([df_usulan, new_data], ignore_index=True)
                        save_data(df_usulan); st.success("Terkirim!"); st.rerun()

        with tab_riwayat:
            # (Tab Riwayat - Kode tidak berubah, hanya pass through)
            my_data = df_usulan[df_usulan["Program_Studi"] == st.session_state["nama_user"]]
            if not my_data.empty:
                sel_keg = st.selectbox("Pilih Kegiatan untuk Direvisi/Update TOR:", my_data["Nama_Kegiatan"].unique())
                df_curr = my_data[my_data["Nama_Kegiatan"] == sel_keg]
                status_saat_ini = df_curr['Status'].iloc[0]
                st.info(f"Status: {status_saat_ini} | Catatan: {df_curr['Catatan_Fakultas'].iloc[0]}")
                
                with st.expander("📄 Update / Susulan Dokumen TOR"):
                    new_tor = st.file_uploader("Upload PDF (Maks 5MB)", type=["pdf"], key=f"up_{sel_keg}")
                    if st.button("Simpan Dokumen", key=f"btn_{sel_keg}"):
                        if new_tor:
                            safe_name = "".join([c for c in sel_keg if c.isalnum()]).rstrip()
                            path = os.path.join(UPLOAD_DIR, f"TOR_UPD_{st.session_state['username']}_{safe_name}.pdf")
                            with open(path, "wb") as f: f.write(new_tor.getbuffer())
                            df_usulan.loc[(df_usulan["Program_Studi"]==st.session_state["nama_user"]) & (df_usulan["Nama_Kegiatan"]==sel_keg), "File_TOR"] = path
                            save_data(df_usulan); st.success("TOR Terupdate!"); st.rerun()

    # ----------------------------------------------------
    # TAMPILAN ADMIN & PIMPINAN (REVIEWER)
    # ----------------------------------------------------
    elif role_user in ["admin", "pimpinan", "dekan", "wadek", "reviewer"]:
        st.title("📊 Dashboard Monitoring & Review")
        
        # PERSIAPAN OPSI SOFT-MAPPING AKOMODASI (Ditarik dari RKAKL Aktif)
        df_rab_aktif = load_table("rab_utama", ["Kegiatan", "Is_Active", "Tahun"], 'WHERE "Is_Active" = 1')
        kegiatan_rkakl = sorted(df_rab_aktif['Kegiatan'].unique().tolist()) if not df_rab_aktif.empty else []
        
        # Menyusun Dropdown Hybrid (Statik + Dinamik)
        opsi_akomodasi = [
            "- Belum Ditentukan -", 
            "⏳ Dianggarkan di Tahun Anggaran Selanjutnya", 
            "🔄 Dipertimbangkan masuk ke Revisi Anggaran Mendatang"
        ] + [f"✅ Diakomodasi via RKAKL: {k}" for k in kegiatan_rkakl]

        col_info, col_toggle = st.columns([3, 1])
        with col_info: st.info("Gunakan tab di bawah untuk meninjau usulan dari setiap Program Studi.")
        with col_toggle: sembunyikan_nilai = st.toggle("🙈 Sembunyikan Nominal Anggaran", value=False)
        
        if role_user == "admin":
            tab_rev, tab_ins, tab_hapus, tab_restore, tab_log = st.tabs(["📋 Review & Analisis", "🤖 Insight", "🗑️ Manajemen Data", "♻️ Restore Data", "🕵️ Log Aktivitas (CCTV)"])
        else:
            tab_rev, tab_ins = st.tabs(["📋 Review & Analisis", "🤖 Insight Pintar"])

        # ---> ISI TAB REVIEW
        with tab_rev:
            if df_usulan.empty: st.warning("Data kosong.")
            else:
                st.subheader("🏙️ Rekapitulasi Anggaran Per Prodi")
                rekap_semua = df_usulan.groupby("Program_Studi")["Total_Usulan"].sum().reset_index()
                rekap_semua.columns = ["Program Studi", "Total Usulan (Rp)"]
                if sembunyikan_nilai:
                    rekap_semua["Total Usulan (Rp)"] = "Rp ***"
                    st.table(rekap_semua)
                else: st.table(rekap_semua.style.format({"Total Usulan (Rp)": format_rupiah}))

                st.markdown("---")
                prodi_sel = st.selectbox("Pilih Prodi untuk melihat daftar kegiatan:", sorted(df_usulan["Program_Studi"].unique()))
                df_p = df_usulan[df_usulan["Program_Studi"] == prodi_sel]
                rekap_keg_prodi = df_p.groupby("Nama_Kegiatan")["Total_Usulan"].sum().reset_index()
                
                for k in rekap_keg_prodi["Nama_Kegiatan"]:
                    df_k = df_p[df_p["Nama_Kegiatan"] == k].copy()
                    total_keg_val = df_k["Total_Usulan"].sum()
                    teks_nominal_expander = "Rp ***" if sembunyikan_nilai else f"Rp {format_rupiah(total_keg_val)}"
                    
                    with st.expander(f"📌 {k.upper()} | Total Usulan: {teks_nominal_expander} | Status: {df_k['Status'].iloc[0]}"):
                        path = df_k["File_TOR"].iloc[0]
                        if path != "-" and os.path.exists(path):
                            with open(path, "rb") as f: st.download_button("📥 Download TOR", f, file_name=os.path.basename(path), key=f"dl_{prodi_sel}_{k}")
                        
                        c1, c2 = st.columns([1, 1])
                        n_s = c1.selectbox("Keputusan (Status):", ["Menunggu Review", "Disetujui", "Perlu Revisi", "Ditolak"], index=["Menunggu Review", "Disetujui", "Perlu Revisi", "Ditolak"].index(df_k["Status"].iloc[0]), key=f"s_{prodi_sel}_{k}")
                        
                        # --- DROPDOWN BARU: MAPPING AKOMODASI ---
                        akomodasi_lama = df_k.get("Akomodasi_Anggaran", pd.Series(["- Belum Ditentukan -"])).iloc[0]
                        if akomodasi_lama not in opsi_akomodasi: opsi_akomodasi.append(akomodasi_lama)
                        n_a = c2.selectbox("Tindak Lanjut / Akomodasi:", opsi_akomodasi, index=opsi_akomodasi.index(akomodasi_lama), key=f"a_{prodi_sel}_{k}")
                        
                        n_n = st.text_area("Catatan Pimpinan (Saran/Koreksi):", value=df_k["Catatan_Fakultas"].iloc[0], key=f"n_{prodi_sel}_{k}")
                        
                        if st.button("Simpan Hasil Review", key=f"b_{prodi_sel}_{k}", type="primary"):
                            df_usulan.loc[(df_usulan["Program_Studi"]==prodi_sel) & (df_usulan["Nama_Kegiatan"]==k), ["Status", "Catatan_Fakultas", "Akomodasi_Anggaran"]] = [n_s, n_n, n_a]
                            save_data(df_usulan); st.success(f"Keputusan & Mapping disimpan!"); st.rerun()
                        
                        if sembunyikan_nilai: st.dataframe(df_k[["Rincian_Belanja", "Volume", "Satuan"]].copy(), hide_index=True, use_container_width=True)
                        else: st.dataframe(df_k[["Rincian_Belanja", "Volume", "Satuan", "Harga_Satuan", "Total_Usulan"]].style.format({"Harga_Satuan": format_rupiah, "Total_Usulan": format_rupiah}), hide_index=True, use_container_width=True)

        # ---> ISI TAB INSIGHT (UNTUK KEDUANYA)
        with tab_ins:
            st.subheader("🤖 Analisis & Insight Pintar")
            if not df_usulan.empty:
                if sembunyikan_nilai: st.warning("⚠️ Insight dinonaktifkan di mode sembunyi.")
                else:
                    tot = df_usulan['Total_Usulan'].sum()
                    if tot > 0:
                        st.info(f"💡 **Total anggaran diajukan: Rp {format_rupiah(tot)}**")
                        st.bar_chart(df_usulan.groupby("Program_Studi")["Total_Usulan"].sum().reset_index().set_index("Program_Studi")["Total_Usulan"])
                        status_pivot = pd.crosstab(df_usulan["Program_Studi"], df_usulan["Status"]).reset_index()
                        rekap_detail = df_usulan.groupby("Program_Studi").agg(Total_Anggaran=("Total_Usulan", "sum"), Jumlah_Kegiatan=("Nama_Kegiatan", "nunique")).reset_index()
                        rekap_final = pd.merge(rekap_detail, status_pivot, on="Program_Studi", how="left").fillna(0)
                        for stat in ["Menunggu Review", "Disetujui", "Perlu Revisi", "Ditolak"]:
                            if stat not in rekap_final.columns: rekap_final[stat] = 0
                        rekap_final.rename(columns={"Program_Studi": "Program Studi", "Jumlah_Kegiatan": "Jml Kegiatan", "Total_Anggaran": "Total Anggaran (Rp)"}, inplace=True)
                        st.dataframe(rekap_final[["Program Studi", "Jml Kegiatan", "Menunggu Review", "Disetujui", "Perlu Revisi", "Ditolak", "Total Anggaran (Rp)"]].style.format({"Total Anggaran (Rp)": format_rupiah}), hide_index=True, use_container_width=True)

                st.markdown("---")
                st.markdown("### 📄 Laporan Cetak Hirarki & Excel")
                prodi_ins_sel = st.selectbox("Pilih Program Studi untuk dilihat:", sorted(df_usulan["Program_Studi"].unique()), key="ins_prodi_sel")
                df_ins_p = df_usulan[df_usulan["Program_Studi"] == prodi_ins_sel]
                
                if not df_ins_p.empty:
                    st.dataframe(format_df_ke_hirarki(df_ins_p, hidden=sembunyikan_nilai), hide_index=True, use_container_width=True)
                    
                    col_ex1, col_ex2 = st.columns(2)
                    with col_ex1: st.download_button("📊 Excel: Laporan Prodi", data=generate_excel(format_df_ke_hirarki(df_ins_p, hidden=sembunyikan_nilai), prodi_ins_sel[:30]), file_name=f"Laporan_{prodi_ins_sel}_2026.xlsx", use_container_width=True)
                    with col_ex2: st.download_button("📊 Excel: Laporan Fakultas", data=generate_excel(format_df_ke_hirarki(df_usulan, hidden=sembunyikan_nilai), "Seluruh_Fakultas"), file_name="Laporan_FIB_Semua_2026.xlsx", use_container_width=True)

        # ---> ISI TAB KHUSUS ADMIN 
        if role_user == "admin":
            with tab_hapus:
                st.subheader("🗑️ Hapus Data Rincian")
                if not df_usulan.empty:
                    opsi_hapus = {idx: f"[{row['Program_Studi']}] {row['Nama_Kegiatan']} - {row['Rincian_Belanja']}" for idx, row in df_usulan.iterrows()}
                    sel_h = st.selectbox("Pilih data rincian belanja:", options=list(opsi_hapus.keys()), format_func=lambda x: opsi_hapus[x])
                    if st.button("🚨 Hapus Permanen", type="primary"):
                        df_usulan = df_usulan.drop(index=sel_h).reset_index(drop=True)
                        save_data(df_usulan); st.success("Dihapus!"); st.rerun()

            with tab_restore:
                st.subheader("♻️ Restore Database dari File Cadangan")
                file_cadangan = st.file_uploader("Upload File Backup CSV/Excel Anda di sini", type=["csv", "xlsx"])
                if st.button("🚀 Jalankan Restore Data", type="primary"):
                    if file_cadangan is not None:
                        try:
                            if file_cadangan.name.endswith('.csv'): df_pulih = pd.read_csv(file_cadangan)
                            else: df_pulih = pd.read_excel(file_cadangan)
                            
                            kolom_wajib = ["Program_Studi", "Nama_Kegiatan", "Rincian_Belanja", "Volume", "Satuan", "Harga_Satuan", "Total_Usulan"]
                            if all(k in df_pulih.columns for k in kolom_wajib):
                                if "Tanggal_Input" not in df_pulih.columns: df_pulih["Tanggal_Input"] = "-"
                                if "Prioritas" not in df_pulih.columns: df_pulih["Prioritas"] = "Sedang"
                                if "Status" not in df_pulih.columns: df_pulih["Status"] = "Menunggu Review"
                                if "Catatan_Fakultas" not in df_pulih.columns: df_pulih["Catatan_Fakultas"] = "-"
                                if "File_TOR" not in df_pulih.columns: df_pulih["File_TOR"] = "-"
                                if "Akomodasi_Anggaran" not in df_pulih.columns: df_pulih["Akomodasi_Anggaran"] = "- Belum Ditentukan -"
                                save_data(df_pulih); st.success("🎉 Seluruh data telah berhasil dipulihkan!"); st.rerun()
                            else: st.error("Gagal! Format kolom pada file yang diupload tidak cocok dengan database aplikasi.")
                        except Exception as e: st.error(f"Kesalahan saat membaca file: {e}")

            with tab_log:
                st.subheader("🕵️ CCTV Jejak Audit (Audit Trail)")
                if st.button("🔄 Refresh Data CCTV"): st.rerun()
                try:
                    with engine.connect() as conn:
                        df_logs = pd.read_sql("SELECT * FROM rab_logs ORDER BY \"Waktu\" DESC LIMIT 500", conn)
                    if not df_logs.empty: st.dataframe(df_logs, use_container_width=True, hide_index=True)
                except: st.info("Menunggu aktivitas pertama terekam...")

show_page()
