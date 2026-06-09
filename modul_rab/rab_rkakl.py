import streamlit as st
import pandas as pd
from datetime import datetime
import streamlit.components.v1 as components
from utils import load_table, get_available_years, split_kode, get_vol_sat_combined, format_rupiah, format_tgl_indo

st.title("📊 Buku Rekapitulasi (RKAKL) Aktif")

list_tahun = get_available_years()
tahun_aktif = st.sidebar.selectbox("📅 Pilih Tahun Anggaran Aktif:", list_tahun)

df_rab_utama = load_table("rab_utama", ["ID_RAB", "Tanggal", "Tahun", "Tgl_Cetak", "Sumber_Dana", "KRO", "RO", "Komponen", "Sub_Komponen", "Kegiatan", "Sasaran", "Volume", "Satuan", "Alokasi", "Jabatan", "Nama_Pejabat", "NIP_Pejabat", "Versi_RAB", "Is_Active", "Catatan"], f"WHERE \"Tahun\" = '{tahun_aktif}'")

if not df_rab_utama.empty:
    ids = tuple(df_rab_utama['ID_RAB'].tolist())
    where_det = f"WHERE \"ID_RAB\" = '{ids[0]}'" if len(ids) == 1 else f"WHERE \"ID_RAB\" IN {ids}"
    df_rab_detail = load_table("rab_detail", ["ID_RAB", "Akun_Belanja", "Uraian", "Vol_1", "Sat_1", "Vol_2", "Sat_2", "Harga_Satuan", "Total_Biaya"], where_det)
else:
    df_rab_detail = pd.DataFrame(columns=["ID_RAB", "Akun_Belanja", "Uraian", "Vol_1", "Sat_1", "Vol_2", "Sat_2", "Harga_Satuan", "Total_Biaya"])

unique_kegiatans = sorted(df_rab_utama['Kegiatan'].unique()) if not df_rab_utama.empty else []
kegiatan_code_map = {keg: f"{i+1:04d}" for i, keg in enumerate(unique_kegiatans)}

def generate_rkakl_html(df_utama, df_detail, kegiatan_code_map, tahun, tgl_cetak, nama_dekan, nip_dekan, sumber_dana, tampilkan_paraf=False):
    if df_utama.empty: return f"<h3>Belum ada data RAB aktif untuk sumber dana {sumber_dana}.</h3>"
    
    total_semua = df_detail[df_detail['ID_RAB'].isin(df_utama['ID_RAB'])]['Total_Biaya'].sum()
    paraf_html = ""
    if tampilkan_paraf:
        paraf_html = """
        <table style="width: 320px; border-collapse: collapse; float: left; margin-top: 20px; font-size: 8pt;">
            <tr><th style="border: 1px solid black; padding: 4px; text-align: center; width: 10%;">No</th><th style="border: 1px solid black; padding: 4px; text-align: center; width: 65%;">Jabatan</th><th style="border: 1px solid black; padding: 4px; text-align: center; width: 25%;">Paraf</th></tr>
            <tr><td style="border: 1px solid black; height: 35px; text-align: center;">1</td><td style="border: 1px solid black; padding-left: 5px;">Wakil Dekan Bidang Keuangan dan Umum</td><td style="border: 1px solid black;"></td></tr>
            <tr><td style="border: 1px solid black; height: 35px; text-align: center;">2</td><td style="border: 1px solid black; padding-left: 5px;">Kepala Bagian Umum</td><td style="border: 1px solid black;"></td></tr>
            <tr><td style="border: 1px solid black; height: 35px; text-align: center;">3</td><td style="border: 1px solid black; padding-left: 5px;">Staf Perencanaan</td><td style="border: 1px solid black;"></td></tr>
        </table>
        """

    html = f"""<!DOCTYPE html><html><head><meta charset="utf-8"><style>@page {{ size: A4 portrait; margin: 10mm; }} body {{ font-family: 'Arial', sans-serif; font-size: 7.5pt; line-height: 1.2; color: #000; }} .center {{ text-align: center; }} .right {{ text-align: right; }} .bold {{ font-weight: bold; }} .tabel-utama {{ width: 100%; border-collapse: collapse; margin-top: 5px; font-size: 7.5pt; }} .tabel-utama th, .tabel-utama td {{ border: 1px solid black; padding: 4px 5px; vertical-align: top; }} .tabel-utama th {{ background-color: #d9d9d9; text-align: center; font-weight: bold; }} .tabel-meta {{ width: 100%; border: none; font-size: 8.5pt; margin-bottom: 10px; }} .tabel-meta td {{ padding: 2px; }} .kro-row {{ background-color: #d9e1f2; }} .ro-row {{ background-color: #e9edf4; }} .komp-row {{ background-color: #fff2cc; }} .sub-row {{ background-color: #fce4d6; }} .keg-row {{ background-color: #e2efda; }} .ttd-box {{ width: 220px; float: right; text-align: left; margin-top: 20px; margin-right: 15px; page-break-inside: avoid; }}</style></head><body>
    <h3 class="center" style="margin-bottom:2px;">LAPORAN RENCANA KERJA DAN ANGGARAN (RKAKL)</h3>
    <h4 class="center" style="margin-top:0px; margin-bottom:15px;">TAHUN ANGGARAN {tahun}</h4>
    <table class="tabel-meta">
        <tr><td width="15%" class="bold">KEMENTERIAN</td><td width="2%">:</td><td>(023) KEMENTERIAN PENDIDIKAN, KEBUDAYAAN, RISET DAN TEKNOLOGI</td></tr>
        <tr><td class="bold">SATUAN KERJA</td><td>:</td><td>(677567) UNIVERSITAS MULAWARMAN</td></tr>
        <tr><td class="bold">PROVINSI</td><td>:</td><td>KALIMANTAN TIMUR</td></tr>
        <tr><td class="bold">KOTA</td><td>:</td><td>KOTA SAMARINDA</td></tr>
        <tr><td class="bold">UNIT KERJA</td><td>:</td><td>Fakultas Ilmu Budaya</td></tr>
        <tr><td class="bold">SUMBER DANA</td><td>:</td><td class="bold">{sumber_dana}</td></tr>
        <tr><td class="bold">ALOKASI</td><td>:</td><td class="bold">Rp. {format_rupiah(total_semua)}</td></tr>
    </table>
    <table class="tabel-utama"><tr><th width="10%">KODE</th><th width="45%">PROGRAM / KEGIATAN / OUTPUT / SUBOUTPUT /<br>KOMPONEN / SUBKOMP / JUDUL KEGIATAN / AKUN / DETIL</th><th width="15%">VOL</th><th width="15%">HARGA SATUAN</th><th width="15%">JUMLAH BIAYA</th></tr>
    """
    for kro, g_kro in df_utama.groupby('KRO'):
        k_kro, n_kro = split_kode(kro)
        tot_kro = df_detail[df_detail['ID_RAB'].isin(g_kro['ID_RAB'])]['Total_Biaya'].sum()
        html += f"<tr class='kro-row bold'><td>{k_kro}</td><td>{n_kro}</td><td></td><td></td><td class='right'>{format_rupiah(tot_kro)}</td></tr>"
        for ro, g_ro in g_kro.groupby('RO'):
            k_ro, n_ro = split_kode(ro)
            tot_ro = df_detail[df_detail['ID_RAB'].isin(g_ro['ID_RAB'])]['Total_Biaya'].sum()
            html += f"<tr class='ro-row bold'><td>{k_ro}</td><td>{n_ro}</td><td></td><td></td><td class='right'>{format_rupiah(tot_ro)}</td></tr>"
            for komp, g_komp in g_ro.groupby('Komponen'):
                k_komp, n_komp = split_kode(komp)
                tot_komp = df_detail[df_detail['ID_RAB'].isin(g_komp['ID_RAB'])]['Total_Biaya'].sum()
                html += f"<tr class='komp-row bold'><td>{k_komp}</td><td>{n_komp}</td><td></td><td></td><td class='right'>{format_rupiah(tot_komp)}</td></tr>"
                for sub, g_sub in g_komp.groupby('Sub_Komponen'):
                    if sub and sub != "-":
                        k_sub, n_sub = split_kode(sub)
                        tot_sub = df_detail[df_detail['ID_RAB'].isin(g_sub['ID_RAB'])]['Total_Biaya'].sum()
                        html += f"<tr class='sub-row bold'><td>{k_sub}</td><td>{n_sub}</td><td></td><td></td><td class='right'>{format_rupiah(tot_sub)}</td></tr>"
                    for keg, g_keg in g_sub.groupby('Kegiatan'):
                        keg_code = kegiatan_code_map.get(keg, "0000"); keg_title = keg.title() 
                        tot_keg = df_detail[df_detail['ID_RAB'].isin(g_keg['ID_RAB'])]['Total_Biaya'].sum()
                        html += f"<tr class='keg-row bold'><td>{keg_code}</td><td style='padding-left:10px;'>{keg_title}</td><td></td><td></td><td class='right'>{format_rupiah(tot_keg)}</td></tr>"
                        for akun, g_akun in df_detail[df_detail['ID_RAB'].isin(g_keg['ID_RAB'])].groupby('Akun_Belanja'):
                            k_akun, n_akun = split_kode(akun)
                            html += f"<tr class='bold'><td>{k_akun}</td><td style='padding-left:20px;'>{n_akun}</td><td></td><td></td><td class='right'>{format_rupiah(g_akun['Total_Biaya'].sum())}</td></tr>"
                            for _, det in g_akun.iterrows():
                                v_sat = get_vol_sat_combined(det['Vol_1'], det['Sat_1'], det['Vol_2'], det['Sat_2'])
                                html += f"<tr><td></td><td style='padding-left:30px;'>- {det['Uraian']}</td><td class='center'>{v_sat}</td><td class='right'>{format_rupiah(det['Harga_Satuan'])}</td><td class='right'>{format_rupiah(det['Total_Biaya'])}</td></tr>"

    html += f"""<tr class='bold' style='background-color:#d9d9d9;'><td colspan='4' class='right'>TOTAL SELURUH ANGGARAN (RKAKL {sumber_dana})</td><td class='right'>Rp {format_rupiah(total_semua)}</td></tr></table>
    <div class="ttd-box">Samarinda, {tgl_cetak}<br>Dekan<br><br><br><br><br><b><u>{nama_dekan}</u></b><br>NIP. {nip_dekan}</div>
    {paraf_html}<div style="clear: both;"></div></body></html>"""
    return html

col_r1, col_r2, col_r3 = st.columns(3)
tgl_skrg = format_tgl_indo(datetime.now().strftime("%Y-%m-%d"))
tgl_cetak_rkakl = col_r1.text_input("Tanggal Cetak Dokumen RKAKL", value=tgl_skrg, key="tgl_rkakl")
dekan_rkakl = col_r2.text_input("Nama Dekan", value="Prof. Dr. M. Bahri Arifin, M.Hum.", key="dek_rkakl")
nip_rkakl = col_r3.text_input("NIP Dekan", value="196211271989031004", key="nip_rkakl")

sumber_dana_rkakl = st.radio("Pilih Sumber Dana yang Akan Ditampilkan/Dicetak:", ["BOPTN", "PNBP"], key="sd_rkakl", horizontal=True)
tampilkan_paraf_rkakl = st.checkbox("Tampilkan Tabel Paraf (Khusus Arsip Hardcopy Internal)", key="paraf_rkakl")
st.markdown("---")

df_aktif = df_rab_utama[(df_rab_utama['Is_Active'] == 1) & (df_rab_utama['Sumber_Dana'] == sumber_dana_rkakl)]

if df_aktif.empty:
    st.info(f"Belum ada RAB aktif untuk sumber dana {sumber_dana_rkakl} tahun {tahun_aktif}.")
else:
    df_det_aktif = df_rab_detail[df_rab_detail['ID_RAB'].isin(df_aktif['ID_RAB'])]
    html_rkakl = generate_rkakl_html(df_aktif, df_det_aktif, kegiatan_code_map, tahun_aktif, tgl_cetak_rkakl, dekan_rkakl, nip_rkakl, sumber_dana_rkakl, tampilkan_paraf_rkakl)
    with st.container(border=True): components.html(html_rkakl, height=600, scrolling=True)
    st.download_button("📥 Cetak Buku Rekap RKAKL (.html)", data=html_rkakl.encode('utf-8'), file_name=f"RKAKL_{sumber_dana_rkakl}_FIB_{tahun_aktif}_{datetime.now().strftime('%Y%m%d')}.html", mime="text/html", type="primary")
