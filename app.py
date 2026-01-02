import streamlit as st
import plotly.graph_objects as go
import plotly.express as px
import pandas as pd
from github import Github, Auth
from io import StringIO
from datetime import datetime
import requests
from streamlit_lottie import st_lottie

# --- PAGE CONFIGURATION (Must be first) ---
st.set_page_config(page_title="5S Power Command", layout="wide", page_icon="⚡")

# --- 1. ASSETS & ANIMATIONS ---
def load_lottieurl(url):
    try:
        r = requests.get(url, timeout=3)
        return r.json() if r.status_code == 200 else None
    except: return None

# New High-Quality Animation Links
anim_wealth = load_lottieurl("https://lottie.host/6e35574d-8651-477d-b570-56965c276b3b/22572535-373f-42a9-823c-99e582862594.json")
anim_warning = load_lottieurl("https://lottie.host/02008323-2895-4673-863a-4934e402802d/41838634-11d9-430c-992a-356c92d529d3.json")
anim_factory = load_lottieurl("https://lottie.host/575a66c6-1215-4688-9189-b57579621379/10839556-9141-4712-a89e-224429715783.json")

# --- 2. PROFESSIONAL STYLING (CSS) ---
st.markdown("""
    <style>
    /* MAIN BACKGROUND GRADIENT (Subtle Dark Blue-Black) */
    .stApp {
        background: linear-gradient(to bottom, #0e1117, #161b22);
    }
    
    /* GLASSMORPHISM CARDS */
    .glass-card {
        background: rgba(255, 255, 255, 0.05);
        backdrop-filter: blur(10px);
        -webkit-backdrop-filter: blur(10px);
        border: 1px solid rgba(255, 255, 255, 0.1);
        border-radius: 15px;
        padding: 20px;
        margin-bottom: 20px;
        box-shadow: 0 4px 6px rgba(0, 0, 0, 0.3);
        text-align: center;
    }
    
    /* NEON GLOW FOR PROFIT */
    .card-profit {
        border: 2px solid #00ff00;
        box-shadow: 0 0 15px rgba(0, 255, 0, 0.3);
        background: linear-gradient(145deg, rgba(0,50,0,0.4), rgba(0,20,0,0.8));
    }
    
    /* NEON GLOW FOR LOSS */
    .card-loss {
        border: 2px solid #ff3333;
        box-shadow: 0 0 15px rgba(255, 50, 50, 0.3);
        background: linear-gradient(145deg, rgba(50,0,0,0.4), rgba(20,0,0,0.8));
    }

    /* SCROLLING TICKER (Fixed Format) */
    .ticker-container {
        width: 100%;
        overflow: hidden;
        background-color: #000;
        border-top: 2px solid #333;
        border-bottom: 2px solid #333;
        white-space: nowrap;
        box-sizing: border-box;
        padding: 10px 0;
    }
    .ticker-text {
        display: inline-block;
        padding-left: 100%;
        animation: ticker 25s linear infinite;
        font-family: 'Courier New', monospace;
        font-weight: bold;
        color: #00ffcc;
        font-size: 18px;
    }
    @keyframes ticker {
        0%   { transform: translate(0, 0); }
        100% { transform: translate(-100%, 0); }
    }
    
    /* BIG METRIC TEXT */
    .metric-value { font-size: 38px; font-weight: 800; margin: 0; }
    .metric-label { font-size: 14px; color: #aaa; text-transform: uppercase; letter-spacing: 1px; }
    
    </style>
""", unsafe_allow_html=True)

# --- 3. GITHUB DATA ENGINE ---
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
        file = repo.get_contents("history_v8.csv", ref=st.secrets["BRANCH"])
        df = pd.read_csv(StringIO(file.decoded_content.decode()))
        df['Date'] = pd.to_datetime(df['Date'])
        return df, file.sha
    except: return pd.DataFrame(columns=["Date", "HR", "Profit", "ESCert"]), None

def save_data(repo, df, sha):
    try:
        csv_content = df.to_csv(index=False)
        msg = "Daily Update" if sha else "Initial Commit"
        if sha: repo.update_file("history_v8.csv", msg, csv_content, sha, branch=st.secrets["BRANCH"])
        else: repo.create_file("history_v8.csv", msg, csv_content, branch=st.secrets["BRANCH"])
        return True
    except: return False

# --- 4. SIDEBAR (CONTROLS) ---
with st.sidebar:
    st.image("https://cdn-icons-png.flaticon.com/512/2933/2933886.png", width=50)
    st.title("Control Panel")
    
    with st.expander("⚙️ Design Parameters", expanded=False):
        DESIGN_HR = st.number_input("Design Heat Rate", value=2250.0)
        TARGET_HR = st.number_input("PAT Target HR", value=2350.0)
        DESIGN_MS = st.number_input("Design MS Temp", value=540.0)
        DESIGN_VAC = st.number_input("Design Vacuum", value=-0.92)
    
    st.markdown("### 📝 Daily Inputs")
    with st.form("daily_form"):
        date_in = st.date_input("Date", datetime.now())
        
        st.markdown("**1. Generation & Efficiency**")
        act_hr = st.number_input("Actual Heat Rate", value=2380.0, step=1.0)
        gen_mu = st.number_input("Gross Gen (MU)", value=12.0, min_value=0.0)
        
        st.markdown("**2. Technical Parameters**")
        ms_temp = st.number_input("MS Temp (°C)", value=535.0)
        vacuum = st.number_input("Vacuum (kg/cm²)", value=-0.90, max_value=0.0)
        fg_temp = st.number_input("APH Out Temp (°C)", value=135.0)
        spray = st.number_input("Total Spray (TPH)", value=15.0)
        gcv = st.number_input("Coal GCV", value=3600.0)
        
        run_btn = st.form_submit_button("🚀 UPDATE DASHBOARD")

# --- 5. CALCULATION CORE ---
# Financials
units = gen_mu * 1_000_000
hr_diff = TARGET_HR - act_hr
kcal_saved = hr_diff * units
escerts = kcal_saved / 10_000_000
coal_saved = (kcal_saved / gcv) if gcv > 0 else 0
carbon = (coal_saved / 1000) * 1.7
trees = abs(carbon) * 40
profit = (escerts * 1000) + (carbon * 500) + (coal_saved * 4.5)

# Technical Losses
loss_ms = max(0, (DESIGN_MS - ms_temp) * 1.2)
loss_vac = max(0, ((vacuum - DESIGN_VAC) / 0.01) * 18) if vacuum > DESIGN_VAC else 0
loss_fg = max(0, (fg_temp - 130) * 1.5)
loss_spray = spray * 2.0
loss_unaccounted = max(0, act_hr - (DESIGN_HR + loss_ms + loss_vac + loss_fg + loss_spray + 50))
score_5s = max(0, 100 - ((loss_ms + loss_vac + loss_fg + loss_spray + loss_unaccounted)/3))

# --- 6. HEADER & TICKER ---
c1, c2 = st.columns([1, 6])
with c1:
    if anim_factory: st_lottie(anim_factory, height=80, key="logo")
    else: st.markdown("<h1>🏭</h1>", unsafe_allow_html=True)
with c2:
    st.markdown("# 5S Power Command Center")
    st.markdown("##### *Real-time Efficiency & Carbon Monitoring System*")

# SCROLLING TICKER
alerts = [f"ACTUAL HR: {act_hr}"]
if loss_vac > 15: alerts.append("⚠️ CONDENSER VACUUM POOR")
if loss_ms > 15: alerts.append("⚠️ MS TEMP LOW")
if profit > 0: alerts.append("✅ PLANT IS PROFITABLE")
else: alerts.append("🔥 PLANT IS BURNING CASH")
ticker_content = "  |  ".join(alerts) + "  |  " + datetime.now().strftime("%H:%M:%S")

st.markdown(f"""
<div class="ticker-container">
    <div class="ticker-text">{ticker_content}</div>
</div>
""", unsafe_allow_html=True)

# --- 7. MAIN KPI DISPLAY (GLASS CARDS) ---
k1, k2, k3, k4 = st.columns(4)

with k1:
    css_class = "card-profit" if profit >= 0 else "card-loss"
    color = "#00ff00" if profit >= 0 else "#ff3333"
    st.markdown(f"""
    <div class="glass-card {css_class}">
        <div class="metric-label">Daily Financial Impact</div>
        <div class="metric-value" style="color: {color};">₹ {profit:,.0f}</div>
    </div>
    """, unsafe_allow_html=True)

with k2:
    st.markdown(f"""
    <div class="glass-card">
        <div class="metric-label">Station Heat Rate</div>
        <div class="metric-value" style="color: #00ccff;">{act_hr:.0f}</div>
        <div style="font-size: 12px; color: #888;">Target: {TARGET_HR}</div>
    </div>
    """, unsafe_allow_html=True)

with k3:
    st.markdown(f"""
    <div class="glass-card">
        <div class="metric-label">PAT ESCerts</div>
        <div class="metric-value" style="color: #ffcc00;">{escerts:.2f}</div>
        <div style="font-size: 12px; color: #888;">1 Cert = 10 Gcal</div>
    </div>
    """, unsafe_allow_html=True)

with k4:
    color_score = "#00ff00" if score_5s > 80 else "#ff9900"
    st.markdown(f"""
    <div class="glass-card">
        <div class="metric-label">Auto-5S Score</div>
        <div class="metric-value" style="color: {color_score};">{score_5s:.1f}</div>
        <div style="font-size: 12px; color: #888;">Cleanliness Index</div>
    </div>
    """, unsafe_allow_html=True)

# --- 8. VISUAL TABS ---
t1, t2, t3 = st.tabs(["📊 SPEEDOMETER & FINANCIALS", "🌱 NATURE & CARBON", "🔧 ROOT CAUSE ANALYSIS"])

with t1:
    c_left, c_right = st.columns([1, 1])
    with c_left:
        st.markdown("### 🏎️ Efficiency Gauge")
        # Custom "Dark Mode" Speedometer
        fig = go.Figure(go.Indicator(
            mode = "gauge+number+delta", value = act_hr,
            domain = {'x': [0, 1], 'y': [0, 1]},
            delta = {'reference': TARGET_HR, 'increasing': {'color': "red"}},
            gauge = {
                'axis': {'range': [2000, 2600], 'tickwidth': 1, 'tickcolor': "white"},
                'bar': {'color': "#00ccff"},
                'bgcolor': "rgba(0,0,0,0)",
                'borderwidth': 2,
                'bordercolor': "#333",
                'steps': [
                    {'range': [2000, DESIGN_HR], 'color': "rgba(0, 255, 0, 0.3)"},
                    {'range': [DESIGN_HR, TARGET_HR], 'color': "rgba(255, 255, 0, 0.3)"},
                    {'range': [TARGET_HR, 2600], 'color': "rgba(255, 0, 0, 0.3)"}
                ],
                'threshold': {'line': {'color': "red", 'width': 4}, 'thickness': 0.75, 'value': act_hr}
            }
        ))
        fig.update_layout(paper_bgcolor = "rgba(0,0,0,0)", font = {'color': "white", 'family': "Arial"})
        st.plotly_chart(fig, use_container_width=True)

    with c_right:
        st.markdown("### 💡 Shift In-Charge Assistant")
        if profit >= 0:
            st.success("✅ **System Optimal:** Parameters are within limits. Maintain current load and soot blowing schedule.")
        else:
            st.error("⚠️ **Action Required:**")
            if loss_vac > 15: st.markdown("- **Vacuum Low:** Check ejectors and gland sealing steam.")
            if loss_ms > 15: st.markdown("- **Temp Low:** Check burner tilt and mill outlet temps.")
            if loss_spray > 10: st.markdown("- **Excess Spray:** Check soot blowing; boiler might be fouled.")

with t2:
    col_env1, col_env2 = st.columns([1, 1])
    with col_env1:
        st.markdown("### 🌳 The Bio-Equivalent")
        if profit >= 0:
            if anim_wealth: st_lottie(anim_wealth, height=250, key="tree_good")
            st.markdown(f"**You saved {trees:,.0f} Trees today!**")
        else:
            if anim_warning: st_lottie(anim_warning, height=250, key="tree_bad")
            st.markdown(f"**Pollution Alert:** Equivalent to cutting **{trees:,.0f} Trees**.")

    with col_env2:
        st.info("ℹ️ **Calculation Logic:**")
        st.markdown("""
        * **Formula:** `Excess CO2 / 0.025`
        * **Science:** A mature tree absorbs ~25kg CO2/year.
        * **Context:** We convert your invisible gas emissions into visible "Trees Lost" to convey impact.
        """)

with t3:
    st.markdown("### 🔍 Where are we losing Heat? (kcal/kWh)")
    losses = pd.DataFrame({
        'Parameter': ['MS Temp', 'Vacuum', 'Flue Gas', 'Spray', 'Unaccounted'],
        'Loss (kcal)': [loss_ms, loss_vac, loss_fg, loss_spray, loss_unaccounted]
    })
    fig_bar = px.bar(losses, x='Parameter', y='Loss (kcal)', color='Loss (kcal)', color_continuous_scale='Reds')
    fig_bar.update_layout(paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", font_color="white")
    st.plotly_chart(fig_bar, use_container_width=True)

# --- 9. HISTORY SAVE ---
repo = init_github()
if repo:
    if st.button("💾 SAVE DATA TO GITHUB"):
        new_row = pd.DataFrame([{"Date": date_in, "HR": act_hr, "Profit": profit, "ESCert": escerts}])
        df_hist, sha = load_data(repo)
        df_updated = pd.concat([df_hist, new_row]).drop_duplicates(subset=["Date"], keep='last') if not df_hist.empty else new_row
        if save_data(repo, df_updated, sha):
            st.success("✅ Data Secured in Cloud!")
            st.balloons()
