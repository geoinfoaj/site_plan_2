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
st.sidebar.header("Site information")
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
road_facing = st.sidebar.selectbox(
    "Road Facing Side",
    ["North", "South", "East", "West", "North-East", "North-West", "South-East", "South-West", "Corner Plot (2 roads)"],
)
total_builtup = st.sidebar.number_input("Total Built-up Area (Sq.m)", min_value=0.0, value=0.0, step=1.0)

st.sidebar.markdown("---")
st.sidebar.header("Key Plan (choose location)")
kp_radius_m = st.sidebar.number_input("Key plan buffer radius (m)", min_value=50, value=200, step=10)
kp_zoom = st.sidebar.slider("Map zoom (10-16)", 10, 16, 14)

# Hidden backend fields retained for mapping/automation
ADLR_SKETCH = ""
CONVERSION_ORDER = ""
ARCH_REG = ""
SANCTION_AUTH = ""
OWNER_SIGNATURE = ""
OWNER_NAME = ""

# ------------- Map section -------------
picked_latlon = None
st.subheader("Pick site location on map (click to place marker)")

if FOLIUM_OK:
    default_center = (12.9716, 77.5946)  # Bangalore
    m = folium.Map(location=default_center, zoom_start=kp_zoom, control_scale=True)
    folium.TileLayer("openstreetmap").add_to(m)
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
    addr = st.text_input("Address for key plan (or 'lat,lon')", "")
    def geocode(q: str) -> Optional[tuple]:
        if not q:
            return None
        if "," in q:
            try:
                a, b = q.split(",")
                return float(a.strip()), float(b.strip())
            except:
                pass
        try:
            r = requests.get(
                "https://nominatim.openstreetmap.org/search",
                params={"q": q, "format": "json", "limit": 1},
                headers={"User-Agent": "SingleSitePlanApp/1.0"},
                timeout=8,
            )
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

# ---------- Helper for static OSM ----------
def latlon_to_tile_xy(lat_deg, lon_deg, zoom):
    lat_rad = math.radians(lat_deg)
    n = 2.0 ** zoom
    xtile = (lon_deg + 180.0) / 360.0 * n
    ytile = (1.0 - math.log(math.tan(lat_rad) + 1 / math.cos(lat_rad)) / math.pi) / 2.0 * n
    return xtile, ytile

def fetch_tile_image(z, x, y):
    url = f"https://tile.openstreetmap.org/{z}/{x}/{y}.png"
    headers = {"User-Agent": "SingleSitePlanApp/1.0"}
    try:
        r = requests.get(url, headers=headers, timeout=8)
        r.raise_for_status()
        return Image.open(io.BytesIO(r.content)).convert("RGBA")
    except Exception:
        return None

def make_keyplan_image(lat, lon, zoom=14, tiles_radius=1, buffer_m=200):
    xtile_f, ytile_f = latlon_to_tile_xy(lat, lon, zoom)
    x_center = int(math.floor(xtile_f))
    y_center = int(math.floor(ytile_f))
    size = 256
    grid = []
    for dy in range(-tiles_radius, tiles_radius + 1):
        row = []
        for dx in range(-tiles_radius, tiles_radius + 1):
            img = fetch_tile_image(zoom, x_center + dx, y_center + dy)
            if img is None:
                img = Image.new("RGBA", (size, size), (240, 240, 240, 255))
            row.append(img)
        grid.append(row)
    cols = 2 * tiles_radius + 1
    stitched = Image.new("RGBA", (cols * size, cols * size))
    for r in range(cols):
        for c in range(cols):
            stitched.paste(grid[r][c], (c * size, r * size))
    frac_x = xtile_f - x_center
    frac_y = ytile_f - y_center
    center_px = (tiles_radius * size + int(frac_x * size), tiles_radius * size + int(frac_y * size))
    R = 6378137.0
    mpp = (math.cos(math.radians(lat)) * 2 * math.pi * R) / (256 * (2**zoom))
    radius_px = max(2, int(buffer_m / mpp))
    draw = ImageDraw.Draw(stitched)
    bbox = [
        center_px[0] - radius_px,
        center_px[1] - radius_px,
        center_px[0] + radius_px,
        center_px[1] + radius_px,
    ]
    draw.ellipse(bbox, outline=(200, 0, 0, 220), width=3)
    draw.ellipse(bbox, fill=(200, 0, 0, 45))
    draw.ellipse(
        [center_px[0] - 3, center_px[1] - 3, center_px[0] + 3, center_px[1] + 3],
        fill=(0, 0, 0, 255),
    )
    return stitched

# ---------- Layout constants ----------
PAGE_W_MM = 420.0
PAGE_H_MM = 297.0
FIG_W_IN = PAGE_W_MM / 25.4
FIG_H_IN = PAGE_H_MM / 25.4
LEFT_MARGIN = 12.0
RIGHT_MARGIN = 12.0
TOP_MARGIN = 12.0
BOTTOM_MARGIN = 12.0
DRAWING_AREA_W = PAGE_W_MM * 0.62
DRAWING_AREA_H = PAGE_H_MM - TOP_MARGIN - BOTTOM_MARGIN - 36
DRAWING_ORIGIN_X = LEFT_MARGIN + 2
DRAWING_ORIGIN_Y = BOTTOM_MARGIN + 36 - 15
INFO_COL_X = DRAWING_ORIGIN_X + DRAWING_AREA_W + 8
INFO_COL_W = PAGE_W_MM - INFO_COL_X - RIGHT_MARGIN
TITLEBLOCK_H = 35.0
TITLEBLOCK_Y = BOTTOM_MARGIN

# ------------- Generate PDF -------------
if st.button("Generate A3 PDF"):
    fig = plt.figure(figsize=(FIG_W_IN, FIG_H_IN), dpi=72)
    ax = fig.add_subplot(111)
    ax.set_xlim(0, PAGE_W_MM)
    ax.set_ylim(0, PAGE_H_MM)
    ax.set_aspect("equal")
    ax.axis("off")

    F_TITLE, F_LABEL, F_BODY, F_COND = 10, 9, 7, 6
    LW_BORDER, LW_BOX, LW_SITE = 0.4, 0.35, 0.9

    ax.add_patch(
        mpatches.Rectangle(
            (LEFT_MARGIN / 2, BOTTOM_MARGIN / 2),
            PAGE_W_MM - LEFT_MARGIN,
            PAGE_H_MM - BOTTOM_MARGIN,
            fill=False,
            lw=LW_BORDER,
        )
    )
    ax.add_patch(
        mpatches.Rectangle(
            (DRAWING_ORIGIN_X, DRAWING_ORIGIN_Y),
            DRAWING_AREA_W,
            DRAWING_AREA_H,
            fill=False,
            lw=LW_BOX,
        )
    )

    SCALE = 100.0
    mm_per_m = 1000.0 / SCALE
    inner_pad = 8.0
    usable_w = DRAWING_AREA_W - 2 * inner_pad
    usable_h = DRAWING_AREA_H - 2 * inner_pad
    req_w_mm = site_width_m * mm_per_m
    req_h_mm = site_length_m * mm_per_m
    mm_per_m_use = min(usable_w / site_width_m, usable_h / site_length_m)
    site_w_mm = site_width_m * mm_per_m_use
    site_h_mm = site_length_m * mm_per_m_use
    site_x = DRAWING_ORIGIN_X + inner_pad + (usable_w - site_w_mm) / 2
    site_y = DRAWING_ORIGIN_Y + inner_pad + (usable_h - site_h_mm) / 2

    ax.add_patch(
        mpatches.Rectangle((site_x, site_y), site_w_mm, site_h_mm, fill=False, lw=LW_SITE)
    )

    ax.text(
        site_x + site_w_mm / 2,
        site_y + site_h_mm + 4,
        f"{site_width_m:.2f} m",
        ha="center",
        va="bottom",
        fontsize=F_BODY,
    )
    ax.text(
        site_x + site_w_mm + 4,
        site_y + site_h_mm / 2,
        f"{site_length_m:.2f} m",
        ha="left",
        va="center",
        fontsize=F_BODY,
        rotation=270,
    )

    road_label_text = f"Road: {road_name} ({road_width_m:.1f} m)"
    if road_facing == "North":
        ax.text(site_x + site_w_mm / 2, site_y + site_h_mm + 12, road_label_text, ha="center", va="bottom", fontsize=F_BODY)
    elif road_facing == "South":
        ax.text(site_x + site_w_mm / 2, site_y - 12, road_label_text, ha="center", va="top", fontsize=F_BODY)
    elif road_facing == "East":
        ax.text(site_x + site_w_mm + 12, site_y + site_h_mm / 2, road_label_text, ha="left", va="center", fontsize=F_BODY, rotation=270)
    elif road_facing == "West":
        ax.text(site_x - 12, site_y + site_h_mm / 2, road_label_text, ha="right", va="center", fontsize=F_BODY, rotation=270)
    else:
        ax.text(site_x + site_w_mm + 6, site_y + site_h_mm + 6, road_label_text, ha="left", va="bottom", fontsize=F_BODY)

    ax.text(site_x + site_w_mm / 2, site_y + site_h_mm + 18, f"SITE (SY.NO. {survey_no})", ha="center", va="bottom", fontsize=F_TITLE, weight="bold")

    # ---- Land use analysis table ----
    key_x = INFO_COL_X + 6
    key_y = PAGE_H_MM - TOP_MARGIN - 74
    key_w = INFO_COL_W - 12
    key_h = 74

    lut_x = INFO_COL_X + 6
    lut_y = key_y - 42
    ax.text(lut_x + (INFO_COL_W / 2 - 6), lut_y + 18, "LAND USE ANALYSIS", ha="center", fontsize=F_LABEL, weight="bold")
    col_w = [18, 60, 36, 30]
    tbl_start_x = lut_x + 2
    tbl_start_y = lut_y + 12
    headers = ["SL. No", "PARTICULARS", "AREA IN Sqm.", "%"]
    xcur = tbl_start_x
    for i, h in enumerate(headers):
        ax.text(xcur + col_w[i] / 2, tbl_start_y, h.upper(), ha="center", va="center", fontsize=F_COND, weight="bold")
        xcur += col_w[i]
    rows = [
        ["1", "SITE AREA", f"{site_width_m * site_length_m:.1f}", "100.00"],
        ["2", "TOTAL SITE AREA", f"{site_width_m * site_length_m:.1f}", "100.00"],
    ]
    row_h = 7.0
    for rid, row in enumerate(rows):
        y = tbl_start_y - (rid + 1) * row_h
        xcur = tbl_start_x
        for i, val in enumerate(row):
            ax.text(xcur + col_w[i] / 2, y, val, ha="center", va="center", fontsize=F_COND)
            xcur += col_w[i]
    # ✅ corrected rectangle syntax
    ax.add_patch(
        mpatches.Rectangle(
            (tbl_start_x - 2, tbl_start_y - (len(rows) + 0.8) * row_h),
            sum(col_w),
            (len(rows) + 0.8) * row_h,
            fill=False,
            lw=0.25,
        )
    )

    # ---- Title block ----
    tb_x, tb_y, tb_w, tb_h = LEFT_MARGIN, BOTTOM_MARGIN, PAGE_W_MM - LEFT_MARGIN - RIGHT_MARGIN, 35.0
    ax.add_patch(mpatches.Rectangle((tb_x, tb_y), tb_w, tb_h, fill=False, lw=LW_BOX))
    dv1 = tb_x + tb_w * 0.50
    dv2 = tb_x + tb_w * 0.72
    ax.plot([dv1, dv1], [tb_y, tb_y + tb_h], lw=0.25, color="black")
    ax.plot([dv2, dv2], [tb_y, tb_y + tb_h], lw=0.25, color="black")
    ax.text(tb_x + 4, tb_y + tb_h - 7, "DRAWING TITLE : SINGLE SITE LAYOUT PLAN", fontsize=F_LABEL)
    ax.text(tb_x + 4, tb_y + tb_h - 13, f"SCALE : 1:{int(SCALE)}", fontsize=F_COND)
    ax.text(tb_x + 4, tb_y + tb_h - 19, f"TOTAL BUILT-UP AREA : {total_builtup:.2f} Sq.m", fontsize=F_COND)
    ax.text(tb_x + 4, tb_y + tb_h - 25, f"SY. NO. : {survey_no}", fontsize=F_COND)
    ax.text(dv1 + 4, tb_y + tb_h - 7, f"VILLAGE : {village}", fontsize=F_COND)
    ax.text(dv1 + 4, tb_y + tb_h - 13, f"TALUK : {taluk}", fontsize=F_COND)
    ax.text(dv1 + 4, tb_y + tb_h - 19, f"EPID : {epid}", fontsize=F_COND)
    ax.text(dv1 + 4, tb_y + tb_h - 25, f"ROAD NAME : {road_name}", fontsize=F_COND)
    ax.text(dv2 + 4, tb_y + tb_h - 7, f"ROAD WIDTH : {road_width_m:.1f} m", fontsize=F_COND)
    ax.text(dv2 + 4, tb_y + tb_h - 13, f"ROAD FACING : {road_facing}", fontsize=F_COND)
    ax.text(dv2 + 4, tb_y + tb_h - 19, f"SITE DIMENSIONS : {site_length_m:.2f} m x {site_width_m:.2f} m", fontsize=F_COND)
    ax.text(dv2 + 4, tb_y + tb_h - 25, f"WARD NO. : {ward_no}    CONSTITUENCY : {constituency}", fontsize=F_COND)
    ax.text(PAGE_W_MM - RIGHT_MARGIN - 4, tb_y + 3, "All Dimensions in metres.", fontsize=F_COND, ha="right")

        # --- Save PDF & show in Streamlit ---
    pdf_buf = io.BytesIO()
    with PdfPages(pdf_buf) as pdf:
        pdf.savefig(fig, bbox_inches="tight", orientation="landscape")
    pdf_buf.seek(0)

    st.success("✅ A3 PDF (Page 1) generated successfully.")
    st.download_button(
        "⬇️ Download A3 PDF",
        data=pdf_buf,
        file_name=f"Single_Site_{survey_no or 'site'}.pdf",
        mime="application/pdf",
    )
    st.pyplot(fig)


