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

# --- CACHED LOOKUP ---
@st.cache_data
def get_pincode_db():
    csv_path = os.path.join(BASE_DIR, "all_india_pincode_directory_2025.csv")
    if not os.path.exists(csv_path): return {}
    df = pd.read_csv(csv_path, dtype={'pincode': str})
    df.columns = [c.lower().strip() for c in df.columns]
    df = df.drop_duplicates(subset=['pincode'], keep='first')
    return df.set_index('pincode').to_dict(orient='index')

# --- DATA EXTRACTION ---
def extract_info(text):
    pin, mob = "", ""
    chunks = re.findall(r'\+?\d+', text)
    for chunk in chunks:
        d = chunk.replace('+', '')
        if len(d) == 6: pin = d
        elif len(d) in [10, 11, 12, 13]: mob = d[-10:]
    return pin, mob

# --- CORE APP ---
st.set_page_config(layout="wide")
pincode_db = get_pincode_db()

if 'web_queue' not in st.session_state: st.session_state.web_queue = []

st.title("📮 Dispatch Manager")

# Layout
col1, col2 = st.columns(2)
with col1:
    s_addr = st.text_area("Sender Address", key="s_addr")
with col2:
    r_addr = st.text_area("Recipient Address", key="r_addr")
    
# Trigger auto-extraction
if st.button("Extract Data"):
    pin, mob = extract_info(r_addr)
    st.session_state.auto_pin = pin
    st.session_state.auto_mob = mob
    st.rerun()

r_mob = st.text_input("Receiver Mobile", value=st.session_state.get("auto_mob", ""))
r_pin = st.text_input("Pincode", value=st.session_state.get("auto_pin", ""))
weight = st.text_input("Weight (g)")

if st.button("Stage Parcel"):
    st.session_state.web_queue.append({
        "from": s_addr, "to": r_addr, "s_mob": "", "r_mob": r_mob, "pin": r_pin, "weight": weight
    })
    st.success("Staged!")

# --- COMPILE ---
if st.button("Compile Manifest"):
    wb = openpyxl.load_workbook(os.path.join(BASE_DIR, "New Format bulk.xlsx"))
    ws = wb.active
    next_row = ws.max_row + 1
    
    for entry in st.session_state.web_queue:
        pin_details = pincode_db.get(str(entry['pin']).strip(), {})
        
        # Mapping based on your request
        ws.cell(row=next_row, column=3, value=safe_numeric(entry['weight']))
        ws.cell(row=next_row, column=6, value=pin_details.get('district', '')) # Recv City
        ws.cell(row=next_row, column=10, value=pin_details.get('district', '')) # Recv Add Line 2
        ws.cell(row=next_row, column=11, value=pin_details.get('statename', '')) # Recv Add Line 3
        # ... Add other mappings here
        next_row += 1
    
    buf = io.BytesIO()
    wb.save(buf)
    st.download_button("Download Excel", buf.getvalue(), "Manifest.xlsx")
