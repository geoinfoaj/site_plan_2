# app.py
"""
Single Site Plan - precise Page 1 replication (A3 landscape)
Behaviors:
 - Use uploaded Arial Narrow TTFs if provided (one-time upload in sidebar)
 - Otherwise use DejaVu Sans fallback
 - Static OSM keyplan via geocode/address or lat,lon
 - Final A3 landscape PDF download
"""

import io, os, math, textwrap, requests
from typing import Optional
from PIL import Image, ImageDraw
import streamlit as st
import matplotlib as mpl
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.backends.backend_pdf import PdfPages
from matplotlib import font_manager

# ---------------- Page config ----------------
st.set_page_config(page_title="Single Site Plan - Page 1 (A3)", layout="wide")
st.title("Single Site Plan (Page 1 style) — A3 Landscape")

# ---------------- Sidebar: optional font upload & inputs ----------------
st.sidebar.header("1) (Optional) Upload Arial Narrow TTFs (one-time per session)")
font_files = st.sidebar.file_uploader("Upload TTFs (Regular, Bold, Italic, BoldItalic) - optional",
                                      type=["ttf","otf"], accept_multiple_files=True)

if font_files:
    tmpdir = "/tmp/streamlit_fonts"
    os.makedirs(tmpdir, exist_ok=True)
    registered = []
    for f in font_files:
        path = os.path.join(tmpdir, f.name)
        with open(path, "wb") as out:
            out.write(f.getbuffer())
        try:
            font_manager.fontManager.addfont(path)
            fp = font_manager.FontProperties(fname=path)
            registered.append(fp.get_name())
        except Exception:
            pass
    if registered:
        mpl.rcParams["font.family"] = registered[0]
        st.sidebar.success("Registered fonts: " + ", ".join(registered))
    else:
        st.sidebar.warning("Uploaded fonts could not be registered. Proceeding with fallback font.")

st.sidebar.markdown("---")
st.sidebar.header("2) Client inputs (fill or leave blank)")
site_no = st.sidebar.text_input("Site Number", "25")
owner = st.sidebar.text_input("Owner Name", "Ashish Jain")
drawing_title = st.sidebar.text_input("DRAWING TITLE", "SINGLE SITE LAYOUT PLAN")
plan_description = st.sidebar.text_area("PLAN DESCRIPTION (centered under title)", "")
adlr_sketch = st.sidebar.text_area("ADLR SKETCH (location description)", "")
conversion_order = st.sidebar.text_area("CONVERSION ORDER DETAILS", "")
architect_reg = st.sidebar.text_input("ARCHITECT SIGNATURE & REGN DETAILS", "")
sanctioning_authority = st.sidebar.text_input("SANCTIONING AUTHORITY", "")
owner_signature_text = st.sidebar.text_input("OWNER SIGNATURE (placeholder)", "")

site_type = st.sidebar.selectbox("Site Use Type", ["RESIDENTIAL","NON-RESIDENTIAL"])
site_width_m = st.sidebar.number_input("Site Width (m)", value=15.0, min_value=0.1, step=0.1)
site_length_m = st.sidebar.number_input("Site Length (m)", value=15.0, min_value=0.1, step=0.1)
road_width_m = st.sidebar.number_input("C/L OF ROAD width (m)", value=6.0, step=0.5)
scale_choice = st.sidebar.selectbox("Scale", ["1:100","1:200"], index=0)

st.sidebar.markdown("---")
st.sidebar.header("3) Key Plan (static fallback)")
kp_input = st.sidebar.text_input("Address (or lat,lon) for key plan", "Bengaluru, India")
kp_radius_m = st.sidebar.number_input("Keyplan buffer radius (m)", value=200, min_value=50, step=10)
kp_zoom = st.sidebar.slider("Zoom (10-16)", 10, 16, 14)

generate = st.sidebar.button("Generate A3 PDF (Page 1)")

# ---------------- constants in mm ----------------
PAGE_W_MM = 420.0
PAGE_H_MM = 297.0
FIG_W_IN = PAGE_W_MM / 25.4
FIG_H_IN = PAGE_H_MM / 25.4

LEFT_MARGIN = 12.0; RIGHT_MARGIN = 12.0; TOP_MARGIN = 12.0; BOTTOM_MARGIN = 12.0
DRAWING_AREA_W = PAGE_W_MM * 0.62
DRAWING_AREA_H = PAGE_H_MM - TOP_MARGIN - BOTTOM_MARGIN - 36
# SHIFT SITE DOWN 15 mm to match sample
DRAWING_ORIGIN_X = LEFT_MARGIN + 2
DRAWING_ORIGIN_Y = BOTTOM_MARGIN + 36 - 15
INFO_COL_X = DRAWING_ORIGIN_X + DRAWING_AREA_W + 8
INFO_COL_W = PAGE_W_MM - INFO_COL_X - RIGHT_MARGIN
TITLEBLOCK_H = 35.0  # increased height
TITLEBLOCK_Y = BOTTOM_MARGIN

# Full 15 general conditions and NOTE (verbatim)
GENERAL_CONDITIONS = [
    "1. The single plot layout plan is approved based on the survey sketch certified by the Assistant Director of Land records.",
    "2. Building construction shall be undertaken only after obtaining approval for the building plan from the city corporation as per the approved single site layout plan.",
    "3. The existing width of road abutting the site in question is marked in the plan. At the time of building plan approval the authority approving the building plan shall allow the maximum FAR permissible considering the minimum width of the road at any stretch towards any one side which shall join a road of equal or higher width.",
    "4. The owner shall provide drinking water, waste water discharge system and drainage system for the site in question. During the building plan approval the owner shall submit a design to implement the rain water harvesting to collect the rain water from the entire site area.",
    "5. Approval of single site layout plan shall not be a document to claim title to the property. In case of pending cases under the Land Reforms Act/Section 136(3) of the Land Revenue Act, 1964, approval of single site layout plan shall be subject to final order. The applicant shall be bound by the final order of the court in this regard and in no case the fees paid for the approval of the single site layout plan will be refunded.",
    "6. If it is found that the land proposed by the applicant includes any land belonging to the Government or any other private land, in such a case, the Authority reserves the rights to modify the single site layout plan or to withdraw the plan.",
    "7. If it is proved that the applicant has provided any false documents or forged documents for the plan sanction, the plan sanction shall stand canceled automatically.",
    "8. The applicant shall be bound to all subsequent orders and the decision relating to payment of fees as required by the Authority.",
    "9. Adequate provisions shall be made to segregate wet waste, dry waste and plastics. Area should be reserved for composting of wet waste, dry waste etc.",
    "10. No Objection Certificates/Approvals for the building plan should be obtained from the competent authorities prior to construction of building on the approved single site.",
    "11. Sewage shall not be discharged into open spaces/vacant areas but should be reused for gardening, cleaning of common areas and various other uses.",
    "12. If the owner wishes to modify the single site layout approval to multi-plot residential layout, the owner shall submit a request to the Greater Bengaluru Authority and obtain approval for the multi-plot residential layout plan as per the zoning regulations.",
    "13. One tree for every 240.0 sq.m. of the total floor area shall be planted and nurtured at the site in question.",
    "14. Prior permission should be obtained from the competent authority before constructing a culvert on the storm water drain between the land in question and the existing road attached to it if any.",
    "15. To abide by such other conditions as may be imposed by the Authority from time to time."
]
NOTE_TEXT = [
    "1. The single plot plan is issued under The Provision of section 17 of KTCP Act 1961",
    "2. The applicant has Remitted Fees of Rs.******* vide challan No. ********* Dated : **.**.****",
    "3. The applicant has to abide by the conditions imposed in the single plot plan approval order",
    "4. This single plot plan issued vide number ***/***/***-******* dated : **.**.****"
]

# ------------------- helper: geocode & static tile keyplan -------------------
def geocode_loc(q: str) -> Optional[tuple]:
    q = (q or "").strip()
    if not q:
        return None
    # lat,lon direct parse
    if "," in q:
        p = [s.strip() for s in q.split(",")]
        if len(p) == 2:
            try:
                return float(p[0]), float(p[1])
            except:
                pass
    # Nominatim
    try:
        r = requests.get("https://nominatim.openstreetmap.org/search",
                         params={"q": q, "format": "json", "limit": 1},
                         headers={"User-Agent": "SingleSitePlan/1.0"}, timeout=8)
        r.raise_for_status()
        data = r.json()
        if data:
            return float(data[0]["lat"]), float(data[0]["lon"])
    except Exception:
        return None
    return None

def latlon_to_tile_xy(lat_deg, lon_deg, zoom):
    lat_rad = math.radians(lat_deg)
    n = 2**zoom
    xt = (lon_deg + 180.0) / 360.0 * n
    yt = (1.0 - math.log(math.tan(lat_rad) + 1/math.cos(lat_rad)) / math.pi) / 2.0 * n
    return xt, yt

def fetch_tile(z, x, y):
    url = f"https://tile.openstreetmap.org/{z}/{x}/{y}.png"
    headers = {"User-Agent": "SingleSitePlan/1.0"}
    try:
        r = requests.get(url, headers=headers, timeout=8)
        r.raise_for_status()
        return Image.open(io.BytesIO(r.content)).convert("RGBA")
    except Exception:
        return None

def make_key_image(lat, lon, zoom=14, tiles_radius=1, buffer_m=200):
    xt_f, yt_f = latlon_to_tile_xy(lat, lon, zoom)
    xc, yc = int(math.floor(xt_f)), int(math.floor(yt_f))
    size = 256
    grid = []
    for dy in range(-tiles_radius, tiles_radius+1):
        row=[]
        for dx in range(-tiles_radius, tiles_radius+1):
            img = fetch_tile(zoom, xc+dx, yc+dy)
            if img is None:
                img = Image.new("RGBA", (size,size), (240,240,240,255))
            row.append(img)
        grid.append(row)
    cols = 2*tiles_radius+1
    stitched = Image.new("RGBA", (cols*size, cols*size))
    for r in range(cols):
        for c in range(cols):
            stitched.paste(grid[r][c], (c*size, r*size))
    frac_x = (xt_f - xc); frac_y = (yt_f - yc)
    center_px = (tiles_radius*size + int(frac_x*size), tiles_radius*size + int(frac_y*size))
    R = 6378137.0
    mpp = (math.cos(math.radians(lat)) * 2 * math.pi * R) / (256 * (2**zoom))
    r_px = max(2, int(buffer_m / mpp))
    draw = ImageDraw.Draw(stitched)
    bbox = [center_px[0]-r_px, center_px[1]-r_px, center_px[0]+r_px, center_px[1]+r_px]
    draw.ellipse(bbox, outline=(200,0,0,220), width=3)
    draw.ellipse(bbox, fill=(200,0,0,45))
    draw.ellipse([center_px[0]-3, center_px[1]-3, center_px[0]+3, center_px[1]+3], fill=(0,0,0,255))
    return stitched

# ------------------- generate PDF & preview -------------------
if generate:
    # try to set Arial Narrow if present in system (or uploaded earlier)
    # if not, fallback to DejaVu Sans (matplotlib default)
    # fonts are optional; layout uses mm coordinates so shape/spacing is consistent
    fig = plt.figure(figsize=(FIG_W_IN, FIG_H_IN), dpi=72)
    ax = fig.add_subplot(111)
    ax.set_xlim(0, PAGE_W_MM); ax.set_ylim(0, PAGE_H_MM)
    ax.set_aspect('equal'); ax.axis('off')

    # tuned font sizes (pt) and line widths (mm-ish approximations)
    F_TITLE = 10; F_LABEL = 9; F_BODY = 7; F_COND = 6
    LW_BORDER = 0.35; LW_BOX = 0.28; LW_SITE = 0.6

    # border
    ax.add_patch(mpatches.Rectangle((LEFT_MARGIN/2, BOTTOM_MARGIN/2),
                                    PAGE_W_MM - LEFT_MARGIN, PAGE_H_MM - BOTTOM_MARGIN,
                                    fill=False, lw=LW_BORDER))

    # drawing box (left)
    ax.add_patch(mpatches.Rectangle((DRAWING_ORIGIN_X, DRAWING_ORIGIN_Y),
                                    DRAWING_AREA_W, DRAWING_AREA_H, fill=False, lw=LW_BOX))

    # compute mm per metre for chosen scale; fit if overflow
    scale_num = int(scale_choice.split(":")[1])
    mm_per_m_theo = 1000.0 / scale_num
    inner_pad = 8.0
    usable_w = DRAWING_AREA_W - 2*inner_pad
    usable_h = DRAWING_AREA_H - 2*inner_pad
    req_w = site_width_m * mm_per_m_theo; req_h = site_length_m * mm_per_m_theo
    mm_per_m = mm_per_m_theo if (req_w <= usable_w and req_h <= usable_h) else min(usable_w/site_width_m, usable_h/site_length_m)

    site_w_mm = site_width_m * mm_per_m; site_h_mm = site_length_m * mm_per_m
    site_x = DRAWING_ORIGIN_X + inner_pad + (usable_w - site_w_mm)/2
    site_y = DRAWING_ORIGIN_Y + inner_pad + (usable_h - site_h_mm)/2

    # draw site rectangle
    ax.add_patch(mpatches.Rectangle((site_x, site_y), site_w_mm, site_h_mm, fill=False, lw=LW_SITE))

    # SITE NO title and centered plan description below it
    ax.text(site_x + site_w_mm/2, site_y + site_h_mm + 8, f"SITE NO. {site_no}", ha='center', va='bottom', fontsize=F_TITLE, weight='bold')
    desc = plan_description.strip() or ("PLAN SHOWING THE RESIDENTIAL SINGLE SITE LAYOUT FOR THE PROPERTY SITUATED IN SY.NO.****, **** VILLAGE, **** TALUK...")
    ax.text(site_x + site_w_mm/2, site_y + site_h_mm + 4, textwrap.fill(desc, width=90), ha='center', va='top', fontsize=F_BODY)

    # ADLR left and conversion right above drawing, spaced ~6 mm
    adlr_text = adlr_sketch.strip() or "ADLR SKETCH SHOWING THE LOCATION OF THE PROPOSED SITE WITHIN THE SURVEY NUMBER."
    conv_text = conversion_order.strip() or "CONVERSION ORDER DETAILS:"
    ax.text(site_x + 4, site_y + site_h_mm + 18, textwrap.fill(adlr_text, width=48), fontsize=F_COND, va='bottom', ha='left')
    ax.text(site_x + site_w_mm - 4, site_y + site_h_mm + 18, textwrap.fill(conv_text, width=48), fontsize=F_COND, va='bottom', ha='right')

    # site area inside left
    ax.text(site_x + 6, site_y + site_h_mm/2, f"{site_type} AREA\n{site_width_m*site_length_m:.2f} Sq.m", fontsize=F_BODY, va='center')

    # C/L of road below
    ax.text(site_x, site_y - 7, f"C/L OF ROAD   {road_width_m:.1f} M WIDE EXISTING ROAD", fontsize=F_COND, va='top')

    # KEY PLAN box + title bar line + N arrow inside
    key_x = INFO_COL_X + 6; key_y = PAGE_H_MM - TOP_MARGIN - 74; key_w = INFO_COL_W - 12; key_h = 74
    ax.add_patch(mpatches.Rectangle((key_x, key_y), key_w, key_h, fill=False, lw=LW_BOX))
    # thin title bar line a little below top edge to mimic example
    ax.plot([key_x, key_x+key_w], [key_y + key_h - 10, key_y + key_h - 10], lw=LW_BOX, color='black')
    ax.text(key_x + 6, key_y + key_h - 6, "KEY PLAN (NOT TO SCALE)", fontsize=F_LABEL, weight='bold', va='top')

    # static key plan image via geocode
    coords = geocode_loc(kp_input)
    if coords:
        try:
            kimg = make_key_image(coords[0], coords[1], zoom=kp_zoom, tiles_radius=1, buffer_m=kp_radius_m)
            # scale raster to fit key box
            px_w = int(key_w * 3); px_h = int(key_h * 3)
            kimg = kimg.resize((px_w, px_h), Image.LANCZOS)
            ax.imshow(kimg, extent=(key_x+1, key_x+key_w-1, key_y+1, key_y+key_h-1), zorder=1)
            # caption below key box: show address if provided else coords
            caption = kp_input.strip() or f"{coords[0]:.6f},{coords[1]:.6f}"
            ax.text(key_x + key_w/2, key_y - 6, caption, fontsize=F_COND, ha='center')
        except Exception as e:
            st.warning("Key plan render error: " + str(e))
    else:
        ax.text(key_x + key_w/2, key_y + key_h/2, "KEY PLAN (no preview)", ha='center', va='center', fontsize=F_COND)

    # NORTH inside key box top-right
    na_x = key_x + key_w - 12; na_y = key_y + key_h - 20
    ax.arrow(na_x, na_y, 0, 10, head_width=3, head_length=4, fc='black', ec='black', lw=0.6)
    ax.text(na_x, na_y + 12, "N", ha='center', va='bottom', fontsize=F_LABEL, weight='bold')

    # LAND USE ANALYSIS table (lifted up, thinner lines)
    lut_x = INFO_COL_X + 6; lut_y = key_y - 42
    ax.text(lut_x + (INFO_COL_W/2 - 6), lut_y + 18, "LAND USE ANALYSIS", ha='center', fontsize=F_LABEL, weight='bold')
    col_w = [18, 60, 36, 30]; tbl_start_x = lut_x + 2; tbl_start_y = lut_y + 12
    headers = ["SL. No", "PARTICULARS", "AREA IN Sqm.", "%"]
    xcur = tbl_start_x
    for i,h in enumerate(headers):
        ax.text(xcur + col_w[i]/2, tbl_start_y, h.upper(), ha='center', va='center', fontsize=F_COND, weight='bold')
        xcur += col_w[i]
    rows = [["1", f"{site_type} AREA", f"{site_width_m*site_length_m:.1f}", "100.00"],
            ["2", "TOTAL SITE AREA", f"{site_width_m*site_length_m:.1f}", "100.00"]]
    row_h = 7.0
    for ri, row in enumerate(rows):
        y = tbl_start_y - (ri+1)*row_h
        xcur = tbl_start_x
        for i,val in enumerate(row):
            ax.text(xcur + col_w[i]/2, y, val, ha='center', va='center', fontsize=F_COND)
            xcur += col_w[i]
    tbl_box_h = (len(rows) + 1.0)*row_h
    ax.add_patch(mpatches.Rectangle((tbl_start_x - 2, tbl_start_y - tbl_box_h + row_h/4),
                                    sum(col_w), tbl_box_h, fill=False, lw=0.25))

    # GENERAL CONDITIONS block (6pt, tight spacing ~4mm)
    gc_x = INFO_COL_X + 4; gc_y_top = tbl_start_y - tbl_box_h - 6
    ax.text(gc_x + (INFO_COL_W/2 - 6), gc_y_top, "GENERAL CONDITIONS OF APPROVAL", ha='center', fontsize=F_LABEL, weight='bold')
    cond_y = gc_y_top - 6; cond_spacing = 4.0
    for i,cond in enumerate(GENERAL_CONDITIONS):
        wrapped = textwrap.fill(cond, width=66)
        ax.text(gc_x + 2, cond_y - i*cond_spacing, wrapped, ha='left', va='top', fontsize=F_COND)

    # NOTE block below general conditions
    note_y = cond_y - len(GENERAL_CONDITIONS)*cond_spacing - 4
    ax.text(gc_x + 2, note_y, "NOTE", fontsize=F_LABEL, weight='bold')
    for j, nline in enumerate(NOTE_TEXT):
        ax.text(gc_x + 2, note_y - (j+1)*4.6, nline, fontsize=F_COND)

    # TITLE BLOCK bottom (35mm) with vertical dividers
    tb_x = LEFT_MARGIN; tb_y = TITLEBLOCK_Y; tb_w = PAGE_W_MM - LEFT_MARGIN - RIGHT_MARGIN; tb_h = TITLEBLOCK_H
    ax.add_patch(mpatches.Rectangle((tb_x, tb_y), tb_w, tb_h, fill=False, lw=LW_BOX))
    # vertical dividers (approximately at 50% and 72% of width)
    dv1 = tb_x + tb_w*0.50; dv2 = tb_x + tb_w*0.72
    ax.plot([dv1,dv1], [tb_y, tb_y+tb_h], lw=0.25, color='black')
    ax.plot([dv2,dv2], [tb_y, tb_y+tb_h], lw=0.25, color='black')
    # left fields
    ax.text(tb_x + 4, tb_y + tb_h - 7, f"DRAWING TITLE : {drawing_title}", fontsize=F_LABEL)
    ax.text(tb_x + 4, tb_y + tb_h - 13, f"SCALE : {scale_choice}", fontsize=F_COND)
    ax.text(tb_x + 4, tb_y + tb_h - 19, f"OWNER : {owner}", fontsize=F_COND)
    # mid fields
    ax.text(dv1 + 4, tb_y + tb_h - 7, f"SANCTIONING AUTHORITY : {sanctioning_authority}", fontsize=F_COND)
    ax.text(dv1 + 4, tb_y + tb_h - 13, f"ARCHITECT SIGNATURE & REGN DETAILS : {architect_reg}", fontsize=F_COND)
    # rightmost: owner signature placeholder
    ax.text(dv2 + 8, tb_y + tb_h - 13, owner_signature_text or "OWNER SIGNATURE", fontsize=F_COND)

    # All dimensions note flush with bottom right border
    ax.text(PAGE_W_MM - RIGHT_MARGIN - 4, tb_y + 3, "All Dimensions in metres.", fontsize=F_COND, ha='right')

    # Save PDF and show preview
    pdf_buf = io.BytesIO()
    with PdfPages(pdf_buf) as pdf:
        pdf.savefig(fig, bbox_inches='tight', orientation='landscape')
    pdf_buf.seek(0)
    fname = f"Single_Site_{site_no}.pdf"
    st.success("A3 (Page 1) PDF generated with final layout adjustments.")
    st.download_button("Download A3 PDF", data=pdf_buf, file_name=fname, mime="application/pdf")
    st.pyplot(fig)
