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

# --- STREAMLIT STATE INITIALIZATION ---
if 'authenticated' not in st.session_state:
    st.session_state.authenticated = False
if 'username' not in st.session_state:
    st.session_state.username = ""
if 'web_queue' not in st.session_state:
    st.session_state.web_queue = []

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
                        "name": reg_name,
                        "email": reg_email,
                        "mobile": reg_mobile,
                        "password": password,
                        "addresses": [],
                        "barcodes": {atype: {"prefix": "", "current": 0, "end": 0, "suffix": ""} for atype in ARTICLE_TYPES}
                    }
                    save_data(data)
                    st.success("Registration success! Choose 'Login to Existing Profile' mode above to enter.")
    st.stop()

# --- ENTERPRISE INTERFACE DASHBOARD ---
current_user = st.session_state.username
db = load_data()
user_profile = db["users"][current_user]

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

# --- DYNAMIC INTERFACE TABS BASED ON ROLE ---
if current_user.lower() == "admin":
    tabs_list = ["📋 Dispatch Manager", "⚙️ Settings & Barcode Ranges", "👥 Admin Panel"]
else:
    tabs_list = ["📋 Dispatch Manager", "⚙️ Settings & Barcode Ranges"]

tabs = st.tabs(tabs_list)

# --- TAB: ADMIN PANEL ---
if current_user.lower() == "admin":
    with tabs[2]:
        st.header("👥 Registered User Directory")
        st.write("Real-time telemetry log of corporate clients onboarded onto this software node.")
        
        user_records = []
        for uid, info in db["users"].items():
            if uid.lower() == "admin":
                continue
            user_records.append({
                "User ID": uid,
                "Full/Company Name": info.get("name", "N/A"),
                "Email ID": info.get("email", "N/A"),
                "Mobile Number": info.get("mobile", "N/A"),
                "Saved Profiles": len(info.get("addresses", []))
            })
        
        if user_records:
            admin_df = pd.DataFrame(user_records)
            st.dataframe(admin_df, use_container_width=True)
            
            output_admin = io.BytesIO()
            with pd.ExcelWriter(output_admin, engine='openpyxl') as writer:
                admin_df.to_excel(writer, index=False, sheet_name='Users')
            
            st.download_button(
                label="📥 Export Client Directory to Excel",
                data=output_admin.getvalue(),
                file_name="Registered_Users_Directory.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
        else:
            st.info("No corporate client profiles have registered on this system node yet.")

# --- TAB 2: RANGE ALLOCATION SETTINGS ---
with tabs[1]:
    st.header("UPU S10 Barcode Range Setup")
    set_article = st.selectbox("Choose Article Classification", ARTICLE_TYPES, key="setup_art")
    b_data = user_profile["barcodes"][set_article]
    
    col_p, col_st, col_en, col_su = st.columns(4)
    with col_p:
        new_prefix = st.text_input("Prefix (e.g., EK)", value=b_data["prefix"], max_chars=2).upper()
    with col_st:
        new_start = st.number_input("Start Serial (8 Digits)", value=int(b_data["current"]), step=1)
    with col_en:
        new_end = st.number_input("End Serial (8 Digits)", value=int(b_data["end"]), step=1)
    with col_su:
        new_suffix = st.text_input("Suffix (e.g., IN)", value=b_data["suffix"], max_chars=2).upper()
        
    if st.button("Save System Range Allocation", type="primary"):
        db["users"][current_user]["barcodes"][set_article] = {
            "prefix": new_prefix, "current": new_start, "end": new_end, "suffix": new_suffix
        }
        save_data(db)
        st.success(f"Tracking ranges configured for {set_article}!")
        st.rerun()
        
    remaining = b_data["end"] - b_data["current"]
    if remaining < 0: remaining = 0
    st.metric(label="Available Unused Serials Remaining", value=f"{remaining + 1 if b_data['end'] > 0 else 0} Units")

# --- TAB 1: WORKSPACE DISPATCH MANAGER ---
with tabs[0]:
    col_inputs, col_preview = st.columns([0.45, 0.55])
    
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
        
        st.write("**Volumetric Specifications**")
        col_m1, col_m2, col_m3, col_m4 = st.columns(4)
        with col_m1: weight = st.text_input("Weight (g)")
        with col_m2: length = st.text_input("Len (cm)")
        with col_m3: breadth = st.text_input("Wid (cm)")
        with col_m4: v_height = st.text_input("Hgt (cm)")
            
        col_mob1, col_mob2 = st.columns(2)
        with col_mob1: s_mob = st.text_input("Sender Mobile (Optional)", value=user_profile.get('mobile', ''))
        with col_mob2: r_mob = st.text_input("Receiver Mobile")

        b_current = user_profile["barcodes"][article_type]
        if b_current["current"] == 0 or b_current["current"] > b_current["end"]:
            st.error("❌ Selected Range empty! Set ranges in the Settings Tab.")
            auto_tracking = None
        else:
            current_serial_8 = int(b_current["current"])
            check_digit = calculate_upu_s10_check_digit(current_serial_8)
            auto_tracking = f"{b_current['prefix']}{current_serial_8:08d}{check_digit}{b_current['suffix']}"
            st.info(f"Next Compliant S10 Tracking ID: **{auto_tracking}**")

        if st.button("➕ Stage to Batch Allocation Queue", type="primary"):
            if not from_address or not to_address or not auto_tracking or not weight or not length or not breadth or not v_height:
                st.error("All address coordinates, volumetric metrics, and range sets must be valid.")
            else:
                st.session_state.web_queue.append({
                    "tracking": auto_tracking, "from": from_address, "to": to_address, "article": article_type,
                    "cod": cod_amount, "cust_id": customer_id, "weight": weight, "length": length,
                    "breadth": breadth, "height": v_height, "s_mob": s_mob, "r_mob": r_mob
                })
                db["users"][current_user]["barcodes"][article_type]["current"] += 1
                save_data(db)
                st.success("Staged successfully into batch frame memory.")
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
            
            if st.button("⚙️ Compile Label PDFs & Sync Template Matrix"):
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
                        my_barcode = Code128(entry['tracking'], writer=ImageWriter())
                        my_barcode.write(bc_buffer)
                        bc_buffer.seek(0)
                        bc_img = Image.open(bc_buffer)
                        
                        lbl_canvas = Image.new('RGB', (W_px, H_px), color='white')
                        draw = ImageDraw.Draw(lbl_canvas)
                        scale = min(W_px, H_px)
                        try:
                            f_l = ImageFont.truetype("arial.ttf", max(24, int(scale * 0.045)))
                            f_m = ImageFont.truetype("arial.ttf", max(20, int(scale * 0.035)))
                            f_b = ImageFont.truetype("arialbd.ttf", max(22, int(scale * 0.040)))
                        except:
                            f_l = f_m = f_b = ImageFont.load_default()
                            
                        y_curr = m_px
                        top_strings = [f"ARTICLE: {entry['article']}", f"CUST ID: {entry['cust_id']}"]
                        if entry['cod']: top_strings.append(f"COD CHARGES: Rs. {entry['cod']}")
                        
                        for line in top_strings:
                            draw.text((m_px, y_curr), line, fill="black", font=f_b)
                            b_box = draw.textbbox((0,0), line, font=f_b)
                            y_curr += (b_box[3] - b_box[1]) + int(H_px * 0.01)
                            
                        y_curr += int(H_px * 0.02)
                        draw.text((m_px, y_curr), "FROM:", fill="black", font=f_b)
                        y_curr += int(scale * 0.04)
                        
                        w_from = wrap_text_to_pixels(entry['from'], draw, f_m, use_w)
                        draw.multiline_text((m_px, y_curr), w_from, fill="black", font=f_m, spacing=6)
                        b_box = draw.multiline_textbbox((m_px, y_curr), w_from, font=f_m, spacing=6)
                        y_cursor_from = b_box[3] + int(H_px * 0.03)
                        
                        draw.text((m_px, y_cursor_from), "TO:", fill="black", font=f_b)
                        y_cursor_from += int(scale * 0.04)
                        
                        w_to = wrap_text_to_pixels(entry['to'], draw, f_l, use_w)
                        draw.multiline_text((m_px, y_cursor_from), w_to, fill="black", font=f_l, spacing=6)
                        b_box = draw.multiline_textbbox((m_px, y_cursor_from), w_to, font=f_l, spacing=6)
                        y_cursor_to = b_box[3] + int(H_px * 0.03)
                        
                        rem_h = H_px - y_cursor_to - m_px
                        if rem_h < int(H_px * 0.15):
                            rem_h = int(H_px * 0.15)
                            y_cursor_to = H_px - rem_h - m_px
                            
                        bc_w_scaled = int(W_px * 0.75)
                        bc_resized = bc_img.resize((bc_w_scaled, rem_h))
                        lbl_canvas.paste(bc_resized, ((W_px - bc_w_scaled) // 2, y_cursor_to))
                        
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
                    
                    st.success("Compilation complete! Web download links are now active below.")

            batch_timestamp = int(time.time())
            if 'pdf_ready' in st.session_state:
                st.download_button(
                    label="📥 Download Consolidated Label PDF Bundle",
                    data=st.session_state.pdf_ready,
                    file_name=f"Compiled_Post_Labels_{batch_timestamp}.pdf",
                    mime="application/pdf",
                    use_container_width=True
                )
            if 'excel_ready' in st.session_state:
                st.download_button(
                    label="📥 Download Template Upload Ready Manifest",
                    data=st.session_state.excel_ready,
                    file_name=f"Bulk_Upload_Manifest_{batch_timestamp}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    use_container_width=True
                )
        else:
            st.info("The dispatch pipeline queue is currently clean.")
