import streamlit as st
import pandas as pd
from datetime import datetime
from utils import load_table, get_available_years, split_kode, format_rupiah, save_table, update_rab_tahun, log_audit

st.title("📝 Buat / Edit Kegiatan RAB")

list_tahun = get_available_years()
tahun_aktif = st.sidebar.selectbox("📅 Pilih Tahun Anggaran Aktif:", list_tahun)

# --- LAZY LOADING ---
df_m_kro = load_table("rab_m_kro", ["KRO", "Sumber_Dana"])
df_m_ro = load_table("rab_m_ro", ["KRO", "RO", "Sumber_Dana"])
df_m_komp = load_table("rab_m_komp", ["RO", "Komponen", "Sumber_Dana"])
df_m_subkomp = load_table("rab_m_subkomp", ["Komponen", "Sub_Komponen", "Sumber_Dana"])
df_m_akun = load_table("rab_m_akun", ["Sub_Komponen", "Account_Code", "Account_Name", "Sumber_Dana"]) 
df_m_pejabat = load_table("rab_m_pejabat", ["Jabatan", "Nama", "NIP"])

df_rab_utama = load_table("rab_utama", ["ID_RAB", "Tanggal", "Tahun", "Tgl_Cetak", "Sumber_Dana", "KRO", "RO", "Komponen", "Sub_Komponen", "Kegiatan", "Sasaran", "Volume", "Satuan", "Alokasi", "Jabatan", "Nama_Pejabat", "NIP_Pejabat", "Versi_RAB", "Is_Active", "Catatan"], f"WHERE \"Tahun\" = '{tahun_aktif}'")

if not df_rab_utama.empty:
    ids = tuple(df_rab_utama['ID_RAB'].tolist())
    where_det = f"WHERE \"ID_RAB\" = '{ids[0]}'" if len(ids) == 1 else f"WHERE \"ID_RAB\" IN {ids}"
    df_rab_detail = load_table("rab_detail", ["ID_RAB", "Akun_Belanja", "Uraian", "Vol_1", "Sat_1", "Vol_2", "Sat_2", "Harga_Satuan", "Total_Biaya"], where_det)
else:
    df_rab_detail = pd.DataFrame(columns=["ID_RAB", "Akun_Belanja", "Uraian", "Vol_1", "Sat_1", "Vol_2", "Sat_2", "Harga_Satuan", "Total_Biaya"])

if 'edit_rab_id' not in st.session_state: st.session_state.edit_rab_id = None

is_edit_mode = st.session_state.edit_rab_id is not None
df_edit_head = pd.DataFrame()
df_edit_det = pd.DataFrame()

if is_edit_mode:
    st.info("✏️ **MODE REVISI:** Anda sedang mengedit/merevisi kegiatan. Data lama akan dimuat ke formulir.")
    if st.button("❌ Batal Edit (Kembali Buat Baru)"):
        st.session_state.edit_rab_id = None; st.rerun()
        
    df_edit_head = df_rab_utama[df_rab_utama['ID_RAB'] == st.session_state.edit_rab_id]
    df_edit_det = df_rab_detail[df_rab_detail['ID_RAB'] == st.session_state.edit_rab_id]

def_sumber = df_edit_head['Sumber_Dana'].iloc[0] if not df_edit_head.empty else "BOPTN"
def_kro = df_edit_head['KRO'].iloc[0] if not df_edit_head.empty else None
def_ro = df_edit_head['RO'].iloc[0] if not df_edit_head.empty else None
def_komp = df_edit_head['Komponen'].iloc[0] if not df_edit_head.empty else None
def_subkomp = df_edit_head['Sub_Komponen'].iloc[0] if not df_edit_head.empty else None
def_keg = df_edit_head['Kegiatan'].iloc[0] if not df_edit_head.empty else ""
def_sasaran = df_edit_head['Sasaran'].iloc[0] if not df_edit_head.empty else ""
def_vol = df_edit_head['Volume'].iloc[0] if not df_edit_head.empty else 1
def_sat = df_edit_head['Satuan'].iloc[0] if not df_edit_head.empty else ""
def_versi = df_edit_head['Versi_RAB'].iloc[0] if not df_edit_head.empty else "Indikatif"

sumber_buat = st.radio("Pilih Sumber Dana RAB:", ["BOPTN", "PNBP"], index=["BOPTN", "PNBP"].index(def_sumber), horizontal=True, key="rb_buat")
st.markdown("---")

if df_m_kro.empty or df_m_ro.empty or df_m_komp.empty or df_m_akun.empty:
    st.warning("⚠️ Master Database masih kosong! Silakan isi Master Data terlebih dahulu.")
else:
    with st.container(border=True):
        st.subheader("1. Klasifikasi Output RAB")
        col_c1, col_c2 = st.columns(2)
        opsi_kro = df_m_kro[df_m_kro['Sumber_Dana'] == sumber_buat]["KRO"].tolist()
        idx_kro = opsi_kro.index(def_kro) if def_kro in opsi_kro else 0
        pilih_kro = col_c1.selectbox("Pilih KRO", opsi_kro if opsi_kro else ["-"], index=idx_kro)
        
        opsi_ro = df_m_ro[(df_m_ro['Sumber_Dana'] == sumber_buat) & (df_m_ro['KRO'] == pilih_kro)]["RO"].tolist()
        idx_ro = opsi_ro.index(def_ro) if def_ro in opsi_ro else 0
        pilih_ro = col_c2.selectbox("Pilih RO", opsi_ro if opsi_ro else ["-"], index=idx_ro)
        
        col_c3, col_c4 = st.columns(2)
        opsi_komp = df_m_komp[(df_m_komp['Sumber_Dana'] == sumber_buat) & (df_m_komp['RO'] == pilih_ro)]["Komponen"].tolist()
        idx_komp = opsi_komp.index(def_komp) if def_komp in opsi_komp else 0
        pilih_komp = col_c3.selectbox("Pilih Komponen", opsi_komp if opsi_komp else ["-"], index=idx_komp)
        
        opsi_subkomp = df_m_subkomp[(df_m_subkomp['Sumber_Dana'] == sumber_buat) & (df_m_subkomp['Komponen'] == pilih_komp)]["Sub_Komponen"].tolist()
        idx_subkomp = opsi_subkomp.index(def_subkomp) if def_subkomp in opsi_subkomp else 0
        pilih_subkomp = col_c4.selectbox("Pilih Sub-Komponen", opsi_subkomp if opsi_subkomp else ["-"], index=idx_subkomp)

    with st.container(border=True):
        st.subheader("2. Informasi Utama Kegiatan")
        col_u1, col_u2 = st.columns(2)
        rab_kegiatan = col_u1.text_input("Nama Kegiatan", value=def_keg, placeholder="Contoh: Pengadaan Peralatan Podcast")
        
        if not def_sasaran:
            _, kro_narasi = split_kode(pilih_kro) if pilih_kro else ("", "")
            def_sasaran = f"Peningkatan {kro_narasi.strip('() ')}" if kro_narasi else ""
        
        rab_sasaran = col_u2.text_input("Sasaran Kegiatan", value=def_sasaran)
        rab_vol = col_u1.number_input("Volume Target", value=int(def_vol), min_value=1)
        rab_satuan = col_u2.text_input("Satuan Ukur", value=def_sat, placeholder="Contoh: Layanan / Bulan")
        
        rab_tahun = col_u1.text_input("Tahun Anggaran", value=tahun_aktif, disabled=True)
        list_versi = ["Transisi","Indikatif", "Definitif", "Revisi 1", "Revisi 2", "Revisi 3", "Revisi 4", "Revisi 5", "Revisi 6", "Revisi 7", "Revisi 8", "Revisi 9", "Revisi 10","Revisi 11","Revisi 12","Revisi 13"]
        idx_versi = list_versi.index(def_versi) if def_versi in list_versi else 0
        rab_versi = col_u2.selectbox("Versi Anggaran (Periode)", list_versi, index=idx_versi)

        def_catatan = df_edit_head.get('Catatan', pd.Series(['-'])).iloc[0] if not df_edit_head.empty else "-"
        rab_catatan = st.text_input("📝 Catatan Revisi Khusus Kegiatan Ini", value=def_catatan)
        if not rab_catatan.strip(): rab_catatan = "-"

    with st.container(border=True):
        st.subheader("3. Rincian Belanja")
        df_akun_f = df_m_akun[(df_m_akun['Sumber_Dana'] == sumber_buat) & (df_m_akun['Sub_Komponen'] == pilih_subkomp)]
        opsi_akun = [f"{row['Account_Code']} - {row['Account_Name']}" for _, row in df_akun_f.iterrows()]
        if not opsi_akun: 
            opsi_akun = ["- Tidak ada akun terpetakan -"]
        else:
            opsi_akun = list(dict.fromkeys(opsi_akun))
        
        if is_edit_mode and not df_edit_det.empty:
            df_det_edit = df_edit_det.rename(columns={"Akun_Belanja":"Akun Belanja", "Uraian":"Uraian Belanja", "Vol_1":"Vol 1", "Sat_1":"Sat 1", "Vol_2":"Vol 2", "Sat_2":"Sat 2", "Harga_Satuan":"Harga Satuan"})
            df_det_edit = df_det_edit[["Akun Belanja", "Uraian Belanja", "Vol 1", "Sat 1", "Vol 2", "Sat 2", "Harga Satuan"]]
        else:
            df_det_edit = pd.DataFrame([{"Akun Belanja": opsi_akun[0], "Uraian Belanja": "", "Vol 1": 1, "Sat 1": "Unit", "Vol 2": 1, "Sat 2": "-", "Harga Satuan": 0}])
        
        df_det_edit['Harga Satuan'] = pd.to_numeric(df_det_edit['Harga Satuan'], errors='coerce').fillna(0).astype(int)
        df_det_edit['Vol 1'] = pd.to_numeric(df_det_edit['Vol 1'], errors='coerce').fillna(1).astype(int)
        df_det_edit['Vol 2'] = pd.to_numeric(df_det_edit['Vol 2'], errors='coerce').fillna(1).astype(int)
        
        df_input_detail = st.data_editor(
            df_det_edit, num_rows="dynamic", use_container_width=True, hide_index=True, key="grid_buat_rab",
            column_config={
                "Akun Belanja": st.column_config.SelectboxColumn("Akun Belanja", options=opsi_akun, required=True),
                "Uraian Belanja": st.column_config.TextColumn("Detail / Uraian", required=True),
                "Vol 1": st.column_config.NumberColumn("Vol 1", min_value=1, step=1, required=True, format="%d"),
                "Sat 1": st.column_config.TextColumn("Sat 1", required=True),
                "Vol 2": st.column_config.NumberColumn("Vol 2", min_value=0, step=1, format="%d"),
                "Sat 2": st.column_config.TextColumn("Sat 2 (Biarkan '-' jika tak ada)"),
                "Harga Satuan": st.column_config.NumberColumn("Harga Satuan (Rp)", min_value=0, step=10000, required=True, format="%,.0f")
            }
        )

        df_input_detail["Vol_1_Num"] = pd.to_numeric(df_input_detail["Vol 1"]).fillna(1)
        df_input_detail["Vol_2_Num"] = pd.to_numeric(df_input_detail["Vol 2"]).fillna(1)
        df_input_detail.loc[df_input_detail["Vol_2_Num"] == 0, "Vol_2_Num"] = 1
        df_input_detail["Harga_Num"] = pd.to_numeric(df_input_detail["Harga Satuan"]).fillna(0)
        total_rab_live = (df_input_detail["Vol_1_Num"] * df_input_detail["Vol_2_Num"] * df_input_detail["Harga_Num"]).sum()
        
        c_pagu1, c_pagu2 = st.columns(2)
        is_pagu_locked = c_pagu1.checkbox("🔒 Aktifkan Kunci Pagu Maksimal (Opsional)")
        batas_pagu = c_pagu2.number_input("Batas Pagu (Rp)", min_value=0, value=int(total_rab_live)) if is_pagu_locked else 0
        
        st.markdown("#### 💰 Akumulasi Anggaran Alokasi Dana")
        if is_pagu_locked and total_rab_live > batas_pagu:
            st.error(f"Total Anggaran (Rp {format_rupiah(total_rab_live)}) MELEBIHI Batas Pagu (Rp {format_rupiah(batas_pagu)})!")
        else:
            st.metric(f"Total Alokasi Dana ({sumber_buat})", f"Rp {format_rupiah(total_rab_live)}")

    with st.container(border=True):
        st.subheader("4. Pengesahan & Simpan")
        col_p1, col_p2 = st.columns(2)
        opsi_pejabat = {idx: f"{row['Jabatan']} - {row['Nama']}" for idx, row in df_m_pejabat.iterrows()}
        pilih_pejabat = col_p1.selectbox("Pilih Pejabat Penandatangan", options=list(opsi_pejabat.keys()), format_func=lambda x: opsi_pejabat[x]) if opsi_pejabat else None
        tgl_cetak = col_p2.date_input("Tanggal Dokumen Cetak")
        
        if st.button("💾 Simpan RAB", type="primary"):
            valid_detail = df_input_detail[df_input_detail["Uraian Belanja"].str.strip() != ""].copy()
            if is_pagu_locked and total_rab_live > batas_pagu:
                st.error("Gagal! Total rincian melebihi batas Pagu yang Anda kunci.")
            elif not rab_kegiatan or valid_detail.empty or pilih_pejabat is None:
                st.error("Gagal! Pastikan Nama Kegiatan, Rincian, dan Pejabat sudah terisi.")
            else:
                if is_edit_mode and def_versi == rab_versi:
                    df_rab_utama = df_rab_utama[df_rab_utama["ID_RAB"] != st.session_state.edit_rab_id]
                    df_rab_detail = df_rab_detail[df_rab_detail["ID_RAB"] != st.session_state.edit_rab_id]
                    
                id_rab_baru = f"RAB-{datetime.now().strftime('%Y%m%d%H%M%S')}"
                dt_pjb = df_m_pejabat.loc[pilih_pejabat]
                
                active_vs = df_rab_utama[(df_rab_utama['Is_Active'] == 1)]['Versi_RAB'].unique()
                is_act = 1 if len(active_vs) == 0 or rab_versi in active_vs else 0

                new_utama = pd.DataFrame([{
                    "ID_RAB": id_rab_baru, "Tanggal": datetime.now().strftime('%Y-%m-%d %H:%M'), "Tahun": tahun_aktif, "Tgl_Cetak": str(tgl_cetak),
                    "Sumber_Dana": sumber_buat, "KRO": pilih_kro, "RO": pilih_ro, "Komponen": pilih_komp, "Sub_Komponen": pilih_subkomp,
                    "Kegiatan": rab_kegiatan.strip(), "Sasaran": rab_sasaran, "Volume": rab_vol, "Satuan": rab_satuan, "Alokasi": total_rab_live,
                    "Jabatan": dt_pjb['Jabatan'], "Nama_Pejabat": dt_pjb['Nama'], "NIP_Pejabat": dt_pjb['NIP'],
                    "Versi_RAB": rab_versi, "Is_Active": is_act, "Catatan": rab_catatan
                }])
                df_rab_utama = pd.concat([df_rab_utama, new_utama], ignore_index=True)
                
                valid_detail["ID_RAB"] = id_rab_baru
                valid_detail["Total_Biaya"] = valid_detail["Vol_1_Num"] * valid_detail["Vol_2_Num"] * valid_detail["Harga_Num"]
                valid_detail.rename(columns={"Akun Belanja": "Akun_Belanja", "Uraian Belanja": "Uraian", "Vol 1":"Vol_1", "Sat 1":"Sat_1", "Vol 2":"Vol_2", "Sat 2":"Sat_2", "Harga Satuan": "Harga_Satuan"}, inplace=True)
                df_rab_detail = pd.concat([df_rab_detail, valid_detail[["ID_RAB", "Akun_Belanja", "Uraian", "Vol_1", "Sat_1", "Vol_2", "Sat_2", "Harga_Satuan", "Total_Biaya"]]], ignore_index=True)
                
                save_success = update_rab_tahun(df_rab_utama, df_rab_detail, tahun_aktif)
                
                if save_success:
                    log_audit("BUAT/EDIT RAB", f"Menyimpan kegiatan '{rab_kegiatan.title()}' untuk Versi '{rab_versi}' ({sumber_buat}) dengan Pagu Rp {format_rupiah(total_rab_live)}")
                    st.session_state.edit_rab_id = None
                    st.success(f"✅ RAB '{rab_kegiatan.title()}' Versi '{rab_versi}' Tersimpan!"); st.rerun()
