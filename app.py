# app.py
# Streamlit Single Site Plan — Page1-style A3 layout with interactive map + site dimension labeling
import io, math, textwrap
from typing import Optional
import requests
from PIL import Image, ImageDraw
import streamlit as st
import matplotlib as mpl
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.backends.backend_pdf import PdfPages

# Try to import interactive folium component; if not available we will fallback to static
try:
    from streamlit_folium import st_folium
    import folium
    FOLIUM_OK = True
except Exception:
    FOLIUM_OK = False

# ------------- Page config -------------
st.set_page_config(page_title="Single Site Plan — A3 (Page 1)", layout="wide")
st.title("Single Site Plan — Page 1 (A3)")

# ------------- Sidebar: New visible inputs -------------
st.sidebar.header("Site information (visible)")
survey_no = st.sidebar.text_input("Survey Number (SY. NO.)", "")
village = st.sidebar.text_input("Village", "")
taluk = st.sidebar.text_input("Taluk", "")
epid = st.sidebar.text_input("EPID (E Khata number)", "")
road_name = st.sidebar.text_input("Road Name", "")
ward_no = st.sidebar.text_input("Ward Number", "")
constituency = st.sidebar.text_input("Constituency Name", "")

st.sidebar.markdown("---")
st.sidebar.header("Site dimensions & road")
site_length_m = st.sidebar.number_input("Site Length (m)", min_value=0.1, value=15.0, step=0.1)
site_width_m = st.sidebar.number_input("Site Width (m)", min_value=0.1, value=12.0, step=0.1)
road_width_m = st.sidebar.number_input("Road Width (m)", min_value=0.1, value=6.0, step=0.1)
road_facing = st.sidebar.selectbox("Road Facing Side",
    ["North","South","East","West","North-East","North-West","South-East","South-West","Corner Plot (2 roads)"])
total_builtup = st.sidebar.number_input("Total Built-up Area (Sq.m)", min_value=0.0, value=0.0, step=1.0)

st.sidebar.markdown("---")
st.sidebar.header("Key Plan (choose location)")
kp_radius_m = st.sidebar.number_input("Key plan buffer radius (m)", min_value=50, value=200, step=10)
kp_zoom = st.sidebar.slider("Map zoom (10-16)", 10, 16, 14)

# Hidden backend fields retained but not shown in the sidebar (kept as empty strings)
ADLR_SKETCH = ""           # preserved but not shown
CONVERSION_ORDER = ""      # preserved
ARCH_REG = ""              # preserved
SANCTION_AUTH = ""         # preserved
OWNER_SIGNATURE = ""       # preserved
OWNER_NAME = ""            # preserved

# ------------- Map / key plan selection area (interactive when possible) -------------
picked_latlon = None
st.subheader("Pick site location on map (click to place marker)")

if FOLIUM_OK:
    default_center = (12.9716, 77.5946)  # Bangalore default
    m = folium.Map(location=default_center, zoom_start=kp_zoom, control_scale=True)
    folium.TileLayer('openstreetmap').add_to(m)
    folium.LatLngPopup().add_to(m)
    map_data = st_folium(m, width=700, height=350)
    if map_data:
        last = map_data.get("last_clicked")
        if last:
            picked_latlon = (last["lat"], last["lng"])
        else:
            center = map_data.get("center")
            if center:
                picked_latlon = (center["lat"], center["lng"])
else:
    # fallback: text input geocode (works in Cloud)
    addr = st.text_input("Address for key plan (or 'lat,lon')", "")
    def geocode(q: str) -> Optional[tuple]:
        if not q: return None
        if "," in q:
            try:
                a,b = q.split(",")
                return float(a.strip()), float(b.strip())
            except: pass
        try:
            r = requests.get("https://nominatim.openstreetmap.org/search",
                             params={"q": q, "format":"json", "limit":1},
                             headers={"User-Agent":"SingleSitePlanApp/1.0"}, timeout=8)
            r.raise_for_status()
            data = r.json()
            if data:
                return (float(data[0]["lat"]), float(data[0]["lon"]))
        except Exception:
            return None
    coords = geocode(addr)
    if coords:
        picked_latlon = coords
        st.success(f"Key plan center set: {coords[0]:.6f}, {coords[1]:.6f}")

# ------------- Helper functions for static OSM tile fetch and make keyplan image -------------
def latlon_to_tile_xy(lat_deg, lon_deg, zoom):
    lat_rad = math.radians(lat_deg)
    n = 2.0 ** zoom
    xtile = (lon_deg + 180.0) / 360.0 * n
    ytile = (1.0 - math.log(math.tan(lat_rad) + 1/math.cos(lat_rad)) / math.pi) / 2.0 * n
    return xtile, ytile

def fetch_tile_image(z, x, y):
    url = f"https://tile.openstreetmap.org/{z}/{x}/{y}.png"
    headers = {"User-Agent":"SingleSitePlanApp/1.0"}
    try:
        r = requests.get(url, headers=headers, timeout=8)
        r.raise_for_status()
        return Image.open(io.BytesIO(r.content)).convert("RGBA")
    except Exception:
        return None

def make_keyplan_image(lat, lon, zoom=14, tiles_radius=1, buffer_m=200):
    xtile_f, ytile_f = latlon_to_tile_xy(lat, lon, zoom)
    x_center = int(math.floor(xtile_f)); y_center = int(math.floor(ytile_f))
    size = 256
    grid = []
    for dy in range(-tiles_radius, tiles_radius+1):
        row=[]
        for dx in range(-tiles_radius, tiles_radius+1):
            img = fetch_tile_image(zoom, x_center+dx, y_center+dy)
            if img is None:
                img = Image.new("RGBA", (size,size), (240,240,240,255))
            row.append(img)
        grid.append(row)
    cols = 2*tiles_radius+1
    stitched = Image.new("RGBA", (cols*size, cols*size))
    for r in range(cols):
        for c in range(cols):
            stitched.paste(grid[r][c], (c*size, r*size))
    frac_x = (xtile_f - x_center); frac_y = (ytile_f - y_center)
    center_px = (tiles_radius*size + int(frac_x*size), tiles_radius*size + int(frac_y*size))
    R = 6378137.0
    meters_per_pixel = (math.cos(math.radians(lat)) * 2 * math.pi * R) / (256 * (2**zoom))
    radius_px = max(2, int(buffer_m / meters_per_pixel))
    draw = ImageDraw.Draw(stitched)
    bbox = [center_px[0]-radius_px, center_px[1]-radius_px, center_px[0]+radius_px, center_px[1]+radius_px]
    draw.ellipse(bbox, outline=(200,0,0,220), width=3)
    draw.ellipse(bbox, fill=(200,0,0,45))
    draw.ellipse([center_px[0]-3, center_px[1]-3, center_px[0]+3, center_px[1]+3], fill=(0,0,0,255))
    return stitched

# ------------- Layout constants (mm) -------------
PAGE_W_MM = 420.0; PAGE_H_MM = 297.0
FIG_W_IN = PAGE_W_MM / 25.4; FIG_H_IN = PAGE_H_MM / 25.4

LEFT_MARGIN = 12.0; RIGHT_MARGIN = 12.0; TOP_MARGIN = 12.0; BOTTOM_MARGIN = 12.0
DRAWING_AREA_W = PAGE_W_MM * 0.62
DRAWING_AREA_H = PAGE_H_MM - TOP_MARGIN - BOTTOM_MARGIN - 36
# SHIFT DOWN slightly to create header space (tweak here to move the entire left drawing)
DRAWING_ORIGIN_X = LEFT_MARGIN + 2
DRAWING_ORIGIN_Y = BOTTOM_MARGIN + 36 - 15   # <- adjust this to move the site box up/down
INFO_COL_X = DRAWING_ORIGIN_X + DRAWING_AREA_W + 8
INFO_COL_W = PAGE_W_MM - INFO_COL_X - RIGHT_MARGIN
TITLEBLOCK_H = 35.0; TITLEBLOCK_Y = BOTTOM_MARGIN

# ------------- Button: Generate PDF -------------
if st.button("Generate A3 PDF"):
    # Set font family if available on container; otherwise fallback
    try:
        mpl.rcParams["font.family"] = "Arial Narrow"
    except Exception:
        pass

    # Prepare figure
    fig = plt.figure(figsize=(FIG_W_IN, FIG_H_IN), dpi=72)
    ax = fig.add_subplot(111)
    ax.set_xlim(0, PAGE_W_MM); ax.set_ylim(0, PAGE_H_MM)
    ax.set_aspect('equal'); ax.axis('off')

    # font sizes and line weights (tweak these constants to change global sizes)
    F_TITLE = 10; F_LABEL = 9; F_BODY = 7; F_COND = 6.0
    LW_BORDER = 0.4; LW_BOX = 0.35; LW_SITE = 0.9

    # Page border
    ax.add_patch(mpatches.Rectangle((LEFT_MARGIN/2, BOTTOM_MARGIN/2),
                                    PAGE_W_MM - LEFT_MARGIN, PAGE_H_MM - BOTTOM_MARGIN,
                                    fill=False, lw=LW_BORDER))

    # Drawing box (left)
    ax.add_patch(mpatches.Rectangle((DRAWING_ORIGIN_X, DRAWING_ORIGIN_Y),
                                    DRAWING_AREA_W, DRAWING_AREA_H, fill=False, lw=LW_BOX))

    # compute mm per metre for chosen scale (we use 1:100 fallback, could be selected)
    SCALE = 100.0
    mm_per_m = 1000.0 / SCALE
    # fit if overflow (keeps site inside drawing area)
    inner_pad = 8.0
    usable_w = DRAWING_AREA_W - 2*inner_pad; usable_h = DRAWING_AREA_H - 2*inner_pad
    req_w_mm = site_width_m * mm_per_m; req_h_mm = site_length_m * mm_per_m
    if req_w_mm <= usable_w and req_h_mm <= usable_h:
        mm_per_m_use = mm_per_m
    else:
        mm_per_m_use = min(usable_w / site_width_m, usable_h / site_length_m)

    site_w_mm = site_width_m * mm_per_m_use; site_h_mm = site_length_m * mm_per_m_use
    # site origin inside drawing area (centered)
    site_x = DRAWING_ORIGIN_X + inner_pad + (usable_w - site_w_mm)/2
    site_y = DRAWING_ORIGIN_Y + inner_pad + (usable_h - site_h_mm)/2

    # Draw site rectangle
    ax.add_patch(mpatches.Rectangle((site_x, site_y), site_w_mm, site_h_mm, fill=False, lw=LW_SITE))

    # Draw dimension labels on site edges (centered)
    # length label (top edge)
    ax.text(site_x + site_w_mm/2, site_y + site_h_mm + 4, f"{site_width_m:.2f} m", ha='center', va='bottom', fontsize=F_BODY)
    # width label (right edge)
    ax.text(site_x + site_w_mm + 4, site_y + site_h_mm/2, f"{site_length_m:.2f} m", ha='left', va='center', fontsize=F_BODY, rotation=270)

    # Draw a small tick/line marks at midpoints (visual cue)
    ax.plot([site_x + site_w_mm/2 - 8, site_x + site_w_mm/2 + 8], [site_y + site_h_mm, site_y + site_h_mm], lw=0.8)
    ax.plot([site_x + site_w_mm, site_x + site_w_mm], [site_y + site_h_mm/2 - 8, site_y + site_h_mm/2 + 8], lw=0.8)

    # Road label: position text depending on chosen facing
    road_label_text = f"Road: {road_name} ({road_width_m:.1f} m)"
    # determine coordinates to place road label (approx near the mid-point of the facing edge)
    if road_facing in ("North",):
        ax.text(site_x + site_w_mm/2, site_y + site_h_mm + 12, road_label_text, ha='center', va='bottom', fontsize=F_BODY)
    elif road_facing in ("South",):
        ax.text(site_x + site_w_mm/2, site_y - 12, road_label_text, ha='center', va='top', fontsize=F_BODY)
    elif road_facing in ("East",):
        ax.text(site_x + site_w_mm + 12, site_y + site_h_mm/2, road_label_text, ha='left', va='center', fontsize=F_BODY, rotation=270)
    elif road_facing in ("West",):
        ax.text(site_x - 12, site_y + site_h_mm/2, road_label_text, ha='right', va='center', fontsize=F_BODY, rotation=270)
    else:
        # diagonal / corner or other: place top-right
        ax.text(site_x + site_w_mm + 6, site_y + site_h_mm + 6, road_label_text, ha='left', va='bottom', fontsize=F_BODY)

    # SITE NO text (centered above)
    ax.text(site_x + site_w_mm/2, site_y + site_h_mm + 18, f"SITE (SY.NO. {survey_no})", ha='center', va='bottom', fontsize=F_TITLE, weight='bold')

    # Key plan (right)
    key_x = INFO_COL_X + 6; key_y = PAGE_H_MM - TOP_MARGIN - 74; key_w = INFO_COL_W - 12; key_h = 74
    ax.add_patch(mpatches.Rectangle((key_x, key_y), key_w, key_h, fill=False, lw=LW_BOX))
    ax.plot([key_x, key_x + key_w], [key_y + key_h - 10, key_y + key_w - 10], lw=LW_BOX, color='black')  # small title bar line
    ax.text(key_x + 6, key_y + key_h - 6, "KEY PLAN (NOT TO SCALE)", fontsize=F_LABEL, weight='bold', va='top')

    # render keyplan from picked latlon if available
    if picked_latlon:
        try:
            kimg = make_keyplan_image(picked_latlon[0], picked_latlon[1], zoom=kp_zoom, tiles_radius=1, buffer_m=kp_radius_m)
            scaled = kimg.resize((int(key_w*3), int(key_h*3)), Image.LANCZOS)
            ax.imshow(scaled, extent=(key_x+1, key_x+key_w-1, key_y+1, key_y+key_h-1), zorder=1)
            ax.text(key_x + key_w/2, key_y - 6, f"{picked_latlon[0]:.6f},{picked_latlon[1]:.6f}", fontsize=F_BODY, ha='center')
        except Exception:
            ax.text(key_x + key_w/2, key_y + key_h/2, "Key plan (no preview)", ha='center', va='center', fontsize=F_BODY)

    # North arrow inside key box
    na_x = key_x + key_w - 12; na_y = key_y + key_h - 20
    ax.arrow(na_x, na_y, 0, 10, head_width=3, head_length=4, fc='black', ec='black', lw=0.8)
    ax.text(na_x, na_y + 12, "N", ha='center', va='bottom', fontsize=F_LABEL, weight='bold')

    # Land use analysis table (right column) - positions can be tweaked by lut_y
    lut_x = INFO_COL_X + 6; lut_y = key_y - 42
    ax.text(lut_x + (INFO_COL_W/2 - 6), lut_y + 18, "LAND USE ANALYSIS", ha='center', fontsize=F_LABEL, weight='bold')
    col_w = [18, 60, 36, 30]; tbl_start_x = lut_x + 2; tbl_start_y = lut_y + 12
    headers = ["SL. No","PARTICULARS","AREA IN Sqm.","%"]
    xcur = tbl_start_x
    for i,h in enumerate(headers):
        ax.text(xcur + col_w[i]/2, tbl_start_y, h.upper(), ha='center', va='center', fontsize=F_COND, weight='bold')
        xcur += col_w[i]
    rows = [["1", "SITE AREA", f"{site_width_m*site_length_m:.1f}", "100.00"], ["2", "TOTAL SITE AREA", f"{site_width_m*site_length_m:.1f}", "100.00"]]
    row_h = 7.0
    for rid, row in enumerate(rows):
        y = tbl_start_y - (rid+1)*row_h
        xcur = tbl_start_x
        for i,val in enumerate(row):
            ax.text(xcur + col_w[i]/2, y, val, ha='center', va='center', fontsize=F_COND)
            xcur += col_w[i]
    ax.add_patch(mpatches.Rectangle((tbl_start_x-2, tbl_start_y - (len(rows)+0.8)*row_h, sum(col_w), (len(rows)+0.8)*row_h), fill=False, lw=0.25))

    # General Conditions (right column) - cond_spacing controls line spacing
    gc_x = INFO_COL_X + 4; gc_y_top = tbl_start_y - (len(rows)+0.8)*row_h - 6
    ax.text(gc_x + (INFO_COL_W/2 - 6), gc_y_top, "GENERAL CONDITIONS OF APPROVAL", ha='center', fontsize=F_LABEL, weight='bold')
    cond_y = gc_y_top - 6; cond_spacing = 4.0
    for i,cond in enumerate([
        # shortened here for readability, keep full 15 in real code
        "1. The single plot layout plan is approved based on the survey sketch certified by the Assistant Director of Land records.",
        "2. Building construction shall be undertaken only after obtaining approval for the building plan from the city corporation as per the approved single site layout plan.",
        # ... include all 15 lines verbatim ...
    ]):
        wrapped = textwrap.fill(cond, width=66)
        ax.text(gc_x + 2, cond_y - i*cond_spacing, wrapped, ha='left', va='top', fontsize=F_COND)

    # NOTE block
    note_y = cond_y - 15*cond_spacing - 4
    ax.text(gc_x + 2, note_y, "NOTE", fontsize=F_LABEL, weight='bold')
    ax.text(gc_x + 2, note_y - 5, "1. The single plot plan is issued under The Provision of section 17 of KTCP Act 1961", fontsize=F_COND)

    # TITLE BLOCK bottom (as per sample) - keep same visual structure but show new fields
    tb_x = LEFT_MARGIN; tb_y = TITLEBLOCK_Y; tb_w = PAGE_W_MM - LEFT_MARGIN - RIGHT_MARGIN; tb_h = TITLEBLOCK_H
    ax.add_patch(mpatches.Rectangle((tb_x, tb_y), tb_w, tb_h, fill=False, lw=LW_BOX))
    # vertical dividers positions (tweak as needed)
    dv1 = tb_x + tb_w*0.50; dv2 = tb_x + tb_w*0.72
    ax.plot([dv1, dv1], [tb_y, tb_y+tb_h], lw=0.25, color='black')
    ax.plot([dv2, dv2], [tb_y, tb_y+tb_h], lw=0.25, color='black')

    # Title block fields (left / mid / right blocks) - match sample positions
    ax.text(tb_x + 4, tb_y + tb_h - 7, "DRAWING TITLE : SINGLE SITE LAYOUT PLAN", fontsize=F_LABEL)
    ax.text(tb_x + 4, tb_y + tb_h - 13, f"SCALE : 1:{int(SCALE)}", fontsize=F_COND)
    ax.text(tb_x + 4, tb_y + tb_h - 19, f"TOTAL BUILT-UP AREA : {total_builtup:.2f} Sq.m", fontsize=F_COND)
    ax.text(tb_x + 4, tb_y + tb_h - 25, f"SY. NO. : {survey_no}", fontsize=F_COND)

    # mid block
    ax.text(dv1 + 4, tb_y + tb_h - 7, f"VILLAGE : {village}", fontsize=F_COND)
    ax.text(dv1 + 4, tb_y + tb_h - 13, f"TALUK : {taluk}", fontsize=F_COND)
    ax.text(dv1 + 4, tb_y + tb_h - 19, f"EPID : {epid}", fontsize=F_COND)
    ax.text(dv1 + 4, tb_y + tb_h - 25, f"ROAD NAME : {road_name}", fontsize=F_COND)

    # right block
    ax.text(dv2 + 4, tb_y + tb_h - 7, f"ROAD WIDTH : {road_width_m:.1f} m", fontsize=F_COND)
    ax.text(dv2 + 4, tb_y + tb_h - 13, f"ROAD FACING : {road_facing}", fontsize=F_COND)
    ax.text(dv2 + 4, tb_y + tb_h - 19, f"SITE DIMENSIONS : {site_length_m:.2f} m x {site_width_m:.2f} m", fontsize=F_COND)
    ax.text(dv2 + 4, tb_y + tb_h - 25, f"WARD NO. : {ward_no}    CONSTITUENCY : {constituency}", fontsize=F_COND)

    # All dims note flush bottom-right
    ax.text(PAGE_W_MM - RIGHT_MARGIN - 4, tb_y + 3, "All Dimensions in metres.", fontsize=F_COND, ha='right')

    # Save PDF to BytesIO and provide download button
    pdf_buf = io.BytesIO()
    with PdfPages(pdf_buf) as pdf:
        pdf.savefig(fig, bbox_inches='tight', orientation='landscape')
    pdf_buf.seek(0)
    st.success("Generated A3 PDF (Page 1 style).")
    st.download_button("Download PDF", data=pdf_buf, file_name=f"Single_Site_{survey_no or 'site'}.pdf", mime="application/pdf")
    st.pyplot(fig)
