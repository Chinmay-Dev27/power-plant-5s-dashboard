import streamlit as st
import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import requests
from io import StringIO, BytesIO
from github import Github, Auth
from streamlit_lottie import st_lottie
import streamlit.components.v1 as components
from fpdf import FPDF
import matplotlib.pyplot as plt
import matplotlib
import base64
import tempfile
import os

# Force matplotlib to use a non-interactive backend
matplotlib.use('Agg')

# --- 1. CONFIGURATION & CSS ---
st.set_page_config(page_title="GMR 5S Dashboard", layout="wide", page_icon="⚡")

# Import Professional Fonts
components.html(
    """
    <link href="https://fonts.googleapis.com/css2?family=Roboto:wght@300;400;500;700&family=Oswald:wght@400;600&family=Orbitron:wght@500;700&display=swap" rel="stylesheet">
    """,
    height=0,
)

# --- 2. VISUAL OVERHAUL ---
st.markdown("""
    <style>
    /* GLOBAL THEME */
    .stApp {
        background-color: #f0f2f6;
        background: linear-gradient(135deg, #0f172a 0%, #1e293b 100%);
        color: #ffffff;
        font-family: 'Roboto', sans-serif;
    }
    
    /* CUSTOM TABS */
    .stTabs [data-baseweb="tab-list"] {
        gap: 8px;
        background-color: rgba(255,255,255,0.05);
        padding: 10px;
        border-radius: 50px;
    }
    .stTabs [data-baseweb="tab"] {
        height: 40px;
        white-space: pre-wrap;
        background-color: transparent;
        border-radius: 20px;
        color: #94a3b8;
        font-weight: 500;
    }
    .stTabs [aria-selected="true"] {
        background-color: #F59E0B; /* Amber/Orange */
        color: white;
    }
    
    /* GLASS CARDS */
    .glass-card {
        background: rgba(30, 41, 59, 0.7);
        border: 1px solid rgba(255, 255, 255, 0.1);
        border-radius: 12px;
        padding: 20px;
        margin-bottom: 15px;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);
        text-align: center;
        transition: transform 0.2s ease;
    }
    .glass-card:hover { transform: translateY(-2px); border-color: rgba(255, 255, 255, 0.3); }
    
    /* UTILS */
    .border-good { border-top: 3px solid #10B981; }
    .border-bad { border-top: 3px solid #EF4444; }
    .big-val { font-family: 'Orbitron', sans-serif; font-size: 26px; font-weight: 700; color: white; }
    .sub-lbl { font-size: 11px; color: #94a3b8; text-transform: uppercase; letter-spacing: 0.5px; }
    
    /* BURJ KHALIFA TEXT */
    .burj-text {
        font-family: 'Oswald', sans-serif;
        font-size: 42px;
        font-weight: 700;
        background: -webkit-linear-gradient(45deg, #F59E0B, #FCD34D);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
    }
    </style>
""", unsafe_allow_html=True)

# --- 3. ASSETS & HELPERS ---
def load_lottieurl(url):
    try:
        r = requests.get(url, timeout=1)
        return r.json() if r.status_code == 200 else None
    except: return None

anim_tree = load_lottieurl("https://lottie.host/6e35574d-8651-477d-b570-56965c276b3b/22572535-373f-42a9-823c-99e582862594.json")
anim_smoke = load_lottieurl("https://lottie.host/575a66c6-1215-4688-9189-b57579621379/10839556-9141-4712-a89e-224429715783.json")
anim_money = load_lottieurl("https://lottie.host/02008323-2895-4673-863a-4934e402802d/41838634-11d9-430c-992a-356c92d529d3.json")
anim_sun = load_lottieurl("https://lottie.host/3c6c9e04-0391-4e9e-99f2-2b6f3c02d139/2Y7Q1j1j1j.json") 

def init_github():
    try:
        if "GITHUB_TOKEN" in st.secrets:
            auth = Auth.Token(st.secrets["GITHUB_TOKEN"])
            g = Github(auth=auth)
            return g.get_repo(st.secrets["REPO_NAME"])
    except: return None

def load_history(repo):
    if not repo: return pd.DataFrame()
    try:
        file = repo.get_contents("plant_history_v28.csv", ref=st.secrets["BRANCH"])
        df = pd.read_csv(StringIO(file.decoded_content.decode()))
        df['Date'] = pd.to_datetime(df['Date'])
        return df, file.sha
    except: 
        cols = ["Date", "Unit", "Profit", "HR", "SOx", "NOx", "Gen", "Ash Util", "Coal Ash %", "Biomass", "Solar", "Vacuum", "MS Temp", "FG Temp", "Spray", "Ash Cement", "Ash Bricks"]
        return pd.DataFrame(columns=cols), None

def save_history(repo, df, sha):
    try:
        csv_content = df.to_csv(index=False)
        msg = "Update" if sha else "Init"
        if sha: repo.update_file("plant_history_v28.csv", msg, csv_content, sha, branch=st.secrets["BRANCH"])
        else: repo.create_file("plant_history_v28.csv", msg, csv_content, branch=st.secrets["BRANCH"])
        return True
    except: return False

def generate_excel_template():
    df = pd.DataFrame({
        'Parameter': ['Generation (MU)', 'Heat Rate (kcal/kWh)', 'Vacuum (kg/cm2)', 'MS Temp (C)', 'FG Temp (C)', 'Spray (TPH)', 'SOx (mg/Nm3)', 'NOx (mg/Nm3)', 'Ash to Cement (Tons)', 'Ash to Bricks (Tons)', 'Biomass (Tons)', 'Solar (MU)'],
        'Unit 1': [8.4, 2380, -0.90, 535, 135, 20, 550, 400, 1000, 500, 0, 0],
        'Unit 2': [8.2, 2310, -0.92, 538, 132, 18, 540, 390, 900, 500, 0, 0],
        'Unit 3': [8.5, 2290, -0.93, 540, 130, 15, 530, 380, 1100, 500, 0, 0]
    })
    return df

def generate_bulk_template():
    df = pd.DataFrame({
        'Date': ['2024-01-01', '2024-01-01', '2024-01-01'],
        'Unit': ['1', '2', '3'],
        'Gen': [8.4, 8.2, 8.5], 'HR': [2380, 2310, 2290], 'Vacuum': [-0.90, -0.92, -0.93], 'MS Temp': [535, 538, 540],
        'FG Temp': [135, 132, 130], 'Spray': [20, 18, 15], 'SOx': [550, 540, 530], 'NOx': [400, 390, 380],
        'Ash Cement': [1000, 900, 1100], 'Ash Bricks': [500, 500, 500], 'Coal Ash %': [35.0, 35.0, 35.0], 
        'Biomass': [0, 0, 0], 'Solar': [0, 0, 0]
    })
    return df

# --- 4. PDF ENGINE ---
class PDF(FPDF):
    def header(self):
        self.set_font('Arial', 'B', 16)
        self.set_text_color(0, 51, 153)
        self.cell(0, 10, 'GMR Kamalanga - 5S Report', 0, 1, 'C')
        self.ln(5)
    def footer(self):
        self.set_y(-15)
        self.set_font('Arial', 'I', 8)
        self.set_text_color(128, 128, 128)
        self.cell(0, 10, f'Page {self.page_no()}', 0, 0, 'C')

def create_full_pdf(units, fleet_pnl, ash_data, green_data):
    pdf = PDF()
    pdf.add_page()
    pdf.set_font("Arial", 'B', 12)
    pdf.cell(0, 10, f"Date: {datetime.now().strftime('%Y-%m-%d')} | P&L: Rs {fleet_pnl:,.0f}", 1, 1, 'C')
    pdf.ln(10)
    
    # War Room Table
    pdf.set_font("Arial", 'B', 10)
    pdf.set_fill_color(220, 220, 220)
    headers = ["Unit", "Gen", "HR", "Profit", "SOx", "NOx"]
    for h in headers: pdf.cell(30, 10, h, 1, 0, 'C', 1)
    pdf.ln()
    pdf.set_font("Arial", size=10)
    for u in units:
        pdf.cell(30, 10, f"U{u['id']}", 1)
        pdf.cell(30, 10, str(u['gen']), 1)
        pdf.cell(30, 10, str(u['hr']), 1)
        pdf.cell(30, 10, f"{u['profit']:,.0f}", 1)
        pdf.cell(30, 10, str(u['sox']), 1)
        pdf.cell(30, 10, str(u['nox']), 1)
        pdf.ln()
    
    # Details Pages
    for u in units:
        pdf.add_page()
        pdf.set_font("Arial", 'B', 14)
        pdf.cell(0, 10, f"Unit {u['id']} Analysis", 0, 1)
        pdf.ln(5)
        
        # Loss Chart
        tech_map = [("Vac", u['losses']['Vacuum']), ("MS", u['losses']['MS Temp']), ("FG", u['losses']['Flue Gas'])]
        fig = plt.figure(figsize=(6, 3))
        plt.bar([x[0] for x in tech_map], [x[1] for x in tech_map], color='#FF3333')
        plt.title("Losses")
        img_buf = tempfile.NamedTemporaryFile(delete=False, suffix='.png')
        plt.savefig(img_buf.name, format='png')
        plt.close()
        pdf.image(img_buf.name, x=10, y=pdf.get_y(), w=100)
        os.unlink(img_buf.name)
        pdf.ln(60)
        
        pdf.set_font("Arial", size=10)
        pdf.cell(0, 10, f"ESCerts: {u['escerts']:.2f} | Carbon Credits: {u['carbon']:.2f}", 0, 1)

    # Environment Page
    pdf.add_page()
    pdf.set_font("Arial", 'B', 14)
    pdf.cell(0, 10, "Environment & Ash", 0, 1)
    pdf.ln(5)
    pdf.set_font("Arial", size=10)
    pdf.cell(0, 10, f"Ash Gen: {ash_data['gen']:.0f} T | Util: {ash_data['util']:.0f} T", 0, 1)
    pdf.cell(0, 10, f"Solar CO2 Saved: {green_data['sol_co2']:.2f} T", 0, 1)
    
    return pdf.output(dest='S').encode('latin-1')

# --- 5. LOGIC ENGINE ---
def calculate_unit(u_id, gen, hr, inputs, design_vals, ash_params):
    TARGET_HR = design_vals['target_hr']; DESIGN_HR = 2250; COAL_GCV = design_vals['gcv']
    
    # Financials
    kcal_diff = (TARGET_HR - hr) * gen * 1_000_000
    escerts = kcal_diff / 10_000_000
    coal_saved_kg = kcal_diff / COAL_GCV
    carbon_tons = (coal_saved_kg / 1000) * 1.7
    profit = (escerts * 1000) + (carbon_tons * 500) + (coal_saved_kg * 4.5)
    
    l_vac = max(0, (inputs['vac'] - (-0.92)) / 0.01 * 18) * -1
    l_ms = max(0, (540 - inputs['ms']) * 1.2)
    l_fg = max(0, (inputs['fg'] - 130) * 1.5)
    l_spray = max(0, (inputs['spray'] - 15) * 2.0)
    l_unacc = max(0, hr - (DESIGN_HR + l_ms + l_fg + l_spray + 50) - abs(l_vac))
    score = max(0, 100 - (abs(l_vac) + l_ms + l_fg + l_spray + l_unacc)/3)
    
    # Ash
    coal_consumed = (gen * hr * 1000) / COAL_GCV if COAL_GCV > 0 else 0
    ash_gen = coal_consumed * (ash_params['ash_pct'] / 100)
    ash_util = ash_params['util_cem'] + ash_params['util_brick']
    ash_stocked = ash_gen - ash_util
    bricks_current = ash_params['util_brick'] * 666
    bricks_potential_total = ash_gen * 666
    burj_pct = (bricks_current / 165_000_000) * 100
    
    # Houses Powered (Approx: 1MWh = 100 homes/day)
    # Solar MU * 1000000 kWh / 10 kWh/day = Houses
    # Biomass Tons * GCV * Efficiency... simplified to coal equiv MWh
    homes_biomass = (ash_params.get('biomass', 0) * 3000 * 1000 / 3600 / 1000) * 100
    
    return {
        "id": u_id, "gen": gen, "hr": hr, "profit": profit, "escerts": escerts, "carbon": carbon_tons,
        "score": score, "sox": inputs['sox'], "nox": inputs['nox'],
        "losses": {"Vacuum": abs(l_vac), "MS Temp": l_ms, "Flue Gas": l_fg, "Spray": l_spray, "Unaccounted": l_unacc},
        "ash": {"generated": ash_gen, "utilized": ash_util, "stocked": ash_stocked, 
                "bricks_made": bricks_current, "cem_util": ash_params['util_cem'],
                "brick_util": ash_params['util_brick'], "burj_pct": burj_pct},
        "limits": design_vals['limits'], "trees": abs(carbon_tons / 0.025),
        "target_hr": TARGET_HR, "homes_bio": homes_biomass
    }

# --- 6. RENDER FUNCTION (DEFINED BEFORE USE) ---
def render_unit_detail(u, configs):
    st.markdown(f"### 🔍 Unit {u['id']} Deep Dive")
    
    c1, c2 = st.columns([1, 1])
    
    with c1:
        st.markdown("#### 🏎️ Efficiency Gauge")
        target = configs[int(u['id'])-1]['target_hr']
        fig = go.Figure(go.Indicator(
            mode = "gauge+number+delta", value = u['hr'],
            delta = {'reference': target, 'increasing': {'color': "#FF3333"}},
            gauge = {
                'axis': {'range': [2000, 2600]}, 'bar': {'color': "#00ccff"},
                'steps': [{'range': [2000, target], 'color': "rgba(0,255,0,0.2)"}, {'range': [target, 2600], 'color': "rgba(255,0,0,0.2)"}],
                'threshold': {'line': {'color': "#FF3333", 'width': 4}, 'thickness': 0.75, 'value': u['hr']}
            }
        ))
        fig.update_layout(height=250, margin=dict(l=20,r=20,t=0,b=0), paper_bgcolor='rgba(0,0,0,0)', font_color='white')
        st.plotly_chart(fig, width="stretch", key=f"gauge_{u['id']}")

    with c2:
        st.markdown("#### 🔧 Loss Analysis")
        loss_df = pd.DataFrame(list(u['losses'].items()), columns=['Param', 'Loss']).sort_values('Loss')
        fig_bar = px.bar(loss_df, x='Loss', y='Param', orientation='h', text='Loss', color='Loss', 
                         color_continuous_scale=['#444', '#FF3333'], template='plotly_dark')
        fig_bar.update_layout(
            paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', font_color='white', height=250,
            xaxis=dict(showgrid=False), yaxis=dict(showgrid=False)
        )
        fig_bar.update_traces(texttemplate='%{text:.1f}', textposition='outside')
        st.plotly_chart(fig_bar, width="stretch", key=f"bar_{u['id']}")

    st.divider()
    c3, c4 = st.columns(2)
    with c3:
        st.markdown(f"""
        <div class="glass-card" style="border-left: 4px solid #FF9933">
            <div class="p-title">5S Score</div>
            <div class="big-val" style="color:#FF9933">{u['score']:.1f}</div>
            <div class="sub-lbl">Technical Hygiene</div>
        </div>""", unsafe_allow_html=True)
    with c4:
        st.markdown(f"""
        <div class="glass-card" style="border-left: 4px solid #00ccff">
            <div class="p-title">Carbon Credits</div>
            <div class="big-val" style="color:#00ccff">{u['carbon']:.1f}</div>
            <div class="sub-lbl">Tons CO2 Avoided</div>
        </div>""", unsafe_allow_html=True)

# --- 7. SIDEBAR & DATA LOADING ---
with st.sidebar:
    try: st.image("1000051706.png", width="stretch")
    except: st.markdown("## **GMR POWER**") 
    st.title("Control Panel")
    
    # DATE PICKER
    date_in = st.date_input("📅 Dashboard Date", datetime.now())
    
    repo = init_github()
    hist_df, sha = load_history(repo)
    
    # Pre-load history data for date
    hist_data = {}
    if not hist_df.empty:
        day_df = hist_df[hist_df['Date'] == pd.Timestamp(date_in)]
        if not day_df.empty:
            st.success(f"Loaded Data for {date_in.strftime('%d-%b-%Y')}")
            for _, row in day_df.iterrows():
                hist_data[str(row['Unit'])] = row
        else:
            st.info("No history for this date. Using defaults.")
    
    # UPLOADERS
    with st.expander("📤 Upload Data"):
        uploaded_file = st.file_uploader("Daily Input", type=['xlsx', 'csv'])
        daily_defaults = {}
        if uploaded_file:
            try:
                df_up = pd.read_csv(uploaded_file) if uploaded_file.name.endswith('.csv') else pd.read_excel(uploaded_file)
                if 'Parameter' in df_up.columns:
                    df_up.set_index('Parameter', inplace=True)
                    daily_defaults = df_up.to_dict()
                    st.toast("Daily Data Applied", icon="✅")
                else: st.error("Daily file missing 'Parameter'.")
            except: st.error("Read Error")
            
        bulk_file = st.file_uploader("Bulk History", type=['csv'])
        if bulk_file and st.button("🚀 Process Bulk"):
            try:
                df_b = pd.read_csv(bulk_file)
                df_b['Date'] = pd.to_datetime(df_b['Date'])
                if repo:
                    df_comb = pd.concat([hist_df, df_b], ignore_index=True)
                    save_history(repo, df_comb, sha)
                    st.success("Bulk Uploaded!")
            except: st.error("Bulk Error")

        col_dl1, col_dl2 = st.columns(2)
        with col_dl1:
            # PRE-FILLED TEMPLATE - DEFERRED
            pass
        with col_dl2:
            st.download_button("Bulk Tpl", generate_bulk_template().to_csv(index=False), "bulk.csv")

    st.markdown("---")
    
    # INPUTS
    tab_conf, tab_inp = st.tabs(["⚙️ Config", "📝 Inputs"])
    
    with tab_conf:
        lim_sox = st.number_input("SOx Limit", value=600)
        lim_nox = st.number_input("NOx Limit", value=450)
        t_u1 = st.number_input("U1 Target HR", 2300); g_u1 = st.number_input("U1 GCV", 3600)
        t_u2 = st.number_input("U2 Target HR", 2310); g_u2 = st.number_input("U2 GCV", 3550)
        t_u3 = st.number_input("U3 Target HR", 2295); g_u3 = st.number_input("U3 GCV", 3620)
        coal_ash = st.number_input("Ash %", 35.0); pond_cap = st.number_input("Pond Cap", 500000); pond_curr = st.number_input("Pond Stock", 350000)
        
    with tab_inp:
        units_data = []
        configs = [{'target_hr': t_u1, 'gcv': g_u1, 'limits':{'sox':lim_sox, 'nox':lim_nox}}, 
                   {'target_hr': t_u2, 'gcv': g_u2, 'limits':{'sox':lim_sox, 'nox':lim_nox}}, 
                   {'target_hr': t_u3, 'gcv': g_u3, 'limits':{'sox':lim_sox, 'nox':lim_nox}}]
        
        def val(u_id, row_key, col_key, def_v):
            if u_id in hist_data and col_key in hist_data[u_id] and pd.notna(hist_data[u_id][col_key]):
                return float(hist_data[u_id][col_key])
            if f"Unit {u_id}" in daily_defaults and row_key in daily_defaults[f"Unit {u_id}"]:
                return float(daily_defaults[f"Unit {u_id}"][row_key])
            return def_v

        for i in range(1, 4):
            u = str(i)
            with st.expander(f"Unit {i}"):
                gen = st.number_input(f"U{u} Gen", value=val(u, 'Generation (MU)', 'Gen', 8.4), key=f"g{u}")
                hr = st.number_input(f"U{u} HR", value=val(u, 'Heat Rate (kcal/kWh)', 'HR', 2380.0), key=f"h{u}")
                vac = st.number_input(f"U{u} Vac", value=val(u, 'Vacuum (kg/cm2)', 'Vacuum', -0.90), step=0.001, format="%.3f", key=f"v{u}")
                ms = st.number_input(f"U{u} MS", value=val(u, 'MS Temp (C)', 'MS Temp', 535.0), key=f"m{u}")
                fg = st.number_input(f"U{u} FG", value=val(u, 'FG Temp (C)', 'FG Temp', 135.0), key=f"f{u}")
                spray = st.number_input(f"U{u} Spray", value=val(u, 'Spray (TPH)', 'Spray', 20.0), key=f"s{u}")
                sox = st.number_input(f"U{u} SOx", value=val(u, 'SOx (mg/Nm3)', 'SOx', 550.0), key=f"sx{u}")
                nox = st.number_input(f"U{u} NOx", value=val(u, 'NOx (mg/Nm3)', 'NOx', 400.0), key=f"nx{u}")
                
                ash_cem = st.number_input(f"U{u} to Cement", value=val(u, 'Ash to Cement (Tons)', 'Ash Cement', 1000.0), key=f"ac{u}")
                ash_brk = st.number_input(f"U{u} to Bricks", value=val(u, 'Ash to Bricks (Tons)', 'Ash Bricks', 500.0), key=f"ab{u}")
                
                ash_p = {'ash_pct': val(u, 'Ash %', 'Coal Ash %', coal_ash), 'util_cem': ash_cem, 'util_brick': ash_brk, 'biomass': val(u, 'Biomass (Tons)', 'Biomass', 0.0)}
                units_data.append(calculate_unit(u, gen, hr, {'vac':vac, 'ms':ms, 'fg':fg, 'spray':spray, 'sox':sox, 'nox':nox}, configs[i-1], ash_p))

        st.markdown("---")
        bio_u1 = st.number_input("Bio U1", value=val('1', 'Biomass (Tons)', 'Biomass', 0.0))
        bio_u2 = st.number_input("Bio U2", value=val('2', 'Biomass (Tons)', 'Biomass', 0.0))
        bio_u3 = st.number_input("Bio U3", value=val('3', 'Biomass (Tons)', 'Biomass', 0.0))
        sol_u1 = st.number_input("Solar", value=val('1', 'Solar (MU)', 'Solar', 0.0))
        bio_gcv = 3000.0

    # PRE-FILLED DOWNLOAD LOGIC
    with col_dl1:
        pre_data = {'Parameter': generate_excel_template()['Parameter']}
        for u in units_data:
            idx = int(u['id'])-1
            pre_data[f"Unit {u['id']}"] = [
                u['gen'], u['hr'], u['losses']['Vacuum']*-1/18*0.01-0.92, 535, 135, 20, u['sox'], u['nox'], 
                u['ash']['cem_util'], u['ash']['brick_util'], 
                (bio_u1 if idx==0 else (bio_u2 if idx==1 else bio_u3)), (sol_u1 if idx==0 else 0)
            ]
        out_d = BytesIO()
        with pd.ExcelWriter(out_d, engine='openpyxl') as writer: pd.DataFrame(pre_data).to_excel(writer, index=False)
        st.download_button("📥 Daily (Pre-filled)", out_d.getvalue(), "daily_prefilled.xlsx")

    if st.button("💾 Save to History", use_container_width=True):
        repo = init_github()
        if repo:
            new_rows = []
            for u in units_data:
                row = {
                    "Date": date_in, "Unit": u['id'], "Profit": u['profit'], 
                    "HR": u['hr'], "SOx": u['sox'], "NOx": u['nox'], "Gen": u['gen'],
                    "Ash Util": u['ash']['utilized'], "Coal Ash %": coal_ash,
                    "Vacuum": u['losses']['Vacuum'], "MS Temp": u['losses']['MS Temp'], "FG Temp": u['losses']['Flue Gas'], "Spray": u['losses']['Spray'],
                    "Ash Cement": u['ash']['cem_util'], "Ash Bricks": u['ash']['brick_util'],
                    "Biomass": bio_u1 if u['id']=='1' else (bio_u2 if u['id']=='2' else bio_u3),
                    "Solar": sol_u1 if u['id']=='1' else 0
                }
                new_rows.append(row)
            df_new = pd.DataFrame(new_rows)
            df_comb = pd.concat([hist_df, df_new], ignore_index=True).drop_duplicates(subset=['Date', 'Unit'], keep='last')
            save_history(repo, df_comb, sha)
            st.success("Saved!")
        else: st.error("No Repo")

# --- CALCS ---
fleet_profit = sum(u['profit'] for u in units_data)
fleet_ash_gen = sum(u['ash']['generated'] for u in units_data)
fleet_ash_util = sum(u['ash']['utilized'] for u in units_data)
fleet_ash_stock = fleet_ash_gen - fleet_ash_util
daily_dump = max(1, fleet_ash_stock)
pond_days_left = (pond_cap - pond_curr) / daily_dump if daily_dump > 0 else 9999

total_bio = bio_u1 + bio_u2 + bio_u3
bio_co2 = (total_bio * bio_gcv * 1000 / 3600) * 1.7
sol_co2 = sol_u1 * 1000 * 0.95
green_trees = (bio_co2 + sol_co2) / 0.025
green_homes = (total_bio * 3 + sol_u1 * 1000) / 10 # Approx 10kWh/day

# MTD Calculations
curr_month = date_in.replace(day=1)
if not hist_df.empty:
    hist_df['Date'] = pd.to_datetime(hist_df['Date'])
    mtd_df = hist_df[(hist_df['Date'] >= pd.Timestamp(curr_month)) & (hist_df['Date'] <= pd.Timestamp(date_in))]
    
    mtd_profit = mtd_df['Profit'].sum() if 'Profit' in mtd_df.columns else fleet_profit
    mtd_ash = mtd_df['Ash Util'].sum() if 'Ash Util' in mtd_df.columns else fleet_ash_util
else:
    mtd_profit = fleet_profit
    mtd_ash = fleet_ash_util

# --- LAYOUT ---
st.title("🏭 GMR Kamalanga 5S Dashboard")
c_top1, c_top2 = st.columns([5, 1])
with c_top1:
    st.markdown(f"**Date:** {date_in.strftime('%d-%b-%Y')} | **Fleet P&L:** {'🟢' if fleet_profit>0 else '🔴'} ₹ {fleet_profit:,.0f}")
with c_top2:
    if st.button("📄 A4 PDF"):
        ash_d = {'gen':fleet_ash_gen, 'util':fleet_ash_util, 'pond_days':pond_days_left, 'bricks':sum(u['ash']['bricks_made'] for u in units_data), 'burj_pct':sum(u['ash']['burj_pct'] for u in units_data)}
        grn_d = {'bio_co2':bio_co2, 'sol_co2':sol_co2, 'trees':green_trees}
        pdf_b = create_full_pdf(units_data, fleet_profit, ash_d, grn_d)
        b64 = base64.b64encode(pdf_b).decode()
        st.markdown(f'<a href="data:application/pdf;base64,{b64}" download="GMR_Report.pdf">Download</a>', unsafe_allow_html=True)

# TABS
tabs = st.tabs(["🏠 War Room", "🌿 Sustainability", "🪨 Ash", "☀️ Green", "⚙️ Unit 1", "⚙️ Unit 2", "⚙️ Unit 3", "📈 Trends", "🎮 Sim", "ℹ️ Info"])

def display_info(summary, formula):
    with st.expander("ℹ️ How to Read This Tab"):
        st.markdown(f"**Summary:** {summary}")
        st.markdown(f"**Formula:** `{formula}`")

# TAB 1: WAR ROOM
with tabs[0]:
    display_info("Executive summary. 'MTD' = Month to Date.", "P&L = (Target HR - Actual HR) * Gen * Coal Cost + Benefits")
    cols = st.columns(4)
    for i, u in enumerate(units_data):
        border = "border-good" if u['profit'] > 0 else "border-bad"
        diff = u['target_hr'] - u['hr']
        with cols[i]:
            st.markdown(f"""
            <div class="glass-card {border}">
                <div class="unit-header">UNIT {u['id']}</div>
                <div class="big-val">₹ {u['profit']:,.0f}</div>
                <div class="sub-lbl">Daily Net Impact</div>
                <hr style="border-color:#ffffff33;">
                <div style="text-align:left; font-size:12px;">
                    <div style="display:flex; justify-content:space-between;"><span>Target:</span><b>{u['target_hr']:.0f}</b></div>
                    <div style="display:flex; justify-content:space-between;"><span>Actual:</span><b>{u['hr']:.0f}</b></div>
                    <div style="display:flex; justify-content:space-between;"><span>Diff:</span><b style="color:{'#00ff88' if diff>0 else '#ff3333'}">{diff:.0f}</b></div>
                    <div style="margin-top:5px; border-top:1px solid #444; padding-top:5px;">
                        SOx: {u['sox']} | NOx: {u['nox']}
                    </div>
                </div>
            </div>
            """, unsafe_allow_html=True)
    
    with cols[3]:
        clr = "#00ff88" if pond_days_left > 60 else "#FF3333"
        st.markdown(f"""
        <div class="glass-card" style="border-top: 4px solid {clr}">
            <div class="unit-header">ASH POND</div>
            <div class="big-val" style="color:{clr}">{pond_days_left:.0f} Days</div>
            <div class="sub-lbl">Capacity Remaining</div>
            <div style="font-size:11px; color:#aaa; margin-top:5px;">MTD Profit: ₹ {mtd_profit:,.0f}</div>
        </div>""", unsafe_allow_html=True)

    with st.expander("💰 Why am I in Loss/Profit?"):
        st.write("""
        **Core Logic:** `(Target Heat Rate - Actual Heat Rate) * Generation`
        1. **Negative Difference:** If Actual HR > Target HR, you are burning *more* coal than designed. This excess cost is your Loss.
        2. **Positive Difference:** If Actual HR < Target HR, you save coal. This saving + ESCert Value + Carbon Credit = Profit.
        """)

# TAB 2: COMPLIANCE
with tabs[1]:
    display_info("Tracks Emission Compliance & Green Initiatives.", "Total Emissions = Gen * Emission Factor")
    
    c1, c2 = st.columns(2)
    with c1:
        st.markdown("#### 🌍 Emissions Status")
        fleet_sox = sum(u['sox'] for u in units_data)/3
        fleet_nox = sum(u['nox'] for u in units_data)/3
        st.metric("Avg SOx", f"{fleet_sox:.0f} mg/Nm3", delta=f"{600-fleet_sox:.0f} headroom")
        st.metric("Avg NOx", f"{fleet_nox:.0f} mg/Nm3", delta=f"{450-fleet_nox:.0f} headroom")
        if fleet_sox > 600: st.error("⚠️ FLEET ACID RAIN RISK")
        
    with c2:
        st.markdown("#### 🌳 Greenbelt Reality Check")
        real_trees = 354762
        virtual_trees = green_trees + sum(u['trees'] for u in units_data)
        st.info("**Physical:** Actual trees planted.\n**Virtual:** CO2 reduction converted to 'Tree Equivalent'.")
        
        c_g1, c_g2 = st.columns(2)
        c_g1.metric("Physical Trees", f"{real_trees:,.0f}")
        c_g2.metric("Virtual Offset", f"{virtual_trees:,.0f}")

# TAB 3: ASH
with tabs[2]:
    display_info("Ash Utilization, Stock, and Brick Potential.", "Pond Life = Remaining Cap / (Gen - Util)")
    c1, c2 = st.columns(2)
    with c1:
        st.metric("Ash Generated", f"{fleet_ash_gen:,.0f} T")
        st.metric("Ash Utilized", f"{fleet_ash_util:,.0f} T", delta=f"{(fleet_ash_util/fleet_ash_gen*100 if fleet_ash_gen else 0):.1f}%")
        
        # Cement vs Bricks Visual
        ash_breakdown = pd.DataFrame({
            'Type': ['Cement', 'Bricks'],
            'Tons': [sum(u['ash']['cem_util'] for u in units_data), sum(u['ash']['brick_util'] for u in units_data)]
        })
        fig_pie = px.pie(ash_breakdown, values='Tons', names='Type', hole=0.4, template='plotly_dark')
        fig_pie.update_layout(height=200, margin=dict(l=0,r=0,t=0,b=0), paper_bgcolor='rgba(0,0,0,0)')
        st.plotly_chart(fig_pie, use_container_width=True)

    with c2:
        burj = sum(u['ash']['burj_pct'] for u in units_data)
        st.markdown(f'<div class="burj-text">{burj:.2f}%</div>', unsafe_allow_html=True)
        st.markdown("of a **Burj Khalifa** (Volume Equivalent)")
        st.metric("MTD Utilization", f"{mtd_ash:,.0f} T")

# TAB 4: RENEWABLES
with tabs[3]:
    display_info("Impact of Biomass Co-firing and Solar Power.", "CO2 Saved = Coal Equiv * 1.7")
    c1, c2 = st.columns(2)
    with c1: 
        st.metric("Biomass CO2 Saved", f"{bio_co2:.2f} T")
        st.metric("Houses Powered", f"{green_homes:,.0f}")
    with c2: 
        st.metric("Solar CO2 Saved", f"{sol_co2:.2f} T")
    if anim_sun: st_lottie(anim_sun, height=150, key="sun_anim")

# TABS 5-7: UNITS
for i, tab in enumerate([tabs[4], tabs[5], tabs[6]]):
    with tab:
        u = units_data[i]
        render_unit_detail(u, configs)

# TAB 8: TRENDS (FIXED GRAPH)
with tabs[7]:
    display_info("Historical Performance Analysis", "Double-click legend to isolate Unit.")
    filter_opt = st.radio("Duration", ["7 Days", "30 Days"], horizontal=True)
    
    if not hist_df.empty:
        # Filter Logic
        cutoff = datetime.now() - timedelta(days=7 if filter_opt=="7 Days" else 30)
        filtered_df = hist_df[hist_df['Date'] >= cutoff]
        
        # Make Unit Categorical for discrete colors
        filtered_df['Unit'] = filtered_df['Unit'].astype(str)
        
        # Dual Axis Chart
        fig = make_subplots(specs=[[{"secondary_y": True}]])
        
        # HR Lines (One per unit)
        colors = {'1': '#00ccff', '2': '#ff9933', '3': '#00ff88'}
        for u_id in filtered_df['Unit'].unique():
            u_df = filtered_df[filtered_df['Unit'] == u_id]
            fig.add_trace(
                go.Scatter(x=u_df['Date'], y=u_df['HR'], name=f"Unit {u_id} HR", mode='lines+markers', line=dict(color=colors.get(u_id, 'white'))),
                secondary_y=False,
            )
        
        # Profit Bar (Fleet Profit Sum per day)
        fleet_trend = filtered_df.groupby('Date')['Profit'].sum().reset_index()
        fig.add_trace(
            go.Bar(x=fleet_trend['Date'], y=fleet_trend['Profit'], name="Fleet Profit", opacity=0.3, marker_color='white'),
            secondary_y=True,
        )
        
        fig.update_layout(
            title="Heat Rate (Left) vs Fleet Profit (Right)", 
            template="plotly_dark", 
            paper_bgcolor='rgba(0,0,0,0)', 
            plot_bgcolor='rgba(0,0,0,0)',
            hovermode="x unified",
            legend=dict(orientation="h", y=1.1)
        )
        fig.update_yaxes(title_text="Heat Rate (kcal/kWh)", secondary_y=False, showgrid=False)
        fig.update_yaxes(title_text="Profit (Rs)", secondary_y=True, showgrid=False)
        
        st.plotly_chart(fig, use_container_width=True)
    else: st.info("No history data available.")

# TAB 9: SIMULATOR
with tabs[8]:
    st.markdown("### 🎮 Simulator")
    s_vac = st.slider("Target Vacuum", -0.85, -0.99, -0.92)
    new_loss = (abs(s_vac) - 0.92) * 100 * 15
    st.metric("Impact", f"{new_loss:.1f} kcal/kWh")

# TAB 10: INFO
with tabs[9]:
    try: st.image("1000051705.jpg", use_container_width=True)
    except: pass
    st.markdown("### 5S Pillars: Sort, Set in Order, Shine, Standardize, Sustain")
