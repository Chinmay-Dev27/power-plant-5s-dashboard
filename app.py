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

# --- ANIMATION ASSETS ---
def load_lottieurl(url):
    r = requests.get(url)
    if r.status_code != 200:
        return None
    return r.json()

# Lottie Animations (Free assets)
anim_profit = load_lottieurl("https://assets5.lottiefiles.com/packages/lf20_V9t630.json") # Growing plant/money
anim_loss = load_lottieurl("https://assets10.lottiefiles.com/packages/lf20_t2yx0x1z.json") # Warning/Fire
anim_factory = load_lottieurl("https://assets8.lottiefiles.com/packages/lf20_2glqweqs.json") # Factory

# --- CUSTOM CSS ---
st.markdown("""
    <style>
    .big-metric { font-size: 28px !important; font-weight: bold; }
    .explanation { background-color: #262730; padding: 15px; border-radius: 10px; font-size: 14px; border: 1px solid #444; }
    </style>
    """, unsafe_allow_html=True)

# --- GITHUB CONNECTION ---
def init_github():
    try:
        if "GITHUB_TOKEN" in st.secrets:
            token = st.secrets["GITHUB_TOKEN"]
            repo_name = st.secrets["REPO_NAME"]
            g = Github(token)
            repo = g.get_repo(repo_name)
            return repo
    except:
        return None
    return None

def load_data(repo):
    if not repo:
         return pd.DataFrame(columns=["Date", "Gross_MU", "Heat_Rate", "Calc_5S_Score", "ESCert_Qty", "Total_Savings_INR"]), None
    try:
        file = repo.get_contents("history_v2.csv", ref=st.secrets["BRANCH"])
        csv_content = file.decoded_content.decode()
        return pd.read_csv(StringIO(csv_content)), file.sha
    except:
        return pd.DataFrame(columns=["Date", "Gross_MU", "Heat_Rate", "Calc_5S_Score", "ESCert_Qty", "Total_Savings_INR"]), None

def save_data(repo, df, sha):
    try:
        csv_content = df.to_csv(index=False)
        if sha:
            repo.update_file("history_v2.csv", "Daily Update", csv_content, sha, branch=st.secrets["BRANCH"])
        else:
            repo.create_file("history_v2.csv", "Initial Commit", csv_content, branch=st.secrets["BRANCH"])
        return True
    except:
        return False

# --- MAIN APP ---

# Header with Animation
c1, c2 = st.columns([1, 4])
with c1:
    st_lottie(anim_factory, height=100, key="factory")
with c2:
    st.title("🏭 Smart 5S & Efficiency Dashboard")
    st.markdown("##### *Digitizing 5S: From Cleaning to Carbon Credits*")

# 1. SIDEBAR: TECHNICAL PARAMETERS
st.sidebar.header("🔧 Daily Plant Readings")
st.sidebar.markdown("Input average daily values to calculate 5S Score.")

with st.sidebar.form("daily_input"):
    date_input = st.date_input("Date", datetime.now())
    
    st.markdown("### 1. Generation")
    gross_gen_mu = st.number_input("Gross Generation (MU)", value=12.0, min_value=0.0, step=0.1)
    
    st.markdown("### 2. Key 5S Indicators (Parameters)")
    # Defaults set to typical 500MW design values
    # MS Temp
    ms_temp = st.number_input("Main Steam Temp (°C)", value=535.0, step=1.0, help="Design: 540°C. Deviation indicates boiler fouling.")
    # Vacuum
    vacuum = st.number_input("Condenser Vacuum (kg/cm2)", value=-0.90, step=0.01, max_value=0.0, help="Design: -0.92. Poor vacuum = Dirty Condenser (Lack of Shine).")
    # Flue Gas
    fg_temp = st.number_input("Flue Gas Temp APH Out (°C)", value=135.0, step=1.0, help="Design: 130°C. High temp = Dirty APH/Soot.")
    # Sprays
    sh_spray = st.number_input("Superheater Spray (TPH)", value=10.0, step=1.0, help="High spray = Poor combustion/cleaning.")
    rh_spray = st.number_input("Reheater Spray (TPH)", value=5.0, step=1.0)
    
    st.markdown("### 3. Fuel")
    coal_gcv = st.number_input("Coal GCV (kcal/kg)", value=3600.0, step=10.0)
    
    submitted = st.form_submit_button("🚀 Calculate Impact")

# --- CALCULATION ENGINE ---

# A. Heat Rate Deviation Logic (The "5S Score")
# Base Design Values (Configurable)
DESIGN_MS_TEMP = 540
DESIGN_VACUUM = -0.92
DESIGN_FG_TEMP = 130
DESIGN_HEAT_RATE = 2250 # Design Heat Rate
TARGET_HEAT_RATE = 2350 # Target for PAT

# Penalties (Approximations based on thermodynamics)
# 1. MS Temp: 1 deg drop = 1.2 kcal penalty
dev_ms = DESIGN_MS_TEMP - ms_temp
loss_ms = max(0, dev_ms * 1.2) 

# 2. Vacuum: 0.01 drop = 18 kcal penalty
dev_vac = vacuum - DESIGN_VACUUM # e.g., -0.90 - (-0.92) = +0.02 deviation
loss_vac = max(0, (dev_vac / 0.01) * 18) if dev_vac > 0 else 0

# 3. Flue Gas: 1 deg rise = 1.5 kcal penalty
dev_fg = fg_temp - DESIGN_FG_TEMP
loss_fg = max(0, dev_fg * 1.5)

# 4. Sprays: Approx 1 TPH spray = 2 kcal penalty (simplified)
loss_spray = (sh_spray + rh_spray) * 2.0

# Total Maintenance/5S Related Loss
total_hr_loss = loss_ms + loss_vac + loss_fg + loss_spray

# Calculate "Actual" Heat Rate based on these losses + Baseline
actual_heat_rate = DESIGN_HEAT_RATE + total_hr_loss + 50 # +50 for other unmeasured losses

# Calculate 5S Score (Normalized 0-100)
# If loss is 0 -> Score 100. If loss is >200 kcal -> Score 0.
calc_5s_score = max(0, 100 - (total_hr_loss / 2))

# B. PAT & Carbon Logic
gross_gen_units = gross_gen_mu * 1_000_000
hr_diff = TARGET_HEAT_RATE - actual_heat_rate # Positive = Savings

# PAT: 1 ESCert = 10,000,000 kcal
total_kcal_saved = hr_diff * gross_gen_units
escerts = total_kcal_saved / 10_000_000

# Carbon: Coal Saved -> CO2
coal_saved_kg = total_kcal_saved / coal_gcv
coal_saved_tons = coal_saved_kg / 1000
carbon_credits = coal_saved_tons * 1.7 # 1.7 tons CO2 per ton coal

# Financials
ESCERT_PRICE = 1500 # Rs estimate
CARBON_PRICE = 500 # Rs estimate
COAL_PRICE = 4500 # Rs/Ton
monetary_pat = escerts * ESCERT_PRICE
monetary_carbon = carbon_credits * CARBON_PRICE
monetary_fuel = coal_saved_tons * COAL_PRICE
total_savings = monetary_pat + monetary_carbon + monetary_fuel

# --- DASHBOARD DISPLAY ---

st.markdown("---")

# 1. ANIMATED KPI ROW
col1, col2, col3, col4 = st.columns(4)

with col1:
    st.metric("Calculated Heat Rate", f"{actual_heat_rate:.0f}", f"{hr_diff:.0f} vs Target")
    st.caption("Derived from MS Temp, Vacuum & FG Temp")

with col2:
    st.metric("Auto-5S Score", f"{calc_5s_score:.1f}/100")
    # Logic: If vacuum is poor, score drops
    if loss_vac > 20:
        st.caption("⚠️ Check Condenser Cleaning")
    elif loss_fg > 20:
        st.caption("⚠️ Check APH / Soot Blow")
    else:
        st.caption("✅ Good Parameters")

with col3:
    st.metric("PAT ESCerts", f"{escerts:.2f}")
    st.caption(f"1 Cert = 10 Million kCal Saved")

with col4:
    st.metric("Carbon Credits", f"{carbon_credits:.2f}")
    st.caption("tCO2 Avoided today")

# 2. MAIN VISUALIZATION (Animation + Data)
st.markdown("### 💰 Financial & Environmental Impact")
m_col1, m_col2 = st.columns([1, 2])

with m_col1:
    # Logic for Animation: If savings positive -> Plant Growing. If negative -> Warning.
    if total_savings > 0:
        st_lottie(anim_profit, height=250, key="win")
        st.success(f"**Total Profit: ₹ {total_savings:,.0f}**")
    else:
        st_lottie(anim_loss, height=250, key="lose")
        st.error(f"**Total Loss: ₹ {total_savings:,.0f}**")

with m_col2:
    # Breakdown Bar Chart
    fig_bar = go.Figure()
    fig_bar.add_trace(go.Bar(
        y=['Fuel Savings', 'ESCert Value', 'Carbon Credit Value'],
        x=[monetary_fuel, monetary_pat, monetary_carbon],
        orientation='h',
        marker=dict(color=['#4CAF50', '#FFC107', '#2196F3'])
    ))
    fig_bar.update_layout(title="Where is the money coming from?", template="plotly_dark")
    st.plotly_chart(fig_bar, use_container_width=True)

# 3. EXPLAINER SECTION (Interactive)
with st.expander("📚 Click to understand the Calculation Logic (Reference)", expanded=False):
    st.markdown("""
    #### 1. How we calculate the "Auto-5S Score"?
    We don't ask you for a manual score. We look at your efficiency parameters:
    * **Vacuum:** Every 0.01 kg/cm² drop costs ~18 kcal/kWh. (Dirty condenser tubes? -> **Shine needed**)
    * **Flue Gas Temp:** Every 10°C rise costs ~15 kcal/kWh. (Dirty APH? -> **Shine needed**)
    * **MS Temp:** Every 10°C drop costs ~12 kcal/kWh. (Burner tilt/Soot blowing? -> **Operational 5S**)
    
    The score starts at **100**. We subtract points for every heat rate penalty.

    #### 2. How are PAT ESCerts Calculated?
    * **Formula:** `(Target HR - Actual HR) × Gen (Units) / 10,000,000`
    * **Logic:** 1 ESCert = 1 Metric Tonne Oil Equivalent (MTOE).
    * **Conversion:** 1 MTOE is legally defined as **10 Million kCal** of energy.
    
    #### 3. How are Carbon Credits Calculated?
    * **Formula:** `Coal Saved (Tons) × 1.7`
    * **Logic:** Standard Indian thermal coal emits approx **1.7 Tons of CO2** for every 1 Ton burned.
    """)

# 4. GITHUB SAVE
repo = init_github()
if repo:
    if st.button("💾 Save to History"):
        df_history, sha = load_data(repo)
        new_row = pd.DataFrame([{
            "Date": str(date_input),
            "Gross_MU": gross_gen_mu,
            "Heat_Rate": actual_heat_rate,
            "Calc_5S_Score": calc_5s_score,
            "ESCert_Qty": escerts,
            "Total_Savings_INR": total_savings
        }])
        
        if not df_history.empty:
            df_updated = pd.concat([df_history, new_row], ignore_index=True)
            df_updated.drop_duplicates(subset=["Date"], keep='last', inplace=True)
        else:
            df_updated = new_row
            
        save_data(repo, df_updated, sha)
        st.success("✅ Data Saved Successfully!")
