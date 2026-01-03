import streamlit as st
import plotly.graph_objects as go
import plotly.express as px
import pandas as pd
import numpy as np
from datetime import datetime
import requests
from io import StringIO
from github import Github, Auth
from streamlit_lottie import st_lottie

# --- 1. CONFIGURATION & CSS ---
st.set_page_config(page_title="GMR Kamalanga 5S Command", layout="wide", page_icon="⚡")

# --- 2. ASSETS ---
def load_lottieurl(url):
    try:
        r = requests.get(url, timeout=2)
        return r.json() if r.status_code == 200 else None
    except: return None

anim_tree_happy = load_lottieurl("https://lottie.host/6e35574d-8651-477d-b570-56965c276b3b/22572535-373f-42a9-823c-99e582862594.json")
anim_smoke = load_lottieurl("https://lottie.host/575a66c6-1215-4688-9189-b57579621379/10839556-9141-4712-a89e-224429715783.json")
anim_money = load_lottieurl("https://lottie.host/02008323-2895-4673-863a-4934e402802d/41838634-11d9-430c-992a-356c92d529d3.json")

st.markdown("""
    <style>
    /* MAIN BACKGROUND GRADIENT */
    .stApp {
        background: linear-gradient(to bottom, #0e1117, #161b22);
    }
    
    /* GLASSMORPHISM CARDS (The v8 Look) */
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
        transition: transform 0.2s;
    }
    .glass-card:hover { transform: scale(1.02); }
    
    /* SCENE BORDERS (Neon Glow) */
    .scene-good { border-top: 4px solid #00ff88; box-shadow: 0 -5px 15px rgba(0, 255, 136, 0.1); }
    .scene-bad { border-top: 4px solid #ff3333; box-shadow: 0 -5px 15px rgba(255, 51, 51, 0.1); }
    
    /* PLACARDS (Visual Info Cards) */
    .placard {
        background: #1c2128;
        padding: 15px;
        border-radius: 8px;
        margin-bottom: 10px;
        border-left: 5px solid #444;
    }
    .placard-red { border-left: 5px solid #ff3333; }
    .placard-green { border-left: 5px solid #00ff88; }
    
    /* TEXT STYLES */
    .metric-value { font-size: 32px; font-weight: 800; margin: 0; }
    .metric-label { font-size: 14px; color: #aaa; text-transform: uppercase; letter-spacing: 1px; }
    .unit-title { font-size: 18px; font-weight: bold; color: #fff; margin-bottom: 10px; border-bottom: 1px solid #333; padding-bottom: 5px;}
    
    </style>
""", unsafe_allow_html=True)

# --- 3. GITHUB ENGINE ---
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
        file = repo.get_contents("plant_history_v9.csv", ref=st.secrets["BRANCH"])
        df = pd.read_csv(StringIO(file.decoded_content.decode()))
        df['Date'] = pd.to_datetime(df['Date'])
        return df, file.sha
    except: return pd.DataFrame(columns=["Date", "Unit", "Profit", "HR", "Score5S"]), None

def save_history(repo, df, sha):
    try:
        csv_content = df.to_csv(index=False)
        msg = "Daily Update" if sha else "Init"
        if sha: repo.update_file("plant_history_v9.csv", msg, csv_content, sha, branch=st.secrets["BRANCH"])
        else: repo.create_file("plant_history_v9.csv", msg, csv_content, branch=st.secrets["BRANCH"])
        return True
    except: return False

# --- 4. CALCULATION LOGIC ---
def calc_unit(u_id, gen, hr, inputs):
    # Constants
    TARGET_HR = 2300; DESIGN_HR = 2250; COAL_GCV = 3600
    
    # A. Financials
    kcal_diff = (TARGET_HR - hr) * gen * 1_000_000
    escerts = kcal_diff / 10_000_000
    coal_saved_kg = kcal_diff / COAL_GCV
    carbon = (coal_saved_kg / 1000) * 1.7
    
    # Money
    profit = (escerts * 1000) + (carbon * 500) + (coal_saved_kg * 4.5)
    
    # B. Trees (1 Tree = 25kg CO2/yr)
    trees = abs(carbon * 1000 / 25)
    
    # C. 5S Score (5 Parameters)
    # 1. Vacuum (-0.92 Ref)
    l_vac = max(0, (inputs['vac'] - (-0.92)) / 0.01 * 18) * -1
    # 2. MS Temp (540 Ref)
    l_ms = max(0, (540 - inputs['ms']) * 1.2)
    # 3. FG Temp (130 Ref)
    l_fg = max(0, (inputs['fg'] - 130) * 1.5)
    # 4. Spray (15 TPH Ref)
    l_spray = max(0, (inputs['spray'] - 15) * 2.0)
    # 5. Unaccounted (Calculated)
    theo_hr = DESIGN_HR + l_ms + l_fg + l_spray + 50 # 50 is constant
    l_unacc = max(0, hr - theo_hr - abs(l_vac)) # Approx logic
    
    # Score Formula
    total_pen = abs(l_vac) + l_ms + l_fg + l_spray + l_unacc
    score_5s = max(0, 100 - (total_pen / 3.5))
    
    return {
        "id": u_id, "gen": gen, "hr": hr, "profit": profit, 
        "escerts": escerts, "carbon": carbon, "trees": trees, "score": score_5s,
        "sox": inputs['sox'], "nox": inputs['nox'],
        "losses": {"Vacuum": abs(l_vac), "MS Temp": l_ms, "Flue Gas": l_fg, "Spray": l_spray, "Isolation": l_unacc}
    }

# --- 5. SIDEBAR INPUTS ---
with st.sidebar:
    st.image("https://cdn-icons-png.flaticon.com/512/2933/2933886.png", width=50)
    st.title("GMR Control Panel")
    date_in = st.date_input("Date", datetime.now())
    
    # Inputs for 3 Units
    units_input = []
    for i in range(1, 4):
        with st.expander(f"Unit {i} Inputs", expanded=(i==1)):
            gen = st.number_input(f"U{i} Gen (MU)", 0.0, 10.0, 8.4, key=f"g{i}")
            hr = st.number_input(f"U{i} HR (kcal)", 2000, 3000, 2380 if i==1 else 2310, key=f"h{i}")
            
            st.markdown(f"**U{i} 5S Parameters**")
            vac = st.slider(f"Vacuum", -0.80, -0.96, -0.90, key=f"v{i}")
            ms = st.number_input(f"MS Temp", 500, 550, 535, key=f"m{i}")
            fg = st.number_input(f"FG Temp", 100, 160, 135, key=f"f{i}")
            spray = st.number_input(f"Spray (TPH)", 0, 100, 20, key=f"s{i}")
            
            st.markdown(f"**U{i} Emissions**")
            sox = st.number_input(f"SOx", 0, 1000, 550, key=f"sx{i}")
            nox = st.number_input(f"NOx", 0, 1000, 400, key=f"nx{i}")
            
            units_input.append(calc_unit(str(i), gen, hr, {'vac':vac, 'ms':ms, 'fg':fg, 'spray':spray, 'sox':sox, 'nox':nox}))

# Process Fleet Data
fleet_profit = sum(u['profit'] for u in units_input)
worst_unit = min(units_input, key=lambda x: x['profit'])

# --- 6. MAIN DASHBOARD ---

# TOP BANNER
c_head1, c_head2 = st.columns([6, 1])
with c_head1:
    st.title("🏭 GMR Kamalanga War Room")
    st.markdown(f"**Fleet Net P&L:** :{'green' if fleet_profit>0 else 'red'}[₹ {fleet_profit:,.0f}] | **Status:** {'✅ Optimal' if fleet_profit > 0 else '⚠️ Attention Required'}")

with c_head2:
    if st.button("💾 Save to GitHub"):
        repo = init_github()
        if repo:
            df_curr, sha = load_history(repo)
            new_rows = []
            for u in units_input:
                new_rows.append({"Date": date_in, "Unit": u['id'], "Profit": u['profit'], "HR": u['hr'], "Score5S": u['score']})
            df_new = pd.DataFrame(new_rows)
            df_comb = pd.concat([df_curr, df_new], ignore_index=True) if not df_curr.empty else df_new
            save_history(repo, df_comb, sha)
            st.success("Saved!")
        else:
            st.error("GitHub Secrets Missing")

st.divider()

# --- SECTION 1: THE WAR ROOM (3 UNITS SUMMARY) ---
st.subheader("1. Fleet Executive Summary")
cols = st.columns(3)
for i, u in enumerate(units_input):
    color = "#00ff88" if u['profit'] > 0 else "#ff3333"
    border = "scene-good" if u['profit'] > 0 else "scene-bad"
    
    with cols[i]:
        st.markdown(f"""
        <div class="glass-card {border}">
            <div class="unit-title">UNIT - {u['id']}</div>
            <div class="metric-value" style="color:{color}">₹ {u['profit']:,.0f}</div>
            <div class="metric-label">Daily P&L</div>
            <p style="margin-top:10px; color:#aaa;">HR: <b>{u['hr']}</b> | 5S Score: <b>{u['score']:.1f}</b></p>
        </div>
        """, unsafe_allow_html=True)

# --- SECTION 2: DEEP DIVE (WORST UNIT FOCUS) ---
st.markdown("### ")
st.subheader(f"2. Priority Focus: Unit {worst_unit['id']} Deep Dive")

# Create the Hybrid Layout (Speedometer + Placards + Animation)
d1, d2, d3 = st.columns([1, 1, 1])

# COL 1: SPEEDOMETER (Visual Impact)
with d1:
    st.markdown("#### 🏎️ Efficiency Gauge")
    fig_gauge = go.Figure(go.Indicator(
        mode = "gauge+number+delta", value = worst_unit['hr'],
        delta = {'reference': 2300, 'increasing': {'color': "red"}},
        gauge = {
            'axis': {'range': [2000, 2600]}, 'bar': {'color': "#00ccff"},
            'steps': [{'range': [2000, 2300], 'color': "rgba(0,255,0,0.3)"}, {'range': [2300, 2600], 'color': "rgba(255,0,0,0.3)"}],
            'threshold': {'line': {'color': "red", 'width': 4}, 'thickness': 0.75, 'value': worst_unit['hr']}
        }
    ))
    fig_gauge.update_layout(paper_bgcolor = "rgba(0,0,0,0)", font = {'color': "white", 'family': "Arial"}, height=300)
    st.plotly_chart(fig_gauge, use_container_width=True)

# COL 2: ANIMATION & EMOTION
with d2:
    st.markdown("#### 🌳 Environmental Impact")
    if worst_unit['profit'] > 0:
        if anim_tree_happy: st_lottie(anim_tree_happy, height=200)
        st.success(f"Equivalent to planting **{worst_unit['trees']:,.0f} Trees**!")
    else:
        if anim_smoke: st_lottie(anim_smoke, height=200)
        st.error(f"Pollution equal to cutting **{worst_unit['trees']:,.0f} Trees**.")

# COL 3: PLACARDS (Data Details)
with d3:
    st.markdown("#### 📜 Key Metrics")
    
    # ESCert Placard
    val_esc = worst_unit['escerts']
    bg_esc = "placard-green" if val_esc > 0 else "placard-red"
    st.markdown(f"""
    <div class="placard {bg_esc}">
        <div class="placard-title">PAT ESCerts</div>
        <div class="placard-val">{val_esc:.2f}</div>
        <div class="placard-sub">Est Value: ₹ {val_esc*1000:,.0f}</div>
    </div>
    """, unsafe_allow_html=True)

    # Emissions Placard
    sox_stat = "⚠️ High" if worst_unit['sox'] > 600 else "✅ Normal"
    st.markdown(f"""
    <div class="placard">
        <div class="placard-title">Emission Compliance</div>
        <div class="placard-val" style="font-size: 20px;">{sox_stat}</div>
        <div class="placard-sub">SOx: {worst_unit['sox']} | NOx: {worst_unit['nox']}</div>
    </div>
    """, unsafe_allow_html=True)

# --- SECTION 3: TABS (History, Simulator, Info) ---
st.divider()
tab_trend, tab_sim, tab_info = st.tabs(["📈 History", "🎮 Simulator", "ℹ️ Reference"])

with tab_trend:
    repo = init_github()
    if repo:
        df_hist, sha = load_history(repo)
        if not df_hist.empty:
            st.markdown("### 📊 Fleet Trends")
            fig_hist = px.line(df_hist, x="Date", y="HR", color="Unit", markers=True, template="plotly_dark")
            st.plotly_chart(fig_hist, use_container_width=True)
        else:
            st.info("No history found. Click 'Save' to start tracking.")
    else:
        st.warning("GitHub not connected.")

with tab_sim:
    st.markdown("### 🎮 What-If Simulator")
    c_sim1, c_sim2 = st.columns([1, 2])
    with c_sim1:
        s_vac = st.slider("Simulate Vacuum Improvement", -0.85, -0.96, -0.90)
        s_gen = st.slider("Simulate Load (MW)", 300, 350, 350)
    with c_sim2:
        base_loss = 20 # approx
        new_loss = (abs(s_vac) - 0.90) * 100 * 15 
        savings = abs(new_loss * s_gen * 24 * 4.5)
        st.metric("Potential Daily Savings", f"₹ {savings:,.0f}")
        if anim_money: st_lottie(anim_money, height=150)

with tab_info:
    c1, c2 = st.columns(2)
    with c1:
        st.markdown("### 📜 Design Parameters (GMR)")
        st.table(pd.DataFrame({
            "Param": ["Design HR", "Target HR", "Design Vac", "SOx Limit"],
            "Value": ["2250 kcal", "2300 kcal", "-0.92 kg/cm2", "600 mg/Nm3"]
        }))
    with c2:
        st.markdown("### 🌳 Calculation Logic")
        st.info("1 ESCert = 10 Million kcal Saved")
        st.info("1 Ton Coal = 1.7 Ton CO2")
        [attachment_0](attachment)
