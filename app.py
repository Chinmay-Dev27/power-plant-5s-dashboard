import streamlit as st
import plotly.graph_objects as go
import pandas as pd
from github import Github
from io import StringIO
from datetime import datetime

# --- CONFIGURATION ---
st.set_page_config(page_title="Power Plant 5S Tracker Pro", layout="wide", page_icon="🏭")

# --- CUSTOM CSS ---
st.markdown("""
    <style>
    .metric-card { background-color: #262730; padding: 15px; border-radius: 5px; border-left: 5px solid #FF4B4B; }
    .good-metric { border-left: 5px solid #00FF00; }
    </style>
    """, unsafe_allow_html=True)

# --- GITHUB CONNECTION ---
def init_github():
    """Connect to GitHub using Secrets"""
    try:
        token = st.secrets["GITHUB_TOKEN"]
        repo_name = st.secrets["REPO_NAME"]
        g = Github(token)
        repo = g.get_repo(repo_name)
        return repo
    except Exception as e:
        st.error(f"GitHub Connection Error: {e}. Check your Secrets.")
        return None

def load_data(repo):
    """Load history.csv from GitHub"""
    try:
        file = repo.get_contents("history.csv", ref=st.secrets["BRANCH"])
        csv_content = file.decoded_content.decode()
        return pd.read_csv(StringIO(csv_content)), file.sha
    except:
        return pd.DataFrame(columns=["Date", "Gross_MU", "Aux_Power", "Heat_Rate", "ESCert_Qty", "Carbon_Credits", "Total_Savings_INR"]), None

def save_data(repo, df, sha):
    """Push updated dataframe back to GitHub"""
    try:
        csv_content = df.to_csv(index=False)
        if sha:
            repo.update_file("history.csv", "Daily Update", csv_content, sha, branch=st.secrets["BRANCH"])
        else:
            repo.create_file("history.csv", "Initial Commit", csv_content, branch=st.secrets["BRANCH"])
        return True
    except Exception as e:
        st.error(f"Save Failed: {e}")
        return False

# --- MAIN APP ---

st.title("🏭 5S & Efficiency Daily Tracker")
st.markdown("### Linking Housekeeping (5S) to Profitability & Regulatory Credits")

# 1. LOAD HISTORY
repo = init_github()
if repo:
    df_history, file_sha = load_data(repo)
else:
    st.stop()

# 2. SIDEBAR INPUTS (FIXED: Added min_value=0.0 to prevent locking)
st.sidebar.header("📝 Enter Today's Data")
date_input = st.sidebar.date_input("Date", datetime.now())

with st.sidebar.expander("⚡ Generation Parameters", expanded=True):
    # FIXED: strictly using keyword arguments (value=..., min_value=...)
    gross_gen_mu = st.sidebar.number_input("Gross Generation (MU)", value=12.0, min_value=0.0, step=0.1)
    act_aux = st.sidebar.number_input("Aux Power (%)", value=6.50, min_value=0.0, step=0.01)
    act_hr = st.sidebar.number_input("Station Heat Rate (kcal/kWh)", value=2350.0, min_value=0.0, step=1.0)
    coal_gcv = st.sidebar.number_input("Coal GCV", value=3800.0, min_value=0.0, step=10.0)

with st.sidebar.expander("🔧 5S & Maintenance Inputs", expanded=True):
    leaks_count = st.sidebar.number_input("Active Steam Leaks (Count)", value=0, min_value=0, step=1)
    oil_cons = st.sidebar.number_input("Oil Consumption (KL)", value=2.5, min_value=0.0, step=0.1)
    s5_score = st.sidebar.slider("Daily 5S Audit Score", 0, 100, 75)

# --- CALCULATIONS ---

# Targets
TARGET_AUX = 6.0
TARGET_HR = 2300
COST_UNIT = 3.50
COST_COAL_TON = 4500
COST_OIL_KL = 60000 
LEAK_COST_DAY = 8000 

# A. Regulatory Calculations (PAT & Carbon)
gross_gen_kwh = gross_gen_mu * 1_000_000

# PAT (ESCert): 1 ESCert = 10 Million Kcal saved vs Baseline
hr_diff_val = TARGET_HR - act_hr # Positive means we are better than target
total_heat_saved_kcal = hr_diff_val * gross_gen_kwh
escerts_earned = total_heat_saved_kcal / 10_000_000 

# Carbon Credits: Coal Saved -> CO2 Avoided
# Coal Consumption Difference (kg)
coal_saved_kg = total_heat_saved_kcal / coal_gcv if coal_gcv > 0 else 0
coal_saved_tons = coal_saved_kg / 1000
# Emission Factor: ~1.7 Tons CO2 per Ton Coal
carbon_credits_earned = coal_saved_tons * 1.7 

# B. Financial Calculations
aux_diff_units = ((TARGET_AUX - act_aux)/100) * gross_gen_kwh
aux_saving_inr = aux_diff_units * COST_UNIT
coal_saving_inr = coal_saved_tons * COST_COAL_TON
oil_saving_inr = (1.0 - oil_cons) * COST_OIL_KL
leak_loss_inr = leaks_count * LEAK_COST_DAY

# Total INR
total_daily_saving = aux_saving_inr + coal_saving_inr + oil_saving_inr - leak_loss_inr

# --- DISPLAY SECTION ---

# 1. REGULATORY & ENVIRONMENTAL (Restored)
st.subheader("🌍 Regulatory & Environmental Impact")
c1, c2, c3 = st.columns(3)

with c1:
    st.markdown("**📜 PAT Scheme (ESCert)**")
    if escerts_earned > 0:
        st.success(f"+ {escerts_earned:.4f} ESCerts")
        st.caption("✅ Earned (Efficiency > Target)")
    else:
        st.error(f"{escerts_earned:.4f} ESCerts")
        st.caption("⚠️ Penalty Risk (Efficiency < Target)")

with c2:
    st.markdown("**🌳 Carbon Trading (CCTS)**")
    if carbon_credits_earned > 0:
        st.success(f"+ {carbon_credits_earned:.2f} Credits")
        st.caption(f"Equivalent to {carbon_credits_earned:.2f} tons CO2 avoided")
    else:
        st.error(f"{carbon_credits_earned:.2f} Credits")
        st.caption("⚠️ Excess Emissions")

with c3:
    st.markdown("**💰 Total Daily Profit/Loss**")
    color = "green" if total_daily_saving > 0 else "red"
    st.markdown(f"<h2 style='color:{color}'>₹ {total_daily_saving:,.0f}</h2>", unsafe_allow_html=True)
    st.caption("Includes Fuel, Aux, Oil & Leaks")

st.markdown("---")

# 2. OPERATIONAL METRICS (Comparison with Yesterday)
st.subheader("📊 Operational Trends")

if not df_history.empty:
    last_entry = df_history.iloc[-1]
    # Handle missing columns if old CSV format
    last_hr = last_entry.get("Heat_Rate", 0)
    last_aux = last_entry.get("Aux_Power", 0)
    delta_hr = act_hr - last_hr
    delta_aux = act_aux - last_aux
else:
    last_hr, delta_hr, last_aux, delta_aux = 0, 0, 0, 0

m1, m2, m3, m4 = st.columns(4)

# Heat Rate: Lower is Better (inverse delta color)
m1.metric("Station Heat Rate", f"{act_hr} kcal/kWh", f"{delta_hr:.0f} vs Yest", delta_color="inverse")

# Aux Power: Lower is Better (inverse delta color)
m2.metric("Aux Power", f"{act_aux} %", f"{delta_aux:.2f}% vs Yest", delta_color="inverse")

# 5S Score: Higher is Better (normal delta color)
m3.metric("5S Audit Score", f"{s5_score}/100", "Daily Score")

# Leaks
m4.metric("Steam Leaks", f"{leaks_count}", f"- ₹{leak_loss_inr:,.0f} Loss", delta_color="inverse")

# --- GRAPHS ---
st.markdown("---")
col_left, col_right = st.columns([1, 1])

with col_left:
    st.subheader("📈 Carbon & ESCert History")
    if not df_history.empty and "Carbon_Credits" in df_history.columns:
        fig_env = go.Figure()
        fig_env.add_trace(go.Bar(x=df_history["Date"], y=df_history["Carbon_Credits"], name="Carbon Credits", marker_color='green'))
        fig_env.add_trace(go.Scatter(x=df_history["Date"], y=df_history["ESCert_Qty"], name="ESCerts", yaxis="y2", line=dict(color='yellow', width=3)))
        
        fig_env.update_layout(
            template="plotly_dark",
            yaxis=dict(title="Carbon Credits"),
            yaxis2=dict(title="ESCerts", overlaying="y", side="right"),
            legend=dict(x=0, y=1.1, orientation="h")
        )
        st.plotly_chart(fig_env, use_container_width=True)
    else:
        st.info("Save data to see history graphs.")

with col_right:
    st.subheader("💧 Financial Waterfall (Today)")
    waterfall_data = pd.DataFrame({
        "Measure": ["Aux Saving", "Coal Saving", "Oil Saving", "Leak Loss", "TOTAL"],
        "Amount": [aux_saving_inr, coal_saving_inr, oil_saving_inr, -leak_loss_inr, total_daily_saving]
    })
    
    fig_water = go.Figure(go.Waterfall(
        name = "20", orientation = "v",
        measure = ["relative", "relative", "relative", "relative", "total"],
        x = waterfall_data["Measure"],
        y = waterfall_data["Amount"],
        connector = {"line":{"color":"rgb(63, 63, 63)"}},
        decreasing = {"marker":{"color":"#FF4B4B"}},
        increasing = {"marker":{"color":"#00FF00"}},
        totals = {"marker":{"color":"#1E88E5"}}
    ))
    fig_water.update_layout(template="plotly_dark", height=400)
    st.plotly_chart(fig_water, use_container_width=True)

# --- SAVE BUTTON ---
if st.button("💾 Save Today's Data to GitHub"):
    new_data = {
        "Date": str(date_input),
        "Gross_MU": gross_gen_mu,
        "Aux_Power": act_aux,
        "Heat_Rate": act_hr,
        "ESCert_Qty": escerts_earned,
        "Carbon_Credits": carbon_credits_earned,
        "Total_Savings_INR": total_daily_saving
    }
    
    df_new_row = pd.DataFrame([new_data])
    # Combine and drop duplicates based on Date
    if not df_history.empty:
        df_updated = pd.concat([df_history, df_new_row], ignore_index=True)
        df_updated.drop_duplicates(subset=["Date"], keep='last', inplace=True)
    else:
        df_updated = df_new_row
    
    if save_data(repo, df_updated, file_sha):
        st.success("✅ Data Saved! Refresh page to update history.")
