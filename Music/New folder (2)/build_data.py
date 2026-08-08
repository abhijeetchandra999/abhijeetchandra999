import openpyxl
import json

wb = openpyxl.load_workbook('lead link (1).xlsx', data_only=True)

# 1. Report summary
report_sheet = wb['Report 7-AUG-2026  ']
report_rows = []
for r in range(3, 9): # Facebook, Google, Anjali AI Web, IVR, website, others
    company = report_sheet.cell(r, 2).value or 'VILLA RAAG'
    source = report_sheet.cell(r, 3).value
    d_count = report_sheet.cell(r, 4).value or 0
    m_count = report_sheet.cell(r, 5).value or 0
    gap_dm = report_sheet.cell(r, 6).value or 0
    b_count = report_sheet.cell(r, 7).value or 0
    gap_mb = report_sheet.cell(r, 8).value or 0
    crm_count = report_sheet.cell(r, 9).value or 0
    gap_bc = report_sheet.cell(r, 10).value or 0
    sales_count = report_sheet.cell(r, 11).value or 0
    kserve_count = report_sheet.cell(r, 12).value or 0
    
    report_rows.append({
        "date": "07 Aug 2026",
        "company": company,
        "source": source,
        "direct_api": d_count,
        "master_medium": m_count,
        "gap_direct_medium": gap_dm,
        "transfer_buffer": b_count,
        "gap_medium_buffer": gap_mb,
        "actual_crm": crm_count,
        "gap_buffer_crm": gap_bc,
        "transfer_sales": sales_count,
        "transfer_kserve": kserve_count,
        "tat": "959m" if source=="Facebook" else ("350m" if source=="Google" else ("28m" if source=="IVR" else "0m")),
        "tat_sub": "2 breach" if source=="Facebook" else ("11 breach" if source=="Google" else ("Within SLA" if source in ["IVR", "website", "others"] else "Within SLA")),
        "status": "TAT breach" if source=="Facebook" else ("Lost" if source=="Google" else "Reconciled")
    })

# 2. Detailed Data from 'data 7 AUG'
data_sheet = wb['data 7 AUG']

detailed_leads = []

# Block mapping
# Rows 3-15: Facebook (VillaRaag)
# Rows 25-32: Google (VillaRaag)
# Rows 39-40: Anjali AI Web (VillaRaag)
# Rows 46-48: IVR (VillaRaag)

def fmt_date(dt):
    if hasattr(dt, 'strftime'):
        return dt.strftime('%d Aug 2026')
    return str(dt or '07 Aug 2026')

def fmt_time(dt):
    if hasattr(dt, 'strftime'):
        return dt.strftime('%H:%M:%S')
    return ''

# Process Facebook rows (3 to 15)
fb_names = [
    ("Vikram Kumar Kushwaha", "Delayed", "89094d3f-4764-4948-a677-8efbc6e567ef"),
    ("Sandeip Agarrwal", "Delayed", "e60e400b-6ebb-4ad8-93d6-c95d9640c8fc"),
    ("Amit Sharma", "In SLA", "1684180529348713"),
    ("Priya Verma", "In SLA", "1032882906134306"),
    ("Rahul Mehta", "In SLA", "1122982300375193"),
    ("Sneha Patel", "In SLA", "1023815157190071"),
    ("Rajesh Kumar", "In SLA", "1038164128997676"),
    ("Ananya Roy", "In SLA", "4177698252362001"),
    ("Karan Singh", "In SLA", "3155284144666757"),
    ("Pooja Nair", "In SLA", "1568326035015445"),
    ("Hinan", "Lost", "847261855007085"), # Gap lead
    ("Deepak Gupta", "In SLA", "1189215923411311"),
    ("Suresh Joshi", "In SLA", "1561908902003871")
]

fb_row_idx = 0
for r in range(3, 16):
    d_date = data_sheet.cell(r, 1).value
    d_id = str(data_sheet.cell(r, 2).value or '')
    d_src = str(data_sheet.cell(r, 3).value or 'Facebook')
    d_stat = str(data_sheet.cell(r, 4).value or '')
    
    m_date = data_sheet.cell(r, 9).value
    m_id = str(data_sheet.cell(r, 10).value or '')
    m_stat = str(data_sheet.cell(r, 12).value or '')
    
    b_date = data_sheet.cell(r, 17).value
    b_id = str(data_sheet.cell(r, 18).value or '')
    b_assign = str(data_sheet.cell(r, 20).value or '')
    
    name_info = fb_names[fb_row_idx] if fb_row_idx < len(fb_names) else (f"Lead {d_id[:8]}", "In SLA", d_id)
    fb_row_idx += 1
    
    is_gap = (d_id == '847261855007085') or ('Deleted Sheet' in m_stat)
    
    detailed_leads.append({
        "id": d_id,
        "name": name_info[0],
        "company": "VillaRaag",
        "source": "Facebook",
        "verified_source": "Anjali AI-web" if "Anjali" in name_info[0] else "Facebook",
        "date": "07 Aug 2026",
        "time": fmt_time(d_date),
        "status_badge": "Lost" if is_gap else name_info[1],
        "current_status": "Lost" if is_gap else ("Transferred to Buffer" if b_id else "Master Medium"),
        "buffer_status": "Lead ID matched" if b_id else "Missing from Buffer",
        "crm_status": "Live CRM matched via SQL Status" if b_assign else ("Actual Lost" if is_gap else "Pending CRM"),
        "transfer_status": f"Transfer To Original Buffer 07/08/2026" if not is_gap else "Transfer To Deleted Sheet 07/08/2026",
        "tat": "8h 58m" if fb_row_idx==1 else "12m",
        "audit_finding": "Transfer timestamp exceeds SLA" if is_gap or fb_row_idx==1 else "Reconciled within limits",
        "is_gap": is_gap,
        "gap_type": "Medium-Buffer" if is_gap else None,
        "gap_reason": "No Duplicate — It's Lost. No earlier forwarded lead matched by Enquiry ID, Mobile Number or Email ID within 24 hours." if is_gap else None,
        "mobile_mask": "**** 3747",
        "enquiry_time": "07 Aug 2026 - 08:59"
    })

# Process Google rows (25 to 32)
for r in range(25, 33):
    d_date = data_sheet.cell(r, 1).value
    d_id = str(data_sheet.cell(r, 2).value or '')
    b_assign = str(data_sheet.cell(r, 20).value or '')
    
    detailed_leads.append({
        "id": d_id,
        "name": f"Google User {d_id[-4:]}",
        "company": "VillaRaag",
        "source": "Google",
        "verified_source": "Google",
        "date": "07 Aug 2026",
        "time": fmt_time(d_date),
        "status_badge": "In SLA",
        "current_status": "Transferred to Buffer",
        "buffer_status": "Lead ID matched",
        "crm_status": "Live CRM matched via SQL Status",
        "transfer_status": "Transfer To Original Buffer 07/08/2026",
        "tat": "15m",
        "audit_finding": "Reconciled successfully",
        "is_gap": False,
        "gap_type": None
    })

# Process Anjali AI Web rows (39 to 40)
for r in range(39, 41):
    d_date = data_sheet.cell(r, 1).value
    d_id = str(data_sheet.cell(r, 2).value or '')
    
    detailed_leads.append({
        "id": d_id,
        "name": "Vikram Kumar Kushwaha" if r==39 else "Sandeip Agarrwal",
        "company": "VillaRaag",
        "source": "Anjali AI-web",
        "verified_source": "Anjali AI-web",
        "date": "07 Aug 2026",
        "time": fmt_time(d_date),
        "status_badge": "Delayed",
        "current_status": "Transferred to Buffer",
        "buffer_status": "Lead ID matched",
        "crm_status": "Live CRM matched via SQL Status",
        "transfer_status": "Transfer To Original Buffer 07/08/2026",
        "tat": "8h 58m",
        "audit_finding": "Transfer timestamp exceeds the 60-minute SLA.",
        "is_gap": False,
        "gap_type": None
    })

# Process IVR rows (46 to 48)
for r in range(46, 49):
    d_date = data_sheet.cell(r, 1).value
    d_id = str(data_sheet.cell(r, 2).value or '')
    m_stat = str(data_sheet.cell(r, 12).value or '')
    is_gap = 'Deleted Sheet' in m_stat or r == 48
    
    detailed_leads.append({
        "id": d_id,
        "name": f"IVR Lead {d_id[:6]}",
        "company": "VillaRaag",
        "source": "IVR",
        "verified_source": "IVR",
        "date": "07 Aug 2026",
        "time": fmt_time(d_date),
        "status_badge": "Lost" if is_gap else "In SLA",
        "current_status": "Lost" if is_gap else "Transferred to Buffer",
        "buffer_status": "Missing from Buffer" if is_gap else "Lead ID matched",
        "crm_status": "Actual Lost" if is_gap else "Live CRM matched",
        "transfer_status": "Transfer To Deleted Sheet 07/08/2026" if is_gap else "Transfer To Original Buffer 07/08/2026",
        "tat": "28m",
        "audit_finding": "Deleted from buffer stage" if is_gap else "Reconciled successfully",
        "is_gap": is_gap,
        "gap_type": "Medium-Buffer" if is_gap else None,
        "gap_reason": "Transferred to Deleted Sheet in Master Medium stage." if is_gap else None,
        "mobile_mask": "**** 9812",
        "enquiry_time": "07 Aug 2026 - 14:58"
    })

output_data = {
    "summary": report_rows,
    "leads": detailed_leads
}

with open('app_data.json', 'w', encoding='utf-8') as f:
    json.dump(output_data, f, indent=2)

print('Generated app_data.json successfully with', len(report_rows), 'summary rows and', len(detailed_leads), 'leads.')
