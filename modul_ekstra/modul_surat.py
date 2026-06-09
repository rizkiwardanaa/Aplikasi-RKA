import streamlit as st
import pandas as pd
import google.generativeai as genai
from docx import Document
from docx.shared import Pt, Cm
from docx.enum.text import WD_ALIGN_PARAGRAPH
from io import BytesIO
import json
from datetime import datetime
from utils import log_audit

# --- FUNGSI AI GEMINI (AUTO-DETECT MODEL) ---
def generate_surat_ai(hal, tujuan, isi_poin):
    prompt = f"""
    Anda adalah staf administrasi Fakultas Ilmu Budaya Universitas Mulawarman. 
    Buatlah isi surat dinas berdasarkan data:
    - Hal: {hal}
    - Tujuan: {tujuan}
    - Poin Utama Isi Surat: {isi_poin}
    
    ATURAN:
    1. Bahasa Indonesia baku dan formal.
    2. Pembuka: "Menindaklanjuti surat dari..." (sesuaikan dengan konteks/tujuan).
    3. Bagian isi: Jabarkan {isi_poin} dengan profesional.
    4. Penutup: "Demikian kami sampaikan, atas kerjasamanya diucapkan terima kasih."
    
    Output JSON murni dengan kunci: "pembuka", "isi", "penutup".
    """
    try:
        genai.configure(api_key=st.secrets["GEMINI_API_KEY_NEW"])
        # MENGGUNAKAN LOGIKA AUTO-DETECT MODEL SEPERTI MODUL TOR
        model_list = genai.list_models()
        model_yang_bisa = [m.name for m in model_list if 'generateContent' in m.supported_generation_methods]
        model_pilihan = next((m for m in model_yang_bisa if 'gemini-1.5' in m), model_yang_bisa[0])
        
        model = genai.GenerativeModel(model_pilihan.replace("models/", ""))
        respons = model.generate_content(prompt)
        return json.loads(respons.text.replace('```json', '').replace('```', '').strip())
    except Exception as e:
        st.error(f"Error AI: {e}")
        return None

# --- BUILDER SURAT DINAS (LAYOUT KAKU SESUAI REFERENSI) ---
def build_surat_docx(meta, narasi):
    doc = Document()
    section = doc.sections[0]
    section.top_margin = Cm(2.5); section.bottom_margin = Cm(2.0)
    section.left_margin = Cm(2.5); section.right_margin = Cm(2.0)

    # HEADER / KOP SURAT (GANTI BAGIAN INI)
    p_kop = doc.add_paragraph()
    p_kop.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r = p_kop.add_run("KEMENTERIAN PENDIDIKAN TINGGI, SAINS, DAN TEKNOLOGI\nUNIVERSITAS MULAWARMAN\nFAKULTAS ILMU BUDAYA\n")
    r.bold = True
    r.font.size = Pt(12)
    p_kop.add_run("Jl. Ki Hajar Dewantara, Kampus Gunung Kelua, Samarinda 75123\nTelepon (0541) 7809033 | http://fib.unmul.ac.id").font.size = Pt(9)
    
    # MENGGANTI .add_picture DENGAN BORDER PARAGRAF (LEBIH AMAN)
    paragraph_format = p_kop.paragraph_format
    paragraph_format.paragraph_border_bottom = Pt(2.0)

    # NOMOR & HAL
    t = doc.add_table(rows=0, cols=3)
    t.add_row().cells[0].text = "Nomor"; t.rows[-1].cells[2].text = meta['nomor']
    t.add_row().cells[0].text = "Lampiran"; t.rows[-1].cells[2].text = meta['lampiran']
    t.add_row().cells[0].text = "Hal"; t.rows[-1].cells[2].text = meta['hal']
    
    doc.add_paragraph(f"\nYth. {meta['tujuan']}\nSamarinda")
    
    # ISI
    doc.add_paragraph(narasi['pembuka'])
    doc.add_paragraph(narasi['isi'])
    doc.add_paragraph(narasi['penutup'])
    
    # FOOTER / TTD & PARAF
    p_ttd = doc.add_paragraph()
    p_ttd.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    p_ttd.add_run(f"Dekan,\n\n\n\n{meta['dekan_nama']}\nNIP {meta['dekan_nip']}").bold = True
    
    doc.add_paragraph("\n\n")
    # TABEL PARAF (Sesuai referensi)
    t_paraf = doc.add_table(rows=4, cols=3)
    t_paraf.style = 'Table Grid'
    data = [["No", "Jabatan", "Paraf"], ["1", "Wakil Dekan Bidang Keuangan dan Umum", ""], ["2", "Kepala Bagian Umum", ""], ["3", "Staf Perencanaan", ""]]
    for i, row in enumerate(t_paraf.rows):
        for j, cell in enumerate(row.cells): cell.text = data[i][j]

    output = BytesIO()
    doc.save(output)
    return output.getvalue()

# --- UI ---
def show_page():
    st.title("✉️ Pengolah Surat Otomatis")
    
    col1, col2 = st.columns(2)
    meta = {
        'nomor': col1.text_input("Nomor Surat", f"499/UN17.13/PR.03.01/{datetime.now().year}"),
        'lampiran': col2.text_input("Lampiran", "1 (satu) berkas"),
        'hal': st.text_input("Hal", "Tindak Lanjut Permintaan Data"),
        'tujuan': st.text_area("Yth. Rektor / Tujuan"),
        'dekan_nama': "Prof. Dr. M. Bahri Arifin, M.Hum.",
        'dekan_nip': "196211271989031004"
    }
    
    isi_poin = st.text_area("Poin-poin isi surat yang ingin disampaikan:")
    
    if st.button("Generate Narasi Surat"):
        narasi = generate_surat_ai(meta['hal'], meta['tujuan'], isi_poin)
        if narasi:
            st.session_state['surat_narasi'] = narasi
            st.success("Draft narasi selesai disusun!")

    if 'surat_narasi' in st.session_state:
        st.write(st.session_state['surat_narasi'])
        if st.download_button("Download Surat (.docx)", build_surat_docx(meta, st.session_state['surat_narasi']), "surat_dinas.docx"):
            log_audit("BUAT SURAT", f"Hal: {meta['hal']}")

show_page()
