import streamlit as st
import json
import os
import pandas as pd
from datetime import datetime, timedelta
import plotly.graph_objects as go
import plotly.express as px

# ==================================================
# 1. KONFIGURASI & DATA
# ==================================================

DATA_DIR = "data"
if not os.path.exists(DATA_DIR):
    os.makedirs(DATA_DIR)

CONFIG_FILE = os.path.join(DATA_DIR, "config.json")
MEMBER_FILE = os.path.join(DATA_DIR, "members.json")
TRANSACTION_FILE = os.path.join(DATA_DIR, "transactions.json")
PENGELUARAN_FILE = os.path.join(DATA_DIR, "pengeluaran.json")
DONATUR_FILE = os.path.join(DATA_DIR, "donatur.json")

def load_json(file_path, default=None):
    if default is None:
        default = {} if not isinstance(default, list) else []
    if os.path.exists(file_path):
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            return default
    return default

def save_json(file_path, data):
    with open(file_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

def format_rupiah(nominal):
    if nominal is None:
        return "Rp 0"
    return f"Rp {nominal:,.0f}".replace(",", ".")

def parse_nominal(nominal_str):
    try:
        return int(nominal_str.replace(".", ""))
    except:
        return None

def get_minggu_ke(tanggal_str, tanggal_mulai_str):
    tgl = datetime.strptime(tanggal_str, "%Y-%m-%d")
    mulai = datetime.strptime(tanggal_mulai_str, "%Y-%m-%d")
    selisih = (tgl - mulai).days
    return (selisih // 7) + 1 if selisih >= 0 else 0

def get_week_range(tanggal_mulai_str, minggu_ke):
    mulai = datetime.strptime(tanggal_mulai_str, "%Y-%m-%d")
    start_date = mulai + timedelta(weeks=minggu_ke - 1)
    end_date = start_date + timedelta(days=6)
    return start_date.strftime("%d-%m-%Y"), end_date.strftime("%d-%m-%Y")

def get_total_pemasukan(transactions, donatur):
    total = sum(t.get('nominal', 0) for t in transactions if t.get('jenis') != 'pengeluaran')
    total += sum(d.get('nominal', 0) for d in donatur if d.get('status') == 'SUDAH BAYAR')
    return total

def get_total_pengeluaran(pengeluaran):
    return sum(p.get('nominal', 0) for p in pengeluaran)

def get_target_total(config, members, donatur):
    pemuda_aktif = sum(1 for m in members if m['kategori'] == 'Pemuda' and m.get('status', 'AKTIF') == 'AKTIF')
    orangtua_aktif = sum(1 for m in members if m['kategori'] == 'Orang Tua' and m.get('status', 'AKTIF') == 'AKTIF')
    total_donatur = sum(d.get('nominal', 0) for d in donatur)
    return (pemuda_aktif * config.get('target_pemuda', 1750000)) + \
           (orangtua_aktif * config.get('target_orangtua', 1000000)) + total_donatur

def get_rekomendasi(members, transactions):
    today = datetime.now().strftime("%Y-%m-%d")
    rekom = []
    for member in members:
        if member.get('status', 'AKTIF') != 'AKTIF':
            continue
        t_member = [t for t in transactions if t.get('nama') == member['nama'] and t.get('jenis') != 'pengeluaran']
        if not t_member:
            rekom.append({"nama": member['nama'], "kategori": member['kategori'], "lama": "Belum pernah bayar", "prioritas": "tinggi"})
        else:
            terakhir = max(t['tanggal'] for t in t_member)
            terakhir_dt = datetime.strptime(terakhir, "%Y-%m-%d")
            today_dt = datetime.strptime(today, "%Y-%m-%d")
            lama = (today_dt - terakhir_dt).days // 7
            if lama > 0:
                if lama >= 3:
                    prioritas = "tinggi"
                elif lama == 2:
                    prioritas = "sedang"
                else:
                    prioritas = "rendah"
                rekom.append({"nama": member['nama'], "kategori": member['kategori'], "lama": f"{lama} minggu", "prioritas": prioritas})
    return sorted(rekom, key=lambda x: 0 if x.get('prioritas') == 'tinggi' else (1 if x.get('prioritas') == 'sedang' else 2))

def get_transaksi_per_member(transactions, nama):
    return [t for t in transactions if t.get('nama') == nama and t.get('jenis') != 'pengeluaran']

# ==================================================
# 2. FUNGSI GRAFIK
# ==================================================

def buat_grafik_pemasukan_per_bulan(transactions):
    if not transactions:
        fig = go.Figure()
        fig.add_annotation(text="Belum ada data", x=0.5, y=0.5, showarrow=False)
        fig.update_layout(height=400)
        return fig
    
    pemasukan = [t for t in transactions if t.get('jenis') != 'pengeluaran']
    if not pemasukan:
        fig = go.Figure()
        fig.add_annotation(text="Belum ada data pemasukan", x=0.5, y=0.5, showarrow=False)
        fig.update_layout(height=400)
        return fig
    
    bulan_data = {}
    for t in pemasukan:
        bulan = datetime.strptime(t['tanggal'], "%Y-%m-%d").strftime("%B %Y")
        bulan_data[bulan] = bulan_data.get(bulan, 0) + t.get('nominal', 0)
    
    if not bulan_data:
        fig = go.Figure()
        fig.add_annotation(text="Belum ada data", x=0.5, y=0.5, showarrow=False)
        fig.update_layout(height=400)
        return fig
    
    fig = go.Figure(data=[go.Bar(
        x=list(bulan_data.keys()),
        y=list(bulan_data.values()),
        marker_color='#4CAF50',
        text=[format_rupiah(v) for v in bulan_data.values()],
        textposition='outside'
    )])
    fig.update_layout(
        title="📈 Pemasukan per Bulan",
        xaxis_title="Bulan",
        yaxis_title="Total (Rp)",
        height=400,
        showlegend=False
    )
    return fig

def buat_grafik_pemasukan_per_minggu(transactions, config):
    if not transactions:
        fig = go.Figure()
        fig.add_annotation(text="Belum ada data", x=0.5, y=0.5, showarrow=False)
        fig.update_layout(height=400)
        return fig
    
    pemasukan = [t for t in transactions if t.get('jenis') != 'pengeluaran']
    if not pemasukan:
        fig = go.Figure()
        fig.add_annotation(text="Belum ada data pemasukan", x=0.5, y=0.5, showarrow=False)
        fig.update_layout(height=400)
        return fig
    
    minggu_data = {}
    for t in pemasukan:
        minggu = t.get('minggu_ke', 0)
        if minggu > 0:
            minggu_data[minggu] = minggu_data.get(minggu, 0) + t.get('nominal', 0)
    
    if not minggu_data:
        fig = go.Figure()
        fig.add_annotation(text="Belum ada data", x=0.5, y=0.5, showarrow=False)
        fig.update_layout(height=400)
        return fig
    
    labels = [f"Minggu {m}" for m in sorted(minggu_data.keys())]
    values = [minggu_data[m] for m in sorted(minggu_data.keys())]
    
    fig = go.Figure(data=[go.Bar(
        x=labels,
        y=values,
        marker_color='#2196F3',
        text=[format_rupiah(v) for v in values],
        textposition='outside'
    )])
    fig.update_layout(
        title="📈 Pemasukan per Minggu",
        xaxis_title="Minggu Ke-",
        yaxis_title="Total (Rp)",
        height=400,
        showlegend=False
    )
    return fig

def buat_grafik_pengeluaran(pengeluaran):
    if not pengeluaran:
        fig = go.Figure()
        fig.add_annotation(text="Belum ada pengeluaran", x=0.5, y=0.5, showarrow=False)
        fig.update_layout(height=400)
        return fig
    
    kategori_data = {}
    for p in pengeluaran:
        kategori_data[p['kategori']] = kategori_data.get(p['kategori'], 0) + p.get('nominal', 0)
    
    if not kategori_data:
        fig = go.Figure()
        fig.add_annotation(text="Belum ada data", x=0.5, y=0.5, showarrow=False)
        fig.update_layout(height=400)
        return fig
    
    colors = ['#FF6B6B', '#FFA94D', '#FFD93D', '#6BCB77', '#4D96FF', '#9B59B6']
    fig = go.Figure(data=[go.Pie(
        labels=list(kategori_data.keys()),
        values=list(kategori_data.values()),
        hole=0.3,
        marker=dict(colors=colors[:len(kategori_data)])
    )])
    fig.update_layout(
        title="🥧 Pengeluaran per Kategori",
        height=400
    )
    return fig

def buat_grafik_perbandingan(transactions, pengeluaran, donatur):
    total_pemasukan = get_total_pemasukan(transactions, donatur)
    total_pengeluaran = get_total_pengeluaran(pengeluaran)
    saldo = total_pemasukan - total_pengeluaran
    
    fig = go.Figure(data=[
        go.Bar(name='Pemasukan', x=['Total'], y=[total_pemasukan], marker_color='#4CAF50'),
        go.Bar(name='Pengeluaran', x=['Total'], y=[total_pengeluaran], marker_color='#FF6B6B'),
        go.Bar(name='Saldo', x=['Total'], y=[saldo if saldo > 0 else 0], marker_color='#FFA94D')
    ])
    fig.update_layout(
        title="📊 Perbandingan Pemasukan vs Pengeluaran",
        yaxis_title="Nominal (Rp)",
        height=400,
        barmode='group'
    )
    return fig

def buat_grafik_progress(target, total_pemasukan):
    progress = (total_pemasukan / target * 100) if target > 0 else 0
    
    fig = go.Figure(go.Indicator(
        mode="gauge+number+delta",
        value=progress,
        title={'text': "Progress Target"},
        domain={'x': [0, 1], 'y': [0, 1]},
        gauge={
            'axis': {'range': [0, 100], 'tickwidth': 1},
            'bar': {'color': "#4CAF50" if progress < 100 else "#FF6B6B"},
            'steps': [
                {'range': [0, 50], 'color': "#FF6B6B"},
                {'range': [50, 80], 'color': "#FFD93D"},
                {'range': [80, 100], 'color': "#4CAF50"}
            ],
            'threshold': {
                'line': {'color': "red", 'width': 4},
                'thickness': 0.75,
                'value': 100
            }
        }
    ))
    fig.update_layout(height=350)
    return fig

# ==================================================
# 3. INISIALISASI DATA
# ==================================================

config = load_json(CONFIG_FILE, {})
if not config:
    config = {
        "tanggal_mulai": "2026-09-04",
        "target_pemuda": 1750000,
        "target_orangtua": 1000000
    }
    save_json(CONFIG_FILE, config)

members = load_json(MEMBER_FILE, [])
if not members:
    members = [
        {"id": 1, "nama": "Budi Santoso", "kategori": "Pemuda", "status": "AKTIF", "tanggal_masuk": "2026-09-04"},
        {"id": 2, "nama": "Andi Pratama", "kategori": "Pemuda", "status": "AKTIF", "tanggal_masuk": "2026-09-04"},
        {"id": 3, "nama": "Caca Ananda", "kategori": "Anak-anak", "status": "AKTIF", "tanggal_masuk": "2026-09-04"},
        {"id": 4, "nama": "Ibu Siti", "kategori": "Perempuan", "status": "AKTIF", "tanggal_masuk": "2026-09-04"},
        {"id": 5, "nama": "Pak Ahmad", "kategori": "Orang Tua", "status": "AKTIF", "tanggal_masuk": "2026-09-04"},
    ]
    save_json(MEMBER_FILE, members)

transactions = load_json(TRANSACTION_FILE, [])
pengeluaran = load_json(PENGELUARAN_FILE, [])
donatur = load_json(DONATUR_FILE, [])
if not donatur:
    donatur = [
        {"id": 1, "nama": "Rzky", "kategori": "Donatur 1", "nominal": 5000000, "status": "SUDAH BAYAR", "tanggal_bayar": "2026-09-04"},
        {"id": 2, "nama": "Bowok", "kategori": "Donatur 2", "nominal": 2500000, "status": "BELUM BAYAR", "tanggal_bayar": None}
    ]
    save_json(DONATUR_FILE, donatur)

# ==================================================
# 4. STREAMLIT UI
# ==================================================

st.set_page_config(page_title="Sistem Iuran", page_icon="💰", layout="wide")

# Sidebar
st.sidebar.title("💰 SISTEM IURAN")
st.sidebar.markdown("---")

menu = st.sidebar.radio(
    "📋 Menu",
    ["📊 Dashboard", 
     "👥 Data Member", 
     "💰 Input Pembayaran", 
     "✏️ Edit Pembayaran",
     "💸 Input Pengeluaran",
     "✏️ Edit Pengeluaran",
     "💰 Manajemen Donatur",
     "📈 Grafik & Analisis",
     "🔔 Rekomendasi",
     "📄 Laporan",
     "⚙️ Setting"]
)

st.sidebar.markdown("---")
total_pemasukan = get_total_pemasukan(transactions, donatur)
total_pengeluaran = get_total_pengeluaran(pengeluaran)
saldo = total_pemasukan - total_pengeluaran
st.sidebar.caption(f"💰 Total Pemasukan: {format_rupiah(total_pemasukan)}")
st.sidebar.caption(f"💸 Total Pengeluaran: {format_rupiah(total_pengeluaran)}")
st.sidebar.caption(f"💵 Saldo: {format_rupiah(saldo)}")
st.sidebar.caption(f"👥 Total Member: {len(members)}")

# ==================================================
# 5. HALAMAN DASHBOARD
# ==================================================

if menu == "📊 Dashboard":
    st.title("📊 Dashboard Keuangan")
    st.caption(f"📅 Periode: {config['tanggal_mulai']} - Agustus 2027")
    
    target = get_target_total(config, members, donatur)
    progress = (total_pemasukan / target * 100) if target > 0 else 0
    
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("💰 Total Pemasukan", format_rupiah(total_pemasukan))
    with col2:
        st.metric("💸 Total Pengeluaran", format_rupiah(total_pengeluaran))
    with col3:
        st.metric("💵 Saldo Bersih", format_rupiah(saldo))
    with col4:
        st.metric("🎯 Progress Target", f"{progress:.1f}%")
    
    st.markdown("---")
    
    col1, col2 = st.columns(2)
    with col1:
        st.plotly_chart(buat_grafik_progress(target, total_pemasukan), use_container_width=True)
    with col2:
        st.plotly_chart(buat_grafik_perbandingan(transactions, pengeluaran, donatur), use_container_width=True)
    
    st.markdown("---")
    st.plotly_chart(buat_grafik_pemasukan_per_bulan(transactions), use_container_width=True)

# ==================================================
# 6. HALAMAN DATA MEMBER
# ==================================================

elif menu == "👥 Data Member":
    st.title("👥 Manajemen Member")
    
    # Tambah Member
    with st.expander("➕ Tambah Member Baru"):
        col1, col2 = st.columns(2)
        with col1:
            nama_baru = st.text_input("Nama")
        with col2:
            kategori_baru = st.selectbox("Kategori", ["Pemuda", "Orang Tua", "Anak-anak", "Perempuan"])
        
        if st.button("➕ Tambah Member", use_container_width=True):
            if nama_baru:
                new_id = max([m['id'] for m in members]) + 1 if members else 1
                members.append({
                    "id": new_id,
                    "nama": nama_baru,
                    "kategori": kategori_baru,
                    "status": "AKTIF",
                    "tanggal_masuk": datetime.now().strftime("%Y-%m-%d")
                })
                save_json(MEMBER_FILE, members)
                st.success(f"✅ Member {nama_baru} berhasil ditambahkan!")
                st.rerun()
            else:
                st.error("❌ Nama harus diisi!")
    
    # Edit Member
    with st.expander("✏️ Edit Member"):
        if members:
            member_options = {f"{m['nama']} ({m['kategori']})": m['id'] for m in members}
            selected = st.selectbox("Pilih Member", list(member_options.keys()))
            member_id = member_options[selected]
            member = next(m for m in members if m['id'] == member_id)
            
            col1, col2, col3 = st.columns(3)
            with col1:
                nama_baru = st.text_input("Nama Baru", value=member['nama'])
            with col2:
                kategori_baru = st.selectbox("Kategori Baru", ["Pemuda", "Orang Tua", "Anak-anak", "Perempuan"], 
                                           index=["Pemuda", "Orang Tua", "Anak-anak", "Perempuan"].index(member['kategori']))
            with col3:
                status_baru = st.selectbox("Status Baru", ["AKTIF", "NONAKTIF"], 
                                          index=["AKTIF", "NONAKTIF"].index(member.get('status', 'AKTIF')))
            
            if st.button("💾 Simpan Perubahan", use_container_width=True):
                member['nama'] = nama_baru
                member['kategori'] = kategori_baru
                member['status'] = status_baru
                save_json(MEMBER_FILE, members)
                st.success("✅ Member berhasil diupdate!")
                st.rerun()
        else:
            st.info("Belum ada member.")
    
    # Hapus Member
    with st.expander("🗑️ Hapus Member"):
        if members:
            member_options = {f"{m['nama']} ({m['kategori']})": m['id'] for m in members}
            selected = st.selectbox("Pilih Member yang akan dihapus", list(member_options.keys()))
            member_id = member_options[selected]
            member = next(m for m in members if m['id'] == member_id)
            
            st.warning(f"⚠️ Anda akan menghapus member: **{member['nama']}**")
            st.warning("⚠️ Semua transaksi member ini juga akan dihapus!")
            
            if st.button("🗑️ Hapus Permanen", use_container_width=True):
                # Hapus transaksi member
                transactions = [t for t in transactions if t.get('nama') != member['nama']]
                save_json(TRANSACTION_FILE, transactions)
                # Hapus member
                members = [m for m in members if m['id'] != member_id]
                save_json(MEMBER_FILE, members)
                st.success(f"✅ Member {member['nama']} berhasil dihapus!")
                st.rerun()
        else:
            st.info("Belum ada member.")
    
    # Daftar Member
    st.markdown("---")
    st.write("### 📋 Daftar Member")
    
    if members:
        df = pd.DataFrame(members)
        df['Status'] = df['status'].apply(lambda x: f"🟢 {x}" if x == 'AKTIF' else f"🔴 {x}")
        st.dataframe(df[['id', 'nama', 'kategori', 'Status', 'tanggal_masuk']].rename(columns={
            'id': 'ID', 'nama': 'Nama', 'kategori': 'Kategori', 'tanggal_masuk': 'Tanggal Masuk'
        }), use_container_width=True)
    else:
        st.info("Belum ada member.")

# ==================================================
# 7. HALAMAN INPUT PEMBAYARAN
# ==================================================

elif menu == "💰 Input Pembayaran":
    st.title("💰 Input Pembayaran Mingguan")
    
    today = datetime.now().strftime("%Y-%m-%d")
    minggu_ke = get_minggu_ke(today, config['tanggal_mulai'])
    start_week, end_week = get_week_range(config['tanggal_mulai'], minggu_ke)
    
    st.caption(f"📅 Minggu ke-{minggu_ke} | Periode: {start_week} - {end_week}")
    
    active_members = [m for m in members if m.get('status', 'AKTIF') == 'AKTIF']
    
    if not active_members:
        st.warning("Belum ada member aktif.")
    else:
        st.write("### 📋 Daftar Tagihan Minggu Ini")
        
        data_input = {}
        for m in active_members:
            data_input[m['id']] = st.number_input(
                f"{m['nama']} ({m['kategori']})",
                min_value=0,
                value=0,
                step=10000,
                key=f"pay_{m['id']}"
            )
        
        if st.button("💾 Simpan Semua", use_container_width=True):
            saved = 0
            for member_id, nominal in data_input.items():
                member = next(m for m in members if m['id'] == member_id)
                transactions.append({
                    "nama": member['nama'],
                    "kategori": member['kategori'],
                    "nominal": nominal,
                    "tanggal": today,
                    "minggu_ke": minggu_ke,
                    "jenis": "iuran"
                })
                saved += 1
            save_json(TRANSACTION_FILE, transactions)
            st.success(f"✅ {saved} pembayaran berhasil disimpan!")
            st.rerun()
        
        # Rekap
        st.markdown("---")
        st.write("### 📊 Rekap Minggu Ini")
        trans_minggu = [t for t in transactions if t.get('minggu_ke') == minggu_ke and t.get('jenis') != 'pengeluaran']
        total_minggu = sum(t.get('nominal', 0) for t in trans_minggu)
        total_bayar = len(set(t.get('nama') for t in trans_minggu if t.get('nominal', 0) > 0))
        total_belum = len(active_members) - total_bayar
        
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Total Bayar", format_rupiah(total_minggu))
        with col2:
            st.metric("Sudah Bayar", f"{total_bayar} orang")
        with col3:
            st.metric("Belum Bayar", f"{total_belum} orang")

# ==================================================
# 8. HALAMAN EDIT PEMBAYARAN
# ==================================================

elif menu == "✏️ Edit Pembayaran":
    st.title("✏️ Edit Pembayaran")
    
    if not transactions:
        st.info("Belum ada transaksi.")
    else:
        # Pilih member
        member_names = list(set(t.get('nama') for t in transactions if t.get('jenis') != 'pengeluaran'))
        if not member_names:
            st.info("Belum ada transaksi pembayaran.")
        else:
            selected_member = st.selectbox("Pilih Member", member_names)
            
            trans_member = get_transaksi_per_member(transactions, selected_member)
            if not trans_member:
                st.info(f"Member {selected_member} belum punya transaksi.")
            else:
                # Tampilkan transaksi
                trans_data = []
                for i, t in enumerate(trans_member):
                    trans_data.append({
                        "No": i + 1,
                        "Tanggal": t.get('tanggal', '-'),
                        "Nominal": format_rupiah(t.get('nominal', 0)),
                        "Minggu": t.get('minggu_ke', '-')
                    })
                st.dataframe(pd.DataFrame(trans_data), use_container_width=True)
                
                # Pilih transaksi yang akan diedit
                trans_options = [f"No {i+1} - {t.get('tanggal', '-')} - {format_rupiah(t.get('nominal', 0))}" for i, t in enumerate(trans_member)]
                selected_idx = st.selectbox("Pilih Transaksi yang akan diedit", range(len(trans_options)), format_func=lambda x: trans_options[x])
                
                trans = trans_member[selected_idx]
                
                st.write("### 📝 Edit Data")
                col1, col2 = st.columns(2)
                with col1:
                    tanggal_baru = st.date_input("Tanggal Baru", value=datetime.strptime(trans.get('tanggal', datetime.now().strftime("%Y-%m-%d")), "%Y-%m-%d"))
                with col2:
                    nominal_baru = st.text_input("Nominal Baru (contoh: 500.000)", value=str(trans.get('nominal', 0)).replace(".", ""))
                
                if st.button("💾 Simpan Perubahan", use_container_width=True):
                    nominal = parse_nominal(nominal_baru)
                    if nominal is not None:
                        trans['tanggal'] = tanggal_baru.strftime("%Y-%m-%d")
                        trans['nominal'] = nominal
                        trans['minggu_ke'] = get_minggu_ke(trans['tanggal'], config['tanggal_mulai'])
                        save_json(TRANSACTION_FILE, transactions)
                        st.success("✅ Transaksi berhasil diupdate!")
                        st.rerun()
                    else:
                        st.error("❌ Format nominal salah! Gunakan titik (contoh: 500.000)")

# ==================================================
# 9. HALAMAN INPUT PENGELUARAN
# ==================================================

elif menu == "💸 Input Pengeluaran":
    st.title("💸 Input Pengeluaran")
    
    with st.form("form_pengeluaran"):
        col1, col2 = st.columns(2)
        with col1:
            kategori = st.text_input("Kategori", placeholder="Contoh: Jajan, Makanan, DLL")
            nominal = st.text_input("Nominal (contoh: 500.000)")
        with col2:
            tanggal = st.date_input("Tanggal", value=datetime.now().date())
            keterangan = st.text_input("Keterangan")
        
        if st.form_submit_button("💾 Simpan Pengeluaran", use_container_width=True):
            nominal_int = parse_nominal(nominal)
            if kategori and nominal_int and nominal_int > 0:
                pengeluaran.append({
                    "kategori": kategori,
                    "nominal": nominal_int,
                    "tanggal": tanggal.strftime("%Y-%m-%d"),
                    "keterangan": keterangan
                })
                save_json(PENGELUARAN_FILE, pengeluaran)
                st.success(f"✅ Pengeluaran {kategori} {format_rupiah(nominal_int)} berhasil disimpan!")
                st.rerun()
            else:
                st.error("❌ Kategori dan nominal harus diisi dengan benar!")
    
    st.markdown("---")
    st.write("### 📋 Riwayat Pengeluaran")
    if pengeluaran:
        df = pd.DataFrame(pengeluaran)
        df['Nominal'] = df['nominal'].apply(format_rupiah)
        st.dataframe(df[['tanggal', 'kategori', 'Nominal', 'keterangan']].rename(columns={
            'tanggal': 'Tanggal', 'kategori': 'Kategori', 'keterangan': 'Keterangan'
        }), use_container_width=True)
        st.caption(f"Total Pengeluaran: {format_rupiah(sum(p['nominal'] for p in pengeluaran))}")

# ==================================================
# 10. HALAMAN EDIT PENGELUARAN
# ==================================================

elif menu == "✏️ Edit Pengeluaran":
    st.title("✏️ Edit Pengeluaran")
    
    if not pengeluaran:
        st.info("Belum ada pengeluaran.")
    else:
        # Pilih pengeluaran
        pengeluaran_options = [f"No {i+1} - {p.get('tanggal', '-')} - {p.get('kategori', '-')} - {format_rupiah(p.get('nominal', 0))}" for i, p in enumerate(pengeluaran)]
        selected_idx = st.selectbox("Pilih Pengeluaran yang akan diedit", range(len(pengeluaran_options)), format_func=lambda x: pengeluaran_options[x])
        
        p = pengeluaran[selected_idx]
        
        st.write("### 📝 Edit Data")
        col1, col2 = st.columns(2)
        with col1:
            kategori_baru = st.text_input("Kategori Baru", value=p.get('kategori', ''))
            nominal_baru = st.text_input("Nominal Baru (contoh: 500.000)", value=str(p.get('nominal', 0)).replace(".", ""))
        with col2:
            tanggal_baru = st.date_input("Tanggal Baru", value=datetime.strptime(p.get('tanggal', datetime.now().strftime("%Y-%m-%d")), "%Y-%m-%d"))
            keterangan_baru = st.text_input("Keterangan Baru", value=p.get('keterangan', ''))
        
        if st.button("💾 Simpan Perubahan", use_container_width=True):
            nominal_int = parse_nominal(nominal_baru)
            if kategori_baru and nominal_int and nominal_int > 0:
                p['kategori'] = kategori_baru
                p['nominal'] = nominal_int
                p['tanggal'] = tanggal_baru.strftime("%Y-%m-%d")
                p['keterangan'] = keterangan_baru
                save_json(PENGELUARAN_FILE, pengeluaran)
                st.success("✅ Pengeluaran berhasil diupdate!")
                st.rerun()
            else:
                st.error("❌ Kategori dan nominal harus diisi dengan benar!")

# ==================================================
# 11. HALAMAN MANAJEMEN DONATUR
# ==================================================

elif menu == "💰 Manajemen Donatur":
    st.title("💰 Manajemen Donatur")
    
    # Tambah Donatur
    with st.expander("➕ Tambah Donatur"):
        col1, col2 = st.columns(2)
        with col1:
            nama_donatur = st.text_input("Nama Donatur")
            nominal_donatur = st.text_input("Nominal (contoh: 5.000.000)")
        with col2:
            kategori_donatur = st.selectbox("Kategori", ["Donatur 1", "Donatur 2"])
            status_donatur = st.selectbox("Status", ["SUDAH BAYAR", "BELUM BAYAR"])
        
        if st.button("➕ Tambah Donatur", use_container_width=True):
            nominal_int = parse_nominal(nominal_donatur)
            if nama_donatur and nominal_int and nominal_int > 0:
                new_id = max([d['id'] for d in donatur]) + 1 if donatur else 1
                donatur.append({
                    "id": new_id,
                    "nama": nama_donatur,
                    "kategori": kategori_donatur,
                    "nominal": nominal_int,
                    "status": status_donatur,
                    "tanggal_bayar": datetime.now().strftime("%Y-%m-%d") if status_donatur == "SUDAH BAYAR" else None
                })
                save_json(DONATUR_FILE, donatur)
                st.success(f"✅ Donatur {nama_donatur} berhasil ditambahkan!")
                st.rerun()
            else:
                st.error("❌ Nama dan nominal harus diisi dengan benar!")
    
    # Edit Donatur
    with st.expander("✏️ Edit Donatur"):
        if donatur:
            donatur_options = {f"{d['nama']} ({d.get('kategori', 'Donatur')}) - {format_rupiah(d['nominal'])}": d['id'] for d in donatur}
            selected = st.selectbox("Pilih Donatur", list(donatur_options.keys()))
            donatur_id = donatur_options[selected]
            d = next(x for x in donatur if x['id'] == donatur_id)
            
            col1, col2 = st.columns(2)
            with col1:
                nama_baru = st.text_input("Nama Baru", value=d['nama'])
                nominal_baru = st.text_input("Nominal Baru", value=str(d['nominal']).replace(".", ""))
            with col2:
                kategori_baru = st.selectbox("Kategori Baru", ["Donatur 1", "Donatur 2"], 
                                           index=["Donatur 1", "Donatur 2"].index(d.get('kategori', 'Donatur 1')))
                status_baru = st.selectbox("Status Baru", ["SUDAH BAYAR", "BELUM BAYAR"],
                                         index=["SUDAH BAYAR", "BELUM BAYAR"].index(d.get('status', 'BELUM BAYAR')))
            
            if st.button("💾 Simpan Perubahan Donatur", use_container_width=True):
                nominal_int = parse_nominal(nominal_baru)
                if nominal_int and nominal_int > 0:
                    d['nama'] = nama_baru
                    d['nominal'] = nominal_int
                    d['kategori'] = kategori_baru
                    d['status'] = status_baru
                    if status_baru == "SUDAH BAYAR" and not d.get('tanggal_bayar'):
                        d['tanggal_bayar'] = datetime.now().strftime("%Y-%m-%d")
                    save_json(DONATUR_FILE, donatur)
                    st.success("✅ Donatur berhasil diupdate!")
                    st.rerun()
                else:
                    st.error("❌ Nominal harus diisi dengan benar!")
        else:
            st.info("Belum ada donatur.")
    
    # Hapus Donatur
    with st.expander("🗑️ Hapus Donatur"):
        if donatur:
            donatur_options = {f"{d['nama']} ({d.get('kategori', 'Donatur')})": d['id'] for d in donatur}
            selected = st.selectbox("Pilih Donatur yang akan dihapus", list(donatur_options.keys()))
            donatur_id = donatur_options[selected]
            d = next(x for x in donatur if x['id'] == donatur_id)
            
            st.warning(f"⚠️ Anda akan menghapus donatur: **{d['nama']}**")
            if st.button("🗑️ Hapus Donatur", use_container_width=True):
                donatur = [x for x in donatur if x['id'] != donatur_id]
                save_json(DONATUR_FILE, donatur)
                st.success(f"✅ Donatur {d['nama']} berhasil dihapus!")
                st.rerun()
        else:
            st.info("Belum ada donatur.")
    
    # Daftar Donatur
    st.markdown("---")
    st.write("### 📋 Daftar Donatur")
    if donatur:
        df = pd.DataFrame(donatur)
        df['Nominal'] = df['nominal'].apply(format_rupiah)
        df['Status'] = df['status'].apply(lambda x: f"✅ {x}" if x == 'SUDAH BAYAR' else f"❌ {x}")
        st.dataframe(df[['nama', 'kategori', 'Nominal', 'Status', 'tanggal_bayar']].rename(columns={
            'nama': 'Nama', 'kategori': 'Kategori', 'tanggal_bayar': 'Tanggal Bayar'
        }), use_container_width=True)
        
        donatur1 = sum(d['nominal'] for d in donatur if d.get('kategori') == 'Donatur 1')
        donatur2 = sum(d['nominal'] for d in donatur if d.get('kategori') == 'Donatur 2')
        col1, col2 = st.columns(2)
        with col1:
            st.metric("💰 Total Donatur 1", format_rupiah(donatur1))
        with col2:
            st.metric("💰 Total Donatur 2", format_rupiah(donatur2))

# ==================================================
# 12. HALAMAN GRAFIK
# ==================================================

elif menu == "📈 Grafik & Analisis":
    st.title("📈 Grafik & Analisis")
    
    tab1, tab2, tab3, tab4 = st.tabs(["📊 Pemasukan", "📊 Pengeluaran", "📊 Perbandingan", "🎯 Progress"])
    
    with tab1:
        st.plotly_chart(buat_grafik_pemasukan_per_bulan(transactions), use_container_width=True)
        st.plotly_chart(buat_grafik_pemasukan_per_minggu(transactions, config), use_container_width=True)
    
    with tab2:
        st.plotly_chart(buat_grafik_pengeluaran(pengeluaran), use_container_width=True)
    
    with tab3:
        st.plotly_chart(buat_grafik_perbandingan(transactions, pengeluaran, donatur), use_container_width=True)
    
    with tab4:
        target = get_target_total(config, members, donatur)
        st.plotly_chart(buat_grafik_progress(target, total_pemasukan), use_container_width=True)

# ==================================================
# 13. HALAMAN REKOMENDASI
# ==================================================

elif menu == "🔔 Rekomendasi":
    st.title("🔔 Rekomendasi Penagihan")
    st.caption(f"📅 Per: {datetime.now().strftime('%d %B %Y')}")
    
    rekom = get_rekomendasi(members, transactions)
    
    if not rekom:
        st.success("✅ Semua member sudah bayar! Tidak ada rekomendasi.")
    else:
        tinggi = [r for r in rekom if r.get('prioritas') == 'tinggi']
        sedang = [r for r in rekom if r.get('prioritas') == 'sedang']
        rendah = [r for r in rekom if r.get('prioritas') == 'rendah']
        
        if tinggi:
            st.subheader("🔴 PRIORITAS TINGGI (3+ minggu tidak bayar)")
            st.dataframe(pd.DataFrame(tinggi), use_container_width=True)
        
        if sedang:
            st.subheader("🟡 PRIORITAS SEDANG (2 minggu tidak bayar)")
            st.dataframe(pd.DataFrame(sedang), use_container_width=True)
        
        if rendah:
            st.subheader("🟢 PRIORITAS RENDAH (1 minggu tidak bayar)")
            st.dataframe(pd.DataFrame(rendah), use_container_width=True)

# ==================================================
# 14. HALAMAN LAPORAN
# ==================================================

elif menu == "📄 Laporan":
    st.title("📄 Laporan Keuangan")
    
    target = get_target_total(config, members, donatur)
    progress = (total_pemasukan / target * 100) if target > 0 else 0
    
    col1, col2 = st.columns(2)
    with col1:
        st.metric("💰 Total Pemasukan", format_rupiah(total_pemasukan))
        st.metric("💸 Total Pengeluaran", format_rupiah(total_pengeluaran))
        st.metric("💵 Saldo Bersih", format_rupiah(saldo))
    with col2:
        st.metric("🎯 Target", format_rupiah(target))
        st.metric("📊 Progress", f"{progress:.1f}%")
        st.metric("👥 Total Member Aktif", len([m for m in members if m.get('status', 'AKTIF') == 'AKTIF']))
    
    st.markdown("---")
    st.write("### 📆 Rincian Pemasukan per Kategori")
    
    kategori_total = {"Pemuda": 0, "Orang Tua": 0, "Anak-anak": 0, "Perempuan": 0}
    for t in transactions:
        if t.get('jenis') == 'pengeluaran':
            continue
        if t.get('kategori') in kategori_total:
            kategori_total[t['kategori']] += t.get('nominal', 0)
    
    donatur1_total = sum(d.get('nominal', 0) for d in donatur if d.get('kategori') == 'Donatur 1')
    donatur2_total = sum(d.get('nominal', 0) for d in donatur if d.get('kategori') == 'Donatur 2')
    
    kategori_data = []
    for k, v in kategori_total.items():
        if v > 0:
            kategori_data.append({"Kategori": k, "Total": format_rupiah(v)})
    if donatur1_total > 0:
        kategori_data.append({"Kategori": "Donatur 1", "Total": format_rupiah(donatur1_total)})
    if donatur2_total > 0:
        kategori_data.append({"Kategori": "Donatur 2", "Total": format_rupiah(donatur2_total)})
    
    if kategori_data:
        st.dataframe(pd.DataFrame(kategori_data), use_container_width=True)

# ==================================================
# 15. HALAMAN SETTING
# ==================================================

elif menu == "⚙️ Setting":
    st.title("⚙️ Pengaturan")
    
    st.write("### 📅 Konfigurasi")
    
    col1, col2 = st.columns(2)
    with col1:
        tanggal_mulai = st.date_input("Tanggal Mulai", value=datetime.strptime(config.get('tanggal_mulai', '2026-09-04'), "%Y-%m-%d"))
    with col2:
        target_pemuda = st.text_input("Target Iuran Pemuda", value=str(config.get('target_pemuda', 1750000)).replace(".", ""))
        target_orangtua = st.text_input("Target Iuran Orang Tua", value=str(config.get('target_orangtua', 1000000)).replace(".", ""))
    
    if st.button("💾 Simpan Konfigurasi", use_container_width=True):
        target_pemuda_int = parse_nominal(target_pemuda)
        target_orangtua_int = parse_nominal(target_orangtua)
        
        if target_pemuda_int and target_orangtua_int:
            config['tanggal_mulai'] = tanggal_mulai.strftime("%Y-%m-%d")
            config['target_pemuda'] = target_pemuda_int
            config['target_orangtua'] = target_orangtua_int
            save_json(CONFIG_FILE, config)
            st.success("✅ Konfigurasi berhasil disimpan!")
            st.rerun()
        else:
            st.error("❌ Format target salah! Gunakan titik (contoh: 1.750.000)")