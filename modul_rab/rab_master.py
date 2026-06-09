import streamlit as st
import pandas as pd
from io import BytesIO
from datetime import datetime
from utils import load_table, save_table, log_audit

st.title("🗂️ Master Database Anggaran")
st.caption("Input Master Data secara manual atau gunakan file Excel untuk backup/restore massal.")

# --- LAZY LOADING DARI UTILS ---
df_m_kro = load_table("rab_m_kro", ["KRO", "Sumber_Dana"])
df_m_ro = load_table("rab_m_ro", ["KRO", "RO", "Sumber_Dana"])
df_m_komp = load_table("rab_m_komp", ["RO", "Komponen", "Sumber_Dana"])
df_m_subkomp = load_table("rab_m_subkomp", ["Komponen", "Sub_Komponen", "Sumber_Dana"])
df_m_akun = load_table("rab_m_akun", ["Sub_Komponen", "Account_Code", "Account_Name", "Sumber_Dana"]) 
df_m_pejabat = load_table("rab_m_pejabat", ["Jabatan", "Nama", "NIP"])

with st.expander("💾 Import & Export Data Master (Excel)", expanded=False):
    c_eks, c_imp = st.columns(2)
    with c_eks:
        st.markdown("**1. Export Data Master**")
        output_master = BytesIO()
        with pd.ExcelWriter(output_master, engine='openpyxl') as writer:
            df_m_kro.to_excel(writer, index=False, sheet_name='KRO')
            df_m_ro.to_excel(writer, index=False, sheet_name='RO')
            df_m_komp.to_excel(writer, index=False, sheet_name='Komponen')
            df_m_subkomp.to_excel(writer, index=False, sheet_name='Sub_Komponen')
            df_m_akun.to_excel(writer, index=False, sheet_name='Akun')
            df_m_pejabat.to_excel(writer, index=False, sheet_name='Pejabat')
        st.download_button(label="📥 Download Backup Master (.xlsx)", data=output_master.getvalue(), file_name=f"Backup_Master_RAB_{datetime.now().strftime('%Y%m%d')}.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", type="primary")
    
    with c_imp:
        st.markdown("**2. Import Data Master**")
        file_master = st.file_uploader("Upload File Backup Excel", type=['xlsx'])
        if st.button("🚀 Jalankan Import", type="primary"):
            if file_master is not None:
                try:
                    xls_master = pd.read_excel(file_master, sheet_name=None)
                    if 'KRO' in xls_master: save_table(xls_master['KRO'], "rab_m_kro")
                    if 'RO' in xls_master: save_table(xls_master['RO'], "rab_m_ro")
                    if 'Komponen' in xls_master: save_table(xls_master['Komponen'], "rab_m_komp")
                    if 'Sub_Komponen' in xls_master: save_table(xls_master['Sub_Komponen'], "rab_m_subkomp")
                    if 'Akun' in xls_master: save_table(xls_master['Akun'], "rab_m_akun")
                    if 'Pejabat' in xls_master: save_table(xls_master['Pejabat'], "rab_m_pejabat")
                    log_audit("IMPORT MASTER", "Melakukan restore master data via Excel")
                    st.success("Data Master berhasil di-import!"); st.rerun()
                except Exception as e: st.error(f"Gagal memproses file: {e}")

sumber_master = st.radio("Pilih Kategori Master yang Ingin Diedit:", ["BOPTN", "PNBP"], horizontal=True)
st.markdown("---")
col_m1, col_m2 = st.columns(2)
with col_m1:
    st.markdown(f"**1. Master KRO ({sumber_master})**")
    df_kro_f = df_m_kro[df_m_kro['Sumber_Dana'] == sumber_master].copy()
    edit_kro = st.data_editor(df_kro_f[["KRO"]], num_rows="dynamic", use_container_width=True, hide_index=True, key="me_kro")
    if st.button("💾 Simpan KRO"): 
        edit_kro['Sumber_Dana'] = sumber_master
        df_sisa = df_m_kro[df_m_kro['Sumber_Dana'] != sumber_master]
        save_table(pd.concat([df_sisa, edit_kro.dropna(subset=["KRO"])]), "rab_m_kro"); st.rerun()
        
    st.markdown(f"**3. Master Komponen ({sumber_master})**")
    df_komp_f = df_m_komp[df_m_komp['Sumber_Dana'] == sumber_master].copy()
    edit_komp = st.data_editor(df_komp_f[["RO", "Komponen"]], num_rows="dynamic", use_container_width=True, hide_index=True, column_config={"RO": st.column_config.SelectboxColumn(options=df_m_ro[df_m_ro['Sumber_Dana'] == sumber_master]["RO"].tolist())}, key="me_komp")
    if st.button("💾 Simpan Komponen"): 
        edit_komp['Sumber_Dana'] = sumber_master
        save_table(pd.concat([df_m_komp[df_m_komp['Sumber_Dana'] != sumber_master], edit_komp.dropna(subset=["Komponen"])]), "rab_m_komp"); st.rerun()

    st.markdown(f"**5. Master Akun Belanja ({sumber_master})**")
    df_akun_f = df_m_akun[df_m_akun['Sumber_Dana'] == sumber_master].copy()
    list_sub = df_m_subkomp[df_m_subkomp['Sumber_Dana'] == sumber_master]["Sub_Komponen"].tolist()
    edit_akun = st.data_editor(df_akun_f[["Sub_Komponen", "Account_Code", "Account_Name"]], num_rows="dynamic", use_container_width=True, hide_index=True, column_config={"Sub_Komponen": st.column_config.SelectboxColumn(options=list_sub if list_sub else ["-"])}, key="me_akun")
    if st.button("💾 Simpan Akun Belanja"): 
        edit_akun['Sumber_Dana'] = sumber_master
        save_table(pd.concat([df_m_akun[df_m_akun['Sumber_Dana'] != sumber_master], edit_akun.dropna(subset=["Account_Code", "Sub_Komponen"])]), "rab_m_akun"); st.rerun()

with col_m2:
    st.markdown(f"**2. Master RO ({sumber_master})**")
    df_ro_f = df_m_ro[df_m_ro['Sumber_Dana'] == sumber_master].copy()
    list_kro = df_m_kro[df_m_kro['Sumber_Dana'] == sumber_master]["KRO"].tolist()
    edit_ro = st.data_editor(df_ro_f[["KRO", "RO"]], num_rows="dynamic", use_container_width=True, hide_index=True, column_config={"KRO": st.column_config.SelectboxColumn(options=list_kro)}, key="me_ro")
    if st.button("💾 Simpan RO"): 
        edit_ro['Sumber_Dana'] = sumber_master
        save_table(pd.concat([df_m_ro[df_m_ro['Sumber_Dana'] != sumber_master], edit_ro.dropna(subset=["RO"])]), "rab_m_ro"); st.rerun()
    
    st.markdown(f"**4. Master Sub-Komponen ({sumber_master})**")
    df_sub_f = df_m_subkomp[df_m_subkomp['Sumber_Dana'] == sumber_master].copy()
    list_komp = df_m_komp[df_m_komp['Sumber_Dana'] == sumber_master]["Komponen"].tolist()
    edit_subkomp = st.data_editor(df_sub_f[["Komponen", "Sub_Komponen"]], num_rows="dynamic", use_container_width=True, hide_index=True, column_config={"Komponen": st.column_config.SelectboxColumn(options=list_komp)}, key="me_subkomp")
    if st.button("💾 Simpan Sub-Komponen"): 
        edit_subkomp['Sumber_Dana'] = sumber_master
        save_table(pd.concat([df_m_subkomp[df_m_subkomp['Sumber_Dana'] != sumber_master], edit_subkomp.dropna(subset=["Sub_Komponen"])]), "rab_m_subkomp"); st.rerun()

    st.markdown("**6. Master Pejabat**")
    edit_pejabat = st.data_editor(df_m_pejabat, num_rows="dynamic", use_container_width=True, hide_index=True, key="me_pej")
    if st.button("💾 Simpan Pejabat"): save_table(edit_pejabat.dropna(how='all'), "rab_m_pejabat"); st.rerun()
