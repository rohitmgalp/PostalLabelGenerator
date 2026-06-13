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

# --- DATABASE LOADING ---
@st.cache_data
def get_pincode_dict():
    csv_path = os.path.join(BASE_DIR, "all_india_pincode_directory_2025.csv")
    if not os.path.exists(csv_path): return {}
    df = pd.read_csv(csv_path, dtype={'pincode': str})
    df.columns = [c.lower().strip() for c in df.columns]
    # Ensure pincode is string and drop duplicates
    df = df.drop_duplicates(subset=['pincode'], keep='first')
    return df.set_index('pincode').to_dict(orient='index')

# --- INITIALIZE STATE ---
if 'web_queue' not in st.session_state: st.session_state.web_queue = []
pincode_db = get_pincode_dict()

# --- HELPER FUNCTIONS ---
def extract_data(text):
    pin, mob = "", ""
    chunks = re.findall(r'\+?\d+', text)
    for chunk in chunks:
        d = chunk.replace('+', '')
        if len(d) == 6: pin = d
        elif len(d) in [10, 11, 12, 13]: mob = d[-10:]
    return pin, mob

def safe_numeric(val):
    try: return float(val) if '.' in str(val) else int(val)
    except: return val

# --- CALLBACKS ---
def process_to_address():
    pin, mob = extract_pincode_and_mobile(st.session_state.to_input)
    st.session_state.auto_pin = pin
    st.session_state.auto_mob = mob

def process_from_address():
    _, mob = extract_pincode_and_mobile(st.session_state.from_input)
    st.session_state.auto_s_mob = mob

# --- UI LAYOUT ---
st.title("📮 Dispatch Manager")

col1, col2 = st.columns(2)

with col1:
    s_addr = st.text_area("Sender Address", key="from_input", on_change=process_from_address)
    s_mob = st.text_input("Sender Mobile", value=st.session_state.get("auto_s_mob", ""))

with col2:
    r_addr = st.text_area("Recipient Address", key="to_input", on_change=process_to_address)
    r_mob = st.text_input("Receiver Mobile", value=st.session_state.get("auto_mob", ""))
    r_pin = st.text_input("Pincode", value=st.session_state.get("auto_pin", ""))

if st.button("Stage Parcel"):
    st.session_state.web_queue.append({
        "from": s_addr, "to": r_addr, "s_mob": s_mob, "r_mob": r_mob, "pin": r_pin
    })
    st.success("Staged!")
    st.rerun()

# --- COMPILATION LOGIC (Inside your existing compilation button) ---
# When you write to Excel, use this lookup:
# pin_details = pincode_db.get(str(r_pin).strip(), {})
# ws.cell(row=next_row, column=6, value=pin_details.get('district', ''))
