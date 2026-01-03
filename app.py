import streamlit as st
import plotly.graph_objects as go
import plotly.express as px
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import requests
from io import StringIO
from github import Github, Auth
from streamlit_lottie import st_lottie
import streamlit.components.v1 as components
import os 

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
    .border-good { border-top: 4px solid #00ff88; } /* Keep Green for Good Performance */
    .border-bad { border-top: 4px solid #FF3333; } /* GMR Red for Alert */
    .border-gmr { border-top: 4px solid #FF9933; } /* GMR Orange for Neutral */
    
    /* PLACARDS */
    .placard {
        background: #002244; padding: 15px; border-radius: 8px; 
        margin-bottom: 10px; text-align: left;
        transition: all 0.3s ease;
        border-left: 4px solid #FF9933; /* GMR Orange Default */
    }
    .placard:hover { background: #003366; }
    .p-title { font-size: 11px; color: #ccc; text-transform: uppercase; letter-spacing: 1px; font-weight: 400;}
    .p-val { font-size: 24px; font-weight: 800; color: white; margin: 5px 0;}
    .p-sub { font-size: 12px; color: #aaa; font-weight: 300; }
    
    /* TEXT */
    .big-money { font-size: 32px; font-weight: 800; color: #FF9933; } /* GMR Orange */
    .unit-header { font-size: 20px; font-weight: 700; border-bottom: 1px solid #ffffff33; padding-bottom: 10px; margin-bottom: 15px; color: white; }
    
    /* ANIMATIONS */
    @keyframes pulse {
        0% { transform: scale(1); }
        50% { transform: scale(1.05); }
        100% { transform: scale(1); }
    }
    .pulse-icon { animation: pulse 2s infinite; }
    
    /* RESPONSIVE */
    @media (max-width: 768px) {
        .glass-card { margin-bottom: 10px; padding: 15px; }
        .stColumns .stColumn > div > div { display: block !important; }
    }
    
    /* PROGRESS BAR */
    .progress { background: #002244; height: 6px; border-radius: 3px; overflow: hidden; margin-top: 5px; }
    .progress-fill { height: 100%; background: linear-gradient(to right, #FF3333, #FF9933); transition: width 0.3s; }
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
        file = repo.get_contents("plant_history_v16.csv", ref=st.secrets["BRANCH"])
        df = pd.read_csv(StringIO(file.decoded_content.decode()))
        df['Date'] = pd.to_datetime(df['Date'])
        return df, file.sha
    except: return pd.DataFrame(columns=["Date", "Unit", "Profit", "HR", "SOx", "NOx", "Gen"]), None

def save_history(repo, df, sha):
    try:
        csv_content = df.to_csv(index=False)
        msg = "Daily Update" if sha else "Init"
        if sha: repo.update_file("plant_history_v16.csv", msg, csv_content, sha, branch=st.secrets["BRANCH"])
        else: repo.create_file("plant_history_v16.csv", msg, csv_content, branch=st.secrets["BRANCH"])
        return True
    except: return False

# --- 4. CALCULATION ENGINE ---
def calculate_unit(u_id, gen, hr, inputs, design_vals, ash_params):
    # Unpack Design Values Specific to Unit
    TARGET_HR = design_vals['target_hr']
    DESIGN_HR = 2250 # Fixed Design
    COAL_GCV = design_vals['gcv']
    LIMIT_SOX = design_vals['limit_sox']
    LIMIT_NOX = design_vals['limit_nox']
    
    # Financials
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
    
    # Emissions Compliance
    carbon_intensity = (carbon_tons / gen) if gen > 0 else 0
    specific_sox = inputs['sox'] / gen if gen > 0 else 0
    specific_nox = inputs['nox'] / gen if gen > 0 else 0
    
    # ASH CALCULATIONS
    coal_consumed = (gen * hr * 1000) / COAL_GCV if COAL_GCV > 0 else 0
    ash_gen = coal_consumed * (ash_params['ash_pct'] / 100)
    ash_util = ash_params['util_tons']
    ash_stocked = ash_gen - ash_util
    
    # Brick Calc
    bricks_current = ash_util * 666
    bricks_potential_total = ash_gen * 666
    
    # Burj Khalifa Logic (1 Burj Khalifa structure ~= 165 Million bricks equivalent volume)
    burj_khalifa_count = bricks_current / 165_000_000
    
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
                "burj_count": burj_khalifa_count}
    }

# --- 5. SIDEBAR INPUTS ---
with st.sidebar:
    # GMR LOGO
    try:
        st.image("1000051706.png", width="stretch") # Replaced use_container_width with width="stretch" per instructions
    except:
        st.markdown("## **GMR POWER**") 
        
    st.title("Control Panel")
    
    tab_input, tab_ash, tab_config = st.tabs(["📝 Daily", "🪨 Ash/Coal", "⚙️ Config"])
    
    # --- TAB: CONFIG ---
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

    # --- TAB: ASH/COAL PARAMETERS ---
    with tab_ash:
        st.markdown("### 🧪 Coal Analysis (Common)")
        coal_ash = st.number_input("Ash Content (%)", 0.0, 60.0, 35.0)
        coal_moist = st.number_input("Moisture (%)", 0.0, 50.0, 12.0)
        coal_fc = st.number_input("Fixed Carbon (%)", 0.0, 100.0, 30.0)
        
        st.markdown("### 🚜 Ash Management")
        pond_cap = st.number_input("Total Pond Capacity (Tons)", value=500000)
        pond_curr = st.number_input("Current Pond Stock (Tons)", value=350000)
        
        st.markdown("### 🏗️ Utilization (Tons/Day)")
        u1_ash_ut = st.number_input("U1 Ash Utilized", value=1500.0)
        u2_ash_ut = st.number_input("U2 Ash Utilized", value=1400.0)
        u3_ash_ut = st.number_input("U3 Ash Utilized", value=1600.0)

    # --- TAB: DAILY INPUTS ---
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
            with st.expander(f"Unit {i} Inputs", expanded=(i==1)):
                gen = st.number_input(f"U{i} Gen (MU) ⚡", 0.0, 12.0, 8.4, key=f"g{i}")
                hr = st.number_input(f"U{i} HR (kcal) 🌡️", 2000, 3000, 2380 if i==1 else 2310, key=f"h{i}")
                
                st.markdown(f"**U{i} Parameters**")
                vac = st.number_input(f"Vacuum (kg/cm2)", value=-0.90, step=0.001, format="%.3f", key=f"v{i}")
                vac_progress = max(0, min(100, (vac + 0.92) / 0.01 * 100))
                st.markdown(f'<div class="progress"><div class="progress-fill" style="width: {vac_progress}%"></div></div>', unsafe_allow_html=True)
                
                ms = st.number_input(f"MS Temp", 500, 550, 535, key=f"m{i}")
                fg = st.number_input(f"FG Temp ☁️", 100, 160, 135, key=f"f{i}")
                spray = st.number_input(f"Spray", 0, 100, 20, key=f"s{i}")
                
                st.markdown(f"**U{i} Emissions**")
                sox = st.number_input(f"SOx", 0, 1000, 550 if i!=2 else 650, key=f"sx{i}")
                sox_border = "2px solid #FF3333" if sox > lim_sox else "2px solid #00ff88"
                st.markdown(f'<input type="number" value="{sox}" style="border: {sox_border};" disabled>', unsafe_allow_html=True)
                
                nox = st.number_input(f"NOx", 0, 1000, 400, key=f"nx{i}")
                nox_border = "2px solid #FF3333" if nox > lim_nox else "2px solid #00ff88"
                st.markdown(f'<input type="number" value="{nox}" style="border: {nox_border};" disabled>', unsafe_allow_html=True)
                
                ash_p = {'ash_pct': coal_ash, 'util_tons': ash_utils[i-1]}
                units_data.append(calculate_unit(str(i), gen, hr, {'vac':vac, 'ms':ms, 'fg':fg, 'spray':spray, 'sox':sox, 'nox':nox}, configs[i-1], ash_p))
        
        # SAVE BUTTON
        st.markdown("---")
        if st.button("💾 Save to GitHub"):
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

# Ash Pond Life Calculation
daily_dump = max(1, fleet_ash_stock)
pond_days_left = (pond_cap - pond_curr) / daily_dump if daily_dump > 0 else 9999

# --- 6. MAIN PAGE LAYOUT ---
st.title("🏭 GMR Kamalanga 5S Dashboard")
st.markdown(f"**Fleet Status:** {'✅ Profitable' if fleet_profit > 0 else '🔥 Loss Making'} | **Net Daily P&L:** ₹ {fleet_profit:,.0f}")

# TABS NAVIGATION
tabs = st.tabs(["🏠 War Room", "UNIT-1 Detail", "UNIT-2 Detail", "UNIT-3 Detail", "🪨 Ash Mgmt", "📚 Info", "📈 Trends", "🎮 Simulator", "🌿 Compliance"])

# --- TAB 1: WAR ROOM (Executive View) ---
with tabs[0]:
    # GMR LOGO IN WAR ROOM
    c_logo, c_title = st.columns([1, 5])
    with c_logo:
        try:
            st.image("1000051706.png", width="stretch") # GMR Logo
        except:
            st.write("GMR")
    with c_title:
        st.markdown("### 🚁 Fleet Executive Summary")
    
    st.divider()
    
    # Alert Banner
    if fleet_profit < 0:
        st.markdown('<div style="background:#3b0e0e; color:#ffcccc; padding:15px; border-radius:8px; text-align:center; border:1px solid #FF3333;">⚠️ Fleet Alert: Efficiency Loss Detected</div>', unsafe_allow_html=True)
    
    cols = st.columns(4) 
    
    # UNIT CARDS
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
            
    # ASH POND LIFE CARD
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

# --- HELPER FUNCTION FOR UNIT DETAIL TABS ---
def render_unit_detail(u, configs):
    st.markdown(f"### 🔍 Deep Dive: Unit {u['id']}")
    
    # Row 1: Speedometer & Big Visuals
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
            st.caption(f"Equivalent to planting **{u['trees']:,.0f} trees** on **{u['acres']:.1f} acres**.")
        else:
            if anim_smoke: st_lottie(anim_smoke, height=180, key=f"s_{u['id']}")
            st.error(f"**High Emissions!** Excess {abs(u['carbon']):.1f} tons of CO2.")
            st.warning(f"Offset required: **{u['trees']:,.0f} trees** on **{u['acres']:.1f} acres**.")

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
        
        # Acid Rain Warning
        if u['sox'] > u['limits']['sox'] or u['nox'] > u['limits']['nox']:
             st.markdown(f'<div style="background:#3b0e0e; color:#ffcccc; padding:10px; border-radius:5px; border:1px solid #FF3333; text-align:center;">⚠️ ACID RAIN RISK<br>High SOx/NOx Levels</div>', unsafe_allow_html=True)
        else:
             st.markdown(f'<div style="background:#0e2e1b; color:#ccffcc; padding:10px; border-radius:5px; border:1px solid #00ff88; text-align:center;">✅ Safe Emissions</div>', unsafe_allow_html=True)

    st.divider()
    
    # Row 2: Placards & Loss Analysis
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

# --- NEW TAB 4: ASH MANAGEMENT ---
with tabs[4]:
    st.markdown("### 🪨 Ash & By-Product Management")
    st.divider()
    
    # Summary Row
    a1, a2, a3 = st.columns(3)
    with a1:
        st.metric("Total Ash Generated", f"{fleet_ash_gen:,.0f} Tons", delta=f"{fleet_ash_gen*0.01:.0f}% of Coal")
    with a2:
        util_pct = (fleet_ash_util / fleet_ash_gen * 100) if fleet_ash_gen > 0 else 0
        st.metric("Total Ash Utilized", f"{fleet_ash_util:,.0f} Tons", delta=f"{util_pct:.1f}% Efficiency")
    with a3:
        st.metric("Net Pond Accumulation", f"{fleet_ash_stock:,.0f} Tons", delta_color="inverse", delta=f"Daily Addn")
        
    st.divider()
    
    # Brick Simulation & Pond Life
    ash1, ash2 = st.columns([1, 1])
    
    with ash1:
        st.markdown("#### 🧱 Brick Manufacturing Potential")
        total_bricks = sum(u['ash']['bricks_made'] for u in units_data)
        
        # BURJ KHALIFA LOGIC
        total_burjs = sum(u['ash']['burj_count'] for u in units_data)
        
        st.info(f"**Current Utilization:** Enough to make **{total_bricks:,.0f} Bricks** today.")
        
        # BURJ KHALIFA METRIC DISPLAY
        st.markdown(f"""
        <div style="background: linear-gradient(to right, #002244, #003366); padding: 15px; border-radius: 10px; border: 1px solid #FF9933; margin-top: 10px;">
            <h4 style="color: #FF9933; margin:0;">🏙️ Burj Khalifa Scale</h4>
            <p style="color: white; font-size: 18px;">With this amount of ash, you could build <b style="font-size: 24px; color: #00ff88;">{total_burjs:.2f}</b> Burj Khalifas!</p>
            <p style="font-size: 11px; color: #aaa;">(Equivalent material volume)</p>
        </div>
        """, unsafe_allow_html=True)
        
        # Comparison Chart
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
            mode = "gauge+number",
            value = pond_days_left,
            title = {'text': "Days to Overflow"},
            gauge = {
                'axis': {'range': [0, 3650]}, 
                'bar': {'color': "#00ff88" if pond_days_left > 365 else "#FF3333"},
                'steps': [
                    {'range': [0, 180], 'color': "rgba(255,0,0,0.3)"},
                    {'range': [180, 3650], 'color': "rgba(0,255,0,0.1)"}
                ]
            }
        ))
        fig_pond.update_layout(height=300, paper_bgcolor='rgba(0,0,0,0)', font_color='white')
        st.plotly_chart(fig_pond, width="stretch")
        
        if pond_days_left < 100:
            st.error(f"CRITICAL: Ash Pond will likely fill up in {pond_days_left:.0f} days at current rate!")
        else:
            st.success(f"Safe: Pond has {pond_days_left/365:.1f} years of life remaining.")

    # Unit-wise Ash Table
    st.markdown("#### Unit-wise Ash Breakdown")
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

# --- TAB 6: INFO ---
with tabs[5]:
    st.markdown("### 📚 Plant Overview & Logic")
    
    # PLANT IMAGE HERE
    try:
        st.image("1000051705.jpg", caption="GMR Kamalanga Energy Limited", width="stretch")
    except:
        st.info("Plant image not found. Please upload '1000051705.jpg' to the folder.")

    st.divider()
    info_c1, info_c2 = st.columns(2)
    
    with info_c1:
        st.markdown("""
        <div class="glass-card">
            <h3 style="color:#FF9933">PAT ESCerts</h3>
            <p><b>Formula:</b> <code>(Target HR - Actual HR) × Gen (MU) × 10⁶ / 10⁷</code></p>
            <p>1 ESCert = 1 MTOE (Metric Tonne Oil Equivalent)</p>
            <p>1 MTOE = 10 Million kcal Heat Energy</p>
        </div>
        """, unsafe_allow_html=True)

    with info_c2:
        st.markdown("""
        <div class="glass-card">
            <h3 style="color:#00ccff">Carbon Credits</h3>
            <p><b>Formula:</b> <code>Coal Saved (Tons) × 1.7</code></p>
            <p>1.7 is the weighted avg emission factor for Indian Coal.</p>
        </div>
        """, unsafe_allow_html=True)
    
    st.image("https://upload.wikimedia.org/wikipedia/commons/thumb/b/bb/Rankine_cycle_with_superheat.jpg/640px-Rankine_cycle_with_superheat.jpg", caption="Reference: Rankine Cycle Logic")

# --- TAB 7: TRENDS ---
with tabs[6]:
    st.markdown("### 📈 Historical Performance")
    period = st.radio("Select Period:", ["Last 7 Days (Weekly)", "Last 30 Days (Monthly)"], horizontal=True)
    
    repo = init_github()
    if repo:
        df_hist, sha = load_history(repo)
        if not df_hist.empty:
            if "7 Days" in period:
                cutoff = datetime.now() - timedelta(days=7)
            else:
                cutoff = datetime.now() - timedelta(days=30)
            
            df_hist = df_hist[df_hist['Date'] >= cutoff]
            
            if not df_hist.empty:
                st.markdown("#### Heat Rate Trend")
                fig_hr = px.line(df_hist, x="Date", y="HR", color="Unit", markers=True, template="plotly_dark")
                fig_hr.update_layout(showlegend=True, xaxis_title="Date", yaxis_title="HR (kcal/kWh)", font_color='white')
                fig_hr.update_xaxes(showgrid=True, gridcolor='#333')
                st.plotly_chart(fig_hr, width="stretch")
                
                st.markdown("#### Profit/Loss Trend")
                fig_pl = px.bar(df_hist, x="Date", y="Profit", color="Unit", barmode="group", template="plotly_dark")
                fig_pl.update_layout(showlegend=True, xaxis_title="Date", yaxis_title="Profit (₹)", font_color='white')
                fig_pl.update_xaxes(showgrid=True, gridcolor='#333')
                st.plotly_chart(fig_pl, width="stretch")
            else:
                st.warning("No data found for the selected period.")
        else:
            st.info("No history saved yet.")
    else:
        st.warning("GitHub not connected.")

# --- TAB 8: SIMULATOR ---
with tabs[7]:
    st.markdown("### 🎮 What-If Simulator")
    if anim_money: st_lottie(anim_money, height=150)
    
    c_sim1, c_sim2 = st.columns([1, 2])
    with c_sim1:
        s_vac = st.slider("Simulate Vacuum Improvement", -0.85, -0.99, -0.90)
        s_gen = st.slider("Simulate Load (MW)", 300, 350, 350)
        s_ms = st.slider("MS Temp", 500, 550, 535)
        s_fg = st.slider("FG Temp", 100, 160, 135)
        s_spray = st.slider("Spray", 0, 100, 20)
    with c_sim2:
        sim_inputs = {'vac': s_vac, 'ms': s_ms, 'fg': s_fg, 'spray': s_spray, 'sox': 550, 'nox': 400}
        sim_unit = calculate_unit("1", s_gen / 100, 2350, sim_inputs, configs[0], {'ash_pct': 35, 'util_tons': 1000}) 
        col1, col2 = st.columns(2)
        with col1:
            st.metric("Current Profit", f"₹ {units_data[0]['profit']:,.0f}")
        with col2:
            st.metric("Simulated Profit", f"₹ {sim_unit['profit']:,.0f}", delta=f"{sim_unit['profit'] - units_data[0]['profit']:,.0f}")

# --- TAB 9: COMPLIANCE ---
with tabs[8]:
    st.markdown("### 🌿 Emissions Compliance & Carbon Accounting")
    st.divider()
    
    total_gen = sum(u['gen'] for u in units_data)
    fleet_carbon = sum(u['carbon'] for u in units_data)
    fleet_sox = sum(u['sox'] * u['gen'] for u in units_data) / total_gen if total_gen > 0 else 0
    fleet_nox = sum(u['nox'] * u['gen'] for u in units_data) / total_gen if total_gen > 0 else 0
    fleet_ci = sum(u['emissions']['carbon_intensity'] * u['gen'] for u in units_data) / total_gen if total_gen > 0 else 0
    
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Fleet CO2 (Tons)", f"{fleet_carbon:.2f}", delta=f"{fleet_carbon:.2f}")
    with col2:
        sox_comp = "✅" if fleet_sox < lim_sox else "❌"
        st.metric(f"Avg SOx/MWh {sox_comp}", f"{fleet_sox:.1f}", delta=f"{fleet_sox - lim_sox:.1f}")
    with col3:
        nox_comp = "✅" if fleet_nox < lim_nox else "❌"
        st.metric(f"Avg NOx/MWh {nox_comp}", f"{fleet_nox:.1f}", delta=f"{fleet_nox - lim_nox:.1f}")
    with col4:
        st.metric("Carbon Intensity (Tons/MWh)", f"{fleet_ci:.2f}")
    
    if fleet_sox > lim_sox or fleet_nox > lim_nox:
        st.markdown(f'<div style="background:#3b0e0e; color:#ffcccc; padding:15px; border-radius:8px; border:1px solid #FF3333; text-align:center; margin:20px 0;">⚠️ FLEET ACID RAIN RISK<br>High Average SOx/NOx Levels</div>', unsafe_allow_html=True)
    else:
        st.markdown(f'<div style="background:#0e2e1b; color:#ccffcc; padding:15px; border-radius:8px; border:1px solid #00ff88; text-align:center; margin:20px 0;">✅ Fleet Safe Emissions</div>', unsafe_allow_html=True)
    
    st.divider()
    
    st.markdown("#### 📊 Carbon Ledger")
    ledger_df = pd.DataFrame([
        {"Item": "Daily CO2", "Value": f"{fleet_carbon:.2f} Tons", "Offset": f"{sum(u['trees'] for u in units_data):,.0f} Trees"},
        {"Item": "ESCerts Offset", "Value": f"{sum(u['escerts'] for u in units_data):.2f} Certs", "Value (₹)": f"₹ {sum(u['escerts'] * 1000 for u in units_data):,.0f}"},
        {"Item": "Net Balance", "Value": "Towards Net-Zero", "Status": "🟢 Positive" if fleet_carbon < 0 else "🔴 Negative"}
    ])
    st.dataframe(ledger_df, width="stretch")
