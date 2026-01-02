import streamlit as st
import plotly.graph_objects as go
import pandas as pd
from github import Github, Auth
from io import StringIO
from datetime import datetime
import requests
from streamlit_lottie import st_lottie

# --- PAGE CONFIGURATION ---
st.set_page_config(page_title="5S Eco-Tracker", layout="wide", page_icon="🏭")

# --- ASSETS (Robust Loader) ---
def load_lottieurl(url):
    try:
        r = requests.get(url, timeout=3)
        return r.json() if r.status_code == 200 else None
    except: return None

# --- ANIMATION LIBRARY ---
# 1. Happy Tree (Profit): Growing plant
anim_happy_tree = load_lottieurl("https://lottie.host/6e35574d-8651-477d-b570-56965c276b3b/22572535-373f-42a9-823c-99e582862594.json")
# 2. Pollution (Loss): Factory Smoke Emitting CO2
anim_pollution = load_lottieurl("https://lottie.host/575a66c6-1215-4688-9189-b57579621379/10839556-9141-4712-a89e-224429715783.json")
# 3. Alert: Warning Triangle
anim_alert = load_lottieurl("https://lottie.host/02008323-2895-4673-863a-4934e402802d/41838634-11d9-430c-992a-356c92d529d3.json")

# --- CUSTOM CSS ---
st.markdown("""
    <style>
    .metric-card-good {
        background-color: #1b4d3e; color: #ffffff; padding: 15px; border-radius: 10px; border-left: 5px solid #00FF00;
    }
    .metric-card-bad {
        background-color: #4d1b1b; color: #ffffff; padding: 15px; border-radius: 10px; border-left: 5px solid #FF0000;
    }
    .justification-text { font-size: 12px; color: #aaaaaa; }
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
        file = repo.get_contents("history_v5.csv", ref=st.secrets["BRANCH"])
        return pd.read_csv(StringIO(file.decoded_content.decode())), file.sha
    except: return pd.DataFrame(), None

def save_data(repo, df, sha):
    try:
        csv_content = df.to_csv(index=False)
        msg = "Daily Update" if sha else "Initial Commit"
        if sha: repo.update_file("history_v5.csv", msg, csv_content, sha, branch=st.secrets["BRANCH"])
        else: repo.create_file("history_v5.csv", msg, csv_content, branch=st.secrets["BRANCH"])
        return True
    except: return False

# --- SIDEBAR: SETTINGS ---
with st.sidebar:
    st.header("⚙️ Plant Settings")
    with st.expander("Design Data (Reference)", expanded=False):
        DESIGN_HEAT_RATE = st.number_input("Design HR (kcal/kWh)", value=2250.0, step=10.0)
        TARGET_HEAT_RATE = st.number_input("PAT Target HR", value=2350.0, step=10.0)
        DESIGN_MS_TEMP = st.number_input("Design MS Temp", value=540.0)
        DESIGN_VACUUM = st.number_input("Design Vacuum", value=-0.92)
        DESIGN_FG_TEMP = st.number_input("Design FG Temp", value=130.0)

    st.header("📝 Daily Log")
    with st.form("daily_input"):
        date_input = st.date_input("Date", datetime.now())
        gross_gen_mu = st.number_input("Gross Gen (MU)", value=12.0, min_value=0.0, step=0.1)
        st.markdown("---")
        st.markdown("**5S Parameters**")
        ms_temp = st.number_input("MS Temp (°C)", value=535.0, step=1.0)
        vacuum = st.number_input("Vacuum (kg/cm2)", value=-0.90, max_value=0.0, step=0.01)
        fg_temp = st.number_input("APH Out Temp (°C)", value=135.0, step=1.0)
        sh_spray = st.number_input("Total Spray (TPH)", value=15.0, step=1.0)
        coal_gcv = st.number_input("Coal GCV", value=3600.0, step=10.0)
        
        submitted = st.form_submit_button("🚀 Analyze Impact")

# --- LOGIC ENGINE ---
if submitted or True:
    # 1. Heat Rate Waterfall Calculation
    loss_ms = max(0, (DESIGN_MS_TEMP - ms_temp) * 1.2)
    loss_vac = max(0, ((vacuum - DESIGN_VACUUM) / 0.01) * 18) if vacuum > DESIGN_VACUUM else 0
    loss_fg = max(0, (fg_temp - DESIGN_FG_TEMP) * 1.5)
    loss_spray = (sh_spray) * 2.0
    loss_constant = 50.0
    calculated_actual_hr = DESIGN_HEAT_RATE + loss_ms + loss_vac + loss_fg + loss_spray + loss_constant

    # 2. Savings Calculations
    gross_gen_units = gross_gen_mu * 1_000_000
    hr_diff_vs_target = TARGET_HEAT_RATE - calculated_actual_hr
    total_kcal_saved = hr_diff_vs_target * gross_gen_units

    # PAT ESCerts (1 MTOE = 10,000,000 kcal)
    escerts = total_kcal_saved / 10_000_000

    # Carbon Credits
    coal_saved_kg = total_kcal_saved / coal_gcv if coal_gcv > 0 else 0
    carbon_credits = (coal_saved_kg / 1000) * 1.7 

    # Tree Logic: 1 Tree absorbs ~25kg (0.025 Tons) CO2 per year. 
    # So 1 Ton CO2 = 40 Trees.
    trees_impact = abs(carbon_credits) * 40 

    # Financials
    ESCERT_PRICE = 1000
    CARBON_PRICE = 500
    COAL_PRICE = 4.5
    monetary_total = (escerts * ESCERT_PRICE) + (carbon_credits * CARBON_PRICE) + (coal_saved_kg * COAL_PRICE)

    # --- DASHBOARD HEADER ---
    st.title("🏭 Smart 5S & Efficiency Dashboard")
    
    # --- ANIMATED HEADER BANNER ---
    col_anim, col_msg = st.columns([1, 4])
    with col_anim:
        # ANIMATION LOGIC: Pollution if loss, Tree if profit
        if monetary_total >= 0:
            if anim_happy_tree: st_lottie(anim_happy_tree, height=150, key="anim_main")
        else:
            if anim_pollution: st_lottie(anim_pollution, height=150, key="anim_main")

    with col_msg:
        if monetary_total >= 0:
            st.markdown(f"""
            <div class="metric-box" style="background-color: #004d00; border: 2px solid #00ff00;">
                <h2 style="color: white; margin:0;">💰 PROFIT: ₹ {monetary_total:,.0f}</h2>
                <p style="color: #ccffcc;">Great Job! Plant efficiency is optimizing profits.</p>
            </div>
            """, unsafe_allow_html=True)
        else:
            st.markdown(f"""
            <div class="metric-box" style="background-color: #5a0000; border: 2px solid #ff4b4b;">
                <h2 style="color: white; margin:0;">🔥 LOSS: ₹ {monetary_total:,.0f}</h2>
                <p style="color: #ffcccc;">Alert! Deviation from design is burning money.</p>
            </div>
            """, unsafe_allow_html=True)

    # --- TABS FOR DETAILS ---
    tab1, tab2, tab3 = st.tabs(["🌱 Environment (Trees & CO2)", "📊 Financials & ESCerts", "🔧 Root Cause Analysis"])

    # TAB 1: ENVIRONMENT
    with tab1:
        c1, c2 = st.columns(2)
        with c1:
            st.subheader("Carbon Impact")
            st.metric("CO2 Emissions vs Baseline", f"{carbon_credits:,.2f} Tons", 
                     delta_color="normal" if carbon_credits > 0 else "inverse")
            
            # The Justification Expander
            with st.expander("ℹ️ How is this calculated?"):
                st.markdown("""
                * **Base Logic:** Coal saved = (Heat Rate Diff × Generation) / GCV.
                * **Emission Factor:** We assume **1.7 Tons CO2** is emitted per 1 Ton of Indian Coal burned.
                """)

        with c2:
            st.subheader("Bio-Equivalent")
            if carbon_credits < 0:
                st.markdown(f"### 🪓 {trees_impact:,.0f} Trees")
                st.error("Today's excess emissions are equivalent to negating the annual carbon absorption of this many mature trees.")
            else:
                st.markdown(f"### 🌲 {trees_impact:,.0f} Trees")
                st.success("Today's efficiency saved the equivalent of planting this many trees!")
            
            with st.expander("ℹ️ Tree Logic Justification"):
                st.markdown("""
                * **Nature's Rate:** A mature tree absorbs approx **25kg of CO2 per year**.
                * **Calculation:** `Excess CO2 (kg) / 25 kg = Trees Required`.
                * *Source: EE.A / Arbor Day Foundation data.*
                """)

    # TAB 2: FINANCIALS
    with tab2:
        c1, c2 = st.columns([2, 1])
        with c1:
            # SPEEDOMETER (Gauge)
            fig_gauge = go.Figure(go.Indicator(
                mode = "gauge+number+delta",
                value = calculated_actual_hr,
                domain = {'x': [0, 1], 'y': [0, 1]},
                title = {'text': "Station Heat Rate (kcal/kWh)"},
                delta = {'reference': TARGET_HEAT_RATE, 'increasing': {'color': "red"}},
                gauge = {
                    'axis': {'range': [2000, 2600]},
                    'bar': {'color': "#222"},
                    'steps': [
                        {'range': [2000, TARGET_HEAT_RATE], 'color': "#00cc00"},
                        {'range': [TARGET_HEAT_RATE, 2600], 'color': "#cc0000"}],
                    'threshold': {'line': {'color': "white", 'width': 4}, 'thickness': 0.75, 'value': TARGET_HEAT_RATE}}
            ))
            st.plotly_chart(fig_gauge, width="stretch")
        
        with c2:
            st.metric("PAT ESCerts", f"{escerts:.2f}", help="1 ESCert = 10 GCal Energy Saved")
            st.metric("Est. Value", f"₹ {escerts * ESCERT_PRICE:,.0f}")
            
            with st.expander("ℹ️ ESCert Formula"):
                st.latex(r'''ESCerts = \frac{(TargetHR - ActualHR) \times Gen(kWh)}{10,000,000}''')
                st.caption("As per BEE PAT Notification (1 MTOE = 10 Gcal)")

    # TAB 3: ROOT CAUSE (TECHNICAL)
    with tab3:
        st.subheader("Why are we losing efficiency?")
        
        # 1. Bar Chart
        fig_dev = go.Figure()
        fig_dev.add_trace(go.Bar(
            x=["MS Temp", "Vacuum", "Flue Gas", "Spray"],
            y=[loss_ms, loss_vac, loss_fg, loss_spray],
            marker_color=['#FF5252' if x > 0 else '#4CAF50' for x in [loss_ms, loss_vac, loss_fg, loss_spray]]
        ))
        fig_dev.update_layout(title="Heat Rate Loss Breakdown (kcal/kWh)", template="plotly_dark", height=300)
        st.plotly_chart(fig_dev, width="stretch")

        # 2. Action Plan
        st.subheader("🛠️ Corrective Actions (5S)")
        c1, c2, c3 = st.columns(3)
        if loss_vac > 10:
            c1.error(f"Vacuum Loss: {loss_vac:.0f} kcal")
            c1.markdown("👉 **Action:** Check Air Ingress / Clean Condenser Tubes")
        else:
            c1.success("Vacuum: Normal")
            
        if loss_fg > 10:
            c2.error(f"APH Loss: {loss_fg:.0f} kcal")
            c2.markdown("👉 **Action:** Soot Blowing Required / Check APH Seal")
        else:
            c2.success("Flue Gas: Normal")
            
        if loss_ms > 10:
            c3.error(f"Temp Loss: {loss_ms:.0f} kcal")
            c3.markdown("👉 **Action:** Check Burner Tilt / Mill Fineness")
        else:
            c3.success("MS Temp: Normal")

    # --- SAVE ---
    repo = init_github()
    if repo and st.button("💾 Save to History"):
        df, sha = load_data(repo)
        new_row = pd.DataFrame([{
            "Date": str(date_input), "HR": calculated_actual_hr, 
            "ESCert": escerts, "Profit": monetary_total
        }])
        if not df.empty:
            df = pd.concat([df, new_row], ignore_index=True).drop_duplicates(subset=["Date"], keep='last')
        else: df = new_row
        
        if save_data(repo, df, sha): st.success("Saved!")
