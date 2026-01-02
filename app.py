import streamlit as st
import plotly.graph_objects as go
import plotly.express as px
import pandas as pd
from datetime import datetime
import time

# --- 1. CONFIGURATION & CSS (The "War Room" Look) ---
st.set_page_config(page_title="CXO Review: Thermal Fleet", layout="wide", page_icon="⚡")

st.markdown("""
    <style>
    /* Global Reset */
    .block-container { padding-top: 1rem; padding-bottom: 1rem; }
    
    /* UNIT CARD STYLING */
    .unit-card {
        background-color: #161b22;
        border: 1px solid #30363d;
        border-radius: 8px;
        padding: 15px;
        text-align: center;
        transition: all 0.3s ease;
    }
    
    /* SCENE STATES (Colors) */
    .scene-critical { border-left: 5px solid #ff3333; box-shadow: 0 0 10px rgba(255, 51, 51, 0.1); }
    .scene-risk { border-left: 5px solid #ffb000; }
    .scene-acceptable { border-left: 5px solid #00ccff; }
    .scene-excellent { border-left: 5px solid #00ff88; box-shadow: 0 0 10px rgba(0, 255, 136, 0.1); }

    /* METRICS */
    .metric-title { font-size: 14px; color: #8b949e; letter-spacing: 1px; text-transform: uppercase; }
    .metric-value { font-size: 28px; font-weight: 700; margin: 5px 0; }
    .metric-delta { font-size: 14px; font-weight: 500; }

    /* ANIMATIONS (CSS Only - No Lottie Loops) */
    @keyframes flash-red { 
        0% { background-color: #161b22; } 
        50% { background-color: #3b0e0e; } 
        100% { background-color: #161b22; } 
    }
    @keyframes flash-green { 
        0% { background-color: #161b22; } 
        50% { background-color: #0e2e1b; } 
        100% { background-color: #161b22; } 
    }
    
    .anim-critical { animation: flash-red 1s ease-in-out 1; }
    .anim-improve { animation: flash-green 1s ease-in-out 1; }

    </style>
""", unsafe_allow_html=True)

# --- 2. LOGIC ENGINE ---

# A. Normalization (KPIs)
def calculate_kpis(gross_gen, act_hr, design_hr):
    """Computes Normalized KPIs for Executive Comparison"""
    # Constants
    COAL_GCV = 3600
    COAL_PRICE = 4500 # Rs/Ton
    PAT_TARGET = design_hr + 50 # Example Target
    
    # 1. HR Delta
    hr_delta = act_hr - PAT_TARGET
    
    # 2. Financial Impact (Simplified for brevity)
    # Energy Loss = Delta HR * Gen * 1000
    # Coal Loss = Energy Loss / GCV
    # Money = Coal Loss * Price/1000
    if gross_gen > 0:
        kcal_loss = hr_delta * gross_gen * 1_000_000
        coal_loss_tons = kcal_loss / COAL_GCV
        profit = -1 * (coal_loss_tons * (COAL_PRICE/1000))
        # Add PAT/Carbon credits logic here if needed, keeping it raw P&L for now
    else:
        profit = 0
        
    # 3. Profit per MU (Normalized)
    profit_per_mu = profit / gross_gen if gross_gen > 0 else 0
    
    return profit, hr_delta, profit_per_mu

# B. SCENE Logic (State Machine)
def get_scene(profit):
    if profit > 100000: return "EXCELLENT", "#00ff88", "scene-excellent"
    elif profit >= 0: return "ACCEPTABLE", "#00ccff", "scene-acceptable"
    elif profit >= -50000: return "RISK", "#ffb000", "scene-risk"
    else: return "CRITICAL", "#ff3333", "scene-critical"

# --- 3. SIDEBAR (PRESENTER MODE ONLY) ---
with st.sidebar:
    st.header("🔒 Presenter Controls")
    EXEC_MODE = st.toggle("🎙️ Executive Mode", True)
    FREEZE = st.toggle("⏸ Freeze Screen", False)
    
    st.divider()
    
    # HIDDEN INPUTS (Simulating Live Data Feed)
    st.caption("Data Injection (Hidden in Call)")
    
    # Unit 6 Data
    u6_gen = st.number_input("U6 Gen (MU)", 12.0, key="u6g")
    u6_hr = st.number_input("U6 HR", 2420.0, key="u6h") # Critical
    
    # Unit 7 Data
    u7_gen = st.number_input("U7 Gen (MU)", 11.5, key="u7g")
    u7_hr = st.number_input("U7 HR", 2360.0, key="u7h") # Risk
    
    # Unit 8 Data
    u8_gen = st.number_input("U8 Gen (MU)", 12.2, key="u8g")
    u8_hr = st.number_input("U8 HR", 2340.0, key="u8h") # Acceptable

# --- 4. DATA PROCESSING (STOP IF FROZEN) ---
if FREEZE:
    st.warning("⚠️ SCREEN FROZEN FOR DISCUSSION")
    st.stop()

# Calculate States
# Target HR assumed 2350 for all
p6, d6, norm6 = calculate_kpis(u6_gen, u6_hr, 2350)
p7, d7, norm7 = calculate_kpis(u7_gen, u7_hr, 2350)
p8, d8, norm8 = calculate_kpis(u8_gen, u8_hr, 2350)

# Store History for Animation Triggers
if 'history' not in st.session_state:
    st.session_state.history = {'U6': "ACCEPTABLE", 'U7': "ACCEPTABLE", 'U8': "ACCEPTABLE"}

units = [
    {"id": "6", "profit": p6, "delta": d6, "norm": norm6, "prev": st.session_state.history['U6']},
    {"id": "7", "profit": p7, "delta": d7, "norm": norm7, "prev": st.session_state.history['U7']},
    {"id": "8", "profit": p8, "delta": d8, "norm": norm8, "prev": st.session_state.history['U8']},
]

# --- 5. VISUAL LAYER: SUMMARY ROW ---
st.title("🏭 Fleet Performance Review")

cols = st.columns(3)

worst_unit_id = None
min_profit = float('inf')

for i, u in enumerate(units):
    # Determine Current State
    state, color, css = get_scene(u['profit'])
    
    # Determine Animation Class (Strict Rule 5)
    anim_class = ""
    if EXEC_MODE:
        if state == "CRITICAL" and u['prev'] != "CRITICAL":
            anim_class = "anim-critical"
        elif u['prev'] == "RISK" and state == "ACCEPTABLE":
            anim_class = "anim-improve"
    
    # Update History
    st.session_state.history[f"U{u['id']}"] = state
    
    # Track Worst Unit
    if u['profit'] < min_profit:
        min_profit = u['profit']
        worst_unit_id = u['id']

    # Render Card
    with cols[i]:
        st.markdown(f"""
        <div class="unit-card {css} {anim_class}">
            <div class="metric-title">UNIT–{u['id']}</div>
            <div class="metric-value" style="color:{color}">₹ {u['profit']:,.0f}</div>
            <div class="metric-delta">HR Δ: {u['delta']:+.0f} | ₹/MU: {u['norm']:,.0f}</div>
            <div style="margin-top:10px; font-size:12px; color:#666;">STATUS: {state}</div>
        </div>
        """, unsafe_allow_html=True)

# --- 6. AUTO-SELECT WORST UNIT (Rule 6) ---
st.divider()

if worst_unit_id:
    # Header logic
    st.markdown(f"### 🔴 Priority Focus: UNIT–{worst_unit_id}")
    
    # Mock Root Cause Data (Dynamic based on selected worst unit)
    # In real app, this queries the specific unit's detailed tags
    c1, c2 = st.columns([2, 1])
    
    with c1:
        # Rule 7: Root Cause Chart - Ranked
        st.caption("DEVIATION PARETO (kcal/kWh Impact)")
        
        # Simulating data based on unit ID for demo
        data = {
            'Parameter': ['Condenser Vacuum', 'MS Temp', 'Unburnt Carbon', 'RH Spray', 'Aux Power'],
            'Loss (kcal)': [35, 12, 8, 5, 2] if worst_unit_id == "6" else [10, 40, 5, 5, 2]
        }
        df_loss = pd.DataFrame(data).sort_values("Loss (kcal)", ascending=True) # Ascending for horizontal bar to put largest top
        
        fig = px.bar(
            df_loss, 
            x="Loss (kcal)", 
            y="Parameter", 
            orientation='h',
            text="Loss (kcal)",
            color="Loss (kcal)",
            color_continuous_scale=['#444', '#ff3333'] # Dark to Red
        )
        fig.update_layout(
            paper_bgcolor='rgba(0,0,0,0)',
            plot_bgcolor='rgba(0,0,0,0)',
            font_color='white',
            height=300,
            margin=dict(l=0, r=0, t=0, b=0),
            xaxis=dict(showgrid=False),
            yaxis=dict(showgrid=False),
            showlegend=False
        )
        fig.update_traces(texttemplate='%{text:.0f}', textposition='outside')
        st.plotly_chart(fig, use_container_width=True, config={'displayModeBar': False})

    with c2:
        # Actionable Insight
        st.caption("SHIFT IN-CHARGE ACTION")
        top_loss = df_loss.iloc[-1]['Parameter'] # Last one is biggest in sorted list
        loss_val = df_loss.iloc[-1]['Loss (kcal)']
        
        st.error(f"**Primary Driver:** {top_loss}")
        st.markdown(f"""
        **Impact:** {loss_val} kcal/kWh deviation.
        
        **Immediate Action:**
        1. {"Check ejectors & air ingress" if "Vacuum" in top_loss else "Check burner tilt & mill fineness"}
        2. Verify sensor calibration.
        3. Review last 4 hours trend.
        """)

# --- 7. FOOTER (CONTEXT) ---
st.caption(f"Live Feed | Mode: {'EXECUTIVE' if EXEC_MODE else 'DEBUG'} | Last Update: {datetime.now().strftime('%H:%M:%S')}")
