import streamlit as st
import openpyxl
import os
import sys
import json
import time
import io
import base64
import pandas as pd
from barcode import Code128
from barcode.writer import ImageWriter
from PIL import Image, ImageDraw, ImageFont

# --- SYSTEM DIRECTORY SETUP ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_FILE = os.path.join(BASE_DIR, "web_postal_data.json")

ARTICLE_TYPES = [
    "Speed Post Parcel", 
    "Indiapost Parcel Retail", 
    "Business Parcel", 
    "Speed Post Parcel COD", 
    "Business Parcel COD"
]

def load_data():
    if not os.path.exists(DATA_FILE):
        return {"users": {}}
    with open(DATA_FILE, "r") as f:
        return json.load(f)

def save_data(data):
    with open(DATA_FILE, "w") as f:
        json.dump(data, f)

# --- UPU S10 COMPLIANT CHECK DIGIT ENGINE ---
def calculate_upu_s10_check_digit(serial_8_digits):
    """Calculates the 9th digit using the Weighted Modulo 11 algorithm"""
    serial_str = f"{int(serial_8_digits):08d}"
    digits = [int(d) for d in serial_str]
    weights = [8, 6, 4, 2, 3, 5, 9, 7]
    total_sum = sum(d * w for d, w in zip(digits, weights))
    remainder = total_sum % 11
    c = 11 - remainder
    if c == 10: return "0"
    elif c == 11: return "5"
    else: return str(c)

# --- TEXT WRAPPING ENGINE ---
def wrap_text_to_pixels(text, draw, font, max_width):
    lines = []
    for p in text.split('\n'):
        words = p.split(' ')
        current_line = ""
        for word in words:
            test_line = current_line + " " + word if current_line else word
            bbox = draw.textbbox((0, 0), test_line, font=font)
            w = bbox[2] - bbox[0]
            if w <= max_width: current_line = test_line
            else:
                if current_line: lines.append(current_line)
                current_line = word
        if current_line: lines.append(current_line)
    return '\n'.join(lines)

# --- PREMIUM BASE64 IMAGE ENCODER ---
def get_base64_image(image_path):
    with open(image_path, "rb") as img_file:
        return base64.b64encode(img_file.read()).decode()

# --- GENERATE SINGLE LABEL CANVAS HELPER ---
def draw_single_label(entry, width_in, height_in):
    DPI = 300
    W_px = int(width_in * DPI)
    H_px = int(height_in * DPI)
    m_px = int(W_px * 0.05)
    
    bc_buffer = io.BytesIO()
    Code128(entry['tracking'], writer=ImageWriter()).write(bc_buffer)
    bc_buffer.seek(0)
    bc_img = Image.open(bc_buffer)
    
    lbl_canvas = Image.new('RGB', (W_px, H_px), color='white')
    draw = ImageDraw.Draw(lbl_canvas)
    scale = min(W_px, H_px)
    
    size_l = max(36, int(scale * 0.058))
    size_m = max(28, int(scale * 0.044))
    size_b = max(32, int(scale * 0.048))
    
    try:
        f_l = ImageFont.load_default(size=size_l)
        f_m = ImageFont.load_default(size=size_m)
        f_b = ImageFont.load_default(size=size_b)
    except:
        f_l = f_m = f_b = ImageFont.load_default()
        
    top_strings = [f"ARTICLE: {entry['article']}"]
    if entry.get('cust_id'): top_strings.append(f"CUST ID: {entry['cust_id']}")
    if entry.get('cod'): top_strings.append(f"COD CHARGES: Rs. {entry['cod']}")
    
    if W_px >= H_px:  # LANDSCAPE MODE
        bc_h_scaled = int(H_px * 0.15)
        bc_w_scaled = int(W_px * 0.65)
        bc_y_pos = H_px - bc_h_scaled - m_px
        col_width = (W_px - (3 * m_px)) // 2
        
        y_left = m_px
        for line in top_strings:
            draw.text((m_px, y_left), line, fill="black", font=f_b)
            b_box = draw.textbbox((0,0), line, font=f_b)
            y_left += (b_box[3] - b_box[1]) + int(H_px * 0.015)
            
        y_left += int(H_px * 0.02)
        draw.text((m_px, y_left), "FROM:", fill="black", font=f_b)
        y_left += int(size_b * 1.2)
        
        w_from = wrap_text_to_pixels(entry['from'], draw, f_m, col_width)
        draw.multiline_text((m_px, y_left), w_from, fill="black", font=f_m, spacing=8)
        
        x_right = m_px + col_width + m_px
        y_right = m_px
        draw.text((x_right, y_right), "TO:", fill="black", font=f_b)
        y_right += int(size_b * 1.2)
        
        w_to = wrap_text_to_pixels(entry['to'], draw, f_l, col_width)
        draw.multiline_text((x_right, y_right), w_to, fill="black", font=f_l, spacing=8)
        
        bc_resized = bc_img.resize((bc_w_scaled, bc_h_scaled))
        lbl_canvas.paste(bc_resized, ((W_px - bc_w_scaled) // 2, bc_y_pos))
    else:  # PORTRAIT MODE
        use_w = W_px - (2 * m_px)
        y_curr = m_px
        for line in top_strings:
            draw.text((m_px, y_curr), line, fill="black", font=f_b)
            b_box = draw.textbbox((0,0), line, font=f_b)
            y_curr += (b_box[3] - b_box[1]) + int(H_px * 0.012)
            
        y_curr += int(H_px * 0.02)
        draw.text((m_px, y_curr), "FROM:", fill="black", font=f_b)
        y_curr += int(size_b * 1.2)
        
        w_from = wrap_text_to_pixels(entry['from'], draw, f_m, use_w)
        draw.multiline_text((m_px, y_curr), w_from, fill="black", font=f_m, spacing=8)
        b_box = draw.multiline_textbbox((m_px, y_curr), w_from, font=f_m, spacing=8)
        y_cursor_from = b_box[3] + int(H_px * 0.04)
        
        draw.text((m_px, y_cursor_from), "TO:", fill="black", font=f_b)
        y_cursor_from += int(size_b * 1.2)
        
        w_to = wrap_text_to_pixels(entry['to'], draw, f_l, use_w)
        draw.multiline_text((m_px, y_cursor_from), w_to, fill="black", font=f_l, spacing=8)
        b_box = draw.multiline_textbbox((m_px, y_cursor_from), w_to, font=f_l, spacing=8)
        y_cursor_to = b_box[3] + int(H_px * 0.04)
        
        bc_h_scaled = int(H_px * 0.12)
        bc_w_scaled = int(W_px * 0.75)
        bc_y_pos = H_px - bc_h_scaled - m_px
        bc_resized = bc_img.resize((bc_w_scaled, bc_h_scaled))
        lbl_canvas.paste(bc_resized, ((W_px - bc_w_scaled) // 2, bc_y_pos))
        
    return lbl_canvas

# --- PREMIUM BACKGROUND INJECTION ---
st.set_page_config(page_title="India Post Enterprise Workspace", page_icon="📮", layout="wide")
bg_file_path = os.path.join(BASE_DIR, "background.png")

if os.path.exists(bg_file_path):
    encoded_bg = get_base64_image(bg_file_path)
    st.markdown(f"""
        <style>
            .stApp {{ background-image: url("data:image/png;base64,{encoded_bg}"); background-size: cover; background-position: center; background-attachment: fixed; }}
            div[data-testid="stColumn"] {{ background-color: rgba(255, 255, 255, 0.92); padding: 30px !important; border-radius: 15px !important; box-shadow: 0 4px 15px rgba(156, 0, 0, 0.05); border: 1px solid rgba(226, 220, 208, 0.6); }}
            .stTextInput input, .stTextArea textarea, .stSelectbox div {{ border-color: #e2dcd0 !important; background-color: #ffffff !important; color: #2b2b2b !important; }}
            div.stButton > button[type="primary"] {{ background-color: #9c0000 !important; color: white !important; border: none !important; font-weight: bold !important; padding: 10px 24px !important; border-radius: 8px !important; }}
            div.stButton > button[type="primary"]:hover {{ background-color: #bd0000 !important; }}
            h1, h2, h3, p, span, label {{ color: #3a0000 !important; }}
        </style>
    """, unsafe_allow_html=True)
else:
    st.markdown("""
        <style>
            .stApp { background-color: #fdfbf7; }
            div.stButton > button[type="primary"] { background-color: #9c0000 !important; color: white !important; }
        </style>
    """, unsafe_allow_html=True)

# --- STREAMLIT STATE INITIALIZATION ---
if 'authenticated' not in st.session_state: st.session_state.authenticated = False
if 'username' not in st.session_state: st.session_state.username = ""
if 'web_queue' not in st.session_state: st.session_state.web_queue = []

# --- AUTHENTICATION SCREEN ---
if not st.session_state.authenticated:
    st.title("📮 India Post - Enterprise Web Portal")
    auth_mode = st.radio("Access Control Node", ["Login to Existing Profile", "Register New Corporate Profile"])
    
    if auth_mode == "Login to Existing Profile":
        st.subheader("Sign In")
        user_id = st.text_input("User ID", key="login_uid").strip()
        password = st.text_input("Password", type="password", key="login_pwd").strip()
        if st.button("Verify & Enter Portal", type="primary"):
            if not user_id or not password:
                st.error("Please enter both User ID and Password fields.")
            else:
                data = load_data()
                if user_id in data["users"] and data["users"][user_id]["password"] == password:
                    st.session_state.authenticated = True
                    st.session_state.username = user_id
                    st.rerun()
                else:
                    st.error("Invalid User ID or Password verification mismatch.")
                    
    else:
        st.subheader("Create Corporate Deployment Account")
        reg_name = st.text_input("Full Name / Company Name").strip()
        reg_email = st.text_input("Email ID").strip()
        reg_mobile = st.text_input("Mobile Number").strip()
        user_id = st.text_input("Create User ID", key="reg_uid").strip()
        password = st.text_input("Create Password", type="password", key="reg_pwd").strip()
        
        if st.button("Register Infrastructure Profile", type="primary"):
            if not reg_name or not reg_email or not reg_mobile or not user_id or not password:
                st.error("All registration field inputs are mandatory values.")
            else:
                data = load_data()
                if user_id in data["users"]:
                    st.error("This User ID is already occupied.")
                else:
                    data["users"][user_id] = {
                        "name": reg_name, "email": reg_email, "mobile": reg_mobile, "password": password,
                        "addresses": [], "used_barcodes": [], "generated_labels": [],
                        "barcodes": {atype: {"prefix": "", "current": 0, "end": 0, "suffix": ""} for atype in ARTICLE_TYPES}
                    }
                    save_data(data)
                    st.success("Registration success! Please log in.")
    st.stop()

# --- ENTERPRISE INTERFACE DASHBOARD ---
current_user = st.session_state.username
db = load_data()
user_profile = db["users"][current_user]

if "used_barcodes" not in user_profile: user_profile["used_barcodes"] = []
if "generated_labels" not in user_profile: user_profile["generated_labels"] = []

st.title("📮 India Post Enterprise Workspace")
st.caption(f"Client Node: **{user_profile.get('name', current_user)}** | ID: `{current_user}`")

col_logout_wrap = st.columns([0.85, 0.15])
with col_logout_wrap[1]:
    if st.button("Core Log Out", use_container_width=True):
        st.session_state.authenticated = False
        st.session_state.username = ""
        st.session_state.web_queue = []
        st.rerun()

tabs_list = ["📋 Dispatch Manager", "⚙️ Settings & Barcode Ranges", "📇 Generated Labels"]
if current_user.lower() == "admin": 
    tabs_list.append("👥 Admin Panel")
tabs = st.tabs(tabs_list)

# --- TAB 3: PERMANENT ARCHIVE (GENERATED LABELS) ---
with tabs[2]:
    st.header("📇 Permanent Generated Labels Registry")
    st.write("Complete operational history ledger across all system print allocations.")
    
    archive = user_profile.get("generated_labels", [])
    
    if not archive:
        st.info("No labels have been permanently generated on this profile node yet.")
    else:
        for idx, item in enumerate(reversed(archive)):
            real_idx = len(archive) - 1 - idx
            
            row_cols = st.columns([0.5, 0.25, 0.25])
            with row_cols[0]:
                st.write(f"**Barcode:** `{item['tracking']}` | **Type:** {item['article']}")
                st.caption(f"**Recipient Summary:** {item['to'].splitlines()[0][:35]}...")
                
            with row_cols[1]:
                lbl_canvas = draw_single_label(item, 6.0, 4.0)
                reprint_buf = io.BytesIO()
                lbl_canvas.save(reprint_buf, "PDF", resolution=300.0)
                st.download_button(
                    label=f"🖨️ Reprint PDF",
                    data=reprint_buf.getvalue(),
                    file_name=f"Reprint_Label_{item['tracking']}.pdf",
                    mime="application/pdf",
                    key=f"rep_{item['tracking']}_{real_idx}"
                )
                
            with row_cols[2]:
                if st.button(f"🗑️ Delete Record", key=f"del_init_{real_idx}"):
                    st.session_state[f"confirm_prompt_{real_idx}"] = True
            
            if st.session_state.get(f"confirm_prompt_{real_idx}", False):
                st.markdown(f"❓ **Do you want to reuse barcode `{item['tracking']}` in your available range stock?**")
                choice_cols = st.columns([0.3, 0.3, 0.4])
                
                with choice_cols[0]:
                    if st.button("Yes (Return to Range)", key=f"re_yes_{real_idx}"):
                        if item['tracking'] in user_profile["used_barcodes"]:
                            user_profile["used_barcodes"].remove(item['tracking'])
                        user_profile
