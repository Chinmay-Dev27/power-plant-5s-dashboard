import streamlit as st
import plotly.graph_objects as go
import plotly.express as px
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import requests
from io import StringIO, BytesIO
from github import Github, Auth
from streamlit_lottie import st_lottie
import streamlit.components.v1 as components
from fpdf import FPDF
import base64

# --- 1. CONFIGURATION & CSS ---
st.set_page_config(page_title="GMR 5S Dashboard", layout="wide", page_icon="⚡")

# Import Google Fonts
components.html(
    """
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;600;700;800&display=swap" rel="stylesheet">
    """,
    height=0,
)

# --- 2. ASSETS ---
def load_lottieurl(url):
    try:
        r = requests.get(url, timeout=2)
        return r.json() if r.status_code == 200 else None
    except: return None

anim_tree = load_lottieurl("https://lottie.host/6e35574d-8651-477d-b570-56965c276b3b/22572535-373f-42a9-823c-99e582862594.json")
anim_smoke = load_lottieurl("https://lottie.host/575a66c6-1215-4688-9189-b57579621379/10839556-9141-4712-a89e-224429715783.json")
anim_money = load_lottieurl("https://lottie.host/02008323-2895-4673-863a-4934e402802d/41838634-11d9-430c-992a-356c92d529d3.json")
anim_sun = load_lottieurl("https://lottie.host/3c6c9e04-0391-4e9e-99f2-2b6f3c02d139/2Y7Q1j1j1j.json") 

# GMR COLORS: Blue #003399 | Orange #FF9933 | Red #FF3333 | Dark #002244
st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;600;700;800&display=swap');
    
    /* MAIN THEME - GMR DARK BLUE GRADIENT */
    .stApp { 
        background: linear-gradient(to bottom, #001f3f, #003366); 
        font-family: 'Inter', sans-serif;
    }
    
    /* GLASS CARDS ENHANCED */
    .glass-card {
        background: rgba(0, 34, 68, 0.6);
        background: radial-gradient(circle at top left, rgba(255,255,255,0.1) 0%, rgba(0,0,0,0.2) 100%);
        backdrop-filter: blur(12px);
        border: 1px solid rgba(255, 255, 255, 0.1);
        border-radius: 16px;
        padding: 20px;
        margin-bottom: 15px;
        box-shadow: 0 8px 32px rgba(0,0,0,0.3);
        text-align: center;
        transition: all 0.3s ease;
        line-height: 1.4;
    }
    .glass-card:hover {
        transform: scale(1.02);
        background: rgba(255, 255, 255, 0.05);
        box-shadow: 0 12px 40px rgba(0,0,0,0.4);
    }
    
    /* GMR BRANDED BORDERS */
    .border-good { border-top: 4px solid #00ff88; }
    .border-bad { border-top: 4px solid #FF3333; }
    .border-gmr { border-top: 4px solid #FF9933; }
    
    /* PLACARDS */
    .placard {
        background: #002244; padding: 15px; border-radius: 8px; 
        margin-bottom: 10px; text-align: left;
        transition: all 0.3s ease;
        border-left: 4px solid #FF9933;
    }
    .placard:hover { background: #003366; }
    .p-title { font-size: 11px; color: #ccc; text-transform: uppercase; letter-spacing: 1px; font-weight: 400;}
    .p-val { font-size: 24px; font-weight: 800; color: white; margin: 5px 0;}
    .p-sub { font-size: 12px; color: #aaa; font-weight: 300; }
    
    /* TEXT */
    .big-money { font-size: 32px; font-weight: 800; color: #FF9933; }
    .unit-header { font-size: 20px; font-weight: 700; border-bottom: 1px solid #ffffff33; padding-bottom: 10px; margin-bottom: 15px; color: white; }
    
    /* ANIMATIONS */
    @keyframes pulse {
        0% { transform: scale(1); }
        50% { transform: scale(1.05); }
        100% { transform: scale(1); }
    }
    .pulse-icon { animation: pulse 2s infinite; }
    
    /* PROGRESS BAR */
    .progress { background: #002244; height: 6px; border-radius: 3px; overflow: hidden; margin-top: 5px; }
    .progress-fill { height: 100%; background: linear-gradient(to right, #FF3333, #FF9933); transition: width 0.3s; }
    </style>
""", unsafe_allow_html=True)

# --- 3. HELPER FUNCTIONS ---
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
        file = repo.get_contents("plant_history_v20.csv", ref=st.secrets["BRANCH"])
        df = pd.read_csv(StringIO(file.decoded_content.decode()))
        df['Date'] = pd.to_datetime(df['Date'])
        return df, file.sha
    except: return pd.DataFrame(columns=["Date", "Unit", "Profit", "HR", "SOx", "NOx", "Gen"]), None

def save_history(repo, df, sha):
    try:
        csv_content = df.to_csv(index=False)
        msg = "Daily Update" if sha else "Init"
        if sha: repo.update_file("plant_history_v20.csv", msg, csv_content, sha, branch=st.secrets["BRANCH"])
        else: repo.create_file("plant_history_v20.csv", msg, csv_content, branch=st.secrets["BRANCH"])
        return True
    except: return False

def generate_excel_template():
    df = pd.DataFrame({
        'Parameter': ['Generation (MU)', 'Heat Rate (kcal/kWh)', 'Vacuum (kg/cm2)', 
                      'MS Temp (C)', 'FG Temp (C)', 'Spray (TPH)', 'SOx (mg/Nm3)', 
                      'NOx (mg/Nm3)', 'Ash Util (Tons)', 'Biomass (Tons)', 'Solar (MU)'],
        'Unit 1': [8.4, 2380, -0.90, 535, 135, 20, 550, 400, 1500, 0, 0],
        'Unit 2': [8.2, 2310, -0.92, 538, 132, 18, 540, 390, 1400, 0, 0],
        'Unit 3': [8.5, 2290, -0.93, 540, 130, 15, 530, 380, 1600, 0, 0]
    })
    return df

def generate_bulk_template():
    df = pd.DataFrame({
        'Date': ['2023-12-01', '2023-12-01', '2023-12-01'],
        'Unit': ['1', '2', '3'],
        'Profit': [50000, -20000, 10000],
        'HR': [2380, 2310, 2290],
        'SOx': [550, 540, 530],
        'NOx': [400, 390, 380],
        'Gen': [8.4, 8.2, 8.5]
    })
    return df

# --- 4. PDF GENERATOR ---
class PDF(FPDF):
    def header(self):
        self.set_font('Arial', 'B', 15)
        self.cell(0, 10, 'GMR Kamalanga - 5S & Efficiency Report', 0, 1, 'C')
        self.ln(5)

    def footer(self):
        self.set_y(-15)
        self.set_font('Arial', 'I', 8)
        self.cell(0, 10, 'Page ' + str(self.page_no()), 0, 0, 'C')

def create_pdf_report(units, fleet_pnl):
    pdf = PDF()
    pdf.add_page()
    pdf.set_font("Arial", size=12)
    
    # Executive Summary
    pdf.set_fill_color(200, 220, 255)
    pdf.cell(0, 10, f"Date: {datetime.now().strftime('%Y-%m-%d')}  |  Fleet P&L: Rs {fleet_pnl:,.0f}", 1, 1, 'C', 1)
    pdf.ln(10)
    
    # Unit Details
    pdf.set_font("Arial", 'B', 12)
    pdf.cell(0, 10, "Unit Performance", 0, 1)
    pdf.set_font("Arial", 'B', 10)
    pdf.cell(30, 10, "Unit", 1)
    pdf.cell(30, 10, "Gen (MU)", 1)
    pdf.cell(30, 10, "HR (kcal)", 1)
    pdf.cell(40, 10, "Profit (Rs)", 1)
    pdf.cell(30, 10, "SOx", 1)
    pdf.cell(30, 10, "NOx", 1)
    pdf.ln()
    
    pdf.set_font("Arial", size=10)
    for u in units:
        pdf.cell(30, 10, f"Unit {u['id']}", 1)
        pdf.cell(30, 10, str(u['gen']), 1)
        pdf.cell(30, 10, str(u['hr']), 1)
        pdf.cell(40, 10, f"{u['profit']:,.0f}", 1)
        pdf.cell(30, 10, str(u['sox']), 1)
        pdf.cell(30, 10, str(u['nox']), 1)
        pdf.ln()
        
    return pdf.output(dest='S').encode('latin-1')

# --- 5. CALCULATION ENGINE ---
def calculate_unit(u_id, gen, hr, inputs, design_vals, ash_params):
    TARGET_HR = design_vals['target_hr']
    DESIGN_HR = 2250 
    COAL_GCV = design_vals['gcv']
    LIMIT_SOX = design_vals['limit_sox']
    LIMIT_NOX = design_vals['limit_nox']
    
    kcal_diff = (TARGET_HR - hr) * gen * 1_000_000
    escerts = kcal_diff / 10_000_000
    coal_saved_kg = kcal_diff / COAL_GCV
    carbon_tons = (coal_saved_kg / 1000) * 1.7
    profit = (escerts * 1000) + (carbon_tons * 500) + (coal_saved_kg * 4.5)
    
    trees_count = abs(carbon_tons / 0.025)
    acres_land = trees_count / 500
    
    l_vac = max(0, (inputs['vac'] - (-0.92)) / 0.01 * 18) * -1
    l_ms = max(0, (540 - inputs['ms']) * 1.2)
    l_fg = max(0, (inputs['fg'] - 130) * 1.5)
    l_spray = max(0, (inputs['spray'] - 15) * 2.0)
    theo_hr = DESIGN_HR + l_ms + l_fg + l_spray + 50 
    l_unacc = max(0, hr - theo_hr - abs(l_vac))
    total_pen = abs(l_vac) + l_ms + l_fg + l_spray + l_unacc
    score_5s = max(0, 100 - (total_pen / 3.0))
    
    carbon_intensity = (carbon_tons / gen) if gen > 0 else 0
    specific_sox = inputs['sox'] / gen if gen > 0 else 0
    specific_nox = inputs['nox'] / gen if gen > 0 else 0
    
    coal_consumed = (gen * hr * 1000) / COAL_GCV if COAL_GCV > 0 else 0
    ash_gen = coal_consumed * (ash_params['ash_pct'] / 100)
    ash_util = ash_params['util_tons']
    ash_stocked = ash_gen - ash_util
    bricks_current = ash_util * 666
    bricks_potential_total = ash_gen * 666
    burj_pct = (bricks_current / 165_000_000) * 100
    
    return {
        "id": u_id, "gen": gen, "hr": hr, "profit": profit, 
        "escerts": escerts, "carbon": carbon_tons, 
        "trees": trees_count, "acres": acres_land,
        "score": score_5s, "sox": inputs['sox'], "nox": inputs['nox'],
        "limits": {'sox': LIMIT_SOX, 'nox': LIMIT_NOX},
        "losses": {"Vacuum": abs(l_vac), "MS Temp": l_ms, "Flue Gas": l_fg, "Spray": l_spray, "Unaccounted": l_unacc},
        "emissions": {"carbon_intensity": carbon_intensity, "specific_sox": specific_sox, "specific_nox": specific_nox},
        "ash": {"generated": ash_gen, "utilized": ash_util, "stocked": ash_stocked, 
                "bricks_made": bricks_current, "bricks_potential": bricks_potential_total,
                "burj_pct": burj_pct}
    }

# --- 6. SIDEBAR INPUTS ---
with st.sidebar:
    try:
        st.image("1000051706.png", width="stretch")
    except:
        st.markdown("## **GMR POWER**") 
        
    st.title("Control Panel")
    
    # EXCEL UPLOAD FEATURE
    st.markdown("### 📤 Daily Input Upload")
    uploaded_file = st.file_uploader("Upload Daily Parameters", type=['xlsx'])
    
    defaults = {}
    if uploaded_file is not None:
        try:
            df_up = pd.read_excel(uploaded_file)
            df_up.set_index('Parameter', inplace=True)
            defaults = df_up.to_dict()
            st.success("Data Loaded!")
        except:
            st.error("Invalid Format")
    
    template_df = generate_excel_template()
    output = BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        template_df.to_excel(writer, index=False)
    st.download_button("📥 Daily Input Template", data=output.getvalue(), file_name="daily_log_template.xlsx")

    st.markdown("---")
    
    # BULK HISTORY UPLOAD (NEW FEATURE)
    with st.expander("📂 Bulk History Upload (Back-Date)"):
        bulk_file = st.file_uploader("Upload Multi-Day History", type=['csv'])
        if bulk_file:
            if st.button("🚀 Process Bulk Upload"):
                try:
                    df_bulk = pd.read_csv(bulk_file)
                    df_bulk['Date'] = pd.to_datetime(df_bulk['Date'])
                    repo = init_github()
                    if repo:
                        df_curr, sha = load_history(repo)
                        df_comb = pd.concat([df_curr, df_bulk], ignore_index=True) if not df_curr.empty else df_bulk
                        save_history(repo, df_comb, sha)
                        st.success(f"Success! {len(df_bulk)} rows added.")
                except Exception as e:
                    st.error(f"Error: {e}")
        
        # Template for Bulk
        bulk_csv = generate_bulk_template().to_csv(index=False)
        st.download_button("📥 Bulk History Template", bulk_csv, "bulk_history_template.csv", "text/csv")

    st.markdown("---")
    
    tab_input, tab_ash, tab_renew, tab_config = st.tabs(["📝 Daily", "🪨 Ash", "☀️ Green", "⚙️ Config"])
    
    with tab_config:
        st.markdown("### 🌍 Emission Limits")
        lim_sox = st.number_input("SOx Limit", value=600)
        lim_nox = st.number_input("NOx Limit", value=450)
        st.markdown("### 🎯 Unit Targets")
        t_u1 = st.number_input("U1 Target HR", value=2300)
        g_u1 = st.number_input("U1 GCV", value=3600)
        st.divider()
        t_u2 = st.number_input("U2 Target HR", value=2310)
        g_u2 = st.number_input("U2 GCV", value=3550)
        st.divider()
        t_u3 = st.number_input("U3 Target HR", value=2295)
        g_u3 = st.number_input("U3 GCV", value=3620)

    with tab_ash:
        coal_ash = st.number_input("Ash Content (%)", 35.0)
        pond_cap = st.number_input("Pond Capacity (Tons)", 500000)
        pond_curr = st.number_input("Current Stock (Tons)", 350000)
        
        def get_val(u, row, def_val):
            if uploaded_file and u in defaults and row in defaults[u]:
                try: return float(defaults[u][row])
                except: return def_val
            return def_val

        u1_ash_ut = st.number_input("U1 Ash Utilized", value=get_val('Unit 1', 'Ash Util (Tons)', 1500.0))
        u2_ash_ut = st.number_input("U2 Ash Utilized", value=get_val('Unit 2', 'Ash Util (Tons)', 1400.0))
        u3_ash_ut = st.number_input("U3 Ash Utilized", value=get_val('Unit 3', 'Ash Util (Tons)', 1600.0))

    with tab_renew:
        st.markdown("### 🌱 Biomass Co-firing")
        bio_u1 = st.number_input("U1 Biomass (Tons)", value=get_val('Unit 1', 'Biomass (Tons)', 0.0))
        bio_u2 = st.number_input("U2 Biomass (Tons)", value=get_val('Unit 2', 'Biomass (Tons)', 0.0))
        bio_u3 = st.number_input("U3 Biomass (Tons)", value=get_val('Unit 3', 'Biomass (Tons)', 0.0))
        bio_gcv = st.number_input("Biomass GCV", value=3000.0)
        st.markdown("### ☀️ Solar Generation")
        sol_u1 = st.number_input("Solar Gen (MU)", value=get_val('Unit 1', 'Solar (MU)', 0.0))
        
    with tab_input:
        date_in = st.date_input("Log Date", datetime.now())
        units_data = []
        configs = [
            {'target_hr': t_u1, 'gcv': g_u1, 'limit_sox': lim_sox, 'limit_nox': lim_nox},
            {'target_hr': t_u2, 'gcv': g_u2, 'limit_sox': lim_sox, 'limit_nox': lim_nox},
            {'target_hr': t_u3, 'gcv': g_u3, 'limit_sox': lim_sox, 'limit_nox': lim_nox}
        ]
        ash_utils = [u1_ash_ut, u2_ash_ut, u3_ash_ut]
        
        for i in range(1, 4):
            u_key = f'Unit {i}'
            with st.expander(f"Unit {i} Inputs", expanded=(i==1)):
                gen = st.number_input(f"U{i} Gen (MU)", value=get_val(u_key, 'Generation (MU)', 8.4), key=f"g{i}")
                hr = st.number_input(f"U{i} HR (kcal)", value=get_val(u_key, 'Heat Rate (kcal/kWh)', 2380.0), key=f"h{i}")
                vac = st.number_input(f"Vacuum", value=get_val(u_key, 'Vacuum (kg/cm2)', -0.90), step=0.001, format="%.3f", key=f"v{i}")
                ms = st.number_input(f"MS Temp", value=get_val(u_key, 'MS Temp (C)', 535.0), key=f"m{i}")
                fg = st.number_input(f"FG Temp", value=get_val(u_key, 'FG Temp (C)', 135.0), key=f"f{i}")
                spray = st.number_input(f"Spray", value=get_val(u_key, 'Spray (TPH)', 20.0), key=f"s{i}")
                sox = st.number_input(f"SOx", value=get_val(u_key, 'SOx (mg/Nm3)', 550.0), key=f"sx{i}")
                nox = st.number_input(f"NOx", value=get_val(u_key, 'NOx (mg/Nm3)', 400.0), key=f"nx{i}")
                ash_p = {'ash_pct': coal_ash, 'util_tons': ash_utils[i-1]}
                units_data.append(calculate_unit(str(i), gen, hr, {'vac':vac, 'ms':ms, 'fg':fg, 'spray':spray, 'sox':sox, 'nox':nox}, configs[i-1], ash_p))
        
        st.markdown("---")
        if st.button("💾 Save Daily to GitHub"):
            repo = init_github()
            if repo:
                df_curr, sha = load_history(repo)
                new_rows = []
                for u in units_data:
                    new_rows.append({
                        "Date": date_in, "Unit": u['id'], "Profit": u['profit'], 
                        "HR": u['hr'], "SOx": u['sox'], "NOx": u['nox'], "Gen": u['gen']
                    })
                df_new = pd.DataFrame(new_rows)
                df_comb = pd.concat([df_curr, df_new], ignore_index=True) if not df_curr.empty else df_new
                save_history(repo, df_comb, sha)
                st.success("History Updated!")
            else:
                st.error("Check GitHub Secrets")

# Calculate Fleet Totals
fleet_profit = sum(u['profit'] for u in units_data)
fleet_ash_gen = sum(u['ash']['generated'] for u in units_data)
fleet_ash_util = sum(u['ash']['utilized'] for u in units_data)
fleet_ash_stock = fleet_ash_gen - fleet_ash_util
daily_dump = max(1, fleet_ash_stock)
pond_days_left = (pond_cap - pond_curr) / daily_dump if daily_dump > 0 else 9999

# Renewables Calculation
total_biomass = bio_u1 + bio_u2 + bio_u3
bio_heat = total_biomass * bio_gcv * 1000
coal_equiv_bio = bio_heat / 3600
bio_co2_saved = coal_equiv_bio * 1.7
solar_co2_saved = sol_u1 * 1000 * 0.95
total_green_co2 = bio_co2_saved + solar_co2_saved
green_trees = total_green_co2 / 0.025
green_homes = (total_biomass * 3 + sol_u1 * 1000) / 10

# --- 6. MAIN PAGE LAYOUT ---
st.title("🏭 GMR Kamalanga 5S Dashboard")
st.markdown(f"**Fleet Status:** {'✅ Profitable' if fleet_profit > 0 else '🔥 Loss Making'} | **Net Daily P&L:** ₹ {fleet_profit:,.0f}")

# HEADER BUTTONS
c_head_L, c_head_R = st.columns([5, 1])
with c_head_R:
    # PDF DOWNLOAD BUTTON
    if st.button("📄 Download Report"):
        pdf_bytes = create_pdf_report(units_data, fleet_profit)
        b64 = base64.b64encode(pdf_bytes).decode()
        href = f'<a href="data:application/octet-stream;base64,{b64}" download="GMR_Daily_Report.pdf" style="text-decoration:none;"><button style="background-color:#FF9933;color:white;border:none;padding:5px 10px;border-radius:5px;cursor:pointer;">📥 Get PDF</button></a>'
        st.markdown(href, unsafe_allow_html=True)

# TABS
tabs = st.tabs(["🏠 War Room", "UNIT-1 Detail", "UNIT-2 Detail", "UNIT-3 Detail", "🪨 Ash Mgmt", "☀️ Renewables", "📚 Info", "📈 Trends", "🎮 Simulator", "🌿 Compliance"])

# --- TAB 1: WAR ROOM ---
with tabs[0]:
    c_logo, c_title = st.columns([1, 5])
    with c_logo:
        try: st.image("1000051706.png", width="stretch")
        except: st.write("GMR")
    with c_title:
        st.markdown("### 🚁 Fleet Executive Summary")
    st.divider()
    
    if fleet_profit < 0:
        st.markdown('<div style="background:#3b0e0e; color:#ffcccc; padding:15px; border-radius:8px; text-align:center; border:1px solid #FF3333;">⚠️ Fleet Alert: Efficiency Loss Detected</div>', unsafe_allow_html=True)
    
    cols = st.columns(4) 
    
    for i, u in enumerate(units_data):
        color = "#00ff88" if u['profit'] > 0 else "#FF3333"
        border = "border-good" if u['profit'] > 0 else "border-bad"
        sox_col = "#FF3333" if u['sox'] > u['limits']['sox'] else "#00ff88"
        nox_col = "#FF3333" if u['nox'] > u['limits']['nox'] else "#00ff88"
        
        with cols[i]:
            st.markdown(f"""
            <div class="glass-card {border}">
                <div class="unit-header">UNIT - {u['id']}</div>
                <div class="big-money" style="color:{color}">₹ {u['profit']:,.0f}</div>
                <div class="p-sub">Daily P&L Impact</div>
                <hr style="border-color:#ffffff33; margin:15px 0;">
                <div style="display:flex; justify-content:space-between; color:#ddd; margin-bottom:10px;">
                    <span>HR: <b>{u['hr']}</b></span>
                    <span>5S Score: <b>{u['score']:.1f}</b></span>
                </div>
                <div style="background:#001122; padding:5px; border-radius:5px; font-size:13px;">
                    <span style="color:{sox_col}">SOx: <b>{u['sox']}</b></span> | 
                    <span style="color:{nox_col}">NOx: <b>{u['nox']}</b></span>
                </div>
            </div>
            """, unsafe_allow_html=True)
            
    with cols[3]:
        pond_color = "#00ff88" if pond_days_left > 30 else "#FF3333"
        st.markdown(f"""
        <div class="glass-card" style="border-top: 4px solid {pond_color};">
            <div class="unit-header">ASH POND</div>
            <div class="big-money" style="color:{pond_color}">{pond_days_left:.0f} Days</div>
            <div class="p-sub">Capacity Remaining</div>
            <hr style="border-color:#ffffff33; margin:15px 0;">
            <div style="font-size:13px; color:#ddd;">
                Generation: <b>{fleet_ash_gen:.0f} T</b><br>
                Utilized: <b>{fleet_ash_util:.0f} T</b>
            </div>
        </div>
        """, unsafe_allow_html=True)

# --- HELPER FUNCTION FOR UNIT DETAIL ---
def render_unit_detail(u, configs):
    st.markdown(f"### 🔍 Deep Dive: Unit {u['id']}")
    c1, c2, c3 = st.columns([1, 1, 1])
    
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
        fig.update_layout(height=250, margin=dict(l=20,r=20,t=0,b=0), paper_bgcolor='rgba(0,0,0,0)', font_color='white', template='plotly_dark')
        st.plotly_chart(fig, width="stretch", key=f"gauge_{u['id']}")

    with c2:
        st.markdown("#### 🌳 Nature's Feedback")
        if u['profit'] > 0:
            if anim_tree: st_lottie(anim_tree, height=180, key=f"t_{u['id']}")
            st.success(f"**Great Job!** You avoided {abs(u['carbon']):.1f} tons of CO2.")
        else:
            if anim_smoke: st_lottie(anim_smoke, height=180, key=f"s_{u['id']}")
            st.error(f"**High Emissions!** Excess {abs(u['carbon']):.1f} tons of CO2.")

    with c3:
        st.markdown("#### 📜 5S & Compliance")
        score_col = "#00ff88" if u['score'] > 80 else "#FF9933"
        st.markdown(f"""
        <div class="glass-card" style="border-left: 5px solid {score_col}; text-align:left;">
            <div class="p-title">Auto-5S Score</div>
            <div class="p-val" style="color:{score_col}">{u['score']:.1f} / 100</div>
            <div class="p-sub">Technical Hygiene Score</div>
        </div>
        """, unsafe_allow_html=True)
        
        if u['sox'] > u['limits']['sox'] or u['nox'] > u['limits']['nox']:
             st.markdown(f'<div style="background:#3b0e0e; color:#ffcccc; padding:10px; border-radius:5px; border:1px solid #FF3333; text-align:center;">⚠️ ACID RAIN RISK<br>High SOx/NOx Levels</div>', unsafe_allow_html=True)
        else:
             st.markdown(f'<div style="background:#0e2e1b; color:#ccffcc; padding:10px; border-radius:5px; border:1px solid #00ff88; text-align:center;">✅ Safe Emissions</div>', unsafe_allow_html=True)

    st.divider()
    r2_c1, r2_c2 = st.columns([1, 2])
    
    with r2_c1:
        st.markdown("#### 💳 Certificate Wallet")
        val_esc = u['escerts'] * 1000 
        bg = "border-good" if val_esc > 0 else "border-bad"
        st.markdown(f"""
        <div class="placard {bg}">
            <div class="p-title">PAT ESCert Value</div>
            <div class="p-val">₹ {val_esc:,.0f}</div>
            <div class="p-sub">{u['escerts']:.2f} Certificates</div>
        </div>
        """, unsafe_allow_html=True)
        
        val_carb = u['carbon']
        carb_title = "CO2 Avoided" if val_carb > 0 else "Excess CO2"
        carb_color = "#00ccff" if val_carb > 0 else "#FF3333"
        st.markdown(f"""
        <div class="placard" style="border-left: 5px solid {carb_color};">
            <div class="p-title">{carb_title}</div>
            <div class="p-val">{abs(val_carb):,.2f} Tons</div>
            <div class="p-sub">Based on Coal Savings</div>
        </div>
        """, unsafe_allow_html=True)

    with r2_c2:
        st.markdown("#### 🔧 Loss Analysis (Pareto)")
        loss_df = pd.DataFrame(list(u['losses'].items()), columns=['Param', 'Loss'])
        loss_df = loss_df.sort_values('Loss', ascending=True).head(3)
        fig_bar = px.bar(loss_df, x='Loss', y='Param', orientation='h', text='Loss', color='Loss', 
                         color_continuous_scale=['#444', '#FF3333'], template='plotly_dark')
        fig_bar.update_layout(paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', font_color='white', height=300)
        fig_bar.update_traces(texttemplate='%{text:.1f}', textposition='outside')
        fig_bar.update_xaxes(showgrid=True, gridcolor='#333')
        st.plotly_chart(fig_bar, width="stretch", key=f"bar_{u['id']}")

# --- RENDER UNIT DETAILS ---
with tabs[1]: render_unit_detail(units_data[0], configs)
with tabs[2]: render_unit_detail(units_data[1], configs)
with tabs[3]: render_unit_detail(units_data[2], configs)

# --- TAB 4: ASH MANAGEMENT ---
with tabs[4]:
    st.markdown("### 🪨 Ash & By-Product Management")
    st.divider()
    
    a1, a2, a3 = st.columns(3)
    with a1:
        st.metric("Total Ash Generated", f"{fleet_ash_gen:,.0f} Tons", delta=f"{fleet_ash_gen*0.01:.0f}% of Coal")
    with a2:
        util_pct = (fleet_ash_util / fleet_ash_gen * 100) if fleet_ash_gen > 0 else 0
        st.metric("Total Ash Utilized", f"{fleet_ash_util:,.0f} Tons", delta=f"{util_pct:.1f}% Efficiency")
    with a3:
        st.metric("Net Pond Accumulation", f"{fleet_ash_stock:,.0f} Tons", delta_color="inverse", delta=f"Daily Addn")
        
    st.divider()
    
    ash1, ash2 = st.columns([1, 1])
    
    with ash1:
        st.markdown("#### 🧱 Brick Manufacturing Potential")
        total_bricks = sum(u['ash']['bricks_made'] for u in units_data)
        total_burj_pct = sum(u['ash']['burj_pct'] for u in units_data)
        
        st.info(f"**Current Utilization:** Enough to make **{total_bricks:,.0f} Bricks** today.")
        
        st.markdown(f"""
        <div style="background: linear-gradient(to right, #002244, #003366); padding: 15px; border-radius: 10px; border: 1px solid #FF9933; margin-top: 10px;">
            <h4 style="color: #FF9933; margin:0;">🏙️ Burj Khalifa Scale</h4>
            <p style="color: white; font-size: 18px;">This ash volume represents <b style="font-size: 24px; color: #00ff88;">{total_burj_pct:.2f}%</b> of a Burj Khalifa structure!</p>
        </div>
        """, unsafe_allow_html=True)
        
        df_ash = pd.DataFrame({
            "Scenario": ["Zero Utilization", "Current Actual", "100% Target"],
            "Bricks": [0, total_bricks, sum(u['ash']['bricks_potential'] for u in units_data)]
        })
        fig_ash = px.bar(df_ash, x="Scenario", y="Bricks", color="Scenario", template="plotly_dark")
        fig_ash.update_layout(paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)')
        st.plotly_chart(fig_ash, width="stretch")

    with ash2:
        st.markdown("#### 🌊 Ash Pond Survival")
        fig_pond = go.Figure(go.Indicator(
            mode = "gauge+number", value = pond_days_left, title = {'text': "Days to Overflow"},
            gauge = {
                'axis': {'range': [0, 3650]}, 
                'bar': {'color': "#00ff88" if pond_days_left > 365 else "#FF3333"},
                'steps': [{'range': [0, 180], 'color': "rgba(255,0,0,0.3)"}, {'range': [180, 3650], 'color': "rgba(0,255,0,0.1)"}]
            }
        ))
        fig_pond.update_layout(height=300, paper_bgcolor='rgba(0,0,0,0)', font_color='white')
        st.plotly_chart(fig_pond, width="stretch")
        
        if pond_days_left < 100:
            st.error(f"CRITICAL: Ash Pond will likely fill up in {pond_days_left:.0f} days at current rate!")
        else:
            st.success(f"Safe: Pond has {pond_days_left/365:.1f} years of life remaining.")

    ash_table = []
    for u in units_data:
        ash_table.append({
            "Unit": f"Unit {u['id']}",
            "Coal Consumed (T)": f"{(u['ash']['generated']/(coal_ash/100)):,.0f}",
            "Ash Generated (T)": f"{u['ash']['generated']:,.0f}",
            "Ash Utilized (T)": f"{u['ash']['utilized']:,.0f}",
            "Utilization %": f"{(u['ash']['utilized']/u['ash']['generated']*100 if u['ash']['generated']>0 else 0):.1f}%"
        })
    st.dataframe(pd.DataFrame(ash_table), width="stretch")

# --- TAB 5: RENEWABLES (GREEN) ---
with tabs[5]:
    st.markdown("### ☀️ Renewables & Sustainability")
    st.info("Carbon credits reward verifiable GHG reductions. Biomass is carbon-neutral as CO₂ released equals what plants absorbed.")
    st.divider()
    
    g1, g2 = st.columns([1, 1])
    with g1:
        st.markdown("#### 🌱 Biomass Co-firing Impact")
        st.metric("Biomass Utilized", f"{total_biomass} Tons")
        st.metric("CO2 Avoided (Biomass)", f"{bio_co2_saved:.2f} Tons", delta_color="normal")
    with g2:
        st.markdown("#### ☀️ Solar Generation Impact")
        st.metric("Solar Generation", f"{sol_u1} MU")
        st.metric("CO2 Avoided (Solar)", f"{solar_co2_saved:.2f} Tons", delta_color="normal")
    
    st.divider()
    st.markdown("#### 🌏 Total Green Impact")
    col_g_1, col_g_2, col_g_3 = st.columns(3)
    with col_g_1:
        st.markdown(f"""<div class="glass-card" style="border-top: 4px solid #00ff88;"><div class="big-money" style="color:#00ff88">{total_green_co2:.2f} Tons</div><div class="p-sub">Total CO2 Avoided</div></div>""", unsafe_allow_html=True)
    with col_g_2:
        st.markdown(f"""<div class="glass-card"><div class="big-money" style="color:#00ccff">{green_trees:,.0f}</div><div class="p-sub">Equivalent Trees</div></div>""", unsafe_allow_html=True)
        if anim_tree: st_lottie(anim_tree, height=100, key="green_tree")
    with col_g_3:
        st.markdown(f"""<div class="glass-card"><div class="big-money" style="color:#FF9933">{green_homes:,.0f}</div><div class="p-sub">Homes Powered</div></div>""", unsafe_allow_html=True)
        if anim_sun: st_lottie(anim_sun, height=100, key="sun")

# --- TAB 6: INFO ---
with tabs[6]:
    st.markdown("### 📚 Plant Overview & Logic")
    try: st.image("1000051705.jpg", caption="GMR Kamalanga Energy Limited", width="stretch")
    except: st.info("Plant image missing.")
    st.divider()
    info_c1, info_c2 = st.columns(2)
    with info_c1: st.markdown("""<div class="glass-card"><h3 style="color:#FF9933">PAT ESCerts</h3><p>Formula: (Target - Actual) * Gen / 10^7</p></div>""", unsafe_allow_html=True)
    with info_c2: st.markdown("""<div class="glass-card"><h3 style="color:#00ccff">Carbon Credits</h3><p>Formula: Coal Saved * 1.7</p></div>""", unsafe_allow_html=True)
    st.image("https://upload.wikimedia.org/wikipedia/commons/thumb/b/bb/Rankine_cycle_with_superheat.jpg/640px-Rankine_cycle_with_superheat.jpg", caption="Reference: Rankine Cycle")

# --- TAB 7: TRENDS ---
with tabs[7]:
    st.markdown("### 📈 Historical Performance")
    period = st.radio("Select Period:", ["Last 7 Days", "Last 30 Days"], horizontal=True)
    repo = init_github()
    if repo:
        df_hist, sha = load_history(repo)
        if not df_hist.empty:
            if "7 Days" in period: cutoff = datetime.now() - timedelta(days=7)
            else: cutoff = datetime.now() - timedelta(days=30)
            df_hist = df_hist[df_hist['Date'] >= cutoff]
            if not df_hist.empty:
                fig_hr = px.line(df_hist, x="Date", y="HR", color="Unit", markers=True, template="plotly_dark")
                st.plotly_chart(fig_hr, width="stretch")
                fig_pl = px.bar(df_hist, x="Date", y="Profit", color="Unit", barmode="group", template="plotly_dark")
                st.plotly_chart(fig_pl, width="stretch")
            else: st.warning("No data.")
        else: st.info("No history.")
    else: st.warning("GitHub not connected.")

# --- TAB 8: SIMULATOR ---
with tabs[8]:
    st.markdown("### 🎮 What-If Simulator")
    if anim_money: st_lottie(anim_money, height=150)
    c_sim1, c_sim2 = st.columns([1, 2])
    with c_sim1:
        s_vac = st.slider("Simulate Vacuum", -0.85, -0.99, -0.90)
        s_gen = st.slider("Simulate Load", 300, 350, 350)
    with c_sim2:
        sim_inputs = {'vac': s_vac, 'ms': 535, 'fg': 135, 'spray': 20, 'sox': 550, 'nox': 400}
        sim_unit = calculate_unit("1", s_gen / 100, 2350, sim_inputs, configs[0], {'ash_pct': 35, 'util_tons': 1000}) 
        st.metric("Simulated Profit", f"₹ {sim_unit['profit']:,.0f}")

# --- TAB 9: COMPLIANCE ---
with tabs[9]:
    st.markdown("### 🌿 Emissions Compliance")
    st.divider()
    col1, col2, col3, col4 = st.columns(4)
    total_gen = sum(u['gen'] for u in units_data)
    fleet_carbon = sum(u['carbon'] for u in units_data)
    fleet_sox = sum(u['sox'] * u['gen'] for u in units_data) / total_gen if total_gen > 0 else 0
    with col1: st.metric("Fleet CO2", f"{fleet_carbon:.2f} T")
    with col2: st.metric("Avg SOx", f"{fleet_sox:.1f}")
    st.divider()
    ledger_df = pd.DataFrame([{"Item": "Daily CO2", "Value": f"{fleet_carbon:.2f} Tons"},{"Item": "ESCerts Offset", "Value (₹)": f"₹ {sum(u['escerts'] * 1000 for u in units_data):,.0f}"}])
    st.dataframe(ledger_df, width="stretch")
