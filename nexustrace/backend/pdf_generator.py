from datetime import datetime
from pathlib import Path

from fpdf import FPDF

if __package__:
    from .config import (
        CHALLANS_DIR,
        COMPANY_ADDRESS,
        COMPANY_CONTACT,
        COMPANY_GST_ID,
        COMPANY_LOGO_PATH,
        COMPANY_NAME,
        ensure_app_dirs,
    )
else:
    from config import (
        CHALLANS_DIR,
        COMPANY_ADDRESS,
        COMPANY_CONTACT,
        COMPANY_GST_ID,
        COMPANY_LOGO_PATH,
        COMPANY_NAME,
        ensure_app_dirs,
    )


class ChallanPDF(FPDF):
    def __init__(self, company_profile=None):
        super().__init__()
        self.company_profile = company_profile or {}

    def header(self):  # noqa: D401 - fpdf callback signature
        self.set_fill_color(24, 42, 74)
        self.rect(0, 0, 210, 30, "F")

        logo_path = str(self.company_profile.get("logo_path") or "").strip()
        if logo_path:
            try:
                self.image(logo_path, x=12, y=6, w=16)
            except Exception:
                pass

        self.set_xy(30, 8)
        self.set_text_color(255, 255, 255)
        self.set_font("Helvetica", "B", 14)
        self.cell(120, 7, str(self.company_profile.get("name") or COMPANY_NAME), ln=True)
        self.set_x(30)
        self.set_font("Helvetica", "", 9)
        self.cell(140, 5, str(self.company_profile.get("address") or COMPANY_ADDRESS), ln=True)
        self.set_x(30)
        self.cell(
            140,
            5,
            f"{str(self.company_profile.get('contact') or COMPANY_CONTACT)} | {str(self.company_profile.get('gst_id') or COMPANY_GST_ID)}",
            ln=True,
        )

        self.set_xy(160, 9)
        self.set_font("Helvetica", "B", 13)
        self.cell(40, 8, "INVOICE", align="R")
        self.ln(17)
        self.set_text_color(0, 0, 0)

    def footer(self):
        self.set_y(-15)
        self.set_font("Helvetica", "I", 9)
        self.set_text_color(90, 90, 90)
        self.cell(0, 8, f"System Generated Document | Page {self.page_no()}", align="C")


def _normalize_product_rows(product_rows, final_count):
    rows = []
    for row in product_rows or []:
        name = str(row.get("product_name") or "").strip()
        if not name:
            continue
        rows.append(
            {
                "product_name": name,
                "count": int(row.get("count") or 0),
            }
        )
    if rows:
        return rows
    return [{"product_name": "All Products", "count": int(final_count or 0)}]


def _filter_rows(product_rows, selected_products):
    if not selected_products:
        return product_rows
    selected = {str(item or "").strip().lower() for item in selected_products if str(item or "").strip()}
    if not selected:
        return product_rows
    return [row for row in product_rows if row["product_name"].strip().lower() in selected]


def _safe_value(value, default="-"):
    text = str(value or "").strip()
    return text if text else default


def _invoice_id_for_session(session_id):
    stamp = datetime.utcnow().strftime("%Y%m%d%H%M%S")
    return f"INV-{session_id}-{stamp}"


def _draw_section_title(pdf: FPDF, title: str):
    pdf.set_fill_color(235, 240, 250)
    pdf.set_font("Helvetica", "B", 10)
    pdf.cell(0, 8, title, border=1, ln=True, fill=True)


def generate_challan(
    session_id,
    operator_id,
    batch_id,
    timestamp,
    final_count,
    product_rows=None,
    video_path=None,
    selected_products=None,
    output_basename=None,
    video_reference_url=None,
    video_file_name=None,
    invoice_id=None,
    transaction_ref=None,
    company_profile=None,
):
    ensure_app_dirs()

    rows = _normalize_product_rows(product_rows, final_count)
    rows = _filter_rows(rows, selected_products)
    if not rows:
        raise ValueError("No matching products found for challan generation.")

    total_count = sum(int(row["count"]) for row in rows)
    generated_at = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")
    invoice_number = invoice_id or _invoice_id_for_session(session_id)
    payment_ref = _safe_value(transaction_ref, "N/A")

    merged_company_profile = {
        "name": COMPANY_NAME,
        "address": COMPANY_ADDRESS,
        "contact": COMPANY_CONTACT,
        "gst_id": COMPANY_GST_ID,
        "logo_path": COMPANY_LOGO_PATH,
    }
    if isinstance(company_profile, dict):
        merged_company_profile.update(company_profile)

    pdf = ChallanPDF(company_profile=merged_company_profile)
    pdf.set_auto_page_break(auto=True, margin=18)
    pdf.add_page()
    pdf.set_font("Helvetica", "", 10)
    pdf.ln(4)

    pdf.set_font("Helvetica", "B", 10)
    pdf.cell(90, 8, "Customer Detail", border=1)
    pdf.cell(40, 8, "Challan No.", border=1)
    pdf.set_font("Helvetica", "", 10)
    pdf.cell(60, 8, str(session_id).zfill(9), border=1, ln=True)

    pdf.set_font("Helvetica", "", 10)
    pdf.cell(90, 8, "M/S", border=1)
    pdf.cell(40, 8, "Pickup Date", border=1)
    try:
        dt = datetime.fromisoformat(str(timestamp).replace("Z", "+00:00"))
        pickup_date = dt.strftime("%d/%m/%Y")
    except Exception:
        pickup_date = str(timestamp)[:10] if timestamp else datetime.utcnow().strftime("%d/%m/%Y")
    pdf.cell(60, 8, pickup_date, border=1, ln=True)

    pdf.cell(90, 8, "Transporter ID", border=1)
    pdf.cell(40, 8, "Lot No.", border=1)
    pdf.cell(60, 8, _safe_value(batch_id, "10"), border=1, ln=True)

    pdf.cell(90, 8, "Courier Partner", border=1)
    pdf.cell(40, 8, "No. of Boxes", border=1)
    pdf.cell(60, 8, str(total_count), border=1, ln=True)

    pdf.ln(5)

    pdf.set_fill_color(240, 240, 240)
    pdf.set_font("Helvetica", "B", 10)
    pdf.cell(20, 9, "Sr. No.", border=1, fill=True)
    pdf.cell(90, 9, "Name of Product", border=1, fill=True)
    pdf.cell(30, 9, "Qty", border=1, fill=True)
    pdf.cell(50, 9, "", border=1, ln=True, fill=True)

    pdf.set_font("Helvetica", "", 10)
    for idx, row in enumerate(rows, start=1):
        pdf.cell(20, 8, f"{idx}.", border=1)
        pdf.cell(90, 8, row["product_name"], border=1)
        pdf.cell(30, 8, str(int(row["count"])), border=1)
        pdf.cell(50, 8, "", border=1, ln=True)

    pdf.set_font("Helvetica", "B", 10)
    pdf.cell(20, 8, "", border=1)
    pdf.cell(90, 8, "Total", border=1)
    pdf.cell(30, 8, str(total_count), border=1)
    pdf.cell(50, 8, "", border=1, ln=True)

    pdf.ln(10)
    if video_reference_url:
        pdf.set_font("Helvetica", "I", 8)
        pdf.set_text_color(0, 0, 255)
        pdf.cell(0, 6, f"Video Evidence: {video_reference_url}", ln=True, link=video_reference_url)
        pdf.set_text_color(0, 0, 0)
        pdf.ln(2)

    pdf.set_font("Helvetica", "I", 9)
    pdf.multi_cell(0, 6, "System Generated Document. Signature: __________________________")

    if output_basename:
        file_name = output_basename
    elif selected_products:
        token = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        file_name = f"challan_{session_id}_{token}.pdf"
    else:
        file_name = f"challan_{session_id}.pdf"

    path = CHALLANS_DIR / file_name
    pdf.output(str(path))
    return str(path)


def generate_multi_session_challan(
    sessions,
    output_basename=None,
    company_profile=None,
):
    ensure_app_dirs()
    if not sessions:
        raise ValueError("No sessions provided for multi-challan generation.")

    # Calculate aggregate total box count
    total_count = sum(int(s[4] if isinstance(s, tuple) else s.get("final_count") or 0) for s in sessions)
    from datetime import datetime
    generated_at = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")

    if __package__:
        from .config import COMPANY_NAME, COMPANY_ADDRESS, COMPANY_CONTACT, COMPANY_GST_ID, COMPANY_LOGO_PATH, CHALLANS_DIR
    else:
        from config import COMPANY_NAME, COMPANY_ADDRESS, COMPANY_CONTACT, COMPANY_GST_ID, COMPANY_LOGO_PATH, CHALLANS_DIR

    merged_company_profile = {
        "name": COMPANY_NAME,
        "address": COMPANY_ADDRESS,
        "contact": COMPANY_CONTACT,
        "gst_id": COMPANY_GST_ID,
        "logo_path": COMPANY_LOGO_PATH,
    }
    if isinstance(company_profile, dict):
        merged_company_profile.update(company_profile)

    pdf = ChallanPDF(company_profile=merged_company_profile)
    pdf.set_auto_page_break(auto=True, margin=18)
    pdf.add_page()
    
    # Title Section
    pdf.set_font("Helvetica", "B", 14)
    pdf.set_text_color(24, 42, 74)
    pdf.cell(0, 10, "Multi-Session Summary Report", ln=True, align="C")
    pdf.set_font("Helvetica", "I", 9)
    pdf.set_text_color(100, 100, 100)
    pdf.cell(0, 6, f"Generated at: {generated_at}", ln=True, align="C")
    pdf.ln(8)

    # Table Header
    pdf.set_text_color(0, 0, 0)
    pdf.set_fill_color(240, 240, 240)
    pdf.set_font("Helvetica", "B", 10)
    pdf.cell(25, 9, "Session ID", border=1, fill=True)
    pdf.cell(35, 9, "Operator", border=1, fill=True)
    pdf.cell(40, 9, "Batch ID", border=1, fill=True)
    pdf.cell(55, 9, "Timestamp", border=1, fill=True)
    pdf.cell(35, 9, "Count", border=1, fill=True, ln=True)

    # Table Body
    pdf.set_font("Helvetica", "", 10)
    for s in sessions:
        # Handle tuple (from database) or dict (from API)
        if isinstance(s, tuple):
            sid, ts, op, batch, count = s[0], s[1], s[2], s[3], s[4]
        else:
            sid, ts, op, batch, count = s.get("id"), s.get("timestamp"), s.get("operator_id"), s.get("batch_id"), s.get("final_count")
            
        pdf.cell(25, 8, f"#{sid}", border=1)
        pdf.cell(35, 8, _safe_value(op, "N/A"), border=1)
        pdf.cell(40, 8, _safe_value(batch, "N/A"), border=1)
        
        try:
            ts_str = str(ts or "")
            dt = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
            ts_display = dt.strftime("%d/%m/%y %H:%M")
        except Exception:
            ts_display = str(ts or "N/A")[:16]
            
        pdf.cell(55, 8, ts_display, border=1)
        pdf.cell(35, 8, str(count or 0), border=1, ln=True, align="C")

    # Grand Total Footer
    pdf.set_font("Helvetica", "B", 11)
    pdf.cell(155, 10, "GRAND TOTAL", border=1, align="R")
    pdf.cell(35, 10, str(total_count), border=1, ln=True, align="C")

    pdf.ln(10)
    pdf.set_font("Helvetica", "I", 9)
    pdf.multi_cell(0, 6, "System Generated Consolidated Report. This document summarizes multiple operational inspection records for auditing purposes.")

    file_name = output_basename or f"multi_challan_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.pdf"
    path = CHALLANS_DIR / file_name
    pdf.output(str(path))
    return str(path)
