import streamlit as st
import plotly.graph_objects as go
import plotly.express as px
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import requests
from streamlit_lottie import st_lottie

# --- 1. PAGE CONFIGURATION ---
st.set_page_config(page_title="GMR Kamalanga 5S Command", layout="wide", page_icon="⚡")

# --- 2. ASSETS & ANIMATIONS ---
def load_lottieurl(url):
    try:
        r = requests.get(url, timeout=2)
        return r.json() if r.status_code == 200 else None
    except: return None

anim_tree_happy = load_lottieurl("https://lottie.host/6e35574d-8651-477d-b570-56965c276b3b/22572535-373f-42a9-823c-99e582862594.json")
anim_smoke = load_lottieurl("https://lottie.host/575a66c6-1215-4688-9189-b57579621379/10839556-9141-4712-a89e-224429715783.json")
anim_money = load_lottieurl("https://lottie.host/02008323-2895-4673-863a-4934e402802d/41838634-11d9-430c-992a-356c92d529d3.json")

# --- 3. CSS STYLING (The "War Room" Look) ---
st.markdown("""
    <style>
    .stApp { background-color: #0e1117; }
    
    /* UNIT CARDS */
    .unit-card {
        background-color: #161b22;
        border: 1px solid #30363d;
        border-radius: 8px;
        padding: 15px;
        text-align: center;
        transition: transform 0.2s;
    }
    .unit-card:hover { transform: scale(1.02); }
    
    /* SCENE BORDERS */
    .scene-good { border-top: 5px solid #00ff88; }
    .scene-bad { border-top: 5px solid #ff3333; }
    .scene-warn { border-top: 5px solid #ffb000; }
    
    /* METRICS */
    .big-money { font-size: 28px; font-weight: 700; color: white; }
    .delta-pos { color: #00ff88; font-size: 14px; }
    .delta-neg { color: #ff3333; font-size: 14px; }
    
    /* EXPLANATION BOXES */
    .fact-box {
        background: #1c2128; border-left: 4px solid #00aaff;
        padding: 10px; margin-bottom: 10px; border-radius: 4px;
        font-size: 14px;
    }
    </style>
""", unsafe_allow_html=True)

# --- 4. CALCULATION ENGINE ---
def calculate_unit(u_id, gen, hr, hr_yest, inputs):
    # GMR Kamalanga 350MW Design Defaults
    DESIGN_HR = 2250 
    TARGET_HR = 2300 # PAT Target
    COAL_GCV = 3600
    
    # 1. Financials (Daily)
    # Energy Saved = (Target - Actual) * Gen * 10^6
    kcal_diff = (TARGET_HR - hr) * gen * 1_000_000
    
    # PAT ESCerts: 1 ESCert = 10 Million kcal
    escerts = kcal_diff / 10_000_000
    
    # Carbon: Coal Saved = kcal_diff / GCV
    coal_saved_kg = kcal_diff / COAL_GCV
    carbon_credits = (coal_saved_kg / 1000) * 1.7 # 1.7 tCO2/tCoal
    
    # Trees: 1 Mature Tree = 25kg CO2/year
    trees_equiv = abs(carbon_credits * 1000 / 25)
    
    # Money (Approx Prices)
    profit = (escerts * 1000) + (carbon_credits * 500) + (coal_saved_kg * 4.5)
    
    # 2. Comparison (Yesterday)
    hr_delta = hr - hr_yest # Positive means HR increased (Bad)
    
    # 3. Technical Losses (For 5S Score)
    # 5S Score = 100 - (Total Penalties / Scaling Factor)
    loss_vac = max(0, (inputs['vac'] - (-0.92)) / 0.01 * 15) * -1 # deviation from -0.92
    loss_ms = max(0, (540 - inputs['ms']) * 1.0)
    loss_fg = max(0, (inputs['fg'] - 130) * 1.0)
    loss_unaccounted = max(0, hr - (DESIGN_HR + loss_ms + loss_fg + 10))
    
    score_5s = max(0, 100 - ((loss_vac + loss_ms + loss_fg + loss_unaccounted)/2))
    
    return {
        "id": u_id, "profit": profit, "hr": hr, "hr_delta": hr_delta,
        "escerts": escerts, "carbon": carbon_credits, "trees": trees_equiv,
        "score_5s": score_5s,
        "losses": {"Vacuum": loss_vac, "MS Temp": loss_ms, "Flue Gas": loss_fg, "Unaccounted": loss_unaccounted}
    }

# --- 5. SIDEBAR INPUTS (The Control Panel) ---
with st.sidebar:
    st.header("⚙️ GMR Control Panel")
    
    with st.tabs(["📝 Today", "⏮️ Yesterday", "🔧 Config"]):
        
        with st.tab("📝 Today"):
            st.markdown("### Unit 1 (350 MW)")
            u1_gen = st.number_input("U1 Gen (MU)", 0.0, 10.0, 8.4)
            u1_hr = st.number_input("U1 HR (kcal)", 2000, 3000, 2380)
            u1_vac = st.slider("U1 Vac", -0.80, -0.95, -0.90)
            
            st.markdown("---")
            st.markdown("### Unit 2 (350 MW)")
            u2_gen = st.number_input("U2 Gen (MU)", 0.0, 10.0, 8.2)
            u2_hr = st.number_input("U2 HR (kcal)", 2000, 3000, 2310)
            u2_vac = st.slider("U2 Vac", -0.80, -0.95, -0.92)

            st.markdown("---")
            st.markdown("### Unit 3 (350 MW)")
            u3_gen = st.number_input("U3 Gen (MU)", 0.0, 10.0, 8.5)
            u3_hr = st.number_input("U3 HR (kcal)", 2000, 3000, 2290)
            u3_vac = st.slider("U3 Vac", -0.80, -0.95, -0.93)

        with st.tab("⏮️ Yesterday"):
            st.caption("Used to calculate daily gain/loss trends")
            u1_hr_y = st.number_input("U1 Yest HR", 2370)
            u2_hr_y = st.number_input("U2 Yest HR", 2320)
            u3_hr_y = st.number_input("U3 Yest HR", 2300)

        with st.tab("🔧 Config"):
            st.text_input("Plant Name", "GMR Kamalanga")
            target_hr = st.number_input("PAT Target HR", 2300)

# --- 6. DATA PROCESSING ---
# We use dummy values for temp/fg to simplify the demo, but logic handles them
u1 = calculate_unit("1", u1_gen, u1_hr, u1_hr_y, {'vac': u1_vac, 'ms': 535, 'fg': 135})
u2 = calculate_unit("2", u2_gen, u2_hr, u2_hr_y, {'vac': u2_vac, 'ms': 538, 'fg': 132})
u3 = calculate_unit("3", u3_gen, u3_hr, u3_hr_y, {'vac': u3_vac, 'ms': 540, 'fg': 130})

units = [u1, u2, u3]
fleet_profit = sum(u['profit'] for u in units)
worst_unit = min(units, key=lambda x: x['profit'])

# --- 7. MAIN DASHBOARD ---

# HEADER
st.title("🏭 GMR Kamalanga 5S Eco-Command")
st.markdown(f"**Fleet Status:** {'✅ Profitable' if fleet_profit > 0 else '🔥 Loss Making'} | **Total Daily P&L:** ₹ {fleet_profit:,.0f}")

st.divider()

# SECTION A: THE WAR ROOM (3 Units Summary)
cols = st.columns(3)
for i, u in enumerate(units):
    # Scene Logic
    if u['profit'] > 0:
        border = "scene-good"
        color = "#00ff88"
        icon = "🟢"
    else:
        border = "scene-bad"
        color = "#ff3333"
        icon = "🔴"
        
    # Delta Logic
    if u['hr_delta'] < 0: # HR Dropped (Good)
        delta_str = f"▼ {abs(u['hr_delta'])} kcal (Improved)"
        d_class = "delta-pos"
    else:
        delta_str = f"▲ {abs(u['hr_delta'])} kcal (Degraded)"
        d_class = "delta-neg"

    with cols[i]:
        st.markdown(f"""
        <div class="unit-card {border}">
            <h3 style="margin:0; color:#aaa">UNIT - {u['id']}</h3>
            <div class="big-money" style="color:{color}">₹ {u['profit']:,.0f}</div>
            <p style="margin:5px 0 0 0; font-size:14px;">HR: <b>{u['hr']}</b> <span class="{d_class}">({delta_str})</span></p>
            <p style="font-size:12px; color:#666;">5S Score: {u['score_5s']:.1f}</p>
        </div>
        """, unsafe_allow_html=True)

# SECTION B: DEEP DIVE (Worst Unit Focus)
st.markdown("### ")
st.subheader(f"⚠️ Priority Focus: Unit {worst_unit['id']} Analysis")

t_impact, t_root = st.columns([1, 1])

with t_impact:
    st.markdown("#### 🌳 Environmental & Financial Impact")
    
    # Emotional Animation (Happy vs Sad)
    if worst_unit['profit'] > 0:
        if anim_tree_happy: st_lottie(anim_tree_happy, height=200, key="happy")
        msg_title = "Excellent Performance!"
        msg_body = f"Unit {worst_unit['id']} is saving the planet."
        msg_color = "success"
    else:
        if anim_smoke: st_lottie(anim_smoke, height=200, key="sad")
        msg_title = "Critical Emissions!"
        msg_body = f"Unit {worst_unit['id']} is bleeding efficiency."
        msg_color = "error"
        
    # Placards (The Calculation Explanations)
    with st.expander("ℹ️ See Calculation Logic (Placards)", expanded=True):
        st.markdown(f"""
        <div class="fact-box">
            <b>📜 PAT ESCerts:</b> {worst_unit['escerts']:.2f}<br>
            <i>Logic:</i> (Target - Actual) × Gen / 10 Million kcal
        </div>
        <div class="fact-box">
            <b>🌫️ Carbon Credits:</b> {worst_unit['carbon']:.2f} Tons<br>
            <i>Logic:</i> Coal Saved × 1.7 (Emission Factor)
        </div>
        <div class="fact-box">
            <b>🌲 Tree Equivalent:</b> {worst_unit['trees']:,.0f} Mature Trees<br>
            <i>Logic:</i> Excess CO2 / 0.025 Tons (Absorption per tree/year)
        </div>
        """, unsafe_allow_html=True)

with t_root:
    st.markdown("#### 🔧 Root Cause (Loss Pareto)")
    
    # Sort losses for Pareto
    loss_df = pd.DataFrame(list(worst_unit['losses'].items()), columns=['Param', 'Val'])
    loss_df = loss_df.sort_values('Val', ascending=True)
    
    # Chart
    fig = px.bar(loss_df, x='Val', y='Param', orientation='h', text='Val',
                 color='Val', color_continuous_scale=['#444', '#ff3333'])
    fig.update_layout(
        template="plotly_dark", 
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(0,0,0,0)',
        height=300,
        title="kcal/kWh Loss Breakdown"
    )
    st.plotly_chart(fig, use_container_width=True)
    
    # Action Plan
    top_loss = loss_df.iloc[-1]['Param']
    st.error(f"**ACTION REQUIRED:** High losses in **{top_loss}**. Initiate 5S cleaning/maintenance immediately.")

# SECTION C: THE PLAYGROUND & HISTORY (Tabs)
st.divider()
tab1, tab2, tab3 = st.tabs(["📈 History & Trends", "🎮 What-If Simulator", "📚 5S Knowledge"])

with tab1:
    st.markdown("### 📅 30-Day Performance Trend")
    # Mock Data Generator
    dates = pd.date_range(end=datetime.now(), periods=30)
    mock_data = pd.DataFrame({
        "Date": dates,
        "Heat Rate": np.linspace(2400, 2300, 30) + np.random.normal(0, 10, 30),
        "Profit": np.linspace(-50000, 50000, 30)
    })
    
    c1, c2 = st.columns(2)
    with c1:
        st.markdown("**Station Heat Rate Trend**")
        fig_hr = px.line(mock_data, x="Date", y="Heat Rate", markers=True, template="plotly_dark")
        fig_hr.add_hline(y=2300, line_dash="dash", line_color="green", annotation_text="Target")
        st.plotly_chart(fig_hr, use_container_width=True)
    with c2:
        st.markdown("**Financial Gain/Loss Trend**")
        fig_p = px.bar(mock_data, x="Date", y="Profit", color="Profit", 
                      color_continuous_scale=["red", "green"], template="plotly_dark")
        st.plotly_chart(fig_p, use_container_width=True)

with tab2:
    st.markdown("### 🎮 Operator Playground")
    st.caption("Adjust parameters to see potential savings (Interactive)")
    
    col_sim1, col_sim2 = st.columns([1, 2])
    with col_sim1:
        sim_vac = st.slider("Improve Vacuum to:", -0.85, -0.96, -0.92)
        sim_ms = st.slider("Improve MS Temp to:", 525, 545, 540)
    
    with col_sim2:
        # Simple Simulator Logic
        # Vacuum: 0.01 = 15 kcal | MS Temp: 1 deg = 1 kcal
        # Base is current Worst Unit
        current_hr = worst_unit['hr']
        # Calculate simulated HR
        # Current Vac/Temp from inputs (simplified for demo)
        base_vac = -0.90
        base_ms = 535
        
        gain_vac = (abs(sim_vac) - abs(base_vac)) / 0.01 * 15
        gain_ms = (sim_ms - base_ms) * 1.0
        
        sim_hr = current_hr - gain_vac - gain_ms
        sim_savings = (current_hr - sim_hr) * 8.4 * 1000000 / 3600 * 4.5 # Rs
        
        st.metric("Simulated New Heat Rate", f"{sim_hr:.0f} kcal/kWh")
        st.markdown(f"### Potential Daily Savings: :green[₹ {max(0, sim_savings):,.0f}]")
        if anim_money: st_lottie(anim_money, height=150, key="sim_money")

with tab3:
    st.markdown("### 📚 Reference Data (GMR Kamalanga)")
    [attachment_0](attachment)
    st.markdown("""
    * **Capacity:** 3 x 350 MW
    * **Boiler:** Sub-Critical, Pulverized Coal
    * **5S Focus Areas:**
        1.  **Vacuum:** Condenser tube cleaning (Shine).
        2.  **Combustion:** Mill fineness & burner tilt (Standardize).
        3.  **Isolation:** Drain passing checks (Sustain).
    """)
