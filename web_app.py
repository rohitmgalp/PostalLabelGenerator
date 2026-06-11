import streamlit as st
import openpyxl
import os
import sys
import json
import time
import io
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
    if c == 10: 
        return "0"
    elif c == 11: 
        return "5"
    else: 
        return str(c)

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
            if w <= max_width: 
                current_line = test_line
            else:
                if current_line: 
                    lines.append(current_line)
                current_line = word
        if current_line: 
            lines.append(current_line)
    return '\n'.join(lines)

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
                    st.error("This User ID is already occupied under an active tracking segment.")
                else:
                    data["users"][user_id] = {
                        "name": reg_name, "email": reg_email, "mobile": reg_mobile, "password": password,
                        "addresses": [], "used_barcodes": [],
                        "barcodes": {atype: {"prefix": "", "current": 0, "end": 0, "suffix": ""} for atype in ARTICLE_TYPES}
                    }
                    save_data(data)
                    st.success("Registration success! Choose 'Login to Existing Profile' mode above to enter.")
    st.stop()

# --- ENTERPRISE INTERFACE DASHBOARD ---
current_user = st.session_state.username
db = load_data()
user_profile = db["users"][current_user]

if "used_barcodes" not in user_profile:
    user_profile["used_barcodes"] = []

col_title, col_logout = st.columns([0.85, 0.15])
with col_title:
    st.title(f"📮 India Post Enterprise Workspace")
    st.caption(f"Client Node: **{user_profile.get('name', current_user)}** | ID: `{current_user}`")
with col_logout:
    if st.button("Core Log Out", use_container_width=True):
        st.session_state.authenticated = False
        st.session_state.username = ""
        st.session_state.web_queue = []
        st.rerun()

tabs_list = ["📋 Dispatch Manager", "⚙️ Settings & Barcode Ranges"]
if current_user.lower() == "admin": 
    tabs_list.append("👥 Admin Panel")
tabs = st.tabs(tabs_list)

# --- TAB: ADMIN PANEL ---
if current_user.lower() == "admin":
    with tabs[2]:
        st.header("👥 Registered User Directory")
        user_records = []
        for uid, info in db["users"].items():
            if uid.lower() == "admin": continue
            user_records.append({
                "User ID": uid, "Full Name": info.get("name", "N/A"),
                "Email ID": info.get("email", "N/A"), "Mobile": info.get("mobile", "N/A"),
                "Saved Profiles": len(info.get("addresses", []))
            })
        if user_records:
            admin_df = pd.DataFrame(user_records)
            st.dataframe(admin_df, use_container_width=True)
            output_admin = io.BytesIO()
            with pd.ExcelWriter(output_admin, engine='openpyxl') as writer:
                admin_df.to_excel(writer, index=False, sheet_name='Users')
            st.download_button(label="📥 Export Client Directory to Excel", data=output_admin.getvalue(), file_name="Registered_Users_Directory.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
        else:
            st.info("No corporate client profiles have registered yet.")

# --- TAB 2: RANGE ALLOCATION SETTINGS ---
with tabs[1]:
    st.header("UPU S10 Barcode Range Setup")
    set_article = st.selectbox("Choose Article Classification", ARTICLE_TYPES, key="setup_art")
    b_data = user_
