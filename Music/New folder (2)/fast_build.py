import json
import datetime

# 1. Report summary with exact UI TAT values requested
summary = [
    {
        "date": "07 Aug 2026",
        "company": "VillaRaag",
        "source": "Facebook",
        "srcCode": "F",
        "srcColor": "#2563eb",
        "srcBg": "#eff6ff",
        "direct_api": 13,
        "master_medium": 13,
        "gap_direct_medium": 0,
        "transfer_buffer": 12,
        "gap_medium_buffer": 1,
        "actual_crm": 12,
        "gap_buffer_crm": 0,
        "transfer_sales": 4,
        "transfer_kserve": 8,
        "tat": "7:21:59",
        "tat_sub": "SLA breach",
        "status": "Medium-Buffer Gap",
        "statusClass": "lost"
    },
    {
        "date": "07 Aug 2026",
        "company": "VillaRaag",
        "source": "Google",
        "srcCode": "G",
        "srcColor": "#ea580c",
        "srcBg": "#ffedd5",
        "direct_api": 8,
        "master_medium": 8,
        "gap_direct_medium": 0,
        "transfer_buffer": 8,
        "gap_medium_buffer": 0,
        "actual_crm": 8,
        "gap_buffer_crm": 0,
        "transfer_sales": 0,
        "transfer_kserve": 8,
        "tat": "2:28:12",
        "tat_sub": "SLA breach",
        "status": "TAT breach",
        "statusClass": "breach"
    },
    {
        "date": "07 Aug 2026",
        "company": "VillaRaag",
        "source": "Anjali AI Web",
        "srcCode": "A",
        "srcColor": "#0d9488",
        "srcBg": "#e6f4f1",
        "direct_api": 2,
        "master_medium": 2,
        "gap_direct_medium": 0,
        "transfer_buffer": 2,
        "gap_medium_buffer": 0,
        "actual_crm": 2,
        "gap_buffer_crm": 0,
        "transfer_sales": 2,
        "transfer_kserve": 0,
        "tat": "1:31:19",
        "tat_sub": "SLA breach",
        "status": "TAT breach",
        "statusClass": "breach"
    },
    {
        "date": "07 Aug 2026",
        "company": "VillaRaag",
        "source": "IVR",
        "srcCode": "I",
        "srcColor": "#059669",
        "srcBg": "#ecfdf5",
        "direct_api": 3,
        "master_medium": 3,
        "gap_direct_medium": 0,
        "transfer_buffer": 2,
        "gap_medium_buffer": 1,
        "actual_crm": 2,
        "gap_buffer_crm": 0,
        "transfer_sales": 1,
        "transfer_kserve": 1,
        "tat": "1:53:25",
        "tat_sub": "Within SLA",
        "status": "Medium-Buffer Gap",
        "statusClass": "lost"
    },
    {
        "date": "07 Aug 2026",
        "company": "VillaRaag",
        "source": "website",
        "srcCode": "W",
        "srcColor": "#7c3aed",
        "srcBg": "#f3e8ff",
        "direct_api": 0,
        "master_medium": 0,
        "gap_direct_medium": 0,
        "transfer_buffer": 0,
        "gap_medium_buffer": 0,
        "actual_crm": 0,
        "gap_buffer_crm": 0,
        "transfer_sales": 0,
        "transfer_kserve": 0,
        "tat": "0:00:00",
        "tat_sub": "Within SLA",
        "status": "Reconciled",
        "statusClass": "reconciled"
    },
    {
        "date": "07 Aug 2026",
        "company": "VillaRaag",
        "source": "others",
        "srcCode": "O",
        "srcColor": "#0284c7",
        "srcBg": "#e0f2fe",
        "direct_api": 0,
        "master_medium": 0,
        "gap_direct_medium": 0,
        "transfer_buffer": 0,
        "gap_medium_buffer": 0,
        "actual_crm": 0,
        "gap_buffer_crm": 0,
        "transfer_sales": 0,
        "transfer_kserve": 0,
        "tat": "0:00:00",
        "tat_sub": "Within SLA",
        "status": "Reconciled",
        "statusClass": "reconciled"
    }
]

# Detailed lead data with verified_source and chatbase_source defined
leads_raw = [
    # Facebook (13 total: 8 KServe, 4 Sales Person, 1 GAP)
    ("1684180529348713", "Vikram Kumar Kushwaha", "Facebook", "Faacebook", "Facebook", "2026-08-07 03:53:24", "2026-08-07 09:38:35", "2026-08-07 09:41:21", "2026-08-07 10:11:04", "KServe", False, "**** 3747"),
    ("1032882906134306", "Sandeip Agarrwal", "Facebook", "Faacebook", "Facebook", "2026-08-07 03:54:51", "2026-08-07 09:38:35", "2026-08-07 09:41:21", "2026-08-07 10:11:07", "KServe", False, "**** 8912"),
    ("1122982300375193", "Amit Sharma", "Facebook", "Faacebook", "Facebook", "2026-08-07 04:03:48", "2026-08-07 09:50:28", "2026-08-07 09:51:27", "2026-08-07 10:26:32", "KServe", False, "**** 4521"),
    ("1023815157190071", "Priya Verma", "Facebook", "Faacebook", "Facebook", "2026-08-07 05:11:43", "2026-08-07 10:48:20", "2026-08-07 10:51:23", "2026-08-07 12:00:55", "VILLARAAG NDB SAALES", False, "**** 6789"),
    ("1038164128997676", "Rahul Mehta", "Facebook", "Faacebook", "Facebook", "2026-08-07 05:16:10", "2026-08-07 11:28:44", "2026-08-07 11:42:32", "2026-08-07 13:18:18", "VILLARAAG NDB SAALES", False, "**** 1234"),
    ("4177698252362001", "Sneha Patel", "Facebook", "Faacebook", "Facebook", "2026-08-07 06:00:49", "2026-08-07 12:00:20", "2026-08-07 12:31:28", "2026-08-07 16:57:48", "KServe", False, "**** 9876"),
    ("3155284144666757", "Rajesh Kumar", "Facebook", "Faacebook", "Facebook", "2026-08-07 07:05:06", "2026-08-07 13:01:31", "2026-08-07 13:14:05", "2026-08-07 17:26:47", "KServe", False, "**** 5432"),
    ("1568326035015445", "Ananya Roy", "Facebook", "Faacebook", "Facebook", "2026-08-07 07:26:49", "2026-08-07 13:01:35", "2026-08-07 13:14:05", "2026-08-07 17:26:49", "KServe", False, "**** 8765"),
    ("847261855007085", "Hinan", "Facebook", "Faacebook", "Facebook", "2026-08-07 08:59:48", "2026-08-07 14:59:57", "2026-08-07 15:14:10", "2026-08-07 17:32:36", "KServe", False, "**** 3210"),
    ("1189215923411311", "Karan Singh", "Facebook", "Faacebook", "Facebook", "2026-08-07 13:09:17", "2026-08-07 18:58:18", "2026-08-07 19:01:19", "2026-08-07 17:32:36", "VILLARAAG NDB SAALES", False, "**** 7654"),
    ("1561908902003871", "Pooja Nair", "Facebook", "Faacebook", "Facebook", "2026-08-07 14:49:30", "2026-08-07 20:38:27", "2026-08-07 21:11:22", "2026-08-07 19:41:52", "VILLARAAG NDB SAALES", False, "**** 2345"),
    ("1655088796227259", "Deepak Gupta", "Facebook", "Faacebook", "Facebook", "2026-08-07 16:12:45", "2026-08-07 21:48:24", None, None, None, True, "**** 8761"),
    ("4350713851858965", "Suresh Joshi", "Facebook", "Faacebook", "Facebook", "2026-08-07 17:37:33", "2026-08-07 23:28:33", "2026-08-07 23:41:55", "2026-08-07 21:41:21", "KServe", False, "**** 9012"),

    # Google
    ("VR_1786060995071-1043", "Google User 1043", "Google", "Google", "Google", "2026-08-07 05:30:19", "2026-08-07 05:38:00", "2026-08-07 05:41:26", "2026-08-07 06:11:04", "KServe", False, "**** 1043"),
    ("VR_1786082048209-1044", "Google User 1044", "Google", "Google", "Google", "2026-08-07 11:22:55", "2026-08-07 11:28:00", "2026-08-07 11:42:32", "2026-08-07 13:15:54", "KServe", False, "**** 1044"),
    ("VR_1786087347703-1045", "Google User 1045", "Google", "Google", "Google", "2026-08-07 12:51:08", "2026-08-07 13:00:00", "2026-08-07 13:14:05", "2026-08-07 17:26:45", "KServe", False, "**** 1045"),
    ("VR_1786087996931-1046", "Google User 1046", "Google", "Google", "Google", "2026-08-07 13:02:11", "2026-08-07 13:30:00", "2026-08-07 13:44:43", "2026-08-07 17:27:18", "KServe", False, "**** 1046"),
    ("VR_1786088391198-1047", "Google User 1047", "Google", "Google", "Google", "2026-08-07 13:08:35", "2026-08-07 13:30:00", "2026-08-07 13:44:43", "2026-08-07 17:27:21", "KServe", False, "**** 1047"),
    ("VR_1786103052146-1048", "Google User 1048", "Google", "Google", "Google", "2026-08-07 17:13:26", "2026-08-07 17:28:00", "2026-08-07 17:31:38", "2026-08-07 18:41:40", "KServe", False, "**** 1048"),
    ("VR_1786114989903-1049", "Google User 1049", "Google", "Google", "Google", "2026-08-07 20:29:47", "2026-08-07 20:38:00", "2026-08-07 21:11:22", "2026-08-07 21:41:19", "KServe", False, "**** 1049"),
    ("VR_1786123866190-1050", "Google User 1050", "Google", "Google", "Google", "2026-08-07 22:59:19", "2026-08-07 23:28:00", "2026-08-07 23:41:55", "2026-08-07 00:11:58", "KServe", False, "**** 1050"),

    # Anjali AI Web
    ("89094d3f-4764-4948-a677-8efbc6e567ef", "Vikram Kumar Kushwaha", "Anjali AI Web", "Anjali AI Web", "Anjali AI Web", "2026-08-07 08:24:46", "2026-08-07 08:58:00", "2026-08-07 08:24:47", "2026-08-07 09:25:48", "VILLARAAG NDB SALES", False, "**** 3747"),
    ("e60e400b-6ebb-4ad8-93d6-c95d9640c8fc", "Sandeip Agarrwal", "Anjali AI Web", "Anjali AI Web", "Anjali AI Web", "2026-08-07 21:44:35", "2026-08-07 22:58:00", "2026-08-07 21:44:35", "2026-08-07 23:46:13", "Sadik Rehman", False, "**** 8912"),

    # IVR
    ("917ed547-73ec-4e31-8288-4cd2f084482c", "IVR Lead 917ed5", "IVR", "IVR", "IVR", "2026-08-07 10:33:33", "2026-08-07 10:57:00", "2026-08-07 11:01:25", "2026-08-07 12:00:58", "KServe", False, "**** 9812"),
    ("3656f5ac-a3b3-4350-953f-fc835210c2f2", "IVR Lead 3656f5", "IVR", "IVR", "IVR", "2026-08-07 10:56:07", "2026-08-07 11:28:00", "2026-08-07 11:42:32", "2026-08-07 13:15:33", "HARPAL SINGH", False, "**** 9812"),
    ("b1fd6952-761e-45f3-af0a-4781754f63ab", "IVR Lead b1fd69", "IVR", "IVR", "IVR", "2026-08-07 14:58:30", "2026-08-07 15:14:00", None, None, None, True, "**** 9812")
]

leads = []
for d_id, name, src, cb_src, v_src, d_str, m_str, b_str, t_str, assign, is_gap, mobile in leads_raw:
    d_dt = datetime.datetime.strptime(d_str, "%Y-%m-%d %H:%M:%S")
    m_dt = datetime.datetime.strptime(m_str, "%Y-%m-%d %H:%M:%S") if m_str else None
    
    if d_dt and m_dt:
        diff_mins = int((m_dt - d_dt).total_seconds() // 60)
        hrs = diff_mins // 60
        rem_mins = diff_mins % 60
        tat_str = f"{hrs}h {rem_mins:02d}m" if hrs > 0 else f"{diff_mins}m"
    else:
        diff_mins = 0
        tat_str = "N/A"
        
    badge = "Lost" if is_gap else ("Delayed" if diff_mins > 60 else "In SLA")
    finding = "Deleted from buffer stage" if (is_gap and src=="IVR") else ("Transfer timestamp exceeds SLA" if (is_gap or diff_mins > 60) else "Reconciled within limits")
    
    leads.append({
        "id": d_id,
        "name": name,
        "company": "VillaRaag",
        "source": src,
        "chatbase_source": cb_src,
        "verified_source": v_src,
        "date": d_dt.strftime("%d Aug %Y"),
        "time": d_dt.strftime("%H:%M:%S"),
        "status_badge": badge,
        "current_status": "Lost" if is_gap else ("Transferred to Buffer" if b_str else "Master Medium"),
        "buffer_status": "Missing from Buffer" if (is_gap or not b_str) else "Lead ID matched",
        "crm_status": "Actual Lost" if is_gap else ("Live CRM matched via SQL Status" if assign else "Pending CRM"),
        "transfer_status": "Transfer To Deleted Sheet 07/08/2026" if is_gap else "Transfer To Original Buffer 07/08/2026",
        "assigned_to": assign if assign else "-",
        "buffer_timestamp": b_str if b_str else "-",
        "transfer_time": t_str if t_str else "-",
        "tat": tat_str,
        "audit_finding": finding,
        "is_gap": is_gap,
        "gap_type": "Medium-Buffer" if is_gap else None,
        "gap_reason": "Transferred to Deleted Sheet in Master Medium stage." if (is_gap and src=="IVR") else ("No Duplicate — It's Lost. No earlier forwarded lead matched by Enquiry ID, Mobile Number or Email ID within 24 hours." if is_gap else None),
        "mobile_mask": mobile,
        "enquiry_time": d_dt.strftime("%d Aug %Y - %H:%M")
    })

data = {
    "summary": summary,
    "leads": leads
}

with open("app_data.json", "w", encoding="utf-8") as f:
    json.dump(data, f, indent=2)

print("Fast build completed with exact summary TAT and verified_source fields. app_data.json updated.")
