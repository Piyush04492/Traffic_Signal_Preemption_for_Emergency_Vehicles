import os
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors

def generate_explanation_pdf():
    pdf_path = "V2X_Project_Explanation.pdf"
    doc = SimpleDocTemplate(
        pdf_path,
        pagesize=letter,
        rightMargin=40,
        leftMargin=40,
        topMargin=40,
        bottomMargin=40
    )
    
    styles = getSampleStyleSheet()
    
    # Custom styles for clean aesthetics
    title_style = ParagraphStyle(
        'DocTitle',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=24,
        leading=28,
        textColor=colors.HexColor('#1e3a8a'),
        spaceAfter=10
    )
    
    subtitle_style = ParagraphStyle(
        'DocSubtitle',
        parent=styles['Normal'],
        fontName='Helvetica-Oblique',
        fontSize=12,
        leading=14,
        textColor=colors.HexColor('#4b5563'),
        spaceAfter=25
    )
    
    h1_style = ParagraphStyle(
        'DocH1',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=16,
        leading=18,
        textColor=colors.HexColor('#1e3a8a'),
        spaceBefore=15,
        spaceAfter=8,
        keepWithNext=True
    )
    
    h2_style = ParagraphStyle(
        'DocH2',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=12,
        leading=14,
        textColor=colors.HexColor('#2563eb'),
        spaceBefore=10,
        spaceAfter=5,
        keepWithNext=True
    )

    body_style = ParagraphStyle(
        'DocBody',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=10,
        leading=13,
        textColor=colors.HexColor('#1f2937'),
        spaceAfter=8
    )

    bullet_style = ParagraphStyle(
        'DocBullet',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=10,
        leading=13,
        textColor=colors.HexColor('#1f2937'),
        leftIndent=15,
        firstLineIndent=-10,
        spaceAfter=4
    )

    q_style = ParagraphStyle(
        'DocQ',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=10.5,
        leading=13,
        textColor=colors.HexColor('#0f766e'),
        spaceBefore=8,
        spaceAfter=4,
        keepWithNext=True
    )
    
    story = []
    
    # ── HEADER section ──
    story.append(Paragraph("V2I Emergency Preemption Simulation System", title_style))
    story.append(Paragraph("A Simplified Technical Guide for Interview Preparation", subtitle_style))
    story.append(Spacer(1, 10))
    
    # ── SECTION 1: INTRODUCTION ──
    story.append(Paragraph("1. Project Overview (The 'Elevator Pitch')", h1_style))
    story.append(Paragraph(
        "This project is a traffic simulation system built in <b>SUMO (Simulation of Urban MObility)</b>. "
        "It evaluates how V2I (Vehicle-to-Infrastructure) communication technology can reduce emergency response times. "
        "The scenario simulates an ambulance traveling through a busy urban corridor with two signalized intersections. "
        "By broadcasting priority request messages to traffic lights, the ambulance dynamically preempts red lights, turning them green.",
        body_style
    ))
    
    # ── SECTION 2: THE 3 MODES ──
    story.append(Paragraph("2. The Three Operation Modes", h1_style))
    story.append(Paragraph(
        "The core of the simulation is comparing three different network configurations under identical civilian traffic flows:",
        body_style
    ))
    
    story.append(Paragraph("<b>1. Baseline (No Preemption):</b>", h2_style))
    story.append(Paragraph("• Standard traffic light schedules. Signals ignore the ambulance completely.", bullet_style))
    story.append(Paragraph("• The ambulance is blocked by civilian queues and stops at red lights, losing valuable response time.", bullet_style))
    story.append(Paragraph("• <i>Travel Time: 76.5 seconds | Stopped Delay: 5.2 seconds</i>", bullet_style))

    story.append(Paragraph("<b>2. 4G LTE preemption (Cloud-Routed):</b>", h2_style))
    story.append(Paragraph("• Priority requests are routed through base stations up to a cloud server, then down to the traffic light controller.", bullet_style))
    story.append(Paragraph("• Realistic Network Latency: <b>50 ms</b> (with potential spikes due to packet drops and core backhaul delay).", bullet_style))
    story.append(Paragraph("• Reliable Range constraint: <b>40 meters</b>. Because of cellular localization limits, preemption is triggered late.", bullet_style))
    story.append(Paragraph("• <i>Travel Time: 72.3 seconds | Stopped Delay: 1.1 seconds</i> (Ambulance slows down/stops briefly because safety yellow clearance phase takes 4.0s to complete).", bullet_style))

    story.append(Paragraph("<b>3. 5G URLLC preemption (Direct Sidelink):</b>", h2_style))
    story.append(Paragraph("• Direct V2X communication (PC5 interface / Sidelink) directly from ambulance radio to RSU traffic light, bypassing base stations.", bullet_style))
    story.append(Paragraph("• Near-Zero Network Latency: <b>2 ms</b> (Ultra-Reliable Low-Latency Communication).", bullet_style))
    story.append(Paragraph("• Long Communication Range: <b>100 meters</b> (Sidelink direct line-of-sight range).", bullet_style))
    story.append(Paragraph("• <i>Travel Time: 68.2 seconds | Stopped Delay: 0.0 seconds</i> (Clearance completes early, ambulance passes at full speed).", bullet_style))

    # ── PERFORMANCE TABLE ──
    story.append(Spacer(1, 10))
    table_data = [
        [
            Paragraph("<b>Mode</b>", body_style),
            Paragraph("<b>Latency</b>", body_style),
            Paragraph("<b>V2I Range</b>", body_style),
            Paragraph("<b>EV Travel Time</b>", body_style),
            Paragraph("<b>EV Stopped Delay</b>", body_style),
        ],
        [
            Paragraph("Baseline", body_style),
            Paragraph("—", body_style),
            Paragraph("—", body_style),
            Paragraph("76.45 s", body_style),
            Paragraph("5.20 s", body_style),
        ],
        [
            Paragraph("4G LTE", body_style),
            Paragraph("50.0 ms", body_style),
            Paragraph("40 m", body_style),
            Paragraph("72.30 s", body_style),
            Paragraph("1.05 s", body_style),
        ],
        [
            Paragraph("5G URLLC", body_style),
            Paragraph("2.0 ms", body_style),
            Paragraph("100 m", body_style),
            Paragraph("68.20 s", body_style),
            Paragraph("0.00 s", body_style),
        ],
    ]
    t = Table(table_data, colWidths=[90, 80, 90, 110, 110])
    t.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#f3f4f6')),
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#d1d5db')),
        ('PADDING', (0,0), (-1,-1), 6),
        ('ALIGN', (0,0), (-1,-1), 'LEFT'),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
    ]))
    story.append(t)
    story.append(Spacer(1, 15))

    # ── SECTION 3: KEY DIFFERENTIATORS ──
    story.append(Paragraph("3. Technical Insights for the Interviewer", h1_style))
    
    story.append(Paragraph("<b>Q1: Why are the travel times different if latency is only 50ms vs 2ms? Both are tiny!</b>", q_style))
    story.append(Paragraph(
        "<b>Answer:</b> The difference is not just latency, but <b>communication range</b> combined with traffic light <b>safety clearance phases</b>. "
        "When a light receives a preemption trigger, it cannot instantly turn green for safety reasons. "
        "It must transition through a 4.0-second yellow clearance phase to let cross-street traffic clear the junction. "
        "<br/>"
        "• With 5G sidelink range (100m), the request is sent 6 seconds before the ambulance arrives. The 4s safety yellow completes before the ambulance gets close, so it passes at 60 km/h."
        "<br/>"
        "• With 4G cellular range (40m), the request is sent only 2.4s before arrival. The safety yellow clearance is still running when the ambulance arrives, forcing it to briefly stop.",
        body_style
    ))

    story.append(Paragraph("<b>Q2: What is URLLC and why does it matter?</b>", q_style))
    story.append(Paragraph(
        "<b>Answer:</b> URLLC stands for <i>Ultra-Reliable Low-Latency Communication</i>. "
        "In 4G cellular networks, network congestion (high traffic load) causes latency spikes and packet drops, requiring retransmissions. "
        "5G URLLC guarantees a 99.999% reliability rate and sub-millisecond radio latency. This makes it viable for safety-critical cooperative driving.",
        body_style
    ))

    story.append(Paragraph("<b>Q3: How is civilian traffic impacted?</b>", q_style))
    story.append(Paragraph(
        "<b>Answer:</b> While emergency preemption saves ambulance travel time, it temporarily blocks cross-street traffic. "
        "The simulation tracks this trade-off using a 'Civilian Delay' metric. 5G URLLC minimizes this impact "
        "because it transitions the signal precisely when needed and restores normal program flows immediately after the ambulance clears the intersection.",
        body_style
    ))

    story.append(Paragraph("<b>Q4: What tools and APIs are utilized?</b>", q_style))
    story.append(Paragraph(
        "<b>Answer:</b> "
        "• <b>SUMO</b> handles the traffic physics, mixed vehicle types (cars, buses, trucks, motorcycles), and lane dynamics."
        "<br/>"
        "• Python's <b>TraCI API</b> is used to interface with the simulator in real-time to track vehicle distances and command traffic lights."
        "<br/>"
        "• <b>Streamlit</b> provides the frontend dashboard, allowing parameter modification and batch run visual comparisons.",
        body_style
    ))

    # Build the document
    doc.build(story)
    print("Explanation PDF generated successfully.")

if __name__ == "__main__":
    generate_explanation_pdf()
