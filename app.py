import streamlit as st
import plotly.graph_objects as go
import pandas as pd

# --- CONFIGURATION & STYLING ---
st.set_page_config(page_title="Power Plant 5S Eco-Dashboard", layout="wide", page_icon="⚡")

# Custom CSS for "Eye-Opening" Animations and Dark Mode
st.markdown("""
    <style>
    .big-font { font-size: 24px !important; font-weight: bold; }
    .profit { color: #00FF00; font-size: 40px; font-weight: bold; animation: pulse 2s infinite; }
    .loss { color: #FF0000; font-size: 40px; font-weight: bold; animation: shake 0.5s; }
    
    @keyframes pulse {
        0% { transform: scale(1); }
        50% { transform: scale(1.05); }
        100% { transform: scale(1); }
    }
    
    @keyframes shake {
        0% { transform: translate(1px, 1px) rotate(0deg); }
        10% { transform: translate(-1px, -2px) rotate(-1deg); }
        20% { transform: translate(-3px, 0px) rotate(1deg); }
        30% { transform: translate(3px, 2px) rotate(0deg); }
        100% { transform: translate(1px, -2px) rotate(-1deg); }
    }
    </style>
    """, unsafe_allow_html=True)

# --- SIDEBAR: INPUT PARAMETERS ---
st.sidebar.header("🏭 Plant Daily Input")
st.sidebar.markdown("Enter today's operational data:")

# Defaults set to typical 500MW unit figures
gross_gen_mu = st.sidebar.number_input("Gross Generation (MU)", value=12.0, step=0.1)
actual_aux_power = st.sidebar.number_input("Actual Aux Power (%)", value=6.50, step=0.01)
actual_heat_rate = st.sidebar.number_input("Actual Station Heat Rate (kcal/kWh)", value=2350, step=1)
coal_gcv = st.sidebar.number_input("Coal GCV (kcal/kg)", value=3800, step=10)

st.sidebar.markdown("---")
st.sidebar.header("🎯 Targets (Baseline)")
target_aux_power = st.sidebar.number_input("Target Aux Power (%)", value=6.00, step=0.01)
target_heat_rate = st.sidebar.number_input("Target Heat Rate (kcal/kWh)", value=2300, step=1)

# --- CALCULATIONS ---

# 1. Energy Calculations
gross_gen_kwh = gross_gen_mu * 1_000_000
aux_diff_percent = target_aux_power - actual_aux_power
aux_power_saved_kwh = (aux_diff_percent / 100) * gross_gen_kwh

# 2. PAT (ESCert) Calculations
# 1 ESCert = 1 MTOE = 10 million kcal
heat_rate_diff = target_heat_rate - actual_heat_rate # Positive is good (Lower actual than target)
total_heat_saved_kcal = heat_rate_diff * gross_gen_kwh
escerts_earned = total_heat_saved_kcal / 10_000_000 

# 3. Carbon Credit Calculations
# Basic formula: Heat Saved -> Coal Saved -> CO2 Saved
# Coal Saved (kg) = Total Heat Saved (kcal) / GCV (kcal/kg)
coal_saved_kg = total_heat_saved_kcal / coal_gcv if coal_gcv > 0 else 0
coal_saved_tons = coal_saved_kg / 1000
# Carbon Emission Factor: Approx 1.7 tons CO2 per ton of Indian Coal (varies, but standard estimate)
co2_avoided_tons = coal_saved_tons * 1.7
carbon_credits_earned = co2_avoided_tons # 1 Credit = 1 Ton CO2

# --- DASHBOARD LAYOUT ---

st.title("⚡ 5S Smart Energy Dashboard")
st.markdown("### Tracking the Financial Impact of Cleanliness & Order")

# Top Level Metrics using Columns
col1, col2, col3 = st.columns(3)

with col1:
    st.markdown("### 🔌 Aux Power Savings")
    if aux_power_saved_kwh >= 0:
        st.markdown(f'<p class="profit">+{aux_power_saved_kwh:,.0f} kWh</p>', unsafe_allow_html=True)
        st.success("✅ Target Achieved!")
    else:
        st.markdown(f'<p class="loss">{aux_power_saved_kwh:,.0f} kWh</p>', unsafe_allow_html=True)
        st.error("⚠️ High Consumption")

with col2:
    st.markdown("### 📜 PAT ESCerts (MTOE)")
    if escerts_earned >= 0:
        st.markdown(f'<p class="profit">+{escerts_earned:.4f} Certs</p>', unsafe_allow_html=True)
        st.caption("1 Cert = 10 Million Kcal Saved")
    else:
        st.markdown(f'<p class="loss">{escerts_earned:.4f} Certs</p>', unsafe_allow_html=True)
        st.caption("Penalty Zone")

with col3:
    st.markdown("### 🌍 Carbon Credits ($tCO_2$)")
    if carbon_credits_earned >= 0:
        st.markdown(f'<p class="profit">+{carbon_credits_earned:.2f} Credits</p>', unsafe_allow_html=True)
        st.caption("1 Credit = 1 Ton CO2 Avoided")
    else:
        st.markdown(f'<p class="loss">{carbon_credits_earned:.2f} Credits</p>', unsafe_allow_html=True)
        st.caption("Excess Emissions")

st.markdown("---")

# --- ANIMATED GAUGES ---
st.subheader("📊 Live Performance Indicators")
c1, c2 = st.columns(2)

# Gauge 1: Station Heat Rate
fig_hr = go.Figure(go.Indicator(
    mode = "gauge+number+delta",
    value = actual_heat_rate,
    domain = {'x': [0, 1], 'y': [0, 1]},
    title = {'text': "Station Heat Rate (kcal/kWh)"},
    delta = {'reference': target_heat_rate, 'increasing': {'color': "red"}, 'decreasing': {'color': "green"}},
    gauge = {
        'axis': {'range': [2000, 2600]},
        'bar': {'color': "lightgray"},
        'steps': [
            {'range': [2000, target_heat_rate], 'color': "lightgreen"},
            {'range': [target_heat_rate, 2600], 'color': "salmon"}],
        'threshold': {
            'line': {'color': "red", 'width': 4},
            'thickness': 0.75,
            'value': target_heat_rate}}))
c1.plotly_chart(fig_hr, use_container_width=True)

# Gauge 2: Aux Power
fig_aux = go.Figure(go.Indicator(
    mode = "gauge+number+delta",
    value = actual_aux_power,
    domain = {'x': [0, 1], 'y': [0, 1]},
    title = {'text': "Auxiliary Power (%)"},
    delta = {'reference': target_aux_power, 'increasing': {'color': "red"}, 'decreasing': {'color': "green"}},
    gauge = {
        'axis': {'range': [4, 10]},
        'bar': {'color': "lightgray"},
        'steps': [
            {'range': [4, target_aux_power], 'color': "lightgreen"},
            {'range': [target_aux_power, 10], 'color': "salmon"}],
        'threshold': {
            'line': {'color': "red", 'width': 4},
            'thickness': 0.75,
            'value': target_aux_power}}))
c2.plotly_chart(fig_aux, use_container_width=True)

# --- MONETARY IMPACT (Hypothetical) ---
st.markdown("### 💰 Estimated Daily Financial Impact")
# Assumptions:
# ESCert Price: ~ ₹1000 per cert (Variable)
# Carbon Credit: ~ ₹500 per credit (Voluntary market, variable)
# Electricity Cost: ~ ₹3.50 per unit (Variable Cost)

escert_price = 1000
carbon_price = 500
unit_cost = 3.50

monetary_aux = aux_power_saved_kwh * unit_cost
monetary_pat = escerts_earned * escert_price
monetary_carbon = carbon_credits_earned * carbon_price
total_monetary = monetary_aux + monetary_pat + monetary_carbon

st.info(f"""
Based on current market estimates:
* **Direct Power Savings:** ₹ {monetary_aux:,.2f}
* **Potential ESCert Value:** ₹ {monetary_pat:,.2f}
* **Potential Carbon Credit Value:** ₹ {monetary_carbon:,.2f}
* **TOTAL DAILY IMPACT:** ₹ {total_monetary:,.2f}
""")

# --- DOCUMENTATION LINKS ---
with st.expander("📚 Reference Documents & Legal Framework"):
    st.markdown("""
    * **PAT Scheme (BEE):** [Bureau of Energy Efficiency - PAT Details](https://beeindia.gov.in/)
    * **Energy Conservation Act, 2001:** Legal basis for PAT.
    * **Carbon Credit Trading Scheme (CCTS), 2023:** [Ministry of Power Notification](https://powermin.gov.in/)
    * **5S Methodology:** "Sort, Set in Order, Shine, Standardize, Sustain"
    """)
