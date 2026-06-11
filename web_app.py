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

# --- STREAMLIT PAGE INITS ---
st.set_page_config(page_title="India Post Enterprise Workspace", page_icon="📮", layout="wide")

# --- PREMIUM BASE64 THEME BACKGROUND INJECTION ---
def get_base64_image(image_path):
    with open(image_path, "rb") as img_file:
        return base64.b64encode(img_file.read()).decode()

bg_file_path = os.path.join(BASE_DIR, "background.png")

if os.path.exists(bg_file_path):
    encoded_bg = get_base64_image(bg_file_path)
    # Inject the image as a fixed full-screen watermark backdrop with clean modern containers
    st.markdown(f"""
        <style>
            .stApp {{
                background-image: url("data:image/png;base64,{encoded_bg}");
                background-size: cover;
                background-position: center;
                background-attachment: fixed;
            }}
            /* Create crisp white layout paper cards so forms stay highly readable over the graphic */
            div[data-testid="stColumn"] {{
                background-color: rgba(255, 255, 255, 0.92);
                padding: 30px !important;
                border-radius: 15px !important;
                box-shadow: 0 4px 15px rgba(156, 0, 0, 0.05);
                border: 1px solid rgba(226, 220, 208, 0.6);
            }}
            .stTextInput input, .stTextArea textarea, .stSelectbox div {{
                border-color: #e2dcd0 !important;
                background-color: #ffffff !important;
                color: #2b2b2b !important;
            }}
            div.stButton > button[type="primary"] {{
                background-color: #9c0000 !important;
                color: white !important;
                border: none !important;
                font-weight: bold !important;
                padding: 10px 24px !important;
                border-radius: 8px !important;
            }}
            div.stButton > button[type="primary"]:hover {{
                background-color: #bd0000 !important;
            }}
            h1, h2, h3, p, span, label {{
                color: #3a0000 !important;
            }}
        </style>
    """, unsafe_allow_html=True)
else:
    # Clean solid fallback style definitions if background asset file is not loaded yet
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

st.title("📮 India Post Enterprise Workspace")
st.caption(f"Client Node: **{user_profile.get('name', current_user)}** | ID: `{current_user}`")

col_logout_wrap = st.columns([0.85, 0.15])
with col_logout_wrap[1]:
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
    b_data = user_profile["barcodes"][set_article]
    
    col_p, col_st, col_en, col_su = st.columns(4)
    with col_p: new_prefix = st.text_input("Prefix (2 Alpha)", value=b_data["prefix"], max_chars=2).upper()
    with col_st: new_start = st.number_input("Start Serial (8 Digits)", value=int(b_data["current"]), step=1)
    with col_en: new_end = st.number_input("End Serial (8 Digits)", value=int(b_data["end"]), step=1)
    with col_su: new_suffix = st.text_input("Suffix (2 Alpha)", value=b_data["suffix"], max_chars=2).upper()
        
    if st.button("Save System Range Allocation", type="primary"):
        db["users"][current_user]["barcodes"][set_article] = { "prefix": new_prefix, "current": new_start, "end": new_end, "suffix": new_suffix }
        save_data(db)
        st.success("Tracking ranges configured!")
        st.rerun()
        
    remaining = b_data["end"] - b_data["current"]
    st.metric(label="Available Unused Serials Remaining", value=f"{max(0, remaining + 1) if b_data['end'] > 0 else 0} Units")

# --- TAB 1: WORKSPACE DISPATCH MANAGER ---
with tabs[0]:
    col_inputs, col_preview = st.columns([0.48, 0.52])
    
    with col_inputs:
        st.subheader("Shipment Properties")
        col_w_in, col_h_in = st.columns(2)
        with col_w_in: width_in = st.number_input("Label Width (Inches)", value=4.0, step=0.5)
        with col_h_in: height_in = st.number_input("Label Height (Inches)", value=6.0, step=0.5)
            
        saved_addresses = user_profile.get("addresses", [])
        selected_saved = st.selectbox("Quick-Load Saved 'From' Address", ["-- Select Profile --"] + saved_addresses)
        from_initial = selected_saved if selected_saved != "-- Select Profile --" else ""
        from_address = st.text_area("Sender 'From' Address Details", value=from_initial)
        
        if st.button("💾 Remember This From Address"):
            if from_address and from_address not in user_profile["addresses"]:
                db["users"][current_user]["addresses"].append(from_address)
                save_data(db)
                st.success("Address profile recorded.")
                st.rerun()
                
        to_address = st.text_area("Recipient 'To' Address Details")
        article_type = st.selectbox("Postal Article Class", ARTICLE_TYPES, key="disp_art")
        
        cod_amount = ""
        if "COD" in article_type: cod_amount = st.text_input("Collect on Delivery (COD) Amount (₹)")
        customer_id = st.text_input("India Post Customer Business ID")
        
        st.write("**Volumetric Specifications (Optional)**")
        col_m1, col_m2, col_m3, col_m4 = st.columns(4)
        with col_m1: weight = st.text_input("Weight (g)")
        with col_m2: length = st.text_input("Len (cm)")
        with col_m3: breadth = st.text_input("Wid (cm)")
        with col_m4: v_height = st.text_input("Hgt (cm)")
            
        col_mob1, col_mob2 = st.columns(2)
        with col_mob1: s_mob = st.text_input("Sender Mobile (Optional)", value=user_profile.get('mobile', ''))
        with col_mob2: r_mob = st.text_input("Receiver Mobile (Optional)")

        # --- DYNAMIC BARCODE COLLISION ELIMINATION ENGINE ---
        b_current = user_profile["barcodes"][article_type]
        used_set = set(user_profile.get("used_barcodes", []))
        queue_set = {item["tracking"] for item in st.session_state.web_queue}

        if b_current["current"] == 0 or b_current["current"] > b_current["end"]:
            st.error("❌ Selected Range empty! Set ranges in the Settings Tab.")
            auto_tracking = None
        else:
            current_serial_8 = int(b_current["current"])
            auto_tracking = None
            while current_serial_8 <= int(b_current["end"]):
                check_digit = calculate_upu_s10_check_digit(current_serial_8)
                test_tracking = f"{b_current['prefix']}{current_serial_8:08d}{check_digit}{b_current['suffix']}"
                if test_tracking not in used_set and test_tracking not in queue_set:
                    auto_tracking = test_tracking
                    break
                current_serial_8 += 1
            
            if auto_tracking:
                st.info(f"Next S10 Tracking ID: **{auto_tracking}**")
                b_current["current"] = current_serial_8
            else:
                st.error("❌ Barcode Duplication Limit Hit! Update Settings.")

        if st.button("➕ Stage to Batch Allocation Queue", type="primary"):
            if not from_address or not to_address or not auto_tracking:
                st.error("From Address, To Address, and a valid Tracking ID range are mandatory.")
            else:
                st.session_state.web_queue.append({
                    "tracking": auto_tracking, "from": from_address, "to": to_address, "article": article_type,
                    "cod": cod_amount, "cust_id": customer_id, 
                    "weight": weight if weight else "", "length": length if length else "", 
                    "breadth": breadth if breadth else "", "height": v_height if v_height else "", 
                    "s_mob": s_mob if s_mob else "", "r_mob": r_mob if r_mob else ""
                })
                db["users"][current_user]["used_barcodes"].append(auto_tracking)
                db["users"][current_user]["barcodes"][article_type]["current"] = b_current["current"] + 1
                save_data(db)
                st.success("Staged successfully!")
                st.rerun()

    with col_preview:
        st.subheader("Staged Processing Queue")
        if st.session_state.web_queue:
            display_df = pd.DataFrame(st.session_state.web_queue)[["tracking", "article", "weight", "cust_id"]]
            st.dataframe(display_df, use_container_width=True)
            if st.button("🗑️ Wipe Entire Active Session Queue"):
                st.session_state.web_queue = []
                st.rerun()
                
            st.write("---")
            st.subheader("Compile Outputs")
            
            if st.button("⚙️ Compile Label PDFs & Sync Template Matrix", type="primary"):
                pdf_pages = []
                template_filename = os.path.join(BASE_DIR, "Template_Master.xlsx")
                if not os.path.exists(template_filename):
                    st.error(f"CRITICAL: Template file missing at: {template_filename}")
                else:
                    wb = openpyxl.load_workbook(template_filename)
                    ws = wb.active
                    next_row = ws.max_row + 1
                    
                    DPI = 300
                    W_px = int(width_in * DPI)
                    H_px = int(height_in * DPI)
                    m_px = int(W_px * 0.05)
                    use_w = W_px - (2 * m_px)
                    
                    for idx, entry in enumerate(st.session_state.web_queue):
                        bc_buffer = io.BytesIO()
                        Code128(entry['tracking'], writer=ImageWriter()).write(bc_buffer)
                        bc_buffer.seek(0)
                        bc_img = Image.open(bc_buffer)
                        
                        lbl_canvas = Image.new('RGB', (W_px, H_px), color='white')
                        draw = ImageDraw.Draw(lbl_canvas)
                        scale = min(W_px, H_px)
                        
                        size_l = max(38, int(scale * 0.060))
                        size_m = max(30, int(scale * 0.046))
                        size_b = max(34, int(scale * 0.050))
                        
                        try:
                            f_l = ImageFont.load_default(size=size_l)
                            f_m = ImageFont.load_default(size=size_m)
                            f_b = ImageFont.load_default(size=size_b)
                        except:
                            f_l = f_m = f_b = ImageFont.load_default()
                            
                        y_curr = m_px
                        top_strings = [f"ARTICLE: {entry['article']}"]
                        if entry['cust_id']: top_strings.append(f"CUST ID: {entry['cust_id']}")
                        if entry['cod']: top_strings.append(f"COD CHARGES: Rs. {entry['cod']}")
                        
                        for line in top_strings:
                            draw.text((m_px, y_curr), line, fill="black", font=f_b)
                            b_box = draw.textbbox((0,0), line, font=f_b)
                            y_curr += (b_box[3] - b_box[1]) + int(H_px * 0.015)
                            
                        y_curr += int(H_px * 0.02)
                        draw.text((m_px, y_curr), "FROM:", fill="black", font=f_b)
                        y_curr += int(size_b * 1.2)
                        
                        w_from = wrap_text_to_pixels(entry['from'], draw, f_m, use_w)
                        draw.multiline_text((m_px, y_curr), w_from, fill="black", font=f_m, spacing=10)
                        b_box = draw.multiline_textbbox((m_px, y_curr), w_from, font=f_m, spacing=10)
                        y_cursor_from = b_box[3] + int(H_px * 0.04)
                        
                        draw.text((m_px, y_cursor_from), "TO:", fill="black", font=f_b)
                        y_cursor_from += int(size_b * 1.2)
                        
                        w_to = wrap_text_to_pixels(entry['to'], draw, f_l, use_w)
                        draw.multiline_text((m_px, y_cursor_from), w_to, fill="black", font=f_l, spacing=10)
                        b_box = draw.multiline_textbbox((m_px, y_cursor_from), w_to, font=f_l, spacing=10)
                        
                        bc_h_scaled = int(H_px * 0.12)
                        bc_w_scaled = int(W_px * 0.75)
                        bc_y_pos = H_px - bc_h_scaled - m_px
                        bc_resized = bc_img.resize((bc_w_scaled, bc_h_scaled))
                        lbl_canvas.paste(bc_resized, ((W_px - bc_w_scaled) // 2, bc_y_pos))
                        
                        pdf_pages.append(lbl_canvas)
                        
                        # --- EXCEL DATA INJECTIONS ---
                        ws.cell(row=next_row, column=1, value=idx + 1)
                        ws.cell(row=next_row, column=2, value=entry['tracking'])
                        ws.cell(row=next_row, column=3, value=entry['weight'])
                        ws.cell(row=next_row, column=5, value=entry['length'])
                        ws.cell(row=next_row, column=6, value=entry['breadth'])
                        ws.cell(row=next_row, column=7, value=entry['height'])
                        
                        c_from = entry['from'].replace('\n', ', ')
                        ws.cell(row=next_row, column=11, value=user_profile.get('name', current_user))
                        ws.cell(row=next_row, column=13, value=c_from[:50])
                        ws.cell(row=next_row, column=14, value=c_from[50:100])
                        ws.cell(row=next_row, column=37, value=entry['s_mob'])
                        
                        c_to = entry['to'].replace('\n', ', ')
                        ws.cell(row=next_row, column=22, value="CUSTOMER")
                        ws.cell(row=next_row, column=24, value=c_to[:50])
                        ws.cell(row=next_row, column=25, value=c_to[50:100])
                        ws.cell(row=next_row, column=38, value=entry['r_mob'])
                        
                        if entry['cod']:
                            ws.cell(row=next_row, column=41, value="TRUE")
                            ws.cell(row=next_row, column=42, value=entry['cod'])
                        next_row += 1
                        
                    pdf_buffer = io.BytesIO()
                    pdf_pages[0].save(pdf_buffer, "PDF", save_all=True, append_images=pdf_pages[1:], resolution=300.0)
                    st.session_state.pdf_ready = pdf_buffer.getvalue()
                    
                    excel_buffer = io.BytesIO()
                    wb.save(excel_buffer)
                    st.session_state.excel_ready = excel_buffer.getvalue()
                    st.success("Compilation complete! Web download links active.")

            batch_timestamp = int(time.time())
            if 'pdf_ready' in st.session_state:
                st.download_button(label="📥 Download Consolidated Label PDF Bundle", data=st.session_state.pdf_ready, file_name=f"Compiled_Post_Labels_{batch_timestamp}.pdf", mime="application/pdf", use_container_width=True)
            if 'excel_ready' in st.session_state:
                st.download_button(label="📥 Download Template Upload Ready Manifest", data=st.session_state.excel_ready, file_name=f"Bulk_Upload_Manifest_{batch_timestamp}.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", use_container_width=True)
        else:
            st.info("The dispatch pipeline queue is currently clean.")
