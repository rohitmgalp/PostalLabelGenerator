import streamlit as st
import openpyxl
import os
import json
import io
import re
import pandas as pd
from barcode import Code128
from barcode.writer import ImageWriter

# --- CONFIG ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# --- CACHED DATABASE ---
@st.cache_data
def get_pincode_db():
    path = os.path.join(BASE_DIR, "all_india_pincode_directory_2025.csv")
    if not os.path.exists(path): return {}
    df = pd.read_csv(path, dtype={'pincode': str})
    df.columns = [c.lower().strip() for c in df.columns]
    return df.drop_duplicates(subset=['pincode'], keep='first').set_index('pincode').to_dict(orient='index')

# --- LOGIC ---
def extract_info(text):
    pin, mob = "", ""
    chunks = re.findall(r'\+?\d+', text)
    for chunk in chunks:
        d = chunk.replace('+', '')
        if len(d) == 6: pin = d
        elif len(d) in [10, 11, 12, 13]: mob = d[-10:]
    return pin, mob

# --- CALLBACKS ---
def update_recipient():
    pin, mob = extract_info(st.session_state.r_addr)
    st.session_state.auto_pin = pin
    st.session_state.auto_mob = mob

def update_sender():
    _, mob = extract_info(st.session_state.s_addr)
    st.session_state.auto_s_mob = mob

# --- APP ---
st.set_page_config(layout="wide")
pincode_db = get_pincode_db()
if 'web_queue' not in st.session_state: st.session_state.web_queue = []

st.title("📮 Dispatch Manager")
col1, col2 = st.columns(2)

with col1:
    s_addr = st.text_area("Sender Address", key="s_addr", on_change=update_sender)
    s_mob = st.text_input("Sender Mobile", value=st.session_state.get("auto_s_mob", ""))

with col2:
    r_addr = st.text_area("Recipient Address", key="r_addr", on_change=update_recipient)
    r_mob = st.text_input("Receiver Mobile", value=st.session_state.get("auto_mob", ""))
    r_pin = st.text_input("Pincode", value=st.session_state.get("auto_pin", ""))

if st.button("Stage Parcel"):
    st.session_state.web_queue.append({
        "from": s_addr, "to": r_addr, "s_mob": s_mob, "r_mob": r_mob, "pin": r_pin
    })
    st.success("Staged!")

if st.button("Compile Manifest"):
    wb = openpyxl.load_workbook(os.path.join(BASE_DIR, "New Format bulk.xlsx"))
    ws = wb.active
    next_row = ws.max_row + 1
    for entry in st.session_state.web_queue:
        pin_d = pincode_db.get(str(entry['pin']).strip(), {})
        # Map your columns here using ws.cell(row=next_row, column=X, value=...)
        next_row += 1
    buf = io.BytesIO()
    wb.save(buf)
    st.download_button("Download Excel", buf.getvalue(), "Manifest.xlsx")
