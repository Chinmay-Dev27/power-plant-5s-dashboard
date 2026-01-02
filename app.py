import streamlit as st
import plotly.graph_objects as go
import pandas as pd
from github import Github, Auth
from io import StringIO
from datetime import datetime
import requests
from streamlit_lottie import st_lottie

# --- PAGE CONFIGURATION ---
st.set_page_config(page_title="Power Plant 5S Eco-Dashboard", layout="wide", page_icon="🏭")

# --- ASSETS & STYLING ---
def load_lottieurl(url):
    try:
        r = requests.get(url, timeout=3)
        return r.json() if r.status_code == 200 else None
    except: return None

# Animations
anim_tree = load_lottieurl("https://lottie.host/6e35574d-8651-477d-b570-56965c276b3b/22572535-373f-42a9-823c-99e582862594.json") # Growing Tree
anim_alert = load_lottieurl("https://lottie.host/02008323-2895-4673-863a-4934e402802d/41838634-11d9-430c-992a-356c92d529d3.json") # Warning Triangle
anim_factory = load_lottieurl("https://lottie.host/575a66c6-1215-4688-9189-b57579621379/10839556-9141-4712-a89e-224429715783.json") # Factory

# Custom CSS to fill empty space and make metrics POP
st.markdown("""
    <style>
    .big-banner-loss { 
        padding: 20px; background-color: #5a0000; color: #ffcccc; 
        border-radius: 10px; text-align: center; font-size: 24px; border: 2px solid #ff4b4b; margin-bottom: 20px;
    }
    .big-banner-win { 
        padding: 20px; background-color: #004d00; color: #ccffcc; 
        border-radius: 10px; text-align: center; font-size: 24px; border: 2px solid #00ff00; margin-bottom: 20px;
    }
    .metric-box {
        background-color: #1E1E1E; padding: 15px; border-radius: 8px; border-left: 5px solid #FFC107;
        margin-bottom: 10px;
    }
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
        file = repo.get_contents("history_v4.csv", ref=st.secrets["BRANCH"])
        return pd.read_csv(StringIO(file.decoded_content.decode())), file.sha
    except: return pd.DataFrame(), None

def save_data(repo, df, sha):
    try:
        csv_content = df.to_csv(index=False)
        msg = "Daily Update" if sha else "Initial Commit"
        if sha: repo.update_file("history_v4.csv", msg, csv_content, sha, branch=st.secrets["BRANCH"])
        else: repo.create_file("history_v4.csv", msg, csv_content, branch=st.secrets["BRANCH"])
        return True
    except: return False

# --- SIDEBAR CONFIG ---
with st.sidebar:
    st.header("⚙️ Plant Configuration")
    with st.expander("Design Data (Reference)", expanded=False):
        # FIX: Added 'value=' to all inputs to prevent TypeError
        DESIGN_HEAT_RATE = st.number_input("Design HR", value=2250.0, step=10.0)
        TARGET_HEAT_RATE = st.number_input("PAT Target HR", value=2350.0, step=10.0)
        DESIGN_MS_TEMP = st.number_input("Design MS Temp", value=540.0)
        DESIGN_VACUUM = st.number_input("Design Vacuum", value=-0.92)
        DESIGN_FG_TEMP = st.number_input("Design FG Temp", value=130.0)

    st.header("📝 Daily Input")
    with st.form("daily_input"):
        date_input = st.date_input("Date", datetime.now())
        # FIX: Added 'value=' and explicit 'min_value='
        gross_gen_mu = st.number_input("Gross Generation (MU)", value=12.0, min_value=0.0, step=0.1)
        
        st.markdown("---")
        st.markdown("**5S Parameters**")
        ms_temp = st.number_input("MS Temp (°C)", value=535.0, step=1.0)
        vacuum = st.number_input("Vacuum (kg/cm2)", value=-0.90, max_value=0.0, step=0.01)
        fg_temp = st.number_input("APH Out Temp (°C)", value=135.0, step=1.0)
        sh_spray = st.number_input("SH Spray (TPH)", value=10.0, step=0.5)
        rh_spray = st.number_input("RH Spray (TPH)", value=5.0, step=0.5)
        coal_gcv = st.number_input("Coal GCV", value=3600.0, step=10.0)
        
        submitted = st.form_submit_button("🚀 Run Analysis")

# --- CALCULATION LOGIC ---
if submitted or True: # Run once on load to show defaults, then update on submit
    # Heat Rate Penalties
    loss_ms = max(0, (DESIGN_MS_TEMP - ms_temp) * 1.2)
    loss_vac = max(0, ((vacuum - DESIGN_VACUUM) / 0.01) * 18) if vacuum > DESIGN_VACUUM else 0
    loss_fg = max(0, (fg_temp - DESIGN_FG_TEMP) * 1.5)
    loss_spray = (sh_spray + rh_spray) * 2.0
    loss_constant = 50.0
    calculated_actual_hr = DESIGN_HEAT_RATE + loss_ms + loss_vac + loss_fg + loss_spray + loss_constant

    # 5S Score
    calc_5s_score = max(0, 100 - ((loss_ms + loss_vac + loss_fg + loss_spray) / 2))

    # Savings & Credits
    gross_gen_units = gross_gen_mu * 1_000_000
    hr_diff_vs_target = TARGET_HEAT_RATE - calculated_actual_hr
    total_kcal_saved = hr_diff_vs_target * gross_gen_units

    # PAT (1 ESCert = 10 Gcal)
    escerts = total_kcal_saved / 10_000_000

    # Carbon
    coal_saved_kg = total_kcal_saved / coal_gcv if coal_gcv > 0 else 0
    carbon_credits = (coal_saved_kg / 1000) * 1.7 # 1.7 tCO2/tCoal

    # Tree Equivalent (1 Tree absorbs ~25kg CO2/year -> ~0.025 Tons)
    # Inverse: 1 Ton CO2 = 40 Trees
    trees_impact = abs(carbon_credits) * 40 

    # Money
    ESCERT_PRICE = 1000
    CARBON_PRICE = 500
    COAL_PRICE = 4.5 # Rs per kg
    monetary_total = (escerts * ESCERT_PRICE) + (carbon_credits * CARBON_PRICE) + (coal_saved_kg * COAL_PRICE)

    # --- DASHBOARD HEADER ---
    col_head1, col_head2 = st.columns([1, 5])
    with col_head1:
        if anim_factory: st_lottie(anim_factory, height=120, key="factory_head")
        else: st.markdown("# 🏭")
    with col_head2:
        st.title("Smart 5S & Efficiency Dashboard")
        st.caption("Digitizing 5S: From Cleaning to Carbon Credits")

    # --- IMPACT BANNER (The "Eye Opener") ---
    if monetary_total >= 0:
        st.markdown(f'<div class="big-banner-win">💰 PROFIT OF THE DAY: ₹ {monetary_total:,.0f}</div>', unsafe_allow_html=True)
    else:
        st.markdown(f'<div class="big-banner-loss">🔥 LOSS OF THE DAY: ₹ {monetary_total:,.0f}</div>', unsafe_allow_html=True)

    # --- MAIN LAYOUT WITH TABS (Fills Empty Space) ---
    tab1, tab2, tab3 = st.tabs(["📊 Financial & PAT", "🌲 Carbon & Environment", "🔧 Technical 5S"])

    # TAB 1: FINANCIALS & ESCERTS
    with tab1:
        col1, col2 = st.columns([2, 1])
        
        with col1:
            st.subheader("PAT Scheme Performance (ESCerts)")
            # Gauge Chart for Heat Rate (The Driver of ESCerts)
            fig_gauge = go.Figure(go.Indicator(
                mode = "gauge+number+delta",
                value = calculated_actual_hr,
                domain = {'x': [0, 1], 'y': [0, 1]},
                title = {'text': "Station Heat Rate (kcal/kWh)"},
                delta = {'reference': TARGET_HEAT_RATE, 'increasing': {'color': "red"}},
                gauge = {
                    'axis': {'range': [DESIGN_HEAT_RATE - 50, TARGET_HEAT_RATE + 200]},
                    'bar': {'color': "#17202A"},
                    'steps': [
                        {'range': [DESIGN_HEAT_RATE - 50, TARGET_HEAT_RATE], 'color': "#2ECC71"}, # Green Zone
                        {'range': [TARGET_HEAT_RATE, TARGET_HEAT_RATE + 200], 'color': "#E74C3C"}], # Red Zone
                    'threshold': {'line': {'color': "white", 'width': 4}, 'thickness': 0.75, 'value': TARGET_HEAT_RATE}}
            ))
            st.plotly_chart(fig_gauge, width="stretch")

        with col2:
            st.markdown("### 📜 Certificate Impact")
            st.markdown(f"""
            <div class="metric-box">
                <b>ESCert Quantity:</b><br>
                <span style="font-size: 30px; color: {'#00FF00' if escerts > 0 else '#FF4B4B'}">
                    {escerts:,.2f}
                </span>
            </div>
            <div class="metric-box">
                <b>Est. Monetary Value:</b><br>
                <span style="font-size: 30px;">₹ {escerts * ESCERT_PRICE:,.0f}</span>
            </div>
            """, unsafe_allow_html=True)
            
            if escerts < 0:
                if anim_alert: st_lottie(anim_alert, height=150, key="alert_pat")
                st.error(f"We are burning {abs(escerts):.2f} Certificates per day!")

    # TAB 2: ENVIRONMENT (TREES & CARBON)
    with tab2:
        c_env1, c_env2 = st.columns([1, 1])
        
        with c_env1:
            st.subheader("🌍 Carbon Footprint")
            # Visualizing CO2
            fig_co2 = go.Figure()
            fig_co2.add_trace(go.Indicator(
                mode = "number",
                value = carbon_credits,
                title = {"text": "Carbon Credits (tCO2 Avoided)"},
                number = {'prefix': "+ " if carbon_credits > 0 else "", 'suffix': " Tons", 'font': {'size': 50, 'color': '#4CAF50' if carbon_credits > 0 else '#FF5252'}}
            ))
            fig_co2.update_layout(height=250)
            st.plotly_chart(fig_co2, width="stretch")
            
        with c_env2:
            st.subheader("🌲 The Tree Equivalent")
            
            if carbon_credits < 0:
                st.warning(f"Today's excess emission is equivalent to cutting down **{trees_impact:,.0f} mature trees**.")
                st.markdown("### 🪓 We need a forest to fix this.")
            else:
                st.success(f"Today's savings is equivalent to planting **{trees_impact:,.0f} trees**!")
                if anim_tree: st_lottie(anim_tree, height=200, key="tree_win")

    # TAB 3: TECHNICAL 5S (THE WHY)
    with tab3:
        st.subheader("🔧 Heat Rate Deviation (The Root Cause)")
        
        # Waterfall Chart - Wide
        fig_water = go.Figure(go.Waterfall(
            name = "20", orientation = "v",
            measure = ["relative", "relative", "relative", "relative", "relative", "total"],
            x = ["Design HR", "MS Temp", "Vacuum", "Flue Gas", "Spray", "ACTUAL"],
            y = [DESIGN_HEAT_RATE, loss_ms, loss_vac, loss_fg, loss_spray, 0],
            connector = {"line":{"color":"rgb(63, 63, 63)"}},
            decreasing = {"marker":{"color":"#2ECC71"}},
            increasing = {"marker":{"color":"#E74C3C"}},
            totals = {"marker":{"color":"#FFFFFF"}}
        ))
        fig_water.update_layout(template="plotly_dark", height=400, title="Where are we losing efficiency?")
        st.plotly_chart(fig_water, width="stretch")
        
        # 5S Score Display
        st.markdown(f"### 🧹 Auto-5S Score: {calc_5s_score:.1f} / 100")
        if calc_5s_score < 80:
            st.info("💡 Tip: Improve Condenser Vacuum (Clean Tubes) to boost score.")

    # --- GITHUB SAVE ---
    repo = init_github()
    if repo and st.button("💾 Save to History"):
        df, sha = load_data(repo)
        new_row = pd.DataFrame([{
            "Date": str(date_input), "HR": calculated_actual_hr, "Score": calc_5s_score, 
            "ESCert": escerts, "Profit": monetary_total
        }])
        if not df.empty:
            df = pd.concat([df, new_row], ignore_index=True).drop_duplicates(subset=["Date"], keep='last')
        else: df = new_row
        
        if save_data(repo, df, sha): st.success("Saved!")
