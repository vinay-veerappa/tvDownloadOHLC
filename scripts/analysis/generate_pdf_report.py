import os
import re
from reportlab.lib.pagesizes import LETTER
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak, Image
from reportlab.lib import colors

def markdown_to_pdf(input_md, output_pdf):
    # Setup document
    doc = SimpleDocTemplate(output_pdf, pagesize=LETTER)
    styles = getSampleStyleSheet()
    
    # Custom styles
    styles.add(ParagraphStyle(name='SubTitle', parent=styles['Heading2'], alignment=1, spaceAfter=20))
    styles.add(ParagraphStyle(name='StrategyCode', parent=styles['Normal'], fontName='Courier', fontSize=8, leftIndent=20))
    
    flowables = []

    with open(input_md, 'r', encoding='utf-8') as f:
        content = f.read()

    # Split into sections based on headers or lines
    lines = content.split('\n')
    
    in_code_block = False
    code_content = []
    
    in_table = False
    table_data = []

    for line in lines:
        # Code block handling
        if line.strip().startswith('```'):
            if in_code_block:
                # End code block
                flowables.append(Paragraph('<br/>'.join(code_content), styles['StrategyCode']))
                flowables.append(Spacer(1, 10))
                code_content = []
                in_code_block = False
            else:
                in_code_block = True
            continue
        
        if in_code_block:
            code_content.append(line.replace(' ', '&nbsp;').replace('<', '&lt;').replace('>', '&gt;'))
            continue

        # Image handling: ![alt](path)
        img_match = re.search(r'!\[.*?\]\((.*?)\)', line)
        if img_match:
            img_path = img_match.group(1).replace('file:///', '')
            # Convert to absolute path if needed
            if img_path.startswith('c:/'):
                pass # Already absolute
            
            if os.path.exists(img_path):
                img = Image(img_path, width=6*inch, height=3.5*inch)
                flowables.append(img)
                flowables.append(Spacer(1, 12))
                continue

        # Table handling (simple markdown table parsing)
        if '|' in line and not in_code_block:
            if '---' in line:
                continue
            # Remove leading/trailing pipes
            clean_line = line.strip().strip('|')
            cols = [c.strip() for c in clean_line.split('|')]
            if cols:
                table_data.append(cols)
                in_table = True
            continue
        elif in_table:
            # Table ended
            if table_data:
                t = Table(table_data, hAlign='LEFT', repeatRows=1)
                t.setStyle(TableStyle([
                    ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
                    ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                    ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                    ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                    ('FONTSIZE', (0, 0), (-1, -1), 8),
                    ('BOTTOMPADDING', (0, 0), (-1, 0), 6),
                    ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
                    ('GRID', (0, 0), (-1, -1), 0.5, colors.black)
                ]))
                flowables.append(t)
                flowables.append(Spacer(1, 15))
            table_data = []
            in_table = False

        # Header handling
        if line.startswith('# '):
            flowables.append(Paragraph(line[2:], styles['Title']))
            flowables.append(Spacer(1, 20))
        elif line.startswith('## '):
            flowables.append(Paragraph(line[3:], styles['Heading1']))
            flowables.append(Spacer(1, 12))
        elif line.startswith('### '):
            flowables.append(Paragraph(line[4:], styles['Heading2']))
            flowables.append(Spacer(1, 10))
        elif line.startswith('#### '):
            flowables.append(Paragraph(line[5:], styles['Heading3']))
            flowables.append(Spacer(1, 8))
        elif line.startswith('- ') or line.startswith('* '):
            # Simple bullet list
            text = line[2:]
            text = re.sub(r'\*\*(.*?)\*\*', r'<b>\1</b>', text)
            flowables.append(Paragraph(f"&bull; {text}", styles['Normal']))
            flowables.append(Spacer(1, 4))
        elif line.strip() == '':
            flowables.append(Spacer(1, 6))
        else:
            # Normal paragraph
            text = re.sub(r'\*\*(.*?)\*\*', r'<b>\1</b>', line)
            flowables.append(Paragraph(text, styles['Normal']))
            flowables.append(Spacer(1, 6))

    # Build the PDF
    doc.build(flowables)
    print(f"PDF Successfully generated at: {output_pdf}")

if __name__ == "__main__":
    input_file = r'c:\Users\vinay\tvDownloadOHLC\docs\strategies\initial_balance_break\STRATEGY_ENCYCLOPEDIA_OMNIBUS.md'
    output_file = r'c:\Users\vinay\tvDownloadOHLC\docs\strategies\initial_balance_break\Strategy_Technical_Encyclopedia_Omnibus.pdf'
    markdown_to_pdf(input_file, output_file)
