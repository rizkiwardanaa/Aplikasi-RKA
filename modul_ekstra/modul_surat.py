import streamlit as st
import google.generativeai as genai
from docx import Document
from docx.shared import Pt, Cm
from docx.enum.text import WD_ALIGN_PARAGRAPH
from io import BytesIO
import json
import os
import base64
from datetime import datetime

from utils import log_audit, format_tgl_indo

# --- FUNGSI BANTUAN MEMBACA GAMBAR ---
def get_image_base64(image_path):
    if os.path.exists(image_path):
        with open(image_path, "rb") as img_file:
            return base64.b64encode(img_file.read()).decode('utf-8')
    return ""

# --- FUNGSI AI GEMINI ---
def generate_surat_ai(hal, tujuan, isi_poin):
    prompt = f"""
    Anda adalah staf administrasi Fakultas Ilmu Budaya Universitas Mulawarman. 
    Buatlah draf narasi surat dinas berdasarkan data:
    - Hal: {hal}
    - Tujuan: {tujuan}
    - Poin Utama Isi Surat: {isi_poin}
    
    ATURAN:
    1. Gunakan bahasa Indonesia baku dan formal.
    2. Pembuka: Tuliskan 1 paragraf pengantar.
    3. Isi: Jabarkan poin dengan profesional dalam 1-2 paragraf yang mengalir.
    4. Penutup: "Demikian kami sampaikan, atas kerjasamanya diucapkan terima kasih."
    
    Output JSON murni dengan kunci: "pembuka", "isi", "penutup".
    """
    try:
        genai.configure(api_key=st.secrets["GEMINI_API_KEY_NEW"])
        model_list = genai.list_models()
        model_yang_bisa = [m.name for m in model_list if 'generateContent' in m.supported_generation_methods]
        
        if not model_yang_bisa: return None
        model_pilihan = next((m for m in model_yang_bisa if 'gemini-1.5' in m), model_yang_bisa[0])
        
        model = genai.GenerativeModel(model_pilihan.replace("models/", ""))
        respons = model.generate_content(prompt)
        return json.loads(respons.text.replace('```json', '').replace('```', '').strip())
    
    except Exception as e:
        if "429" in str(e):
            st.error("❌ Kuota AI Habis (Limit). Tunggu 20-30 detik lalu klik Generate lagi.")
        else:
            st.error(f"Error AI: {e}")
        return None

# --- BUILDER SURAT DINAS (.DOCX) ---
def build_surat_docx(meta, narasi):
    doc = Document()
    
    section = doc.sections[0]
    section.top_margin = Cm(1.5)
    section.bottom_margin = Cm(1.5)
    section.left_margin = Cm(2.5)
    section.right_margin = Cm(2.5)

    if os.path.exists("Header Kop Surat.jpg"):
        p_kop = doc.add_paragraph()
        p_kop.alignment = WD_ALIGN_PARAGRAPH.CENTER
        p_kop.add_run().add_picture("Header Kop Surat.jpg", width=Cm(16))
    else:
        p_kop = doc.add_paragraph()
        p_kop.alignment = WD_ALIGN_PARAGRAPH.CENTER
        p_kop.add_run("KEMENTERIAN PENDIDIKAN TINGGI, SAINS, DAN TEKNOLOGI\nUNIVERSITAS MULAWARMAN\nFAKULTAS ILMU BUDAYA\n").bold = True
        p_kop.add_run("Jl. Ki Hajar Dewantara, Kampus Gunung Kelua, Samarinda 75123\nTelepon (0541) 7809033")
    
    doc.add_paragraph()
    
    t_meta = doc.add_table(rows=3, cols=4)
    for row in t_meta.rows:
        row.cells[0].width = Cm(2.0)
        row.cells[1].width = Cm(0.5)
        row.cells[2].width = Cm(8.0)
        row.cells[3].width = Cm(5.0)

    t_meta.cell(0, 0).text = "Nomor"
    t_meta.cell(0, 1).text = ":"
    t_meta.cell(0, 2).text = meta['nomor']
    t_meta.cell(0, 3).text = meta['tgl_surat']
    t_meta.cell(0, 3).paragraphs[0].alignment = WD_ALIGN_PARAGRAPH.RIGHT

    t_meta.cell(1, 0).text = "Lampiran"
    t_meta.cell(1, 1).text = ":"
    t_meta.cell(1, 2).text = meta['lampiran']

    t_meta.cell(2, 0).text = "Hal"
    t_meta.cell(2, 1).text = ":"
    t_meta.cell(2, 2).text = meta['hal']

    p_tujuan = doc.add_paragraph()
    p_tujuan.add_run("\nYth. " + meta['tujuan'] + "\nSamarinda\n")

    p_buka = doc.add_paragraph(narasi['pembuka'])
    p_buka.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
    
    p_isi = doc.add_paragraph(narasi['isi'])
    p_isi.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
    
    p_tutup = doc.add_paragraph(narasi['penutup'])
    p_tutup.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
    
    p_ttd = doc.add_paragraph()
    p_ttd.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    p_ttd.add_run("Dekan,\n\n\n\n")
    p_ttd.add_run(meta['dekan_nama'] + "\nNIP " + meta['dekan_nip']).bold = True
    
    doc.add_paragraph("\n")
    
    t_paraf = doc.add_table(rows=4, cols=3)
    t_paraf.style = 'Table Grid'
    for row in t_paraf.rows:
        row.cells[0].width = Cm(1.0)
        row.cells[1].width = Cm(6.5)
        row.cells[2].width = Cm(2.5)

    data = [["NO", "JABATAN", "PARAF"], ["1", "Wakil Dekan Bidang Keuangan dan Umum", ""], ["2", "Kepala Bagian Umum", ""], ["3", "Staf Perencanaan", ""]]
    for i, row in enumerate(t_paraf.rows):
        for j, cell in enumerate(row.cells): 
            cell.text = data[i][j]
            if i == 0: cell.paragraphs[0].runs[0].bold = True

    output = BytesIO()
    doc.save(output)
    return output.getvalue()


# --- BUILDER SURAT PDF (HTML DENGAN GAMBAR & WATERMARK) ---
def generate_surat_html(meta, narasi):
    img_header = get_image_base64("Header Kop Surat.jpg")
    img_footer = get_image_base64("Footer Kop Surat.jpg")
    img_maskot = get_image_base64("Maskot Baru.png")
    
    html_header = f'<img src="data:image/jpeg;base64,{img_header}" class="header-img">' if img_header else '<h2 style="text-align:center;">[GAMBAR HEADER TIDAK DITEMUKAN]</h2><hr>'
    html_footer = f'<img src="data:image/jpeg;base64,{img_footer}" class="footer-img">' if img_footer else ''
    html_watermark = f'<img src="data:image/png;base64,{img_maskot}" class="watermark-img">' if img_maskot else ''

    # PRE-FORMAT STRING AGAR AMAN DARI SYNTAX ERROR DI PYTHON CLOUD
    tujuan_html = meta['tujuan'].replace('\n', '<br>')
    nomor_surat = meta['nomor']
    tgl_surat = meta['tgl_surat']
    lampiran_surat = meta['lampiran']
    hal_surat = meta['hal']
    pembuka_surat = narasi['pembuka']
    isi_surat = narasi['isi']
    penutup_surat = narasi['penutup']
    dekan_nama = meta['dekan_nama']
    dekan_nip = meta['dekan_nip']

    html = f"""<!DOCTYPE html>
    <html><head><meta charset="utf-8">
    <style>
        @page {{ size: A4 portrait; margin: 10mm; }}
        body {{ 
            font-family: 'Times New Roman', Times, serif; 
            font-size: 11.5pt; 
            line-height: 1.5; 
            color: #000; 
            text-align: justify; 
            position: relative;
            padding-bottom: 120px;
        }}
        .header-img {{ width: 100%; display: block; margin-bottom: 25px; }}
        .watermark-img {{ 
            position: fixed; 
            top: 50%; 
            left: 50%; 
            transform: translate(-50%, -50%); 
            opacity: 0.15; 
            width: 450px; 
            z-index: -1; 
        }}
        .footer-img {{ 
            position: fixed; 
            bottom: 0; 
            left: 0; 
            width: 100%; 
            z-index: 10; 
        }}
        table.meta-table {{ width: 100%; border-collapse: collapse; margin-bottom: 15px; border: none; }}
        table.meta-table td {{ padding: 1px; vertical-align: top; border: none; }}
        .isi-surat p {{ 
            text-indent: 0; 
            margin-top: 5px; 
            margin-bottom: 15px; 
            text-align: justify; 
        }}
        .tujuan {{ margin-bottom: 20px; margin-top: 15px; }}
        .ttd-box {{ width: 250px; float: right; text-align: left; margin-top: 30px; }}
        .paraf-box {{ width: 320px; float: left; margin-top: 80px; clear: left; }}
        table.paraf-table {{ width: 100%; border-collapse: collapse; font-size: 9.5pt; font-family: 'Arial', sans-serif; }}
        table.paraf-table th, table.paraf-table td {{ border: 1px solid black; padding: 4px 6px; }}
        table.paraf-table th {{ text-align: left; }}
    </style></head><body>
    
    {html_watermark}
    
    {html_header}
    
    <table class="meta-table">
        <tr>
            <td style="width: 12%;">Nomor</td><td style="width: 2%;">:</td><td style="width: 56%;">{nomor_surat}</td>
            <td style="width: 30%; text-align: right;">{tgl_surat}</td>
        </tr>
        <tr><td>Lampiran</td><td>:</td><td colspan="2">{lampiran_surat}</td></tr>
        <tr><td>Hal</td><td>:</td><td colspan="2">{hal_surat}</td></tr>
    </table>
    
    <div class="tujuan">
        Yth. {tujuan_html}<br>
        Samarinda
    </div>
    
    <div class="isi-surat">
        <p>{pembuka_surat}</p>
        <p>{isi_surat}</p>
        <p>{penutup_surat}</p>
    </div>
    
    <div class="ttd-box">
        Dekan,<br><br><br><br><br>
        <b>{dekan_nama}</b><br>
        NIP {dekan_nip}
    </div>
    
    <div class="paraf-box">
        <table class="paraf-table">
            <tr><th style="width: 10%; text-align: center;">NO</th><th style="width: 65%;">JABATAN</th><th style="width: 25%;">PARAF</th></tr>
            <tr><td style="text-align: center;">1</td><td>Wakil Dekan Bidang Keuangan dan Umum</td><td></td></tr>
            <tr><td style="text-align: center;">2</td><td>Kepala Bagian Umum</td><td></td></tr>
            <tr><td style="text-align: center;">3</td><td>Staf Perencanaan</td><td></td></tr>
        </table>
    </div>
    
    {html_footer}
    
    <div style="clear: both;"></div>
    </body></html>"""
    return html

# --- ANTARMUKA PENGGUNA (UI) ---
def show_page():
    st.title("✉️ Pengolah Surat Otomatis")
    st.caption("Didukung oleh Google Gemini AI. Menghasilkan surat dinas dengan kop gambar dan watermark.")
    
    missing_files = []
    if not os.path.exists("Header Kop Surat.jpg"): missing_files.append("Header Kop Surat.jpg")
    if not os.path.exists("Footer Kop Surat.jpg"): missing_files.append("Footer Kop Surat.jpg")
    if not os.path.exists("Maskot Baru.png"): missing_files.append("Maskot Baru.png")
    
    if missing_files:
        st.warning(f"⚠️ Peringatan: File template gambar berikut belum ditemukan di folder aplikasi: **{', '.join(missing_files)}**. Surat tetap bisa dibuat, tapi gambar tersebut tidak akan muncul.")

    with st.container(border=True):
        st.subheader("1. Identitas Surat")
        col1, col2, col3 = st.columns(3)
        meta = {
            'nomor': col1.text_input("Nomor Surat", f"499/UN17.13/PR.03.01/{datetime.now().year}"),
            'lampiran': col2.text_input("Lampiran", "1 (satu) berkas"),
            'tgl_surat': col3.text_input("Tanggal Surat", format_tgl_indo(datetime.now().strftime("%Y-%m-%d"))),
            'hal': st.text_input("Hal / Perihal", "Tindak Lanjut Permintaan Data"),
            'tujuan': st.text_area("Yth. / Pihak Tujuan", "Rektor\nUniversitas Mulawarman\nc.q Wakil Rektor Bidang Perencanaan, Kerjasama, dan Sistem Informasi"),
            'dekan_nama': "Prof. Dr. M. Bahri Arifin, M.Hum.",
            'dekan_nip': "196211271989031004"
        }
    
    with st.container(border=True):
        st.subheader("2. Materi & Poin Utama Surat")
        isi_poin = st.text_area("Ketik intisari yang ingin Anda sampaikan:", "FIB mengirimkan Data Alokasi Anggaran Peningkatan Kualitas Penelitian dan Pengabdian kepada Masyarakat Tahun Anggaran 2025 dan 2026. Data ini sebagai bahan penyusunan rencana kerja.")
        
        if st.button("✨ Generate Narasi Surat", type="primary"):
            with st.spinner("AI sedang merangkai bahasa yang sopan dan formal..."):
                narasi = generate_surat_ai(meta['hal'], meta['tujuan'], isi_poin)
                if narasi:
                    st.session_state['surat_narasi'] = narasi
                    st.success("Draft narasi selesai disusun! Silakan periksa di bawah.")

    if 'surat_narasi' in st.session_state:
        st.markdown("---")
        st.subheader("3. Editor Draft Surat")
        
        with st.form("form_edit_surat"):
            edit_pembuka = st.text_area("Paragraf Pembuka", value=st.session_state['surat_narasi'].get('pembuka', ''), height=100)
            edit_isi = st.text_area("Paragraf Isi", value=st.session_state['surat_narasi'].get('isi', ''), height=150)
            edit_penutup = st.text_area("Paragraf Penutup", value=st.session_state['surat_narasi'].get('penutup', ''), height=80)
            
            if st.form_submit_button("Simpan Perubahan Teks"):
                st.session_state['surat_narasi'] = {'pembuka': edit_pembuka, 'isi': edit_isi, 'penutup': edit_penutup}
                st.success("Teks berhasil diperbarui.")
        
        st.markdown("### 🖨️ Cetak Dokumen")
        col_x1, col_x2 = st.columns(2)
        
        # Penanganan nama file agar aman
        hal_safe = meta['hal'].replace(' ', '_')
        
        with col_x1:
            file_word = build_surat_docx(meta, st.session_state['surat_narasi'])
            st.download_button(
                label="📥 Download Surat (.docx)",
                data=file_word,
                file_name=f"Surat_{hal_safe}.docx",
                mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                use_container_width=True
            )
        
        with col_x2:
            html_print = generate_surat_html(meta, st.session_state['surat_narasi'])
            if st.download_button(
                label="📑 Cetak PDF (Format Template Gambar)",
                data=html_print.encode('utf-8'),
                file_name=f"Surat_{hal_safe}.html",
                mime="text/html",
                use_container_width=True,
                help="Buka file ini di browser Chrome/Edge, lalu tekan Ctrl+P. Gambar Header, Footer, dan Maskot akan otomatis termuat."
            ):
                log_audit("BUAT SURAT", f"Hal: {meta['hal']} (Cetak Template Gambar)")

show_page()