@echo off
echo 🎯 VisionRD PDF Report Generator
echo ================================
echo.

echo 📦 Installing required packages...
pip install reportlab svglib pillow

echo.
echo 🎨 Creating professional PDF report with VisionRD branding...
python create_pdf_report.py

echo.
echo ✅ VisionRD report generation complete!
echo.
pause