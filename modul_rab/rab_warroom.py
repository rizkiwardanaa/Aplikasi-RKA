import streamlit as st
import pandas as pd
from io import BytesIO
from datetime import datetime
from utils import load_table, get_available_years, format_rupiah, update_rab_tahun, log_audit

st.title("🛠️ War Room: Mode Edit Matrik Revisi")

if 'war_room_drafts' not in st.session_state: st.session_state['war_room_drafts'] = {}
if 'war_room_cats' not in st.session_state: st.session_state['war_room_cats'] = {}
if 'war_room_view' not in st.session_state: st.session_state['war_room_view'] = ""

list_tahun = get_available_years()
tahun_aktif = st.sidebar.selectbox("📅 Pilih Tahun Anggaran Aktif:", list_tahun)

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

unique_kegiatans = sorted(df_rab_utama['Kegiatan'].unique()) if not df_rab_utama.empty else []
kegiatan_code_map = {keg: f"{i+1:04d}" for i, keg in enumerate(unique_kegiatans)}

if df_rab_utama.empty:
    st.warning("Belum ada data untuk tahun aktif ini. Silakan buat RAB terlebih dahulu.")
else:
    col_wr1, col_wr2 = st.columns(2)
    list_v_rapat = sorted(df_rab_utama['Versi_RAB'].unique())
    versi_rapat = col_wr1.selectbox("Pilih Versi yang Akan Disimulasikan:", list_v_rapat)
    sumber_dana_rapat = col_wr2.radio("Sumber Dana:", ["BOPTN", "PNBP"], key="sd_rapat", horizontal=True)

    current_view = f"{versi_rapat}_{sumber_dana_rapat}"
    if st.session_state['war_room_view'] != current_view:
        st.session_state['war_room_drafts'].clear()
        st.session_state['war_room_cats'].clear()
        st.session_state['war_room_view'] = current_view

    df_ur = df_rab_utama[(df_rab_utama['Versi_RAB'] == versi_rapat) & (df_rab_utama['Sumber_Dana'] == sumber_dana_rapat)]
    df_dr = df_rab_detail[df_rab_detail['ID_RAB'].isin(df_ur['ID_RAB'])]
    pagu_awal_db = df_ur['Alokasi'].sum() if not df_ur.empty else 0

    keg_to_id = {row['Kegiatan']: row['ID_RAB'] for _, row in df_ur.iterrows()}
    list_keg_rapat = list(keg_to_id.keys()) if keg_to_id else ["-"]
    
    list_akun_raw = df_m_akun[df_m_akun['Sumber_Dana'] == sumber_dana_rapat]
    list_akun_rapat = (list_akun_raw['Account_Code'].astype(str) + " - " + list_akun_raw['Account_Name']).drop_duplicates().tolist() if not list_akun_raw.empty else ["-"]

    with st.expander("⚡ Suntik Kegiatan Mendadak"):
        with st.form("form_suntik_kegiatan"):
            s_kro = st.selectbox("KRO", df_m_kro[df_m_kro['Sumber_Dana'] == sumber_dana_rapat]['KRO'].tolist() or ["-"])
            s_ro = st.selectbox("RO", df_m_ro[df_m_ro['Sumber_Dana'] == sumber_dana_rapat]['RO'].tolist() if not df_m_ro.empty else ["-"])
            s_komp = st.selectbox("Komponen", df_m_komp[df_m_komp['Sumber_Dana'] == sumber_dana_rapat]['Komponen'].tolist() or ["-"])
            s_sub = st.selectbox("Sub Komponen", df_m_subkomp[df_m_subkomp['Sumber_Dana'] == sumber_dana_rapat]['Sub_Komponen'].tolist() or ["-"])
            s_keg = st.text_input("Nama Kegiatan Baru")
            
            if st.form_submit_button("Suntik Kegiatan"):
                if s_keg:
                    new_id = f"RAB-{datetime.now().strftime('%Y%m%d%H%M%S')}"
                    dt_pjb = df_m_pejabat.iloc[0] if not df_m_pejabat.empty else {"Jabatan":"-", "Nama":"-", "NIP":"-"}
                    new_u = pd.DataFrame([{
                        "ID_RAB": new_id, "Tanggal": datetime.now().strftime('%Y-%m-%d %H:%M'), "Tahun": tahun_aktif, "Tgl_Cetak": datetime.now().strftime('%Y-%m-%d'),
                        "Sumber_Dana": sumber_dana_rapat, "KRO": s_kro, "RO": s_ro, "Komponen": s_komp, "Sub_Komponen": s_sub,
                        "Kegiatan": s_keg.strip(), "Sasaran": "-", "Volume": 1, "Satuan": "Layanan", "Alokasi": 0,
                        "Jabatan": dt_pjb['Jabatan'], "Nama_Pejabat": dt_pjb['Nama'], "NIP_Pejabat": dt_pjb['NIP'],
                        "Versi_RAB": versi_rapat, "Is_Active": 0, "Catatan": "-"
                    }])
                    df_rab_utama = pd.concat([df_rab_utama, new_u], ignore_index=True)
                    update_rab_tahun(df_rab_utama, df_rab_detail, tahun_aktif)
                    log_audit("SUNTIK KEGIATAN", f"Menambahkan '{s_keg.strip()}' di versi '{versi_rapat}'")
                    st.success("Tersuntik!"); st.rerun()

    st.markdown("---")
    
    if df_ur.empty:
        st.info("Belum ada kegiatan.")
    else:
        hud_placeholder = st.empty()
        df_ur_sorted = df_ur.sort_values(by=['KRO', 'RO', 'Komponen', 'Sub_Komponen', 'Kegiatan'])
        
        all_valid_edits = []
        all_catatan_dict = {}
        pagu_live = 0
        c_kro, c_ro, c_komp, c_sub = "", "", "", ""

        for _, row_keg in df_ur_sorted.iterrows():
            if row_keg['KRO'] != c_kro: st.markdown(f"<div style='background-color:#d9e1f2; padding:8px; font-weight:bold; margin-top:15px; border-radius:4px;'>🟦 {row_keg['KRO']}</div>", unsafe_allow_html=True); c_kro = row_keg['KRO']; c_ro = ""
            if row_keg['RO'] != c_ro: st.markdown(f"<div style='background-color:#e9edf4; padding:6px; font-weight:bold; margin-left:15px;'>💠 {row_keg['RO']}</div>", unsafe_allow_html=True); c_ro = row_keg['RO']; c_komp = ""
            if row_keg['Komponen'] != c_komp: st.markdown(f"<div style='background-color:#fff2cc; padding:6px; font-weight:bold; margin-left:30px;'>🟨 {row_keg['Komponen']}</div>", unsafe_allow_html=True); c_komp = row_keg['Komponen']; c_sub = ""
            if row_keg['Sub_Komponen'] != c_sub and str(row_keg['Sub_Komponen']).strip() not in ["", "-"]: st.markdown(f"<div style='background-color:#fce4d6; padding:6px; font-weight:bold; margin-left:45px;'>🟧 {row_keg['Sub_Komponen']}</div>", unsafe_allow_html=True); c_sub = row_keg['Sub_Komponen']

            keg_id = row_keg['ID_RAB']; keg_name = row_keg['Kegiatan']
            keg_code = kegiatan_code_map.get(keg_name, "0000")
            df_det_keg = df_dr[df_dr['ID_RAB'] == keg_id].copy()
            df_det_keg['Target_Kegiatan'] = keg_name 
            keg_total_awal = df_det_keg.get('Total_Biaya', pd.Series([0])).sum()
            
            if keg_id not in st.session_state['war_room_drafts']:
                df_edit_view = df_det_keg[['Target_Kegiatan', 'Akun_Belanja', 'Uraian', 'Vol_1', 'Sat_1', 'Vol_2', 'Sat_2', 'Harga_Satuan']].copy()
                if df_edit_view.empty: df_edit_view = pd.DataFrame([{"Target_Kegiatan": keg_name, "Akun_Belanja": list_akun_rapat[0] if list_akun_rapat else "-", "Uraian": "", "Vol_1": 1, "Sat_1": "Unit", "Vol_2": 1, "Sat_2": "-", "Harga_Satuan": 0}])
                df_edit_view['Harga_Satuan'] = pd.to_numeric(df_edit_view['Harga_Satuan'], errors='coerce').fillna(0).astype(int)
                df_edit_view['Vol_1'] = pd.to_numeric(df_edit_view['Vol_1'], errors='coerce').fillna(1).astype(int)
                df_edit_view['Vol_2'] = pd.to_numeric(df_edit_view['Vol_2'], errors='coerce').fillna(1).astype(int)
                st.session_state['war_room_drafts'][keg_id] = df_edit_view

            if keg_id not in st.session_state['war_room_cats']:
                cat_val = str(row_keg.get('Catatan', '-'))
                st.session_state['war_room_cats'][keg_id] = cat_val if cat_val and cat_val.lower() != 'nan' else "-"

            with st.expander(f"🟢 KEGIATAN: {keg_code} - {keg_name.title()} (Rp {format_rupiah(keg_total_awal)})", expanded=True):
                cat_input = st.text_input("📝 Catatan Revisi:", value=st.session_state['war_room_cats'][keg_id], key=f"cat_{keg_id}")
                st.session_state['war_room_cats'][keg_id] = cat_input.strip() if cat_input.strip() else "-"
                all_catatan_dict[keg_id] = st.session_state['war_room_cats'][keg_id]
                
                edited_keg = st.data_editor(
                    st.session_state['war_room_drafts'][keg_id], num_rows="dynamic", use_container_width=True, key=f"ed_{keg_id}",
                    column_config={
                        "Target_Kegiatan": st.column_config.SelectboxColumn("Kegiatan", options=list_keg_rapat, required=True),
                        "Akun_Belanja": st.column_config.SelectboxColumn("Akun Belanja", options=list_akun_rapat, required=True),
                        "Uraian": st.column_config.TextColumn("Detail", required=True),
                        "Vol_1": st.column_config.NumberColumn("Vol 1", min_value=0, step=1, format="%d"),
                        "Sat_1": st.column_config.TextColumn("Sat 1"),
                        "Vol_2": st.column_config.NumberColumn("Vol 2", min_value=0, step=1, format="%d"),
                        "Sat_2": st.column_config.TextColumn("Sat 2"),
                        "Harga_Satuan": st.column_config.NumberColumn("Harga Satuan", min_value=0, step=50000, format="%,.0f")
                    }
                )
                st.session_state['war_room_drafts'][keg_id] = edited_keg.copy()
                edited_keg['Vol_1'] = pd.to_numeric(edited_keg['Vol_1']).fillna(1)
                edited_keg['Vol_2'] = pd.to_numeric(edited_keg['Vol_2']).fillna(1)
                edited_keg.loc[edited_keg['Vol_2'] == 0, 'Vol_2'] = 1 
                edited_keg['Harga_Satuan'] = pd.to_numeric(edited_keg['Harga_Satuan']).fillna(0)
                
                keg_total = (edited_keg['Vol_1'] * edited_keg['Vol_2'] * edited_keg['Harga_Satuan']).sum()
                pagu_live += keg_total
                st.caption(f"**Total Anggaran Kegiatan Ini: Rp {format_rupiah(keg_total)}**")
                all_valid_edits.append(edited_keg)

        with hud_placeholder.container():
            col_h1, col_h2, col_h3 = st.columns(3)
            pagu_awal_input = col_h1.number_input("Pagu Awal Versi", value=int(pagu_awal_db), step=1000000)
            col_h2.metric("Total Draf Saat Ini", f"Rp {format_rupiah(pagu_live)}")
            selisih_dana = pagu_awal_input - pagu_live
            col_h3.metric("Keranjang Sisa Dana" if selisih_dana >= 0 else "🚨 OVER BUDGET", f"Rp {format_rupiah(selisih_dana)}")

        col_act1, col_act2 = st.columns([1, 1])
        with col_act1:
            if st.button("💾 Ketok Palu: Simpan Hasil Revisi ke Database", type="primary", use_container_width=True):
                edited_df_all = pd.concat(all_valid_edits)
                valid_edits = edited_df_all[edited_df_all['Uraian'].str.strip() != ""].copy()
                valid_edits['ID_RAB'] = valid_edits['Target_Kegiatan'].map(keg_to_id)
                valid_edits = valid_edits.dropna(subset=['ID_RAB'])
                valid_edits['Total_Biaya'] = valid_edits['Vol_1'] * valid_edits['Vol_2'] * valid_edits['Harga_Satuan']
                
                df_rab_detail = df_rab_detail[~df_rab_detail['ID_RAB'].isin(keg_to_id.values())]
                new_detail = valid_edits[['ID_RAB', 'Akun_Belanja', 'Uraian', 'Vol_1', 'Sat_1', 'Vol_2', 'Sat_2', 'Harga_Satuan', 'Total_Biaya']]
                df_rab_detail = pd.concat([df_rab_detail, new_detail], ignore_index=True)
                
                new_alokasi = valid_edits.groupby('ID_RAB')['Total_Biaya'].sum()
                for id_r in keg_to_id.values():
                    df_rab_utama.loc[df_rab_utama['ID_RAB'] == id_r, 'Alokasi'] = new_alokasi.get(id_r, 0)
                    df_rab_utama.loc[df_rab_utama['ID_RAB'] == id_r, 'Catatan'] = all_catatan_dict.get(id_r, "-")
                    
                if update_rab_tahun(df_rab_utama, df_rab_detail, tahun_aktif):
                    log_audit("KETOK PALU REVISI", f"Menyimpan draf War Room untuk versi '{versi_rapat}'. Total: Rp {format_rupiah(pagu_live)}")
                    st.session_state['war_room_drafts'].clear()
                    st.session_state['war_room_cats'].clear()
                    st.success("Perubahan & Catatan berhasil diketok palu!"); st.rerun()

        with col_act2:
            if len(all_valid_edits) > 0:
                df_backup = pd.concat(all_valid_edits)
                valid_backup = df_backup[df_backup['Uraian'].str.strip() != ""].copy()
                if not valid_backup.empty:
                    output_backup = BytesIO()
                    with pd.ExcelWriter(output_backup, engine='openpyxl') as writer: valid_backup.to_excel(writer, index=False)
                    st.download_button("📥 Download Draf Backup (Excel)", data=output_backup.getvalue(), file_name=f"Backup_WarRoom_{versi_rapat}_{sumber_dana_rapat}.xlsx", use_container_width=True)
