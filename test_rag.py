import os
import requests
import time
import subprocess
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors

API_URL = "http://localhost:8000"

def create_mock_pdf(filename="ktu_activity_points.pdf"):
    """
    Generates a structured PDF with a table representing KTU Activity Point guidelines.
    """
    doc = SimpleDocTemplate(filename, pagesize=letter)
    story = []
    
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        'TitleStyle',
        parent=styles['Heading1'],
        fontName='Helvetica-Bold',
        fontSize=18,
        spaceAfter=12,
        textColor=colors.HexColor("#1e3a8a")
    )
    
    body_style = ParagraphStyle(
        'BodyStyle',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=10,
        leading=14,
        spaceAfter=10
    )
    
    # Title & Intro
    story.append(Paragraph("KTU Student Activity Points Allocation Rules", title_style))
    story.append(Paragraph(
        "As part of the KTU curriculum guidelines, students must acquire at least 100 activity points "
        "to qualify for the B.Tech Degree. Points are allocated based on participation in national, college, "
        "and department level events as outlined in the official table below.",
        body_style
    ))
    story.append(Spacer(1, 10))
    
    # Table Data
    data = [
        ["Activity Category", "Clearance Level", "Max Points Allowed"],
        ["National Initiative (NSS/NCC)", "National", "50 Points"],
        ["Sports & Athletics Tournament", "State/University", "30 Points"],
        ["Technical Fest & Paper Presentation", "National/State", "25 Points"],
        ["Community Service & Teaching", "Local/College", "20 Points"],
        ["Leadership (Student Senate Officer)", "College Level", "15 Points"]
    ]
    
    t = Table(data, colWidths=[200, 150, 120])
    t.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#1e3a8a")),
        ('TEXTCOLOR', (0,0), (-1,0), colors.white),
        ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
        ('FONTSIZE', (0,0), (-1,0), 10),
        ('BOTTOMPADDING', (0,0), (-1,0), 8),
        ('BACKGROUND', (0,1), (-1,-1), colors.HexColor("#f3f4f6")),
        ('GRID', (0,0), (-1,-1), 1, colors.HexColor("#cbd5e1")),
        ('FONTNAME', (0,1), (-1,-1), 'Helvetica'),
        ('FONTSIZE', (0,1), (-1,-1), 9),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('BOTTOMPADDING', (0,1), (-1,-1), 6),
        ('TOPPADDING', (0,0), (-1,-1), 6),
    ]))
    
    story.append(t)
    story.append(Spacer(1, 15))
    story.append(Paragraph("Note: Document verification is mandatory by faculty advisors before point approval.", body_style))
    
    doc.build(story)
    print(f"[INFO] Mock PDF created: {filename}")

def create_faculty_confidential_pdf(filename="faculty_salary_scheme.pdf"):
    """
    Generates a confidential PDF that should only be accessible by Faculty.
    """
    doc = SimpleDocTemplate(filename, pagesize=letter)
    story = []
    
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        'ConfTitleStyle',
        parent=styles['Heading1'],
        fontName='Helvetica-Bold',
        fontSize=18,
        spaceAfter=12,
        textColor=colors.HexColor("#b91c1c")
    )
    body_style = ParagraphStyle(
        'ConfBodyStyle',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=10,
        leading=14,
        spaceAfter=10
    )
    
    story.append(Paragraph("CONFIDENTIAL: Faculty Salary Scheme Revision 2026", title_style))
    story.append(Paragraph(
        "This document contains proprietary information regarding the revised salary schemes "
        "and performance appraisals for KTU-affiliated institutional faculty members. "
        "Under no circumstances should this information be shared with students or external parties.",
        body_style
    ))
    story.append(Spacer(1, 10))
    
    data = [
        ["Grade Level", "Appraisal Rating", "Revised Increment %"],
        ["Professor (Grade A)", "Exceeds Expectations", "12% Increment"],
        ["Associate Professor", "Meets Expectations", "8% Increment"],
        ["Assistant Professor", "Developing", "5% Increment"]
    ]
    t = Table(data, colWidths=[150, 150, 150])
    t.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#b91c1c")),
        ('TEXTCOLOR', (0,0), (-1,0), colors.white),
        ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
        ('BOTTOMPADDING', (0,0), (-1,0), 6),
        ('GRID', (0,0), (-1,-1), 1, colors.HexColor("#fca5a5")),
        ('BACKGROUND', (0,1), (-1,-1), colors.HexColor("#fef2f2")),
    ]))
    story.append(t)
    
    doc.build(story)
    print(f"[INFO] Faculty Confidential PDF created: {filename}")

def run_tests():
    print("\n--- Starting Verification Tests ---")
    
    # Session tokens
    student_headers = {"Authorization": "Bearer token-student-session-key-2026"}
    faculty_headers = {"Authorization": "Bearer token-faculty-session-key-2026"}
    admin_headers = {"Authorization": "Bearer token-admin-session-key-2026"}
    
    # 1. Test Health endpoint
    try:
        res = requests.get(f"{API_URL}/api/health")
        print(f"[TEST PASS] Health Check: status={res.json().get('status')}")
    except Exception as e:
        print(f"[TEST FAIL] Health Check failed: {e}")
        return

    # 2. Upload mock PDF as Admin (Clearance: Student)
    pdf_file = "ktu_activity_points.pdf"
    with open(pdf_file, "rb") as f:
        res = requests.post(
            f"{API_URL}/api/admin/upload",
            headers=admin_headers,
            data={
                "role_access": "Student",
                "doc_type": "Activity Points",
                "topic": "Activity point guidelines"
            },
            files={"file": (pdf_file, f, "application/pdf")}
        )
    print(f"[TEST PASS] Admin upload Student document: status={res.status_code}, response={res.json().get('message')}")

    # 3. Upload confidential PDF as Admin (Clearance: Faculty)
    conf_file = "faculty_salary_scheme.pdf"
    with open(conf_file, "rb") as f:
        res = requests.post(
            f"{API_URL}/api/admin/upload",
            headers=admin_headers,
            data={
                "role_access": "Faculty",
                "doc_type": "Guidelines",
                "topic": "Salary schemes"
            },
            files={"file": (conf_file, f, "application/pdf")}
        )
    print(f"[TEST PASS] Admin upload Faculty confidential document: status={res.status_code}, response={res.json().get('message')}")

    # 4. Attempt to upload a document as Student -> Should block (RBAC test)
    with open(pdf_file, "rb") as f:
        res = requests.post(
            f"{API_URL}/api/admin/upload",
            headers=student_headers,
            data={
                "role_access": "Student",
                "doc_type": "Activity Points",
                "topic": "Hack test"
            },
            files={"file": (pdf_file, f, "application/pdf")}
        )
    if res.status_code == 403:
        print(f"[TEST PASS] Blocked Student upload (RBAC works): status={res.status_code}")
    else:
        print(f"[TEST FAIL] Student upload was not blocked! status={res.status_code}")

    # 5. Attempt to upload a document as Faculty -> Should block (RBAC test, only Admin allowed now)
    with open(pdf_file, "rb") as f:
        res = requests.post(
            f"{API_URL}/api/admin/upload",
            headers=faculty_headers,
            data={
                "role_access": "Student",
                "doc_type": "Activity Points",
                "topic": "Hack test"
            },
            files={"file": (pdf_file, f, "application/pdf")}
        )
    if res.status_code == 403:
        print(f"[TEST PASS] Blocked Faculty upload (RBAC works): status={res.status_code}")
    else:
        print(f"[TEST FAIL] Faculty upload was not blocked! status={res.status_code}")

    # 6. Query Student-accessible document as Student
    res = requests.post(
        f"{API_URL}/api/query",
        headers=student_headers,
        json={"query": "How many points do I get for National Initiative (NSS/NCC)?"}
    )
    print(f"[TEST RESULT] Student Query (Allowed Doc): status={res.status_code}")
    print(f"RAG Response: {res.json().get('response')}\n")

    # 7. Query Faculty-only document as Student -> Should filter out
    res = requests.post(
        f"{API_URL}/api/query",
        headers=student_headers,
        json={"query": "What is the revised salary increment for Professor Grade A?"}
    )
    print(f"[TEST RESULT] Student Query (Confidential Doc): status={res.status_code}")
    print(f"RAG Response (Should state 'not found'): {res.json().get('response')}\n")

    # 8. Query Faculty-only document as Faculty -> Should succeed
    res = requests.post(
        f"{API_URL}/api/query",
        headers=faculty_headers,
        json={"query": "What is the revised salary increment for Professor Grade A?"}
    )
    print(f"[TEST RESULT] Faculty Query (Confidential Doc): status={res.status_code}")
    print(f"RAG Response: {res.json().get('response')}\n")

    # 9. Post a new Notification announcement as Admin
    res = requests.post(
        f"{API_URL}/api/admin/notify",
        headers=admin_headers,
        json={
            "title": "URGENT KTU HOLIDAY WARNING",
            "content": "A red alert weather warning has been issued. All exams scheduled for August 3rd, 2026 are postponed.",
            "role_access": "All"
        }
    )
    print(f"[TEST PASS] Admin Post Announcement: status={res.status_code}, title={res.json().get('title')}")

    # 10. Query chatbot as student about the holiday -> Verify real-time RAG ingestion
    res = requests.post(
        f"{API_URL}/api/query",
        headers=student_headers,
        json={"query": "Are there any exams postponed on August 3rd, 2026?"}
    )
    print(f"[TEST RESULT] Student Query (Real-time Notification): status={res.status_code}")
    print(f"RAG Response: {res.json().get('response')}\n")

if __name__ == "__main__":
    create_mock_pdf()
    create_faculty_confidential_pdf()
    
    # Wait for the server to load if just started
    time.sleep(2)
    run_tests()
