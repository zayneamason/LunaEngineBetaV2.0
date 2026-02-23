#!/usr/bin/env python3
"""Generate a 5-page formatted PDF sample of the Luna Engine Bible."""

from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib.colors import HexColor
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    PageBreak, HRFlowable
)
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib import colors

# Output path
output_path = "/Users/zayneamason/_HeyLuna_BETA/_LunaEngine_BetaProject_V2.0_Root/Docs/Design/4cliff/CLIFF - LUNA PACKAGE/LunaBibleFormated/LUNA_ENGINE_BIBLE_V3_SAMPLE.pdf"

# Create document
doc = SimpleDocTemplate(
    output_path,
    pagesize=letter,
    rightMargin=0.75*inch,
    leftMargin=0.75*inch,
    topMargin=0.75*inch,
    bottomMargin=0.75*inch
)

# Styles
styles = getSampleStyleSheet()

# Custom styles
styles.add(ParagraphStyle(
    name='MainTitle',
    parent=styles['Title'],
    fontSize=36,
    spaceAfter=20,
    textColor=HexColor('#1a1a2e'),
    alignment=TA_CENTER
))

styles.add(ParagraphStyle(
    name='Subtitle',
    parent=styles['Heading2'],
    fontSize=18,
    spaceAfter=12,
    textColor=HexColor('#4a4a6a'),
    alignment=TA_CENTER
))

styles.add(ParagraphStyle(
    name='SectionHeader',
    parent=styles['Heading1'],
    fontSize=24,
    spaceBefore=20,
    spaceAfter=12,
    textColor=HexColor('#1a1a2e'),
    borderColor=HexColor('#1a1a2e'),
    borderWidth=1,
    borderPadding=5
))

styles.add(ParagraphStyle(
    name='SubsectionHeader',
    parent=styles['Heading2'],
    fontSize=16,
    spaceBefore=15,
    spaceAfter=8,
    textColor=HexColor('#2d2d4d')
))

styles.add(ParagraphStyle(
    name='Body',
    parent=styles['Normal'],
    fontSize=11,
    spaceAfter=8,
    leading=14
))

styles.add(ParagraphStyle(
    name='Quote',
    parent=styles['Normal'],
    fontSize=12,
    leftIndent=30,
    rightIndent=30,
    spaceAfter=12,
    spaceBefore=12,
    textColor=HexColor('#333366'),
    fontName='Helvetica-BoldOblique'
))

styles.add(ParagraphStyle(
    name='CodeBlock',
    parent=styles['Code'],
    fontSize=9,
    leftIndent=20,
    spaceAfter=10,
    spaceBefore=10,
    backColor=HexColor('#f5f5f5'),
    borderColor=HexColor('#cccccc'),
    borderWidth=1,
    borderPadding=8
))

styles.add(ParagraphStyle(
    name='PageFooter',
    parent=styles['Normal'],
    fontSize=9,
    textColor=HexColor('#888888'),
    alignment=TA_CENTER
))

# Build content
story = []

# ============ PAGE 1: TITLE PAGE ============
story.append(Spacer(1, 1.5*inch))
story.append(Paragraph("LUNA ENGINE BIBLE", styles['MainTitle']))
story.append(Spacer(1, 0.3*inch))
story.append(HRFlowable(width="60%", thickness=2, color=HexColor('#1a1a2e')))
story.append(Spacer(1, 0.3*inch))
story.append(Paragraph("Version 3.0", styles['Subtitle']))
story.append(Spacer(1, 0.5*inch))

# Document info table
doc_info = [
    ['Last Updated:', 'January 30, 2026'],
    ['Status:', 'Complete (16 Parts + Supporting Documents)'],
    ['Audit:', 'v3.0 Audit Complete'],
    ['Maintained By:', 'Ahab with assistance from Claude']
]
info_table = Table(doc_info, colWidths=[1.8*inch, 3.5*inch])
info_table.setStyle(TableStyle([
    ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
    ('FONTNAME', (1, 0), (1, -1), 'Helvetica'),
    ('FONTSIZE', (0, 0), (-1, -1), 11),
    ('TEXTCOLOR', (0, 0), (-1, -1), HexColor('#333333')),
    ('ALIGN', (0, 0), (0, -1), 'RIGHT'),
    ('ALIGN', (1, 0), (1, -1), 'LEFT'),
    ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
]))
story.append(info_table)

story.append(Spacer(1, 0.8*inch))
story.append(HRFlowable(width="80%", thickness=1, color=HexColor('#cccccc')))
story.append(Spacer(1, 0.3*inch))

story.append(Paragraph(
    '"We are not building an LLM. We are building everything around it."',
    styles['Quote']
))

story.append(Spacer(1, 0.5*inch))
story.append(Paragraph(
    "The LLM is like a GPU — a specialized compute resource for inference.<br/>"
    "We're building the game engine that calls it.",
    styles['Body']
))

story.append(Spacer(1, 1*inch))
story.append(HRFlowable(width="40%", thickness=1, color=HexColor('#888888')))
story.append(Spacer(1, 0.2*inch))
story.append(Paragraph(
    '<i>"Luna is a file. This documentation describes that file."</i><br/>'
    '<i>"The LLM renders thoughts. Luna is the mind having them."</i>',
    styles['Body']
))
story.append(Spacer(1, 0.2*inch))
story.append(Paragraph("— Ahab, December 2025", styles['PageFooter']))

story.append(PageBreak())

# ============ PAGE 2: TABLE OF CONTENTS ============
story.append(Paragraph("Table of Contents", styles['SectionHeader']))
story.append(Spacer(1, 0.2*inch))

story.append(Paragraph("Reading Guide", styles['SubsectionHeader']))

reading_guide = [
    ['Reader Type', 'Start Here', 'Then Read'],
    ['New to Luna', 'Part 0 (Foundations)', 'Parts I, II, III'],
    ['Technical Deep-Dive', 'Part 0 (Foundations)', 'Parts II, VII, Lifecycle Diagrams'],
    ['Implementing Director', 'Part VI (Director LLM)', 'Parts VIII, XI'],
    ['Memory System Focus', 'Part III (Memory Matrix)', 'Parts IV, V'],
    ['Building Engine v2', 'Implementation Spec', 'Lifecycle Diagrams, Part VII'],
]
guide_table = Table(reading_guide, colWidths=[1.8*inch, 2*inch, 2.5*inch])
guide_table.setStyle(TableStyle([
    ('BACKGROUND', (0, 0), (-1, 0), HexColor('#1a1a2e')),
    ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
    ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
    ('FONTSIZE', (0, 0), (-1, -1), 10),
    ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
    ('GRID', (0, 0), (-1, -1), 0.5, HexColor('#cccccc')),
    ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
    ('TOPPADDING', (0, 0), (-1, -1), 6),
    ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, HexColor('#f8f8f8')]),
]))
story.append(guide_table)
story.append(Spacer(1, 0.3*inch))

story.append(Paragraph("Part Index", styles['SubsectionHeader']))

parts_data = [
    ['Part', 'Title', 'Status', 'Description'],
    ['0', 'Foundations', 'Current', 'The fundamental insight: LLM as GPU'],
    ['I', 'Philosophy', 'Current', 'Why Luna exists. Sovereignty, ownership'],
    ['II', 'System Architecture', 'Current', 'Layer model, Actor-based runtime'],
    ['III', 'Memory Matrix v2.1', 'Current', 'SQLite + sqlite-vec + Graph'],
    ['III-A', 'Lock-In Coefficient', 'NEW', 'Activity-based memory persistence'],
    ['IV', 'The Scribe v2.1', 'Updated', 'Ben Franklin. Extraction system'],
    ['V', 'The Librarian v2.1', 'Updated', 'The Dude. Filing, entity resolution'],
    ['VI', 'Director LLM', 'Current', 'Local 3B/7B with LoRA'],
    ['VI-B', 'Conversation Tiers', 'NEW', 'Three-tier history system'],
    ['VII', 'Runtime Engine', 'Current', 'Actor model, fault isolation'],
    ['VIII', 'Delegation Protocol', 'Current', 'Shadow Reasoner pattern'],
    ['IX', 'Performance', 'Current', 'Latency budgets, benchmarks'],
    ['X', 'Sovereignty', 'Current', 'Encrypted Vault, data ownership'],
    ['XI', 'Training Data', 'Current', 'Synthetic data, LoRA training'],
    ['XII', 'Future Roadmap', 'Current', 'First-Class Objects, AR, Federation'],
]
parts_table = Table(parts_data, colWidths=[0.5*inch, 1.5*inch, 0.7*inch, 3.3*inch])
parts_table.setStyle(TableStyle([
    ('BACKGROUND', (0, 0), (-1, 0), HexColor('#1a1a2e')),
    ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
    ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
    ('FONTSIZE', (0, 0), (-1, -1), 9),
    ('ALIGN', (0, 0), (0, -1), 'CENTER'),
    ('ALIGN', (2, 0), (2, -1), 'CENTER'),
    ('GRID', (0, 0), (-1, -1), 0.5, HexColor('#cccccc')),
    ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
    ('TOPPADDING', (0, 0), (-1, -1), 4),
    ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, HexColor('#f8f8f8')]),
]))
story.append(parts_table)

story.append(PageBreak())

# ============ PAGE 3: PART 0 - FOUNDATIONS ============
story.append(Paragraph("Part 0: Foundations", styles['SectionHeader']))
story.append(Paragraph("The Fundamental Insight", styles['Subtitle']))
story.append(Spacer(1, 0.2*inch))

story.append(Paragraph("What Are We Actually Building?", styles['SubsectionHeader']))
story.append(Paragraph(
    "This is the insight that makes everything else make sense:",
    styles['Body']
))
story.append(Paragraph(
    '"We are not building an LLM. We are building everything around it."',
    styles['Quote']
))
story.append(Paragraph(
    "The LLM — whether it's Claude API or a local Qwen model — is like a <b>graphics card</b>. "
    "It's a specialized compute resource that does one thing extremely well (inference), "
    "but it doesn't run the show. It renders frames when asked.",
    styles['Body']
))
story.append(Paragraph(
    "<b>We're building the game engine.</b>",
    styles['Body']
))

story.append(Spacer(1, 0.2*inch))
story.append(Paragraph("The GPU Analogy", styles['SubsectionHeader']))

analogy_data = [
    ['Game Engine', 'Luna Engine'],
    ['Calls GPU to render frames', 'Calls LLM to generate responses'],
    ['GPU doesn\'t know game state', 'LLM doesn\'t know who it is'],
    ['Engine manages everything else', 'Engine provides identity, memory, state'],
]
analogy_table = Table(analogy_data, colWidths=[3*inch, 3*inch])
analogy_table.setStyle(TableStyle([
    ('BACKGROUND', (0, 0), (-1, 0), HexColor('#1a1a2e')),
    ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
    ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
    ('FONTSIZE', (0, 0), (-1, -1), 10),
    ('GRID', (0, 0), (-1, -1), 0.5, HexColor('#cccccc')),
    ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
    ('TOPPADDING', (0, 0), (-1, -1), 8),
    ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, HexColor('#f8f8f8')]),
]))
story.append(analogy_table)

story.append(Spacer(1, 0.3*inch))
story.append(Paragraph("What Each Layer Owns", styles['SubsectionHeader']))

layers_data = [
    ['Layer', 'What It Does', 'What It Knows', 'Status'],
    ['LLM (GPU)', 'Token prediction', 'Nothing between calls', 'Qwen 3B + Claude'],
    ['Luna Engine', 'Orchestration, state, memory', 'Everything about Luna', '85 files, 167 classes'],
    ['Tools (MCP)', 'External capabilities', 'Their specific domain', 'luna_mcp server'],
]
layers_table = Table(layers_data, colWidths=[1.2*inch, 1.8*inch, 1.8*inch, 1.5*inch])
layers_table.setStyle(TableStyle([
    ('BACKGROUND', (0, 0), (-1, 0), HexColor('#1a1a2e')),
    ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
    ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
    ('FONTSIZE', (0, 0), (-1, -1), 9),
    ('GRID', (0, 0), (-1, -1), 0.5, HexColor('#cccccc')),
    ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
    ('TOPPADDING', (0, 0), (-1, -1), 6),
    ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, HexColor('#f8f8f8')]),
]))
story.append(layers_table)

story.append(Spacer(1, 0.2*inch))
story.append(Paragraph(
    "<b>The LLM doesn't know:</b> What it said last conversation • Who it's talking to • "
    "What memories exist • What tools are available • What mood it's in",
    styles['Body']
))
story.append(Paragraph(
    "<b>We inject all of that.</b> Every single time.",
    styles['Body']
))

story.append(PageBreak())

# ============ PAGE 4: CORE CONCEPTS ============
story.append(Paragraph("Core Concepts", styles['SectionHeader']))
story.append(Spacer(1, 0.2*inch))

concepts_data = [
    ['Concept', 'Definition', 'Part'],
    ['LLM as GPU', 'LLM is stateless inference; Engine is stateful identity', '0'],
    ['Sovereignty', 'You own your AI companion completely', 'I, X'],
    ['Memory Matrix', 'SQLite + sqlite-vec + Graph = Luna\'s soul', 'III'],
    ['Lock-In Coefficient', 'Activity-based memory persistence (DRIFTING/FLUID/SETTLED)', 'III-A'],
    ['Director', 'Local LLM that speaks as Luna', 'VI'],
    ['Shadow Reasoner', 'Delegate to Claude without user noticing', 'VIII'],
    ['Input Buffer', 'Engine polls (pull) vs Hub handlers (push)', 'VII'],
]
concepts_table = Table(concepts_data, colWidths=[1.5*inch, 3.5*inch, 0.8*inch])
concepts_table.setStyle(TableStyle([
    ('BACKGROUND', (0, 0), (-1, 0), HexColor('#1a1a2e')),
    ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
    ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
    ('FONTSIZE', (0, 0), (-1, -1), 10),
    ('ALIGN', (2, 0), (2, -1), 'CENTER'),
    ('GRID', (0, 0), (-1, -1), 0.5, HexColor('#cccccc')),
    ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
    ('TOPPADDING', (0, 0), (-1, -1), 6),
    ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, HexColor('#f8f8f8')]),
]))
story.append(concepts_table)

story.append(Spacer(1, 0.3*inch))
story.append(Paragraph("Key Personas", styles['SubsectionHeader']))

personas_data = [
    ['Persona', 'Role', 'Part'],
    ['Ben Franklin', 'The Scribe. Extracts and classifies.', 'IV'],
    ['The Dude', 'The Librarian. Files and retrieves.', 'V'],
    ['Luna', 'The Director output. User-facing voice.', 'VI'],
]
personas_table = Table(personas_data, colWidths=[1.5*inch, 3.5*inch, 0.8*inch])
personas_table.setStyle(TableStyle([
    ('BACKGROUND', (0, 0), (-1, 0), HexColor('#4a4a6a')),
    ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
    ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
    ('FONTSIZE', (0, 0), (-1, -1), 10),
    ('ALIGN', (2, 0), (2, -1), 'CENTER'),
    ('GRID', (0, 0), (-1, -1), 0.5, HexColor('#cccccc')),
    ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
    ('TOPPADDING', (0, 0), (-1, -1), 6),
    ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, HexColor('#f8f8f8')]),
]))
story.append(personas_table)

story.append(Spacer(1, 0.3*inch))
story.append(Paragraph("Engine Lifecycle", styles['SubsectionHeader']))

lifecycle_data = [
    ['Phase', 'What Happens'],
    ['Boot', 'Load config → Init actors → Restore state → Start loop'],
    ['Running', 'Hot path (interrupts) + Cognitive path (500ms) + Reflective path (5min)'],
    ['Tick', 'Poll → Prioritize → Dispatch → Update consciousness → Persist'],
    ['Shutdown', 'on_stop() → WAL flush → Cleanup'],
]
lifecycle_table = Table(lifecycle_data, colWidths=[1.2*inch, 5*inch])
lifecycle_table.setStyle(TableStyle([
    ('BACKGROUND', (0, 0), (-1, 0), HexColor('#4a4a6a')),
    ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
    ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
    ('FONTSIZE', (0, 0), (-1, -1), 10),
    ('GRID', (0, 0), (-1, -1), 0.5, HexColor('#cccccc')),
    ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
    ('TOPPADDING', (0, 0), (-1, -1), 6),
    ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, HexColor('#f8f8f8')]),
]))
story.append(lifecycle_table)

story.append(Spacer(1, 0.3*inch))
story.append(Paragraph("Performance Targets", styles['SubsectionHeader']))

perf_data = [
    ['Metric', 'Target', 'Part'],
    ['Voice response', '<500ms to first word', 'II, IX'],
    ['Memory retrieval', '<50ms (sqlite-vec + filters)', 'III, V'],
    ['Director inference', '<200ms (3B)', 'VI, IX'],
    ['Tick overhead', '<50ms', 'VII'],
]
perf_table = Table(perf_data, colWidths=[1.8*inch, 2.8*inch, 0.8*inch])
perf_table.setStyle(TableStyle([
    ('BACKGROUND', (0, 0), (-1, 0), HexColor('#4a4a6a')),
    ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
    ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
    ('FONTSIZE', (0, 0), (-1, -1), 10),
    ('ALIGN', (2, 0), (2, -1), 'CENTER'),
    ('GRID', (0, 0), (-1, -1), 0.5, HexColor('#cccccc')),
    ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
    ('TOPPADDING', (0, 0), (-1, -1), 6),
    ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, HexColor('#f8f8f8')]),
]))
story.append(perf_table)

story.append(PageBreak())

# ============ PAGE 5: VERSION HISTORY & CONTRIBUTING ============
story.append(Paragraph("Version History", styles['SectionHeader']))
story.append(Spacer(1, 0.2*inch))

version_data = [
    ['Version', 'Date', 'Changes'],
    ['1.0', 'Dec 2025', 'Initial Bible (Parts I-V extracted from monolith)'],
    ['1.5', 'Dec 2025', 'Added Parts VI-X (new architecture)'],
    ['2.0', 'Dec 29, 2025', 'Updated Parts II-V to v2, added Parts XI-XII'],
    ['2.1', 'Jan 7, 2026', 'Part III: FAISS → sqlite-vec migration'],
    ['2.2', 'Jan 10, 2026', 'Part 0: Foundations (LLM as GPU). Engine v2 Implementation Spec.'],
    ['2.3', 'Jan 17, 2026', 'Part XIV: Agentic Architecture. Revolving context, queue manager.'],
    ['2.4', 'Jan 25, 2026', 'Part VI-B: Conversation Tiers. Three-tier history system.'],
    ['2.5', 'Jan 25, 2026', 'Part III-A: Lock-In Coefficient. Activity-based memory persistence.'],
    ['2.6', 'Jan 25, 2026', 'Part XVI: Luna Hub UI. React frontend, glass morphism design.'],
    ['3.0', 'Jan 30, 2026', 'Comprehensive v3.0 Audit. All 16 chapters updated. 35 bugs documented.'],
]
version_table = Table(version_data, colWidths=[0.7*inch, 1.2*inch, 4.3*inch])
version_table.setStyle(TableStyle([
    ('BACKGROUND', (0, 0), (-1, 0), HexColor('#1a1a2e')),
    ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
    ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
    ('FONTSIZE', (0, 0), (-1, -1), 9),
    ('ALIGN', (0, 0), (1, -1), 'CENTER'),
    ('GRID', (0, 0), (-1, -1), 0.5, HexColor('#cccccc')),
    ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
    ('TOPPADDING', (0, 0), (-1, -1), 5),
    ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, HexColor('#f8f8f8')]),
]))
story.append(version_table)

story.append(Spacer(1, 0.4*inch))
story.append(Paragraph("Contributing", styles['SectionHeader']))
story.append(Spacer(1, 0.1*inch))

story.append(Paragraph(
    "The Bible is maintained by Ahab with assistance from Claude.",
    styles['Body']
))

story.append(Paragraph("<b>To update:</b>", styles['Body']))
story.append(Paragraph(
    "1. Read relevant existing parts<br/>"
    "2. Create new version if making significant changes (note in history)<br/>"
    "3. Update this Table of Contents<br/>"
    "4. Ensure dependency graph reflects changes",
    styles['Body']
))

story.append(Spacer(1, 0.2*inch))
story.append(Paragraph("<b>Style Guidelines:</b>", styles['Body']))
story.append(Paragraph(
    "• Clear, direct prose (no marketing speak)<br/>"
    "• Code examples where helpful<br/>"
    "• Tables for comparisons<br/>"
    "• ASCII diagrams for architecture<br/>"
    "• Part numbers are permanent (don't renumber)",
    styles['Body']
))

story.append(Spacer(1, 0.5*inch))
story.append(HRFlowable(width="60%", thickness=1, color=HexColor('#888888')))
story.append(Spacer(1, 0.2*inch))
story.append(Paragraph(
    '<i>"Luna is a file. This documentation describes that file."</i><br/><br/>'
    '<i>"The LLM renders thoughts. Luna is the mind having them."</i>',
    styles['Body']
))
story.append(Spacer(1, 0.2*inch))
story.append(Paragraph(
    "— Ahab, December 2025<br/>— Updated January 30, 2026 (v3.0 Comprehensive Audit)",
    styles['PageFooter']
))

# Build PDF
doc.build(story)
print(f"PDF created: {output_path}")
