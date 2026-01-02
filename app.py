import streamlit as st
import plotly.graph_objects as go
import plotly.express as px
import pandas as pd
from github import Github, Auth
from io import StringIO
from datetime import datetime, timedelta
import requests
from streamlit_lottie import st_lottie

# --- PAGE CONFIGURATION ---
st.set_page_config(page_title="5S Eco-Tracker Pro", layout="wide", page_icon="🏭")

# --- ASSETS (Robust Loader) ---
def load_lottieurl(url):
    try:
        r = requests.get(url, timeout=3)
        return r.json() if r.status_code == 200 else None
    except: return None

# Animations
anim_happy_tree = load_lottieurl("https://lottie.host/6e35574d-8651-477d-b570-56965c276b3b/22572535-373f-42a9-823c-99e582862594.json")
anim_pollution = load_lottieurl("https://lottie.host/575a66c6-1215-4688-9189-b57579621379/10839556-9141-4712-a89e-224429715783.json")
anim_factory = load_lottieurl("https://lottie.host/575a66c6-1215-4688-9189-b57579621379/10839556-9141-4712-a89e-224429715783.json")

# --- CUSTOM CSS ---
st.markdown("""
    <style>
    .metric-container {
        background-color: #1E1E1E; border: 1px solid #333; padding: 20px; border-radius: 10px; margin-bottom: 10px;
    }
    </style>
""", unsafe_allow_html=True)

# --- GITHUB CONNECTION ---
def init_github():
    try:
        if "GITHUB_TOKEN" in st.secrets:
            auth = Auth.Token(st.secrets["GITHUB_TOKEN"])
            g = Github(auth=auth)
            return g.get_repo(st.secrets["REPO_NAME"])
    except: return None

def load_data(repo):
    if not repo: return pd.DataFrame(), None
    try:
        file = repo.get_contents("history_v6.csv", ref=st.secrets["BRANCH"])
        df = pd.read_csv(StringIO(file.decoded_content.decode()))
        df['Date'] = pd.to_datetime(df['Date']) # Ensure Date is datetime object
        return df, file.sha
    except: return pd.DataFrame(columns=["Date", "HR", "ESCert", "Carbon", "Profit"]), None

def save_data(repo, df, sha):
    try:
        csv_content = df.to_csv(index=False)
        msg = "Daily Update" if sha else "Initial Commit"
        if sha: repo.update_file("history_v6.csv", msg, csv_content, sha, branch=st.secrets["BRANCH"])
        else: repo.create_file("history_v6.csv", msg, csv_content, branch=st.secrets["BRANCH"])
        return True
    except: return False

# --- SIDEBAR: SETTINGS ---
with st.sidebar:
    st.header("⚙️ Plant Settings")
    with st.expander("Design Data (Reference)", expanded=False):
        DESIGN_HEAT_RATE = st.number_input("Design HR", value=2250.0)
        TARGET_HEAT_RATE = st.number_input("PAT Target HR", value=2350.0)
        DESIGN_MS_TEMP = st.number_input("Design MS Temp", value=540.0)
        DESIGN_VACUUM = st.number_input("Design Vacuum", value=-0.92)
        DESIGN_FG_TEMP = st.number_input("Design FG Temp", value=130.0)

    st.header("📝 Daily Log")
    with st.form("daily_input"):
        date_input = st.date_input("Date", datetime.now())
        
        st.markdown("### 1. Key Performance")
        # THIS IS NEW: Direct Input for Heat Rate
        actual_hr_input = st.number_input("Actual Heat Rate (kcal/kWh)", value=2380.0, step=1.0, help="Today's measured Station Heat Rate")
        gross_gen_mu = st.number_input("Gross Gen (MU)", value=12.0, min_value=0.0, step=0.1)
        
        st.markdown("### 2. 5S Parameters (For Analysis)")
        ms_temp = st.number_input("MS Temp (°C)", value=535.0, step=1.0)
        vacuum = st.number_input("Vacuum (kg/cm2)", value=-0.90, max_value=0.0, step=0.01)
        fg_temp = st.number_input("APH Out Temp (°C)", value=135.0, step=1.0)
        sh_spray = st.number_input("Total Spray (TPH)", value=15.0, step=1.0)
        coal_gcv = st.number_input("Coal GCV", value=3600.0, step=10.0)
        
        submitted = st.form_submit_button("🚀 Update Dashboard")

# --- LOGIC ENGINE ---

# 1. Financials (Based on ACTUAL INPUT)
gross_gen_units = gross_gen_mu * 1_000_000
hr_diff_vs_target = TARGET_HEAT_RATE - actual_hr_input
total_kcal_saved = hr_diff_vs_target * gross_gen_units

# PAT (1 ESCert = 10 Gcal)
escerts = total_kcal_saved / 10_000_000

# Carbon Credits
coal_saved_kg = total_kcal_saved / coal_gcv if coal_gcv > 0 else 0
carbon_credits = (coal_saved_kg / 1000) * 1.7 
trees_impact = abs(carbon_credits) * 40 

# Money
ESCERT_PRICE = 1000
CARBON_PRICE = 500
COAL_PRICE = 4.5
monetary_total = (escerts * ESCERT_PRICE) + (carbon_credits * CARBON_PRICE) + (coal_saved_kg * COAL_PRICE)

# 2. Technical Analysis (Based on PARAMETERS)
loss_ms = max(0, (DESIGN_MS_TEMP - ms_temp) * 1.2)
loss_vac = max(0, ((vacuum - DESIGN_VACUUM) / 0.01) * 18) if vacuum > DESIGN_VACUUM else 0
loss_fg = max(0, (fg_temp - DESIGN_FG_TEMP) * 1.5)
loss_spray = (sh_spray) * 2.0
loss_constant = 50.0

# "Calculated" HR based on losses
theoretical_hr_from_losses = DESIGN_HEAT_RATE + loss_ms + loss_vac + loss_fg + loss_spray + loss_constant
# "Unaccounted" Loss (Difference between what you input and what parameters say)
unaccounted_loss = max(0, actual_hr_input - theoretical_hr_from_losses)

# 3. 5S Score
total_identifiable_loss = loss_ms + loss_vac + loss_fg + loss_spray + unaccounted_loss
calc_5s_score = max(0, 100 - (total_identifiable_loss / 3))

# --- DASHBOARD LAYOUT ---

# HEADER
c_head1, c_head2 = st.columns([1, 6])
with c_head1: 
    if anim_factory: st_lottie(anim_factory, height=100, key="head")
with c_head2:
    st.title("Smart 5S & Efficiency Dashboard")
    st.markdown(f"**Date:** {date_input.strftime('%d %b %Y')} | **Unit Load:** {gross_gen_mu/0.024:.0f} MW (Avg)")

# BANNER
if monetary_total >= 0:
    st.markdown(f'<div style="background:#004d00;padding:15px;border-radius:10px;text-align:center;border:2px solid #00ff00;">'
                f'<h2 style="color:white;margin:0">💰 PROFIT: ₹ {monetary_total:,.0f}</h2></div>', unsafe_allow_html=True)
else:
    st.markdown(f'<div style="background:#5a0000;padding:15px;border-radius:10px;text-align:center;border:2px solid #ff4b4b;">'
                f'<h2 style="color:white;margin:0">🔥 LOSS: ₹ {monetary_total:,.0f}</h2></div>', unsafe_allow_html=True)

st.markdown("---")

# TABS
tab_main, tab_trend, tab_anal = st.tabs(["📊 Live Dashboard", "📈 Trends & History", "🔧 Technical Breakdown"])

# TAB 1: LIVE DASHBOARD
with tab_main:
    col_l, col_r = st.columns([1, 1])
    
    with col_l:
        st.subheader("Speedometer: Station Heat Rate")
        # ANIMATED GAUGE
        fig_gauge = go.Figure(go.Indicator(
            mode = "gauge+number+delta",
            value = actual_hr_input, # Uses Input Value directly
            domain = {'x': [0, 1], 'y': [0, 1]},
            title = {'text': "kcal/kWh"},
            delta = {'reference': TARGET_HEAT_RATE, 'increasing': {'color': "red"}, 'decreasing': {'color': "green"}},
            gauge = {
                'axis': {'range': [2000, 2600], 'tickwidth': 1},
                'bar': {'color': "white"},
                'steps': [
                    {'range': [2000, DESIGN_HEAT_RATE], 'color': "#008000"}, # Best
                    {'range': [DESIGN_HEAT_RATE, TARGET_HEAT_RATE], 'color': "#FFD700"}, # Warning
                    {'range': [TARGET_HEAT_RATE, 2600], 'color': "#FF0000"}], # Bad
                'threshold': {'line': {'color': "cyan", 'width': 4}, 'thickness': 0.75, 'value': actual_hr_input}}
        ))
        st.plotly_chart(fig_gauge, width="stretch")
        
    with col_r:
        st.subheader("Environmental Impact")
        c1, c2 = st.columns(2)
        with c1:
            st.metric("PAT ESCerts", f"{escerts:.2f}", delta_color="normal")
            st.metric("Carbon Credits", f"{carbon_credits:.2f}", delta_color="normal")
        with c2:
            # Animation Logic
            if monetary_total >= 0:
                st.markdown(f"#### 🌲 {trees_impact:,.0f} Trees Planted")
                if anim_happy_tree: st_lottie(anim_happy_tree, height=150, key="tree")
            else:
                st.markdown(f"#### 🪓 {trees_impact:,.0f} Trees Cut")
                if anim_pollution: st_lottie(anim_pollution, height=150, key="smoke")

# TAB 2: TRENDS (THE NEW FEATURE)
with tab_trend:
    repo = init_github()
    df_hist, sha = load_data(repo)
    
    if not df_hist.empty and len(df_hist) > 1:
        st.markdown("### 📅 Weekly & Monthly Performance")
        
        # Sort by date
        df_hist = df_hist.sort_values('Date')
        
        # Graph 1: Heat Rate Trend
        fig_trend_hr = px.line(df_hist, x='Date', y='HR', markers=True, title='Station Heat Rate Trend')
        fig_trend_hr.add_hline(y=TARGET_HEAT_RATE, line_dash="dash", line_color="red", annotation_text="Target")
        fig_trend_hr.update_layout(template="plotly_dark", hovermode="x unified")
        st.plotly_chart(fig_trend_hr, width="stretch")
        
        # Graph 2: Financial Trend
        col_t1, col_t2 = st.columns(2)
        with col_t1:
            fig_trend_fin = px.bar(df_hist, x='Date', y='Profit', title='Daily Profit/Loss (₹)',
                                 color='Profit', color_continuous_scale=['red', 'green'])
            fig_trend_fin.update_layout(template="plotly_dark")
            st.plotly_chart(fig_trend_fin, width="stretch")
            
        with col_t2:
            fig_trend_carb = px.area(df_hist, x='Date', y='Carbon', title='Carbon Credits Accumulated')
            fig_trend_carb.update_layout(template="plotly_dark")
            st.plotly_chart(fig_trend_carb, width="stretch")
            
    else:
        st.info("⚠️ Not enough history yet. Save data for at least 2 days to see trends here.")

# TAB 3: ANALYSIS
with tab_anal:
    st.subheader("Where is the heat going?")
    
    # Waterfall with Unaccounted
    fig_water = go.Figure(go.Waterfall(
        name = "20", orientation = "v",
        measure = ["relative", "relative", "relative", "relative", "relative", "relative", "total"],
        x = ["Design HR", "MS Temp", "Vacuum", "Flue Gas", "Spray", "Unaccounted", "ACTUAL"],
        y = [DESIGN_HEAT_RATE, loss_ms, loss_vac, loss_fg, loss_spray, unaccounted_loss, 0],
        connector = {"line":{"color":"rgb(63, 63, 63)"}},
        decreasing = {"marker":{"color":"#00FF00"}},
        increasing = {"marker":{"color":"#FF4B4B"}},
        totals = {"marker":{"color":"#FFFFFF"}}
    ))
    fig_water.update_layout(title="Loss Breakdown (kcal/kWh)", template="plotly_dark", height=400)
    st.plotly_chart(fig_water, width="stretch")
    
    if unaccounted_loss > 30:
        st.warning(f"⚠️ High Unaccounted Loss ({unaccounted_loss:.0f} kcal). Check Cycle Isolation / Passing Valves.")

# --- SAVE BUTTON ---
if repo:
    if st.button("💾 Save Today's Data"):
        new_row = pd.DataFrame([{
            "Date": date_input, 
            "HR": actual_hr_input, 
            "ESCert": escerts, 
            "Carbon": carbon_credits, 
            "Profit": monetary_total
        }])
        
        if not df_hist.empty:
            df_updated = pd.concat([df_hist, new_row]).drop_duplicates(subset=["Date"], keep='last')
        else:
            df_updated = new_row
            
        if save_data(repo, df_updated, sha): st.success("Data Saved & Trends Updated!")
