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
        draw.
