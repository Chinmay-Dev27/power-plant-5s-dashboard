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

# --- 2. VISUAL OVERHAUL ---
st.markdown("""
    <style>
    .stApp { background-color: #f0f2f6; background: linear-gradient(135deg, #0f172a 0%, #1e293b 100%); color: #ffffff; font-family: 'Roboto', sans-serif; }
    .stTabs [data-baseweb="tab-list"] { gap: 8px; background-color: rgba(255,255,255,0.05); padding: 10px; border-radius: 50px; }
    .stTabs [data-baseweb="tab"] { height: 40px; white-space: pre-wrap; background-color: transparent; border-radius: 20px; color: #94a3b8; font-weight: 500; }
    .stTabs [aria-selected="true"] { background-color: #F59E0B; color: white; }
    .glass-card { background: rgba(30, 41, 59, 0.7); border: 1px solid rgba(255, 255, 255, 0.1); border-radius: 12px; padding: 20px; margin-bottom: 15px; box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1); text-align: center; transition: transform 0.2s ease; }
    .glass-card:hover { transform: translateY(-2px); border-color: rgba(255, 255, 255, 0.3); }
    .border-good { border-top: 3px solid #10B981; }
    .border-bad { border-top: 3px solid #EF4444; }
    .border-shut { border-top: 3px solid #64748b; }
    .border-green { border-top: 3px solid #00ff88; }
    .border-solar { border-top: 3px solid #FFD700; }
    .big-val { font-family: 'Orbitron', sans-serif; font-size: 26px; font-weight: 700; color: white; }
    .sub-lbl { font-size: 11px; color: #94a3b8; text-transform: uppercase; letter-spacing: 0.5px; }
    .section-header { font-family: 'Oswald', sans-serif; font-size: 22px; color: #F59E0B; margin: 20px 0 10px 0; border-bottom: 1px solid #444; }
    </style>
""", unsafe_allow_html=True)

# --- 3. GLOBAL HELPERS (DEFINED FIRST TO AVOID NAME ERROR) ---
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

def load_history(repo):
    if not repo: return pd.DataFrame(), None
    try:
        file = repo.get_contents("plant_history_v28.csv", ref=st.secrets["BRANCH"])
        df = pd.read_csv(StringIO(file.decoded_content.decode()))
        cols = ['Gen', 'HR', 'Target HR', 'Profit', 'Vacuum', 'MS Temp', 'FG Temp', 'Spray', 'SOx', 'NOx', 'Ash Util', 'Ash Cement', 'Ash Bricks', 'Biomass', 'Solar']
        for c in cols:
            if c in df.columns: df[c] = pd.to_numeric(df[c], errors='coerce').fillna(0)
        df['Date'] = pd.to_datetime(df['Date'])
        
        # MTD FIX: Remove duplicates immediately
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

def get_default_config():
    return {
        "u1_target_hr": 2315, "u2_target_hr": 2315, "u3_target_hr": 2315,
        "u1_gcv": 3600, "u2_gcv": 3550, "u3_gcv": 3620,
        "coal_ash_pct": 35.0, 
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

def load_analytics_state(repo):
    default_data = {"greenbelt_raw": [], "ash_raw": []}
    if not repo: return default_data, None
    try:
        file = repo.get_contents("analytics_state_v1.json", ref=st.secrets["BRANCH"])
        data = json.loads(file.decoded_content.decode())
        # Smart Adapter for Dictionary Format
        if "greenbelt_raw" not in data and len(data) > 2:
            converted = []
            for sp, det in data.items():
                if isinstance(det, dict) and "year_wise_plantation" in det:
                    for yr, cnt in det["year_wise_plantation"].items():
                        if cnt > 0:
                            m = int(cnt * (1 - det.get("mortality_rate", 0.1)))
                            converted.append({"Year": yr, "Species": sp, "Planted": cnt, "Matured": m})
            if converted: data = {"greenbelt_raw": converted, "ash_raw": data.get("ash_raw", [])}
        return data, file.sha
    except: return default_data, None

def save_analytics_state(repo, data, sha):
    if not repo: return False
    try:
        if sha: repo.update_file("analytics_state_v1.json", "Update Analytics", json.dumps(data), sha, branch=st.secrets["BRANCH"])
        else: repo.create_file("analytics_state_v1.json", "Init Analytics", json.dumps(data), branch=st.secrets["BRANCH"])
        return True
    except: return False

# Placeholders for Excel parsing (superseded by JSON)
def parse_plantation_file(f): return []
def parse_ash_file(f): return []

def generate_excel_template():
    return pd.DataFrame({'Parameter': ['Gen (MU)', 'HR (kcal/kWh)', 'Vac (kg/cm2)', 'MS (C)', 'FG (C)', 'Spray (TPH)', 'SOx', 'NOx'], 'Unit 1': [0]*8, 'Unit 2': [0]*8, 'Unit 3': [0]*8})

def format_lacs(value):
    val_lac = value / 100000
    return f"₹ {val_lac:,.2f} Lac"

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
    return pdf.output(dest='S').encode('latin-1')

def calculate_unit(u_id, gen, hr, inputs, design_vals, ash_params):
    TARGET_HR = design_vals['target_hr']; COAL_GCV = design_vals['gcv']
    if gen <= 0 or hr <= 0:
        profit = -1 * (350 * 1000 * 24 * 3) 
        score = 0; l_vac = l_ms = l_fg = l_spray = l_unacc = 0; carbon_tons = escerts = 0; status = "SHUTDOWN"
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
        l_unacc = max(0, hr - (2250 + l_ms + l_fg + l_spray + 50) - abs(l_vac))
        score = max(0, 100 - (abs(l_vac) + l_ms + l_fg + l_spray + l_unacc)/3)
    
    coal_consumed = (gen * hr * 1000) / COAL_GCV if COAL_GCV > 0 and gen > 0 else 0
    ash_gen = coal_consumed * (ash_params['ash_pct'] / 100)
    ash_util = ash_params['util_cem'] + ash_params['util_brick']
    
    return {
        "id": u_id, "gen": gen, "hr": hr, "profit": profit, "carbon": carbon_tons, "score": score,
        "sox": inputs['sox'], "nox": inputs['nox'], "ash": {"generated": ash_gen, "utilized": ash_util, "cem_util": ash_params['util_cem'], "brick_util": ash_params['util_brick']},
        "losses": {"Vacuum": abs(l_vac), "MS Temp": l_ms, "Flue Gas": l_fg, "Spray": l_spray, "Unaccounted": l_unacc},
        "target_hr": TARGET_HR, "status": status, "homes_bio": ash_params.get('biomass', 0)*1000*1.2/4, "trees": abs(carbon_tons/0.025)
    }

def render_unit_detail(u, configs):
    st.markdown(f"### 🔍 Unit {u['id']} Deep Dive")
    if u['status'] == "SHUTDOWN":
        st.error("🚨 UNIT SHUTDOWN")
        return
    c1, c2 = st.columns(2)
    with c1:
        fig = go.Figure(go.Indicator(mode = "gauge+number+delta", value = u['hr'], delta = {'reference': u['target_hr'], 'increasing': {'color': "#FF3333"}}, gauge = {'axis': {'range': [2000, 2600]}, 'bar': {'color': "#00ccff"}, 'threshold': {'line': {'color': "red", 'width': 4}, 'thickness': 0.75, 'value': u['hr']}}))
        fig.update_layout(height=250, margin=dict(l=20,r=20,t=0,b=0), paper_bgcolor='rgba(0,0,0,0)', font_color='white')
        st.plotly_chart(fig, use_container_width=True)
    with c2:
        loss_df = pd.DataFrame(list(u['losses'].items()), columns=['Param', 'Loss']).sort_values('Loss')
        fig_bar = px.bar(loss_df, x='Loss', y='Param', orientation='h', text='Loss', color='Loss', color_continuous_scale=['#444', '#FF3333'], template='plotly_dark')
        fig_bar.update_layout(paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', height=250)
        st.plotly_chart(fig_bar, use_container_width=True)

# --- 7. MAIN APP FLOW ---
with st.sidebar:
    try: st.image("1000051706.png", width="stretch")
    except: st.markdown("## **GMR POWER**") 
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
        for _, row in day_df.iterrows(): hist_data[str(row['Unit'])] = row

    with st.expander("📤 Upload Operational Data"):
        uploaded_file = st.file_uploader("Daily Input", type=['xlsx', 'csv'])
        if uploaded_file:
            try:
                df_up = pd.read_csv(uploaded_file) if uploaded_file.name.endswith('.csv') else pd.read_excel(uploaded_file)
                if 'Parameter' in df_up.columns:
                    df_up.set_index('Parameter', inplace=True)
                    st.session_state['daily_data'] = df_up.to_dict()
                    st.toast("Applied!", icon="✅")
            except: st.error("Error")
            
    with st.expander("📂 Supplementary Reports"):
        st.info("Upload 'Ash.xlsx' or 'Plantation.xlsx' (Uses JSON mainly)")
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

    # INPUTS
    tab_conf, tab_inp = st.tabs(["⚙️ Config", "📝 Inputs"])
    with tab_conf:
        lim_sox = st.number_input("SOx Limit", value=plant_conf['limits']['sox'])
        lim_nox = st.number_input("NOx Limit", value=plant_conf['limits']['nox'])
        coal_ash = st.number_input("Ash %", value=plant_conf['coal_ash_pct'])
        if st.button("💾 Save Config"):
            new_conf = {**plant_conf, "coal_ash_pct": coal_ash, "limits": {"nox": lim_nox, "sox": lim_sox, "spm": 50}}
            save_plant_config(repo, new_conf, conf_sha)
            st.rerun()
            
    with tab_inp:
        configs = [{'target_hr': plant_conf['u1_target_hr'], 'gcv': plant_conf['u1_gcv'], 'limits':plant_conf['limits']}, 
                   {'target_hr': plant_conf['u2_target_hr'], 'gcv': plant_conf['u2_gcv'], 'limits':plant_conf['limits']}, 
                   {'target_hr': plant_conf['u3_target_hr'], 'gcv': plant_conf['u3_gcv'], 'limits':plant_conf['limits']}]
        
        def val(u_id, row_key, col_key, def_v):
            if u_id in hist_data and col_key in hist_data[u_id]: return float(hist_data[u_id][col_key])
            return def_v

        for i in range(1, 4):
            u = str(i)
            with st.expander(f"Unit {i}"):
                gen = st.number_input(f"U{u} Gen", value=val(u, 'Generation', 'Gen', 8.4), key=f"g{u}")
                hr = st.number_input(f"U{u} HR", value=val(u, 'Heat Rate', 'HR', 2380.0), key=f"h{u}")
                vac = st.number_input(f"U{u} Vac", value=val(u, 'Vacuum', 'Vacuum', -0.90), step=0.001, format="%.3f", key=f"v{u}")
                ms = st.number_input(f"U{u} MS", value=val(u, 'MS Temp', 'MS Temp', 535.0), key=f"m{u}")
                fg = st.number_input(f"U{u} FG", value=val(u, 'FG Temp', 'FG Temp', 135.0), key=f"f{u}")
                spray = st.number_input(f"U{u} Spray", value=val(u, 'Spray', 'Spray', 20.0), key=f"s{u}")
                sox = st.number_input(f"U{u} SOx", value=val(u, 'SOx', 'SOx', 550.0), key=f"sx{u}")
                nox = st.number_input(f"U{u} NOx", value=val(u, 'NOx', 'NOx', 400.0), key=f"nx{u}")
                ash_cem = st.number_input(f"U{u} Cement", value=val(u, 'Ash Cement', 'Ash Cement', 1000.0), key=f"ac{u}")
                ash_brk = st.number_input(f"U{u} Bricks", value=val(u, 'Ash Bricks', 'Ash Bricks', 500.0), key=f"ab{u}")
                ash_p = {'ash_pct': coal_ash, 'util_cem': ash_cem, 'util_brick': ash_brk, 'biomass': val(u, 'Biomass', 'Biomass', 0.0)}
                units_data.append(calculate_unit(u, gen, hr, {'vac':vac, 'ms':ms, 'fg':fg, 'spray':spray, 'sox':sox, 'nox':nox}, configs[i-1], ash_p))
        
        bio_u1 = st.number_input("Bio U1", 0.0); sol_u1 = st.number_input("Solar", 0.0)

    if st.button("💾 Save History"):
        if repo:
            new_rows = []
            for u in units_data:
                new_rows.append({
                    "Date": date_in.strftime('%Y-%m-%d'), "Unit": u['id'], "Profit": u['profit'], "HR": u['hr'], "Gen": u['gen'], 
                    "Ash Util": u['ash']['utilized'], "Coal Ash %": coal_ash, "Ash Cement": u['ash']['cem_util'], "Ash Bricks": u['ash']['brick_util'],
                    "Vacuum": u['losses']['Vacuum'], "MS Temp": u['losses']['MS Temp'], "FG Temp": u['losses']['Flue Gas'], "Spray": u['losses']['Spray'],
                    "SOx": u['sox'], "NOx": u['nox'], "Biomass": bio_u1 if u['id']=='1' else 0, "Solar": sol_u1 if u['id']=='1' else 0
                })
            df_comb = pd.concat([hist_df, pd.DataFrame(new_rows)], ignore_index=True)
            save_history(repo, df_comb, sha)
            st.success("Saved!")

# --- AGGREGATES ---
fleet_profit = sum(u['profit'] for u in units_data)
fleet_ash_gen = sum(u['ash']['generated'] for u in units_data)
fleet_ash_util = sum(u['ash']['utilized'] for u in units_data)

# MTD CORRECTION LOGIC (STRICT)
curr_month_start = pd.Timestamp(date_in.replace(day=1))
sel_date = pd.Timestamp(date_in)
# 1. Get History STRICTLY before today (Yesterday and back) to avoid double counting
past_mtd_df = hist_df[(hist_df['Date'] >= curr_month_start) & (hist_df['Date'] < sel_date)]
past_profit = past_mtd_df['Profit'].sum() if not past_mtd_df.empty else 0
past_ash = past_mtd_df['Ash Util'].sum() if not past_mtd_df.empty else 0
# 2. Add Current Live Inputs
mtd_profit = past_profit + fleet_profit
mtd_ash = past_ash + fleet_ash_util

# ASH POND LOGIC
avg_gen_18m = fleet_ash_gen if fleet_ash_gen > 0 else 5000
total_cap = avg_gen_18m * 540 # 18 months
net_daily = avg_gen_18m - fleet_ash_util
pond_days = total_cap / net_daily if net_daily > 0 else 9999

# --- TABS ---
tabs = st.tabs(["🏠 War Room", "🌿 Sustainability", "🪨 Ash Ops", "☀️ Green", "⚙️ Unit 1", "⚙️ Unit 2", "⚙️ Unit 3", "📈 Trends", "🎮 Sim", "📊 Analytics", "ℹ️ Info"])

with tabs[0]: # War Room
    display_info(r"""
    **Executive Summary:**
    * **Unit P&L:** Green = Profit, Red = Loss. Derived from Heat Rate diff.
    * **Ash Pond:** Days remaining until both Lagoons are full (based on 18-month un-utilized capacity).
    * **MTD:** `(Sum of History from 1st to Yesterday) + (Live Today)`.
    """)
    cols = st.columns(4)
    for i, u in enumerate(units_data):
        clr = "#00B981" if u['profit'] > 0 else "#EF4444"
        with cols[i]:
            st.markdown(f"""<div class="glass-card" style="border-top: 3px solid {clr}"><div class="unit-header">UNIT {u['id']}</div><div class="big-val" style="color:{clr}">{format_lacs(u['profit'])}</div><div class="sub-lbl">Daily Net Impact</div></div>""", unsafe_allow_html=True)
    with cols[3]:
        st.markdown(f"""<div class="glass-card" style="border-top: 3px solid {'#00B981' if pond_days>100 else 'red'}"><div class="unit-header">ASH POND</div><div class="big-val">{pond_days:.0f}</div><div class="sub-lbl">Days Left</div></div>""", unsafe_allow_html=True)
    st.metric("MTD Profit", format_lacs(mtd_profit))

with tabs[1]: # Sustainability
    display_info(r"""
    **Logic:**
    * **SOx/NOx:** Real-time stack monitoring data vs CPCB Limits.
    * **Greenbelt:** Converts CO2 offset from trees into "Physical Trees".
    """)
    st.markdown("#### Emissions vs Limits")
    avg_sox = sum(u['sox'] for u in units_data)/3
    st.metric("Avg SOx", f"{avg_sox:.0f}", delta=f"{plant_conf['limits']['sox']-avg_sox:.0f} margin")
    if avg_sox > plant_conf['limits']['sox']: st.error("⚠️ SOx Limit Exceeded")

with tabs[2]: # Ash Ops (Visual)
    display_info(r"""
    **Ash Management:**
    * **Generation:** Calculated based on Coal Consumption & Ash %.
    * **Utilization:** Broken down into Cement (High Value) and Bricks/Landfill (Low Value).
    """)
    st.markdown("### 🪨 Ash Operations")
    c1, c2 = st.columns(2)
    with c1:
        # Burj Visual
        fig = go.Figure(go.Bar(x=['Vol'], y=[100], name='Burj Khalifa', marker_color='#333'))
        fig.add_trace(go.Bar(x=['Vol'], y=[(fleet_ash_gen/500000)*100], name='Daily Ash', marker_color='#F59E0B'))
        fig.update_layout(barmode='overlay', title="Volume vs Burj Khalifa", height=300, paper_bgcolor='rgba(0,0,0,0)')
        st.plotly_chart(fig, use_container_width=True)
    with c2:
        # Lagoon Gauges
        fill = max(0, min(100, 100 - (pond_days/540*100))) if pond_days < 9999 else 0
        fig_g = go.Figure(go.Indicator(mode="gauge+number", value=fill, title={'text':"Lagoon Fill %"}, gauge={'axis':{'range':[0,100]}, 'bar':{'color':"red" if fill>80 else "green"}}))
        fig_g.update_layout(height=300, paper_bgcolor='rgba(0,0,0,0)')
        st.plotly_chart(fig_g, use_container_width=True)

with tabs[3]: # Green
    display_info(r"""
    **Green Power Impact:**
    * **Biomass:** Co-firing agricultural waste with coal. Reduces net CO2.
    * **Solar:** Captive solar power reducing auxiliary consumption.
    """)
    st.metric("Biomass CO2 Saved", f"{(bio_u1)*1.7:.2f} T")

for i in range(3): # Units
    with tabs[4+i]: 
        display_info(r"""
        **Unit Performance:**
        * **Loss Analysis:** Breakdown of Heat Rate deviation sources (Vacuum, Temp, Spray).
        * **5S Score:** Technical hygiene score based on parameter adherence.
        """)
        render_unit_detail(units_data[i], configs)

with tabs[7]: # Trends
    display_info("Historical Performance Analysis. Filters out shutdown days (HR < 100) to keep graph clean.")
    if not hist_df.empty:
        df_t = hist_df.groupby('Date')['Profit'].sum().reset_index()
        st.plotly_chart(px.bar(df_t, x='Date', y='Profit', title="Fleet Profit Trend", template="plotly_dark"), use_container_width=True)

with tabs[8]: # Sim
    display_info(r"""
    **Simulation Logic:**
    Adjust parameters to see the instant impact on **Net Heat Rate** and **Daily Profit**.
    * **Vacuum:** Lower (more negative) is better.
    """)
    s_vac = st.slider("Simulate Vacuum", -0.8, -0.99, -0.92)
    st.metric("Impact", f"{(abs(s_vac)-0.92)*100*-15:.1f} kcal/kWh")

with tabs[9]: # Analytics
    gb_raw = analytics_state.get('greenbelt_raw', [])
    ash_raw = analytics_state.get('ash_raw', [])
    
    # --- GREENBELT SECTION ---
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
        if sel_species:
            df_yr = df_yr[df_yr['Species'].isin(sel_species)]
            
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
            st.plotly_chart(fig_mix, use_container_width=True)
        with p2:
            df_yr['Dead'] = df_yr['Planted'] - df_yr['Matured']
            fig_surv = px.bar(df_yr, x='Species', y=['Matured', 'Dead'], title="Survival vs Mortality by Species", barmode='stack', color_discrete_sequence=['#00ff88', '#ff3333'], template='plotly_dark')
            st.plotly_chart(fig_surv, use_container_width=True)

        st.markdown("#### 🌡️ Plantation Heatmap")
        hm_view = st.radio("Heatmap View", ["Species vs Year", "Year vs Species"], horizontal=True)
        if hm_view == "Species vs Year":
            fig_heat = px.density_heatmap(df_gb, x='Year', y='Species', z='Planted', color_continuous_scale='Greens')
        else:
            fig_heat = px.density_heatmap(df_gb, x='Species', y='Year', z='Planted', color_continuous_scale='Greens')
        st.plotly_chart(fig_heat, use_container_width=True)

    else:
        st.info("Greenbelt data missing in 'analytics_state_v1.json'.")

    # --- ASH SECTION ---
    st.divider()
    if ash_raw:
        df_ash = pd.DataFrame(ash_raw)
        st.markdown('<div class="section-header">🪨 Ash Utilization Analytics</div>', unsafe_allow_html=True)
        
        ac1, ac2 = st.columns(2)
        with ac1:
            sel_month = st.selectbox("📅 Select Month", df_ash['Month'].unique())
        with ac2:
            sim_boost = st.slider("🚀 Simulate Efficiency Boost (%)", 0, 50, 0)
            
        latest_ash = df_ash[df_ash['Month'] == sel_month].iloc[0]
        ignore = ['Month', 'Generation', 'Utilization']
        valid_cols = [c for c in df_ash.columns if c not in ignore and isinstance(latest_ash[c], (int, float)) and latest_ash[c] > 0]
        
        c1, c2 = st.columns(2)
        with c1:
            pie_vals = {k: latest_ash[k] for k in valid_cols}
            fig_ash_pie = px.pie(values=list(pie_vals.values()), names=list(pie_vals.keys()), title=f"Utilization Split ({sel_month})", hole=0.4, template='plotly_dark')
            st.plotly_chart(fig_ash_pie, use_container_width=True)
        with c2:
            fig_area = px.area(df_ash, x='Month', y=valid_cols, title="Utilization Trend (All Months)", template='plotly_dark')
            util_col = 'Utilization' if 'Utilization' in df_ash.columns else df_ash.columns[2]
            sim_line = df_ash[util_col] * (1 + sim_boost/100)
            fig_area.add_scatter(x=df_ash['Month'], y=sim_line, mode='lines', name='Simulated Target', line=dict(color='white', dash='dash'))
            st.plotly_chart(fig_area, use_container_width=True)
    else:
        st.info("Upload 'ash.xlsx' to activate Ash Analytics.")

with tabs[10]: # Info (Restored)
    st.markdown("### 📚 Formula Reference")
    st.latex(r"Profit = (Target_{HR} - Actual_{HR}) \times Gen \times 1000")
    st.latex(r"Ash_{Gen} = Coal_{Cons} \times Ash\%")
    st.markdown("**5S Score:** `100 - (Deviation_Penalty / 3)`")
    st.markdown("**MTD:** Sum of History (1st to Yesterday) + Live Today.")
    st.write("- **Solar Homes:** 1 MU = 1 Million Units. Avg Home = 1460 Units/Year (~4/day).")
    st.write("- **Biomass:** 1 kg Biomass ≈ 1.2 kWh Electricity equivalent (avoided coal).")
