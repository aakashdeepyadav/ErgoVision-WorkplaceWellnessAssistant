import os
import sqlite3
from datetime import datetime, timedelta
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors

import config
from src.database import DatabaseManager

class ReportGenerator:
    def __init__(self, db_manager: DatabaseManager):
        self.db = db_manager

    def generate_weekly_report_pdf(self, output_path: str = "weekly_wellness_report.pdf"):
        # Fetch last 7 days of summaries
        summaries = self.db.get_weekly_summaries(days=7)
        if not summaries:
            raise ValueError("No data available to generate report.")

        doc = SimpleDocTemplate(output_path, pagesize=letter)
        styles = getSampleStyleSheet()
        title_style = styles['Heading1']
        normal_style = styles['Normal']

        elements = []

        # Title
        elements.append(Paragraph("ErgoVision Weekly Wellness Report", title_style))
        elements.append(Spacer(1, 12))
        
        # Summary Header
        today = datetime.now().strftime("%Y-%m-%d")
        elements.append(Paragraph(f"Generated on: {today}", normal_style))
        elements.append(Spacer(1, 24))

        # Table Data
        data = [["Date", "Sessions", "Time (min)", "Avg Fatigue", "Breaks", "Alerts"]]
        for row in summaries:
            data.append([
                row['date'],
                str(row['total_sessions']),
                f"{row['total_minutes']:.1f}",
                f"{row['avg_fatigue_score']:.1f}",
                str(row['breaks_taken']),
                str(row['total_alerts'])
            ])

        # Table Styling
        table = Table(data)
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#0f766e")),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 12),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.HexColor("#f4f7fb")),
            ('TEXTCOLOR', (0, 1), (-1, -1), colors.HexColor("#1e293b")),
            ('GRID', (0, 0), (-1, -1), 1, colors.HexColor("#cbd5e1"))
        ]))
        
        elements.append(table)
        elements.append(Spacer(1, 24))
        
        # Recommendations
        elements.append(Paragraph("Insights & Recommendations", styles['Heading2']))
        elements.append(Spacer(1, 12))
        avg_alerts = sum(row['total_alerts'] for row in summaries) / len(summaries)
        
        if avg_alerts > 10:
            rec = "You have a high number of alerts on average. Consider adjusting your workstation ergonomics or taking more frequent breaks."
        else:
            rec = "Your posture and break compliance are looking good. Keep up the great work!"
            
        elements.append(Paragraph(rec, normal_style))

        doc.build(elements)
        return output_path
