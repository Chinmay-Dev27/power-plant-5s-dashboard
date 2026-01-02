import streamlit as st
import plotly.graph_objects as go
import plotly.express as px
import pandas as pd
from github import Github, Auth
from io import StringIO
from datetime import datetime
import requests
from streamlit_lottie import st_lottie

# --- PAGE CONFIGURATION ---
st.set_page_config(page_title="5S Live Eco-Tracker", layout="wide", page_icon="⚡")

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
anim_alert = load_lottieurl("https://lottie.host/02008323-2895-4673-863a-4934e402802d/41838634-11d9-430c-992a-356c92d529d3.json")

# --- CUSTOM CSS (DYNAMIC ANIMATIONS) ---
st.markdown("""
    <style>
    /* Pulse Animation for Live KPIs */
    @keyframes pulse-green {
        0% { box-shadow: 0 0 0 0 rgba(0, 255, 0, 0.4); }
        70% { box-shadow: 0 0 0 10px rgba(0, 255, 0, 0); }
        100% { box-shadow: 0 0 0 0 rgba(0, 255, 0, 0); }
    }
    @keyframes pulse-red {
        0% { box-shadow: 0 0 0 0 rgba(255, 0, 0, 0.4); }
        70% { box-shadow: 0 0 0 10px rgba(255, 0, 0, 0); }
        100% { box-shadow: 0 0 0 0 rgba(255, 0, 0, 0); }
    }
    
    .live-card-good {
        background-color: #0f2e1d; padding: 20px; border-radius: 10px; 
        border: 2px solid #00ff00; animation: pulse-green 2s infinite;
        text-align: center;
    }
    .live-card-bad {
        background-color: #3b0e0e; padding: 20px; border-radius: 10px; 
        border: 2px solid #ff4b4b; animation: pulse-red 2s infinite;
        text-align: center;
    }
    
    /* Marquee / Ticker */
    .ticker-wrap {
        width: 100%; overflow: hidden; background-color: #111; padding-top: 10px; padding-bottom: 10px;
        border-bottom: 1px solid #333; margin-bottom: 20px;
    }
    .ticker-item { display: inline-block; padding-left: 100%; animation: ticker 30s linear infinite; color: #ffcc00; font-family: monospace; font-size: 18px; }
    @keyframes ticker { 0% { transform: translate3d(0, 0, 0); } 100% { transform: translate3d(-100%, 0, 0); } }
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
        file = repo.get_contents("history_v7.csv", ref=st.secrets["BRANCH"])
        df = pd.read_csv(StringIO(file.decoded_content.decode()))
        df['Date'] = pd.to_datetime(df['Date'])
        return df, file.sha
    except: return pd.DataFrame(columns=["Date", "HR", "ESCert", "Carbon", "Profit"]), None

def save_data(repo, df, sha):
    try:
        csv_content = df.to_csv(index=False)
        msg = "Daily Update" if sha else "Initial Commit"
        if sha: repo.update_file("history_v7.csv", msg, csv_content, sha, branch=st.secrets["BRANCH"])
        else: repo.create_file("history_v7.csv", msg, csv_content, branch=st.secrets["BRANCH"])
        return True
    except: return False

# --- SIDEBAR: INPUTS ---
with st.sidebar:
    st.header("⚙️ Plant Configuration")
    with st.expander("Design Data", expanded=False):
        DESIGN_HEAT_RATE = st.number_input("Design HR", value=2250.0)
        TARGET_HEAT_RATE = st.number_input("PAT Target HR", value=2350.0)
        DESIGN_MS_TEMP = st.number_input("Design MS Temp", value=540.0)
        DESIGN_VACUUM = st.number_input("Design Vacuum", value=-0.92)
        DESIGN_FG_TEMP = st.number_input("Design FG Temp", value=130.0)

    st.header("📝 Daily Log")
    with st.form("daily_input"):
        date_input = st.date_input("Date", datetime.now())
        
        st.markdown("### ⚡ Performance Input")
        actual_hr_input = st.number_input("Actual Heat Rate (kcal/kWh)", value=2380.0, step=1.0)
        gross_gen_mu = st.number_input("Gross Gen (MU)", value=12.0, min_value=0.0, step=0.1)
        
        st.markdown("### 🔧 5S Parameters")
        ms_temp = st.number_input("MS Temp (°C)", value=535.0, step=1.0)
        vacuum = st.number_input("Vacuum (kg/cm2)", value=-0.90, max_value=0.0, step=0.01)
        fg_temp = st.number_input("APH Out Temp (°C)", value=135.0, step=1.0)
        sh_spray = st.number_input("Total Spray (TPH)", value=15.0, step=1.0)
        coal_gcv = st.number_input("Coal GCV", value=3600.0, step=10.0)
        
        submitted = st.form_submit_button("🚀 Update Live Dashboard")

# --- CALCULATION ENGINE ---
# 1. Financials
gross_gen_units = gross_gen_mu * 1_000_000
hr_diff_vs_target = TARGET_HEAT_RATE - actual_hr_input
total_kcal_saved = hr_diff_vs_target * gross_gen_units
escerts = total_kcal_saved / 10_000_000

# Carbon & Trees
coal_saved_kg = total_kcal_saved / coal_gcv if coal_gcv > 0 else 0
carbon_credits = (coal_saved_kg / 1000) * 1.7 
trees_impact = abs(carbon_credits) * 40 

# Money
ESCERT_PRICE = 1000
CARBON_PRICE = 500
COAL_PRICE = 4.5
monetary_total = (escerts * ESCERT_PRICE) + (carbon_credits * CARBON_PRICE) + (coal_saved_kg * COAL_PRICE)

# 2. Technical Losses
loss_ms = max(0, (DESIGN_MS_TEMP - ms_temp) * 1.2)
loss_vac = max(0, ((vacuum - DESIGN_VACUUM) / 0.01) * 18) if vacuum > DESIGN_VACUUM else 0
loss_fg = max(0, (fg_temp - DESIGN_FG_TEMP) * 1.5)
loss_spray = (sh_spray) * 2.0
loss_constant = 50.0
theoretical_hr = DESIGN_HEAT_RATE + loss_ms + loss_vac + loss_fg + loss_spray + loss_constant
unaccounted_loss = max(0, actual_hr_input - theoretical_hr)
calc_5s_score = max(0, 100 - ((loss_ms + loss_vac + loss_fg + loss_spray + unaccounted_loss) / 3))

# --- GENERATE TICKER MESSAGE ---
alerts = []
if loss_vac > 15: alerts.append(f"⚠️ HIGH VACUUM LOSS ({loss_vac:.0f} kcal) - CHECK CONDENSER")
if loss_fg > 15: alerts.append(f"⚠️ HIGH FLUE GAS TEMP ({loss_fg:.0f} kcal) - CHECK APH")
if unaccounted_loss > 30: alerts.append(f"⚠️ UNACCOUNTED LOSS ({unaccounted_loss:.0f} kcal) - CHECK ISOLATION")
if len(alerts) == 0: alerts.append("✅ UNIT PARAMETERS NORMAL - KEEP IT UP!")
ticker_text = " | ".join(alerts) + " | " + f"LIVE HEAT RATE: {actual_hr_input} | PROFIT: ₹ {monetary_total:,.0f}"

# --- DASHBOARD HEADER ---
col_logo, col_title = st.columns([1, 6])
with col_logo:
    if anim_factory: st_lottie(anim_factory, height=80, key="head_anim")
with col_title:
    st.title("⚡ Smart 5S & Efficiency Dashboard")

# SCROLLING TICKER
st.markdown(f'<div class="ticker-wrap"><div class="ticker-item">{ticker_text}</div></div>', unsafe_allow_html=True)

# PULSING KPI CARDS
kpi1, kpi2, kpi3 = st.columns(3)
with kpi1:
    st.markdown(f"""
    <div class="{'live-card-good' if monetary_total >= 0 else 'live-card-bad'}">
        <h3 style="margin:0; color:white;">Daily Impact</h3>
        <h1 style="margin:0; font-size: 36px; color:white;">₹ {monetary_total:,.0f}</h1>
    </div>
    """, unsafe_allow_html=True)
with kpi2:
    st.markdown(f"""
    <div style="background-color: #222; padding: 20px; border-radius: 10px; border: 1px solid #444; text-align: center;">
        <h3 style="margin:0; color:#aaa;">Station Heat Rate</h3>
        <h1 style="margin:0; font-size: 36px; color:cyan;">{actual_hr_input:.0f}</h1>
        <p style="margin:0; color:#888;">Target: {TARGET_HEAT_RATE}</p>
    </div>
    """, unsafe_allow_html=True)
with kpi3:
    st.markdown(f"""
    <div style="background-color: #222; padding: 20px; border-radius: 10px; border: 1px solid #444; text-align: center;">
        <h3 style="margin:0; color:#aaa;">Auto-5S Score</h3>
        <h1 style="margin:0; font-size: 36px; color:orange;">{calc_5s_score:.1f}</h1>
        <p style="margin:0; color:#888;">/ 100</p>
    </div>
    """, unsafe_allow_html=True)

st.markdown("---")

# --- TABS ---
tab_env, tab_fin, tab_trend = st.tabs(["🌱 Environment (The Trees)", "📊 Financial Analysis", "📈 Trends"])

# TAB 1: ENVIRONMENT (Restored Emotions)
with tab_env:
    c1, c2 = st.columns([1, 1])
    with c1:
        st.subheader("Nature's Feedback")
        if monetary_total >= 0:
            if anim_happy_tree: st_lottie(anim_happy_tree, height=300, key="happy")
            st.success(f"**Great job!** You saved the equivalent of **{trees_impact:,.0f} Trees** today.")
        else:
            if anim_pollution: st_lottie(anim_pollution, height=300, key="sad")
            st.error(f"**Warning!** Excess emissions equal cutting down **{trees_impact:,.0f} Mature Trees**.")

    with c2:
        st.subheader("Carbon Details")
        st.metric("CO2 Emissions vs Baseline", f"{carbon_credits:,.2f} Tons", delta_color="normal")
        
        # RESTORED EXPLANATION
        with st.expander("ℹ️ Why Trees? (Justification)", expanded=True):
            st.markdown("""
            * **The Math:** `Excess CO2 (Tons) / 0.025`
            * **The Logic:** A mature tree absorbs ~25kg (0.025 Tons) of CO2 per year.
            * **Impact:** If we emit 100 tons excess, we need 4,000 trees to clean it up.
            """)

# TAB 2: FINANCIALS & TECHNICAL
with tab_fin:
    c1, c2 = st.columns([2, 1])
    with c1:
        st.subheader("Live Efficiency Gauge")
        fig_gauge = go.Figure(go.Indicator(
            mode = "gauge+number+delta", value = actual_hr_input,
            delta = {'reference': TARGET_HEAT_RATE, 'increasing': {'color': "red"}},
            gauge = {
                'axis': {'range': [2000, 2600]}, 'bar': {'color': "white"},
                'steps': [{'range': [2000, TARGET_HEAT_RATE], 'color': "#00cc00"}, {'range': [TARGET_HEAT_RATE, 2600], 'color': "#cc0000"}]}
        ))
        st.plotly_chart(fig_gauge, width="stretch")
        
        # WATERFALL (Technical)
        st.subheader("Loss Breakdown (kcal/kWh)")
        fig_water = go.Figure(go.Waterfall(
            orientation = "v", measure = ["relative"]*6 + ["total"],
            x = ["Design", "MS Temp", "Vacuum", "FG Temp", "Spray", "Unaccounted", "ACTUAL"],
            y = [DESIGN_HEAT_RATE, loss_ms, loss_vac, loss_fg, loss_spray, unaccounted_loss, 0],
            decreasing = {"marker":{"color":"#00FF00"}}, increasing = {"marker":{"color":"#FF4B4B"}}
        ))
        fig_water.update_layout(template="plotly_dark", height=300)
        st.plotly_chart(fig_water, width="stretch")

    with c2:
        st.subheader("Certificate Wallet")
        st.metric("PAT ESCerts", f"{escerts:.2f}")
        st.metric("Est. Value", f"₹ {escerts * ESCERT_PRICE:,.0f}")
        
        # RESTORED EXPLANATION
        with st.expander("ℹ️ ESCert Logic", expanded=True):
            st.caption("1 ESCert = 10 Gcal (10 Million kcal) energy saved vs Target.")
            st.latex(r"Cert = \frac{(Target - Actual) \times Gen}{10^7}")

# TAB 3: TRENDS
with tab_trend:
    repo = init_github()
    df_hist, sha = load_data(repo)
    if not df_hist.empty and len(df_hist) > 1:
        st.subheader("Performance History")
        df_hist = df_hist.sort_values('Date')
        
        fig_trend = px.line(df_hist, x='Date', y='HR', markers=True, title="Heat Rate Trend")
        fig_trend.add_hline(y=TARGET_HEAT_RATE, line_dash="dash", line_color="red")
        fig_trend.update_layout(template="plotly_dark")
        st.plotly_chart(fig_trend, width="stretch")
        
        fig_money = px.bar(df_hist, x='Date', y='Profit', title="Daily Profit/Loss (₹)", color='Profit', color_continuous_scale=['red', 'green'])
        fig_money.update_layout(template="plotly_dark")
        st.plotly_chart(fig_money, width="stretch")
    else:
        st.info("Save more data to generate trends.")

# --- SAVE BUTTON ---
if repo:
    if st.button("💾 Save Data"):
        new_row = pd.DataFrame([{
            "Date": date_input, "HR": actual_hr_input, "ESCert": escerts, 
            "Carbon": carbon_credits, "Profit": monetary_total
        }])
        if not df_hist.empty:
            df_updated = pd.concat([df_hist, new_row]).drop_duplicates(subset=["Date"], keep='last')
        else: df_updated = new_row
        if save_data(repo, df_updated, sha): st.success("Data Saved!")
