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

def get_total_pemasukan(transactions):
    total = sum(t.get('nominal', 0) for t in transactions if t.get('jenis') != 'pengeluaran')
    return total

def get_total_pengeluaran(pengeluaran):
    return sum(p.get('nominal', 0) for p in pengeluaran)

def get_target_total(config, members):
    donatur1 = sum(1 for m in members if m['kategori'] == 'Donatur 1' and m.get('status', 'AKTIF') == 'AKTIF')
    donatur2 = sum(1 for m in members if m['kategori'] == 'Donatur 2' and m.get('status', 'AKTIF') == 'AKTIF')
    pemuda = sum(1 for m in members if m['kategori'] == 'Pemuda' and m.get('status', 'AKTIF') == 'AKTIF')
    orangtua = sum(1 for m in members if m['kategori'] == 'Orang Tua' and m.get('status', 'AKTIF') == 'AKTIF')
    target = (donatur1 * config.get('target_donatur1', 5000000)) + \
             (donatur2 * config.get('target_donatur2', 2500000)) + \
             (pemuda * config.get('target_pemuda', 1500000)) + \
             (orangtua * config.get('target_orangtua', 1000000))
    return target

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
# 2. FUNGSI IKON UNTUK SIDEBAR
# ==================================================

def get_icon(menu_name):
    icons = {
        "Dashboard": "chart-pie",
        "Manajemen Member": "users",
        "Input Pembayaran": "hand-holding-usd",
        "Edit Pembayaran": "pen",
        "Input Pengeluaran": "money-bill-wave",
        "Edit Pengeluaran": "edit",
        "Grafik & Analisis": "chart-line",
        "Rekomendasi": "bell",
        "Laporan & Rekap": "file-alt",
        "Setting": "cog"
    }
    return icons.get(menu_name, "circle")

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
        title="Pemasukan per Bulan",
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
        title="Pemasukan per Minggu",
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
        title="Pengeluaran per Kategori",
        height=400
    )
    return fig

def buat_grafik_perbandingan(transactions, pengeluaran):
    total_pemasukan = get_total_pemasukan(transactions)
    total_pengeluaran = get_total_pengeluaran(pengeluaran)
    saldo = total_pemasukan - total_pengeluaran
    
    fig = go.Figure(data=[
        go.Bar(name='Pemasukan', x=['Total'], y=[total_pemasukan], marker_color='#4CAF50'),
        go.Bar(name='Pengeluaran', x=['Total'], y=[total_pengeluaran], marker_color='#FF6B6B'),
        go.Bar(name='Saldo', x=['Total'], y=[saldo if saldo > 0 else 0], marker_color='#FFA94D')
    ])
    fig.update_layout(
        title="Perbandingan Pemasukan vs Pengeluaran",
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
        "tanggal_mulai": "2026-09-11",
        "target_donatur1": 5000000,
        "target_donatur2": 2500000,
        "target_pemuda": 1500000,
        "target_orangtua": 1000000
    }
    save_json(CONFIG_FILE, config)

members = load_json(MEMBER_FILE, [])
if not members:
    members = [
        {"id": 1, "nama": "Juned", "kategori": "Donatur 1", "status": "AKTIF", "tanggal_masuk": "2026-09-11"},
        {"id": 2, "nama": "Anto", "kategori": "Donatur 1", "status": "AKTIF", "tanggal_masuk": "2026-09-11"},
        {"id": 3, "nama": "Heri", "kategori": "Donatur 1", "status": "AKTIF", "tanggal_masuk": "2026-09-11"},
        {"id": 4, "nama": "Harjo", "kategori": "Donatur 1", "status": "AKTIF", "tanggal_masuk": "2026-09-11"},
        {"id": 5, "nama": "Kempeng", "kategori": "Donatur 1", "status": "AKTIF", "tanggal_masuk": "2026-09-11"},
        {"id": 6, "nama": "Sholeh", "kategori": "Donatur 1", "status": "AKTIF", "tanggal_masuk": "2026-09-11"},
        {"id": 7, "nama": "Junaidy tb (titis)", "kategori": "Donatur 1", "status": "AKTIF", "tanggal_masuk": "2026-09-11"},
        {"id": 8, "nama": "Muslimin (edwin)", "kategori": "Donatur 1", "status": "AKTIF", "tanggal_masuk": "2026-09-11"},
        {"id": 9, "nama": "Yanto", "kategori": "Donatur 1", "status": "AKTIF", "tanggal_masuk": "2026-09-11"},
        {"id": 10, "nama": "Asrofi", "kategori": "Donatur 1", "status": "AKTIF", "tanggal_masuk": "2026-09-11"},
        {"id": 11, "nama": "Akrom", "kategori": "Donatur 1", "status": "AKTIF", "tanggal_masuk": "2026-09-11"},
        {"id": 12, "nama": "Apip (dewa puyuh)", "kategori": "Donatur 1", "status": "AKTIF", "tanggal_masuk": "2026-09-11"},
        {"id": 13, "nama": "Viori salon (khoiri)", "kategori": "Donatur 1", "status": "AKTIF", "tanggal_masuk": "2026-09-11"},
        {"id": 14, "nama": "Bowok", "kategori": "Donatur 2", "status": "AKTIF", "tanggal_masuk": "2026-09-11"},
        {"id": 15, "nama": "Aji", "kategori": "Donatur 2", "status": "AKTIF", "tanggal_masuk": "2026-09-11"},
        {"id": 16, "nama": "Borod", "kategori": "Donatur 2", "status": "AKTIF", "tanggal_masuk": "2026-09-11"},
        {"id": 17, "nama": "Kholis", "kategori": "Donatur 2", "status": "AKTIF", "tanggal_masuk": "2026-09-11"},
        {"id": 18, "nama": "Apip ar", "kategori": "Donatur 2", "status": "AKTIF", "tanggal_masuk": "2026-09-11"},
        {"id": 19, "nama": "Akim", "kategori": "Donatur 2", "status": "AKTIF", "tanggal_masuk": "2026-09-11"},
    ]
    pemuda_list = ["Didik", "Wanto", "Deny", "Ikam", "Inu", "Eko", "Dimas", "Riki", "Deny gobel", "Belod", 
                   "Kevin", "Umar", "Umam", "Cais", "Eko tuwek", "Mukri", "Wawan", "Mhad", "Fikri", "Feri",
                   "Ulum", "Apot", "Faza", "Slamet", "Azam", "Hermawan", "Santo", "Hesa", "Ipan", "Fais",
                   "Fakhur", "Riki pabrek", "Reza", "Deny j", "Ari the", "Roni", "Zamas", "Alvin", "Rt ne", "Febri",
                   "Ozi", "Sandi", "Agung", "Pendi", "Darno", "Kipli", "Bapi", "Rozak", "Biin", "Ipul",
                   "Ikhlas", "Imin woyo", "Batok", "Hasem", "Ipan (rid)", "Galang", "Danil", "Ayes", "Slamet (ibrohim)", "Riskon",
                   "Amet", "Botok", "Zaenal", "Ozi gendut", "Warji", "Putra", "Ciko (jikin)", "Furqon", "Faiq", "Hedi (tasbut)",
                   "Syukron (kepoanakan panjul)", "Dalas", "Apip (ngontrak gon kj lihin)"]
    for i, nama in enumerate(pemuda_list, start=20):
        members.append({"id": i, "nama": nama, "kategori": "Pemuda", "status": "AKTIF", "tanggal_masuk": "2026-09-11"})
    
    orangtua_list = ["Gendowor", "Ndhon", "Didik", "Ajed", "Carmudi", "Bisri", "Kholidin (yati)", "Iwan", "Libid", "Syukron",
                     "De parto", "Kondor", "Kholidin bos", "Lutfi", "Budi", "Edi", "Baset", "Panjol", "Mundhor", "Jembar",
                     "Casyadi (jembar)", "Anto ratna", "Den bogol", "Irak", "Lupi", "Agus", "Izal fakhur", "Slamet T", "Kholidin ayam", "Pedro",
                     "Slamet (waidah)", "Dirun", "Jono", "Wagio", "Wahidun", "Si'in", "Sipur", "Arik vita"]
    next_id = len(members) + 1
    for nama in orangtua_list:
        members.append({"id": next_id, "nama": nama, "kategori": "Orang Tua", "status": "AKTIF", "tanggal_masuk": "2026-09-11"})
        next_id += 1
    
    save_json(MEMBER_FILE, members)

transactions = load_json(TRANSACTION_FILE, [])
pengeluaran = load_json(PENGELUARAN_FILE, [])

# ==================================================
# 4. STREAMLIT UI
# ==================================================

st.set_page_config(page_title="Sistem Iuran", page_icon="💰", layout="wide", initial_sidebar_state="expanded")

# Inject Font Awesome CSS
st.markdown("""
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.5.0/css/all.min.css">
    <style>
        /* ... CSS lainnya ... */
        
        /* Tambahkan CSS untuk sidebar menu */
        .sidebar-menu {
            font-size: 18px;
            padding: 10px 0;
            cursor: pointer;
            border-radius: 8px;
            transition: 0.2s;
        }
        .sidebar-menu:hover {
            background-color: #edf2f7;
            padding-left: 12px;
        }
    </style>
""", unsafe_allow_html=True)

# ==================================================
# SIDEBAR MENU (TAMPILAN BESAR & BISA DIKLIK)
# ==================================================

# Logo & Judul
st.sidebar.markdown("""
    <div style='text-align: center; margin-bottom: 20px;'>
        <h2 style='color: #1a365d; margin: 0;'>SISTEM IURAN</h2>
        <hr style='border: 1px solid #e2e8f0;'>
    </div>
""", unsafe_allow_html=True)

# Daftar menu
menu_list = [
    "Dashboard",
    "Manajemen Member",
    "Input Pembayaran",
    "Edit Pembayaran",
    "Input Pengeluaran",
    "Edit Pengeluaran",
    "Grafik & Analisis",
    "Rekomendasi",
    "Laporan & Rekap",
    "Setting"
]

# Inisialisasi session state untuk menu
if 'menu' not in st.session_state:
    st.session_state.menu = "Dashboard"

# Buat tombol untuk setiap menu (teks besar)
for item in menu_list:
    if st.sidebar.button(
        item,
        key=item,
        use_container_width=True,
        type="primary" if st.session_state.menu == item else "secondary"
    ):
        st.session_state.menu = item
        st.rerun()

st.sidebar.markdown("---")

# Statistik ringkas di bawah (opsional)
total_pemasukan = get_total_pemasukan(transactions)
total_pengeluaran = get_total_pengeluaran(pengeluaran)
saldo = total_pemasukan - total_pengeluaran

st.sidebar.markdown(f"""
    <div style='background: #f7fafc; padding: 16px; border-radius: 8px;'>
        <div style='color: #4a5568; font-size: 14px;'>Total Pemasukan</div>
        <div style='color: #1a365d; font-size: 20px; font-weight: 700;'>{format_rupiah(total_pemasukan)}</div>
        <div style='color: #4a5568; font-size: 14px; margin-top: 8px;'>Total Pengeluaran</div>
        <div style='color: #1a365d; font-size: 20px; font-weight: 700;'>{format_rupiah(total_pengeluaran)}</div>
        <div style='color: #4a5568; font-size: 14px; margin-top: 8px;'>Saldo</div>
        <div style='color: #1a365d; font-size: 20px; font-weight: 700;'>{format_rupiah(saldo)}</div>
        <div style='color: #4a5568; font-size: 14px; margin-top: 8px;'>Total Member</div>
        <div style='color: #1a365d; font-size: 20px; font-weight: 700;'>{len(members)}</div>
    </div>
""", unsafe_allow_html=True)

# Gunakan session state sebagai menu aktif
menu = st.session_state.menu

# ==================================================
# 6. HALAMAN DASHBOARD
# ==================================================

if menu == "Dashboard":
    st.markdown("<h1 class='main-header'>Dashboard Keuangan</h1>", unsafe_allow_html=True)
    st.markdown(f"<p class='sub-header'>Periode: {config['tanggal_mulai']} - Agustus 2027</p>", unsafe_allow_html=True)

    target = get_target_total(config, members)
    progress = (total_pemasukan / target * 100) if target > 0 else 0

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Total Pemasukan", format_rupiah(total_pemasukan))
    with col2:
        st.metric("Total Pengeluaran", format_rupiah(total_pengeluaran))
    with col3:
        st.metric("Saldo Bersih", format_rupiah(saldo))
    with col4:
        st.metric("Progress Target", f"{progress:.1f}%")

    st.markdown("---")

    col1, col2 = st.columns(2)
    with col1:
        st.plotly_chart(
            buat_grafik_progress(target, total_pemasukan),
            use_container_width=True,
            key="dashboard_progress"
        )
    with col2:
        st.plotly_chart(
            buat_grafik_perbandingan(transactions, pengeluaran),
            use_container_width=True,
            key="dashboard_perbandingan"
        )

    st.markdown("---")
    st.plotly_chart(
        buat_grafik_pemasukan_per_bulan(transactions),
        use_container_width=True,
        key="dashboard_pemasukan_bulan"
    )

# ==================================================
# 7. HALAMAN MANAJEMEN MEMBER
# ==================================================

elif menu == "Manajemen Member":
    st.markdown("<h1 class='main-header'>Manajemen Member</h1>", unsafe_allow_html=True)

    filter_kategori = st.radio(
        "Pilih Kategori",
        ["Donatur", "Pemuda", "Orang Tua", "Perempuan", "Anak-anak", "Semua Member"],
        horizontal=True
    )

    sub_filter = "Semua"
    if filter_kategori == "Donatur":
        sub_filter = st.radio(
            "Pilih Donatur",
            ["Donatur 1", "Donatur 2", "Lihat Semua Donatur"],
            horizontal=True
        )

    filtered_members = []
    if filter_kategori == "Donatur":
        if sub_filter == "Donatur 1":
            filtered_members = [m for m in members if m['kategori'] == 'Donatur 1']
        elif sub_filter == "Donatur 2":
            filtered_members = [m for m in members if m['kategori'] == 'Donatur 2']
        else:
            filtered_members = [m for m in members if m['kategori'] in ['Donatur 1', 'Donatur 2']]
    elif filter_kategori == "Pemuda":
        filtered_members = [m for m in members if m['kategori'] == 'Pemuda']
    elif filter_kategori == "Orang Tua":
        filtered_members = [m for m in members if m['kategori'] == 'Orang Tua']
    elif filter_kategori == "Perempuan":
        filtered_members = [m for m in members if m['kategori'] == 'Perempuan']
    elif filter_kategori == "Anak-anak":
        filtered_members = [m for m in members if m['kategori'] == 'Anak-anak']
    else:
        filtered_members = members

    with st.expander("Tambah Member"):
        col1, col2 = st.columns(2)
        with col1:
            nama_baru = st.text_input("Nama")
        with col2:
            kategori_baru = st.selectbox("Kategori", ["Donatur 1", "Donatur 2", "Pemuda", "Orang Tua", "Perempuan", "Anak-anak"])

        if st.button("Tambah Member", use_container_width=True):
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

    search = st.text_input("Cari Member", placeholder="Ketik nama...")
    if search:
        filtered_members = [m for m in filtered_members if search.lower() in m['nama'].lower()]

    st.write(f"### {filter_kategori} ({len(filtered_members)} orang)")

    if filtered_members:
        df = pd.DataFrame(filtered_members)
        df['Status'] = df['status'].apply(lambda x: f"🟢 {x}" if x == 'AKTIF' else f"🔴 {x}")

        total_bayar = []
        for m in filtered_members:
            total = sum(t.get('nominal', 0) for t in transactions if t.get('nama') == m['nama'] and t.get('jenis') != 'pengeluaran')
            total_bayar.append(format_rupiah(total))
        df['Total Bayar'] = total_bayar

        st.dataframe(df[['id', 'nama', 'kategori', 'Status', 'Total Bayar', 'tanggal_masuk']].rename(columns={
            'id': 'ID', 'nama': 'Nama', 'kategori': 'Kategori', 'tanggal_masuk': 'Tanggal Masuk'
        }), use_container_width=True)

        # ==========================================
        # HAPUS MEMBER
        # ==========================================
        st.write("### Hapus Member")
        member_options = {f"{m['nama']} ({m['kategori']})": m['id'] for m in members}
        selected = st.selectbox("Pilih Member yang akan dihapus", list(member_options.keys()))
        member_id = member_options[selected]
        member = next(m for m in members if m['id'] == member_id)

        if st.button("Hapus Member"):
            st.warning(f"Yakin ingin menghapus {member['nama']}?")
            col1, col2 = st.columns(2)
            with col1:
                if st.button("Ya, Hapus"):
                    members = [m for m in members if m['id'] != member_id]
                    transactions = [t for t in transactions if t.get('nama') != member['nama']]
                    save_json(MEMBER_FILE, members)
                    save_json(TRANSACTION_FILE, transactions)
                    st.success(f"Member {member['nama']} berhasil dihapus!")
                    st.rerun()
            with col2:
                if st.button("Batal"):
                    st.rerun()

        # ==========================================
        # EDIT MEMBER
        # ==========================================
        st.write("### Edit Member")
        member_options_edit = {f"{m['nama']} ({m['kategori']})": m['id'] for m in members}
        selected_edit = st.selectbox("Pilih Member yang akan diedit", list(member_options_edit.keys()))
        member_id_edit = member_options_edit[selected_edit]
        member_edit = next(m for m in members if m['id'] == member_id_edit)

        col1, col2, col3 = st.columns(3)
        with col1:
            nama_baru = st.text_input("Nama Baru", value=member_edit['nama'])
        with col2:
            kategori_baru = st.selectbox("Kategori Baru", ["Donatur 1", "Donatur 2", "Pemuda", "Orang Tua", "Perempuan", "Anak-anak"],
                                       index=["Donatur 1", "Donatur 2", "Pemuda", "Orang Tua", "Perempuan", "Anak-anak"].index(member_edit['kategori']))
        with col3:
            status_baru = st.selectbox("Status Baru", ["AKTIF", "NONAKTIF"],
                                      index=["AKTIF", "NONAKTIF"].index(member_edit.get('status', 'AKTIF')))

        if st.button("Simpan Perubahan Member"):
            member_edit['nama'] = nama_baru
            member_edit['kategori'] = kategori_baru
            member_edit['status'] = status_baru
            save_json(MEMBER_FILE, members)
            st.success("Member berhasil diupdate!")
            st.rerun()

    else:
        st.info("Belum ada member di kategori ini.")

# ==================================================
# 8. HALAMAN INPUT PEMBAYARAN
# ==================================================

elif menu == "Input Pembayaran":
    st.markdown("<h1 class='main-header'>Input Pembayaran Mingguan</h1>", unsafe_allow_html=True)
    
    today = datetime.now().strftime("%Y-%m-%d")
    minggu_ke = get_minggu_ke(today, config['tanggal_mulai'])
    start_week, end_week = get_week_range(config['tanggal_mulai'], minggu_ke) if minggu_ke > 0 else ("-", "-")
    
    st.markdown(f"<p class='sub-header'>Minggu ke-{minggu_ke} | Periode: {start_week} - {end_week}</p>", unsafe_allow_html=True)
    
    active_members = [m for m in members if m.get('status', 'AKTIF') == 'AKTIF']
    
    if not active_members:
        st.warning("Belum ada member aktif.")
    else:
        # ==========================================
        # FILTER KATEGORI
        # ==========================================
        filter_kategori = st.radio(
            "Pilih Kategori",
            ["Donatur", "Pemuda", "Orang Tua", "Perempuan", "Anak-anak", "Semua Member"],
            horizontal=True
        )
        
        # Filter berdasarkan kategori
        if filter_kategori == "Donatur":
            filtered_members = [m for m in active_members if m['kategori'] in ['Donatur 1', 'Donatur 2']]
        elif filter_kategori == "Pemuda":
            filtered_members = [m for m in active_members if m['kategori'] == 'Pemuda']
        elif filter_kategori == "Orang Tua":
            filtered_members = [m for m in active_members if m['kategori'] == 'Orang Tua']
        elif filter_kategori == "Perempuan":
            filtered_members = [m for m in active_members if m['kategori'] == 'Perempuan']
        elif filter_kategori == "Anak-anak":
            filtered_members = [m for m in active_members if m['kategori'] == 'Anak-anak']
        else:  # Semua Member
            filtered_members = active_members
        
        # ==========================================
        # FITUR CARI MEMBER
        # ==========================================
        search = st.text_input("🔍 Cari Member", placeholder="Ketik nama...")
        if search:
            filtered_members = [m for m in filtered_members if search.lower() in m['nama'].lower()]
        
        # ==========================================
        # TAMPILKAN DAFTAR TAGIHAN
        # ==========================================
        st.write(f"### 📋 Daftar Tagihan {filter_kategori} ({len(filtered_members)} orang)")
        
        data_input = {}
        for m in filtered_members:
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
        
        # ==========================================
        # REKAP MINGGU INI
        # ==========================================
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
# 9. HALAMAN EDIT PEMBAYARAN
# ==================================================

elif menu == "Edit Pembayaran":
    st.markdown("<h1 class='main-header'>Edit Pembayaran</h1>", unsafe_allow_html=True)
    
    if not transactions:
        st.info("Belum ada transaksi.")
    else:
        member_names = list(set(t.get('nama') for t in transactions if t.get('jenis') != 'pengeluaran'))
        if not member_names:
            st.info("Belum ada transaksi pembayaran.")
        else:
            selected_member = st.selectbox("Pilih Member", member_names)
            
            trans_member = get_transaksi_per_member(transactions, selected_member)
            if not trans_member:
                st.info(f"Member {selected_member} belum punya transaksi.")
            else:
                trans_data = []
                for i, t in enumerate(trans_member):
                    trans_data.append({
                        "No": i + 1,
                        "Tanggal": t.get('tanggal', '-'),
                        "Nominal": format_rupiah(t.get('nominal', 0)),
                        "Minggu": t.get('minggu_ke', '-')
                    })
                st.dataframe(pd.DataFrame(trans_data), use_container_width=True)
                
                trans_options = [f"No {i+1} - {t.get('tanggal', '-')} - {format_rupiah(t.get('nominal', 0))}" for i, t in enumerate(trans_member)]
                selected_idx = st.selectbox("Pilih Transaksi yang akan diedit", range(len(trans_options)), format_func=lambda x: trans_options[x])
                
                trans = trans_member[selected_idx]
                
                st.write("### Edit Data")
                col1, col2 = st.columns(2)
                with col1:
                    tanggal_baru = st.date_input("Tanggal Baru", value=datetime.strptime(trans.get('tanggal', datetime.now().strftime("%Y-%m-%d")), "%Y-%m-%d"))
                with col2:
                    nominal_baru = st.text_input("Nominal Baru (contoh: 500.000)", value=str(trans.get('nominal', 0)).replace(".", ""))
                
                if st.button("Simpan Perubahan", use_container_width=True):
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


        # ==========================================
        # HAPUS PEMBAYARAN
        # ==========================================
        st.write("### Hapus Pembayaran")
        trans_options = [f"No {i+1} - {t.get('tanggal', '-')} - {format_rupiah(t.get('nominal', 0))}" for i, t in enumerate(trans_member)]
        selected_idx = st.selectbox("Pilih Transaksi yang akan dihapus", range(len(trans_options)), format_func=lambda x: trans_options[x])
        
        if st.button("Hapus Transaksi", use_container_width=True):
            trans_to_delete = trans_member[selected_idx]
            transactions.remove(trans_to_delete)
            save_json(TRANSACTION_FILE, transactions)
            st.success("Transaksi berhasil dihapus!")
            st.rerun()


# ==================================================
# 10. HALAMAN INPUT PENGELUARAN
# ==================================================

elif menu == "Input Pengeluaran":
    st.markdown("<h1 class='main-header'>Input Pengeluaran</h1>", unsafe_allow_html=True)
    
    with st.form("form_pengeluaran"):
        col1, col2 = st.columns(2)
        with col1:
            kategori = st.text_input("Kategori", placeholder="Contoh: Jajan, Makanan, DLL")
            nominal = st.text_input("Nominal (contoh: 500.000)")
        with col2:
            tanggal = st.date_input("Tanggal", value=datetime.now().date())
            keterangan = st.text_input("Keterangan")
        
        if st.form_submit_button("Simpan Pengeluaran", use_container_width=True):
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
    st.write("### Riwayat Pengeluaran")
    if pengeluaran:
        df = pd.DataFrame(pengeluaran)
        df['Nominal'] = df['nominal'].apply(format_rupiah)
        st.dataframe(df[['tanggal', 'kategori', 'Nominal', 'keterangan']].rename(columns={
            'tanggal': 'Tanggal', 'kategori': 'Kategori', 'keterangan': 'Keterangan'
        }), use_container_width=True)
        st.caption(f"Total Pengeluaran: {format_rupiah(sum(p['nominal'] for p in pengeluaran))}")

# ==================================================
# 11. HALAMAN EDIT PENGELUARAN
# ==================================================

elif menu == "Edit Pengeluaran":
    st.markdown("<h1 class='main-header'>Edit Pengeluaran</h1>", unsafe_allow_html=True)
    
    if not pengeluaran:
        st.info("Belum ada pengeluaran.")
    else:
        pengeluaran_options = [f"No {i+1} - {p.get('tanggal', '-')} - {p.get('kategori', '-')} - {format_rupiah(p.get('nominal', 0))}" for i, p in enumerate(pengeluaran)]
        selected_idx = st.selectbox("Pilih Pengeluaran yang akan diedit", range(len(pengeluaran_options)), format_func=lambda x: pengeluaran_options[x])
        
        p = pengeluaran[selected_idx]
        
        st.write("### Edit Data")
        col1, col2 = st.columns(2)
        with col1:
            kategori_baru = st.text_input("Kategori Baru", value=p.get('kategori', ''))
            nominal_baru = st.text_input("Nominal Baru (contoh: 500.000)", value=str(p.get('nominal', 0)).replace(".", ""))
        with col2:
            tanggal_baru = st.date_input("Tanggal Baru", value=datetime.strptime(p.get('tanggal', datetime.now().strftime("%Y-%m-%d")), "%Y-%m-%d"))
            keterangan_baru = st.text_input("Keterangan Baru", value=p.get('keterangan', ''))
        
        if st.button("Simpan Perubahan", use_container_width=True):
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

        # ==========================================
        # HAPUS PENGELUARAN
        # ==========================================
        st.write("### Hapus Pengeluaran")
        pengeluaran_options = [f"No {i+1} - {p.get('tanggal', '-')} - {p.get('kategori', '-')} - {format_rupiah(p.get('nominal', 0))}" for i, p in enumerate(pengeluaran)]
        selected_idx = st.selectbox("Pilih Pengeluaran yang akan dihapus", range(len(pengeluaran_options)), format_func=lambda x: pengeluaran_options[x])
        
        if st.button("Hapus Pengeluaran", use_container_width=True):
            p_to_delete = pengeluaran[selected_idx]
            pengeluaran.remove(p_to_delete)
            save_json(PENGELUARAN_FILE, pengeluaran)
            st.success("Pengeluaran berhasil dihapus!")
            st.rerun()

# ==================================================
# 12. HALAMAN MANAJEMEN DONATUR
# ==================================================

elif menu == "Manajemen Donatur":
    st.markdown("<h1 class='main-header'>Manajemen Donatur</h1>", unsafe_allow_html=True)
    
    with st.expander("Tambah Donatur"):
        col1, col2 = st.columns(2)
        with col1:
            nama_donatur = st.text_input("Nama Donatur")
            nominal_donatur = st.text_input("Nominal (contoh: 5.000.000)")
        with col2:
            kategori_donatur = st.selectbox("Kategori", ["Donatur 1", "Donatur 2"])
            status_donatur = st.selectbox("Status", ["SUDAH BAYAR", "BELUM BAYAR"])
        
        if st.button("Tambah Donatur", use_container_width=True):
            nominal_int = parse_nominal(nominal_donatur)
            if nama_donatur and nominal_int and nominal_int > 0:
                donatur.append({
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
    
    st.write("### Daftar Donatur")
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
            st.metric("Total Donatur 1", format_rupiah(donatur1))
        with col2:
            st.metric("Total Donatur 2", format_rupiah(donatur2))
    else:
        st.info("Belum ada donatur.")

# ==================================================
# 13. HALAMAN GRAFIK
# ==================================================

elif menu == "Grafik & Analisis":
    st.markdown("<h1 class='main-header'>Grafik & Analisis</h1>", unsafe_allow_html=True)
    
    tab1, tab2, tab3, tab4 = st.tabs(["Pemasukan", "Pengeluaran", "Perbandingan", "Progress"])
    
    with tab1:
        # Beri key unik
        st.plotly_chart(
            buat_grafik_pemasukan_per_bulan(transactions), 
            use_container_width=True,
            key="grafik_bulan"  # ← TAMBAHKAN INI!
        )
        st.plotly_chart(
            buat_grafik_pemasukan_per_minggu(transactions, config), 
            use_container_width=True,
            key="grafik_minggu"  # ← TAMBAHKAN INI!
        )
    
    with tab2:
        st.plotly_chart(
            buat_grafik_pengeluaran(pengeluaran), 
            use_container_width=True,
            key="grafik_pengeluaran"  # ← TAMBAHKAN INI!
        )
    
    with tab3:
        st.plotly_chart(
            buat_grafik_perbandingan(transactions, pengeluaran), 
            use_container_width=True,
            key="grafik_perbandingan"  # ← TAMBAHKAN INI!
        )
    
    with tab4:
        target = get_target_total(config, members)
        st.plotly_chart(
            buat_grafik_progress(target, total_pemasukan), 
            use_container_width=True,
            key="grafik_progress"  # ← TAMBAHKAN INI!
        )

# ==================================================
# 14. HALAMAN REKOMENDASI
# ==================================================

elif menu == "Rekomendasi":
    st.markdown("<h1 class='main-header'>Rekomendasi Penagihan</h1>", unsafe_allow_html=True)
    st.markdown(f"<p class='sub-header'>Per: {datetime.now().strftime('%d %B %Y')}</p>", unsafe_allow_html=True)
    
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
# 15. HALAMAN LAPORAN & REKAP
# ==================================================

elif menu == "Laporan & Rekap":
    st.markdown("<h1 class='main-header'>Laporan & Rekap Keuangan</h1>", unsafe_allow_html=True)
    
    target = get_target_total(config, members)
    progress = (total_pemasukan / target * 100) if target > 0 else 0
    
    st.write("### Ringkasan Keuangan")
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Total Pemasukan", format_rupiah(total_pemasukan))
    with col2:
        st.metric("Total Pengeluaran", format_rupiah(total_pengeluaran))
    with col3:
        st.metric("Saldo Bersih", format_rupiah(saldo))
    with col4:
        st.metric("Progress Target", f"{progress:.1f}%")
    
    st.markdown("---")
    
    st.write("### Rekap Per Kategori")
    kategori_data = []
    for kategori in ["Donatur 1", "Donatur 2", "Pemuda", "Orang Tua", "Perempuan", "Anak-anak"]:
        count = sum(1 for m in members if m['kategori'] == kategori and m.get('status', 'AKTIF') == 'AKTIF')
        total_bayar_k = sum(t.get('nominal', 0) for t in transactions if t.get('kategori') == kategori and t.get('jenis') != 'pengeluaran')
        if kategori == "Donatur 1":
            target_k = config.get('target_donatur1', 5000000) * count
        elif kategori == "Donatur 2":
            target_k = config.get('target_donatur2', 2500000) * count
        elif kategori == "Pemuda":
            target_k = config.get('target_pemuda', 1500000) * count
        elif kategori == "Orang Tua":
            target_k = config.get('target_orangtua', 1000000) * count
        else:
            target_k = 0
        if count > 0 or total_bayar_k > 0:
            progress_k = (total_bayar_k / target_k * 100) if target_k > 0 else 0
            kategori_data.append({
                "Kategori": kategori,
                "Jumlah": count,
                "Total Bayar": format_rupiah(total_bayar_k),
                "Target": format_rupiah(target_k),
                "Progress": f"{progress_k:.1f}%"
            })
    
    if kategori_data:
        st.dataframe(pd.DataFrame(kategori_data), use_container_width=True)
    
    st.markdown("---")
    
    st.write("### Rekap Per Minggu")
    minggu_data = {}
    for t in transactions:
        if t.get('jenis') == 'pengeluaran':
            continue
        minggu = t.get('minggu_ke', 0)
        if minggu > 0:
            minggu_data[minggu] = minggu_data.get(minggu, 0) + t.get('nominal', 0)
    
    if minggu_data:
        data = []
        for minggu, total in sorted(minggu_data.items()):
            start_week, end_week = get_week_range(config['tanggal_mulai'], minggu)
            data.append({
                "Minggu": f"Minggu {minggu}",
                "Periode": f"{start_week} - {end_week}",
                "Total": format_rupiah(total)
            })
        st.dataframe(pd.DataFrame(data), use_container_width=True)
    else:
        st.info("Belum ada data pembayaran.")
    
    st.markdown("---")
    
    st.write("### Rekap Per Bulan")
    bulan_data = {}
    for t in transactions:
        if t.get('jenis') == 'pengeluaran':
            continue
        tanggal = datetime.strptime(t['tanggal'], "%Y-%m-%d")
        bulan = tanggal.strftime("%B %Y")
        bulan_data[bulan] = bulan_data.get(bulan, 0) + t.get('nominal', 0)
    
    if bulan_data:
        data = []
        for bulan, total in sorted(bulan_data.items()):
            data.append({
                "Bulan": bulan,
                "Total": format_rupiah(total)
            })
        st.dataframe(pd.DataFrame(data), use_container_width=True)
    else:
        st.info("Belum ada data pembayaran.")
    # ==========================================
    # REKAP PER MEMBER
    # ==========================================
    st.markdown("---")
    st.write("### Rekap Per Member")
    
    # Pilih member dari daftar yang aktif
    active_members = [m for m in members if m.get('status', 'AKTIF') == 'AKTIF']
    if active_members:
        # Buat daftar pilihan
        member_options = {f"{m['nama']} ({m['kategori']})": m['id'] for m in active_members}
        selected_label = st.selectbox("Pilih Member", list(member_options.keys()))
        selected_id = member_options[selected_label]
        member = next(m for m in active_members if m['id'] == selected_id)
        
        # Hitung data member
        total_bayar = sum(t.get('nominal', 0) for t in transactions if t.get('nama') == member['nama'] and t.get('jenis') != 'pengeluaran')
        
        # Tentukan target berdasarkan kategori
        if member['kategori'] == 'Donatur 1':
            target = config.get('target_donatur1', 5000000)
        elif member['kategori'] == 'Donatur 2':
            target = config.get('target_donatur2', 2500000)
        elif member['kategori'] == 'Pemuda':
            target = config.get('target_pemuda', 1500000)
        elif member['kategori'] == 'Orang Tua':
            target = config.get('target_orangtua', 1000000)
        else:
            target = 0
        
        sisa = target - total_bayar if target > 0 else 0
        progress = (total_bayar / target * 100) if target > 0 else 0
        
        # Tampilkan detail
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Target", format_rupiah(target))
        with col2:
            st.metric("Total Bayar", format_rupiah(total_bayar))
        with col3:
            st.metric("Sisa", format_rupiah(sisa))
        
        # Progress bar
        if target > 0:
            st.progress(min(progress / 100, 1.0))
            st.caption(f"Progress: {progress:.1f}%")
        else:
            st.info("Kategori ini tidak memiliki target iuran.")
        
        # Riwayat pembayaran
        trans_member = get_transaksi_per_member(transactions, member['nama'])
        if trans_member:
            st.write("#### Riwayat Pembayaran")
            df = pd.DataFrame(trans_member)
            df['Nominal'] = df['nominal'].apply(format_rupiah)
            st.dataframe(df[['tanggal', 'minggu_ke', 'Nominal']].rename(columns={
                'tanggal': 'Tanggal', 'minggu_ke': 'Minggu'
            }), use_container_width=True)
        else:
            st.info("Belum ada riwayat pembayaran untuk member ini.")
    else:
        st.info("Belum ada member aktif.")

# ==================================================
# 16. HALAMAN SETTING
# ==================================================

elif menu == "Setting":
    st.markdown("<h1 class='main-header'>Pengaturan</h1>", unsafe_allow_html=True)
    
    st.write("### Konfigurasi")
    
    col1, col2 = st.columns(2)
    with col1:
        tanggal_mulai = st.date_input("Tanggal Mulai", value=datetime.strptime(config.get('tanggal_mulai', '2026-09-11'), "%Y-%m-%d"))
    with col2:
        target_donatur1 = st.text_input("Target Donatur 1", value=str(config.get('target_donatur1', 5000000)).replace(".", ""))
        target_donatur2 = st.text_input("Target Donatur 2", value=str(config.get('target_donatur2', 2500000)).replace(".", ""))
        target_pemuda = st.text_input("Target Pemuda", value=str(config.get('target_pemuda', 1500000)).replace(".", ""))
        target_orangtua = st.text_input("Target Orang Tua", value=str(config.get('target_orangtua', 1000000)).replace(".", ""))
    
    if st.button("Simpan Konfigurasi", use_container_width=True):
        target_d1 = parse_nominal(target_donatur1)
        target_d2 = parse_nominal(target_donatur2)
        target_p = parse_nominal(target_pemuda)
        target_ot = parse_nominal(target_orangtua)
        
        if target_d1 and target_d2 and target_p and target_ot:
            config['tanggal_mulai'] = tanggal_mulai.strftime("%Y-%m-%d")
            config['target_donatur1'] = target_d1
            config['target_donatur2'] = target_d2
            config['target_pemuda'] = target_p
            config['target_orangtua'] = target_ot
            save_json(CONFIG_FILE, config)
            st.success("✅ Konfigurasi berhasil disimpan!")
            st.rerun()
        else:
            st.error("❌ Format target salah! Gunakan titik (contoh: 1.500.000)")
