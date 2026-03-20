from fpdf import FPDF

if __package__:
    from .config import CHALLANS_DIR, ensure_app_dirs
else:
    from config import CHALLANS_DIR, ensure_app_dirs

def generate_challan(session_id, operator_id, batch_id, timestamp, final_count):
    ensure_app_dirs()
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", size=16)
    pdf.cell(200, 10, txt="NexusTrace Challan", ln=True, align='C')
    pdf.ln(10)
    pdf.set_font("Arial", size=12)
    pdf.cell(200, 10, txt=f"Session ID: {session_id}", ln=True)
    pdf.cell(200, 10, txt=f"Operator ID: {operator_id}", ln=True)
    pdf.cell(200, 10, txt=f"Batch ID: {batch_id}", ln=True)
    pdf.cell(200, 10, txt=f"Timestamp: {timestamp}", ln=True)
    pdf.cell(200, 10, txt=f"Final Box Count: {final_count}", ln=True)
    path = CHALLANS_DIR / f"challan_{session_id}.pdf"
    pdf.output(str(path))
    return str(path)
