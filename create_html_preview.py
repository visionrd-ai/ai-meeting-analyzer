#!/usr/bin/env python3
"""
Create HTML preview of the VisionRD report.
"""

import os
from datetime import datetime

def create_html_preview():
    """Create HTML preview of the report."""
    
    # Read the text report
    with open('weekly_work_report.txt', 'r', encoding='utf-8') as f:
        content = f.read()
    
    # HTML template with VisionRD branding
    html_template = f"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>VisionRD - Perfect AI Development Report</title>
    <style>
        body {{
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            line-height: 1.6;
            color: #1f2937;
            max-width: 1200px;
            margin: 0 auto;
            padding: 20px;
            background: #f9fafb;
        }}
        
        .header {{
            text-align: center;
            background: white;
            padding: 40px;
            border-radius: 12px;
            box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
            margin-bottom: 30px;
        }}
        
        .logo {{
            width: 100px;
            height: 100px;
            margin: 0 auto 20px;
        }}
        
        .company-name {{
            font-size: 28px;
            font-weight: bold;
            color: #dc2626;
            margin-bottom: 10px;
        }}
        
        .report-title {{
            font-size: 32px;
            font-weight: bold;
            color: #1f2937;
            margin-bottom: 10px;
        }}
        
        .report-subtitle {{
            font-size: 18px;
            color: #6b7280;
            margin-bottom: 20px;
        }}
        
        .metadata {{
            background: white;
            padding: 20px;
            border-radius: 8px;
            margin-bottom: 20px;
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
            gap: 15px;
        }}
        
        .metadata-item {{
            display: flex;
            justify-content: space-between;
            padding: 8px 0;
            border-bottom: 1px solid #e5e7eb;
        }}
        
        .metadata-label {{
            font-weight: bold;
            color: #374151;
        }}
        
        .content {{
            background: white;
            padding: 30px;
            border-radius: 12px;
            box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
            margin-bottom: 20px;
        }}
        
        .day-header {{
            background: linear-gradient(135deg, #dc2626, #b91c1c);
            color: white;
            padding: 20px;
            border-radius: 8px;
            margin: 30px 0 20px 0;
            font-size: 20px;
            font-weight: bold;
        }}
        
        .section-header {{
            background: #f3f4f6;
            padding: 15px;
            border-left: 4px solid #dc2626;
            margin: 20px 0 15px 0;
            font-weight: bold;
            font-size: 16px;
        }}
        
        .feature-item {{
            padding: 8px 0;
            margin-left: 20px;
            border-bottom: 1px solid #f3f4f6;
        }}
        
        .feature-item:last-child {{
            border-bottom: none;
        }}
        
        .checkmark {{
            color: #10b981;
            font-weight: bold;
        }}
        
        .hours {{
            background: #fef3c7;
            padding: 10px;
            border-radius: 6px;
            margin: 15px 0;
            font-weight: bold;
            text-align: center;
        }}
        
        .footer {{
            text-align: center;
            background: white;
            padding: 30px;
            border-radius: 12px;
            box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
            margin-top: 30px;
            color: #6b7280;
        }}
        
        .print-button {{
            position: fixed;
            top: 20px;
            right: 20px;
            background: #dc2626;
            color: white;
            border: none;
            padding: 12px 24px;
            border-radius: 8px;
            cursor: pointer;
            font-weight: bold;
            box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
        }}
        
        .print-button:hover {{
            background: #b91c1c;
        }}
        
        @media print {{
            body {{ background: white; }}
            .print-button {{ display: none; }}
        }}
    </style>
</head>
<body>
    <button class="print-button" onclick="window.print()">🖨️ Print Report</button>
    
    <div class="header">
        <div class="logo">
            <svg width="100" height="100" viewBox="0 0 100 100">
                <circle cx="50" cy="50" r="45" fill="#dc2626" opacity="0.1"/>
                <text x="50" y="60" text-anchor="middle" font-family="Arial, sans-serif" font-size="16" font-weight="bold" fill="#dc2626">VisionRD</text>
            </svg>
        </div>
        <div class="company-name">VisionRD</div>
        <div class="report-title">PERFECT AI MEETING ANALYZER</div>
        <div class="report-subtitle">6-Day Development Cycle Report</div>
    </div>
    
    <div class="metadata">
        <div class="metadata-item">
            <span class="metadata-label">Report Date:</span>
            <span>{datetime.now().strftime('%B %d, %Y')}</span>
        </div>
        <div class="metadata-item">
            <span class="metadata-label">Project:</span>
            <span>Perfect AI Meeting Analyzer</span>
        </div>
        <div class="metadata-item">
            <span class="metadata-label">Development Period:</span>
            <span>6 Days Intensive Development</span>
        </div>
        <div class="metadata-item">
            <span class="metadata-label">Total Hours:</span>
            <span>48-52 hours</span>
        </div>
        <div class="metadata-item">
            <span class="metadata-label">Company:</span>
            <span>VisionRD</span>
        </div>
    </div>
    
    <div class="content">
"""
    
    # Process the content
    lines = content.split('\n')
    
    for line in lines:
        line = line.strip()
        
        if not line:
            html_template += '<br>'
            continue
        
        # Skip header lines we already added
        if any(skip in line for skip in ['PERFECT AI MEETING ANALYZER', 'WEEKLY WORK REPORT', 'TOTAL HOURS WORKED', 'PROJECT:', 'DEVELOPER:', 'PERIOD:']):
            continue
        
        # Skip separator lines
        if line.startswith('=') and len(line) > 50:
            continue
        
        # Day headers
        if line.startswith('DAY ') and ':' in line:
            html_template += f'<div class="day-header">{line}</div>'
            continue
        
        # Section headers (all caps with colons)
        if line.isupper() and line.endswith(':') and len(line) > 10:
            html_template += f'<div class="section-header">{line}</div>'
            continue
        
        # Checkmark items
        if line.startswith('✅'):
            html_template += f'<div class="feature-item"><span class="checkmark">✅</span> {line[2:].strip()}</div>'
            continue
        
        # Hours
        if line.startswith('HOURS:'):
            html_template += f'<div class="hours">{line}</div>'
            continue
        
        # Regular content
        if line and not line.startswith('='):
            html_template += f'<p>{line}</p>'
    
    # Close HTML
    html_template += """
    </div>
    
    <div class="footer">
        <h3>Report Generated by VisionRD</h3>
        <p>© """ + str(datetime.now().year) + """ VisionRD - All Rights Reserved</p>
        <p>Perfect AI Meeting Analyzer Development Project</p>
    </div>
</body>
</html>
"""
    
    # Save HTML file
    html_filename = f"VisionRD_Report_Preview_{datetime.now().strftime('%Y%m%d')}.html"
    with open(html_filename, 'w', encoding='utf-8') as f:
        f.write(html_template)
    
    print(f"✅ HTML preview created: {html_filename}")
    return html_filename

if __name__ == "__main__":
    html_file = create_html_preview()
    
    # Try to open the HTML file
    try:
        import webbrowser
        webbrowser.open(html_file)
        print(f"🌐 Opening HTML preview in browser...")
    except:
        print(f"📁 HTML preview saved: {os.path.abspath(html_file)}")