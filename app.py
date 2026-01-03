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

st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;600;700;800&display=swap');
    
    /* MAIN THEME */
    .stApp { 
        background: linear-gradient(to bottom, #0e1117, #161b22); 
        font-family: 'Inter', sans-serif;
    }
    
    /* GLASS CARDS ENHANCED */
    .glass-card {
        background: rgba(255, 255, 255, 0.05);
        background: radial-gradient(circle at top left, rgba(255,255,255,0.1) 0%, rgba(255,255,255,0.05) 100%);
        backdrop-filter: blur(10px);
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
        background: rgba(255, 255, 255, 0.08);
        box-shadow: 0 12px 40px rgba(0,0,0,0.4);
    }
    
    /* SCENE COLORS */
    .border-good { border-top: 4px solid #00ff88; }
    .border-bad { border-top: 4px solid #ff3333; }
    
    /* PLACARDS */
    .placard {
        background: #1c2128; padding: 15px; border-radius: 8px; 
        margin-bottom: 10px; text-align: left;
        transition: all 0.3s ease;
    }
    .placard:hover { background: #252b33; }
    .p-title { font-size: 11px; color: #aaa; text-transform: uppercase; letter-spacing: 1px; font-weight: 400;}
    .p-val { font-size: 24px; font-weight: 800; color: white; margin: 5px 0;}
    .p-sub { font-size: 12px; color: #888; font-weight: 300; }
    
    /* TEXT */
    .big-money { font-size: 32px; font-weight: 800; }
    .unit-header { font-size: 20px; font-weight: 700; border-bottom: 1px solid #333; padding-bottom: 10px; margin-bottom: 15px; color: white; }
    
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
    .progress { background: #333; height: 4px; border-radius: 2px; overflow: hidden; margin-top: 5px; }
    .progress-fill { height: 100%; background: linear-gradient(to right, #ff3333, #00ff88); transition: width 0.3s; }
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
        file = repo.get_contents("plant_history_v13.csv", ref=st.secrets["BRANCH"])
        df = pd.read_csv(StringIO(file.decoded_content.decode()))
        df['Date'] = pd.to_datetime(df['Date'])
        return df, file.sha
    except: return pd.DataFrame(columns=["Date", "Unit", "Profit", "HR", "SOx", "NOx", "Gen"]), None

def save_history(repo, df, sha):
    try:
        csv_content = df.to_csv(index=False)
        msg = "Daily Update" if sha else "Init"
        if sha: repo.update_file("plant_history_v13.csv", msg, csv_content, sha, branch=st.secrets["BRANCH"])
        else: repo.create_file("plant_history_v13.csv", msg, csv_content, branch=st.secrets["BRANCH"])
        return True
    except: return False

# --- 4. CALCULATION ENGINE ---
def calculate_unit(u_id, gen, hr, inputs, design_vals):
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
    
    # Emissions Compliance Additions
    carbon_intensity = (carbon_tons / gen) if gen > 0 else 0  # CO2/MWh
    specific_sox = inputs['sox'] / gen if gen > 0 else 0  # SOx/MWh
    specific_nox = inputs['nox'] / gen if gen > 0 else 0  # NOx/MWh
    
    return {
        "id": u_id, "gen": gen, "hr": hr, "profit": profit, 
        "escerts": escerts, "carbon": carbon_tons, 
        "trees": trees_count, "acres": acres_land,
        "score": score_5s, "sox": inputs['sox'], "nox": inputs['nox'],
        "limits": {'sox': LIMIT_SOX, 'nox': LIMIT_NOX},
        "losses": {"Vacuum": abs(l_vac), "MS Temp": l_ms, "Flue Gas": l_fg, "Spray": l_spray, "Unaccounted": l_unacc},
        "emissions": {"carbon_intensity": carbon_intensity, "specific_sox": specific_sox, "specific_nox": specific_nox}
    }

# --- 5. SIDEBAR INPUTS ---
with st.sidebar:
    components.html('<div class="pulse-icon">⚡</div>', height=50)  # Pulsing icon
    st.title("Control Panel")
    
    tab_input, tab_config = st.tabs(["📝 Daily Data", "⚙️ Config"])
    
    # --- TAB: CONFIG (Limits & Refs) ---
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

    # --- TAB: DAILY INPUTS ---
    with tab_input:
        date_in = st.date_input("Log Date", datetime.now())
        units_data = []
        configs = [
            {'target_hr': t_u1, 'gcv': g_u1, 'limit_sox': lim_sox, 'limit_nox': lim_nox},
            {'target_hr': t_u2, 'gcv': g_u2, 'limit_sox': lim_sox, 'limit_nox': lim_nox},
            {'target_hr': t_u3, 'gcv': g_u3, 'limit_sox': lim_sox, 'limit_nox': lim_nox}
        ]
        
        for i in range(1, 4):
            with st.expander(f"Unit {i} Inputs", expanded=(i==1)):
                gen = st.number_input(f"U{i} Gen (MU) ⚡", 0.0, 12.0, 8.4, key=f"g{i}")
                hr = st.number_input(f"U{i} HR (kcal) 🌡️", 2000, 3000, 2380 if i==1 else 2310, key=f"h{i}")
                
                st.markdown(f"**U{i} Parameters**")
                vac = st.number_input(f"Vacuum (kg/cm2)", value=-0.90, step=0.001, format="%.3f", key=f"v{i}")
                # Progress bar for vacuum
                vac_progress = max(0, min(100, (vac + 0.92) / 0.01 * 100))
                st.markdown(f'<div class="progress"><div class="progress-fill" style="width: {vac_progress}%"></div></div>', unsafe_allow_html=True)
                
                ms = st.number_input(f"MS Temp", 500, 550, 535, key=f"m{i}")
                fg = st.number_input(f"FG Temp ☁️", 100, 160, 135, key=f"f{i}")
                spray = st.number_input(f"Spray", 0, 100, 20, key=f"s{i}")
                
                st.markdown(f"**U{i} Emissions**")
                sox = st.number_input(f"SOx", 0, 1000, 550 if i!=2 else 650, key=f"sx{i}")
                nox = st.number_input(f"NOx", 0, 1000, 400, key=f"nx{i}")
                
                units_data.append(calculate_unit(str(i), gen, hr, {'vac':vac, 'ms':ms, 'fg':fg, 'spray':spray, 'sox':sox, 'nox':nox}, configs[i-1]))
        
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

# --- 6. MAIN PAGE LAYOUT ---
st.title("🏭 GMR Kamalanga 5S Dashboard")
st.markdown(f"**Fleet Status:** {'✅ Profitable' if fleet_profit > 0 else '🔥 Loss Making'} | **Net Daily P&L:** ₹ {fleet_profit:,.0f}")

# TABS NAVIGATION
tabs = st.tabs(["🏠 War Room", "UNIT-1 Detail", "UNIT-2 Detail", "UNIT-3 Detail", "📚 Info", "📈 Trends", "🎮 Simulator", "🌿 Compliance & Carbon"])

# --- TAB 1: WAR ROOM (Executive View) ---
with tabs[0]:
    st.markdown("### 🚁 Fleet Executive Summary")
    st.divider()
    
    # Alert Banner
    if fleet_profit < 0:
        st.markdown('<div style="background:#3b0e0e; color:#ffcccc; padding:15px; border-radius:8px; text-align:center; border:1px solid red;">⚠️ Fleet Alert: Optimize Vacuum in U2 for ₹45k savings</div>', unsafe_allow_html=True)
    
    cols = st.columns(3)
    for i, u in enumerate(units_data):
        color = "#00ff88" if u['profit'] > 0 else "#ff3333"
        border = "border-good" if u['profit'] > 0 else "border-bad"
        
        # SOx/NOx Status Colors
        sox_col = "#ff3333" if u['sox'] > u['limits']['sox'] else "#00ff88"
        nox_col = "#ff3333" if u['nox'] > u['limits']['nox'] else "#00ff88"
        
        with cols[i]:
            st.markdown(f"""
            <div class="glass-card {border}">
                <div class="unit-header">UNIT - {u['id']}</div>
                <div class="big-money" style="color:{color}">₹ {u['profit']:,.0f}</div>
                <div class="p-sub">Daily P&L Impact</div>
                <hr style="border-color:#333; margin:15px 0;">
                <div style="display:flex; justify-content:space-between; color:#ddd; margin-bottom:10px;">
                    <span>HR: <b>{u['hr']}</b></span>
                    <span>5S Score: <b>{u['score']:.1f}</b></span>
                </div>
                <div style="background:#111; padding:5px; border-radius:5px; font-size:13px;">
                    <span style="color:{sox_col}">SOx: <b>{u['sox']}</b></span> | 
                    <span style="color:{nox_col}">NOx: <b>{u['nox']}</b></span>
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
            delta = {'reference': target, 'increasing': {'color': "red"}},
            gauge = {
                'axis': {'range': [2000, 2600]}, 'bar': {'color': "#00ccff"},
                'steps': [{'range': [2000, target], 'color': "rgba(0,255,0,0.2)"}, {'range': [target, 2600], 'color': "rgba(255,0,0,0.2)"}],
                'threshold': {'line': {'color': "red", 'width': 4}, 'thickness': 0.75, 'value': u['hr']}
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
        score_col = "#00ff88" if u['score'] > 80 else "#ffb000"
        st.markdown(f"""
        <div class="glass-card" style="border-left: 5px solid {score_col}; text-align:left;">
            <div class="p-title">Auto-5S Score</div>
            <div class="p-val" style="color:{score_col}">{u['score']:.1f} / 100</div>
            <div class="p-sub">Technical Hygiene Score</div>
        </div>
        """, unsafe_allow_html=True)
        
        # Acid Rain Warning
        if u['sox'] > u['limits']['sox'] or u['nox'] > u['limits']['nox']:
             st.markdown(f'<div style="background:#3b0e0e; color:#ffcccc; padding:10px; border-radius:5px; border:1px solid red; text-align:center;">⚠️ ACID RAIN RISK<br>High SOx/NOx Levels</div>', unsafe_allow_html=True)
        else:
             st.markdown(f'<div style="background:#0e2e1b; color:#ccffcc; padding:10px; border-radius:5px; border:1px solid green; text-align:center;">✅ Safe Emissions</div>', unsafe_allow_html=True)

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
        loss_df = loss_df.sort_values('Loss', ascending=True).head(3)  # Top 3
        fig_bar = px.bar(loss_df, x='Loss', y='Param', orientation='h', text='Loss', color='Loss', 
                         color_continuous_scale=['#444', '#ff3333'], template='plotly_dark')
        fig_bar.update_layout(paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', font_color='white', height=300)
        fig_bar.update_traces(texttemplate='%{text:.1f}', textposition='outside')
        fig_bar.update_xaxes(showgrid=True, gridcolor='#333')
        st.plotly_chart(fig_bar, width="stretch", key=f"bar_{u['id']}")

# --- RENDER UNIT DETAILS ---
with tabs[1]: render_unit_detail(units_data[0], configs)
with tabs[2]: render_unit_detail(units_data[1], configs)
with tabs[3]: render_unit_detail(units_data[2], configs)

# --- TAB 5: INFO ---
with tabs[4]:
    st.markdown("### 📚 Calculation Breakdown")
    info_c1, info_c2 = st.columns(2)
    
    with info_c1:
        st.markdown("""
        <div class="glass-card">
            <h3 style="color:#ffcc00">PAT ESCerts</h3>
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

# --- TAB 6: TRENDS (UPDATED) ---
with tabs[5]:
    st.markdown("### 📈 Historical Performance")
    
    # Filter Selection
    period = st.radio("Select Period:", ["Last 7 Days (Weekly)", "Last 30 Days (Monthly)"], horizontal=True)
    
    repo = init_github()
    if repo:
        df_hist, sha = load_history(repo)
        if not df_hist.empty:
            # Date Filtering Logic
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

# --- TAB 7: SIMULATOR ---
with tabs[6]:
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
        # Simulate calculation
        sim_inputs = {'vac': s_vac, 'ms': s_ms, 'fg': s_fg, 'spray': s_spray, 'sox': 550, 'nox': 400}
        sim_unit = calculate_unit("1", s_gen / 100, 2350, sim_inputs, configs[0])  # Approx
        col1, col2 = st.columns(2)
        with col1:
            st.metric("Current Profit", f"₹ {units_data[0]['profit']:,.0f}")
        with col2:
            st.metric("Simulated Profit", f"₹ {sim_unit['profit']:,.0f}", delta=f"{sim_unit['profit'] - units_data[0]['profit']:,.0f}")

# --- NEW TAB 8: COMPLIANCE & CARBON ---
with tabs[7]:
    st.markdown("### 🌿 Emissions Compliance & Carbon Accounting")
    st.divider()
    
    # Fleet Emissions Summary - FIXED SUMS
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
    
    # Fleet Acid Rain Warning
    if fleet_sox > lim_sox or fleet_nox > lim_nox:
        st.markdown(f'<div style="background:#3b0e0e; color:#ffcccc; padding:15px; border-radius:8px; border:1px solid red; text-align:center; margin:20px 0;">⚠️ FLEET ACID RAIN RISK<br>High Average SOx/NOx Levels</div>', unsafe_allow_html=True)
    else:
        st.markdown(f'<div style="background:#0e2e1b; color:#ccffcc; padding:15px; border-radius:8px; border:1px solid green; text-align:center; margin:20px 0;">✅ Fleet Safe Emissions</div>', unsafe_allow_html=True)
    
    st.divider()
    
    # Carbon Ledger
    st.markdown("#### 📊 Carbon Ledger")
    ledger_df = pd.DataFrame([
        {"Item": "Daily CO2", "Value": f"{fleet_carbon:.2f} Tons", "Offset": f"{sum(u['trees'] for u in units_data):,.0f} Trees"},
        {"Item": "ESCerts Offset", "Value": f"{sum(u['escerts'] for u in units_data):.2f} Certs", "Value (₹)": f"₹ {sum(u['escerts'] * 1000 for u in units_data):,.0f}"},
        {"Item": "Net Balance", "Value": "Towards Net-Zero", "Status": "🟢 Positive" if fleet_carbon < 0 else "🔴 Negative"}
    ])
    st.dataframe(ledger_df, use_container_width=True)
    
    # Historical Compliance (from GitHub)
    repo = init_github()
    if repo:
        df_hist, _ = load_history(repo)
        if not df_hist.empty:
            df_hist['Year'] = df_hist['Date'].dt.year
            current_year = datetime.now().year
            yearly_emissions = df_hist[df_hist['Year'] == current_year].groupby('Unit').agg({
                'SOx': 'sum', 'NOx': 'sum', 'Gen': 'sum'
            }).reset_index()
            if not yearly_emissions.empty:
                yearly_emissions['Avg SOx/MWh'] = yearly_emissions['SOx'] / yearly_emissions['Gen']
                yearly_emissions['Avg NOx/MWh'] = yearly_emissions['NOx'] / yearly_emissions['Gen']
                
                st.markdown("#### 📈 Yearly Compliance Trends")
                fig_comp = px.bar(yearly_emissions, x='Unit', y=['Avg SOx/MWh', 'Avg NOx/MWh'], 
                                  barmode='group', template='plotly_dark', title="Annual Specific Emissions")
                fig_comp.add_hline(y=lim_sox, line_dash="dash", line_color="red", annotation_text="SOx Limit")
                fig_comp.add_hline(y=lim_nox, line_dash="dash", line_color="orange", annotation_text="NOx Limit")
                fig_comp.update_layout(font_color='white', height=400)
                st.plotly_chart(fig_comp, use_container_width=True)
                
                # Export Report Button
                if st.button("📄 Export Compliance Report"):
                    csv = yearly_emissions.to_csv(index=False)
                    st.download_button("Download CSV", csv, "compliance_report.csv", "text/csv")
            else:
                st.warning("No data for current year.")
        else:
            st.info("No history saved yet.")
    else:
        st.warning("GitHub not connected for historical compliance data.")