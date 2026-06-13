import streamlit as st
import openpyxl
import os
import json
import time
import io
import re
import pandas as pd
from barcode import Code128
from barcode.writer import ImageWriter
from PIL import Image, ImageDraw, ImageFont

# --- SYSTEM CONFIG ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_FILE = os.path.join(BASE_DIR, "web_postal_data.json")

def load_data():
    if not os.path.exists(DATA_FILE): return {"users": {}}
    with open(DATA_FILE, "r") as f: return json.load(f)

def save_data(data):
    with open(DATA_FILE, "w") as f: json.dump(data, f)

# --- UTILS ---
def extract_pincode_and_mobile(text):
    pincode, mobile = "", ""
    if not text: return pincode, mobile
    chunks = re.findall(r'\+?\d+', text)
    for chunk in chunks:
        digits_only = chunk.replace('+', '')
        if len(digits_only) == 6: pincode = digits_only
        elif len(digits_only) == 10: mobile = digits_only
        elif len(digits_only) in [11, 12, 13]: mobile = digits_only[-10:]
    return pincode, mobile

@st.cache_data
def load_pincode_db():
    csv_path = os.path.join(BASE_DIR, "all_india_pincode_directory_2025.csv")
    if not os.path.exists(csv_path): return {}
    df = pd.read_csv(csv_path, usecols=['pincode', 'district', 'statename'], dtype={'pincode': str})
    df.columns = [c.lower().strip() for c in df.columns]
    df['pincode'] = df['pincode'].astype(str).str.strip().str.replace(r'\.0$', '', regex=True)
    return df.drop_duplicates(subset=['pincode'], keep='first').set_index('pincode').to_dict(orient='index')

# --- CALLBACKS ---
def update_recipient_data():
    text = st.session_state.recipient_input
    pin, mob = extract_pincode_and_mobile(text)
    st.session_state.temp_pin = pin
    st.session_state.temp_mob = mob

def update_sender_data():
    text = st.session_state.sender_input
    _, mob = extract_pincode_and_mobile(text)
    st.session_state.temp_s_mob = mob

# --- APP LAYOUT ---
st.set_page_config(layout="wide")

# State holders
if "temp_pin" not in st.session_state: st.session_state.temp_pin = ""
if "temp_mob" not in st.session_state: st.session_state.temp_mob = ""
if "temp_s_mob" not in st.session_state: st.session_state.temp_s_mob = ""

st.title("📮 Dispatch Manager")

col1, col2 = st.columns(2)

with col1:
    st.subheader("Sender Details")
    s_input = st.text_area("Sender Address", key="sender_input", on_change=update_sender_data)
    s_mob = st.text_input("Sender Mobile", value=st.session_state.temp_s_mob)

with col2:
    st.subheader("Recipient Details")
    r_input = st.text_area("Recipient Address", key="recipient_input", on_change=update_recipient_data)
    r_mob = st.text_input("Receiver Mobile", value=st.session_state.temp_mob)
    r_pin = st.text_input("Pincode", value=st.session_state.temp_pin)

if st.button("Stage Parcel"):
    st.session_state.web_queue.append({
        "from": s_input, "to": r_input, "r_mob": r_mob, "pincode": r_pin
    })
    # Reset UI
    st.session_state.temp_pin = ""
    st.session_state.temp_mob = ""
    st.rerun()
