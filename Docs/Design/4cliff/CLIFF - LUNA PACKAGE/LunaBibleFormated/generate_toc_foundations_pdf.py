#!/usr/bin/env python3
"""Generate PDF from the combined TOC + Foundations + Philosophy markdown."""

import re
from pathlib import Path
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib.colors import HexColor
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    PageBreak, HRFlowable, Preformatted
)
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib import colors

# Paths
BASE_DIR = Path("/Users/zayneamason/_HeyLuna_BETA/_LunaEngine_BetaProject_V2.0_Root/Docs/Design/4cliff/CLIFF - LUNA PACKAGE/LunaBibleFormated")
INPUT_PATH = BASE_DIR / "00-FOUNDATIONS-AND-TOC.md"
OUTPUT_PATH = BASE_DIR / "LUNA_ENGINE_BIBLE_TOC_FOUNDATIONS_PHILOSOPHY.pdf"

# Page dimensions
PAGE_WIDTH = letter[0]  # 8.5 inches
PAGE_HEIGHT = letter[1]  # 11 inches
MARGIN = 0.75 * inch
CONTENT_WIDTH = PAGE_WIDTH - (2 * MARGIN)  # ~7 inches

# Colors
COLORS = {
    'primary': HexColor('#1a1a2e'),
    'secondary': HexColor('#4a4a6a'),
    'accent': HexColor('#7b68ee'),
    'text': HexColor('#333333'),
    'light_text': HexColor('#666666'),
    'bg_alt': HexColor('#f8f8f8'),
    'border': HexColor('#cccccc'),
    'code_bg': HexColor('#f5f5f5'),
}


def create_styles():
    """Create custom paragraph styles."""
    styles = getSampleStyleSheet()

    styles.add(ParagraphStyle(
        name='MainTitle',
        parent=styles['Title'],
        fontSize=28,
        spaceAfter=12,
        textColor=COLORS['primary'],
        alignment=TA_CENTER
    ))

    styles.add(ParagraphStyle(
        name='PartHeader',
        parent=styles['Heading1'],
        fontSize=20,
        spaceBefore=20,
        spaceAfter=10,
        textColor=COLORS['primary'],
        backColor=HexColor('#f0f0f8'),
        borderPadding=5
    ))

    styles.add(ParagraphStyle(
        name='SectionHeader',
        parent=styles['Heading2'],
        fontSize=13,
        spaceBefore=14,
        spaceAfter=6,
        textColor=COLORS['secondary']
    ))

    styles.add(ParagraphStyle(
        name='SubsectionHeader',
        parent=styles['Heading3'],
        fontSize=11,
        spaceBefore=10,
        spaceAfter=4,
        textColor=COLORS['text'],
        fontName='Helvetica-Bold'
    ))

    styles.add(ParagraphStyle(
        name='Body',
        parent=styles['Normal'],
        fontSize=9,
        spaceAfter=5,
        leading=12,
        textColor=COLORS['text']
    ))

    styles.add(ParagraphStyle(
        name='Quote',
        parent=styles['Normal'],
        fontSize=10,
        leftIndent=12,
        rightIndent=12,
        spaceAfter=8,
        spaceBefore=8,
        textColor=COLORS['accent'],
        fontName='Helvetica-BoldOblique'
    ))

    styles.add(ParagraphStyle(
        name='CodeBlock',
        parent=styles['Code'],
        fontSize=6,
        leftIndent=5,
        rightIndent=5,
        spaceAfter=6,
        spaceBefore=6,
        backColor=COLORS['code_bg'],
        borderColor=COLORS['border'],
        borderWidth=0.5,
        borderPadding=4,
        leading=7.5
    ))

    styles.add(ParagraphStyle(
        name='BulletItem',
        parent=styles['Normal'],
        fontSize=9,
        leftIndent=15,
        spaceAfter=2,
        bulletIndent=8,
        textColor=COLORS['text']
    ))

    styles.add(ParagraphStyle(
        name='Footer',
        parent=styles['Normal'],
        fontSize=8,
        textColor=COLORS['light_text'],
        alignment=TA_CENTER
    ))

    styles.add(ParagraphStyle(
        name='TableCell',
        fontSize=7,
        leading=9,
        textColor=COLORS['text']
    ))

    styles.add(ParagraphStyle(
        name='TableHeader',
        fontSize=7,
        leading=9,
        fontName='Helvetica-Bold',
        textColor=colors.white
    ))

    return styles


def parse_table(lines):
    """Parse markdown table into data rows."""
    rows = []
    for line in lines:
        if line.strip().startswith('|') and not re.match(r'\|[-:\s|]+\|', line):
            cells = [c.strip() for c in line.strip().split('|')[1:-1]]
            if cells:
                rows.append(cells)
    return rows


def create_table(data, styles):
    """Create a formatted table with proper text wrapping."""
    if not data or len(data) < 2:
        return None

    num_cols = len(data[0])

    # Calculate proportional column widths based on max content length
    col_lengths = []
    for col_idx in range(num_cols):
        max_len = 0
        for row in data:
            if col_idx < len(row):
                max_len = max(max_len, len(str(row[col_idx])))
        col_lengths.append(max(max_len, 5))  # minimum 5 chars

    total_len = sum(col_lengths)

    # Use slightly less than content width for safety margin
    available = CONTENT_WIDTH - 0.2 * inch
    col_widths = [(l / total_len) * available for l in col_lengths]

    # Wrap cell content in Paragraphs for text wrapping
    wrapped_data = []
    for row_idx, row in enumerate(data):
        wrapped_row = []
        for cell in row:
            cell_text = str(cell).replace('**', '').replace('*', '').replace('`', '')
            if row_idx == 0:
                wrapped_row.append(Paragraph(cell_text, styles['TableHeader']))
            else:
                wrapped_row.append(Paragraph(cell_text, styles['TableCell']))
        wrapped_data.append(wrapped_row)

    table = Table(wrapped_data, colWidths=col_widths)
    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), COLORS['primary']),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('GRID', (0, 0), (-1, -1), 0.5, COLORS['border']),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
        ('TOPPADDING', (0, 0), (-1, -1), 3),
        ('LEFTPADDING', (0, 0), (-1, -1), 3),
        ('RIGHTPADDING', (0, 0), (-1, -1), 3),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, COLORS['bg_alt']]),
    ]))
    return table


def process_markdown(md_content, styles):
    """Convert markdown to flowables."""
    flowables = []
    lines = md_content.split('\n')
    i = 0

    while i < len(lines):
        line = lines[i]

        # Main title
        if line.startswith('# ') and not line.startswith('# Part'):
            title = line[2:].strip()
            flowables.append(Paragraph(title, styles['MainTitle']))
            flowables.append(Spacer(1, 8))

        # Part header
        elif line.startswith('# Part'):
            flowables.append(PageBreak())
            title = line[2:].strip()
            flowables.append(Paragraph(title, styles['PartHeader']))
            flowables.append(Spacer(1, 10))

        # Section header (##)
        elif line.startswith('## '):
            title = line[3:].strip()
            flowables.append(Paragraph(title, styles['SectionHeader']))

        # Subsection header (###)
        elif line.startswith('### '):
            title = line[4:].strip()
            flowables.append(Paragraph(title, styles['SubsectionHeader']))

        # Horizontal rule
        elif line.strip() == '---':
            flowables.append(Spacer(1, 6))
            flowables.append(HRFlowable(width="100%", thickness=0.5, color=COLORS['border']))
            flowables.append(Spacer(1, 6))

        # Code block
        elif line.strip().startswith('```'):
            code_lines = []
            i += 1
            while i < len(lines) and not lines[i].strip().startswith('```'):
                code_lines.append(lines[i])
                i += 1
            if code_lines:
                code_text = '\n'.join(code_lines)
                # Truncate very long code blocks
                if len(code_lines) > 35:
                    code_text = '\n'.join(code_lines[:35]) + '\n... (truncated)'
                flowables.append(Preformatted(code_text, styles['CodeBlock']))

        # Table
        elif line.strip().startswith('|'):
            table_lines = [line]
            i += 1
            while i < len(lines) and lines[i].strip().startswith('|'):
                table_lines.append(lines[i])
                i += 1
            i -= 1  # Back up one
            data = parse_table(table_lines)
            if data:
                table = create_table(data, styles)
                if table:
                    flowables.append(table)
                    flowables.append(Spacer(1, 6))

        # Quote (> )
        elif line.strip().startswith('> '):
            quote_text = line.strip()[2:]
            quote_text = re.sub(r'\*\*(.+?)\*\*', r'<b>\1</b>', quote_text)
            flowables.append(Paragraph(quote_text, styles['Quote']))

        # Bold quote line (standalone bold)
        elif line.strip().startswith('**') and line.strip().endswith('**') and len(line.strip()) > 4:
            text = line.strip()[2:-2]
            flowables.append(Paragraph(f'<b>{text}</b>', styles['Quote']))

        # Bullet point
        elif line.strip().startswith('- '):
            text = line.strip()[2:]
            text = re.sub(r'\*\*(.+?)\*\*', r'<b>\1</b>', text)
            text = re.sub(r'\*(.+?)\*', r'<i>\1</i>', text)
            flowables.append(Paragraph(f"• {text}", styles['BulletItem']))

        # Numbered list
        elif re.match(r'^\d+\.\s', line.strip()):
            text = re.sub(r'^\d+\.\s', '', line.strip())
            text = re.sub(r'\*\*(.+?)\*\*', r'<b>\1</b>', text)
            flowables.append(Paragraph(text, styles['BulletItem']))

        # Regular paragraph
        elif line.strip() and not line.startswith('**Version') and not line.startswith('**Last') and not line.startswith('**Status'):
            text = line.strip()
            text = re.sub(r'\*\*(.+?)\*\*', r'<b>\1</b>', text)
            text = re.sub(r'\*(.+?)\*', r'<i>\1</i>', text)
            text = re.sub(r'`(.+?)`', r'<font face="Courier" size="8">\1</font>', text)
            if text:
                flowables.append(Paragraph(text, styles['Body']))

        # Metadata lines
        elif line.startswith('**Version') or line.startswith('**Last') or line.startswith('**Status'):
            text = line.strip().replace('**', '')
            flowables.append(Paragraph(f"<i>{text}</i>", styles['Footer']))

        i += 1

    return flowables


def add_page_number(canvas, doc):
    """Add page numbers."""
    page_num = canvas.getPageNumber()
    text = f"Luna Engine Bible v3.0 — Page {page_num}"
    canvas.saveState()
    canvas.setFont('Helvetica', 7)
    canvas.setFillColor(COLORS['light_text'])
    canvas.drawCentredString(PAGE_WIDTH / 2, 0.4 * inch, text)
    canvas.restoreState()


def main():
    print("=" * 60)
    print("Generating PDF: TOC + Foundations + Philosophy")
    print("=" * 60)

    # Read markdown
    with open(INPUT_PATH, 'r', encoding='utf-8') as f:
        md_content = f.read()

    print(f"Read {len(md_content)} characters from markdown")

    # Create styles
    styles = create_styles()

    # Create document
    doc = SimpleDocTemplate(
        str(OUTPUT_PATH),
        pagesize=letter,
        rightMargin=MARGIN,
        leftMargin=MARGIN,
        topMargin=MARGIN,
        bottomMargin=MARGIN
    )

    # Process markdown
    print("Processing markdown...")
    story = process_markdown(md_content, styles)
    print(f"Generated {len(story)} flowables")

    # Build PDF
    print("Building PDF...")
    doc.build(story, onFirstPage=add_page_number, onLaterPages=add_page_number)

    print(f"\n{'=' * 60}")
    print(f"SUCCESS! PDF created at:")
    print(f"  {OUTPUT_PATH}")
    print(f"{'=' * 60}")


if __name__ == "__main__":
    main()
