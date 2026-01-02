import streamlit as st
import plotly.graph_objects as go
import pandas as pd
from github import Github
from io import StringIO
from datetime import datetime
import requests
from streamlit_lottie import st_lottie

# --- CONFIGURATION ---
st.set_page_config(page_title="Power Plant 5S Eco-Dashboard", layout="wide", page_icon="🏭")

# --- ASSETS (Robust Loader) ---
def load_lottieurl(url):
    try:
        r = requests.get(url, timeout=5)
        if r.status_code != 200:
            return None
        return r.json()
    except:
        return None

# Load animations (Using stable host links)
anim_profit = load_lottieurl("https://lottie.host/6e35574d-8651-477d-b570-56965c276b3b/22572535-373f-42a9-823c-99e582862594.json")
anim_loss = load_lottieurl("https://lottie.host/02008323-2895-4673-863a-4934e402802d/41838634-11d9-430c-992a-356c92d529d3.json")
anim_factory = load_lottieurl("https://lottie.host/575a66c6-1215-4688-9189-b57579621379/10839556-9141-4712-a89e-224429715783.json")

# --- GITHUB CONNECTION ---
def init_github():
    try:
        if "GITHUB_TOKEN" in st.secrets:
            token = st.secrets["GITHUB_TOKEN"]
            repo_name = st.secrets["REPO_NAME"]
            g = Github(token)
            repo = g.get_repo(repo_name)
            return repo
    except: return None
    return None

def load_data(repo):
    if not repo:
         return pd.DataFrame(columns=["Date", "Gross_MU", "Heat_Rate", "Calc_5S_Score", "ESCert_Qty", "Total_Savings_INR"]), None
    try:
        file = repo.get_contents("history_v3.csv", ref=st.secrets["BRANCH"])
        csv_content = file.decoded_content.decode()
        return pd.read_csv(StringIO(csv_content)), file.sha
    except:
        return pd.DataFrame(columns=["Date", "Gross_MU", "Heat_Rate", "Calc_5S_Score", "ESCert_Qty", "Total_Savings_INR"]), None

def save_data(repo, df, sha):
    try:
        csv_content = df.to_csv(index=False)
        if sha:
            repo.update_file("history_v3.csv", "Daily Update", csv_content, sha, branch=st.secrets["BRANCH"])
        else:
            repo.create_file("history_v3.csv", "Initial Commit", csv_content, branch=st.secrets["BRANCH"])
        return True
    except: return False

# --- MAIN APP LAYOUT ---

c1, c2 = st.columns([1, 4])
with c1: 
    if anim_factory:
        st_lottie(anim_factory, height=100, key="factory")
    else:
        st.markdown("# 🏭")
with c2: 
    st.title("🏭 Smart 5S & Efficiency Dashboard")
    st.markdown("##### *Digitizing 5S: From Cleaning to Carbon Credits*")

# ==========================================
# SIDEBAR: CONFIGURATION & INPUTS
# ==========================================

with st.sidebar:
    st.header("⚙️ Reference Configuration")
    with st.expander("Step 1: Set Design & Targets", expanded=False):
        st.markdown("**1. Design Heat Rate (OEM):**")
        DESIGN_HEAT_RATE = st.number_input("Design HR (kcal/kWh)", value=2250.0, step=10.0, help="The theoretical best HR from the BHEL/OEM manual.")
        
        st.markdown("**2. PAT Target (BEE):**")
        TARGET_HEAT_RATE = st.number_input("Govt Target HR (kcal/kWh)", value=2350.0, step=10.0, help="The target assigned to you for PAT Cycle.")
        
        st.markdown("**3. Base Parameters (Design):**")
        DESIGN_MS_TEMP = st.number_input("Design MS Temp (°C)", value=540.0)
        DESIGN_VACUUM = st.number_input("Design Vacuum (kg/cm2)", value=-0.92)
        DESIGN_FG_TEMP = st.number_input("Design FG Temp (°C)", value=130.0)

    st.header("📝 Daily Log Sheet")
    with st.form("daily_input"):
        date_input = st.date_input("Date", datetime.now())
        gross_gen_mu = st.number_input("Gross Generation (MU)", value=12.0, min_value=0.0)
        
        st.markdown("---")
        st.markdown("**5S Parameters (Today's Avg)**")
        # Note: No min/max limits here to allow for startups/shutdowns logic
        ms_temp = st.number_input("Main Steam Temp (°C)", value=535.0)
        vacuum = st.number_input("Condenser Vacuum (kg/cm2)", value=-0.90, max_value=0.0)
        fg_temp = st.number_input("Flue Gas Temp APH Out (°C)", value=135.0)
        
        st.markdown("**Boiler Cleaning (Soot/Ash)**")
        sh_spray = st.number_input("Superheater Spray (TPH)", value=10.0)
        rh_spray = st.number_input("Reheater Spray (TPH)", value=5.0)
        
        st.markdown("**Fuel Quality**")
        coal_gcv = st.number_input("Coal GCV (kcal/kg)", value=3600.0)
        
        submitted = st.form_submit_button("🚀 Calculate Results")

# ==========================================
# CALCULATION LOGIC
# ==========================================

# 1. DEVIATION CALCULATIONS (Heat Rate Waterfall)
# We start from DESIGN and add penalties to reach ACTUAL.

# MS Temp Penalty (Approx 1.2 kcal per deg deviation)
dev_ms = DESIGN_MS_TEMP - ms_temp
loss_ms = max(0, dev_ms * 1.2)

# Vacuum Penalty (Approx 18 kcal per 0.01 deviation)
dev_vac = vacuum - DESIGN_VACUUM 
loss_vac = max(0, (dev_vac / 0.01) * 18) if dev_vac > 0 else 0

# Flue Gas Penalty (Approx 1.5 kcal per deg deviation)
dev_fg = fg_temp - DESIGN_FG_TEMP
loss_fg = max(0, dev_fg * 1.5)

# Spray Penalty (Enthalpy loss ~2 kcal per TPH)
loss_spray = (sh_spray + rh_spray) * 2.0

# Unaccounted/Constant Losses (Radiation, Blowdown etc - Fixed assumption)
loss_constant = 50.0 

# FINAL CALCULATED HEAT RATE
calculated_actual_hr = DESIGN_HEAT_RATE + loss_ms + loss_vac + loss_fg + loss_spray + loss_constant

# 2. 5S SCORE CALCULATION
# 100 Points = Zero Controllable Loss.
total_controllable_loss = loss_ms + loss_vac + loss_fg + loss_spray
# Formula: Deduct 1 point for every 2 kcal deviation
calc_5s_score = max(0, 100 - (total_controllable_loss / 2))

# 3. REGULATORY SAVINGS (vs TARGET)
gross_gen_units = gross_gen_mu * 1_000_000
hr_diff_vs_target = TARGET_HEAT_RATE - calculated_actual_hr

# PAT ESCerts (1 MTOE = 10,000,000 kcal)
total_kcal_saved = hr_diff_vs_target * gross_gen_units
escerts = total_kcal_saved / 10_000_000

# Carbon Credits
# Coal saved (kg) = Heat Saved (kcal) / GCV
coal_saved_kg = total_kcal_saved / coal_gcv if coal_gcv > 0 else 0
carbon_credits = (coal_saved_kg / 1000) * 1.7 # 1.7 tCO2/tCoal

# 4. FINANCIALS (Estimates)
ESCERT_PRICE = 1000
CARBON_PRICE = 500
COAL_PRICE = 4500
monetary_pat = escerts * ESCERT_PRICE
monetary_carbon = carbon_credits * CARBON_PRICE
monetary_fuel = (coal_saved_kg / 1000) * COAL_PRICE
total_savings = monetary_pat + monetary_carbon + monetary_fuel

# ==========================================
# VISUALIZATION
# ==========================================

st.markdown("---")

# A. SCORECARDS
c1, c2, c3, c4 = st.columns(4)

# Heat Rate
c1.metric("Calculated Heat Rate", f"{calculated_actual_hr:.0f}", f"{calculated_actual_hr - DESIGN_HEAT_RATE:.0f} > Design", delta_color="inverse")

# 5S Score
c2.metric("Auto-5S Score", f"{calc_5s_score:.1f}/100", "Based on Parameters")

# ESCerts
if escerts > 0:
    c3.metric("PAT ESCerts", f"{escerts:.2f}", "Earned")
else:
    c3.metric("PAT ESCerts", f"{escerts:.2f}", "Penalty Risk", delta_color="inverse")

# Carbon Credits
c4.metric("Carbon Credits", f"{carbon_credits:.2f}", "tCO2 Avoided")

# B. HEAT RATE WATERFALL & ANIMATION
st.subheader("📉 Heat Rate Deviation Analysis (The 'Why')")
col_chart, col_anim = st.columns([2, 1])

with col_chart:
    # Bar Chart for Deviations
    fig_dev = go.Figure()
    fig_dev.add_trace(go.Bar(
        x=["MS Temp Loss", "Vacuum Loss", "Flue Gas Loss", "Spray Loss"],
        y=[loss_ms, loss_vac, loss_fg, loss_spray],
        marker_color='#FF4B4B',
        text=[f"{loss_ms:.0f}", f"{loss_vac:.0f}", f"{loss_fg:.0f}", f"{loss_spray:.0f}"],
        textposition='auto'
    ))
    fig_dev.update_layout(
        title="Efficiency Losses (kcal/kWh) - Lower is Better", 
        yaxis_title="Heat Rate Loss", 
        template="plotly_dark",
        height=350
    )
    st.plotly_chart(fig_dev, use_container_width=True)

with col_anim:
    st.markdown("### Daily Financial Impact")
    
    if total_savings > 0:
        if anim_profit:
            st_lottie(anim_profit, height=200, key="win")
        else:
            st.markdown("# 🌳💰")
        st.success(f"**Profit: ₹ {total_savings:,.0f}**")
        
    else:
        if anim_loss:
            st_lottie(anim_loss, height=200, key="lose")
        else:
            st.markdown("# ⚠️🔥")
        st.error(f"**Loss: ₹ {total_savings:,.0f}**")

# C. EXPLANATION
with st.expander("ℹ️ How Reference Values are Used?"):
    st.markdown(f"""
    1. **Design HR ({DESIGN_HEAT_RATE}):** We compare today's performance against this to calculate the **Losses** (Red Bars). 
       * *Formula:* Actual = Design + (Vacuum Loss + Temp Loss + ...).
    2. **PAT Target ({TARGET_HEAT_RATE}):** We compare the Calculated Actual against this to determine **ESCerts**.
       * *Formula:* Savings = (Target - Actual) × Generation.
    """)

# D. GITHUB SAVE BUTTON
repo = init_github()
if repo:
    if st.button("💾 Save Data to History"):
        df_history, sha = load_data(repo)
        new_row = pd.DataFrame([{
            "Date": str(date_input),
            "Gross_MU": gross_gen_mu,
            "Heat_Rate": calculated_actual_hr,
            "Calc_5S_Score": calc_5s_score,
            "ESCert_Qty": escerts,
            "Total_Savings_INR": total_savings
        }])
        
        if not df_history.empty:
            df_updated = pd.concat([df_history, new_row], ignore_index=True)
            df_updated.drop_duplicates(subset=["Date"], keep='last', inplace=True)
        else:
            df_updated = new_row
            
        if save_data(repo, df_updated, sha):
            st.success("✅ Saved Successfully! Refresh the page to update history.")
        else:
            st.error("❌ Failed to save. Check permissions.")
else:
    st.warning("GitHub not connected. Check your Secrets.")
