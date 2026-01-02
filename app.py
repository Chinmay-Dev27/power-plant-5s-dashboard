import streamlit as st
import plotly.graph_objects as go
import plotly.express as px
import pandas as pd
from github import Github
from io import StringIO
from datetime import datetime

# --- CONFIGURATION ---
st.set_page_config(page_title="Power Plant 5S Tracker Pro", layout="wide", page_icon="🏭")

# --- CUSTOM CSS ---
st.markdown("""
    <style>
    .metric-card { background-color: #1E1E1E; padding: 20px; border-radius: 10px; border: 1px solid #333; }
    .profit { color: #00FF00; font-weight: bold; }
    .loss { color: #FF4B4B; font-weight: bold; }
    </style>
    """, unsafe_allow_html=True)

# --- GITHUB CONNECTION FUNCTIONS ---
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
        # If file doesn't exist, create an empty dataframe
        return pd.DataFrame(columns=["Date", "Gross_MU", "Aux_Power", "Heat_Rate", "Leaks_Count", "Oil_KL", "S5_Score", "Total_Savings_INR"]), None

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
st.markdown("### Linking Housekeeping (5S) to Profitability")

# 1. LOAD HISTORY
repo = init_github()
if repo:
    df_history, file_sha = load_data(repo)
else:
    st.stop()

# 2. SIDEBAR INPUTS (Today's Data)
st.sidebar.header("📝 Enter Today's Data")
date_input = st.sidebar.date_input("Date", datetime.now())

# Group 1: Generation Params
with st.sidebar.expander("⚡ Generation Parameters", expanded=True):
    gross_gen_mu = st.sidebar.number_input("Gross Generation (MU)", 12.0, step=0.1)
    act_aux = st.sidebar.number_input("Aux Power (%)", 6.50, step=0.01)
    act_hr = st.sidebar.number_input("Station Heat Rate (kcal/kWh)", 2350, step=1)
    coal_gcv = st.sidebar.number_input("Coal GCV", 3800, step=10)

# Group 2: The "Extra Ideas" (5S Impact)
with st.sidebar.expander("🔧 5S & Maintenance Inputs", expanded=True):
    leaks_count = st.sidebar.number_input("Active Steam Leaks (Count)", 0, step=1, help="Number of visible steam passings/leaks")
    oil_cons = st.sidebar.number_input("Oil Consumption (KL)", 2.5, step=0.1, help="LDO/HFO used for support")
    s5_score = st.sidebar.slider("Daily 5S Audit Score", 0, 100, 75)

# --- CALCULATIONS ---

# Constants (Assumptions for financials)
TARGET_AUX = 6.0
TARGET_HR = 2300
TARGET_OIL = 1.0 # KL/day design
COST_UNIT = 3.50 # Rs/kWh
COST_COAL_TON = 4500 # Rs/Ton approx
COST_OIL_KL = 60000 # Rs/KL approx
LEAK_COST_DAY = 8000 # Rs approx cost per medium leak per day

# 1. Aux Power Impact
aux_diff_units = ((TARGET_AUX - act_aux)/100) * (gross_gen_mu * 1_000_000)
aux_saving_inr = aux_diff_units * COST_UNIT

# 2. Heat Rate Impact (PAT)
hr_diff = TARGET_HR - act_hr
heat_saving_kcal = hr_diff * (gross_gen_mu * 1_000_000)
coal_saving_kg = heat_saving_kcal / coal_gcv
coal_saving_inr = (coal_saving_kg / 1000) * COST_COAL_TON

# 3. Extra: Steam Leaks & Oil
leak_loss_inr = leaks_count * LEAK_COST_DAY
oil_diff_kl = TARGET_OIL - oil_cons
oil_saving_inr = oil_diff_kl * COST_OIL_KL

# Total Net Benefit (vs Baseline)
total_daily_saving = aux_saving_inr + coal_saving_inr + oil_saving_inr - leak_loss_inr

# --- DISPLAY SECTION ---

# A. COMPARISON WITH YESTERDAY
st.subheader("📅 Today vs Yesterday")

if not df_history.empty:
    last_entry = df_history.iloc[-1]
    last_hr = last_entry["Heat_Rate"]
    last_s5 = last_entry["S5_Score"]
    delta_hr = act_hr - last_hr
    delta_s5 = s5_score - last_s5
else:
    last_hr, delta_hr, last_s5, delta_s5 = 0, 0, 0, 0

c1, c2, c3, c4 = st.columns(4)
c1.metric("Station Heat Rate", f"{act_hr} kcal/kWh", f"{delta_hr} vs Yest", delta_color="inverse")
c2.metric("5S Score", f"{s5_score}/100", f"{delta_s5} vs Yest")
c3.metric("Steam Leaks", f"{leaks_count}", f"Cost: ₹{leak_loss_inr:,.0f}/day", delta_color="inverse")
c4.metric("Net Financial Impact", f"₹ {total_daily_saving:,.0f}", "vs Baseline")

st.markdown("---")

# B. DETAILED IMPACT VISUALIZATION
col_left, col_right = st.columns([1, 2])

with col_left:
    st.markdown("### 💰 Financial Breakdown")
    st.write("Where are we gaining or losing money today?")
    
    waterfall_data = pd.DataFrame({
        "Measure": ["Aux Power", "Heat Rate (Coal)", "Oil Deviation", "Steam Leaks", "TOTAL"],
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
    fig_water.update_layout(title="Daily Profit/Loss Waterfall (₹)", template="plotly_dark", height=400)
    st.plotly_chart(fig_water, use_container_width=True)

with col_right:
    st.markdown("### 📈 The 5S Correlation Effect")
    if len(df_history) > 1:
        # Create a dual-axis chart to show if Better 5S = Better Heat Rate
        fig_trend = go.Figure()
        
        # Line 1: 5S Score
        fig_trend.add_trace(go.Scatter(x=df_history["Date"], y=df_history["S5_Score"], name="5S Score",
                                 line=dict(color='orange', width=2)))
        
        # Line 2: Heat Rate
        fig_trend.add_trace(go.Scatter(x=df_history["Date"], y=df_history["Heat_Rate"], name="Heat Rate",
                                 yaxis="y2", line=dict(color='cyan', width=2)))
        
        fig_trend.update_layout(
            title="Does Cleaning (5S) improve Efficiency (Heat Rate)?",
            template="plotly_dark",
            yaxis=dict(title="5S Score", range=[0, 100]),
            yaxis2=dict(title="Heat Rate", overlaying="y", side="right"),
            legend=dict(x=0, y=1.1, orientation="h")
        )
        st.plotly_chart(fig_trend, use_container_width=True)
    else:
        st.info("Start saving data to see the correlation graph here!")

# --- SAVE BUTTON ---
st.markdown("---")
if st.button("💾 Save Today's Data to History"):
    # Prepare row
    new_data = {
        "Date": str(date_input),
        "Gross_MU": gross_gen_mu,
        "Aux_Power": act_aux,
        "Heat_Rate": act_hr,
        "Leaks_Count": leaks_count,
        "Oil_KL": oil_cons,
        "S5_Score": s5_score,
        "Total_Savings_INR": total_daily_saving
    }
    
    # Append to dataframe
    df_new_row = pd.DataFrame([new_data])
    df_updated = pd.concat([df_history, df_new_row], ignore_index=True)
    
    # Remove duplicates (prevent double saving same date)
    df_updated.drop_duplicates(subset=["Date"], keep='last', inplace=True)
    
    # Push to GitHub
    if save_data(repo, df_updated, file_sha):
        st.success("✅ Data Saved Successfully to GitHub! The dashboard will update on refresh.")
        st.balloons()
