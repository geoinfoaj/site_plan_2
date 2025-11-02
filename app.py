import io, math, textwrap, requests
from PIL import Image, ImageDraw
import streamlit as st
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.backends.backend_pdf import PdfPages

try:
    from streamlit_folium import st_folium
    import folium
    FOLIUM_OK = True
except Exception:
    FOLIUM_OK = False

st.set_page_config(page_title="Single Site Plan — Page 1 (A3)", layout="centered")

st.header("🏗️ Anantha Single Site Plan — (A3)")
st.markdown("Enter all details below, then click **Generate A3 PDF**.")

# ----------- Site Details -----------
st.subheader("🧾 Site Details")
survey_no = st.text_input("Survey Number (SY. NO.)")
village = st.text_input("Village")
taluk = st.text_input("Taluk")
epid = st.text_input("EPID (E Khata number)")
ward_no = st.text_input("Ward Number")
constituency = st.text_input("Constituency Name")

# ----------- Dimensions -----------
st.subheader("📐 Plot Dimensions")
site_length_m = st.number_input("Site Length (m)", min_value=0.1, value=15.0)
site_width_m = st.number_input("Site Width (m)", min_value=0.1, value=12.0)
total_builtup = st.number_input("Total Built-up Area (Sq.m)", min_value=0.0, value=0.0, step=1.0)

# ----------- Roads -----------
st.subheader("🚗 Roads Around the Site")
road_info = {}
for side in ["North", "South", "East", "West"]:
    c1, c2 = st.columns([1, 1.2])
    with c1:
        has_road = st.checkbox(f"{side} Road", value=(side == "North"))
    with c2:
        width = st.number_input(f"{side} Road Width (m)", min_value=0.0,
                                value=6.0 if has_road else 0.0, step=0.5, key=f"{side}_width")
    road_info[side.lower()] = {"exists": has_road, "width": width}

# ----------- Key Plan Map -----------
st.subheader("🗺️ Key Plan — Click on map to set site location")
kp_radius_m = 50
kp_zoom = 18

default_center = (12.9716, 77.5946)
m = folium.Map(location=default_center, zoom_start=kp_zoom, control_scale=True)
folium.TileLayer("openstreetmap").add_to(m)
folium.LatLngPopup().add_to(m)

def latlon_to_tile_xy(lat_deg, lon_deg, zoom):
    lat_rad = math.radians(lat_deg)
    n = 2.0 ** zoom
    xtile = (lon_deg + 180.0) / 360.0 * n
    ytile = (1.0 - math.log(math.tan(lat_rad) + 1 / math.cos(lat_rad)) / math.pi) / 2.0 * n
    return xtile, ytile

def fetch_tile(z, x, y):
    url = f"https://tile.openstreetmap.org/{z}/{x}/{y}.png"
    headers = {"User-Agent": "SingleSitePlanApp/1.0"}
    try:
        r = requests.get(url, headers=headers, timeout=8)
        r.raise_for_status()
        return Image.open(io.BytesIO(r.content)).convert("RGBA")
    except Exception:
        return Image.new("RGBA", (256, 256), (240, 240, 240, 255))

def make_keyplan_image(lat, lon, zoom=16, radius_m=200):
    xtile, ytile = latlon_to_tile_xy(lat, lon, zoom)
    size = 256
    x_c, y_c = int(xtile), int(ytile)
    stitched = Image.new("RGBA", (3*size, 3*size))
    for dx in range(-1, 2):
        for dy in range(-1, 2):
            img = fetch_tile(zoom, x_c+dx, y_c+dy)
            stitched.paste(img, ((dx+1)*size, (dy+1)*size))
    R = 6378137.0
    mpp = (math.cos(math.radians(lat)) * 2 * math.pi * R) / (256 * (2**zoom))
    radius_px = int(radius_m / mpp)
    cx = (xtile - x_c + 1) * size
    cy = (ytile - y_c + 1) * size
    draw = ImageDraw.Draw(stitched)
    draw.ellipse([cx - radius_px, cy - radius_px, cx + radius_px, cy + radius_px],
                 outline=(200, 0, 0, 255), width=6)
    draw.ellipse([cx - 4, cy - 4, cx + 4, cy + 4], fill=(0, 0, 0))
    return stitched

if "marker" not in st.session_state:
    st.session_state.marker = None

clicked = st_folium(m, width=700, height=400)
if clicked and clicked.get("last_clicked"):
    lat, lon = clicked["last_clicked"]["lat"], clicked["last_clicked"]["lng"]
    st.session_state.marker = (lat, lon)
picked_latlon = st.session_state.marker

if picked_latlon:
    lat, lon = picked_latlon
    m2 = folium.Map(location=(lat, lon), zoom_start=kp_zoom, control_scale=True)
    folium.Marker((lat, lon), tooltip="Selected Site Location").add_to(m2)
    folium.Circle(
        location=(lat, lon),
        radius=kp_radius_m,
        color="red", weight=4,
        fill=True, fill_color="#ff0000", fill_opacity=0.05
    ).add_to(m2)
    st_folium(m2, width=700, height=400)
    st.success(f"📍 Location set: {lat:.6f}, {lon:.6f}")

# ----------- ADLR Sketch Upload -----------
st.subheader("📄 ADLR Sketch (Optional)")
adlr_file = st.file_uploader("Upload ADLR sketch image (JPG, PNG)", type=["jpg", "jpeg", "png"])

# ----------- PDF Generation -----------
if st.button("📄 Generate A3 PDF"):
    PAGE_W_MM, PAGE_H_MM = 420.0, 297.0
    FIG_W_IN, FIG_H_IN = PAGE_W_MM/25.4, PAGE_H_MM/25.4
    LEFT, RIGHT, TOP, BOTTOM = 12, 12, 12, 12
    DRAW_W = PAGE_W_MM*0.62
    DRAW_H = PAGE_H_MM - TOP - BOTTOM
    DRAW_X = LEFT 
    DRAW_Y = BOTTOM

    F_TITLE, F_LABEL, F_BODY, F_COND = 9.5, 8.5, 6.5, 4.5
    LW_BORDER, LW_BOX, LW_SITE = 0.25, 0.25, 0.6
    SCALE = 100.0
    mm_per_m = 1000.0 / SCALE

    fig = plt.figure(figsize=(FIG_W_IN, FIG_H_IN), dpi=72)
    ax = fig.add_subplot(111)
    ax.set_xlim(0, PAGE_W_MM); ax.set_ylim(0, PAGE_H_MM)
    ax.set_aspect("equal"); ax.axis("off")

    # Border
    ax.add_patch(mpatches.Rectangle((LEFT/2, BOTTOM/2),
                                    PAGE_W_MM-LEFT, PAGE_H_MM-BOTTOM,
                                    fill=False, lw=LW_BORDER))

    # Site placement
    inner_pad = 4.0
    usable_w = DRAW_W - 4*inner_pad; usable_h = DRAW_H - 4*inner_pad
    mm_per_m_use = min(usable_w/site_width_m, usable_h/site_length_m)
    site_w_mm = site_width_m*mm_per_m_use; site_h_mm = site_length_m*mm_per_m_use
    site_x = DRAW_X + inner_pad + (usable_w - site_w_mm)/2
    site_y = DRAW_Y + inner_pad + (usable_h - site_h_mm)/2

    # Site rectangle
    ax.add_patch(
        mpatches.Rectangle(
            (site_x, site_y), site_w_mm, site_h_mm,
            fill=False, lw=LW_SITE, linestyle=(0, (16,5,4,5,4,5))
        )
    )

    # Roads
    for side, info in road_info.items():
        if not info["exists"]: continue
        w_m = info["width"]
        road_band = w_m * mm_per_m
        if side == "north":
            rx, ry, rw, rh = site_x, site_y + site_h_mm, site_w_mm, road_band
            rot, txtx, txty = 0, rx+rw/2, ry+rh/2
        elif side == "south":
            rx, ry, rw, rh = site_x, site_y - road_band, site_w_mm, road_band
            rot, txtx, txty = 0, rx+rw/2, ry+rh/2
        elif side == "east":
            rx, ry, rw, rh = site_x + site_w_mm, site_y, road_band, site_h_mm
            rot, txtx, txty = 90, rx+rw/2, ry+rh/2
        elif side == "west":
            rx, ry, rw, rh = site_x - road_band, site_y, road_band, site_h_mm
            rot, txtx, txty = 90, rx+rw/2, ry+rh/2
        ax.add_patch(
            mpatches.Rectangle((rx, ry), rw, rh, facecolor="#e0e0e0",
                               edgecolor="black", lw=0.4, hatch="////")
        )
        label_offset = 3 * (1000.0 / SCALE)
        if side == "north": txty += road_band/2 + label_offset
        elif side == "south": txty -= road_band/2 + label_offset
        elif side == "east": txtx += road_band/2 + label_offset
        elif side == "west": txtx -= road_band/2 + label_offset
        ax.text(txtx, txty,
                f"{side.title()} ({w_m:.1f} m ROAD)",
                ha="center", va="center", fontsize=F_BODY, rotation=rot)

    # Site label
    ax.text(site_x + site_w_mm/2, site_y + site_h_mm + 30,
            f"SITE (SY.NO. {survey_no})",
            ha="center", va="bottom", fontsize=F_TITLE, weight="bold")

    # ---------- RIGHT COLUMN ----------
    INFO_X = DRAW_X + DRAW_W + 15

    # --- KEY PLAN ---
    key_x, key_y, key_w, key_h = INFO_X, PAGE_H_MM - 75, 110, 70
    ax.add_patch(mpatches.Rectangle((key_x, key_y), key_w, key_h, fill=False, lw=0.25))
    ax.text(key_x + key_w/2, key_y + key_h + 4, "KEY PLAN (NOT TO SCALE)",
            ha="center", va="bottom", fontsize=F_LABEL, weight="bold")

    if picked_latlon:
        try:
            lat, lon = picked_latlon
            kimg = make_keyplan_image(lat, lon, zoom=kp_zoom, radius_m=kp_radius_m)
            kimg = kimg.resize((int(key_w*5), int(key_h*5)), Image.LANCZOS)
            ax.imshow(kimg, extent=(key_x+1, key_x+key_w-1, key_y+1, key_y+key_h-1))
        except Exception:
            ax.text(key_x + key_w/2, key_y + key_h/2,
                "Key Plan (Error loading map)", ha="center", va="center",
                fontsize=F_BODY, style="italic", color="red")
    else:
        ax.text(key_x + key_w/2, key_y + key_h/2,
            "KEY PLAN (To be inserted here)",
            ha="center", va="center", fontsize=F_BODY, style="italic", color="gray")

       

    # North arrow
    na_x = key_x + key_w - 8; na_y = key_y + key_h - 18
    ax.arrow(na_x, na_y, 0, 10, head_width=3, head_length=4, fc="black", ec="black", lw=0.6)
    ax.text(na_x, na_y + 12, "N", ha="center", va="bottom", fontsize=F_LABEL, weight="bold")

    # --- ADLR SKETCH ---
    adlr_x, adlr_y, adlr_w, adlr_h = INFO_X, key_y - 75, 110, 65
    ax.add_patch(mpatches.Rectangle((adlr_x, adlr_y), adlr_w, adlr_h, fill=False, lw=0.25))
    ax.text(adlr_x + adlr_w/2, adlr_y + adlr_h + 4,
            "ADLR SKETCH SHOWING THE LOCATION OF THE PROPOSED SITE WITHIN THE SURVEY NUMBER",
            ha="center", va="bottom", fontsize=F_COND, weight="bold")
    if adlr_file:
        adlr_img = Image.open(adlr_file).convert("RGB")
        adlr_img.thumbnail((adlr_w*5, adlr_h*5))
        ax.imshow(adlr_img, extent=(adlr_x+1, adlr_x+adlr_w-1, adlr_y+1, adlr_y+adlr_h-1))
    else:
        ax.text(adlr_x + adlr_w/2, adlr_y + adlr_h/2,
                "ADLR SKETCH (To be inserted here)", ha="center", va="center",
                fontsize=F_BODY, style="italic", color="gray")

    # --- LAND USE ANALYSIS ---
    lut_x, lut_y = INFO_X, adlr_y 
    ax.text(lut_x + 40, lut_y + 15, "LAND USE ANALYSIS",
            ha="center", va="bottom", fontsize=F_LABEL, weight="bold")
    headers = ["SL.No", "PARTICULARS", "AREA (Sq.m)", "%"]
    col_w = [12, 55, 30, 20]
    row_h = 6.5
    tbl_x, tbl_y = lut_x, lut_y
    xcur = tbl_x
    for i, h in enumerate(headers):
        ax.text(xcur + col_w[i]/2, tbl_y, h,
                ha="center", va="bottom", fontsize=F_COND, weight="bold")
        xcur += col_w[i]
    rows = [
        ["1", "SITE AREA", f"{site_width_m*site_length_m:.1f}", "100.00"],
        ["2", "TOTAL SITE AREA", f"{site_width_m*site_length_m:.1f}", "100.00"]
    ]
    for r_idx, row in enumerate(rows):
        y = tbl_y - (r_idx + 1)*row_h
        xcur = tbl_x
        for i, val in enumerate(row):
            ax.text(xcur + col_w[i]/2, y, val, ha="center", va="top", fontsize=F_COND)
            xcur += col_w[i]
    ax.add_patch(mpatches.Rectangle(
        (tbl_x - 1.5, tbl_y - (len(rows)+1)*row_h),
        sum(col_w)+3, (len(rows)+1.2)*row_h, fill=False, lw=0.25))

    # --- GENERAL CONDITIONS + NOTE ---
    GENERAL_CONDITIONS = [
        "1. The single plot layout plan is approved based on the survey sketch certified by the Assistant Director of Land Records.",
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
        "13. One tree for every 240.0 sq.m of the total floor area shall be planted and nurtured at the site in question.",
        "14. Prior permission should be obtained from the competent authority before constructing a culvert on the storm water drain between the land in question and the existing road attached to it if any.",
        "15. To abide by such other conditions as may be imposed by the Authority from time to time."
    ]

    NOTE_TEXT = [
        "1. The single plot plan is issued under the provisions of section 17 of KTCP Act 1961.",
        "2. The applicant has remitted fees of Rs.******* vide challan No. ********* Dated : **.**.****.",
        "3. The applicant has to abide by the conditions imposed in the single plot plan approval order.",
        "4. This single plot plan is issued vide number ***/***/***-******* dated : **.**.****."
    ]

    gc_x, gc_y_top = INFO_X, lut_y
    ax.text(gc_x, gc_y_top, "GENERAL CONDITIONS OF APPROVAL",
            ha="left", va="bottom", fontsize=4)
    cond_y = gc_y_top
    for cond in GENERAL_CONDITIONS:
        wrapped = textwrap.fill(cond, width=60)
        ax.text(gc_x, cond_y, wrapped, ha="left", va="top", fontsize=4)
        cond_y -= 8.0

    note_y = cond_y 
    ax.text(gc_x, note_y, "NOTE", fontsize=F_LABEL, weight="bold")
    for i, note in enumerate(NOTE_TEXT):
        ax.text(gc_x, note_y - (i + 1)*4.0, note, fontsize=F_COND, ha="left")

    # --- TITLE BLOCK ---
    tb_x, tb_y, tb_w, tb_h = LEFT, BOTTOM, PAGE_W_MM - LEFT - RIGHT, 35
    ax.add_patch(mpatches.Rectangle((tb_x, tb_y), tb_w, tb_h, fill=False, lw=LW_BOX))
    dv1, dv2 = tb_x + tb_w*0.48, tb_x + tb_w*0.70
    ax.plot([dv1,dv1],[tb_y,tb_y+tb_h],lw=0.25,color="black")
    ax.plot([dv2,dv2],[tb_y,tb_y+tb_h],lw=0.25,color="black")
    ax.text(tb_x+6, tb_y+tb_h-7, "DRAWING TITLE : SINGLE SITE LAYOUT PLAN", fontsize=F_LABEL, weight="bold")
    ax.text(tb_x+6, tb_y+tb_h-13, f"SCALE : 1:{int(SCALE)}", fontsize=F_COND)
    ax.text(tb_x+6, tb_y+tb_h-19, f"TOTAL BUILT-UP AREA : {total_builtup:.2f} Sq.m", fontsize=F_COND)
    ax.text(tb_x+6, tb_y+tb_h-25, f"SY. NO. : {survey_no}", fontsize=F_COND)
    ax.text(dv1+6, tb_y+tb_h-7, f"VILLAGE : {village}", fontsize=F_COND)
    ax.text(dv1+6, tb_y+tb_h-13, f"TALUK : {taluk}", fontsize=F_COND)
    ax.text(dv1+6, tb_y+tb_h-19, f"EPID : {epid}", fontsize=F_COND)
    ax.text(dv2+6, tb_y+tb_h-25, f"WARD NO. : {ward_no}    CONSTITUENCY : {constituency}", fontsize=F_COND)
    ax.text(PAGE_W_MM-RIGHT-4, tb_y+3, "All Dimensions in metres.", fontsize=F_COND, ha="right")
    ax.text(PAGE_W_MM - RIGHT - 4, tb_y - 5,
            "Prepared by Anantha (Ankusha Project)", fontsize=F_COND, ha="right", style="italic")

    # --- Export PDF ---
    pdf_buf = io.BytesIO()
    with PdfPages(pdf_buf) as pdf:
        pdf.savefig(fig, bbox_inches="tight", orientation="landscape", dpi=1200)
    pdf_buf.seek(0)

    st.download_button("⬇️ Download A3 PDF", data=pdf_buf,
                       file_name=f"Single_Site_{survey_no or 'site'}.pdf",
                       mime="application/pdf")
    st.pyplot(fig)





























