import streamlit as st
import pandas as pd
import os
from io import BytesIO

# ==========================================
# 1. KONFIGURASI HALAMAN & DATABASE
# ==========================================
st.set_page_config(page_title="Kompiler Usulan Anggaran FIB", page_icon="📝", layout="wide")

FILE_DATABASE = "database_usulan_prodi.csv"

def load_data():
    if os.path.exists(FILE_DATABASE):
        df = pd.read_csv(FILE_DATABASE)
        if "Status" not in df.columns:
            df["Status"] = "Menunggu Review"
        if "Catatan_Fakultas" not in df.columns:
            df["Catatan_Fakultas"] = "-"
        return df
    else:
        return pd.DataFrame(columns=[
            "Tanggal_Input", "Program_Studi", "Nama_Kegiatan", 
            "Rincian_Belanja", "Volume", "Satuan", "Harga_Satuan", 
            "Total_Usulan", "Prioritas", "Status", "Catatan_Fakultas"
        ])

def save_data(df):
    df.to_csv(FILE_DATABASE, index=False)

df_usulan = load_data()

# ==========================================
# 2. NAVIGASI SIDEBAR
# ==========================================
with st.sidebar:
    st.header("Sistem Perencanaan")
    menu = st.radio("Pilih Mode Akses:", ["📤 Form Usulan Prodi", "📊 Dashboard Fakultas (Admin)"])
    st.markdown("---")
    st.info("Data tersimpan otomatis di 'database_usulan_prodi.csv'.")

# ==========================================
# MODE 1: FORMULIR INPUT UNTUK PRODI
# ==========================================
if menu == "📤 Form Usulan Prodi":
    st.title("📤 Formulir Usulan Kegiatan & Anggaran")
    st.subheader("Penyusunan RKA Tahun Anggaran 2026")
    
    with st.form("form_usulan", clear_on_submit=True):
        st.markdown("### 1️⃣ Informasi Utama Kegiatan")
        col1, col2, col3 = st.columns([1, 2, 1])
        with col1:
            prodi = st.selectbox("Program Studi / Unit:", [
                "Sastra Indonesia", "Sastra Inggris", "Etnomusikologi",
                "Kajian Budaya (S2)", "Pariwisata Budaya"
            ])
        with col2:
            nama_kegiatan = st.text_input("Nama Kegiatan Utama")
        with col3:
            prioritas = st.selectbox("Prioritas:", ["Tinggi", "Sedang", "Rendah"])
            
        st.markdown("---")
        st.markdown("### 2️⃣ Rincian RAB")
        df_template = pd.DataFrame([{"Rincian Belanja": "", "Volume": 0, "Satuan": "", "Harga Satuan": 0}])
        edited_df = st.data_editor(df_template, num_rows="dynamic", use_container_width=True, hide_index=True)
        
        submit = st.form_submit_button("Kirim Usulan")
        
        if submit:
            valid_rows = edited_df[edited_df["Rincian Belanja"].str.strip() != ""]
            if not nama_kegiatan.strip() or valid_rows.empty:
                st.error("Nama Kegiatan dan rincian belanja wajib diisi!")
            else:
                data_list = []
                tgl = pd.Timestamp.now().strftime("%Y-%m-%d %H:%M")
                for _, row in valid_rows.iterrows():
                    tot = row["Volume"] * row["Harga Satuan"]
                    data_list.append({
                        "Tanggal_Input": tgl, "Program_Studi": prodi, "Nama_Kegiatan": nama_kegiatan,
                        "Rincian_Belanja": row["Rincian Belanja"], "Volume": row["Volume"],
                        "Satuan": row["Satuan"], "Harga_Satuan": row["Harga Satuan"],
                        "Total_Usulan": tot, "Prioritas": prioritas,
                        "Status": "Menunggu Review", "Catatan_Fakultas": "-"
                    })
                df_usulan = pd.concat([df_usulan, pd.DataFrame(data_list)], ignore_index=True)
                save_data(df_usulan)
                st.success(f"Usulan '{nama_kegiatan}' berhasil dikirim ke Fakultas.")

# ==========================================
# MODE 2: DASHBOARD VISUAL (ADMIN FIB)
# ==========================================
elif menu == "📊 Dashboard Fakultas (Admin)":
    st.title("📊 Dashboard Monitoring & Review Usulan")
    
    if df_usulan.empty:
        st.warning("Belum ada data usulan.")
    else:
        # Metrik Utama
        c1, c2, c3 = st.columns(3)
        c1.metric("Total Dana Diusulkan", f"Rp {df_usulan['Total_Usulan'].sum():,.0f}".replace(',', '.'))
        c2.metric("Kegiatan Menunggu Review", len(df_usulan[df_usulan["Status"] == "Menunggu Review"]["Nama_Kegiatan"].unique()))
        c3.metric("Prodi Berpartisipasi", df_usulan["Program_Studi"].nunique())

        st.markdown("---")
        
        # TAB MENU
        tab1, tab2, tab3 = st.tabs(["📋 Review Per Prodi", "🗑️ Manajemen Data (Hapus)", "🤖 Komparasi & Insight Pintar"])
        
        # --- TAB 1: REVIEW DATA ---
        with tab1:
            prodi_list = sorted(df_usulan["Program_Studi"].unique())
            selected_prodi = st.selectbox("Pilih Prodi untuk Review:", prodi_list)
            
            df_prodi = df_usulan[df_usulan["Program_Studi"] == selected_prodi]
            kegiatan_list = df_prodi["Nama_Kegiatan"].unique()

            st.write(f"Daftar Kegiatan dari **{selected_prodi}**:")

            for keg in kegiatan_list:
                df_keg = df_prodi[df_prodi["Nama_Kegiatan"] == keg].copy()
                total_keg = df_keg["Total_Usulan"].sum()
                status_saat_ini = df_keg["Status"].iloc[0]
                catatan_saat_ini = df_keg["Catatan_Fakultas"].iloc[0]
                
                status_icon = "⏳"
                if status_saat_ini == "Disetujui": status_icon = "✅"
                elif status_saat_ini == "Perlu Revisi": status_icon = "⚠️"
                elif status_saat_ini == "Ditolak": status_icon = "❌"
                
                with st.expander(f"{status_icon} {keg.upper()} | Rp {total_keg:,.0f} | Status: {status_saat_ini}"):
                    
                    st.markdown("#### 📝 Panel Review Fakultas")
                    col_stat, col_note = st.columns([1, 2])
                    
                    with col_stat:
                        new_status = st.selectbox(
                            "Update Status:", 
                            ["Menunggu Review", "Disetujui", "Perlu Revisi", "Ditolak"],
                            index=["Menunggu Review", "Disetujui", "Perlu Revisi", "Ditolak"].index(status_saat_ini),
                            key=f"stat_{selected_prodi}_{keg}"
                        )
                    with col_note:
                        new_note = st.text_area("Catatan/Alasan:", value=catatan_saat_ini, key=f"note_{selected_prodi}_{keg}", height=70)
                    
                    if st.button("Update Status & Catatan", key=f"btn_update_{keg}"):
                        mask = (df_usulan["Program_Studi"] == selected_prodi) & (df_usulan["Nama_Kegiatan"] == keg)
                        df_usulan.loc[mask, "Status"] = new_status
                        df_usulan.loc[mask, "Catatan_Fakultas"] = new_note
                        save_data(df_usulan)
                        st.success(f"Status diperbarui!")
                        st.rerun()

                    st.markdown("---")
                    st.markdown("#### 📋 Rincian Belanja")
                    df_keg["Hapus"] = False
                    df_display = df_keg[["Hapus", "Rincian_Belanja", "Volume", "Satuan", "Harga_Satuan", "Total_Usulan"]]
                    
                    edited_df = st.data_editor(
                        df_display,
                        column_config={
                            "Hapus": st.column_config.CheckboxColumn("Hapus?", default=False),
                            "Rincian_Belanja": st.column_config.TextColumn("Rincian Belanja", disabled=True),
                            "Total_Usulan": st.column_config.NumberColumn("Subtotal (Rp)", format="Rp %d")
                        },
                        hide_index=True, use_container_width=True, key=f"editor_{selected_prodi}_{keg}"
                    )
                    
                    if st.button("✂️ Hapus Rincian Tercentang", key=f"del_checked_{keg}"):
                        indices_to_drop = edited_df[edited_df["Hapus"] == True].index
                        if len(indices_to_drop) > 0:
                            df_usulan = df_usulan.drop(index=indices_to_drop)
                            save_data(df_usulan)
                            st.success("Rincian berhasil dihapus.")
                            st.rerun()

            st.markdown("---")
            st.markdown("### 💾 Ekspor Data")
            def to_excel(df_to_save):
                output = BytesIO()
                with pd.ExcelWriter(output, engine='openpyxl') as writer:
                    df_to_save.to_excel(writer, index=False, sheet_name='Kompilasi_Review')
                return output.getvalue()

            st.download_button("📥 Download Excel Hasil Review", data=to_excel(df_usulan), file_name="Rekap_Review_Anggaran_2026.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

        # --- TAB 2: HAPUS DATA ---
        with tab2:
            st.subheader("🗑️ Hapus Data Usulan yang Salah")
            opsi_hapus = {}
            for idx, row in df_usulan.iterrows():
                teks = f"[{row['Program_Studi']}] {row['Nama_Kegiatan']} ➡️ {row['Rincian_Belanja']} | Rp {row['Total_Usulan']:,.0f}".replace(',', '.')
                opsi_hapus[idx] = teks
            
            pilih_hapus = st.selectbox("Pilih Data Rincian yang Ingin Dihapus:", options=list(opsi_hapus.keys()), format_func=lambda x: opsi_hapus[x])
            
            if st.button("🚨 Hapus Rincian Ini", type="primary"):
                df_usulan = df_usulan.drop(index=pilih_hapus).reset_index(drop=True)
                save_data(df_usulan)
                st.success("Data berhasil dihapus!")
                st.rerun()

        # --- TAB 3: INSIGHT PINTAR (PSEUDO-AI) ---
        with tab3:
            st.subheader("🤖 Analisis & Komparasi Otomatis")
            st.write("Sistem membaca seluruh usulan dan menyusun ringkasan eksekutif untuk Anda.")
            
            # Algoritma Pembacaan Data
            total_anggaran = df_usulan['Total_Usulan'].sum()
            prodi_terbesar = df_usulan.groupby('Program_Studi')['Total_Usulan'].sum().idxmax()
            nilai_terbesar = df_usulan.groupby('Program_Studi')['Total_Usulan'].sum().max()
            persentase_terbesar = (nilai_terbesar / total_anggaran) * 100 if total_anggaran > 0 else 0
            
            # Mencari item paling mahal
            item_termahal = df_usulan.loc[df_usulan['Total_Usulan'].idxmax()]
            
            # Status usulan
            status_counts = df_usulan['Status'].value_counts()
            jml_disetujui = status_counts.get("Disetujui", 0)
            jml_menunggu = status_counts.get("Menunggu Review", 0)
            
            # Teks Analisis bergaya AI
            st.markdown("### 💡 Ringkasan Laporan Pimpinan:")
            st.info(f"""
            Berdasarkan data usulan yang masuk hingga hari ini, total anggaran yang diajukan oleh Program Studi mencapai **Rp {total_anggaran:,.0f}**.
            
            * 📊 **Prodi dengan Usulan Tertinggi:** **{prodi_terbesar}** memimpin usulan anggaran sebesar **Rp {nilai_terbesar:,.0f}**. Ini setara dengan **{persentase_terbesar:.1f}%** dari total seluruh usulan di Fakultas Ilmu Budaya.
            * 💸 **Item Rincian Termahal:** Terdapat alokasi dana tunggal terbesar pada Prodi **{item_termahal['Program_Studi']}** untuk rincian belanja **"{item_termahal['Rincian_Belanja']}"** (Kegiatan: {item_termahal['Nama_Kegiatan']}) senilai **Rp {item_termahal['Total_Usulan']:,.0f}**. Mohon cek rasionalitas SBM-nya.
            * ⏳ **Progres Review Fakultas:** Saat ini terdapat **{jml_menunggu} rincian** yang masih menunggu persetujuan (Menunggu Review), dan **{jml_disetujui} rincian** yang telah berstatus Disetujui.
            """)
            
            st.markdown("---")
            st.markdown("### 📊 Visualisasi Perbandingan Prodi")
            
            col_chart1, col_chart2 = st.columns(2)
            
            with col_chart1:
                st.markdown("**1. Komparasi Total Dana per Prodi**")
                rekap_prodi = df_usulan.groupby("Program_Studi")["Total_Usulan"].sum().reset_index()
                st.bar_chart(rekap_prodi.set_index("Program_Studi")["Total_Usulan"])
                
            with col_chart2:
                st.markdown("**2. Jumlah Item Kegiatan per Prodi**")
                jml_kegiatan = df_usulan.groupby("Program_Studi")["Nama_Kegiatan"].nunique().reset_index()
                st.bar_chart(jml_kegiatan.set_index("Program_Studi")["Nama_Kegiatan"])