# LD Lookup — Version 6.0.2.2 (Lookup & Audit, camera + OCR.space)
# - Item lookup: single code + Find/Clear
# - Audit: camera photo + one editable text area; auto-fix 7-digit -> Lxxxxxxx; highlight corrections
# - Table: LNumber + Image (100px clickable thumb → opens raw image source in new tab)
# - Header color = #0960AC; LD logo from repo root (Ld-logo.png)
# - OCR: uses OCR.space API via Streamlit secrets (OCRSPACE_API_KEY)

import re
from typing import List, Tuple

import pandas as pd  # (kept in case you expand later)
import requests
import streamlit as st

# ------------- Page & Styles -------------
BG_DARK = "#0960AC"          # page background
HEADER = "#0960AC"           # header color
VERSION = "6.0.2"

st.set_page_config(page_title=f"LD Lookup v{VERSION}", page_icon="🧾", layout="wide")

st.markdown(
    f"""
    <style>
      .stApp, .main {{ background-color: {BG_DARK}; }}
      .block-container {{
          background: #ffffff;
          border-radius: 16px;
          padding: 18px 18px 10px 18px;
          box-shadow: 0 2px 12px rgba(0,0,0,.12);
      }}
      .topbar {{
          background: {HEADER};
          color: #fff;
          padding: 14px 18px;
          border-radius: 12px;
          margin-bottom: 10px;
          display: flex; align-items: center; gap: 14px;
      }}
      .topbar h1 {{ margin: 0; font-size: 22px; color: #fff; }}
      .disclaimer {{ color:#0960AC; font-size:.92rem; margin:4px 0 0 0; }}
      .tbl table {{ border-collapse: collapse; width: 100%; }}
      .tbl th, .tbl td {{ border: 1px solid #e6e6e6; padding: 8px; vertical-align: middle; font-size: .92rem; }}
      .tbl th {{ background: #f6f7fb; color: {BG_DARK}; text-align: left; }}
      .thumb {{
          height: 100px; width: auto; object-fit: contain; border-radius: 6px;
          border: 1px solid #e6e6e6; background: #fff;
      }}
      .chip {{ display:inline-block; padding:4px 8px; margin:2px; border-radius:10px; background:#F2F7FF; border:1px solid #DFE7F5; }}
      .chip.fixed {{ background:#FFF7CC; border-color:#F3D25A; }}
      .muted {{ color:#6b7280; font-size:.9rem; }}
      @media (max-width: 640px) {{
        .tbl th, .tbl td {{ font-size: .88rem; }}
        .thumb {{ height: 96px; }}
      }}
    </style>
    """,
    unsafe_allow_html=True,
)

# ------------- Header with logo -------------
logo_col, title_col = st.columns([1, 5])
with logo_col:
    try:
        st.image("Ld-logo.png", use_column_width=True)
    except Exception:
        pass  # logo optional
with title_col:
    st.markdown(
        f"""
        <div class="topbar">
          <h1>LD Lookup — Version {VERSION} (Lookup & Audit)</h1>
        </div>
        <div class="disclaimer">This is not an official app — currently in debugging mode</div>
        """,
        unsafe_allow_html=True,
    )

# ------------- Constants & Helpers -------------
IMG_WIDTH = 640
IMG_QUALITY = 75
CDN_TEMPLATE = "https://cdn-tp2.mozu.com/28945-m4/cms/files/{L}.jpg?w={w}&q={q}"

RE_LNUM = re.compile(r"\bL\d+\b", flags=re.IGNORECASE)
RE_BARE7 = re.compile(r"\b(\d{7})\b")

def build_image_url(l_number: str, width=IMG_WIDTH, quality=IMG_QUALITY) -> str:
    l = str(l_number).strip().upper()
    return CDN_TEMPLATE.format(L=l, w=width, q=quality)

def extract_lnumbers_from_text_with_correction(text: str) -> Tuple[List[str], List[str]]:
    """
    Returns (lnumbers, corrected):
      - lnumbers: deduped, order-preserving list of 'L\\d+'
      - corrected: subset that came from bare 7-digit numbers auto-prefixed with 'L'
    """
    if not text:
        return [], []
    found: List[str] = []
    corrected: List[str] = []

    for m in RE_LNUM.finditer(text):
        found.append(m.group(0).upper())

    for m in RE_BARE7.finditer(text):
        candidate = f"L{m.group(1)}"
        found.append(candidate.upper())
        corrected.append(candidate.upper())

    out, seen = [], set()
    corr_out: List[str] = []
    corr_set = set(corrected)
    for x in found:
        if x not in seen:
            seen.add(x)
            out.append(x)
            if x in corr_set:
                corr_out.append(x)
    return out, corr_out

# OCR.space (for Audit camera input)
def _ocrspace_bytes(image_bytes: bytes) -> str:
    api_key = st.secrets.get("OCRSPACE_API_KEY")
    if not api_key:
        return ""
    try:
        endpoint = "https://api.ocr.space/parse/image"
        files = {"file": ("upload.png", image_bytes)}
        data = {"isOverlayRequired": "false", "language": "eng", "scale": "true"}
        headers = {"apikey": api_key}
        r = requests.post(endpoint, headers=headers, data=data, files=files, timeout=30)
        r.raise_for_status()
        js = r.json()
        if js.get("IsErroredOnProcessing") or not js.get("ParsedResults"):
            return ""
        return "\n".join(p.get("ParsedText", "") for p in js["ParsedResults"])
    except Exception:
        return ""

# ---- Rendering helpers ----
def render_table(l_numbers: List[str]) -> None:
    """Render a table: LNumber + clickable 100px thumbnail that opens the raw image source."""
    rows = []
    for l in l_numbers:
        url = build_image_url(l)
        img_cell = (
            f'<a href="{url}" target="_blank" rel="noopener noreferrer" '
            f'title="Open full-size image">'
            f'<img class="thumb" src="{url}" alt="{l}"></a>'
        )
        rows.append(f"<tr><td>{l}</td><td>{img_cell}</td></tr>")
    st.markdown(
        f"""
        <div class="tbl">
          <table>
            <thead><tr><th>LNumber</th><th>Image</th></tr></thead>
            <tbody>{''.join(rows)}</tbody>
          </table>
        </div>
        """,
        unsafe_allow_html=True,
    )

def clear_lookup_callback():
    st.session_state["lookup_input"] = ""
    st.rerun()

# ------------- Tabs -------------
tab_lookup, tab_audit = st.tabs(["Item lookup", "Audit"])

# ===== Tab 1: Item lookup =====
with tab_lookup:
    col1, col2, col3 = st.columns([2, 1, 1])

    with col1:
        user_input = st.text_input(
            "Enter LD Number",
            max_chars=8,
            placeholder="L1304179 or 1304179",
            key="lookup_input",
        )
    with col2:
        find_clicked = st.button("Find", type="primary", key="lookup_find_btn")
    with col3:
        st.button("Clear", type="secondary", key="lookup_clear_btn",
                  on_click=clear_lookup_callback)

    lnums: List[str] = []
    fixed: List[str] = []
    if find_clicked and st.session_state["lookup_input"].strip():
        found, corrected = extract_lnumbers_from_text_with_correction(
            st.session_state["lookup_input"].strip()
        )
        if found:
            lnums = [found[0]]  # single check
            fixed = corrected
        else:
            st.warning("No valid LD number found.")

    if lnums:
        if lnums[0] in fixed:
            st.markdown(
                f"<div class='muted'>Corrected → <span class='chip fixed'>{lnums[0]}</span></div>",
                unsafe_allow_html=True,
            )
        else:
            st.markdown(
                f"<div class='muted'>Detected → <span class='chip'>{lnums[0]}</span></div>",
                unsafe_allow_html=True,
            )
        render_table(lnums)

# ===== Tab 2: Audit (camera + one text area) =====
with tab_audit:
    st.caption("Take a picture of a list and/or paste free text. I’ll normalize 7-digit numbers to Lxxxxxxx. Edit before running.")
    c1, c2 = st.columns([1.1, 1])

    with c1:
        camera_img = st.camera_input("Take a picture of a list (optional)")

    with c2:
        combined_text = st.text_area(
            "Paste/edit L-numbers (any separators). I’ll try to also read from the camera photo if provided.",
            height=220,
            key="audit_combined_text",
        )

    # Collect text: camera OCR + typed/pasted
    raw_text_parts: List[str] = []
    if combined_text.strip():
        raw_text_parts.append(combined_text)

    if camera_img is not None:
        txt = _ocrspace_bytes(camera_img.getvalue())
        if txt:
            raw_text_parts.append(txt)

    all_text = "\n".join(raw_text_parts)
    lnums_bulk: List[str] = []
    fixed_bulk: List[str] = []

    if all_text.strip():
        extracted, corrected = extract_lnumbers_from_text_with_correction(all_text)
        lnums_bulk = extracted
        fixed_bulk = corrected

    # Prefill single field (if user didn't type yet)
    detected_default = " ".join(lnums_bulk) if not combined_text.strip() else combined_text
    edited_text = st.text_area(
        "Edit the final list here, then run:",
        value=detected_default,
        height=120,
        key="audit_final_list"
    )

    if fixed_bulk:
        chips = "".join([f"<span class='chip fixed'>{x}</span>" for x in fixed_bulk])
        st.markdown(f"<div class='muted'>Auto-corrected from 7 digits → {chips}</div>", unsafe_allow_html=True)

    run_audit = st.button("Run Audit", type="primary")
    if run_audit:
        final_list, _ = extract_lnumbers_from_text_with_correction(edited_text)
        if not final_list:
            st.warning("No L-numbers to process after edits.")
        else:
            render_table(final_list)

