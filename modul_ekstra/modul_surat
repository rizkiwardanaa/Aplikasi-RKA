import streamlit as st
from docx import Document
from docx.shared import Pt, Cm, Inches
from docx.enum.text import WD_ALIGN_PARAGRAPH
from io import BytesIO
from datetime import datetime
import google.generativeai as genai
import json

# Mengambil fungsi dari Gudang Inti
from utils import log_audit

def generate_surat_ai(hal, tujuan, isi_poin):
    prompt = f"""
    Anda adalah staf administrasi Fakultas Ilmu Budaya Universitas Mulawarman. 
    Buatlah isi surat dinas berdasarkan data berikut:
    - Hal: {hal}
    - Tujuan: {tujuan}
    - Poin Utama Isi Surat: {isi_poin}
    
    ATURAN:
    1. Gunakan bahasa Indonesia baku dan formal.
    2. Bagian pembuka: Menindaklanjuti surat dari Sekretaris Direktorat Jenderal Pendidikan Tinggi... (sesuaikan dengan konteks).
    3. Bagian isi: Jabarkan {isi_poin} dengan profesional.
    4. Bagian penutup: "Demikian kami sampaikan, atas kerjasamanya diucapkan terima kasih."
    
    Berikan output dalam bentuk JSON dengan kunci: "pembuka", "isi", "penutup".
    """
    try:
        genai.configure(api_key=st.secrets["GEMINI_API_KEY_NEW"])
        model = genai.GenerativeModel('gemini-1.5-flash')
        respons = model.generate_content(prompt)
        return json.loads(respons.text.replace('```json', '').replace('```', '').strip())
    except Exception as e:
        st.error(f"Error AI: {e}")
        return None

def build_surat_docx(meta, narasi):
    doc = Document()
    # Setting Margin
    section = doc.sections[0]
    section.top_margin = Cm(2.5); section.bottom_margin = Cm(2.0)
    section.left_margin = Cm(2.5); section.right_margin = Cm(2.0)

    # Header / Kop Surat (Sesuai referensi)
    p_kop = doc.add_paragraph()
    p_kop.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p_kop.add_run("KEMENTERIAN PENDIDIKAN TINGGI, SAINS, DAN TEKNOLOGI\nUNIVERSITAS MULAWARMAN\nFAKULTAS ILMU BUDAYA\n").bold = True
    p_kop.add_run("Jl. Ki Hajar Dewantara, Kampus Gunung Kelua, Samarinda 75123\nTelepon (0541) 7809033 | http://fib.unmul.ac.id").font.size = Pt(9)
    doc.add_paragraph().add_run().add_picture(BytesIO(), width=Inches(6)) # Garis pembatas

    # Metadata Surat
    table = doc.add_table(rows=0, cols=3)
    table.add_row().cells[0].text = "Nomor"; table.add_row().cells[2].text = meta['nomor']
    table.add_row().cells[0].text = "Lampiran"; table.add_row().cells[2].text = meta['lampiran']
    table.add_row().cells[0].text = "Hal"; table.add_row().cells[2].text = meta['hal']
    
    doc.add_paragraph(f"\nYth. {meta['tujuan']}\nSamarinda")
    
    # Isi Surat
    doc.add_paragraph(narasi['pembuka'])
    doc.add_paragraph(narasi['isi'])
    doc.add_paragraph(narasi['penutup'])
    
    # Footer / TTD
    p_ttd = doc.add_paragraph()
    p_ttd.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    p_ttd.add_run("Dekan,\n\n\n\n").bold = True
    p_ttd.add_run(f"{meta['dekan_nama']}\nNIP {meta['dekan_nip']}")
    
    output = BytesIO()
    doc.save(output)
    return output.getvalue()

# --- UI ---
def show_page():
    st.title("✉️ Pengolah Surat Otomatis")
    
    col1, col2 = st.columns(2)
    meta = {
        'nomor': col1.text_input("Nomor Surat", "499/UN17.13/PR.03.01/2026"),
        'lampiran': col2.text_input("Lampiran", "1 (satu) berkas"),
        'hal': st.text_input("Hal", "Tindak Lanjut Permintaan Data"),
        'tujuan': st.text_area("Tujuan Surat"),
        'dekan_nama': "Prof. Dr. M. Bahri Arifin, M.Hum.",
        'dekan_nip': "196211271989031004"
    }
    
    isi_poin = st.text_area("Poin-poin isi surat:")
    
    if st.button("Generate Surat"):
        narasi = generate_surat_ai(meta['hal'], meta['tujuan'], isi_poin)
        if narasi:
            st.session_state['surat_narasi'] = narasi
            st.success("Surat berhasil disusun!")

    if 'surat_narasi' in st.session_state:
        st.write(st.session_state['surat_narasi'])
        if st.download_button("Download Docx", build_surat_docx(meta, st.session_state['surat_narasi']), "surat.docx"):
            log_audit("BUAT SURAT", f"Hal: {meta['hal']}")

show_page()
