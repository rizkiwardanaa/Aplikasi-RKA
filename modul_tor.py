import streamlit as st
import pandas as pd
from sqlalchemy import create_engine
import google.generativeai as genai
from docx import Document
from docx.shared import Pt, Inches
from docx.enum.text import WD_ALIGN_PARAGRAPH
from io import BytesIO
import json
from datetime import datetime

# --- KONEKSI DATABASE ---
# --- GANTI BAGIAN KONEKSI DATABASE DI modul_tor.py DENGAN INI ---
@st.cache_resource
def get_engine():
    # Menggunakan cache_resource agar engine hanya dibuat sekali untuk seluruh aplikasi
    return create_engine(st.secrets["DB_URL"], pool_size=5, max_overflow=10)

engine = get_engine()
# -------------------------------------------------------------

def format_rupiah(x):
    try: return f"{float(x):,.0f}".replace(',', '.')
    except (ValueError, TypeError): return x

def split_kode(teks):
    s = str(teks).strip()
    if " - " in s:
        parts = s.split(" - ", 1)
        return parts[0].strip(), parts[1].strip()
    parts = s.split(" ", 1)
    if len(parts) == 2:
        first_part = parts[0].strip()
        if any(c.isdigit() for c in first_part) or len(first_part) <= 8 or "." in first_part:
            return first_part, parts[1].strip()
    if any(c.isdigit() for c in s) or len(s) <= 8 or "." in s:
        return s, ""
    return "", s

@st.cache_data(ttl=60)
def load_active_rab():
    conn = engine.connect()
    try:
        df_utama = pd.read_sql("SELECT * FROM rab_utama WHERE \"Is_Active\" = 1", conn)
        if not df_utama.empty:
            ids = tuple(df_utama['ID_RAB'].tolist())
            if len(ids) == 1:
                df_detail = pd.read_sql(f"SELECT * FROM rab_detail WHERE \"ID_RAB\" = '{ids[0]}'", conn)
            else:
                df_detail = pd.read_sql(f"SELECT * FROM rab_detail WHERE \"ID_RAB\" IN {ids}", conn)
        else:
            df_detail = pd.DataFrame()
    except Exception as e:
        df_utama, df_detail = pd.DataFrame(), pd.DataFrame()
    conn.close()
    return df_utama, df_detail

# --- FUNGSI AI GEMINI (JSON MODE) ---
def generate_narasi_tor_json(kegiatan, total_anggaran, sasaran, list_belanja, poin_tambahan):
    try:
        genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
        
        # 1. Gunakan model yang paling umum dan pasti tersedia
        # 'gemini-1.5-flash' adalah model yang sangat cepat dan hemat kuota
        model = genai.GenerativeModel('gemini-3.1-flash-lite')
        
        prompt = f"""
        Anda adalah perencana anggaran ahli di Fakultas Ilmu Budaya Universitas Mulawarman. 
        Tugas Anda adalah menulis komponen isi untuk Term of Reference (TOR) berdasarkan data berikut:
        
        - Nama Kegiatan: {kegiatan}
        - Sasaran: {sasaran}
        - Total Dana: Rp {total_anggaran}
        - Item Utama: {list_belanja}
        - Catatan: {poin_tambahan}
        
        Kembalikan output murni dalam format JSON (tanpa blok kode markdown ```json) dengan kunci persis seperti ini:
        {{
            "dasar_hukum": "Tuliskan 3-4 dasar hukum yang relevan dengan kegiatan ini.",
            "gambaran_umum": "Tuliskan 2 paragraf gambaran umum mengapa kegiatan ini penting.",
            "penerima_manfaat": "Jelaskan siapa penerima manfaat dari kegiatan ini dalam 1 paragraf.",
            "metode_pelaksanaan": "Jelaskan bagaimana metode pelaksanaan kegiatan ini dalam 1 paragraf.",
            "tahapan_waktu": "Jelaskan tahapan dan waktu pelaksanaan secara singkat.",
            "biaya_diperlukan": "Tulis 1 paragraf naratif bahwa total anggaran adalah Rp {total_anggaran} dari dana FIB Unmul."
        }}
        """
        
        respons = model.generate_content(prompt)
        # Tambahan: Bersihkan karakter markdown jika AI memberikan respons berlebih
        teks_respons = respons.text.replace('```json', '').replace('```', '').strip()
            
        return json.loads(teks_respons)
        
    except Exception as e:
        # Logika Cadangan: Jika 1.5-flash gagal, kita gunakan model yang paling "tua" tapi paling stabil
        try:
            st.warning("Model 1.5-flash gagal, mencoba model cadangan (gemini-pro)...")
            model = genai.GenerativeModel('gemini-pro')
            respons = model.generate_content(prompt)
            teks_respons = respons.text.replace('```json', '').replace('```', '').strip()
            return json.loads(teks_respons)
        except Exception as e2:
            st.error(f"Gagal total menghubungi Gemini. Pastikan API Key benar. Error: {e2}")
            return None

# --- BUILDER MICROSOFT WORD (.DOCX) ---
def build_docx(meta, narasi):
    doc = Document()
    
    # KOP & JUDUL
    p_judul = doc.add_paragraph()
    p_judul.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r_judul = p_judul.add_run("KERANGKA ACUAN KERJA/TERM OF REFERENCE\n")
    r_judul.bold = True
    r_judul.font.size = Pt(12)
    
    # METADATA TABLE (Borderless)
    table = doc.add_table(rows=0, cols=3)
    # Atur lebar kolom (rasio)
    for row in table.rows:
        row.cells[0].width = Inches(2.0)
        row.cells[1].width = Inches(0.2)
        row.cells[2].width = Inches(4.0)

    def add_meta_row(label, value):
        cells = table.add_row().cells
        cells[0].text = label
        cells[1].text = ":"
        cells[2].text = str(value)
        
    add_meta_row("Kementerian Negara/Lembaga", "(023) Kementerian Pendidikan, Kebudayaan, Riset dan Teknologi")
    add_meta_row("Unit Eselon I", "(17) Direktorat Jenderal Pendidikan Tinggi, Riset dan Teknologi")
    add_meta_row("Program", f"{meta['ro_code']} ({meta['ro_name']} ({meta['sumber_dana']}))")
    add_meta_row("Sasaran Program", meta['sasaran_prog'])
    add_meta_row("Indikator Kinerja Program", meta['ikp'])
    add_meta_row("Kegiatan", meta['kegiatan_induk'])
    add_meta_row("Sasaran Kegiatan", meta['sasaran_keg'])
    add_meta_row("Indikator Kinerja Kegiatan", meta['ikk'])
    add_meta_row("Klasifikasi Rincian Output", meta['kro_teks'])
    add_meta_row("Indikator KRO", meta['ind_kro'])
    add_meta_row("Rincian Output", meta['ro_teks'])
    add_meta_row("Volume RO", f"{meta['vol']}")
    add_meta_row("Satuan RO", meta['sat'])

    # BAB A
    doc.add_paragraph("\nA. Latar Belakang").bold = True
    doc.add_paragraph("1. Dasar Hukum").bold = True
    doc.add_paragraph(narasi.get('dasar_hukum', ''))
    
    doc.add_paragraph("2. Gambaran Umum").bold = True
    doc.add_paragraph(narasi.get('gambaran_umum', ''))
    
    # BAB B
    doc.add_paragraph("B. Penerima Manfaat").bold = True
    doc.add_paragraph(narasi.get('penerima_manfaat', ''))
    
    # BAB C
    doc.add_paragraph("C. Strategi Pencapaian Keluaran").bold = True
    doc.add_paragraph("1. Metode Pelaksanaan").bold = True
    doc.add_paragraph(narasi.get('metode_pelaksanaan', ''))
    
    doc.add_paragraph("2. Tahapan dan Waktu Pelaksanaan").bold = True
    doc.add_paragraph(narasi.get('tahapan_waktu', ''))
    
    # BAB D
    doc.add_paragraph("D. Biaya Yang Diperlukan").bold = True
    doc.add_paragraph(narasi.get('biaya_diperlukan', ''))

    # TANDA TANGAN
    doc.add_paragraph("\n")
    p_ttd = doc.add_paragraph(f"Samarinda, {meta['tgl_cetak']}\nPenanggung Jawab Kegiatan\n\n\n\n")
    p_ttd.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    r_nama = p_ttd.add_run(f"({meta['ketua']})")
    r_nama.bold = True
    
    output = BytesIO()
    doc.save(output)
    return output.getvalue()

# --- BUILDER PDF / HTML PRINT-READY ---
def generate_tor_html(meta, narasi):
    html = f"""
    <!DOCTYPE html>
    <html><head><meta charset="utf-8">
    <style>
        @page {{ size: A4 portrait; margin: 20mm; }}
        body {{ font-family: 'Arial', sans-serif; font-size: 11pt; line-height: 1.5; color: #000; text-align: justify; }}
        .center {{ text-align: center; font-weight: bold; font-size: 12pt; margin-bottom: 20px; }}
        table {{ width: 100%; border-collapse: collapse; margin-bottom: 20px; }}
        td {{ padding: 2px 4px; vertical-align: top; }}
        .label {{ width: 35%; }}
        .titik {{ width: 3%; text-align: center; }}
        .value {{ width: 62%; }}
        .bab-title {{ font-weight: bold; margin-top: 15px; margin-bottom: 5px; }}
        .sub-bab {{ font-weight: bold; margin-top: 10px; margin-bottom: 5px; padding-left: 15px; }}
        .isi-text {{ margin-top: 0px; margin-bottom: 10px; padding-left: 15px; white-space: pre-wrap; }}
        .isi-sub-text {{ margin-top: 0px; margin-bottom: 10px; padding-left: 30px; white-space: pre-wrap; }}
        .ttd-box {{ width: 250px; float: right; text-align: left; margin-top: 40px; }}
    </style></head><body>
    <div class="center">KERANGKA ACUAN KERJA/TERM OF REFERENCE</div>
    
    <table>
        <tr><td class="label">Kementerian Negara/Lembaga</td><td class="titik">:</td><td class="value">(023) Kementerian Pendidikan, Kebudayaan, Riset dan Teknologi</td></tr>
        <tr><td class="label">Unit Eselon I</td><td class="titik">:</td><td class="value">(17) Direktorat Jenderal Pendidikan Tinggi, Riset dan Teknologi</td></tr>
        <tr><td class="label">Program</td><td class="titik">:</td><td class="value">{meta['ro_code']} ({meta['ro_name']} ({meta['sumber_dana']}))</td></tr>
        <tr><td class="label">Sasaran Program</td><td class="titik">:</td><td class="value">{meta['sasaran_prog']}</td></tr>
        <tr><td class="label">Indikator Kinerja Program</td><td class="titik">:</td><td class="value">{meta['ikp']}</td></tr>
        <tr><td class="label">Kegiatan</td><td class="titik">:</td><td class="value">{meta['kegiatan_induk']}</td></tr>
        <tr><td class="label">Sasaran Kegiatan</td><td class="titik">:</td><td class="value">{meta['sasaran_keg']}</td></tr>
        <tr><td class="label">Indikator Kinerja Kegiatan</td><td class="titik">:</td><td class="value">{meta['ikk']}</td></tr>
        <tr><td class="label">Klasifikasi Rincian Output</td><td class="titik">:</td><td class="value">{meta['kro_teks']}</td></tr>
        <tr><td class="label">Indikator KRO</td><td class="titik">:</td><td class="value">{meta['ind_kro']}</td></tr>
        <tr><td class="label">Rincian Output</td><td class="titik">:</td><td class="value">{meta['ro_teks']}</td></tr>
        <tr><td class="label">Volume RO</td><td class="titik">:</td><td class="value">{meta['vol']}</td></tr>
        <tr><td class="label">Satuan RO</td><td class="titik">:</td><td class="value">{meta['sat']}</td></tr>
    </table>
    
    <div class="bab-title">A. Latar Belakang</div>
    <div class="sub-bab">1. Dasar Hukum</div>
    <div class="isi-sub-text">{narasi.get('dasar_hukum', '')}</div>
    <div class="sub-bab">2. Gambaran Umum</div>
    <div class="isi-sub-text">{narasi.get('gambaran_umum', '')}</div>
    
    <div class="bab-title">B. Penerima Manfaat</div>
    <div class="isi-text">{narasi.get('penerima_manfaat', '')}</div>
    
    <div class="bab-title">C. Strategi Pencapaian Keluaran</div>
    <div class="sub-bab">1. Metode Pelaksanaan</div>
    <div class="isi-sub-text">{narasi.get('metode_pelaksanaan', '')}</div>
    <div class="sub-bab">2. Tahapan dan Waktu Pelaksanaan</div>
    <div class="isi-sub-text">{narasi.get('tahapan_waktu', '')}</div>
    
    <div class="bab-title">D. Biaya Yang Diperlukan</div>
    <div class="isi-text">{narasi.get('biaya_diperlukan', '')}</div>
    
    <div class="ttd-box">
        Samarinda, {meta['tgl_cetak']}<br>
        Penanggung Jawab Kegiatan<br><br><br><br><br>
        <b>({meta['ketua']})</b>
    </div>
    </body></html>
    """
    return html

# =====================================================================
# TAMPILAN HALAMAN UTAMA
# =====================================================================
def show_page():
    st.title("🤖 Asisten Penyusun TOR Otomatis")
    st.caption("Didukung oleh Google Gemini AI. Menghasilkan struktur TOR standar Universitas.")
    
    df_utama, df_detail = load_active_rab()
    
    if df_utama.empty:
        st.warning("⚠️ Belum ada dokumen RAB yang berstatus AKTIF. Silakan aktifkan RAB di modul Pengolah RAB terlebih dahulu.")
        return

    if 'tor_json' not in st.session_state: st.session_state.tor_json = None
    
    kegiatan_list = sorted(df_utama['Kegiatan'].unique())
    
    tab_setup, tab_drafting, tab_cetak = st.tabs(["1️⃣ Setup Data Meta", "2️⃣ Drafting AI Gemini", "3️⃣ Finalisasi & Cetak"])

    # --- TAB 1: SETUP ---
    with tab_setup:
        st.subheader("Pilih Data Kegiatan (RAB Aktif)")
        pilih_keg = st.selectbox("Kegiatan:", kegiatan_list, format_func=lambda x: x.title())
        
        df_keg_utama = df_utama[df_utama['Kegiatan'] == pilih_keg].iloc[0]
        df_keg_det = df_detail[df_detail['ID_RAB'] == df_keg_utama['ID_RAB']]
        tot_rp = df_keg_det['Total_Biaya'].sum()
        
        st.info(f"**Sasaran:** {df_keg_utama['Sasaran']}\n\n**Total Pagu:** Rp {format_rupiah(tot_rp)}")
        
        st.markdown("---")
        st.subheader("Informasi Operasional & Penanggung Jawab")
        col1, col2 = st.columns(2)
        in_ketua = col1.text_input("Nama Penanggung Jawab / Pejabat", value=df_keg_utama['Nama_Pejabat'])
        in_tgl_cetak = col2.text_input("Tanggal Cetak Dokumen", value=df_keg_utama['Tanggal'][:10])
        in_poin = st.text_area("Catatan Latar Belakang untuk AI (Opsional)", placeholder="Ketik ide/alasan singkat mengapa kegiatan ini butuh dilaksanakan agar AI bisa merangkainya.")

    # BUILD METADATA DICTIONARY
    kro_code, kro_name = split_kode(df_keg_utama['KRO'])
    ro_code, ro_name = split_kode(df_keg_utama['RO'])
    
    meta_tor = {
        'sumber_dana': df_keg_utama['Sumber_Dana'],
        'ro_code': ro_code,
        'ro_name': ro_name,
        'sasaran_prog': f"Peningkatan {kro_name}",
        'ikp': f"Meningkatnya Kualitas {kro_name}",
        'kegiatan_induk': "7730. (Peningkatan Kualitas dan Kapasitas Perguruan Tinggi)",
        'sasaran_keg': df_keg_utama['Sasaran'],
        'ikk': "Meningkatnya Kualitas dan Kapasitas Perguruan Tinggi",
        'kro_teks': f"{kro_code}. ({kro_name})",
        'ind_kro': f"Meningkatnya Kualitas {ro_name}",
        'ro_teks': f"{ro_code}. ({ro_name})",
        'vol': df_keg_utama['Volume'],
        'sat': df_keg_utama['Satuan'],
        'ketua': in_ketua,
        'tgl_cetak': in_tgl_cetak,
        'keg_title': pilih_keg.title()
    }

    # --- TAB 2: AI DRAFTING ---
    with tab_drafting:
        st.subheader("Penyusunan Narasi Berbantu AI")
        st.markdown("AI Gemini akan membaca rincian RAB dan menyusun narasi TOR per bab.")
        
        if st.button("✨ Auto-Generate Narasi TOR", type="primary"):
            with st.spinner("AI sedang menganalisis data dan merangkai paragraf..."):
                list_barang = ", ".join(df_keg_det['Uraian'].tolist()[:15])
                
                hasil_json = generate_narasi_tor_json(
                    kegiatan=meta_tor['keg_title'],
                    total_anggaran=format_rupiah(tot_rp),
                    sasaran=meta_tor['sasaran_keg'],
                    list_belanja=list_barang,
                    poin_tambahan=in_poin
                )
                
                if hasil_json:
                    st.session_state.tor_json = hasil_json
                    st.success("Draft berhasil disusun! Silakan periksa dan edit di bawah ini.")
                
        if st.session_state.tor_json:
            st.markdown("### 📝 Editor Draft TOR")
            st.caption("Anda dapat menyunting langsung teks di bawah ini sebelum dicetak.")
            
            with st.form("form_edit_tor"):
                edit_dh = st.text_area("A.1. Dasar Hukum", value=st.session_state.tor_json.get('dasar_hukum', ''), height=150)
                edit_gu = st.text_area("A.2. Gambaran Umum", value=st.session_state.tor_json.get('gambaran_umum', ''), height=150)
                edit_pm = st.text_area("B. Penerima Manfaat", value=st.session_state.tor_json.get('penerima_manfaat', ''), height=100)
                edit_mp = st.text_area("C.1. Metode Pelaksanaan", value=st.session_state.tor_json.get('metode_pelaksanaan', ''), height=100)
                edit_tw = st.text_area("C.2. Tahapan dan Waktu Pelaksanaan", value=st.session_state.tor_json.get('tahapan_waktu', ''), height=100)
                edit_bd = st.text_area("D. Biaya Yang Diperlukan", value=st.session_state.tor_json.get('biaya_diperlukan', ''), height=100)
                
                if st.form_submit_button("Simpan Perubahan Draft", type="primary"):
                    st.session_state.tor_json = {
                        'dasar_hukum': edit_dh, 'gambaran_umum': edit_gu, 'penerima_manfaat': edit_pm,
                        'metode_pelaksanaan': edit_mp, 'tahapan_waktu': edit_tw, 'biaya_diperlukan': edit_bd
                    }
                    st.success("Perubahan tersimpan! Lanjut ke tab 3 untuk mencetak.")

    # --- TAB 3: CETAK ---
    with tab_cetak:
        st.subheader("Cetak Dokumen Resmi")
        if st.session_state.tor_json:
            st.success("Narasi telah siap. Metadata akan dilampirkan otomatis ke dalam dokumen.")
            
            col_x1, col_x2 = st.columns(2)
            
            with col_x1:
                file_word = build_docx(meta_tor, st.session_state.tor_json)
                st.download_button(
                    label="📥 Download TOR (.docx)",
                    data=file_word,
                    file_name=f"TOR_{meta_tor['keg_title'].replace(' ', '_')}.docx",
                    mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                    use_container_width=True
                )
            
            with col_x2:
                html_print = generate_tor_html(meta_tor, st.session_state.tor_json)
                st.download_button(
                    label="📑 Cetak PDF (HTML Print-Ready)",
                    data=html_print.encode('utf-8'),
                    file_name=f"TOR_{meta_tor['keg_title'].replace(' ', '_')}.html",
                    mime="text/html",
                    use_container_width=True,
                    help="Buka file di browser Chrome/Edge, lalu tekan Ctrl+P. Pilih orientasi Portrait."
                )
        else:
            st.warning("⚠️ Anda belum menyusun narasi. Silakan klik 'Auto-Generate Narasi TOR' di tab 2.")
