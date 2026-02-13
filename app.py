import streamlit as st
import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import requests
from io import StringIO, BytesIO
from github import Github, Auth
from streamlit_lottie import st_lottie
import streamlit.components.v1 as components
from fpdf import FPDF
import matplotlib.pyplot as plt
import matplotlib
import base64
import json
from functools import lru_cache
import warnings

warnings.filterwarnings('ignore')
matplotlib.use('Agg')

# ==================== CONFIGURATION ====================
st.set_page_config(
    page_title="GMR 5S Dashboard", 
    layout="wide", 
    page_icon="⚡",
    initial_sidebar_state="expanded"
)

# Import Professional Fonts
components.html("""
    <link href="https://fonts.googleapis.com/css2?family=Roboto:wght@400;500;700&family=Oswald:wght@400;600&family=Orbitron:wght@500;700&display=swap" rel="stylesheet">
""", height=0)

# ==================== ENHANCED CSS ====================
st.markdown("""
    <style>
    .stApp { 
        background: linear-gradient(135deg, #0f172a 0%, #1e293b 100%); 
        color: #ffffff; 
        font-family: 'Roboto', sans-serif; 
    }
    .stTabs [data-baseweb="tab-list"] { 
        gap: 8px; 
        background-color: rgba(255,255,255,0.05); 
        padding: 10px; 
        border-radius: 50px; 
    }
    .stTabs [data-baseweb="tab"] { 
        height: 40px; 
        white-space: pre-wrap; 
        background-color: transparent; 
        border-radius: 20px; 
        color: #ffffff; 
        font-weight: 700; 
        font-size: 16px; 
    }
    .stTabs [aria-selected="true"] { 
        background-color: #F59E0B; 
        color: white; 
    }
    .glass-card { 
        background: rgba(30, 41, 59, 0.7); 
        border: 1px solid rgba(255, 255, 255, 0.2); 
        border-radius: 12px; 
        padding: 20px; 
        margin-bottom: 15px; 
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.3); 
        text-align: center; 
        transition: transform 0.2s ease; 
    }
    .glass-card:hover { 
        transform: translateY(-2px); 
        border-color: rgba(255, 255, 255, 0.5); 
    }
    .border-good { border-top: 4px solid #4ade80; }
    .border-bad { border-top: 4px solid #f87171; }
    .border-shut { border-top: 4px solid #ffffff; }
    .border-green { border-top: 4px solid #34d399; }
    .border-solar { border-top: 4px solid #fde047; }
    .big-val { 
        font-family: 'Orbitron', sans-serif; 
        font-size: 28px; 
        font-weight: 700; 
        color: #ffffff; 
        text-shadow: 1px 1px 3px rgba(0,0,0,0.8); 
    }
    .sub-lbl { 
        font-size: 13px; 
        color: #ffffff; 
        text-transform: uppercase; 
        letter-spacing: 0.5px; 
        font-weight: 700; 
        margin-top: 5px; 
    }
    .section-header { 
        font-family: 'Oswald', sans-serif; 
        font-size: 24px; 
        color: #fcd34d; 
        margin: 20px 0 10px 0; 
        border-bottom: 1px solid #ffffff; 
        padding-bottom: 5px; 
    }
    .unit-header { 
        font-size: 15px; 
        font-weight: 800; 
        color: #ffffff; 
        margin-bottom: 10px; 
        letter-spacing: 1px;
    }
    .kpi-container {
        display: flex;
        justify-content: space-around;
        flex-wrap: wrap;
        gap: 10px;
        margin: 20px 0;
    }
    .alert-box {
        padding: 15px;
        border-radius: 8px;
        margin: 10px 0;
        font-weight: 600;
    }
    .alert-danger {
        background: rgba(239, 68, 68, 0.2);
        border-left: 4px solid #ef4444;
    }
    .alert-warning {
        background: rgba(251, 191, 36, 0.2);
        border-left: 4px solid #fbbf24;
    }
    .alert-success {
        background: rgba(16, 185, 129, 0.2);
        border-left: 4px solid #10b981;
    }
    </style>
""", unsafe_allow_html=True)

# ==================== UTILITY FUNCTIONS ====================
@lru_cache(maxsize=32)
def load_lottieurl(url):
    """Cached Lottie animation loader"""
    try:
        r = requests.get(url, timeout=2)
        return r.json() if r.status_code == 200 else None
    except:
        return None

def format_lacs(value):
    """Format currency in Indian Lacs"""
    val_lac = value / 100000
    return f"₹ {val_lac:,.2f} Lac"

def display_info(details):
    """Display expandable info section"""
    with st.expander("ℹ️ How to Read This Tab (Calculations & Logic)"):
        st.markdown(details)

# Load animations (cached)
anim_tree = load_lottieurl("https://lottie.host/6e35574d-8651-477d-b570-56965c276b3b/22572535-373f-42a9-823c-99e582862594.json")
anim_smoke = load_lottieurl("https://lottie.host/575a66c6-1215-4688-9189-b57579621379/10839556-9141-4712-a89e-224429715783.json")
anim_money = load_lottieurl("https://lottie.host/02008323-2895-4673-863a-4934e402802d/41838634-11d9-430c-992a-356c92d529d3.json")
anim_sun = load_lottieurl("https://lottie.host/3c6c9e04-0391-4e9e-99f2-2b6f3c02d139/2Y7Q1j1j1j.json")

# ==================== GITHUB INTEGRATION ====================
@st.cache_resource
def init_github():
    """Initialize GitHub repository connection"""
    try:
        if "GITHUB_TOKEN" in st.secrets:
            auth = Auth.Token(st.secrets["GITHUB_TOKEN"])
            g = Github(auth=auth)
            return g.get_repo(st.secrets["REPO_NAME"])
    except:
        return None

def load_history(repo):
    """Load historical data from GitHub"""
    if not repo:
        return pd.DataFrame(), None
    try:
        file = repo.get_contents("plant_history_v28.csv", ref=st.secrets["BRANCH"])
        df = pd.read_csv(StringIO(file.decoded_content.decode()))
        
        # Optimize data types
        numeric_cols = ['Gen', 'HR', 'Target HR', 'Profit', 'Vacuum', 'MS Temp', 
                       'FG Temp', 'Spray', 'SOx', 'NOx', 'Ash Util', 'Ash Cement', 
                       'Ash Bricks', 'Biomass', 'Solar']
        for c in numeric_cols:
            if c in df.columns:
                df[c] = pd.to_numeric(df[c], errors='coerce').fillna(0)
        
        df['Date'] = pd.to_datetime(df['Date'])
        cutoff_date = pd.Timestamp("2026-01-31")
        df = df[df['Date'] <= cutoff_date]
        df = df.sort_values('Date').drop_duplicates(subset=['Date', 'Unit'], keep='last')
        
        return df, file.sha
    except Exception as e:
        st.error(f"Error loading history: {e}")
        return pd.DataFrame(), None

def save_history(repo, df, sha):
    """Save historical data to GitHub"""
    try:
        df['Date'] = pd.to_datetime(df['Date']).dt.strftime('%Y-%m-%d')
        df = df.drop_duplicates(subset=['Date', 'Unit'], keep='last')
        csv_content = df.to_csv(index=False)
        msg = "Update history" if sha else "Initialize history"
        
        if sha:
            repo.update_file("plant_history_v28.csv", msg, csv_content, sha, branch=st.secrets["BRANCH"])
        else:
            repo.create_file("plant_history_v28.csv", msg, csv_content, branch=st.secrets["BRANCH"])
        return True
    except Exception as e:
        st.error(f"Error saving history: {e}")
        return False

# ==================== CONFIGURATION MANAGEMENT ====================
def get_default_config():
    """Return default plant configuration"""
    return {
        "u1_target_hr": 2315,
        "u2_target_hr": 2315,
        "u3_target_hr": 2315,
        "u1_gcv": 3600,
        "u2_gcv": 3550,
        "u3_gcv": 3620,
        "coal_ash_pct": 35.0,
        "limits": {"nox": 450, "sox": 1400, "spm": 50}
    }

def load_plant_config(repo):
    """Load plant configuration from GitHub"""
    default = get_default_config()
    if not repo:
        return default, None
    try:
        file = repo.get_contents("plant_config.json", ref=st.secrets["BRANCH"])
        data = json.loads(file.decoded_content.decode())
        return {**default, **data}, file.sha
    except:
        return default, None

def save_plant_config(repo, data, sha):
    """Save plant configuration to GitHub"""
    if not repo:
        return False
    try:
        content = json.dumps(data, indent=2)
        msg = "Update plant config"
        
        if sha:
            repo.update_file("plant_config.json", msg, content, sha, branch=st.secrets["BRANCH"])
        else:
            repo.create_file("plant_config.json", msg, content, branch=st.secrets["BRANCH"])
        return True
    except Exception as e:
        st.error(f"Error saving config: {e}")
        return False

# ==================== ANALYTICS STATE MANAGEMENT ====================
def load_analytics_state(repo):
    """Load analytics state from GitHub"""
    default_data = {"greenbelt_raw": [], "ash_raw": []}
    if not repo:
        return default_data, None
    try:
        file = repo.get_contents("analytics_state_v1.json", ref=st.secrets["BRANCH"])
        data = json.loads(file.decoded_content.decode())
        
        # Migration logic for old format
        if "greenbelt_raw" not in data and len(data) > 2:
            converted_list = []
            for species, details in data.items():
                if isinstance(details, dict) and "year_wise_plantation" in details:
                    for yr, count in details["year_wise_plantation"].items():
                        if count > 0:
                            mortality = details.get("mortality_rate", 0.1)
                            matured = count * (1 - mortality)
                            converted_list.append({
                                "Year": yr,
                                "Species": species,
                                "Planted": count,
                                "Matured": int(matured)
                            })
            if converted_list:
                data = {
                    "greenbelt_raw": converted_list,
                    "ash_raw": data.get("ash_raw", [])
                }
        
        return data, file.sha
    except:
        return default_data, None

def save_analytics_state(repo, data, sha):
    """Save analytics state to GitHub"""
    if not repo:
        return False
    try:
        content = json.dumps(data, indent=2)
        msg = "Update analytics state"
        
        if sha:
            repo.update_file("analytics_state_v1.json", msg, content, sha, branch=st.secrets["BRANCH"])
        else:
            repo.create_file("analytics_state_v1.json", msg, content, branch=st.secrets["BRANCH"])
        return True
    except Exception as e:
        st.error(f"Error saving analytics: {e}")
        return False

# ==================== CALCULATION ENGINE ====================
def calculate_unit(u_id, gen, hr, inputs, design_vals, ash_params):
    """
    Enhanced unit calculation with detailed loss breakdown
    """
    TARGET_HR = design_vals['target_hr']
    DESIGN_HR = 2250
    COAL_GCV = design_vals['gcv']
    
    # Coal consumption and CO2 emissions
    coal_consumed = (gen * hr * 1000) / COAL_GCV if COAL_GCV > 0 and gen > 0 else 0
    co2_emitted = coal_consumed * 1.7
    
    # Check for shutdown
    if gen <= 0 or hr <= 0:
        return {
            "id": u_id,
            "gen": gen,
            "hr": hr,
            "profit": -1 * (350 * 1000 * 24 * 3),  # Shutdown penalty
            "escerts": 0,
            "carbon": 0,
            "co2_emitted": 0,
            "score": 0,
            "sox": inputs['sox'],
            "nox": inputs['nox'],
            "losses": {"Vacuum": 0, "MS Temp": 0, "Flue Gas": 0, "Spray": 0, "Unaccounted": 0},
            "ash": {"generated": 0, "utilized": 0, "stocked": 0, "bricks_made": 0,
                    "cem_util": 0, "brick_util": 0, "burj_pct": 0},
            "limits": design_vals['limits'],
            "trees": 0,
            "target_hr": TARGET_HR,
            "homes_bio": 0,
            "inputs": inputs,
            "status": "SHUTDOWN"
        }
    
    # Running calculations
    status = "RUNNING"
    
    # Heat rate impact calculations
    kcal_diff = (TARGET_HR - hr) * gen * 1_000_000
    escerts = kcal_diff / 10_000_000
    coal_saved_kg = kcal_diff / COAL_GCV
    carbon_tons = (coal_saved_kg / 1000) * 1.7
    
    # Profit calculation
    profit = (escerts * 1000) + (carbon_tons * 500) + (coal_saved_kg * 4.5)
    
    # Loss breakdown
    l_vac = max(0, (inputs['vac'] - (-0.92)) / 0.01 * 18) * -1
    l_ms = max(0, (540 - inputs['ms']) * 1.2)
    l_fg = max(0, (inputs['fg'] - 130) * 1.5)
    l_spray = max(0, (inputs['spray'] - 15) * 2.0)
    l_unacc = max(0, hr - (DESIGN_HR + l_ms + l_fg + l_spray + 50) - abs(l_vac))
    
    # 5S Score
    score = max(0, 100 - (abs(l_vac) + l_ms + l_fg + l_spray + l_unacc) / 3)
    
    # Ash calculations
    ash_gen = coal_consumed * (ash_params['ash_pct'] / 100)
    ash_util = ash_params['util_cem'] + ash_params['util_brick']
    ash_stocked = ash_gen - ash_util
    bricks_current = ash_params['util_brick'] * 666
    burj_pct = (bricks_current / 165_000_000) * 100
    
    # Biomass home equivalency
    homes_bio = ash_params.get('biomass', 0) * 1000 * 1.2 / 4
    
    return {
        "id": u_id,
        "gen": gen,
        "hr": hr,
        "profit": profit,
        "escerts": escerts,
        "carbon": carbon_tons,
        "co2_emitted": co2_emitted,
        "score": score,
        "sox": inputs['sox'],
        "nox": inputs['nox'],
        "losses": {
            "Vacuum": abs(l_vac),
            "MS Temp": l_ms,
            "Flue Gas": l_fg,
            "Spray": l_spray,
            "Unaccounted": l_unacc
        },
        "ash": {
            "generated": ash_gen,
            "utilized": ash_util,
            "stocked": ash_stocked,
            "bricks_made": bricks_current,
            "cem_util": ash_params['util_cem'],
            "brick_util": ash_params['util_brick'],
            "burj_pct": burj_pct
        },
        "limits": design_vals['limits'],
        "trees": abs(carbon_tons / 0.025),
        "target_hr": TARGET_HR,
        "homes_bio": homes_bio,
        "inputs": inputs,
        "status": status
    }

# ==================== VISUALIZATION COMPONENTS ====================
def create_gauge_chart(value, title, range_min, range_max, target=None, color="#38bdf8"):
    """Create a gauge chart"""
    fig = go.Figure(go.Indicator(
        mode="gauge+number" + ("+delta" if target else ""),
        value=value,
        delta={'reference': target} if target else None,
        title={'text': title, 'font': {'color': 'white'}},
        number={'font': {'color': 'white'}},
        gauge={
            'axis': {'range': [range_min, range_max], 'tickfont': {'color': 'white'}},
            'bar': {'color': color},
            'steps': [
                {'range': [range_min, target if target else range_max/2], 'color': "rgba(0,255,0,0.2)"},
                {'range': [target if target else range_max/2, range_max], 'color': "rgba(255,0,0,0.2)"}
            ] if target else [],
            'threshold': {
                'line': {'color': "#ef4444", 'width': 4},
                'thickness': 0.75,
                'value': value
            }
        }
    ))
    
    fig.update_layout(
        height=250,
        margin=dict(l=20, r=20, t=40, b=10),
        paper_bgcolor='rgba(0,0,0,0)',
        font_color='white'
    )
    
    return fig

def create_loss_bar_chart(losses_dict):
    """Create horizontal bar chart for loss analysis"""
    loss_df = pd.DataFrame(
        list(losses_dict.items()),
        columns=['Parameter', 'Loss']
    ).sort_values('Loss', ascending=True)
    
    fig = px.bar(
        loss_df,
        x='Loss',
        y='Parameter',
        orientation='h',
        text='Loss',
        color='Loss',
        color_continuous_scale=['#ffffff', '#ef4444'],
        template='plotly_dark'
    )
    
    fig.update_layout(
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(0,0,0,0)',
        font_color='white',
        height=250,
        xaxis=dict(showgrid=False, tickfont=dict(color='white')),
        yaxis=dict(showgrid=False, tickfont=dict(color='white')),
        showlegend=False
    )
    
    fig.update_traces(
        texttemplate='%{text:.1f}',
        textposition='outside',
        textfont=dict(color='white')
    )
    
    return fig

def render_unit_detail(u, configs):
    """Enhanced unit detail view"""
    st.markdown(f"### 🔍 Unit {u['id']} Deep Dive")
    
    if u['status'] == "SHUTDOWN":
        st.error("🚨 UNIT SHUTDOWN - No Efficiency Analysis Available")
        return
    
    col1, col2 = st.columns([1, 1])
    
    with col1:
        st.markdown("#### 🏎️ Efficiency Gauge")
        target = configs[int(u['id']) - 1]['target_hr']
        fig_gauge = create_gauge_chart(
            u['hr'],
            "Heat Rate (kcal/kWh)",
            2000,
            2600,
            target,
            "#38bdf8"
        )
        st.plotly_chart(fig_gauge, use_container_width=True, key=f"gauge_{u['id']}")
    
    with col2:
        st.markdown("#### 🔧 Loss Analysis")
        fig_bar = create_loss_bar_chart(u['losses'])
        st.plotly_chart(fig_bar, use_container_width=True, key=f"bar_{u['id']}")
    
    st.divider()
    
    col3, col4, col5 = st.columns(3)
    
    with col3:
        st.markdown(f"""
        <div class="glass-card" style="border-left: 4px solid #fcd34d">
            <div class="p-title" style="color:#ffffff; font-weight:800;">5S Score</div>
            <div class="big-val" style="color:#fcd34d">{u['score']:.1f}</div>
            <div class="sub-lbl" style="color:#ffffff;">Technical Hygiene</div>
        </div>
        """, unsafe_allow_html=True)
    
    with col4:
        st.markdown(f"""
        <div class="glass-card" style="border-left: 4px solid #38bdf8">
            <div class="p-title" style="color:#ffffff; font-weight:800;">Carbon Credits</div>
            <div class="big-val" style="color:#38bdf8">{u['carbon']:.1f}</div>
            <div class="sub-lbl" style="color:#ffffff;">Tons CO2 Avoided</div>
        </div>
        """, unsafe_allow_html=True)
    
    with col5:
        # Compliance check
        sox_status = "✅" if u['sox'] <= u['limits']['sox'] else "❌"
        nox_status = "✅" if u['nox'] <= u['limits']['nox'] else "❌"
        
        st.markdown(f"""
        <div class="glass-card" style="border-left: 4px solid {'#10b981' if sox_status == '✅' and nox_status == '✅' else '#ef4444'}">
            <div class="p-title" style="color:#ffffff; font-weight:800;">Compliance</div>
            <div style="font-size:16px; color:#ffffff; margin-top:10px;">
                SOx {sox_status} {u['sox']:.0f}/{u['limits']['sox']}<br>
                NOx {nox_status} {u['nox']:.0f}/{u['limits']['nox']}
            </div>
        </div>
        """, unsafe_allow_html=True)

# ==================== PDF GENERATION ====================
class PDF(FPDF):
    def header(self):
        self.set_font('Arial', 'B', 16)
        self.set_text_color(0, 51, 153)
        self.cell(0, 10, 'GMR Kamalanga - 5S Report', 0, 1, 'C')
        self.ln(5)
    
    def footer(self):
        self.set_y(-15)
        self.set_font('Arial', 'I', 8)
        self.set_text_color(128, 128, 128)
        self.cell(0, 10, f'Page {self.page_no()}', 0, 0, 'C')

def create_full_pdf(units, fleet_pnl, ash_data, green_data):
    """Generate comprehensive PDF report"""
    pdf = PDF()
    pdf.add_page()
    pdf.set_font("Arial", 'B', 12)
    pdf.cell(0, 10, f"Date: {datetime.now().strftime('%Y-%m-%d')} | P&L: Rs {fleet_pnl:,.0f}", 1, 1, 'C')
    pdf.ln(10)
    
    # Header
    pdf.set_font("Arial", 'B', 10)
    pdf.set_fill_color(220, 220, 220)
    headers = ["Unit", "Gen", "HR", "Profit", "SOx", "NOx"]
    for h in headers:
        pdf.cell(30, 10, h, 1, 0, 'C', 1)
    pdf.ln()
    
    # Data
    pdf.set_font("Arial", size=10)
    for u in units:
        pdf.cell(30, 10, f"U{u['id']}", 1)
        pdf.cell(30, 10, str(u['gen']), 1)
        pdf.cell(30, 10, str(u['hr']), 1)
        pdf.cell(30, 10, f"{u['profit']:,.0f}", 1)
        pdf.cell(30, 10, str(u['sox']), 1)
        pdf.cell(30, 10, str(u['nox']), 1)
        pdf.ln()
    
    return pdf.output(dest='S').encode('latin-1')

# ==================== MAIN APPLICATION ====================
def main():
    # Initialize session state
    if 'daily_data' not in st.session_state:
        st.session_state['daily_data'] = {}
    
    # Sidebar
    with st.sidebar:
        try:
            st.image("1000051706.png", use_container_width=True)
        except:
            st.markdown("## **GMR POWER**")
        
        st.title("Control Panel")
        
        # Date selection
        date_in = st.date_input("📅 Dashboard Date", datetime.now())
        
        # Initialize data structures
        units_data = []
        repo = init_github()
        hist_df, sha = load_history(repo)
        analytics_state, analytics_sha = load_analytics_state(repo)
        plant_conf, conf_sha = load_plant_config(repo)
        
        # Check for historical data
        hist_data = {}
        if not hist_df.empty:
            date_in_ts = pd.Timestamp(date_in)
            day_df = hist_df[hist_df['Date'] == date_in_ts]
            
            if not day_df.empty:
                st.success(f"✓ Data Found: {date_in.strftime('%d %b %Y')}")
                for _, row in day_df.iterrows():
                    hist_data[str(row['Unit'])] = row
            else:
                st.info("No history for this date. Using manual inputs.")
        
        # File upload section
        with st.expander("📤 Upload Operational Data"):
            uploaded_file = st.file_uploader("Daily Input (Excel/CSV)", type=['xlsx', 'csv'])
            if uploaded_file:
                try:
                    if uploaded_file.name.endswith('.csv'):
                        df_up = pd.read_csv(uploaded_file)
                    else:
                        df_up = pd.read_excel(uploaded_file)
                    
                    if 'Parameter' in df_up.columns:
                        df_up.set_index('Parameter', inplace=True)
                        st.session_state['daily_data'] = df_up.to_dict()
                        st.toast("✅ Daily Data Applied", icon="✅")
                except Exception as e:
                    st.error(f"Read Error: {e}")
            
            # Bulk upload
            bulk_file = st.file_uploader("Bulk History Upload", type=['csv'])
            if bulk_file and st.button("🚀 Process Bulk Upload"):
                try:
                    df_b = pd.read_csv(bulk_file)
                    df_b['Date'] = pd.to_datetime(df_b['Date']).dt.strftime('%Y-%m-%d')
                    
                    if repo:
                        file = repo.get_contents("plant_history_v28.csv", ref=st.secrets["BRANCH"])
                        df_curr = pd.read_csv(StringIO(file.decoded_content.decode()))
                        df_comb = pd.concat([df_curr, df_b], ignore_index=True)
                        df_comb['Date'] = pd.to_datetime(df_comb['Date'])
                        df_comb = df_comb.sort_values('Date')
                        df_comb['Date'] = df_comb['Date'].dt.strftime('%Y-%m-%d')
                        df_comb = df_comb.drop_duplicates(subset=['Date', 'Unit'], keep='last')
                        
                        csv_c = df_comb.to_csv(index=False)
                        repo.update_file(
                            "plant_history_v28.csv",
                            "Bulk upload",
                            csv_c,
                            file.sha,
                            branch=st.secrets["BRANCH"]
                        )
                        
                        st.success(f"✅ Bulk Uploaded! Records: {len(df_comb)}")
                        st.rerun()
                except Exception as e:
                    st.error(f"Bulk Error: {e}")
        
        st.markdown("---")
        
        # Configuration and Inputs
        tab_conf, tab_inp = st.tabs(["⚙️ Config", "📝 Inputs"])
        
        with tab_conf:
            st.subheader("🏭 Plant Design Parameters")
            
            col1, col2 = st.columns(2)
            
            with col1:
                lim_sox = st.number_input("SOx Limit (mg/Nm³)", value=plant_conf['limits']['sox'])
                lim_nox = st.number_input("NOx Limit (mg/Nm³)", value=plant_conf['limits']['nox'])
                lim_spm = st.number_input("SPM Limit (mg/Nm³)", value=plant_conf['limits']['spm'])
                coal_ash = st.number_input("Coal Ash %", value=plant_conf['coal_ash_pct'], step=0.1)
            
            with col2:
                t_u1 = st.number_input("U1 Target HR", value=plant_conf['u1_target_hr'])
                t_u2 = st.number_input("U2 Target HR", value=plant_conf['u2_target_hr'])
                t_u3 = st.number_input("U3 Target HR", value=plant_conf['u3_target_hr'])
            
            g_u1 = plant_conf['u1_gcv']
            g_u2 = plant_conf['u2_gcv']
            g_u3 = plant_conf['u3_gcv']
            
            if st.button("💾 Save Config Permanently"):
                new_conf = {
                    "u1_target_hr": t_u1,
                    "u2_target_hr": t_u2,
                    "u3_target_hr": t_u3,
                    "u1_gcv": g_u1,
                    "u2_gcv": g_u2,
                    "u3_gcv": g_u3,
                    "coal_ash_pct": coal_ash,
                    "limits": {
                        "nox": lim_nox,
                        "sox": lim_sox,
                        "spm": lim_spm
                    }
                }
                
                if save_plant_config(repo, new_conf, conf_sha):
                    st.success("✅ Configuration Updated on GitHub!")
                    st.rerun()
        
        with tab_inp:
            configs = [
                {'target_hr': t_u1, 'gcv': g_u1, 'limits': {'sox': lim_sox, 'nox': lim_nox}},
                {'target_hr': t_u2, 'gcv': g_u2, 'limits': {'sox': lim_sox, 'nox': lim_nox}},
                {'target_hr': t_u3, 'gcv': g_u3, 'limits': {'sox': lim_sox, 'nox': lim_nox}}
            ]
            
            def val(u_id, row_key, col_key, def_v):
                """Get value from history or session"""
                if u_id in hist_data and col_key in hist_data[u_id]:
                    if pd.notna(hist_data[u_id][col_key]):
                        return float(hist_data[u_id][col_key])
                
                sess = st.session_state.get('daily_data', {})
                if f"Unit {u_id}" in sess and row_key in sess[f"Unit {u_id}"]:
                    return float(sess[f"Unit {u_id}"][row_key])
                
                return def_v
            
            # Unit inputs
            for i in range(1, 4):
                u = str(i)
                d_key = date_in.strftime('%Y%m%d')
                
                with st.expander(f"Unit {i}", expanded=(i == 1)):
                    gen = st.number_input(
                        f"U{u} Generation (MU)",
                        value=val(u, 'Generation (MU)', 'Gen', 8.4),
                        key=f"g{u}_{d_key}"
                    )
                    
                    hr = st.number_input(
                        f"U{u} Heat Rate (kcal/kWh)",
                        value=val(u, 'Heat Rate (kcal/kWh)', 'HR', 2380.0),
                        key=f"h{u}_{d_key}"
                    )
                    
                    vac = st.number_input(
                        f"U{u} Vacuum (kg/cm²)",
                        value=val(u, 'Vacuum (kg/cm2)', 'Vacuum', -0.90),
                        step=0.001,
                        format="%.3f",
                        key=f"v{u}_{d_key}"
                    )
                    
                    ms = st.number_input(
                        f"U{u} MS Temp (°C)",
                        value=val(u, 'MS Temp (C)', 'MS Temp', 535.0),
                        key=f"m{u}_{d_key}"
                    )
                    
                    fg = st.number_input(
                        f"U{u} FG Temp (°C)",
                        value=val(u, 'FG Temp (C)', 'FG Temp', 135.0),
                        key=f"f{u}_{d_key}"
                    )
                    
                    spray = st.number_input(
                        f"U{u} Spray Water (TPH)",
                        value=val(u, 'Spray (TPH)', 'Spray', 20.0),
                        key=f"s{u}_{d_key}"
                    )
                    
                    sox = st.number_input(
                        f"U{u} SOx (mg/Nm³)",
                        value=val(u, 'SOx (mg/Nm3)', 'SOx', 550.0),
                        key=f"sx{u}_{d_key}"
                    )
                    
                    nox = st.number_input(
                        f"U{u} NOx (mg/Nm³)",
                        value=val(u, 'NOx (mg/Nm3)', 'NOx', 400.0),
                        key=f"nx{u}_{d_key}"
                    )
                    
                    ash_cem = st.number_input(
                        f"U{u} Ash to Cement (Tons)",
                        value=val(u, 'Ash to Cement (Tons)', 'Ash Cement', 1000.0),
                        key=f"ac{u}_{d_key}"
                    )
                    
                    ash_brk = st.number_input(
                        f"U{u} Ash to Bricks (Tons)",
                        value=val(u, 'Ash to Bricks (Tons)', 'Ash Bricks', 500.0),
                        key=f"ab{u}_{d_key}"
                    )
                    
                    ash_p = {
                        'ash_pct': coal_ash,
                        'util_cem': ash_cem,
                        'util_brick': ash_brk,
                        'biomass': val(u, 'Biomass (Tons)', 'Biomass', 0.0)
                    }
                    
                    # Calculate unit performance
                    units_data.append(
                        calculate_unit(
                            u,
                            gen,
                            hr,
                            {
                                'vac': vac,
                                'ms': ms,
                                'fg': fg,
                                'spray': spray,
                                'sox': sox,
                                'nox': nox
                            },
                            configs[i - 1],
                            ash_p
                        )
                    )
            
            st.markdown("---")
            
            # Renewables
            bio_u1 = st.number_input(
                "Biomass U1 (Tons)",
                value=val('1', 'Biomass (Tons)', 'Biomass', 0.0),
                key=f"b1_{date_in.strftime('%Y%m%d')}"
            )
            
            bio_u2 = st.number_input(
                "Biomass U2 (Tons)",
                value=val('2', 'Biomass (Tons)', 'Biomass', 0.0),
                key=f"b2_{date_in.strftime('%Y%m%d')}"
            )
            
            bio_u3 = st.number_input(
                "Biomass U3 (Tons)",
                value=val('3', 'Biomass (Tons)', 'Biomass', 0.0),
                key=f"b3_{date_in.strftime('%Y%m%d')}"
            )
            
            sol_u1 = st.number_input(
                "Solar Generation (MU)",
                value=val('1', 'Solar (MU)', 'Solar', 0.0),
                key=f"sol_{date_in.strftime('%Y%m%d')}"
            )
            
            bio_gcv = 3000.0
        
        # Save button
        if st.button("💾 Save to History", use_container_width=True):
            if repo:
                new_rows = []
                for u in units_data:
                    row = {
                        "Date": date_in.strftime('%Y-%m-%d'),
                        "Unit": u['id'],
                        "Profit": u['profit'],
                        "HR": u['hr'],
                        "SOx": u['sox'],
                        "NOx": u['nox'],
                        "Gen": u['gen'],
                        "Ash Util": u['ash']['utilized'],
                        "Coal Ash %": coal_ash,
                        "Vacuum": u['losses']['Vacuum'],
                        "MS Temp": u['losses']['MS Temp'],
                        "FG Temp": u['losses']['Flue Gas'],
                        "Spray": u['losses']['Spray'],
                        "Ash Cement": u['ash']['cem_util'],
                        "Ash Bricks": u['ash']['brick_util'],
                        "Biomass": bio_u1 if u['id'] == '1' else (bio_u2 if u['id'] == '2' else bio_u3),
                        "Solar": sol_u1 if u['id'] == '1' else 0
                    }
                    new_rows.append(row)
                
                df_new = pd.DataFrame(new_rows)
                df_comb = pd.concat([hist_df, df_new], ignore_index=True)
                df_comb = df_comb.drop_duplicates(subset=['Date', 'Unit'], keep='last')
                
                if save_history(repo, df_comb, sha):
                    st.success("✅ Data Saved Successfully!")
                    st.rerun()
            else:
                st.error("❌ GitHub repository not connected")
    
    # Calculate fleet-level metrics
    fleet_profit = sum(u['profit'] for u in units_data) if units_data else 0
    fleet_ash_gen = sum(u['ash']['generated'] for u in units_data) if units_data else 0
    fleet_ash_util = sum(u['ash']['utilized'] for u in units_data) if units_data else 0
    
    # Time-based calculations
    date_in_ts = pd.Timestamp(date_in)
    curr_month_start = pd.Timestamp(date_in.replace(day=1))
    fy_start = pd.Timestamp(
        year=date_in.year if date_in.month >= 4 else date_in.year - 1,
        month=4,
        day=1
    )
    
    # Historical aggregations
    past_mtd_ash_gen = past_ytd_ash_gen = 0
    past_mtd_ash_util = past_ytd_ash_util = 0
    past_mtd_profit = 0
    
    if not hist_df.empty:
        past_mtd_df = hist_df[
            (hist_df['Date'] >= curr_month_start) & 
            (hist_df['Date'] < date_in_ts)
        ].copy()
        
        past_ytd_df = hist_df[
            (hist_df['Date'] >= fy_start) & 
            (hist_df['Date'] < date_in_ts)
        ].copy()
        
        past_mtd_profit = past_mtd_df['Profit'].sum() if not past_mtd_df.empty else 0
        
        def calc_ash_gen(df):
            if df.empty:
                return 0
            return (df['Gen'] * df['HR'] * 1000 / 3600 * (coal_ash / 100)).sum()
        
        past_mtd_ash_gen = calc_ash_gen(past_mtd_df)
        past_ytd_ash_gen = calc_ash_gen(past_ytd_df)
        past_mtd_ash_util = past_mtd_df['Ash Util'].sum() if not past_mtd_df.empty else 0
        past_ytd_ash_util = past_ytd_df['Ash Util'].sum() if not past_ytd_df.empty else 0
    
    # Current totals (History + Today)
    mtd_ash_gen_total = past_mtd_ash_gen + fleet_ash_gen
    ytd_ash_gen_total = past_ytd_ash_gen + fleet_ash_gen
    mtd_ash_util_total = past_mtd_ash_util + fleet_ash_util
    ytd_ash_util_total = past_ytd_ash_util + fleet_ash_util
    mtd_profit = past_mtd_profit + fleet_profit
    
    mtd_dump = mtd_ash_gen_total - mtd_ash_util_total
    ytd_dump = ytd_ash_gen_total - ytd_ash_util_total
    
    # Lagoon tracking
    daily_avg_gen = fleet_ash_gen if fleet_ash_gen > 0 else 5000
    total_pond_capacity_tons = daily_avg_gen * 540
    simulated_starting_fill = total_pond_capacity_tons * 0.50
    current_lagoon_volume = simulated_starting_fill + ytd_dump
    lagoon_fill_pct = max(0, min(100, (current_lagoon_volume / total_pond_capacity_tons) * 100))
    
    daily_net_dump = fleet_ash_gen - fleet_ash_util
    pond_days_left = (
        (total_pond_capacity_tons - current_lagoon_volume) / daily_net_dump
        if daily_net_dump > 0
        else 9999
    )
    
    # Renewable calculations
    total_bio = bio_u1 + bio_u2 + bio_u3
    bio_co2 = (total_bio * bio_gcv * 1000 / 3600) * 1.7
    sol_co2 = sol_u1 * 1000 * 0.95
    solar_homes = (sol_u1 * 1000000) / 4
    bio_homes = sum(u['homes_bio'] for u in units_data) if units_data else 0
    
    # ==================== MAIN DASHBOARD ====================
    st.title("🏭 GMR Kamalanga 5S Dashboard")
    
    col_top1, col_top2 = st.columns([5, 1])
    
    with col_top1:
        st.markdown(
            f"**Date:** {date_in.strftime('%d-%b-%Y')} | "
            f"**Fleet P&L:** {format_lacs(fleet_profit)}"
        )
    
    with col_top2:
        if st.button("📄 Generate PDF"):
            ash_d = {
                'gen': fleet_ash_gen,
                'util': fleet_ash_util,
                'pond_days': pond_days_left,
                'bricks': sum(u['ash']['bricks_made'] for u in units_data) if units_data else 0,
                'burj_pct': sum(u['ash']['burj_pct'] for u in units_data) if units_data else 0
            }
            
            grn_d = {
                'bio_co2': bio_co2,
                'sol_co2': sol_co2,
                'trees': bio_co2 / 0.025
            }
            
            pdf_b = create_full_pdf(units_data, fleet_profit, ash_d, grn_d)
            b64 = base64.b64encode(pdf_b).decode()
            
            st.markdown(
                f'<a href="data:application/pdf;base64,{b64}" download="GMR_Report.pdf">'
                'Download PDF</a>',
                unsafe_allow_html=True
            )
    
    # Tab navigation
    tabs = st.tabs([
        "🏠 War Room",
        "🌿 Sustainability",
        "🪨 Ash Ops",
        "☀️ Green Energy",
        "⚙️ Unit 1",
        "⚙️ Unit 2",
        "⚙️ Unit 3",
        "📈 Trends",
        "🎮 Simulator",
        "📊 Analytics",
        "ℹ️ Info"
    ])
    
    # TAB 1: WAR ROOM
    with tabs[0]:
        display_info(r"""
        **Executive Summary:**
        * **Unit P&L:** Compares actual efficiency vs target. Green = Profit, Red = Loss.
        * **Ash Pond Days:** Remaining life based on current capacity and daily filling rate.
        * **MTD Profit:** Sum of historical data + today's live inputs.
        
        **Key Formulas:**
        * $$Profit = (Target_{HR} - Actual_{HR}) \times Generation \times 1000$$
        * $$Pond\_Days = \frac{Capacity - Current\_Fill}{Daily\_Net\_Dump}$$
        """)
        
        st.markdown('<div class="section-header">📅 Daily Snapshot</div>', unsafe_allow_html=True)
        
        cols = st.columns(4)
        
        if units_data:
            for i, u in enumerate(units_data):
                color = "#4ade80" if u['profit'] > 0 else "#f87171"
                border = "border-good" if u['profit'] > 0 else "border-bad"
                
                if u['status'] == "SHUTDOWN":
                    border = "border-shut"
                    color = "#ffffff"
                
                with cols[i]:
                    st.markdown(f"""
                    <div class="glass-card {border}">
                        <div class="unit-header">UNIT {u['id']}</div>
                        <div class="big-val" style="color:{color}">{format_lacs(u['profit'])}</div>
                        <div class="sub-lbl" style="color:#ffffff;">
                            {u['status'] if u['status'] == 'SHUTDOWN' else 'Daily Net Impact'}
                        </div>
                        <hr style="border-color:#ffffff33;">
                        <div style="text-align:left; font-size:12px; color:#ffffff; font-weight:600;">
                            <div style="display:flex; justify-content:space-between;">
                                <span>Target:</span><b>{u['target_hr']:.0f}</b>
                            </div>
                            <div style="display:flex; justify-content:space-between;">
                                <span>Actual:</span><b>{u['hr']:.0f}</b>
                            </div>
                            <div style="margin-top:5px; border-top:1px solid #444; padding-top:5px;">
                                SOx: <span style="color:{'#f87171' if u['sox'] > plant_conf['limits']['sox'] else '#ffffff'}">
                                {u['sox']}</span> | NOx: {u['nox']}
                            </div>
                        </div>
                    </div>
                    """, unsafe_allow_html=True)
        
        with cols[3]:
            clr = "#f87171" if lagoon_fill_pct > 80 else "#38bdf8"
            st.markdown(f"""
            <div class="glass-card" style="border-top: 4px solid {clr}">
                <div class="unit-header" style="color:#38bdf8;">ASH LAGOONS</div>
                <div class="big-val" style="color:{clr}">{lagoon_fill_pct:.1f}%</div>
                <div class="sub-lbl" style="color:#ffffff;">Overall Fill Level</div>
                <div style="font-size:11px; color:#ffffff; font-weight:600; margin-top:5px;">
                    Tracking YTD Dumping
                </div>
            </div>
            """, unsafe_allow_html=True)
        
        st.markdown('<div class="section-header">📆 Monthly Performance (MTD)</div>', unsafe_allow_html=True)
        
        col_m1, col_m2, col_m3 = st.columns(3)
        
        col_m1.metric("MTD Fleet Profit", format_lacs(mtd_profit))
        col_m2.metric("MTD Ash Utilization", f"{mtd_ash_util_total:,.0f} Tons")
        col_m3.info("MTD = Sum of saved history (excluding today) + live inputs")
    
    # TAB 2: SUSTAINABILITY
    with tabs[1]:
        display_info(r"""
        **Sustainability & Carbon Footprint:**
        * **Daily CO₂ Emissions:** `Coal Consumed (Tons) × 1.7`
        * **Daily Tree Offset:** `Total Matured Trees × (25 kg / 365 days) / 1000`
        * **Area Required:** ~1000 trees per acre for new plantations
        """)
        
        st.markdown("#### 🏭 Daily Unit CO₂ Emissions")
        
        cols = st.columns(3)
        total_daily_co2 = 0
        
        for i, u in enumerate(units_data):
            u_co2 = u.get('co2_emitted', 0)
            total_daily_co2 += u_co2
            
            with cols[i]:
                st.markdown(f"""
                <div class="glass-card border-bad">
                    <div class="unit-header">UNIT {u['id']}</div>
                    <div class="big-val" style="color:#f87171">{u_co2:,.0f} T</div>
                    <div class="sub-lbl" style="color:#ffffff;">CO₂ Emitted Today</div>
                </div>
                """, unsafe_allow_html=True)
        
        st.markdown("#### 🌍 Fleet Combined Effect vs Tree Offset")
        
        gb_raw = analytics_state.get('greenbelt_raw', [])
        
        if gb_raw:
            df_gb = pd.DataFrame(gb_raw)
            real_trees = df_gb['Matured'].sum() if 'Matured' in df_gb.columns else 354762
        else:
            real_trees = 354762
        
        yearly_offset_tons = real_trees * 25.0 / 1000.0
        daily_offset_tons = yearly_offset_tons / 365.0
        net_daily_co2 = total_daily_co2 - daily_offset_tons
        
        col_net1, col_net2, col_net3 = st.columns(3)
        
        col_net1.metric("Total CO₂ Emitted", f"{total_daily_co2:,.0f} T/Day")
        col_net2.metric(
            "Trees CO₂ Offset",
            f"{daily_offset_tons:,.1f} T/Day",
            help=f"Annual Tree Offset: {yearly_offset_tons:,.0f} Tons/Year"
        )
        col_net3.metric(
            "Net CO₂ Footprint",
            f"{net_daily_co2:,.0f} T/Day",
            delta=f"-{daily_offset_tons:.1f} T offset",
            delta_color="inverse"
        )
        
        st.divider()
        st.markdown("#### 📆 MTD Carbon Offset & Remediation Plan")
        
        past_co2_emitted = 0
        
        if not hist_df.empty:
            past_mtd_df = hist_df[
                (hist_df['Date'] >= curr_month_start) & 
                (hist_df['Date'] < date_in_ts)
            ].copy()
            
            if not past_mtd_df.empty:
                past_mtd_df['Coal_Tons'] = (past_mtd_df['Gen'] * past_mtd_df['HR'] * 1000) / 3585
                past_co2_emitted = (past_mtd_df['Coal_Tons'] * 1.7).sum()
        
        mtd_co2_emitted = past_co2_emitted + total_daily_co2
        days_mtd = (date_in_ts - curr_month_start).days + 1
        mtd_offset = daily_offset_tons * days_mtd
        mtd_deficit = mtd_co2_emitted - mtd_offset
        
        if mtd_deficit > 0:
            offset_per_tree_mtd = (25.0 / 365.0) * days_mtd / 1000.0
            trees_needed = mtd_deficit / offset_per_tree_mtd if offset_per_tree_mtd > 0 else 0
            area_needed_acres = trees_needed / 1000.0
            
            offset_pct = (mtd_offset / mtd_co2_emitted * 100) if mtd_co2_emitted > 0 else 0
            
            st.markdown(f"""
            <div class="alert-box alert-warning">
                ⚠️ <b>Carbon Deficit Alert:</b> Your trees offset only <b>{offset_pct:.2f}%</b> 
                of MTD emissions.
            </div>
            """, unsafe_allow_html=True)
            
            m1, m2, m3 = st.columns(3)
            m1.metric("MTD CO₂ Emitted", f"{mtd_co2_emitted:,.0f} T")
            m2.metric("Additional Trees Needed", f"{trees_needed:,.0f}")
            m3.metric("Land Area Required", f"{area_needed_acres:,.0f} Acres")
        else:
            st.markdown("""
            <div class="alert-box alert-success">
                🌿 <b>Carbon Neutral!</b> Your greenbelt has successfully offset all MTD emissions.
            </div>
            """, unsafe_allow_html=True)
            st.metric("MTD Net CO₂", f"{mtd_deficit:,.0f} T")
    
    # TAB 3: ASH OPERATIONS
    with tabs[2]:
        st.markdown("### 🪨 Ash Operations Center")
        
        display_info(r"""
        **Ash Management:**
        * **Generation:** Based on Coal Consumption & Ash %
        * **Burj Khalifa Index:** Percentage of Burj Khalifa that could be built 
          if all ash was converted to bricks (165M bricks total)
        * **Lagoon Status:** Real-time tracking based on un-utilized ash dumping
        """)
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.markdown(f"""
            <div class="glass-card border-solar">
                <div class="unit-header" style="color:#fde047;">MTD ASH GENERATED</div>
                <div class="big-val" style="color:#fde047;">{mtd_ash_gen_total:,.0f} T</div>
            </div>
            """, unsafe_allow_html=True)
        
        with col2:
            st.markdown(f"""
            <div class="glass-card border-green">
                <div class="unit-header" style="color:#4ade80;">MTD ASH UTILIZED</div>
                <div class="big-val" style="color:#4ade80;">{mtd_ash_util_total:,.0f} T</div>
            </div>
            """, unsafe_allow_html=True)
        
        with col3:
            st.markdown(f"""
            <div class="glass-card border-bad">
                <div class="unit-header" style="color:#f87171;">MTD UN-UTILIZED DUMP</div>
                <div class="big-val" style="color:#f87171;">{max(0, mtd_dump):,.0f} T</div>
            </div>
            """, unsafe_allow_html=True)
        
        st.divider()
        st.markdown("#### ⏱️ Real-Time Daily Flow & Lagoon Dials")
        
        g1, g2, g3, g4 = st.columns(4)
        
        max_scale = max(5000, fleet_ash_gen * 1.2)
        
        with g1:
            fig_g1 = create_gauge_chart(
                fleet_ash_gen,
                "Daily Gen (T)",
                0,
                max_scale,
                color="#fde047"
            )
            st.plotly_chart(fig_g1, use_container_width=True)
        
        with g2:
            fig_g2 = create_gauge_chart(
                fleet_ash_util,
                "Daily Util (T)",
                0,
                max_scale,
                color="#4ade80"
            )
            st.plotly_chart(fig_g2, use_container_width=True)
        
        with g3:
            fig_l1 = create_gauge_chart(
                lagoon_fill_pct,
                "Lagoon 1 Fill %",
                0,
                100,
                color="#f87171" if lagoon_fill_pct > 80 else "#38bdf8"
            )
            st.plotly_chart(fig_l1, use_container_width=True)
        
        with g4:
            fig_l2 = create_gauge_chart(
                lagoon_fill_pct,
                "Lagoon 2 Fill %",
                0,
                100,
                color="#f87171" if lagoon_fill_pct > 80 else "#38bdf8"
            )
            st.plotly_chart(fig_l2, use_container_width=True)
        
        st.divider()
        
        col_vis1, col_vis2 = st.columns([1, 1])
        
        with col_vis1:
            st.markdown("#### 🏗️ Volume vs Burj Khalifa (165M Bricks)")
            
            burj_total_bricks = 165_000_000
            
            daily_burj_pct = (fleet_ash_gen * 666 / burj_total_bricks) * 100
            mtd_burj_pct = (mtd_ash_gen_total * 666 / burj_total_bricks) * 100
            ytd_burj_pct = (ytd_ash_gen_total * 666 / burj_total_bricks) * 100
            
            df_burj = pd.DataFrame({
                'Timeline': ['Daily Gen', 'MTD Gen', 'YTD Gen'],
                '% Built': [daily_burj_pct, mtd_burj_pct, ytd_burj_pct]
            })
            
            fig_burj = px.bar(
                df_burj,
                x='Timeline',
                y='% Built',
                text='% Built',
                title="Percentage of Burj Khalifa Built",
                color='Timeline',
                color_discrete_sequence=['#34d399', '#fcd34d', '#f87171'],
                template='plotly_dark'
            )
            
            fig_burj.update_traces(
                texttemplate='%{text:.2f}%',
                textposition='outside',
                textfont=dict(color='white')
            )
            
            fig_burj.update_layout(
                height=350,
                paper_bgcolor='rgba(0,0,0,0)',
                plot_bgcolor='rgba(0,0,0,0)',
                font_color='white',
                showlegend=False
            )
            
            fig_burj.update_yaxes(title="%", showgrid=False)
            
            st.plotly_chart(fig_burj, use_container_width=True)
        
        with col_vis2:
            if units_data:
                st.markdown("#### 📉 Today's Disposal Breakdown")
                
                ash_breakdown = pd.DataFrame({
                    'Type': ['Cement', 'Bricks'],
                    'Tons': [
                        sum(u['ash']['cem_util'] for u in units_data),
                        sum(u['ash']['brick_util'] for u in units_data)
                    ]
                })
                
                fig_pie = px.pie(
                    ash_breakdown,
                    values='Tons',
                    names='Type',
                    hole=0.4,
                    template='plotly_dark',
                    color_discrete_sequence=['#fbbf24', '#38bdf8']
                )
                
                fig_pie.update_layout(
                    height=350,
                    margin=dict(t=30, b=10, l=10, r=10),
                    paper_bgcolor='rgba(0,0,0,0)',
                    font_color='white'
                )
                
                st.plotly_chart(fig_pie, use_container_width=True)
    
    # TAB 4: GREEN ENERGY
    with tabs[3]:
        display_info(r"""
        **Green Power Impact:**
        * **Biomass:** Co-firing agricultural waste with coal reduces net CO2
        * **Solar:** Captive solar power reducing auxiliary consumption
        
        **Equivalency:**
        * $$Homes\_Powered = \frac{Renewable\_Units}{4 \text{ (Avg Daily Consumption)}}$$
        """)
        
        st.markdown("#### ⚡ Green Power Impact")
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown(f"""
            <div class="glass-card border-green">
                <div class="unit-header">BIOMASS</div>
                <div class="big-val" style="color:#10b981">{bio_co2:.2f} T</div>
                <div class="sub-lbl" style="color:#ffffff;">CO2 Saved Today</div>
                <hr style="border-color:#ffffff33;">
                <div class="big-val" style="font-size:24px; color:#ffffff;">{bio_homes:,.0f}</div>
                <div class="sub-lbl" style="color:#ffffff;">Homes Powered</div>
            </div>
            """, unsafe_allow_html=True)
        
        with col2:
            st.markdown(f"""
            <div class="glass-card border-solar">
                <div class="unit-header">SOLAR</div>
                <div class="big-val" style="color:#fde047">{sol_co2:.2f} T</div>
                <div class="sub-lbl" style="color:#ffffff;">CO2 Saved Today</div>
                <hr style="border-color:#ffffff33;">
                <div class="big-val" style="font-size:24px; color:#ffffff;">{solar_homes:,.0f}</div>
                <div class="sub-lbl" style="color:#ffffff;">Homes Powered</div>
            </div>
            """, unsafe_allow_html=True)
        
        if anim_sun:
            st_lottie(anim_sun, height=150, key="sun_anim")
    
    # TABS 5-7: INDIVIDUAL UNITS
    if units_data:
        for i, tab in enumerate([tabs[4], tabs[5], tabs[6]]):
            with tab:
                display_info(r"""
                **Unit Performance:**
                * **Loss Analysis:** Breakdown of Heat Rate deviation sources
                * **5S Score:** Technical hygiene score based on parameter adherence
                
                **Loss Formulas (Approx):**
                * Vacuum: 15 kcal/kWh per 0.01 kg/cm² deviation
                * MS Temp: 0.7 kcal/kWh per °C deviation
                """)
                
                render_unit_detail(units_data[i], configs)
    
    # TAB 8: TRENDS
    with tabs[7]:
        display_info("Historical performance analysis. Filters out shutdown days (HR < 100).")
        
        filter_opt = st.radio("Duration", ["7 Days", "30 Days", "90 Days"], horizontal=True)
        
        if not hist_df.empty:
            days_back = {"7 Days": 7, "30 Days": 30, "90 Days": 90}[filter_opt]
            cutoff = date_in - timedelta(days=days_back)
            cutoff_ts = pd.Timestamp(cutoff)
            
            filtered_df = hist_df[
                (hist_df['Date'] >= cutoff_ts) & 
                (hist_df['Date'] <= date_in_ts)
            ]
            
            filtered_df = filtered_df[filtered_df['HR'] > 100]
            filtered_df['Date_dt'] = filtered_df['Date'].dt.date
            filtered_df['Unit'] = filtered_df['Unit'].astype(str)
            
            fig = make_subplots(specs=[[{"secondary_y": True}]])
            
            colors = {'1': '#38bdf8', '2': '#fbbf24', '3': '#10b981'}
            
            for u_id in filtered_df['Unit'].unique():
                u_df = filtered_df[filtered_df['Unit'] == u_id]
                fig.add_trace(
                    go.Scatter(
                        x=u_df['Date_dt'],
                        y=u_df['HR'],
                        name=f"Unit {u_id} HR",
                        mode='lines+markers',
                        line=dict(color=colors.get(u_id, 'white'))
                    ),
                    secondary_y=False
                )
            
            fleet_trend = filtered_df.groupby('Date_dt')['Profit'].sum().reset_index()
            
            fig.add_trace(
                go.Bar(
                    x=fleet_trend['Date_dt'],
                    y=fleet_trend['Profit'],
                    name="Fleet Profit",
                    opacity=0.3,
                    marker_color='white'
                ),
                secondary_y=True
            )
            
            fig.update_layout(
                title="Heat Rate vs Profit Trend",
                template="plotly_dark",
                paper_bgcolor='rgba(0,0,0,0)',
                plot_bgcolor='rgba(0,0,0,0)',
                hovermode="x unified",
                legend=dict(orientation="h", y=1.1),
                font_color='white',
                height=500
            )
            
            fig.update_yaxes(
                title_text="Heat Rate (kcal/kWh)",
                secondary_y=False,
                showgrid=False,
                tickfont=dict(color='white')
            )
            
            fig.update_yaxes(
                title_text="Profit (₹)",
                secondary_y=True,
                showgrid=False,
                tickfont=dict(color='white')
            )
            
            fig.update_xaxes(tickfont=dict(color='white'))
            
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No historical data available for trend analysis.")
    
    # TAB 9: SIMULATOR
    with tabs[8]:
        st.markdown("### 🎮 Performance Simulator")
        
        display_info(r"""
        **Simulation Logic:**
        Adjust parameters to see instant impact on **Net Heat Rate** and **Daily Profit**.
        * **Vacuum:** Lower (more negative) is better
        * **APC:** Auxiliary Power Consumption directly reduces salable power
        * **GCV:** Gross Calorific Value of coal affects fuel quantity needed
        """)
        
        s_col1, s_col2, s_col3 = st.columns(3)
        
        with s_col1:
            s_vac = st.slider(
                "Vacuum (kg/cm²)",
                -0.60,
                -0.99,
                -0.92,
                step=0.001,
                help="Standard: -0.92"
            )
            s_ms = st.slider("MS Temp (°C)", 510, 545, 540)
        
        with s_col2:
            s_fg = st.slider("FG Temp (°C)", 110, 160, 130)
            s_apc = st.slider("APC (%)", 5.0, 10.0, 6.5, step=0.1)
        
        with s_col3:
            s_gcv = st.slider("Coal GCV (kcal/kg)", 2800, 4500, 3600)
            s_bio = st.slider("Biomass (%)", 0, 20, 0)
        
        # Simulation calculations
        sim_vac_loss = (abs(s_vac) - 0.92) * 100 * -15
        sim_ms_loss = (540 - s_ms) * 0.7
        sim_fg_loss = (s_fg - 130) / 2
        sim_hr_impact = sim_vac_loss + sim_ms_loss + sim_fg_loss
        
        base_revenue = 25200000
        sim_apc_loss = base_revenue * ((s_apc - 6.5) / 100) * -1
        sim_hr_profit = (-1 * sim_hr_impact) * 8.4 * 1000
        total_sim_impact = sim_hr_profit + sim_apc_loss
        
        st.divider()
        
        r1, r2, r3 = st.columns(3)
        
        with r1:
            st.metric(
                "Net Heat Rate Impact",
                f"{sim_hr_impact:.1f} kcal/kWh",
                delta_color="inverse"
            )
        
        with r2:
            st.metric("Daily Profit Impact", format_lacs(total_sim_impact))
        
        with r3:
            st.metric("APC Cost Impact", format_lacs(sim_apc_loss))
    
    # TAB 10: ANALYTICS
    with tabs[9]:
        st.markdown("### 📊 Interactive Analytics Playground")
        
        gb_raw = analytics_state.get('greenbelt_raw', [])
        ash_raw = analytics_state.get('ash_raw', [])
        
        if gb_raw:
            df_gb = pd.DataFrame(gb_raw)
            
            st.markdown('<div class="section-header">🌳 Greenbelt Simulator</div>', unsafe_allow_html=True)
            
            col_gb1, col_gb2 = st.columns(2)
            
            with col_gb1:
                all_years = sorted(df_gb['Year'].unique(), reverse=True)
                sel_year = st.selectbox("📅 Select Financial Year", all_years)
            
            with col_gb2:
                all_species = sorted(df_gb['Species'].unique())
                sel_species = st.multiselect(
                    "🌿 Filter Species",
                    all_species,
                    default=all_species[:5]
                )
            
            df_yr = df_gb[df_gb['Year'] == sel_year]
            if sel_species:
                df_yr = df_yr[df_yr['Species'].isin(sel_species)]
            
            total_planted = df_yr['Planted'].sum()
            total_matured = df_yr['Matured'].sum()
            avg_survival = (total_matured / total_planted * 100) if total_planted > 0 else 0
            mortality = 100 - avg_survival
            carb_sink = total_matured * 25
            carb_sink_ton = carb_sink / 1000
            
            k1, k2, k3, k4 = st.columns(4)
            
            k1.metric("Survival Rate", f"{avg_survival:.1f}%")
            k2.metric("Mortality Rate", f"{mortality:.1f}%", delta_color="inverse")
            k3.metric("Matured Alive", f"{total_matured:,}")
            k4.metric("CO2 Sink Potential", f"{carb_sink_ton:,.1f} Tons/Yr")
            
            st.divider()
            
            p1, p2 = st.columns(2)
            
            with p1:
                fig_mix = px.pie(
                    df_yr,
                    values='Planted',
                    names='Species',
                    title=f"Planted Mix ({sel_year})",
                    hole=0.4,
                    template='plotly_dark'
                )
                fig_mix.update_layout(
                    paper_bgcolor='rgba(0,0,0,0)',
                    font_color='white'
                )
                st.plotly_chart(fig_mix, use_container_width=True)
            
            with p2:
                df_yr['Dead'] = df_yr['Planted'] - df_yr['Matured']
                
                fig_surv = px.bar(
                    df_yr,
                    x='Species',
                    y=['Matured', 'Dead'],
                    title="Survival vs Mortality by Species",
                    barmode='stack',
                    color_discrete_sequence=['#10b981', '#ef4444'],
                    template='plotly_dark'
                )
                fig_surv.update_layout(
                    paper_bgcolor='rgba(0,0,0,0)',
                    font_color='white'
                )
                st.plotly_chart(fig_surv, use_container_width=True)
            
            st.markdown("#### 🌡️ Plantation Heatmap")
            
            hm_view = st.radio(
                "Heatmap View",
                ["Species vs Year", "Year vs Species"],
                horizontal=True
            )
            
            if hm_view == "Species vs Year":
                fig_heat = px.density_heatmap(
                    df_gb,
                    x='Year',
                    y='Species',
                    z='Planted',
                    color_continuous_scale='Greens'
                )
            else:
                fig_heat = px.density_heatmap(
                    df_gb,
                    x='Species',
                    y='Year',
                    z='Planted',
                    color_continuous_scale='Greens'
                )
            
            fig_heat.update_layout(
                paper_bgcolor='rgba(0,0,0,0)',
                font_color='white'
            )
            st.plotly_chart(fig_heat, use_container_width=True)
        else:
            st.info("Greenbelt data missing in 'analytics_state_v1.json'.")
        
        st.divider()
        
        if ash_raw:
            df_ash = pd.DataFrame(ash_raw)
            
            st.markdown('<div class="section-header">🪨 Ash Utilization Analytics</div>', unsafe_allow_html=True)
            
            col_ash1, col_ash2 = st.columns(2)
            
            with col_ash1:
                sel_month = st.selectbox("📅 Select Month", df_ash['Month'].unique())
            
            with col_ash2:
                sim_boost = st.slider("🚀 Simulate Efficiency Boost (%)", 0, 50, 0)
            
            latest_ash = df_ash[df_ash['Month'] == sel_month].iloc[0]
            
            ignore = ['Month', 'Generation', 'Utilization']
            valid_cols = [
                c for c in df_ash.columns
                if c not in ignore
                and isinstance(latest_ash[c], (int, float))
                and latest_ash[c] > 0
            ]
            
            col1, col2 = st.columns(2)
            
            with col1:
                pie_vals = {k: latest_ash[k] for k in valid_cols}
                
                fig_ash_pie = px.pie(
                    values=list(pie_vals.values()),
                    names=list(pie_vals.keys()),
                    title=f"Utilization Split ({sel_month})",
                    hole=0.4,
                    template='plotly_dark'
                )
                fig_ash_pie.update_layout(
                    paper_bgcolor='rgba(0,0,0,0)',
                    font_color='white'
                )
                st.plotly_chart(fig_ash_pie, use_container_width=True)
            
            with col2:
                fig_area = px.area(
                    df_ash,
                    x='Month',
                    y=valid_cols,
                    title="Utilization Trend (All Months)",
                    template='plotly_dark'
                )
                
                util_col = 'Utilization' if 'Utilization' in df_ash.columns else df_ash.columns[2]
                sim_line = df_ash[util_col] * (1 + sim_boost / 100)
                
                fig_area.add_scatter(
                    x=df_ash['Month'],
                    y=sim_line,
                    mode='lines',
                    name='Simulated Target',
                    line=dict(color='white', dash='dash')
                )
                
                fig_area.update_layout(
                    paper_bgcolor='rgba(0,0,0,0)',
                    font_color='white'
                )
                st.plotly_chart(fig_area, use_container_width=True)
        else:
            st.info("Upload 'ash.xlsx' to activate Ash Analytics.")
    
    # TAB 11: INFO
    with tabs[10]:
        st.markdown("### 📚 Knowledge Base & Formulas")
        
        st.markdown("#### 1. Financial Mechanics (Profit)")
        st.latex(r"Profit = (Target_{HR} - Actual_{HR}) \times Generation \times 1000")
        st.write("""
        > **Why 1000?** It represents the conversion factor translating thermal efficiency 
        savings directly into Rupees based on GCV and Coal Costs.
        """)
        
        st.markdown("#### 2. Technical Hygiene (5S Score)")
        st.latex(r"Penalty = \frac{|Vac_{dev}| + MS_{dev} + FG_{dev} + Spray_{dev}}{3}")
        st.latex(r"Score = 100 - Penalty")
        
        st.markdown("#### 3. Ash Pond Lifecycle")
        st.latex(r"Remaining\_Days = \frac{Total\_Capacity_{18 months}}{Daily\_Gen - Daily\_Util}")
        st.write("""
        > **Rule:** If generation exceeds utilization, the pond begins to fill. 
        Defaults to 9999 days (Stable) if $Util \ge Gen$.
        """)
        
        st.markdown("#### 4. Carbon Footprint & Sustainability")
        st.latex(r"Daily\_CO_2\_Emitted = \frac{Generation \times Heat Rate \times 1000}{GCV} \times 1.7")
        st.latex(r"Daily\_Tree\_Offset = \frac{Total\_Matured\_Trees \times 25 \text{ kg}}{365 \times 1000}")
        
        st.markdown("#### 5. Renewables Equivalency")
        st.write("""
        - **Solar Homes:** 1 MU Solar = 1 Million Units. Avg Home consumes ~4 units/day.
        - **Biomass:** 1 kg Biomass ≈ 1.2 kWh Electricity equivalent (avoided coal).
        """)

if __name__ == "__main__":
    main()
"""
GMR Dashboard - Advanced Features Module
==========================================

Copy these functions into your enhanced dashboard to add new capabilities.
Each function is standalone and can be integrated independently.
"""

import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.express as px
from datetime import datetime, timedelta


# ==================== 1. PREDICTIVE ANALYTICS ====================

def predict_hr_trend(hist_df, unit_id, days_ahead=7):
    """
    Predict heat rate trend using simple linear regression
    
    Args:
        hist_df: Historical dataframe
        unit_id: Unit to predict for ('1', '2', or '3')
        days_ahead: Number of days to predict
    
    Returns:
        DataFrame with predictions
    """
    from sklearn.linear_model import LinearRegression
    
    # Filter for specific unit and running status
    unit_data = hist_df[
        (hist_df['Unit'] == unit_id) & 
        (hist_df['HR'] > 100)
    ].copy()
    
    if len(unit_data) < 7:
        return None
    
    # Prepare features
    unit_data['days_since_start'] = (
        unit_data['Date'] - unit_data['Date'].min()
    ).dt.days
    
    X = unit_data[['days_since_start']].values
    y = unit_data['HR'].values
    
    # Train model
    model = LinearRegression()
    model.fit(X, y)
    
    # Predict
    last_day = unit_data['days_since_start'].max()
    future_days = np.array([
        [last_day + i] for i in range(1, days_ahead + 1)
    ])
    predictions = model.predict(future_days)
    
    # Create prediction dataframe
    future_dates = [
        unit_data['Date'].max() + timedelta(days=i) 
        for i in range(1, days_ahead + 1)
    ]
    
    pred_df = pd.DataFrame({
        'Date': future_dates,
        'Predicted_HR': predictions,
        'Trend': 'Improving' if model.coef_[0] < 0 else 'Degrading'
    })
    
    return pred_df


def render_predictive_analytics(hist_df):
    """Render the predictive analytics section"""
    st.markdown("### 🔮 Predictive Analytics")
    
    col1, col2 = st.columns(2)
    
    with col1:
        selected_unit = st.selectbox("Select Unit", ['1', '2', '3'])
    
    with col2:
        forecast_days = st.slider("Forecast Days", 3, 14, 7)
    
    predictions = predict_hr_trend(hist_df, selected_unit, forecast_days)
    
    if predictions is not None:
        # Show prediction chart
        fig = go.Figure()
        
        # Historical data
        unit_hist = hist_df[
            (hist_df['Unit'] == selected_unit) & 
            (hist_df['HR'] > 100)
        ].tail(30)
        
        fig.add_trace(go.Scatter(
            x=unit_hist['Date'],
            y=unit_hist['HR'],
            mode='lines+markers',
            name='Historical',
            line=dict(color='#38bdf8')
        ))
        
        # Predictions
        fig.add_trace(go.Scatter(
            x=predictions['Date'],
            y=predictions['Predicted_HR'],
            mode='lines+markers',
            name='Predicted',
            line=dict(color='#fbbf24', dash='dash')
        ))
        
        fig.update_layout(
            title=f"Unit {selected_unit} - Heat Rate Forecast",
            template='plotly_dark',
            paper_bgcolor='rgba(0,0,0,0)',
            plot_bgcolor='rgba(0,0,0,0)',
            font_color='white',
            height=400
        )
        
        st.plotly_chart(fig, use_container_width=True)
        
        # Show prediction table
        st.dataframe(
            predictions.style.background_gradient(
                subset=['Predicted_HR'],
                cmap='RdYlGn_r'
            ),
            use_container_width=True
        )
        
        # Trend indicator
        trend = predictions['Trend'].iloc[0]
        if trend == 'Improving':
            st.success("📈 Trend: Heat Rate Improving (Better Efficiency)")
        else:
            st.warning("📉 Trend: Heat Rate Degrading (Maintenance Recommended)")
    else:
        st.info("Insufficient data for prediction. Need at least 7 days of history.")


# ==================== 2. REAL-TIME ALERTS ====================

def check_critical_alerts(units_data, plant_conf, lagoon_fill_pct):
    """
    Check for critical conditions and generate alerts
    
    Returns:
        List of alert dictionaries
    """
    alerts = []
    
    for u in units_data:
        # Skip shutdown units
        if u['status'] == 'SHUTDOWN':
            continue
        
        # Critical SOx violation
        if u['sox'] > plant_conf['limits']['sox'] * 1.1:
            alerts.append({
                'unit': u['id'],
                'type': 'danger',
                'icon': '🚨',
                'title': 'Critical Emissions',
                'message': f"SOx at {u['sox']:.0f} mg/Nm³ (Limit: {plant_conf['limits']['sox']})"
            })
        
        # NOx warning
        if u['nox'] > plant_conf['limits']['nox'] * 0.9:
            alerts.append({
                'unit': u['id'],
                'type': 'warning',
                'icon': '⚠️',
                'title': 'Emissions Warning',
                'message': f"NOx approaching limit: {u['nox']:.0f} mg/Nm³"
            })
        
        # Significant losses
        if u['profit'] < -100000:
            alerts.append({
                'unit': u['id'],
                'type': 'danger',
                'icon': '💰',
                'title': 'Financial Alert',
                'message': f"Significant loss: ₹{u['profit']:,.0f}"
            })
        
        # Low 5S score
        if u['score'] < 70:
            alerts.append({
                'unit': u['id'],
                'type': 'warning',
                'icon': '📊',
                'title': 'Performance Alert',
                'message': f"5S Score below threshold: {u['score']:.1f}/100"
            })
        
        # High vacuum loss
        if u['losses']['Vacuum'] > 30:
            alerts.append({
                'unit': u['id'],
                'type': 'warning',
                'icon': '🔧',
                'title': 'Maintenance Required',
                'message': f"High vacuum loss: {u['losses']['Vacuum']:.1f} kcal/kWh"
            })
    
    # Lagoon critical
    if lagoon_fill_pct > 85:
        alerts.append({
            'unit': 'Fleet',
            'type': 'danger',
            'icon': '🪨',
            'title': 'Ash Lagoon Critical',
            'message': f"Lagoon fill at {lagoon_fill_pct:.1f}% - Immediate action required"
        })
    elif lagoon_fill_pct > 75:
        alerts.append({
            'unit': 'Fleet',
            'type': 'warning',
            'icon': '🪨',
            'title': 'Ash Lagoon Warning',
            'message': f"Lagoon fill at {lagoon_fill_pct:.1f}% - Plan utilization increase"
        })
    
    return alerts


def render_alerts_dashboard(units_data, plant_conf, lagoon_fill_pct):
    """Render real-time alerts dashboard"""
    alerts = check_critical_alerts(units_data, plant_conf, lagoon_fill_pct)
    
    if alerts:
        st.markdown("### 🚨 Active Alerts")
        
        # Count by type
        danger_count = sum(1 for a in alerts if a['type'] == 'danger')
        warning_count = sum(1 for a in alerts if a['type'] == 'warning')
        
        col1, col2, col3 = st.columns(3)
        col1.metric("Total Alerts", len(alerts))
        col2.metric("Critical", danger_count, delta_color="inverse")
        col3.metric("Warnings", warning_count)
        
        # Display alerts
        for alert in alerts:
            alert_class = f"alert-{alert['type']}"
            st.markdown(f"""
            <div class="alert-box {alert_class}">
                <div style="display: flex; align-items: center; gap: 10px;">
                    <span style="font-size: 24px;">{alert['icon']}</span>
                    <div>
                        <div style="font-weight: 700; font-size: 16px;">
                            Unit {alert['unit']}: {alert['title']}
                        </div>
                        <div style="font-size: 14px; margin-top: 5px;">
                            {alert['message']}
                        </div>
                    </div>
                </div>
            </div>
            """, unsafe_allow_html=True)
    else:
        st.success("✅ No active alerts - All systems operating normally")


# ==================== 3. BENCHMARKING DASHBOARD ====================

def create_unit_comparison_radar(units_data):
    """Create radar chart comparing all units"""
    
    # Normalize metrics for radar chart
    metrics = {
        'Efficiency': [],
        'Profit': [],
        '5S Score': [],
        'Emissions': [],
        'Utilization': []
    }
    
    for u in units_data:
        if u['status'] != 'SHUTDOWN':
            # Efficiency (inverse of HR deviation)
            hr_dev = abs(u['hr'] - u['target_hr'])
            metrics['Efficiency'].append(max(0, 100 - hr_dev / 10))
            
            # Profit (normalized to 0-100)
            profit_norm = max(0, min(100, (u['profit'] / 200000) * 100))
            metrics['Profit'].append(profit_norm)
            
            # 5S Score
            metrics['5S Score'].append(u['score'])
            
            # Emissions (inverse - lower is better)
            sox_score = max(0, 100 - (u['sox'] / u['limits']['sox']) * 100)
            metrics['Emissions'].append(sox_score)
            
            # Utilization (based on generation)
            util_score = (u['gen'] / 10.0) * 100
            metrics['Utilization'].append(min(100, util_score))
    
    # Create radar chart
    fig = go.Figure()
    
    categories = list(metrics.keys())
    
    for i, u in enumerate(units_data):
        if u['status'] != 'SHUTDOWN':
            values = [metrics[cat][i] for cat in categories]
            
            fig.add_trace(go.Scatterpolar(
                r=values,
                theta=categories,
                fill='toself',
                name=f"Unit {u['id']}",
                line=dict(width=2)
            ))
    
    fig.update_layout(
        polar=dict(
            radialaxis=dict(
                visible=True,
                range=[0, 100],
                tickfont=dict(color='white')
            )
        ),
        showlegend=True,
        template='plotly_dark',
        paper_bgcolor='rgba(0,0,0,0)',
        font_color='white',
        height=500,
        title="Unit Performance Comparison"
    )
    
    return fig


def render_benchmarking_dashboard(units_data, hist_df):
    """Render comprehensive benchmarking dashboard"""
    st.markdown("### 📊 Fleet Benchmarking")
    
    # Current comparison
    col1, col2 = st.columns([2, 1])
    
    with col1:
        fig_radar = create_unit_comparison_radar(units_data)
        st.plotly_chart(fig_radar, use_container_width=True)
    
    with col2:
        st.markdown("#### 🏆 Rankings")
        
        # Create rankings
        running_units = [u for u in units_data if u['status'] != 'SHUTDOWN']
        
        # By profit
        ranked_profit = sorted(running_units, key=lambda x: x['profit'], reverse=True)
        st.markdown("**💰 Profit Leaders:**")
        for i, u in enumerate(ranked_profit, 1):
            medal = "🥇" if i == 1 else "🥈" if i == 2 else "🥉"
            st.markdown(f"{medal} Unit {u['id']}: ₹{u['profit']:,.0f}")
        
        st.divider()
        
        # By efficiency
        ranked_hr = sorted(running_units, key=lambda x: x['hr'])
        st.markdown("**⚡ Efficiency Leaders:**")
        for i, u in enumerate(ranked_hr, 1):
            medal = "🥇" if i == 1 else "🥈" if i == 2 else "🥉"
            st.markdown(f"{medal} Unit {u['id']}: {u['hr']:.0f} kcal/kWh")
    
    # Historical benchmarking
    if not hist_df.empty:
        st.markdown("#### 📈 30-Day Performance Trends")
        
        last_30 = hist_df[hist_df['Date'] >= (datetime.now() - timedelta(days=30))]
        
        # Average by unit
        unit_avg = last_30.groupby('Unit').agg({
            'HR': 'mean',
            'Profit': 'sum',
            'SOx': 'mean',
            'NOx': 'mean'
        }).reset_index()
        
        # Create comparison table
        st.dataframe(
            unit_avg.style.background_gradient(
                subset=['HR'],
                cmap='RdYlGn_r'
            ).background_gradient(
                subset=['Profit'],
                cmap='RdYlGn'
            ),
            use_container_width=True
        )


# ==================== 4. WHAT-IF SCENARIO PLANNER ====================

def scenario_calculator(scenario_params, base_unit_data):
    """Calculate outcomes for a given scenario"""
    
    # Extract parameters
    target_hr = scenario_params['target_hr']
    coal_price = scenario_params['coal_price']
    capacity_factor = scenario_params['capacity_factor']
    ash_util_pct = scenario_params['ash_utilization']
    
    # Calculate adjusted generation
    adjusted_gen = base_unit_data['gen'] * capacity_factor
    
    # Calculate profit impact
    hr_improvement = base_unit_data['hr'] - target_hr
    profit_delta = hr_improvement * adjusted_gen * 1000
    
    # Coal cost impact
    coal_tons = (adjusted_gen * target_hr * 1000) / 3600
    coal_cost = coal_tons * coal_price
    
    # Ash utilization benefit
    ash_gen = coal_tons * 0.35  # 35% ash
    ash_util_tons = ash_gen * (ash_util_pct / 100)
    ash_revenue = ash_util_tons * 500  # ₹500 per ton
    
    total_impact = profit_delta + ash_revenue - coal_cost
    
    return {
        'daily_profit': total_impact,
        'monthly_profit': total_impact * 30,
        'annual_profit': total_impact * 365,
        'hr_achieved': target_hr,
        'coal_tons': coal_tons,
        'ash_utilized': ash_util_tons
    }


def render_scenario_planner(units_data):
    """Render what-if scenario planning tool"""
    st.markdown("### 🎯 What-If Scenario Planner")
    
    st.info("""
    **Scenario Planning Tool**: Model different operational strategies and compare outcomes.
    Adjust parameters below to see projected financial and operational impacts.
    """)
    
    # Select base unit
    base_unit_id = st.selectbox("Select Base Unit", ['1', '2', '3'])
    base_unit = next(u for u in units_data if u['id'] == base_unit_id)
    
    # Create scenarios
    num_scenarios = st.slider("Number of Scenarios to Compare", 2, 4, 3)
    
    scenarios = []
    scenario_results = []
    
    cols = st.columns(num_scenarios)
    
    for i in range(num_scenarios):
        with cols[i]:
            st.markdown(f"#### Scenario {i + 1}")
            
            scenario_name = st.text_input(
                "Name",
                f"Scenario {i + 1}",
                key=f"name_{i}"
            )
            
            target_hr = st.number_input(
                "Target HR",
                value=int(base_unit['target_hr'] - (i * 10)),
                key=f"hr_{i}"
            )
            
            capacity = st.slider(
                "Capacity Factor",
                0.5,
                1.0,
                0.85 - (i * 0.05),
                key=f"cap_{i}"
            )
            
            coal_price = st.number_input(
                "Coal Price (₹/kg)",
                value=4.5 + (i * 0.2),
                step=0.1,
                key=f"coal_{i}"
            )
            
            ash_util = st.slider(
                "Ash Utilization %",
                50,
                100,
                75 + (i * 5),
                key=f"ash_{i}"
            )
            
            scenario = {
                'name': scenario_name,
                'target_hr': target_hr,
                'capacity_factor': capacity,
                'coal_price': coal_price,
                'ash_utilization': ash_util
            }
            
            result = scenario_calculator(scenario, base_unit)
            
            scenarios.append(scenario)
            scenario_results.append({**scenario, **result})
            
            # Display quick metrics
            st.metric(
                "Daily Profit",
                f"₹{result['daily_profit']:,.0f}",
                delta=f"vs Current: ₹{result['daily_profit'] - base_unit['profit']:,.0f}"
            )
            
            st.metric(
                "Annual Projection",
                f"₹{result['annual_profit'] / 100000:.2f} Lac"
            )
    
    # Comparison visualization
    st.markdown("#### 📊 Scenario Comparison")
    
    comparison_df = pd.DataFrame(scenario_results)
    
    # Create comparison chart
    fig = go.Figure()
    
    metrics_to_compare = ['daily_profit', 'monthly_profit', 'annual_profit']
    metric_names = ['Daily', 'Monthly', 'Annual']
    
    for i, metric in enumerate(metrics_to_compare):
        fig.add_trace(go.Bar(
            name=metric_names[i],
            x=comparison_df['name'],
            y=comparison_df[metric],
            text=comparison_df[metric].apply(lambda x: f"₹{x/100000:.1f}L"),
            textposition='auto'
        ))
    
    fig.update_layout(
        title="Profit Comparison Across Scenarios",
        template='plotly_dark',
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(0,0,0,0)',
        font_color='white',
        barmode='group',
        height=400
    )
    
    st.plotly_chart(fig, use_container_width=True)
    
    # Detailed comparison table
    st.markdown("#### 📋 Detailed Comparison")
    
    st.dataframe(
        comparison_df[[
            'name',
            'target_hr',
            'capacity_factor',
            'daily_profit',
            'monthly_profit',
            'coal_tons',
            'ash_utilized'
        ]].style.format({
            'target_hr': '{:.0f}',
            'capacity_factor': '{:.2%}',
            'daily_profit': '₹{:,.0f}',
            'monthly_profit': '₹{:,.0f}',
            'coal_tons': '{:,.0f}',
            'ash_utilized': '{:,.0f}'
        }).background_gradient(
            subset=['daily_profit', 'monthly_profit'],
            cmap='RdYlGn'
        ),
        use_container_width=True
    )
    
    # Recommendations
    best_scenario = max(scenario_results, key=lambda x: x['annual_profit'])
    
    st.success(f"""
    🎯 **Recommended Scenario:** {best_scenario['name']}
    
    - **Projected Annual Profit:** ₹{best_scenario['annual_profit'] / 100000:.2f} Lac
    - **Target Heat Rate:** {best_scenario['target_hr']:.0f} kcal/kWh
    - **Required Capacity Factor:** {best_scenario['capacity_factor']:.1%}
    """)


# ==================== 5. EXPORT & REPORTING ====================

def create_comprehensive_excel_report(units_data, hist_df, fleet_metrics):
    """
    Generate comprehensive Excel report with multiple sheets
    
    Returns:
        BytesIO object containing Excel file
    """
    from io import BytesIO
    
    output = BytesIO()
    
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        # 1. Executive Summary
        summary_df = pd.DataFrame({
            'Metric': [
                'Report Date',
                'Total Generation (MU)',
                'Fleet P&L (₹)',
                'MTD Profit (₹)',
                'Average Heat Rate',
                'Fleet 5S Score',
                'Compliance Status'
            ],
            'Value': [
                datetime.now().strftime('%Y-%m-%d'),
                f"{sum(u['gen'] for u in units_data):.2f}",
                f"{fleet_metrics['profit']:,.0f}",
                f"{fleet_metrics['mtd_profit']:,.0f}",
                f"{sum(u['hr'] for u in units_data) / len(units_data):.2f}",
                f"{sum(u['score'] for u in units_data) / len(units_data):.1f}",
                "COMPLIANT"
            ]
        })
        summary_df.to_excel(writer, sheet_name='Executive Summary', index=False)
        
        # 2. Unit-wise Performance
        unit_df = pd.DataFrame([
            {
                'Unit': u['id'],
                'Status': u['status'],
                'Generation (MU)': u['gen'],
                'Heat Rate (kcal/kWh)': u['hr'],
                'Target HR': u['target_hr'],
                'Deviation': u['hr'] - u['target_hr'],
                'Profit (₹)': u['profit'],
                'SOx (mg/Nm³)': u['sox'],
                'NOx (mg/Nm³)': u['nox'],
                '5S Score': u['score'],
                'CO2 Emitted (T)': u['co2_emitted']
            }
            for u in units_data
        ])
        unit_df.to_excel(writer, sheet_name='Unit Performance', index=False)
        
        # 3. Loss Breakdown
        loss_data = []
        for u in units_data:
            for param, loss in u['losses'].items():
                loss_data.append({
                    'Unit': u['id'],
                    'Parameter': param,
                    'Loss (kcal/kWh)': loss
                })
        loss_df = pd.DataFrame(loss_data)
        loss_df.to_excel(writer, sheet_name='Loss Analysis', index=False)
        
        # 4. Ash Management
        ash_df = pd.DataFrame([
            {
                'Unit': u['id'],
                'Ash Generated (T)': u['ash']['generated'],
                'Ash Utilized (T)': u['ash']['utilized'],
                'To Cement (T)': u['ash']['cem_util'],
                'To Bricks (T)': u['ash']['brick_util'],
                'Bricks Made': u['ash']['bricks_made'],
                'Utilization %': (u['ash']['utilized'] / u['ash']['generated'] * 100) 
                                  if u['ash']['generated'] > 0 else 0
            }
            for u in units_data
        ])
        ash_df.to_excel(writer, sheet_name='Ash Management', index=False)
        
        # 5. Historical Trends
        if not hist_df.empty:
            # Last 30 days
            recent_hist = hist_df.tail(90)
            recent_hist.to_excel(writer, sheet_name='Historical Data', index=False)
        
        # 6. Compliance Report
        compliance_df = pd.DataFrame([
            {
                'Unit': u['id'],
                'SOx (mg/Nm³)': u['sox'],
                'SOx Limit': u['limits']['sox'],
                'SOx Status': '✓' if u['sox'] <= u['limits']['sox'] else '✗',
                'NOx (mg/Nm³)': u['nox'],
                'NOx Limit': u['limits']['nox'],
                'NOx Status': '✓' if u['nox'] <= u['limits']['nox'] else '✗'
            }
            for u in units_data
        ])
        compliance_df.to_excel(writer, sheet_name='Compliance', index=False)
    
    output.seek(0)
    return output


def render_export_section(units_data, hist_df, fleet_metrics):
    """Render export and reporting section"""
    st.markdown("### 📥 Export & Reports")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        if st.button("📊 Generate Excel Report", use_container_width=True):
            with st.spinner("Generating comprehensive report..."):
                excel_data = create_comprehensive_excel_report(
                    units_data,
                    hist_df,
                    fleet_metrics
                )
                
                st.download_button(
                    label="⬇️ Download Excel Report",
                    data=excel_data,
                    file_name=f"GMR_Report_{datetime.now().strftime('%Y%m%d')}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    use_container_width=True
                )
    
    with col2:
        if st.button("📄 Generate CSV", use_container_width=True):
            # Simple CSV export
            unit_df = pd.DataFrame([
                {
                    'Unit': u['id'],
                    'Generation': u['gen'],
                    'Heat_Rate': u['hr'],
                    'Profit': u['profit'],
                    'SOx': u['sox'],
                    'NOx': u['nox'],
                    'Score': u['score']
                }
                for u in units_data
            ])
            
            csv = unit_df.to_csv(index=False)
            
            st.download_button(
                label="⬇️ Download CSV",
                data=csv,
                file_name=f"GMR_Data_{datetime.now().strftime('%Y%m%d')}.csv",
                mime="text/csv",
                use_container_width=True
            )
    
    with col3:
        st.info("**Scheduled Reports**: Configure automated daily/weekly reports in settings")


# ==================== 6. MAINTENANCE PREDICTOR ====================

def predict_maintenance_needs(unit_data, hist_df, unit_id):
    """
    Predict maintenance needs based on performance degradation
    
    Returns:
        Dict with maintenance recommendations
    """
    maintenance_items = []
    
    # Check heat rate trend
    if not hist_df.empty:
        recent_hr = hist_df[
            (hist_df['Unit'] == unit_id) & 
            (hist_df['HR'] > 100)
        ].tail(7)['HR'].mean()
        
        if recent_hr > unit_data['target_hr'] + 50:
            maintenance_items.append({
                'priority': 'High',
                'component': 'Boiler Tubes',
                'issue': 'Heat rate degradation detected',
                'recommendation': 'Schedule tube cleaning / soot blowing',
                'estimated_improvement': f"{recent_hr - unit_data['target_hr']:.0f} kcal/kWh"
            })
    
    # Check vacuum performance
    if abs(unit_data['inputs']['vac']) < 0.85:
        maintenance_items.append({
            'priority': 'High',
            'component': 'Condenser',
            'issue': f"Low vacuum: {unit_data['inputs']['vac']:.3f} kg/cm²",
            'recommendation': 'Check condenser tubes, cooling water flow',
            'estimated_improvement': 'Up to 30 kcal/kWh'
        })
    
    # Check MS temperature
    if unit_data['inputs']['ms'] < 530:
        maintenance_items.append({
            'priority': 'Medium',
            'component': 'Superheater',
            'issue': f"Low MS temp: {unit_data['inputs']['ms']:.0f}°C",
            'recommendation': 'Inspect superheater, check spray control',
            'estimated_improvement': 'Up to 15 kcal/kWh'
        })
    
    # Check spray water
    if unit_data['inputs']['spray'] > 25:
        maintenance_items.append({
            'priority': 'Medium',
            'component': 'Spray Control',
            'issue': f"Excessive spray: {unit_data['inputs']['spray']:.1f} TPH",
            'recommendation': 'Adjust spray control system, check setpoints',
            'estimated_improvement': 'Up to 10 kcal/kWh'
        })
    
    return maintenance_items


def render_maintenance_dashboard(units_data, hist_df):
    """Render maintenance prediction dashboard"""
    st.markdown("### 🔧 Predictive Maintenance")
    
    selected_unit_id = st.selectbox("Select Unit for Analysis", ['1', '2', '3'])
    selected_unit = next(u for u in units_data if u['id'] == selected_unit_id)
    
    if selected_unit['status'] == 'SHUTDOWN':
        st.warning("Unit is currently shutdown. Maintenance analysis not applicable.")
        return
    
    # Get maintenance predictions
    maintenance_needs = predict_maintenance_needs(selected_unit, hist_df, selected_unit_id)
    
    if maintenance_needs:
        st.warning(f"⚠️ {len(maintenance_needs)} maintenance items identified")
        
        # Priority summary
        col1, col2, col3 = st.columns(3)
        
        high_priority = sum(1 for m in maintenance_needs if m['priority'] == 'High')
        medium_priority = sum(1 for m in maintenance_needs if m['priority'] == 'Medium')
        low_priority = sum(1 for m in maintenance_needs if m['priority'] == 'Low')
        
        col1.metric("High Priority", high_priority, delta_color="inverse")
        col2.metric("Medium Priority", medium_priority)
        col3.metric("Low Priority", low_priority)
        
        # Display maintenance items
        for i, item in enumerate(maintenance_needs, 1):
            priority_color = {
                'High': '#ef4444',
                'Medium': '#fbbf24',
                'Low': '#10b981'
            }[item['priority']]
            
            st.markdown(f"""
            <div class="glass-card" style="border-left: 4px solid {priority_color}">
                <div style="display: flex; justify-content: space-between; align-items: center;">
                    <div>
                        <div style="font-weight: 700; font-size: 16px; color: white;">
                            {i}. {item['component']}
                        </div>
                        <div style="color: #9ca3af; font-size: 14px; margin-top: 5px;">
                            {item['issue']}
                        </div>
                        <div style="color: white; font-size: 14px; margin-top: 10px;">
                            💡 <b>Recommendation:</b> {item['recommendation']}
                        </div>
                        <div style="color: #10b981; font-size: 13px; margin-top: 5px;">
                            📈 <b>Potential Improvement:</b> {item['estimated_improvement']}
                        </div>
                    </div>
                    <div style="background: {priority_color}; padding: 10px 20px; border-radius: 8px; font-weight: 700;">
                        {item['priority']}
                    </div>
                </div>
            </div>
            """, unsafe_allow_html=True)
    else:
        st.success("✅ No immediate maintenance needs identified. Unit operating optimally.")


# ==================== INTEGRATION GUIDE ====================

"""
INTEGRATION GUIDE:
=================

To add these features to your dashboard, follow these steps:

1. PREDICTIVE ANALYTICS:
   Add to the Analytics tab:
   
   with tabs[9]:  # Analytics tab
       render_predictive_analytics(hist_df)

2. REAL-TIME ALERTS:
   Add at the top of War Room tab:
   
   with tabs[0]:  # War Room
       render_alerts_dashboard(units_data, plant_conf, lagoon_fill_pct)

3. BENCHMARKING:
   Add as a new tab or within Analytics:
   
   render_benchmarking_dashboard(units_data, hist_df)

4. SCENARIO PLANNER:
   Add as a new section in Simulator tab:
   
   with tabs[8]:  # Simulator
       render_scenario_planner(units_data)

5. EXPORT REPORTS:
   Add to a new "Reports" section:
   
   render_export_section(units_data, hist_df, {
       'profit': fleet_profit,
       'mtd_profit': mtd_profit
   })

6. MAINTENANCE PREDICTOR:
   Add as new tab or within Unit tabs:
   
   render_maintenance_dashboard(units_data, hist_df)

Each function is self-contained and can be added independently!
"""

