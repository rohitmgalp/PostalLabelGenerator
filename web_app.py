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

DISPATCH_ARTICLES = [
    "Speed Post Parcel", 
    "Indiapost Parcel Retail", 
    "Business Parcel", 
    "Speed Post Parcel COD", 
    "Business Parcel COD"
]

BARCODE_POOL_KEYS = [
    "Speed Post Parcel (Regular & COD Shared Pool)",
    "Indiapost Parcel Retail",
    "Business Parcel",
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

def get_pool_key(article_type):
    if article_type in ["Speed Post Parcel", "Speed Post Parcel COD"]:
        return "Speed Post Parcel (Regular & COD Shared Pool)"
    return article_type

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
    text_str = str(text)
    lines = []
    for p in text_str.split('\n'):
        words = p.split(' ')
        current_line = ""
        for word in words:
            test_line = current_line + " " + word if current_line else word
            bbox = draw.textbbox((0, 0), test_line, font=font)
            w = bbox[2] - bbox[0]
            if w <= max_width: 
                current_line = test_line
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
    my_barcode = Code128(entry['tracking'], writer=ImageWriter())
    my_barcode.write(bc_buffer, options={"write_text": False, "background": "white", "quiet_zone": 1.0})
    bc_buffer.seek(0)
    bc_img = Image.open(bc_buffer)
    
    lbl_canvas = Image.new('RGB', (W_px, H_px), color='white')
    draw = ImageDraw.Draw(lbl_canvas)
    scale = min(W_px, H_px)
    
    size_l = max(36, int(scale * 0.058))
    size_m = max(28, int(scale * 0.044))
    size_b = max(32, int(scale * 0.048))
    size_bc_text = max(30, int(scale * 0.046))
    
    try:
        f_l = ImageFont.load_default(size=size_l)
        f_m = ImageFont.load_default(size=size_m)
        f_b = ImageFont.load_default(size=size_b)
        f_bc = ImageFont.load_default(size=size_bc_text)
    except:
        f_l = f_m = f_b = f_bc = ImageFont.load_default()
        
    top_strings = [f"ARTICLE: {entry['article']}"]
    if entry.get('cust_id'): top_strings.append(f"CUST ID: {entry['cust_id']}")
    if entry.get('cod'): top_strings.append(f"COD CHARGES: Rs. {entry['cod']}")
    
    if W_px >= H_px:  # LANDSCAPE MODE
        bc_h_scaled = int(H_px * 0.13)
        bc_w_scaled = int(W_px * 0.65)
        bc_y_pos = H_px - bc_h_scaled - m_px - int(H_px * 0.05)
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
        bc_h_scaled = int(H_px * 0.11)
        bc_w_scaled = int(W_px * 0.75)
        bc_y_pos = H_px - bc_h_scaled - m_px - int(H_px * 0.05)
        
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
        
        bc_resized = bc_img.resize((bc_w_scaled, bc_h_scaled))
        lbl_canvas.paste(bc_resized, ((W_px - bc_w_scaled) // 2, bc_y_pos))
        
    bbox_bc = draw.textbbox((0, 0), entry['tracking'], font=f_bc)
    text_bc_w = bbox_bc[2] - bbox_bc[0]
    draw.text(((W_px - text_bc_w) // 2, bc_y_pos + bc_h_scaled + int(H_px * 0.012)), entry['tracking'], fill="black", font=f_bc)
        
    return lbl_canvas

# --- THEME & FLOATING WHATSAPP BUTTON STYLING INJECTION ---
st.set_page_config(page_title="India Post Enterprise Workspace", page_icon="📮", layout="wide")
bg_file_path = os.path.join(BASE_DIR, "background.png")

whatsapp_html = """
    <a href="https://wa.me/918075386388" target="_blank" class="whatsapp-float">
        <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" fill="currentColor" viewBox="0 0 16 16" style="margin-right: 8px; display: inline-block; vertical-align: middle;">
            <path d="M13.601 2.326A7.85 7.85 0 0 0 7.994 0C3.627 0 .068 3.558.064 7.926c0 1.399.366 2.76 1.057 3.965L0 16l4.204-1.102a7.9 7.9 0 0 0 3.79.965h.004c4.368 0 7.926-3.558 7.93-7.93A7.9 7.9 0 0 0 13.6 2.326zM7.994 14.521a6.6 6.6 0 0 1-3.356-.92l-.24-.144-2.494.654.666-2.433-.156-.251a6.56 6.56 0 0 1-1.007-3.505c1.11-4.285 4.564-6.574 8.718-6.574a6.58 6.58 0 0 1 4.66 2.72 6.58 6.58 0 0 1 1.936 4.663c-.004 4.2-3.563 7.759-7.923 7.759M11.57 9.447c-.19-.094-1.127-.556-1.301-.62-.174-.064-.3-.094-.426.094-.126.188-.488.62-.6.749-.113.128-.226.144-.417.05-.19-.095-.807-.296-1.536-.855-.567-.457-.951-1.022-1.062-1.116-.112-.094-.012-.145.083-.242.085-.087.174-.188.26-.283.087-.095.116-.16.174-.319.059-.158.03-.3-.015-.394-.045-.094-.426-1.026-.583-1.409-.153-.367-.307-.317-.418-.317-.109-.004-.234-.004-.36-.004a.69.69 0 0 0-.5.234c-.174.188-.665.65-0.665 1.583s.678 1.834.773 1.96c.095.127 1.332 2.035 3.226 2.856.45.195.8.311 1.075.398.452.144.863.124 1.189.062.363-.069 1.127-.461 1.284-.906.158-.444.158-.825.11-1.013-.048-.19-.174-.3-.365-.394"/>
        </svg>Contact Us
    </a>
"""

if os.path.exists(bg_file_path):
    encoded_bg = get_base64_image(bg_file_path)
    st.markdown(f"""
        <style>
            .stApp {{ background-image: url("data:image/png;base64,{encoded_bg}"); background-size: cover; background-position: center; background-attachment: fixed; }}
            div[data-testid="stHeader"] {{ background: transparent !important; }}
            .stTextInput input, .stTextArea textarea, .stSelectbox div {{ border-color: #cbd5e1 !important; background-color: #ffffff !important; color: #0f172a !important; }}
            div.stButton > button[type="primary"] {{ background-color: #9c0000 !important; color: white !important; border: none !important; font-weight
