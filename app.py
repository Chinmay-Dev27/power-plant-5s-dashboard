import streamlit as st
import plotly.graph_objects as go
import plotly.express as px
import pandas as pd
from datetime import datetime

# --- 1. CONFIGURATION & CSS ---
st.set_page_config(page_title="Fleet Command: 5S & Efficiency", layout="wide", page_icon="⚡")

st.markdown("""
    <style>
    .block-container { padding-top: 1rem; padding-bottom: 2rem; }
    
    /* UNIT CARD STYLING */
    .unit-card {
        background-color: #0e1117;
        border: 1px solid #30363d;
        border-radius: 8px;
        padding: 15px;
        text-align: center;
        transition: all 0.3s ease;
        height: 100%;
    }
    
    /* SCENE STATES */
    .scene-critical { border-top: 5px solid #ff3333; box-shadow: 0 4px 20px rgba(255, 51, 51, 0.1); }
    .scene-risk { border-top: 5px solid #ffb000; }
    .scene-acceptable { border-top: 5px solid #00ccff; }
    .scene-excellent { border-top: 5px solid #00ff88; box-shadow: 0 4px 20px rgba(0, 255, 136, 0.1); }

    /* METRICS */
    .metric-title { font-size: 16px; color: #8b949e; letter-spacing: 1px; font-weight: 600; margin-bottom: 10px; }
    .metric-value { font-size: 32px; font-weight: 700; margin: 0; }
    .metric-sub { font-size: 13px; color: #8b949e; margin-top: 5px; }
    
    /* ANIMATIONS (CSS Only - No Lottie Loops) */
    @keyframes flash-red { 
        0% { background-color: #0e1117; } 50% { background-color: #3b0e0e; } 100% { background-color: #0e1117; } 
    }
    .anim-critical { animation: flash-red 1s ease-in-out 1; }
    
    </style>
""", unsafe_allow_html=True)

# --- 2. LOGIC ENGINE (Now supports 3 Units) ---

def calculate_unit_performance(u_id, gen_mu, act_hr, inputs):
    """
    Calculates Financials, ESCerts, Carbon, and 5S Score for a single unit.
    """
    # 1. CONSTANTS (Design Data)
    DESIGN_HR = 2250
    TARGET_HR = 2350
    DESIGN_MS = 540
    DESIGN_VAC = -0.92
    DESIGN_FG = 130
    COAL_GCV = 3600
    
    # 2. TECHNICAL LOSS CALCULATION (For 5S Score)
    # Unpack specific parameters for this unit
    ms_temp = inputs.get('ms', 535)
    vacuum = inputs.get('vac', -0.90)
    fg_temp = inputs.get('fg', 135)
    spray = inputs.get('spray', 15)
    
    # Loss Logic
    loss_ms = max(0, (DESIGN_MS - ms_temp) * 1.2)
    loss_vac = max(0, ((vacuum - DESIGN_VAC) / 0.01) * 18) if vacuum > DESIGN_VAC else 0
    loss_fg = max(0, (fg_temp - DESIGN_FG) * 1.5)
    loss_spray = spray * 2.0
    
    # Unaccounted (The difference between calculated losses and actual input HR)
    theoretical_hr = DESIGN_HR + loss_ms + loss_vac + loss_fg + loss_spray + 50
    loss_unaccounted = max(0, act_hr - theoretical_hr)
    
    # 5S Score Formula (100 - weighted losses)
    # We penalize Unaccounted loss heavily as it implies poor housekeeping/leaks
    total_penalty = (loss_ms + loss_vac + loss_fg + loss_spray + (loss_unaccounted * 1.5))
    score_5s = max(0, 100 - (total_penalty / 3))

    # 3. REGULATORY CALCULATION (Carbon & ESCerts)
    gross_gen_units = gen_mu * 1_000_000
    hr_diff = TARGET_HR - act_hr
    kcal_saved = hr_diff * gross_gen_units
    
    # PAT (1 ESCert = 10 Gcal)
    escerts = kcal_saved / 10_000_000
    
    # Carbon
    coal_saved_kg = kcal_saved / COAL_GCV if COAL_GCV > 0 else 0
    carbon_credits = (coal_saved_kg / 1000) * 1.7 # 1.7 tCO2/tCoal
    
    # 4. FINANCIALS
    # Prices
    P_ESC = 1000
    P_CARB = 500
    P_COAL = 4500/1000 # Rs/kg
    
    profit = (escerts * P_ESC) + (carbon_credits * P_CARB) + (coal_saved_kg * P_COAL)
    
    return {
        "id": u_id,
        "profit": profit,
        "hr_act": act_hr,
        "hr_delta": act_hr - TARGET_HR,
        "score_5s": score_5s,
        "escerts": escerts,
        "carbon": carbon_credits,
        "losses": {
            "Vacuum": loss_vac, "MS Temp": loss_ms, "Flue Gas": loss_fg, 
            "Spray": loss_spray, "Unaccounted": loss_unaccounted
        }
    }

def get_scene(profit):
    if profit > 50000: return "EXCELLENT", "#00ff88", "scene-excellent"
    elif profit >= 0: return "ACCEPTABLE", "#00ccff", "scene-acceptable"
    elif profit >= -25000: return "RISK", "#ffb000", "scene-risk"
    else: return "CRITICAL", "#ff3333", "scene-critical"

# --- 3. SIDEBAR (PRESENTER INPUTS) ---
with st.sidebar:
    st.header("🔒 Presenter Mode")
    EXEC_MODE = st.toggle("🎙️ Executive View", True)
    
    st.divider()
    st.caption("Live Data Injection")
    
    # UNIT 6 INPUTS
    with st.expander("Unit 6 Parameters", expanded=True):
        u6_gen = st.number_input("U6 Gen (MU)", 12.0)
        u6_hr = st.number_input("U6 HR (kcal)", 2410.0) # High HR
        u6_vac = st.number_input("U6 Vac", -0.88) # Poor Vac
    
    # UNIT 7 INPUTS
    with st.expander("Unit 7 Parameters", expanded=False):
        u7_gen = st.number_input("U7 Gen (MU)", 11.8)
        u7_hr = st.number_input("U7 HR (kcal)", 2345.0) # Good HR
        u7_vac = st.number_input("U7 Vac", -0.92)

    # UNIT 8 INPUTS
    with st.expander("Unit 8 Parameters", expanded=False):
        u8_gen = st.number_input("U8 Gen (MU)", 12.2)
        u8_hr = st.number_input("U8 HR (kcal)", 2330.0) # Excellent HR
        u8_vac = st.number_input("U8 Vac", -0.93)

# --- 4. PROCESSING ---
# Pack inputs
u6_data = calculate_unit_performance("6", u6_gen, u6_hr, {'vac': u6_vac})
u7_data = calculate_unit_performance("7", u7_gen, u7_hr, {'vac': u7_vac})
u8_data = calculate_unit_performance("8", u8_gen, u8_hr, {'vac': u8_vac})

units = [u6_data, u7_data, u8_data]

# Find Worst Unit
worst_unit = min(units, key=lambda x: x['profit'])
best_unit = max(units, key=lambda x: x['profit'])

# --- 5. VISUAL LAYOUT ---

# HEADER
c1, c2 = st.columns([6, 1])
with c1:
    st.title("🏭 Fleet Performance Command")
    st.caption(f"Real-time Review | Focus: {worst_unit['id']} | Last Update: {datetime.now().strftime('%H:%M')}")
with c2:
    # Aggregated Fleet Profit
    fleet_total = sum(u['profit'] for u in units)
    color = "#00ff88" if fleet_total >= 0 else "#ff3333"
    st.markdown(f"<h3 style='color:{color}; text-align:right'>₹ {fleet_total:,.0f}</h3>", unsafe_allow_html=True)
    st.markdown("<p style='text-align:right; color:#666'>Fleet Net P&L</p>", unsafe_allow_html=True)

st.divider()

# A. UNIT SUMMARY ROW (Status First)
cols = st.columns(3)
for i, u in enumerate(units):
    state, color, css = get_scene(u['profit'])
    
    # Animation Trigger (CSS)
    anim = "anim-critical" if state == "CRITICAL" and EXEC_MODE else ""
    
    with cols[i]:
        st.markdown(f"""
        <div class="unit-card {css} {anim}">
            <div class="metric-title">UNIT – {u['id']}</div>
            <div class="metric-value" style="color:{color}">₹ {u['profit']:,.0f}</div>
            <div class="metric-sub">
                HR: {u['hr_act']:.0f} <span style="color:#666">({u['hr_delta']:+.0f})</span>
            </div>
            <div class="metric-sub" style="margin-top:10px; border-top:1px solid #333; padding-top:5px;">
                5S Score: <b>{u['score_5s']:.1f}</b> | ESCerts: <b>{u['escerts']:.1f}</b>
            </div>
        </div>
        """, unsafe_allow_html=True)

# B. PRIORITY FOCUS SECTION (Auto-Selected)
st.markdown("### ") # Spacer
st.markdown(f"### 🔴 Priority Drill-Down: UNIT–{worst_unit['id']}")

# Create 2 Columns: Root Cause Chart | Regulatory & 5S Impact
drill_c1, drill_c2 = st.columns([2, 1])

with drill_c1:
    st.markdown("#### 📉 Efficiency Deviation Profile")
    # Prepare Data for Chart
    loss_data = pd.DataFrame(list(worst_unit['losses'].items()), columns=['Parameter', 'Loss'])
    loss_data = loss_data.sort_values('Loss', ascending=True) # Sort for bar chart
    
    # Highlight the biggest bar
    colors = ['#333'] * len(loss_data)
    colors[-1] = '#ff3333' # Make the biggest loss RED
    
    fig = px.bar(
        loss_data, x="Loss", y="Parameter", orientation='h', text="Loss",
        color_discrete_sequence=['#ff3333']
    )
    fig.update_traces(marker_color=colors, texttemplate='%{text:.0f}', textposition='outside')
    fig.update_layout(
        plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)',
        font_color='white', height=320, 
        xaxis_title="Heat Rate Loss (kcal/kWh)", yaxis_title=None,
        xaxis=dict(showgrid=False), margin=dict(l=0, r=0, t=20, b=0)
    )
    st.plotly_chart(fig, use_container_width=True, config={'displayModeBar': False})

with drill_c2:
    st.markdown("#### 🌍 Regulatory & 5S Impact")
    
    # 1. 5S Score Card (with context)
    score = worst_unit['score_5s']
    s_color = "#00ff88" if score > 80 else "#ff3333"
    st.markdown(f"""
    <div style="background:#161b22; padding:15px; border-radius:5px; border-left:4px solid {s_color}; margin-bottom:10px;">
        <span style="color:#8b949e; font-size:12px;">AUTO-5S SCORE</span><br>
        <span style="font-size:24px; font-weight:bold; color:{s_color}">{score:.1f} / 100</span>
    </div>
    """, unsafe_allow_html=True)
    
    # 2. ESCerts & Carbon Grid
    g1, g2 = st.columns(2)
    with g1:
        st.metric("PAT ESCerts", f"{worst_unit['escerts']:.1f}", delta_color="normal")
    with g2:
        st.metric("Carbon Credits", f"{worst_unit['carbon']:.1f}", delta_color="normal")
        
    # 3. Action Recommendation
    top_loss_param = loss_data.iloc[-1]['Parameter']
    st.error(f"⚠️ **ACTION:** High losses in **{top_loss_param}**. Immediate {top_loss_param} system audit required.")

# --- 6. FOOTER ---
if not EXEC_MODE:
    st.divider()
    st.json(worst_unit) # Debug view
