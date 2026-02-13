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
import json

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

# --- 2. VISUAL OVERHAUL (BRIGHTER FONTS) ---
st.markdown("""
    <style>
    .stApp { background-color: #f0f2f6; background: linear-gradient(135deg, #0f172a 0%, #1e293b 100%); color: #ffffff; font-family: 'Roboto', sans-serif; }
    .stTabs [data-baseweb="tab-list"] { gap: 8px; background-color: rgba(255,255,255,0.05); padding: 10px; border-radius: 50px; }
    .stTabs [data-baseweb="tab"] { height: 40px; white-space: pre-wrap; background-color: transparent; border-radius: 20px; color: #f8fafc; font-weight: 600; font-size: 16px; }
    .stTabs [aria-selected="true"] { background-color: #F59E0B; color: white; }
    .glass-card { background: rgba(30, 41, 59, 0.7); border: 1px solid rgba(255, 255, 255, 0.2); border-radius: 12px; padding: 20px; margin-bottom: 15px; box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1); text-align: center; transition: transform 0.2s ease; }
    .glass-card:hover { transform: translateY(-2px); border-color: rgba(255, 255, 255, 0.4); }
    .border-good { border-top: 4px solid #4ade80; }
    .border-bad { border-top: 4px solid #f87171; }
    .border-shut { border-top: 4px solid #94a3b8; }
    .border-green { border-top: 4px solid #34d399; }
    .border-solar { border-top: 4px solid #fde047; }
    .big-val { font-family: 'Orbitron', sans-serif; font-size: 28px; font-weight: 700; color: #ffffff; text-shadow: 1px 1px 3px rgba(0,0,0,0.8); }
    .sub-lbl { font-size: 13px; color: #e2e8f0; text-transform: uppercase; letter-spacing: 0.5px; font-weight: 600; margin-top: 5px; }
    .section-header { font-family: 'Oswald', sans-serif; font-size: 24px; color: #fcd34d; margin: 20px 0 10px 0; border-bottom: 1px solid #444; padding-bottom: 5px; }
    .unit-header { font-size: 15px; font-weight: 800; color: #f8fafc; margin-bottom: 10px; letter-spacing: 1px;}
    </style>
""", unsafe_allow_html=True)

# --- 3. GLOBAL HELPERS ---
def display_info(details):
    with st.expander("ℹ️ How to Read This Tab (Calculations & Logic)"):
        st.markdown(details)

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

# --- HISTORY CSV HANDLING ---
def load_history(repo):
    if not repo: return pd.DataFrame()
    try:
        file = repo.get_contents("plant_history_v28.csv", ref=st.secrets["BRANCH"])
        df = pd.read_csv(StringIO(file.decoded_content.decode()))
        cols = ['Gen', 'HR', 'Target HR', 'Profit', 'Vacuum', 'MS Temp', 'FG Temp', 'Spray', 'SOx', 'NOx', 'Ash Util', 'Ash Cement', 'Ash Bricks', 'Biomass', 'Solar']
        for c in cols:
            if c in df.columns: df[c] = pd.to_numeric(df[c], errors='coerce').fillna(0)
        df['Date'] = pd.to_datetime(df['Date'])
        cutoff_date = pd.Timestamp("2026-01-31")
        df = df[df['Date'] <= cutoff_date]
        df = df.sort_values('Date').drop_duplicates(subset=['Date', 'Unit'], keep='last')
        return df, file.sha
    except: 
        return pd.DataFrame(), None

def save_history(repo, df, sha):
    try:
        df['Date'] = pd.to_datetime(df['Date']).dt.strftime('%Y-%m-%d')
        df = df.drop_duplicates(subset=['Date', 'Unit'], keep='last')
        csv_content = df.to_csv(index=False)
        msg = "Update" if sha else "Init"
        if sha: repo.update_file("plant_history_v28.csv", msg, csv_content, sha, branch=st.secrets["BRANCH"])
        else: repo.create_file("plant_history_v28.csv", msg, csv_content, branch=st.secrets["BRANCH"])
        return True
    except: return False

# --- CONFIGURATION STATE HANDLING ---
def get_default_config():
    return {
        "u1_target_hr": 2315, "u2_target_hr": 2315, "u3_target_hr": 2315,
        "u1_gcv": 3600, "u2_gcv": 3550, "u3_gcv": 3620,
        "coal_ash_pct": 35.0, "pond_cap": 500000, "pond_curr": 350000,
        "limits": {"nox": 450, "sox": 1400, "spm": 50}
    }

def load_plant_config(repo):
    default = get_default_config()
    if not repo: return default, None
    try:
        file = repo.get_contents("plant_config.json", ref=st.secrets["BRANCH"])
        data = json.loads(file.decoded_content.decode())
        return {**default, **data}, file.sha
    except:
        return default, None

def save_plant_config(repo, data, sha):
    if not repo: return False
    try:
        if sha: repo.update_file("plant_config.json", "Update Config", json.dumps(data), sha, branch=st.secrets["BRANCH"])
        else: repo.create_file("plant_config.json", "Init Config", json.dumps(data), branch=st.secrets["BRANCH"])
        return True
    except: return False

# --- ANALYTICS STATE HANDLING ---
def load_analytics_state(repo):
    default_data = {
        "greenbelt_raw": [], 
        "ash_raw": []
    }
    if not repo: return default_data, None
    
    try:
        file = repo.get_contents("analytics_state_v1.json", ref=st.secrets["BRANCH"])
        data = json.loads(file.decoded_content.decode())
        
        if "greenbelt_raw" not in data and len(data) > 2:
            converted_list = []
            for species, details in data.items():
                if isinstance(details, dict) and "year_wise_plantation" in details:
                    for yr, count in details["year_wise_plantation"].items():
                        if count > 0:
                            mortality = details.get("mortality_rate", 0.1)
                            matured = count * (1 - mortality)
                            converted_list.append({
                                "Year": yr,
                                "Species": species,
                                "Planted": count,
                                "Matured": int(matured)
                            })
            if converted_list:
                data = {"greenbelt_raw": converted_list, "ash_raw": data.get("ash_raw", [])} 
        
        return data, file.sha
    except:
        return default_data, None

def save_analytics_state(repo, data, sha):
    if not repo: return False
    try:
        if sha: repo.update_file("analytics_state_v1.json", "Update Analytics", json.dumps(data), sha, branch=st.secrets["BRANCH"])
        else: repo.create_file("analytics_state_v1.json", "Init Analytics", json.dumps(data), branch=st.secrets["BRANCH"])
        return True
    except: return False

def parse_plantation_file(uploaded_file): return []
def parse_ash_file(uploaded_file): return []

def generate_excel_template():
    return pd.DataFrame({'Parameter': ['Gen (MU)', 'HR (kcal/kWh)', 'Vac (kg/cm2)', 'MS (C)', 'FG (C)', 'Spray (TPH)', 'SOx', 'NOx'], 'Unit 1': [0]*8, 'Unit 2': [0]*8, 'Unit 3': [0]*8})

def format_lacs(value):
    val_lac = value / 100000
    return f"₹ {val_lac:,.2f} Lac"

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
    pdf.add_page()
    pdf.set_font("Arial", 'B', 14)
    pdf.cell(0, 10, "Environment & Ash", 0, 1)
    pdf.ln(5)
    pdf.set_font("Arial", size=10)
    pdf.cell(0, 10, f"Ash Gen: {ash_data['gen']:.0f} T | Util: {ash_data['util']:.0f} T", 0, 1)
    pdf.cell(0, 10, f"Solar CO2 Saved: {green_data['sol_co2']:.2f} T", 0, 1)
    return pdf.output(dest='S').encode('latin-1')

# --- 5. CALCULATION ENGINE ---
def calculate_unit(u_id, gen, hr, inputs, design_vals, ash_params):
    TARGET_HR = design_vals['target_hr']; DESIGN_HR = 2250; COAL_GCV = design_vals['gcv']
    
    coal_consumed = (gen * hr * 1000) / COAL_GCV if COAL_GCV > 0 and gen > 0 else 0
    co2_emitted = coal_consumed * 1.7 
    
    if gen <= 0 or hr <= 0:
        profit = -1 * (350 * 1000 * 24 * 3) 
        score = 0
        l_vac = l_ms = l_fg = l_spray = l_unacc = 0
        carbon_tons = escerts = 0
        status = "SHUTDOWN"
    else:
        status = "RUNNING"
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
    
    ash_gen = coal_consumed * (ash_params['ash_pct'] / 100)
    ash_util = ash_params['util_cem'] + ash_params['util_brick']
    ash_stocked = ash_gen - ash_util
    bricks_current = ash_params['util_brick'] * 666
    burj_pct = (bricks_current / 165_000_000) * 100
    homes_bio = ash_params.get('biomass', 0) * 1000 * 1.2 / 4 
    
    return {
        "id": u_id, "gen": gen, "hr": hr, "profit": profit, "escerts": escerts if status=="RUNNING" else 0, "carbon": carbon_tons if status=="RUNNING" else 0,
        "co2_emitted": co2_emitted,
        "score": score, "sox": inputs['sox'], "nox": inputs['nox'],
        "losses": {"Vacuum": abs(l_vac), "MS Temp": l_ms, "Flue Gas": l_fg, "Spray": l_spray, "Unaccounted": l_unacc},
        "ash": {"generated": ash_gen, "utilized": ash_util, "stocked": ash_stocked, 
                "bricks_made": bricks_current, "cem_util": ash_params['util_cem'],
                "brick_util": ash_params['util_brick'], "burj_pct": burj_pct},
        "limits": design_vals['limits'], "trees": abs((carbon_tons if status=="RUNNING" else 0) / 0.025),
        "target_hr": TARGET_HR, "homes_bio": homes_bio,
        "inputs": inputs, "status": status
    }

# --- 6. RENDER FUNCTION ---
def render_unit_detail(u, configs):
    st.markdown(f"### 🔍 Unit {u['id']} Deep Dive")
    if u['status'] == "SHUTDOWN":
        st.error("🚨 UNIT SHUTDOWN - No Efficiency Analysis Available")
        return
    c1, c2 = st.columns([1, 1])
    with c1:
        st.markdown("#### 🏎️ Efficiency Gauge")
        target = configs[int(u['id'])-1]['target_hr']
        fig = go.Figure(go.Indicator(
            mode = "gauge+number+delta", value = u['hr'],
            delta = {'reference': target, 'increasing': {'color': "#ef4444"}},
            gauge = {
                'axis': {'range': [2000, 2600]}, 'bar': {'color': "#38bdf8"},
                'steps': [{'range': [2000, target], 'color': "rgba(0,255,0,0.2)"}, {'range': [target, 2600], 'color': "rgba(255,0,0,0.2)"}],
                'threshold': {'line': {'color': "#ef4444", 'width': 4}, 'thickness': 0.75, 'value': u['hr']}
            }
        ))
        fig.update_layout(height=250, margin=dict(l=20,r=20,t=0,b=0), paper_bgcolor='rgba(0,0,0,0)', font_color='white')
        st.plotly_chart(fig, width="stretch", key=f"gauge_{u['id']}")
    with c2:
        st.markdown("#### 🔧 Loss Analysis")
        loss_df = pd.DataFrame(list(u['losses'].items()), columns=['Param', 'Loss']).sort_values('Loss')
        fig_bar = px.bar(loss_df, x='Loss', y='Param', orientation='h', text='Loss', color='Loss', 
                         color_continuous_scale=['#444', '#ef4444'], template='plotly_dark')
        fig_bar.update_layout(
            paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', font_color='white', height=250,
            xaxis=dict(showgrid=False), yaxis=dict(showgrid=False)
        )
        fig_bar.update_traces(texttemplate='%{text:.1f}', textposition='outside')
        st.plotly_chart(fig_bar, width="stretch", key=f"bar_{u['id']}")
    st.divider()
    c3, c4 = st.columns(2)
    with c3: st.markdown(f"""<div class="glass-card" style="border-left: 4px solid #fcd34d"><div class="p-title" style="color:#f8fafc; font-weight:800;">5S Score</div><div class="big-val" style="color:#fcd34d">{u['score']:.1f}</div><div class="sub-lbl">Technical Hygiene</div></div>""", unsafe_allow_html=True)
    with c4: st.markdown(f"""<div class="glass-card" style="border-left: 4px solid #38bdf8"><div class="p-title" style="color:#f8fafc; font-weight:800;">Carbon Credits</div><div class="big-val" style="color:#38bdf8">{u['carbon']:.1f}</div><div class="sub-lbl">Tons CO2 Avoided</div></div>""", unsafe_allow_html=True)

# --- 7. SIDEBAR & DATA LOADING ---
with st.sidebar:
    try: st.image("1000051706.png", width="stretch")
    except: st.markdown("## **GMR POWER**") 
    st.title("Control Panel")
    
    date_in = st.date_input("📅 Dashboard Date", datetime.now())
    units_data = []
    repo = init_github()
    hist_df, sha = load_history(repo)
    analytics_state, analytics_sha = load_analytics_state(repo)
    plant_conf, conf_sha = load_plant_config(repo)
    
    hist_data = {}
    if not hist_df.empty:
        date_in_ts = pd.Timestamp(date_in)
        day_df = hist_df[hist_df['Date'] == date_in_ts]
        if not day_df.empty:
            st.success(f"Data Found: {date_in.strftime('%d %b %Y')}")
            for _, row in day_df.iterrows():
                hist_data[str(row['Unit'])] = row
        else:
            st.info("No history for this date. Using inputs.")
    
    with st.expander("📤 Upload Operational Data"):
        uploaded_file = st.file_uploader("Daily Input", type=['xlsx', 'csv'])
        daily_defaults = {}
        if uploaded_file:
            try:
                df_up = pd.read_csv(uploaded_file) if uploaded_file.name.endswith('.csv') else pd.read_excel(uploaded_file)
                if 'Parameter' in df_up.columns:
                    df_up.set_index('Parameter', inplace=True)
                    daily_defaults = df_up.to_dict()
                    st.session_state['daily_data'] = daily_defaults
                    st.toast("Daily Data Applied", icon="✅")
            except: st.error("Read Error")
            
        bulk_file = st.file_uploader("Bulk History", type=['csv'])
        if bulk_file and st.button("🚀 Process Bulk"):
            try:
                df_b = pd.read_csv(bulk_file)
                df_b['Date'] = pd.to_datetime(df_b['Date']).dt.strftime('%Y-%m-%d')
                if repo:
                    file = repo.get_contents("plant_history_v28.csv", ref=st.secrets["BRANCH"])
                    df_curr = pd.read_csv(StringIO(file.decoded_content.decode()))
                    df_comb = pd.concat([df_curr, df_b], ignore_index=True)
                    df_comb['Date'] = pd.to_datetime(df_comb['Date'])
                    df_comb = df_comb.sort_values('Date')
                    df_comb['Date'] = df_comb['Date'].dt.strftime('%Y-%m-%d')
                    df_comb = df_comb.drop_duplicates(subset=['Date', 'Unit'], keep='last')
                    csv_c = df_comb.to_csv(index=False)
                    repo.update_file("plant_history_v28.csv", "Bulk Add", csv_c, file.sha, branch=st.secrets["BRANCH"])
                    st.success(f"Bulk Uploaded! Records: {len(df_comb)}")
                    st.rerun()
            except Exception as e: st.error(f"Bulk Error: {e}")

    with st.expander("📂 Supplementary Reports (Analytics)"):
        st.info("Upload 'Ash.xlsx' or 'Plantation.xlsx' to update Analytics.")
        supp_file = st.file_uploader("Upload Report", type=['xlsx', 'csv'])
        if supp_file:
            if "ash" in supp_file.name.lower():
                ash_parsed = parse_ash_file(supp_file)
                if ash_parsed:
                    analytics_state['ash_raw'] = ash_parsed
                    save_analytics_state(repo, analytics_state, analytics_sha)
                    st.success("Ash Data Saved!")
                    st.rerun()
            elif "plantation" in supp_file.name.lower():
                plant_parsed = parse_plantation_file(supp_file)
                if plant_parsed:
                    analytics_state['greenbelt_raw'] = plant_parsed
                    save_analytics_state(repo, analytics_state, analytics_sha)
                    st.success("Plantation Data Saved!")
                    st.rerun()

    col_dl1, col_dl2 = st.columns(2)
    with col_dl1:
        if units_data:
            pre_data_dict = {'Parameter': generate_excel_template()['Parameter']}
            for u in units_data:
                idx = int(u['id'])-1
                inp = u['inputs']
                vals = [u['gen'], u['hr'], inp['vac'], inp['ms'], inp['fg'], inp['spray'], u['sox'], u['nox'], u['ash']['cem_util'], u['ash']['brick_util'], (bio_u1 if idx==0 else (bio_u2 if idx==1 else bio_u3)), (sol_u1 if idx==0 else 0)]
                pre_data_dict[f"Unit {u['id']}"] = vals
            out_d = BytesIO()
            pd.DataFrame(pre_data_dict).to_excel(out_d, index=False, engine='openpyxl', sheet_name='DailyData')
            st.download_button("📥 Daily (Pre-filled)", out_d.getvalue(), "daily_prefilled.xlsx")

    st.markdown("---")
    
    # --- CONFIG TAB ---
    tab_conf, tab_inp = st.tabs(["⚙️ Config", "📝 Inputs"])
    with tab_conf:
        st.subheader("🏭 Plant Design Parameters")
        c_conf1, c_conf2 = st.columns(2)
        with c_conf1:
            lim_sox = st.number_input("SOx Limit", value=plant_conf['limits']['sox'])
            lim_nox = st.number_input("NOx Limit", value=plant_conf['limits']['nox'])
            lim_spm = st.number_input("SPM Limit", value=plant_conf['limits']['spm'])
            coal_ash = st.number_input("Ash %", value=plant_conf['coal_ash_pct'])
        with c_conf2:
            t_u1 = st.number_input("U1 Target HR", value=plant_conf['u1_target_hr'])
            t_u2 = st.number_input("U2 Target HR", value=plant_conf['u2_target_hr'])
            t_u3 = st.number_input("U3 Target HR", value=plant_conf['u3_target_hr'])
        
        g_u1, g_u2, g_u3 = plant_conf['u1_gcv'], plant_conf['u2_gcv'], plant_conf['u3_gcv']
        pond_cap = plant_conf.get('pond_cap', 500000)
        pond_curr = st.number_input("Pond Current Stock", value=plant_conf.get('pond_curr', 350000))

        if st.button("💾 Save Config Permanently"):
            new_conf = {
                "u1_target_hr": t_u1, "u2_target_hr": t_u2, "u3_target_hr": t_u3,
                "u1_gcv": g_u1, "u2_gcv": g_u2, "u3_gcv": g_u3,
                "coal_ash_pct": coal_ash, "pond_cap": pond_cap, "pond_curr": pond_curr,
                "limits": {"nox": lim_nox, "sox": lim_sox, "spm": lim_spm}
            }
            if save_plant_config(repo, new_conf, conf_sha):
                st.success("Configuration Updated on GitHub!")
                st.rerun()
        
    with tab_inp:
        configs = [{'target_hr': t_u1, 'gcv': g_u1, 'limits':{'sox':lim_sox, 'nox':lim_nox}}, 
                   {'target_hr': t_u2, 'gcv': g_u2, 'limits':{'sox':lim_sox, 'nox':lim_nox}}, 
                   {'target_hr': t_u3, 'gcv': g_u3, 'limits':{'sox':lim_sox, 'nox':lim_nox}}]
        
        def val(u_id, row_key, col_key, def_v):
            if u_id in hist_data and col_key in hist_data[u_id] and pd.notna(hist_data[u_id][col_key]):
                return float(hist_data[u_id][col_key])
            sess = st.session_state.get('daily_data', {})
            if f"Unit {u_id}" in sess and row_key in sess[f"Unit {u_id}"]:
                return float(sess[f"Unit {u_id}"][row_key])
            return def_v

        for i in range(1, 4):
            u = str(i)
            d_key = date_in.strftime('%Y%m%d')
            with st.expander(f"Unit {i}"):
                gen = st.number_input(f"U{u} Gen", value=val(u, 'Generation (MU)', 'Gen', 8.4), key=f"g{u}_{d_key}")
                hr = st.number_input(f"U{u} HR", value=val(u, 'Heat Rate (kcal/kWh)', 'HR', 2380.0), key=f"h{u}_{d_key}")
                vac = st.number_input(f"U{u} Vac", value=val(u, 'Vacuum (kg/cm2)', 'Vacuum', -0.90), step=0.001, format="%.3f", key=f"v{u}_{d_key}")
                ms = st.number_input(f"U{u} MS", value=val(u, 'MS Temp (C)', 'MS Temp', 535.0), key=f"m{u}_{d_key}")
                fg = st.number_input(f"U{u} FG", value=val(u, 'FG Temp (C)', 'FG Temp', 135.0), key=f"f{u}_{d_key}")
                spray = st.number_input(f"U{u} Spray", value=val(u, 'Spray (TPH)', 'Spray', 20.0), key=f"s{u}_{d_key}")
                sox = st.number_input(f"U{u} SOx", value=val(u, 'SOx (mg/Nm3)', 'SOx', 550.0), key=f"sx{u}_{d_key}")
                nox = st.number_input(f"U{u} NOx", value=val(u, 'NOx (mg/Nm3)', 'NOx', 400.0), key=f"nx{u}_{d_key}")
                ash_cem = st.number_input(f"U{u} to Cement", value=val(u, 'Ash to Cement (Tons)', 'Ash Cement', 1000.0), key=f"ac{u}_{d_key}")
                ash_brk = st.number_input(f"U{u} to Bricks", value=val(u, 'Ash to Bricks (Tons)', 'Ash Bricks', 500.0), key=f"ab{u}_{d_key}")
                ash_p = {'ash_pct': val(u, 'Ash %', 'Coal Ash %', coal_ash), 'util_cem': ash_cem, 'util_brick': ash_brk, 'biomass': val(u, 'Biomass (Tons)', 'Biomass', 0.0)}
                units_data.append(calculate_unit(u, gen, hr, {'vac':vac, 'ms':ms, 'fg':fg, 'spray':spray, 'sox':sox, 'nox':nox}, configs[i-1], ash_p))

        st.markdown("---")
        bio_u1 = st.number_input("Bio U1", value=val('1', 'Biomass (Tons)', 'Biomass', 0.0), key=f"b1_{d_key}")
        bio_u2 = st.number_input("Bio U2", value=val('2', 'Biomass (Tons)', 'Biomass', 0.0), key=f"b2_{d_key}")
        bio_u3 = st.number_input("Bio U3", value=val('3', 'Biomass (Tons)', 'Biomass', 0.0), key=f"b3_{d_key}")
        sol_u1 = st.number_input("Solar", value=val('1', 'Solar (MU)', 'Solar', 0.0), key=f"sol_{d_key}")
        bio_gcv = 3000.0

    if st.button("💾 Save to History", use_container_width=True):
        repo = init_github()
        if repo:
            new_rows = []
            for u in units_data:
                row = {
                    "Date": date_in.strftime('%Y-%m-%d'), "Unit": u['id'], "Profit": u['profit'], 
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

# --- CALCS & CUMULATIVE ASH POND ---
fleet_profit = sum(u['profit'] for u in units_data) if units_data else 0
fleet_ash_gen = sum(u['ash']['generated'] for u in units_data) if units_data else 0
fleet_ash_util = sum(u['ash']['utilized'] for u in units_data) if units_data else 0

# --- ASH YTD & MTD LOGIC FOR VISUALS ---
curr_month_start = pd.Timestamp(date_in.replace(day=1))
date_in_ts = pd.Timestamp(date_in)

if date_in.month >= 4:
    fy_start = pd.Timestamp(year=date_in.year, month=4, day=1)
else:
    fy_start = pd.Timestamp(year=date_in.year-1, month=4, day=1)

# Historical calculations (STRICTLY before today)
past_mtd_ash_gen, past_mtd_ash_util, past_ytd_ash_gen, past_ytd_ash_util, past_mtd_profit = 0, 0, 0, 0, 0

if not hist_df.empty:
    past_mtd_df = hist_df[(hist_df['Date'] >= curr_month_start) & (hist_df['Date'] < date_in_ts)].copy()
    past_ytd_df = hist_df[(hist_df['Date'] >= fy_start) & (hist_df['Date'] < date_in_ts)].copy()
    
    past_mtd_profit = past_mtd_df['Profit'].sum() if not past_mtd_df.empty else 0
    
    def calc_ash_gen(df):
        if df.empty: return 0
        return (df['Gen'] * df['HR'] * 1000 / 3600 * (coal_ash / 100)).sum()
        
    past_mtd_ash_gen = calc_ash_gen(past_mtd_df)
    past_ytd_ash_gen = calc_ash_gen(past_ytd_df)
    past_mtd_ash_util = past_mtd_df['Ash Util'].sum() if not past_mtd_df.empty else 0
    past_ytd_ash_util = past_ytd_df['Ash Util'].sum() if not past_ytd_df.empty else 0

# Add live inputs to get TRUE MTD/YTD
mtd_ash_gen_total = past_mtd_ash_gen + fleet_ash_gen
ytd_ash_gen_total = past_ytd_ash_gen + fleet_ash_gen
mtd_ash_util_total = past_mtd_ash_util + fleet_ash_util
ytd_ash_util_total = past_ytd_ash_util + fleet_ash_util

mtd_dump = mtd_ash_gen_total - mtd_ash_util_total
ytd_dump = ytd_ash_gen_total - ytd_ash_util_total
mtd_profit = past_mtd_profit + fleet_profit

# Dynamic Lagoon Impact Logic
total_pond_cap = pond_cap if pond_cap else 500000
current_pond_stock = pond_curr + ytd_dump
lagoon_fill_pct = min(100, max(0, (current_pond_stock / total_pond_cap) * 100))

# Renewables
total_bio = bio_u1 + bio_u2 + bio_u3
bio_co2 = (total_bio * bio_gcv * 1000 / 3600) * 1.7
sol_co2 = sol_u1 * 1000 * 0.95
solar_homes = (sol_u1 * 1000000) / 4
bio_homes = sum(u['homes_bio'] for u in units_data) if units_data else 0

# --- LAYOUT ---
st.title("🏭 GMR Kamalanga 5S Dashboard")
c_top1, c_top2 = st.columns([5, 1])
with c_top1:
    st.markdown(f"**Date:** {date_in.strftime('%d-%b-%Y')} | **Fleet P&L:** {format_lacs(fleet_profit)}")
with c_top2:
    if st.button("📄 A4 PDF"):
        ash_d = {'gen':fleet_ash_gen, 'util':fleet_ash_util, 'pond_days':9999, 'bricks':sum(u['ash']['bricks_made'] for u in units_data) if units_data else 0, 'burj_pct':sum(u['ash']['burj_pct'] for u in units_data) if units_data else 0}
        grn_d = {'bio_co2':bio_co2, 'sol_co2':sol_co2, 'trees':bio_co2/0.025}
        pdf_b = create_full_pdf(units_data, fleet_profit, ash_d, grn_d)
        b64 = base64.b64encode(pdf_b).decode()
        st.markdown(f'<a href="data:application/pdf;base64,{b64}" download="GMR_Report.pdf">Download</a>', unsafe_allow_html=True)

# TABS
tabs = st.tabs(["🏠 War Room", "🌿 Sustainability", "🪨 Ash Ops", "☀️ Green", "⚙️ Unit 1", "⚙️ Unit 2", "⚙️ Unit 3", "📈 Trends", "🎮 Sim", "📊 Analytics", "ℹ️ Info"])

# TAB 1: WAR ROOM
with tabs[0]:
    display_info(r"""
    **Executive Summary:**
    * **Unit P&L:** Compares actual efficiency vs target. Green = Profit, Red = Loss.
    * **MTD Profit:** Calculated strictly as `Sum(History[1st -> Yesterday]) + Live_Today`.
    """)
    st.markdown('<div class="section-header">📅 Daily Snapshot</div>', unsafe_allow_html=True)
    cols = st.columns(4)
    if units_data:
        for i, u in enumerate(units_data):
            color = "#4ade80" if u['profit'] > 0 else "#f87171"
            border = "border-good" if u['profit'] > 0 else "border-bad"
            if u['status'] == "SHUTDOWN":
                border = "border-shut"
                color = "#94a3b8"
            with cols[i]:
                st.markdown(f"""
                <div class="glass-card {border}">
                    <div class="unit-header">UNIT {u['id']}</div>
                    <div class="big-val" style="color:{color}">{format_lacs(u['profit'])}</div>
                    <div class="sub-lbl">{u['status'] if u['status']=='SHUTDOWN' else 'Daily Net Impact'}</div>
                    <hr style="border-color:#ffffff33;">
                    <div style="text-align:left; font-size:12px; color:#e2e8f0;">
                        <div style="display:flex; justify-content:space-between;"><span>Target:</span><b>{u['target_hr']:.0f}</b></div>
                        <div style="display:flex; justify-content:space-between;"><span>Actual:</span><b>{u['hr']:.0f}</b></div>
                        <div style="margin-top:5px; border-top:1px solid #444; padding-top:5px;">
                            SOx: <span style="color:{'#f87171' if u['sox']>plant_conf['limits']['sox'] else '#fff'}">{u['sox']}</span> | NOx: {u['nox']}
                        </div>
                    </div>
                </div>
                """, unsafe_allow_html=True)
    
    with cols[3]:
        st.markdown(f"""
        <div class="glass-card" style="border-top: 4px solid {'#f87171' if lagoon_fill_pct>80 else '#38bdf8'}">
            <div class="unit-header" style="color:#38bdf8;">ASH LAGOON FILL</div>
            <div class="big-val" style="color:{'#f87171' if lagoon_fill_pct>80 else '#38bdf8'}">{lagoon_fill_pct:.1f}%</div>
            <div class="sub-lbl">Overall Capacity Utilized</div>
            <div style="font-size:11px; color:#cbd5e1; margin-top:5px;">
            Tracking YTD Net Dumping
            </div>
        </div>""", unsafe_allow_html=True)

    st.markdown('<div class="section-header">📆 Monthly Performance (MTD)</div>', unsafe_allow_html=True)
    c_m1, c_m2, c_m3 = st.columns(3)
    c_m1.metric("MTD Fleet Profit", format_lacs(mtd_profit))
    c_m2.metric("MTD Ash Utilization", f"{mtd_ash_util_total:,.0f} Tons")
    c_m3.info("MTD Data aggregates strictly from the 1st of the month to avoid double-counting.")

# TAB 2: SUSTAINABILITY
with tabs[1]:
    display_info(r"""
    **Sustainability & Carbon Footprint:**
    * **Daily CO₂ Emissions:** Calculated as `Coal Consumed (Tons) × 1.7`.
    * **Daily Tree Offset:** `Total Matured Trees × (25 kg / 365 days) / 1000`.
    * **Area Required:** Assumes approx 1000 trees per acre for new plantations to offset the deficit.
    """)
    st.markdown("#### 🏭 Daily Unit CO₂ Emissions")
    cols = st.columns(3)
    total_daily_co2 = 0
    for i, u in enumerate(units_data):
        u_co2 = u.get('co2_emitted', 0)
        total_daily_co2 += u_co2
        with cols[i]:
            st.markdown(f"""
            <div class="glass-card border-bad">
                <div class="unit-header">UNIT {u['id']}</div>
                <div class="big-val" style="color:#f87171">{u_co2:,.0f} T</div>
                <div class="sub-lbl">CO₂ Emitted Today</div>
            </div>""", unsafe_allow_html=True)
            
    st.markdown("#### 🌍 Fleet Combined Effect vs Tree Offset")
    gb_raw = analytics_state.get('greenbelt_raw', [])
    if gb_raw:
        df_gb = pd.DataFrame(gb_raw)
        real_trees = df_gb['Matured'].sum() if 'Matured' in df_gb.columns else 354762
    else:
        real_trees = 354762
        
    yearly_offset_tons = real_trees * 25.0 / 1000.0
    daily_offset_tons = yearly_offset_tons / 365.0
    net_daily_co2 = total_daily_co2 - daily_offset_tons
    
    c_net1, c_net2, c_net3 = st.columns(3)
    c_net1.metric("Total CO₂ Emitted", f"{total_daily_co2:,.0f} T/Day")
    c_net2.metric("Trees CO₂ Offset", f"{daily_offset_tons:,.1f} T/Day", help=f"Annual Tree Offset is {yearly_offset_tons:,.0f} Tons/Year")
    c_net3.metric("Net CO₂ Footprint", f"{net_daily_co2:,.0f} T/Day", delta=f"-{daily_offset_tons:.1f} T offset", delta_color="inverse")
    
    st.divider()
    st.markdown("#### 📆 MTD Carbon Offset & Remediation Plan")
    
    past_co2_emitted = 0
    if not hist_df.empty:
        past_mtd_df = hist_df[(hist_df['Date'] >= curr_month_start) & (hist_df['Date'] < date_in_ts)].copy()
        if not past_mtd_df.empty:
            past_mtd_df['Coal_Tons'] = (past_mtd_df['Gen'] * past_mtd_df['HR'] * 1000) / 3585
            past_co2_emitted = (past_mtd_df['Coal_Tons'] * 1.7).sum()
    
    mtd_co2_emitted = past_co2_emitted + total_daily_co2
    days_mtd = (date_in_ts - curr_month_start).days + 1
    mtd_offset = daily_offset_tons * days_mtd
    mtd_deficit = mtd_co2_emitted - mtd_offset
    
    if mtd_deficit > 0:
        offset_per_tree_mtd = (25.0 / 365.0) * days_mtd / 1000.0
        trees_needed = mtd_deficit / offset_per_tree_mtd if offset_per_tree_mtd > 0 else 0
        area_needed_acres = trees_needed / 1000.0
        
        st.warning(f"⚠️ **Carbon Deficit Alert:** Your trees offset only **{(mtd_offset/mtd_co2_emitted*100) if mtd_co2_emitted>0 else 0:.3f}%** of MTD emissions.")
        
        m1, m2, m3 = st.columns(3)
        m1.metric("MTD CO₂ Emitted", f"{mtd_co2_emitted:,.0f} T")
        m2.metric("Additional Trees Needed", f"{trees_needed:,.0f}")
        m3.metric("Land Area Required", f"{area_needed_acres:,.0f} Acres")
    else:
        st.success("🌿 **Carbon Neutral!** Your greenbelt has successfully offset all MTD emissions.")
        st.metric("MTD Net CO₂", f"{mtd_deficit:,.0f} T")

# TAB 3: ASH OPS (VISUAL REDESIGN)
with tabs[2]:
    st.markdown("### 🪨 Ash Operations Center")
    display_info("Daily & MTD Ash Management: Generation vs Utilization, Lagoon Status, and Utilization Breakdown.")
    
    # Brighter Cards for MTD Metrics
    c1, c2, c3 = st.columns(3)
    with c1:
        st.markdown(f"""<div class="glass-card border-solar"><div class="unit-header" style="color:#fde047; font-size:16px;">MTD ASH GENERATED</div><div class="big-val" style="color:#fde047;">{mtd_ash_gen_total:,.0f} T</div></div>""", unsafe_allow_html=True)
    with c2:
        util_pct = (mtd_ash_util_total / mtd_ash_gen_total * 100) if mtd_ash_gen_total > 0 else 0
        st.markdown(f"""<div class="glass-card border-green"><div class="unit-header" style="color:#6ee7b7; font-size:16px;">MTD ASH UTILIZED</div><div class="big-val" style="color:#6ee7b7;">{mtd_ash_util_total:,.0f} T</div><div class="sub-lbl" style="color:#a7f3d0;">{util_pct:.1f}%</div></div>""", unsafe_allow_html=True)
    with c3:
        dump_color = "#f87171" if mtd_dump > 0 else "#38bdf8"
        st.markdown(f"""<div class="glass-card" style="border-top: 4px solid {dump_color}"><div class="unit-header" style="color:{dump_color}; font-size:16px;">MTD UN-UTILIZED DUMP</div><div class="big-val" style="color:{dump_color};">{max(0, mtd_dump):,.0f} T</div></div>""", unsafe_allow_html=True)
    
    st.divider()
    
    # Real-Time Flow & Lagoon Impact
    st.markdown("#### ⏱️ Real-Time Daily Flow & Dynamic Lagoon Impact")
    g1, g2, g3, g4 = st.columns(4)
    max_scale = max(5000, fleet_ash_gen * 1.2)
    with g1:
        fig_g1 = go.Figure(go.Indicator(mode="gauge+number", value=fleet_ash_gen, title={'text':"Daily Gen (T)", 'font':{'color':'#fde047'}}, gauge={'axis':{'range':[0, max_scale]}, 'bar':{'color':"#fbbf24"}}))
        fig_g1.update_layout(height=200, margin=dict(l=10,r=10,t=40,b=10), paper_bgcolor='rgba(0,0,0,0)', font_color='white')
        st.plotly_chart(fig_g1, use_container_width=True)
    with g2:
        fig_g2 = go.Figure(go.Indicator(mode="gauge+number", value=fleet_ash_util, title={'text':"Daily Util (T)", 'font':{'color':'#6ee7b7'}}, gauge={'axis':{'range':[0, max_scale]}, 'bar':{'color':"#10b981"}}))
        fig_g2.update_layout(height=200, margin=dict(l=10,r=10,t=40,b=10), paper_bgcolor='rgba(0,0,0,0)', font_color='white')
        st.plotly_chart(fig_g2, use_container_width=True)
    with g3:
        fig_l1 = go.Figure(go.Indicator(mode="gauge+number", value=lagoon_fill_pct, title={'text':"Lagoon 1 (95 Ac)", 'font':{'color':'#38bdf8'}}, gauge={'axis':{'range':[0,100]}, 'bar':{'color':"#f87171" if lagoon_fill_pct>80 else "#38bdf8"}}))
        fig_l1.update_layout(height=200, margin=dict(l=10,r=10,t=40,b=10), paper_bgcolor='rgba(0,0,0,0)', font_color='white')
        st.plotly_chart(fig_l1, use_container_width=True)
    with g4:
        fig_l2 = go.Figure(go.Indicator(mode="gauge+number", value=lagoon_fill_pct, title={'text':"Lagoon 2 (90 Ac)", 'font':{'color':'#38bdf8'}}, gauge={'axis':{'range':[0,100]}, 'bar':{'color':"#f87171" if lagoon_fill_pct>80 else "#38bdf8"}}))
        fig_l2.update_layout(height=200, margin=dict(l=10,r=10,t=40,b=10), paper_bgcolor='rgba(0,0,0,0)', font_color='white')
        st.plotly_chart(fig_l2, use_container_width=True)
        
    st.divider()
        
    c_vis1, c_vis2 = st.columns([1, 1])
    with c_vis1:
        st.markdown("#### 🏗️ Volume vs Burj Khalifa")
        burj_vol_equiv = 500000 
        pct_mtd = (mtd_ash_gen_total / burj_vol_equiv) * 100
        pct_ytd = (ytd_ash_gen_total / burj_vol_equiv) * 100
        
        fig_burj = go.Figure()
        fig_burj.add_trace(go.Bar(x=['Burj Khalifa', 'MTD Ash', 'YTD Ash'], y=[100, pct_mtd, pct_ytd], marker_color=['#94a3b8', '#fbbf24', '#f87171']))
        fig_burj.update_layout(title="Ash Volume Equivalency (%)", height=300, paper_bgcolor='rgba(0,0,0,0)', font_color='white', showlegend=False)
        st.plotly_chart(fig_burj, use_container_width=True)

    with c_vis2:
        if units_data:
            st.markdown("#### 📉 Today's Disposal Breakdown")
            ash_breakdown = pd.DataFrame({'Type': ['Cement', 'Bricks'], 'Tons': [sum(u['ash']['cem_util'] for u in units_data), sum(u['ash']['brick_util'] for u in units_data)]})
            fig_pie = px.pie(ash_breakdown, values='Tons', names='Type', hole=0.4, template='plotly_dark', color_discrete_sequence=['#fbbf24', '#38bdf8'])
            fig_pie.update_layout(height=300, margin=dict(t=30, b=10, l=10, r=10), paper_bgcolor='rgba(0,0,0,0)', font_color='white')
            st.plotly_chart(fig_pie, use_container_width=True)

# TAB 4: RENEWABLES
with tabs[3]:
    display_info(r"""
    **Green Power Impact:**
    * **Biomass:** Co-firing agricultural waste with coal. Reduces net CO2.
    * **Solar:** Captive solar power reducing auxiliary consumption.
    
    **Equivalency:**
    * $$Homes\_Powered = \frac{Renewable\_Units}{4 \text{ (Avg Daily Consumption)}}$$
    """)
    st.markdown("#### ⚡ Green Power Impact")
    c1, c2 = st.columns(2)
    with c1:
        st.markdown(f"""<div class="glass-card border-green"><div class="unit-header">BIOMASS</div><div class="big-val" style="color:#10b981">{bio_co2:.2f} T</div><div class="sub-lbl">CO2 Saved Today</div><hr style="border-color:#ffffff33;"><div class="big-val" style="font-size:24px; color:#fff">{bio_homes:,.0f}</div><div class="sub-lbl">Homes Powered</div></div>""", unsafe_allow_html=True)
    with c2:
        st.markdown(f"""<div class="glass-card border-solar"><div class="unit-header">SOLAR</div><div class="big-val" style="color:#fde047">{sol_co2:.2f} T</div><div class="sub-lbl">CO2 Saved Today</div><hr style="border-color:#ffffff33;"><div class="big-val" style="font-size:24px; color:#fff">{solar_homes:,.0f}</div><div class="sub-lbl">Homes Powered</div></div>""", unsafe_allow_html=True)
    if anim_sun: st_lottie(anim_sun, height=150, key="sun_anim")

# TABS 5-7: UNITS
if units_data:
    for i, tab in enumerate([tabs[4], tabs[5], tabs[6]]):
        with tab:
            display_info(r"""
            **Unit Performance:**
            * **Loss Analysis:** Breakdown of Heat Rate deviation sources (Vacuum, Temp, Spray).
            * **5S Score:** Technical hygiene score based on parameter adherence.
            
            **Loss Formulas (Approx):**
            * Vacuum: 15 kcal/kWh per 0.01 deviation.
            * MS Temp: 0.7 kcal/kWh per degree deviation.
            """)
            u = units_data[i]
            render_unit_detail(u, configs)

# TAB 8: TRENDS
with tabs[7]:
    display_info("Historical Performance Analysis. Filters out shutdown days (HR < 100) to keep graph clean.")
    filter_opt = st.radio("Duration", ["7 Days", "30 Days"], horizontal=True)
    if not hist_df.empty:
        days_back = 7 if filter_opt=="7 Days" else 30
        cutoff = date_in - timedelta(days=days_back)
        cutoff_ts = pd.Timestamp(cutoff)
        filtered_df = hist_df[(hist_df['Date'] >= cutoff_ts) & (hist_df['Date'] <= date_in_ts)]
        filtered_df = filtered_df[filtered_df['HR'] > 100]
        filtered_df['Date_dt'] = filtered_df['Date'].dt.date
        filtered_df['Unit'] = filtered_df['Unit'].astype(str)
        fig = make_subplots(specs=[[{"secondary_y": True}]])
        colors = {'1': '#38bdf8', '2': '#fbbf24', '3': '#10b981'}
        for u_id in filtered_df['Unit'].unique():
            u_df = filtered_df[filtered_df['Unit'] == u_id]
            fig.add_trace(go.Scatter(x=u_df['Date_dt'], y=u_df['HR'], name=f"Unit {u_id} HR", mode='lines+markers', line=dict(color=colors.get(u_id, 'white'))), secondary_y=False)
        fleet_trend = filtered_df.groupby('Date_dt')['Profit'].sum().reset_index()
        fig.add_trace(go.Bar(x=fleet_trend['Date_dt'], y=fleet_trend['Profit'], name="Fleet Profit", opacity=0.3, marker_color='white'), secondary_y=True)
        fig.update_layout(title="Heat Rate vs Profit", template="plotly_dark", paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', hovermode="x unified", legend=dict(orientation="h", y=1.1))
        fig.update_yaxes(title_text="Heat Rate", secondary_y=False, showgrid=False)
        fig.update_yaxes(title_text="Profit", secondary_y=True, showgrid=False)
        st.plotly_chart(fig, use_container_width=True)
    else: st.info("No history data available.")

# TAB 9: SIMULATOR
with tabs[8]:
    st.markdown("### 🎮 Simulator")
    display_info(r"""
    **Simulation Logic:**
    Adjust parameters to see the instant impact on **Net Heat Rate** and **Daily Profit**.
    * **Vacuum:** Lower (more negative) is better.
    * **APC:** Auxiliary Power Consumption directly reduces salable power.
    * **GCV:** Gross Calorific Value of coal affects fuel quantity needed.
    """)
    s_c1, s_c2, s_c3 = st.columns(3)
    with s_c1:
        s_vac = st.slider("Vacuum (kg/cm2)", -0.60, -0.99, -0.92, step=0.001, help="Standard: -0.92")
        s_ms = st.slider("MS Temp (°C)", 510, 545, 540)
    with s_c2:
        s_fg = st.slider("FG Temp (°C)", 110, 160, 130)
        s_apc = st.slider("APC (%)", 5.0, 10.0, 6.5, step=0.1)
    with s_c3:
        s_gcv = st.slider("Coal GCV (kcal/kg)", 2800, 4500, 3600)
        s_bio = st.slider("Biomass (%)", 0, 20, 0)
    sim_vac_loss = (abs(s_vac) - 0.92) * 100 * -15 
    sim_ms_loss = (540 - s_ms) * 0.7
    sim_fg_loss = (s_fg - 130) / 2
    sim_hr_impact = sim_vac_loss + sim_ms_loss + sim_fg_loss
    base_revenue = 25200000 
    sim_apc_loss = base_revenue * ((s_apc - 6.5)/100) * -1
    sim_hr_profit = (-1 * sim_hr_impact) * 8.4 * 1000
    total_sim_impact = sim_hr_profit + sim_apc_loss
    st.divider()
    r1, r2, r3 = st.columns(3)
    with r1: st.metric("Net Heat Rate Impact", f"{sim_hr_impact:.1f} kcal/kWh", delta_color="inverse")
    with r2: st.metric("Daily Profit Impact", format_lacs(total_sim_impact))
    with r3: st.metric("APC Cost Impact", format_lacs(sim_apc_loss))

# TAB 10: ANALYTICS
with tabs[9]:
    st.markdown("### 📊 Interactive Analytics Playground")
    gb_raw = analytics_state.get('greenbelt_raw', [])
    ash_raw = analytics_state.get('ash_raw', [])
    
    if gb_raw:
        df_gb = pd.DataFrame(gb_raw)
        st.markdown('<div class="section-header">🌳 Greenbelt Simulator</div>', unsafe_allow_html=True)
        c_gb1, c_gb2 = st.columns(2)
        with c_gb1:
            all_years = sorted(df_gb['Year'].unique(), reverse=True)
            sel_year = st.selectbox("📅 Select Financial Year", all_years)
        with c_gb2:
            all_species = sorted(df_gb['Species'].unique())
            sel_species = st.multiselect("🌿 Keep/Remove Species (Filter)", all_species, default=all_species[:5])
        
        df_yr = df_gb[df_gb['Year'] == sel_year]
        if sel_species: df_yr = df_yr[df_yr['Species'].isin(sel_species)]
            
        total_planted = df_yr['Planted'].sum()
        total_matured = df_yr['Matured'].sum()
        avg_survival = (total_matured / total_planted * 100) if total_planted > 0 else 0
        mortality = 100 - avg_survival
        carb_sink = total_matured * 25 
        carb_sink_ton = carb_sink / 1000
        
        k1, k2, k3, k4 = st.columns(4)
        k1.metric("Survival Rate", f"{avg_survival:.1f}%")
        k2.metric("Mortality Rate", f"{mortality:.1f}%", delta_color="inverse")
        k3.metric("Matured Alive", f"{total_matured:,}")
        k4.metric("CO2 Sink Potential", f"{carb_sink_ton:,.1f} Tons/Yr")
        
        st.divider()
        p1, p2 = st.columns(2)
        with p1:
            fig_mix = px.pie(df_yr, values='Planted', names='Species', title=f"Planted Mix ({sel_year})", hole=0.4, template='plotly_dark')
            fig_mix.update_layout(paper_bgcolor='rgba(0,0,0,0)', font_color='white')
            st.plotly_chart(fig_mix, use_container_width=True)
        with p2:
            df_yr['Dead'] = df_yr['Planted'] - df_yr['Matured']
            fig_surv = px.bar(df_yr, x='Species', y=['Matured', 'Dead'], title="Survival vs Mortality by Species", barmode='stack', color_discrete_sequence=['#10b981', '#ef4444'], template='plotly_dark')
            fig_surv.update_layout(paper_bgcolor='rgba(0,0,0,0)', font_color='white')
            st.plotly_chart(fig_surv, use_container_width=True)

        st.markdown("#### 🌡️ Plantation Heatmap")
        hm_view = st.radio("Heatmap View", ["Species vs Year", "Year vs Species"], horizontal=True)
        if hm_view == "Species vs Year":
            fig_heat = px.density_heatmap(df_gb, x='Year', y='Species', z='Planted', color_continuous_scale='Greens')
        else:
            fig_heat = px.density_heatmap(df_gb, x='Species', y='Year', z='Planted', color_continuous_scale='Greens')
        fig_heat.update_layout(paper_bgcolor='rgba(0,0,0,0)', font_color='white')
        st.plotly_chart(fig_heat, use_container_width=True)
    else: st.info("Greenbelt data missing in 'analytics_state_v1.json'.")

    st.divider()
    if ash_raw:
        df_ash = pd.DataFrame(ash_raw)
        st.markdown('<div class="section-header">🪨 Ash Utilization Analytics</div>', unsafe_allow_html=True)
        ac1, ac2 = st.columns(2)
        with ac1: sel_month = st.selectbox("📅 Select Month", df_ash['Month'].unique())
        with ac2: sim_boost = st.slider("🚀 Simulate Efficiency Boost (%)", 0, 50, 0)
            
        latest_ash = df_ash[df_ash['Month'] == sel_month].iloc[0]
        ignore = ['Month', 'Generation', 'Utilization']
        valid_cols = [c for c in df_ash.columns if c not in ignore and isinstance(latest_ash[c], (int, float)) and latest_ash[c] > 0]
        
        c1, c2 = st.columns(2)
        with c1:
            pie_vals = {k: latest_ash[k] for k in valid_cols}
            fig_ash_pie = px.pie(values=list(pie_vals.values()), names=list(pie_vals.keys()), title=f"Utilization Split ({sel_month})", hole=0.4, template='plotly_dark')
            fig_ash_pie.update_layout(paper_bgcolor='rgba(0,0,0,0)', font_color='white')
            st.plotly_chart(fig_ash_pie, use_container_width=True)
        with c2:
            fig_area = px.area(df_ash, x='Month', y=valid_cols, title="Utilization Trend (All Months)", template='plotly_dark')
            util_col = 'Utilization' if 'Utilization' in df_ash.columns else df_ash.columns[2]
            sim_line = df_ash[util_col] * (1 + sim_boost/100)
            fig_area.add_scatter(x=df_ash['Month'], y=sim_line, mode='lines', name='Simulated Target', line=dict(color='white', dash='dash'))
            fig_area.update_layout(paper_bgcolor='rgba(0,0,0,0)', font_color='white')
            st.plotly_chart(fig_area, use_container_width=True)
    else: st.info("Upload 'ash.xlsx' to activate Ash Analytics.")

# TAB 11: INFO
with tabs[10]:
    st.markdown("### 📚 Knowledge Base & Formulas")
    
    st.markdown("#### 1. Financial Mechanics (Profit)")
    st.latex(r"Profit = (Target_{HR} - Actual_{HR}) \times Generation \times 1000")
    st.write("> **Why 1000?** It represents the conversion factor translating thermal efficiency savings directly into Rupees based on GCV and Coal Costs.")
    
    st.markdown("#### 2. Technical Hygiene (5S Score)")
    st.latex(r"Penalty = \frac{|Vac_{dev}| + MS_{dev} + FG_{dev} + Spray_{dev}}{3}")
    st.latex(r"Score = 100 - Penalty")
    
    st.markdown("#### 3. Ash Pond Lifecycle")
    st.latex(r"Remaining\_Days = \frac{Total\_Capacity_{18 months}}{Daily\_Gen - Daily\_Util}")
    st.write("> **Rule:** If generation exceeds utilization, the pond begins to fill. Defaults to 9999 days (Stable) if $Util \ge Gen$.")
    
    st.markdown("#### 4. Carbon Footprint & Sustainability")
    st.latex(r"Daily\_CO_2\_Emitted = \frac{Generation \times Heat Rate \times 1000}{GCV} \times 1.7")
    st.latex(r"Daily\_Tree\_Offset = \frac{Total\_Matured\_Trees \times 25 \text{ kg}}{365 \times 1000}")
    
    st.markdown("#### 5. Renewables Equivalency")
    st.write("- **Solar Homes:** 1 MU Solar = 1 Million Units. Avg Home consumes ~4 units/day.")
    st.write("- **Biomass:** 1 kg Biomass ≈ 1.2 kWh Electricity equivalent (avoided coal).")
