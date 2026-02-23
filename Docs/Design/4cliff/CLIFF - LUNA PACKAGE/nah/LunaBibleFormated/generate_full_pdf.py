#!/usr/bin/env python3
"""
Generate a fully formatted PDF of the Luna Engine Bible v3.0.

This script reads all extracted JSON files and creates a professionally
formatted PDF with proper headers, tables, code blocks, and visual hierarchy.
"""

import json
import os
from pathlib import Path
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib.colors import HexColor
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    PageBreak, HRFlowable, Preformatted, KeepTogether
)
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.lib import colors
from reportlab.platypus.flowables import BalancedColumns

# Paths
BASE_DIR = Path("/Users/zayneamason/_HeyLuna_BETA/_LunaEngine_BetaProject_V2.0_Root/Docs/Design/4cliff/CLIFF - LUNA PACKAGE/LunaBibleFormated")
OUTPUT_PATH = BASE_DIR / "LUNA_ENGINE_BIBLE_V3_FORMATTED.pdf"

# Color scheme
COLORS = {
    'primary': HexColor('#1a1a2e'),
    'secondary': HexColor('#4a4a6a'),
    'accent': HexColor('#7b68ee'),
    'text': HexColor('#333333'),
    'light_text': HexColor('#666666'),
    'bg_alt': HexColor('#f8f8f8'),
    'border': HexColor('#cccccc'),
    'code_bg': HexColor('#f5f5f5'),
    'success': HexColor('#28a745'),
    'warning': HexColor('#ffc107'),
    'error': HexColor('#dc3545'),
}


def create_styles():
    """Create custom paragraph styles."""
    styles = getSampleStyleSheet()

    # Main title
    styles.add(ParagraphStyle(
        name='MainTitle',
        parent=styles['Title'],
        fontSize=36,
        spaceAfter=20,
        textColor=COLORS['primary'],
        alignment=TA_CENTER
    ))

    # Part header (large section)
    styles.add(ParagraphStyle(
        name='PartHeader',
        parent=styles['Heading1'],
        fontSize=24,
        spaceBefore=30,
        spaceAfter=15,
        textColor=COLORS['primary'],
        borderColor=COLORS['primary'],
        borderWidth=2,
        borderPadding=8,
        backColor=HexColor('#f0f0f8')
    ))

    # Section header
    styles.add(ParagraphStyle(
        name='SectionHeader',
        parent=styles['Heading2'],
        fontSize=16,
        spaceBefore=20,
        spaceAfter=10,
        textColor=COLORS['secondary']
    ))

    # Subsection header
    styles.add(ParagraphStyle(
        name='SubsectionHeader',
        parent=styles['Heading3'],
        fontSize=12,
        spaceBefore=12,
        spaceAfter=6,
        textColor=COLORS['text'],
        fontName='Helvetica-Bold'
    ))

    # Body text
    styles.add(ParagraphStyle(
        name='Body',
        parent=styles['Normal'],
        fontSize=10,
        spaceAfter=8,
        leading=14,
        textColor=COLORS['text']
    ))

    # Quote/emphasis
    styles.add(ParagraphStyle(
        name='Quote',
        parent=styles['Normal'],
        fontSize=11,
        leftIndent=20,
        rightIndent=20,
        spaceAfter=12,
        spaceBefore=12,
        textColor=COLORS['accent'],
        fontName='Helvetica-BoldOblique'
    ))

    # Code style
    styles.add(ParagraphStyle(
        name='CodeBlock',
        parent=styles['Code'],
        fontSize=8,
        leftIndent=10,
        rightIndent=10,
        spaceAfter=10,
        spaceBefore=10,
        backColor=COLORS['code_bg'],
        borderColor=COLORS['border'],
        borderWidth=1,
        borderPadding=6,
        leading=10
    ))

    # Note/warning
    styles.add(ParagraphStyle(
        name='Note',
        parent=styles['Normal'],
        fontSize=9,
        leftIndent=15,
        spaceAfter=8,
        textColor=COLORS['light_text'],
        fontName='Helvetica-Oblique'
    ))

    # TOC entry
    styles.add(ParagraphStyle(
        name='TOCEntry',
        parent=styles['Normal'],
        fontSize=10,
        spaceAfter=4,
        leftIndent=20
    ))

    # Footer
    styles.add(ParagraphStyle(
        name='Footer',
        parent=styles['Normal'],
        fontSize=8,
        textColor=COLORS['light_text'],
        alignment=TA_CENTER
    ))

    return styles


def create_table(data, col_widths=None, header=True):
    """Create a formatted table from data."""
    if not data or len(data) == 0:
        return None

    # Calculate column widths if not provided
    if col_widths is None:
        num_cols = len(data[0]) if data else 1
        available_width = 6.5 * inch
        col_widths = [available_width / num_cols] * num_cols

    table = Table(data, colWidths=col_widths)

    style_commands = [
        ('FONTSIZE', (0, 0), (-1, -1), 9),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('GRID', (0, 0), (-1, -1), 0.5, COLORS['border']),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
        ('TOPPADDING', (0, 0), (-1, -1), 5),
        ('LEFTPADDING', (0, 0), (-1, -1), 5),
        ('RIGHTPADDING', (0, 0), (-1, -1), 5),
    ]

    if header and len(data) > 1:
        style_commands.extend([
            ('BACKGROUND', (0, 0), (-1, 0), COLORS['primary']),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, COLORS['bg_alt']]),
        ])

    table.setStyle(TableStyle(style_commands))
    return table


def process_content(content, styles):
    """Convert extracted content to flowables."""
    flowables = []

    if isinstance(content, str):
        # Simple text content
        if content.strip():
            flowables.append(Paragraph(content, styles['Body']))
    elif isinstance(content, dict):
        # Complex content with type
        content_type = content.get('type', 'text')

        if content_type == 'text':
            text = content.get('text', content.get('content', ''))
            if text:
                flowables.append(Paragraph(text, styles['Body']))

        elif content_type == 'quote':
            text = content.get('text', content.get('content', ''))
            if text:
                flowables.append(Paragraph(f'"{text}"', styles['Quote']))

        elif content_type == 'code':
            code = content.get('code', content.get('content', ''))
            lang = content.get('language', '')
            if code:
                # Truncate very long code blocks
                lines = code.split('\n')
                if len(lines) > 50:
                    code = '\n'.join(lines[:50]) + '\n... (truncated)'
                flowables.append(Paragraph(f"<b>{lang}</b>" if lang else "", styles['Note']))
                flowables.append(Preformatted(code, styles['CodeBlock']))

        elif content_type == 'table':
            headers = content.get('headers', [])
            rows = content.get('rows', content.get('data', []))
            if headers or rows:
                table_data = []
                if headers:
                    table_data.append(headers)
                table_data.extend(rows)
                if table_data:
                    table = create_table(table_data)
                    if table:
                        flowables.append(table)
                        flowables.append(Spacer(1, 10))

        elif content_type == 'diagram':
            desc = content.get('description', content.get('content', ''))
            if desc:
                flowables.append(Paragraph(f"<b>[Diagram]</b> {desc}", styles['Note']))

        elif content_type == 'note' or content_type == 'warning':
            text = content.get('text', content.get('content', ''))
            if text:
                prefix = "NOTE: " if content_type == 'note' else "WARNING: "
                flowables.append(Paragraph(f"<b>{prefix}</b>{text}", styles['Note']))

    return flowables


def process_section(section, styles, level=1):
    """Process a section and its subsections."""
    flowables = []

    # Get heading
    heading = section.get('heading', section.get('title', ''))

    # Choose style based on level
    if level == 1:
        style = styles['SectionHeader']
    else:
        style = styles['SubsectionHeader']

    if heading:
        flowables.append(Paragraph(heading, style))

    # Process content
    content = section.get('content', '')
    if content:
        flowables.extend(process_content(content, styles))

    # Process tables
    tables = section.get('tables', [])
    for table_data in tables:
        if isinstance(table_data, dict):
            flowables.extend(process_content({'type': 'table', **table_data}, styles))
        elif isinstance(table_data, list):
            table = create_table(table_data)
            if table:
                flowables.append(table)
                flowables.append(Spacer(1, 10))

    # Process code blocks
    code_blocks = section.get('code_blocks', section.get('codeBlocks', []))
    for code in code_blocks:
        flowables.extend(process_content({'type': 'code', **code} if isinstance(code, dict) else {'type': 'code', 'code': code}, styles))

    # Process diagrams
    diagrams = section.get('diagrams', [])
    for diagram in diagrams:
        flowables.extend(process_content({'type': 'diagram', **diagram} if isinstance(diagram, dict) else {'type': 'diagram', 'description': diagram}, styles))

    # Process subsections
    subsections = section.get('subsections', [])
    for subsection in subsections:
        flowables.extend(process_section(subsection, styles, level + 1))

    return flowables


def process_part(part, styles):
    """Process a complete part."""
    flowables = []

    # Part header
    part_num = part.get('part', '')
    title = part.get('title', '')

    if part_num or title:
        header_text = f"Part {part_num}: {title}" if part_num else title
        flowables.append(PageBreak())
        flowables.append(Paragraph(header_text, styles['PartHeader']))
        flowables.append(Spacer(1, 20))

    # Process sections
    sections = part.get('sections', part.get('subsections', []))
    for section in sections:
        flowables.extend(process_section(section, styles))

    return flowables


def load_json_files():
    """Load all extracted JSON files in order."""
    json_files = sorted(BASE_DIR.glob('extracted_pages_*.json'))
    all_sections = []

    for json_file in json_files:
        try:
            with open(json_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                # Handle different JSON structures (sections vs parts)
                sections = data.get('sections', [])
                parts = data.get('parts', [])
                combined = sections + parts
                all_sections.extend(combined)
                print(f"Loaded {json_file.name}: {len(combined)} items")
        except Exception as e:
            print(f"Error loading {json_file}: {e}")

    return all_sections


def create_title_page(styles):
    """Create the title page."""
    flowables = []

    flowables.append(Spacer(1, 2*inch))
    flowables.append(Paragraph("LUNA ENGINE BIBLE", styles['MainTitle']))
    flowables.append(Spacer(1, 0.3*inch))
    flowables.append(HRFlowable(width="60%", thickness=3, color=COLORS['primary']))
    flowables.append(Spacer(1, 0.3*inch))
    flowables.append(Paragraph("Version 3.0 — Formatted Edition", styles['SectionHeader']))
    flowables.append(Spacer(1, 0.5*inch))

    # Info table
    info_data = [
        ['Original Date:', 'January 30, 2026'],
        ['Status:', 'Complete (16 Parts + Supporting Documents)'],
        ['Formatted:', 'February 6, 2026'],
        ['Pages:', '320 pages (original)'],
    ]
    info_table = Table(info_data, colWidths=[1.8*inch, 4*inch])
    info_table.setStyle(TableStyle([
        ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 11),
        ('ALIGN', (0, 0), (0, -1), 'RIGHT'),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
    ]))
    flowables.append(info_table)

    flowables.append(Spacer(1, 1*inch))
    flowables.append(HRFlowable(width="80%", thickness=1, color=COLORS['border']))
    flowables.append(Spacer(1, 0.3*inch))

    flowables.append(Paragraph(
        '"We are not building an LLM. We are building everything around it."',
        styles['Quote']
    ))

    flowables.append(Spacer(1, 0.3*inch))
    flowables.append(Paragraph(
        "The LLM is like a GPU — a specialized compute resource for inference.<br/>"
        "We're building the game engine that calls it.",
        styles['Body']
    ))

    flowables.append(Spacer(1, 1.5*inch))
    flowables.append(Paragraph(
        '<i>"Luna is a file. This documentation describes that file."</i><br/><br/>'
        '<i>"The LLM renders thoughts. Luna is the mind having them."</i>',
        styles['Body']
    ))
    flowables.append(Spacer(1, 0.2*inch))
    flowables.append(Paragraph("— Ahab, December 2025", styles['Footer']))

    return flowables


def add_page_number(canvas, doc):
    """Add page numbers to each page."""
    page_num = canvas.getPageNumber()
    text = f"Luna Engine Bible v3.0 — Page {page_num}"
    canvas.saveState()
    canvas.setFont('Helvetica', 8)
    canvas.setFillColor(COLORS['light_text'])
    canvas.drawCentredString(letter[0] / 2, 0.5 * inch, text)
    canvas.restoreState()


def main():
    """Generate the complete formatted PDF."""
    print("=" * 60)
    print("LUNA ENGINE BIBLE v3.0 — PDF FORMATTER")
    print("=" * 60)

    # Create styles
    styles = create_styles()

    # Create document
    doc = SimpleDocTemplate(
        str(OUTPUT_PATH),
        pagesize=letter,
        rightMargin=0.75*inch,
        leftMargin=0.75*inch,
        topMargin=0.75*inch,
        bottomMargin=0.75*inch
    )

    # Build story
    story = []

    # Title page
    print("\nCreating title page...")
    story.extend(create_title_page(styles))

    # Load all JSON files
    print("\nLoading extracted content...")
    all_sections = load_json_files()
    print(f"Total sections loaded: {len(all_sections)}")

    # Process each section
    print("\nProcessing sections...")
    for i, section in enumerate(all_sections):
        try:
            part_flowables = process_part(section, styles)
            story.extend(part_flowables)
            if (i + 1) % 10 == 0:
                print(f"  Processed {i + 1}/{len(all_sections)} sections...")
        except Exception as e:
            print(f"  Warning: Error processing section {i}: {e}")

    # Build PDF
    print("\nBuilding PDF...")
    try:
        doc.build(story, onFirstPage=add_page_number, onLaterPages=add_page_number)
        print(f"\n{'=' * 60}")
        print(f"SUCCESS! PDF created at:")
        print(f"  {OUTPUT_PATH}")
        print(f"{'=' * 60}")
    except Exception as e:
        print(f"ERROR building PDF: {e}")
        raise


if __name__ == "__main__":
    main()
