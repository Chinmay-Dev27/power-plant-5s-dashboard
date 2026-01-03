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
st.set_page_config(page_title="GMR 5S Command", layout="wide", page_icon="⚡")

# --- 2. ASSETS ---
def load_lottieurl(url):
    try:
        r = requests.get(url, timeout=2)
        return r.json() if r.status_code == 200 else None
    except: return None

anim_tree = load_lottieurl("https://lottie.host/6e35574d-8651-477d-b570-56965c276b3b/22572535-373f-42a9-823c-99e582862594.json")
anim_smoke = load_lottieurl("https://lottie.host/575a66c6-1215-4688-9189-b57579621379/10839556-9141-4712-a89e-224429715783.json")

st.markdown("""
    <style>
    /* MAIN THEME */
    .stApp { background: linear-gradient(to bottom, #0e1117, #161b22); }
    
    /* GLASS CARDS */
    .glass-card {
        background: rgba(255, 255, 255, 0.05);
        backdrop-filter: blur(10px);
        border: 1px solid rgba(255, 255, 255, 0.1);
        border-radius: 12px;
        padding: 20px;
        margin-bottom: 15px;
        box-shadow: 0 4px 6px rgba(0,0,0,0.3);
        text-align: center;
    }
    
    /* SCENE COLORS */
    .border-good { border-top: 4px solid #00ff88; }
    .border-bad { border-top: 4px solid #ff3333; }
    .border-warn { border-top: 4px solid #ffb000; }
    
    /* PLACARDS */
    .placard {
        background: #1c2128; padding: 15px; border-radius: 8px; 
        margin-bottom: 10px; text-align: left;
    }
    .p-title { font-size: 11px; color: #aaa; text-transform: uppercase; letter-spacing: 1px;}
    .p-val { font-size: 24px; font-weight: bold; color: white; margin: 5px 0;}
    .p-sub { font-size: 12px; color: #888; }
    
    /* TEXT */
    .big-money { font-size: 32px; font-weight: 800; }
    .unit-header { font-size: 20px; font-weight: bold; border-bottom: 1px solid #333; padding-bottom: 10px; margin-bottom: 15px; color: white; }
    </style>
""", unsafe_allow_html=True)

# --- 3. CALCULATION ENGINE ---
def calculate_unit(u_id, gen, hr, inputs, design_vals):
    # Unpack Design Values Specific to Unit
    TARGET_HR = design_vals['target_hr']
    DESIGN_HR = 2250 # Fixed Design
    COAL_GCV = design_vals['gcv']
    LIMIT_SOX = design_vals['limit_sox']
    LIMIT_NOX = design_vals['limit_nox']
    
    # Financials
    # Energy Diff: Positive = Savings, Negative = Loss
    kcal_diff = (TARGET_HR - hr) * gen * 1_000_000
    
    escerts = kcal_diff / 10_000_000
    coal_saved_kg = kcal_diff / COAL_GCV
    carbon_tons = (coal_saved_kg / 1000) * 1.7
    
    # Money
    profit = (escerts * 1000) + (carbon_tons * 500) + (coal_saved_kg * 4.5)
    
    # Trees & Land Logic
    trees_count = abs(carbon_tons / 0.025)
    acres_land = trees_count / 500
    
    # 5S Technical Score
    l_vac = max(0, (inputs['vac'] - (-0.92)) / 0.01 * 18) * -1
    l_ms = max(0, (540 - inputs['ms']) * 1.2)
    l_fg = max(0, (inputs['fg'] - 130) * 1.5)
    l_spray = max(0, (inputs['spray'] - 15) * 2.0)
    theo_hr = DESIGN_HR + l_ms + l_fg + l_spray + 50 
    l_unacc = max(0, hr - theo_hr - abs(l_vac))
    
    total_pen = abs(l_vac) + l_ms + l_fg + l_spray + l_unacc
    score_5s = max(0, 100 - (total_pen / 3.0))
    
    return {
        "id": u_id, "gen": gen, "hr": hr, "profit": profit, 
        "escerts": escerts, "carbon": carbon_tons, 
        "trees": trees_count, "acres": acres_land,
        "score": score_5s, "sox": inputs['sox'], "nox": inputs['nox'],
        "limits": {'sox': LIMIT_SOX, 'nox': LIMIT_NOX},
        "losses": {"Vacuum": abs(l_vac), "MS Temp": l_ms, "Flue Gas": l_fg, "Spray": l_spray, "Unaccounted": l_unacc}
    }

# --- 4. SIDEBAR INPUTS ---
with st.sidebar:
    st.image("https://cdn-icons-png.flaticon.com/512/2933/2933886.png", width=50)
    st.title("Control Panel")
    
    tab_input, tab_config = st.tabs(["📝 Daily Data", "⚙️ Config"])
    
    # --- TAB: CONFIG (Limits & Refs) ---
    with tab_config:
        st.markdown("### 🌍 Emission Limits (Common)")
        lim_sox = st.number_input("SOx Limit (mg/Nm3)", value=600)
        lim_nox = st.number_input("NOx Limit (mg/Nm3)", value=450)
        
        st.markdown("### 🎯 Unit Targets")
        t_u1 = st.number_input("U1 Target HR", value=2300)
        g_u1 = st.number_input("U1 GCV", value=3600)
        st.divider()
        t_u2 = st.number_input("U2 Target HR", value=2310)
        g_u2 = st.number_input("U2 GCV", value=3550)
        st.divider()
        t_u3 = st.number_input("U3 Target HR", value=2295)
        g_u3 = st.number_input("U3 GCV", value=3620)

    # --- TAB: DAILY INPUTS ---
    with tab_input:
        units_data = []
        # Configurations mapping
        configs = [
            {'target_hr': t_u1, 'gcv': g_u1, 'limit_sox': lim_sox, 'limit_nox': lim_nox},
            {'target_hr': t_u2, 'gcv': g_u2, 'limit_sox': lim_sox, 'limit_nox': lim_nox},
            {'target_hr': t_u3, 'gcv': g_u3, 'limit_sox': lim_sox, 'limit_nox': lim_nox}
        ]
        
        for i in range(1, 4):
            with st.expander(f"Unit {i} Inputs", expanded=(i==1)):
                gen = st.number_input(f"U{i} Gen (MU)", 0.0, 12.0, 8.4, key=f"g{i}")
                hr = st.number_input(f"U{i} HR (kcal)", 2000, 3000, 2380 if i==1 else 2310, key=f"h{i}")
                
                st.markdown(f"**U{i} Parameters**")
                vac = st.slider(f"Vacuum", -0.80, -0.98, -0.90, key=f"v{i}") 
                ms = st.number_input(f"MS Temp", 500, 550, 535, key=f"m{i}")
                fg = st.number_input(f"FG Temp", 100, 160, 135, key=f"f{i}")
                spray = st.number_input(f"Spray", 0, 100, 20, key=f"s{i}")
                
                st.markdown(f"**U{i} Emissions**")
                sox = st.number_input(f"SOx", 0, 1000, 550 if i!=2 else 650, key=f"sx{i}")
                nox = st.number_input(f"NOx", 0, 1000, 400, key=f"nx{i}")
                
                units_data.append(calculate_unit(str(i), gen, hr, {'vac':vac, 'ms':ms, 'fg':fg, 'spray':spray, 'sox':sox, 'nox':nox}, configs[i-1]))

# Calculate Fleet Totals
fleet_profit = sum(u['profit'] for u in units_data)

# --- 5. MAIN PAGE LAYOUT ---
st.title("🏭 GMR Kamalanga Command Center")
st.markdown(f"**Fleet Status:** {'✅ Profitable' if fleet_profit > 0 else '🔥 Loss Making'} | **Net Daily P&L:** ₹ {fleet_profit:,.0f}")

# TABS NAVIGATION
tabs = st.tabs(["🏠 War Room", "UNIT-1 Detail", "UNIT-2 Detail", "UNIT-3 Detail", "📚 Info"])

# --- TAB 1: WAR ROOM (Executive View) ---
with tabs[0]:
    st.markdown("### 🚁 Fleet Executive Summary")
    st.divider()
    
    cols = st.columns(3)
    for i, u in enumerate(units_data):
        color = "#00ff88" if u['profit'] > 0 else "#ff3333"
        border = "border-good" if u['profit'] > 0 else "border-bad"
        
        with cols[i]:
            st.markdown(f"""
            <div class="glass-card {border}">
                <div class="unit-header">UNIT - {u['id']}</div>
                <div class="big-money" style="color:{color}">₹ {u['profit']:,.0f}</div>
                <div class="p-sub">Daily P&L Impact</div>
                <hr style="border-color:#333; margin:15px 0;">
                <div style="display:flex; justify-content:space-between; color:#ddd;">
                    <span>HR: <b>{u['hr']}</b></span>
                    <span>5S Score: <b>{u['score']:.1f}</b></span>
                </div>
            </div>
            """, unsafe_allow_html=True)
            
            # Mini Compliance Status
            if u['sox'] > u['limits']['sox'] or u['nox'] > u['limits']['nox']:
                st.error(f"⚠️ Emission Breach (Limit: {u['limits']['sox']}/{u['limits']['nox']})")
            else:
                st.success("✅ Emissions Compliant")

# --- HELPER FUNCTION FOR UNIT DETAIL TABS ---
def render_unit_detail(u):
    st.markdown(f"### 🔍 Deep Dive: Unit {u['id']}")
    
    # Row 1: Speedometer & Big Visuals
    c1, c2, c3 = st.columns([1, 1, 1])
    
    with c1:
        st.markdown("#### 🏎️ Efficiency Gauge")
        # Dynamic Target in Gauge
        target = configs[int(u['id'])-1]['target_hr']
        fig = go.Figure(go.Indicator(
            mode = "gauge+number+delta", value = u['hr'],
            delta = {'reference': target, 'increasing': {'color': "red"}},
            gauge = {
                'axis': {'range': [2000, 2600]}, 'bar': {'color': "#00ccff"},
                'steps': [{'range': [2000, target], 'color': "rgba(0,255,0,0.2)"}, {'range': [target, 2600], 'color': "rgba(255,0,0,0.2)"}],
                'threshold': {'line': {'color': "red", 'width': 4}, 'thickness': 0.75, 'value': u['hr']}
            }
        ))
        fig.update_layout(height=250, margin=dict(l=20,r=20,t=0,b=0), paper_bgcolor='rgba(0,0,0,0)', font_color='white')
        # FIXED: Replaced use_container_width=True with width="stretch"
        st.plotly_chart(fig, width="stretch", key=f"gauge_{u['id']}")

    with c2:
        st.markdown("#### 🌳 Nature's Feedback")
        if u['profit'] > 0:
            if anim_tree: st_lottie(anim_tree, height=180, key=f"t_{u['id']}")
            st.success(f"**Great Job!** You avoided {abs(u['carbon']):.1f} tons of CO2.")
            st.caption(f"Equivalent to planting **{u['trees']:,.0f} trees** on **{u['acres']:.1f} acres** of land.")
        else:
            if anim_smoke: st_lottie(anim_smoke, height=180, key=f"s_{u['id']}")
            st.error(f"**High Emissions!** Excess {abs(u['carbon']):.1f} tons of CO2 released.")
            st.warning(f"We need to plant **{u['trees']:,.0f} trees** on **{u['acres']:.1f} acres** to offset this damage.")

    with c3:
        st.markdown("#### 📜 5S & Compliance Score")
        score_col = "#00ff88" if u['score'] > 80 else "#ffb000"
        st.markdown(f"""
        <div class="glass-card" style="border-left: 5px solid {score_col}; text-align:left;">
            <div class="p-title">Auto-5S Score</div>
            <div class="p-val" style="color:{score_col}">{u['score']:.1f} / 100</div>
            <div class="p-sub">Technical Hygiene Score</div>
        </div>
        """, unsafe_allow_html=True)
        
        # SOx/NOx Alert Visuals
        sox_col = "placard-green" if u['sox'] <= u['limits']['sox'] else "placard-red"
        st.markdown(f"""
        <div class="placard {sox_col}" style="padding:10px;">
            <div class="p-title">Emission Risk</div>
            <div class="p-val" style="font-size:18px;">SOx: {u['sox']} / NOx: {u['nox']}</div>
            <div class="p-sub">{'✅ Safe Level' if u['sox'] <= u['limits']['sox'] else '⚠️ ACID RAIN RISK'}</div>
        </div>
        """, unsafe_allow_html=True)

    st.divider()
    
    # Row 2: Detailed Placards (Glasscards)
    r2_c1, r2_c2 = st.columns([1, 2])
    
    with r2_c1:
        st.markdown("#### 💳 Certificate Wallet")
        # ESCert Card
        val_esc = u['escerts'] * 1000 
        bg = "border-good" if val_esc > 0 else "border-bad"
        st.markdown(f"""
        <div class="placard {bg}">
            <div class="p-title">PAT ESCert Value</div>
            <div class="p-val">₹ {val_esc:,.0f}</div>
            <div class="p-sub">{u['escerts']:.2f} Certificates</div>
        </div>
        """, unsafe_allow_html=True)
        
        # Carbon Credit Card
        val_carb = u['carbon']
        carb_title = "CO2 Avoided (Credits)" if val_carb > 0 else "Excess CO2 (Penalty)"
        carb_color = "#00ccff" if val_carb > 0 else "#ff3333"
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
        loss_df = loss_df.sort_values('Loss', ascending=True)
        
        fig_bar = px.bar(loss_df, x='Loss', y='Param', orientation='h', text='Loss',
                        color='Loss', color_continuous_scale=['#444', '#ff3333'])
        fig_bar.update_layout(paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', 
                             font_color='white', height=300, xaxis_title="Heat Rate Loss (kcal/kWh)")
        fig_bar.update_traces(texttemplate='%{text:.1f}')
        # FIXED: Replaced use_container_width=True with width="stretch"
        st.plotly_chart(fig_bar, width="stretch", key=f"bar_{u['id']}")

# --- RENDER TABS 2, 3, 4 (UNIT DETAILS) ---
with tabs[1]: render_unit_detail(units_data[0])
with tabs[2]: render_unit_detail(units_data[1])
with tabs[3]: render_unit_detail(units_data[2])

# --- TAB 5: INFO ---
with tabs[4]:
    st.markdown("### 📚 Calculation Breakdown")
    
    info_c1, info_c2 = st.columns(2)
    
    with info_c1:
        st.markdown("#### 📜 PAT Scheme Calculation")
        st.markdown("""
        <div class="glass-card">
            <h3 style="color:#ffcc00">PAT ESCerts</h3>
            <p><b>Formula:</b> <code>(Target HR - Actual HR) × Gen (MU) × 10⁶ / 10⁷</code></p>
            <p>1 ESCert = 1 MTOE (Metric Tonne Oil Equivalent)</p>
            <p>1 MTOE = 10 Million kcal Heat Energy</p>
            <hr style="border-color:#444">
            <p style="font-size:12px; color:#aaa">Example: If you save 10 kcal/kWh on 12 MU gen, you save 120 Million kcal = <b>12 ESCerts</b>.</p>
        </div>
        """, unsafe_allow_html=True)

    with info_c2:
        st.markdown("#### 🌍 Carbon Credit Calculation")
        st.markdown("""
        <div class="glass-card">
            <h3 style="color:#00ccff">Carbon Credits (CCTS)</h3>
            <p><b>Formula:</b> <code>Coal Saved (Tons) × 1.7</code></p>
            <p><b>Step 1:</b> Calculate Heat Saved (kcal).</p>
            <p><b>Step 2:</b> Convert to Coal (Heat / GCV).</p>
            <p><b>Step 3:</b> Multiply by Emission Factor (1.7 Tons CO2/Ton Coal).</p>
        </div>
        """, unsafe_allow_html=True)
    
    st.image("https://upload.wikimedia.org/wikipedia/commons/thumb/b/bb/Rankine_cycle_with_superheat.jpg/640px-Rankine_cycle_with_superheat.jpg", caption="Reference: Rankine Cycle Logic")
