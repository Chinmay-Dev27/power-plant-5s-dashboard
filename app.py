import streamlit as st
import plotly.graph_objects as go
import plotly.express as px
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import requests
from streamlit_lottie import st_lottie

# --- 1. CONFIGURATION & CSS ---
st.set_page_config(page_title="5S Eco-Exhibition", layout="wide", page_icon="🌿")

# --- 2. ASSETS & ANIMATIONS ---
def load_lottieurl(url):
    try:
        r = requests.get(url, timeout=2)
        return r.json() if r.status_code == 200 else None
    except: return None

# Load Animations (Robust)
anim_tree = load_lottieurl("https://lottie.host/6e35574d-8651-477d-b570-56965c276b3b/22572535-373f-42a9-823c-99e582862594.json")
anim_factory = load_lottieurl("https://lottie.host/575a66c6-1215-4688-9189-b57579621379/10839556-9141-4712-a89e-224429715783.json")
anim_money = load_lottieurl("https://lottie.host/02008323-2895-4673-863a-4934e402802d/41838634-11d9-430c-992a-356c92d529d3.json")

st.markdown("""
    <style>
    /* Global Styling */
    .stApp { background: linear-gradient(to bottom, #0e1117, #161b22); }
    .block-container { padding-top: 1rem; padding-bottom: 3rem; }
    
    /* CARDS */
    .metric-card {
        background: rgba(255, 255, 255, 0.05);
        border: 1px solid rgba(255, 255, 255, 0.1);
        border-radius: 10px;
        padding: 15px;
        text-align: center;
        backdrop-filter: blur(5px);
    }
    .scene-good { border-top: 4px solid #00ff88; }
    .scene-bad { border-top: 4px solid #ff3333; }
    
    /* TEXT */
    .big-stat { font-size: 32px; font-weight: 700; margin: 0; }
    .sub-stat { font-size: 14px; color: #aaa; }
    
    /* TABS */
    .stTabs [data-baseweb="tab-list"] { gap: 20px; }
    .stTabs [data-baseweb="tab"] {
        height: 50px;
        white-space: pre-wrap;
        background-color: #1c2128;
        border-radius: 5px;
        color: white;
        font-size: 16px;
    }
    .stTabs [aria-selected="true"] {
        background-color: #00ff88;
        color: black;
        font-weight: bold;
    }
    </style>
""", unsafe_allow_html=True)

# --- 3. DATA GENERATOR (Mock History for Trends) ---
@st.cache_data
def get_mock_history():
    dates = pd.date_range(end=datetime.now(), periods=30).tolist()
    data = []
    base_hr = 2380
    for d in dates:
        # Simulate improvement over time
        noise = np.random.randint(-20, 20)
        trend = -1 * (dates.index(d)) # Slow improvement
        hr = base_hr + noise + trend
        
        # Calculate derived metrics
        escerts = (2350 - hr) * 12 * 1_000_000 / 10_000_000
        profit = escerts * 1000 + (np.random.randint(-5000, 5000))
        
        data.append({"Date": d, "Heat Rate": hr, "Profit": profit, "ESCerts": escerts})
    return pd.DataFrame(data)

df_hist = get_mock_history()

# --- 4. CALCULATION ENGINE ---
def calculate_single_unit(u_id, gen, hr, inputs):
    # Constants
    TARGET_HR = 2350
    DESIGN_HR = 2250
    COAL_GCV = 3600
    
    # Financials
    kcal_diff = (TARGET_HR - hr) * gen * 1_000_000
    escerts = kcal_diff / 10_000_000
    coal_saved_kg = kcal_diff / COAL_GCV
    carbon = (coal_saved_kg / 1000) * 1.7
    profit = (escerts * 1000) + (carbon * 500) + (coal_saved_kg * 4.5)
    
    # Technical Loss (Simplified for display)
    loss_vac = max(0, (inputs['vac'] - (-0.92)) / 0.01 * 18) * -1
    loss_ms = max(0, (540 - inputs['ms']) * 1.2)
    
    return {
        "id": u_id, "profit": profit, "hr": hr, "escerts": escerts, "carbon": carbon,
        "losses": {"Vacuum": loss_vac, "MS Temp": loss_ms, "Spray": 5, "Unaccounted": 10}
    }

# --- 5. SIDEBAR ---
with st.sidebar:
    st.image("https://cdn-icons-png.flaticon.com/512/2933/2933886.png", width=50)
    st.header("Exhibition Controls")
    
    st.markdown("### 🎛️ Live Unit Inputs")
    u6_hr = st.slider("Unit-6 Heat Rate", 2200, 2600, 2410)
    u7_hr = st.slider("Unit-7 Heat Rate", 2200, 2600, 2345)
    u8_hr = st.slider("Unit-8 Heat Rate", 2200, 2600, 2330)

# Process Data
u6 = calculate_single_unit("6", 12.0, u6_hr, {'vac': -0.88, 'ms': 530})
u7 = calculate_single_unit("7", 11.8, u7_hr, {'vac': -0.92, 'ms': 538})
u8 = calculate_single_unit("8", 12.2, u8_hr, {'vac': -0.93, 'ms': 540})
units = [u6, u7, u8]
fleet_profit = sum(u['profit'] for u in units)

# --- 6. MAIN TABS ---
t_main, t_trends, t_sim, t_learn, t_gallery = st.tabs([
    "🏭 Fleet Command", "📈 History & Trends", "🎮 What-If Simulator", "📚 Knowledge Bank", "🏆 5S Gallery"
])

# --- TAB 1: FLEET COMMAND (The CXO View) ---
with t_main:
    st.markdown(f"### ⚡ Real-Time Fleet Status")
    
    # Top Summary
    c1, c2, c3 = st.columns(3)
    c1.metric("Fleet Net Profit (Daily)", f"₹ {fleet_total:,.0f}", delta_color="normal")
    c2.metric("Total Carbon Avoided", f"{sum(u['carbon'] for u in units):,.1f} Tons", "vs Baseline")
    c3.metric("Fleet Avg Heat Rate", f"{int((u6_hr+u7_hr+u8_hr)/3)} kcal/kWh")
    
    st.divider()
    
    # 3-Unit Cards
    cols = st.columns(3)
    for i, u in enumerate(units):
        color = "#00ff88" if u['profit'] > 0 else "#ff3333"
        border = "scene-good" if u['profit'] > 0 else "scene-bad"
        
        with cols[i]:
            st.markdown(f"""
            <div class="metric-card {border}">
                <div class="sub-stat">UNIT - {u['id']}</div>
                <div class="big-stat" style="color:{color}">₹ {u['profit']:,.0f}</div>
                <div class="sub-stat">HR: {u['hr']} | ESCerts: {u['escerts']:.1f}</div>
            </div>
            """, unsafe_allow_html=True)
            
            # Mini Graph for each unit
            fig_mini = go.Figure(go.Indicator(
                mode="gauge+number", value=u['hr'],
                gauge={'axis': {'range': [2200, 2500]}, 'bar': {'color': color}}
            ))
            fig_mini.update_layout(height=120, margin=dict(l=20,r=20,t=0,b=0), paper_bgcolor='rgba(0,0,0,0)')
            st.plotly_chart(fig_mini, use_container_width=True)

# --- TAB 2: HISTORY & TRENDS ---
with t_trends:
    st.markdown("### 📅 Performance Over Last 30 Days")
    
    # Interactive Plotly Charts
    c1, c2 = st.columns(2)
    with c1:
        st.markdown("**Heat Rate Improvement Trend**")
        fig_hr = px.line(df_hist, x="Date", y="Heat Rate", markers=True, template="plotly_dark")
        fig_hr.add_hline(y=2350, line_dash="dash", line_color="green", annotation_text="Target")
        st.plotly_chart(fig_hr, use_container_width=True)
        
    with c2:
        st.markdown("**Financial Gains (Cumulative)**")
        df_hist['CumProfit'] = df_hist['Profit'].cumsum()
        fig_prof = px.area(df_hist, x="Date", y="CumProfit", template="plotly_dark", color_discrete_sequence=['#00ff88'])
        st.plotly_chart(fig_prof, use_container_width=True)

# --- TAB 3: WHAT-IF SIMULATOR (Interactive) ---
with t_sim:
    st.markdown("### 🎮 The Efficiency Playground")
    st.markdown("Adjust the sliders to see how much money you *could* save.")
    
    col_in, col_out = st.columns([1, 2])
    
    with col_in:
        st.markdown("#### 🔧 Adjust Parameters")
        sim_vac = st.slider("Improve Vacuum (kg/cm2)", -0.80, -0.95, -0.90)
        sim_ms = st.slider("Improve MS Temp (°C)", 520, 545, 535)
        sim_gen = st.slider("Unit Load (MW)", 300, 600, 500)
    
    with col_out:
        # Simulation Math
        base_hr = 2400
        # Vacuum gain: 0.01 = 18 kcal
        gain_vac = (sim_vac - (-0.80)) / 0.01 * 18 * -1
        # MS Temp gain: 1 deg = 1.2 kcal
        gain_ms = (sim_ms - 520) * 1.2
        
        new_hr = base_hr - gain_ms + gain_vac # Simplified logic
        savings_kwh = (2400 - new_hr) * (sim_gen * 24 * 1000) / 3600 # kg coal approx
        money_saved = savings_kwh * 4.5
        
        st.markdown(f"""
        <div style="background:#1c2128; padding:20px; border-radius:10px; text-align:center;">
            <h2>Potential Daily Savings</h2>
            <h1 style="color:#00ff88; font-size:60px;">₹ {abs(money_saved):,.0f}</h1>
            <p>By optimizing Vacuum to {sim_vac} and Temp to {sim_ms}</p>
        </div>
        """, unsafe_allow_html=True)
        
        if anim_money: st_lottie(anim_money, height=200)

# --- TAB 4: KNOWLEDGE BANK (Educational) ---
with t_learn:
    c1, c2 = st.columns(2)
    
    with c1:
        st.markdown("### 📚 What is PAT Scheme?")
        st.info("""
        **PAT (Perform, Achieve and Trade)** is a regulatory instrument by the Bureau of Energy Efficiency (BEE).
        
        * **Currency:** ESCert (Energy Saving Certificate)
        * **Value:** 1 ESCert = 1 MTOE (Metric Tonne of Oil Equivalent)
        * **Conversion:** 1 MTOE = **10 Million kCal**
        """)
        st.markdown("[🔗 Visit BEE India Official Site](https://beeindia.gov.in/)")
        
        st.markdown("### 🌍 Carbon Credit Logic")
        st.markdown("""
        * **Coal CO2:** Indian coal emits ~1.7 Tons of CO2 per Ton burned.
        * **Tree Equivalent:** A mature tree absorbs ~25kg CO2/year.
        * **Formula:** `Coal Saved (Tons) * 1.7 = Carbon Credits`
        """)

    with c2:
        st.markdown("### 🧹 5S in Thermal Plants")
        
        st.markdown("""
        1.  **Sort (Seiri):** Remove scrap metal from boiler floors.
        2.  **Set in Order (Seiton):** Label all valves and drains clearly.
        3.  **Shine (Seiso):** Clean condenser tubes (Improves Vacuum!).
        4.  **Standardize (Seiketsu):** Daily checklists for soot blowing.
        5.  **Sustain (Shitsuke):** Weekly audits and rewards.
        """)
        if anim_tree: st_lottie(anim_tree, height=200)

# --- TAB 5: 5S GALLERY (Visuals) ---
with t_gallery:
    st.markdown("### 📸 5S Transformation Gallery")
    
    gc1, gc2, gc3 = st.columns(3)
    with gc1:
        st.image("https://via.placeholder.com/300x200?text=Before+5S", caption="Cluttered Boiler Floor")
    with gc2:
        st.markdown("## ➡️ TRANSFORMED ➡️")
    with gc3:
        st.image("https://via.placeholder.com/300x200/00ff88/000000?text=After+5S", caption="Clean & Labelled Floor")
    
    st.success("Cleanliness directly improves safety and reduces maintenance downtime by 15%.")

# --- FOOTER ---
st.markdown("---")
st.caption("Designed for 5S Exhibition | Power Plant Efficiency Cell")
