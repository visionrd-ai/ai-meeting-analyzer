#!/usr/bin/env python3
"""
Convert weekly work report to professional PDF with VisionRD branding.
"""

import os
import sys
from datetime import datetime

def install_required_packages():
    """Install required packages for PDF generation."""
    packages = [
        "reportlab",
        "svglib", 
        "pillow"
    ]
    
    for package in packages:
        try:
            __import__(package.replace("-", "_"))
            print(f"✅ {package} already installed")
        except ImportError:
            print(f"📦 Installing {package}...")
            os.system(f"pip install {package}")

def create_pdf_report():
    """Create professional PDF report with VisionRD branding."""
    try:
        from reportlab.lib.pagesizes import letter, A4
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, PageBreak, Table, TableStyle
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.units import inch
        from reportlab.lib import colors
        from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
        from reportlab.platypus.flowables import Image
        from svglib.svglib import renderSVG
        from reportlab.graphics import renderPDF
        import io
        
        print("🎯 Creating VisionRD Professional Report...")
        
        # Create PDF document
        pdf_filename = f"VisionRD_Perfect_AI_Development_Report_{datetime.now().strftime('%Y%m%d')}.pdf"
        doc = SimpleDocTemplate(pdf_filename, pagesize=A4, 
                              rightMargin=72, leftMargin=72, 
                              topMargin=72, bottomMargin=18)
        
        # Container for the 'Flowable' objects
        story = []
        
        # Get styles
        styles = getSampleStyleSheet()
        
        # Custom styles
        title_style = ParagraphStyle(
            'CustomTitle',
            parent=styles['Heading1'],
            fontSize=24,
            spaceAfter=30,
            alignment=TA_CENTER,
            textColor=colors.HexColor('#1f2937')
        )
        
        company_style = ParagraphStyle(
            'CompanyStyle',
            parent=styles['Normal'],
            fontSize=16,
            spaceAfter=20,
            alignment=TA_CENTER,
            textColor=colors.HexColor('#dc2626')
        )
        
        header_style = ParagraphStyle(
            'HeaderStyle',
            parent=styles['Heading2'],
            fontSize=16,
            spaceAfter=12,
            spaceBefore=20,
            textColor=colors.HexColor('#1f2937'),
            borderWidth=1,
            borderColor=colors.HexColor('#e5e7eb'),
            borderPadding=10,
            backColor=colors.HexColor('#f9fafb')
        )
        
        subheader_style = ParagraphStyle(
            'SubHeaderStyle',
            parent=styles['Heading3'],
            fontSize=14,
            spaceAfter=8,
            spaceBefore=12,
            textColor=colors.HexColor('#374151')
        )
        
        body_style = ParagraphStyle(
            'BodyStyle',
            parent=styles['Normal'],
            fontSize=10,
            spaceAfter=6,
            leftIndent=20
        )
        
        # Add logo if it exists
        try:
            if os.path.exists('logo.svg'):
                # Convert SVG to reportlab drawing
                drawing = renderSVG.svg2rlg('logo.svg')
                # Scale the logo
                drawing.width = 100
                drawing.height = 100
                drawing.scale(100/drawing.width, 100/drawing.height)
                story.append(drawing)
                story.append(Spacer(1, 20))
        except Exception as e:
            print(f"⚠️ Could not load logo: {e}")
        
        # Company header
        story.append(Paragraph("VisionRD", company_style))
        story.append(Paragraph("PERFECT AI MEETING ANALYZER", title_style))
        story.append(Paragraph("6-Day Development Cycle Report", styles['Heading2']))
        story.append(Spacer(1, 20))
        
        # Report metadata
        metadata_data = [
            ['Report Date:', datetime.now().strftime('%B %d, %Y')],
            ['Project:', 'Perfect AI Meeting Analyzer'],
            ['Development Period:', '6 Days Intensive Development'],
            ['Total Hours:', '48-52 hours'],
            ['Company:', 'VisionRD']
        ]
        
        metadata_table = Table(metadata_data, colWidths=[2*inch, 3*inch])
        metadata_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (0, -1), colors.HexColor('#f3f4f6')),
            ('TEXTCOLOR', (0, 0), (-1, -1), colors.black),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('GRID', (0, 0), (-1, -1), 1, colors.HexColor('#e5e7eb')),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ]))
        
        story.append(metadata_table)
        story.append(Spacer(1, 30))
        
        # Read the text report
        with open('weekly_work_report.txt', 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Process the content
        lines = content.split('\n')
        current_section = ""
        
        for line in lines:
            line = line.strip()
            
            if not line:
                story.append(Spacer(1, 6))
                continue
            
            # Skip the header lines we already added
            if any(skip in line for skip in ['PERFECT AI MEETING ANALYZER', 'WEEKLY WORK REPORT', 'TOTAL HOURS WORKED', 'PROJECT:', 'DEVELOPER:', 'PERIOD:']):
                continue
            
            # Main section headers (with ===)
            if line.startswith('=') and len(line) > 50:
                continue  # Skip separator lines
            
            # Day headers
            if line.startswith('DAY ') and ':' in line:
                story.append(PageBreak())
                story.append(Paragraph(line, header_style))
                continue
            
            # Section headers (all caps with colons)
            if line.isupper() and line.endswith(':') and len(line) > 10:
                story.append(Paragraph(line, subheader_style))
                continue
            
            # Checkmark items
            if line.startswith('✅'):
                story.append(Paragraph(line, body_style))
                continue
            
            # File lists
            if line.startswith('- ') or line.startswith('FILES '):
                story.append(Paragraph(line, body_style))
                continue
            
            # Hours
            if line.startswith('HOURS:'):
                story.append(Paragraph(f"<b>{line}</b>", body_style))
                story.append(Spacer(1, 12))
                continue
            
            # Regular content
            if line and not line.startswith('='):
                story.append(Paragraph(line, body_style))
        
        # Add footer
        story.append(PageBreak())
        story.append(Spacer(1, 50))
        
        footer_style = ParagraphStyle(
            'FooterStyle',
            parent=styles['Normal'],
            fontSize=12,
            alignment=TA_CENTER,
            textColor=colors.HexColor('#6b7280')
        )
        
        story.append(Paragraph("Report Generated by VisionRD", footer_style))
        story.append(Paragraph(f"© {datetime.now().year} VisionRD - All Rights Reserved", footer_style))
        story.append(Paragraph("Perfect AI Meeting Analyzer Development Project", footer_style))
        
        # Build PDF
        doc.build(story)
        
        print(f"✅ PDF report created: {pdf_filename}")
        return pdf_filename
        
    except ImportError as e:
        print(f"❌ Missing required package: {e}")
        print("Installing required packages...")
        install_required_packages()
        print("Please run the script again after installation.")
        return None
    except Exception as e:
        print(f"❌ Error creating PDF: {e}")
        return None

def main():
    """Main function."""
    print("🎯 VisionRD PDF Report Generator")
    print("=" * 50)
    
    # Check if report file exists
    if not os.path.exists('weekly_work_report.txt'):
        print("❌ weekly_work_report.txt not found!")
        return False
    
    # Check if logo exists
    if os.path.exists('logo.svg'):
        print("✅ VisionRD logo found")
    else:
        print("⚠️ logo.svg not found - PDF will be created without logo")
    
    # Install packages if needed
    install_required_packages()
    
    # Create PDF
    pdf_file = create_pdf_report()
    
    if pdf_file:
        print(f"\n🎉 Success! Professional PDF report created:")
        print(f"📄 {pdf_file}")
        print(f"\n📊 Report includes:")
        print("   ✅ VisionRD company branding")
        print("   ✅ Professional formatting")
        print("   ✅ Complete 6-day development summary")
        print("   ✅ Database and user management details")
        print("   ✅ Technical achievements and metrics")
        
        # Try to open the PDF
        try:
            if sys.platform == "win32":
                os.startfile(pdf_file)
            elif sys.platform == "darwin":
                os.system(f"open {pdf_file}")
            else:
                os.system(f"xdg-open {pdf_file}")
            print(f"📖 Opening PDF in default viewer...")
        except:
            print(f"📁 PDF saved in current directory: {os.path.abspath(pdf_file)}")
        
        return True
    else:
        print("❌ Failed to create PDF report")
        return False

if __name__ == "__main__":
    try:
        success = main()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n❌ PDF generation cancelled by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        sys.exit(1)