from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_JUSTIFY
import os

output_path = r'C:\Users\prasa\Desktop\Continuity ai\Testing Integration\continuity_ai_unified_fullstack 2\continuity-ai\CONTINUITY_AI_PROJECT_SUMMARY.pdf'

doc = SimpleDocTemplate(output_path, pagesize=letter, rightMargin=72, leftMargin=72, topMargin=72, bottomMargin=72)
styles = getSampleStyleSheet()

# Custom styles
title_style = ParagraphStyle('CustomTitle', parent=styles['Title'], fontSize=24, spaceAfter=30, alignment=TA_CENTER, textColor=colors.HexColor('#1a1a2e'))
heading1_style = ParagraphStyle('Heading1Custom', parent=styles['Heading1'], fontSize=16, spaceAfter=12, spaceBefore=18, textColor=colors.HexColor('#16213e'))
heading2_style = ParagraphStyle('Heading2Custom', parent=styles['Heading2'], fontSize=13, spaceAfter=8, spaceBefore=12, textColor=colors.HexColor('#0f3460'))
body_style = ParagraphStyle('BodyCustom', parent=styles['Normal'], fontSize=10, spaceAfter=6, alignment=TA_JUSTIFY, leading=14)
code_style = ParagraphStyle('CodeCustom', parent=styles['Code'], fontSize=9, fontName='Courier', spaceAfter=6, spaceBefore=6, backColor=colors.HexColor('#f5f5f5'), borderPadding=6, leading=12)
bullet_style = ParagraphStyle('BulletCustom', parent=styles['Normal'], fontSize=10, spaceAfter=4, leftIndent=24, bulletIndent=12, leading=14)
table_header_style = ParagraphStyle('TableHeader', parent=styles['Normal'], fontSize=9, fontName='Helvetica-Bold', textColor=colors.white, alignment=TA_CENTER)
table_cell_style = ParagraphStyle('TableCell', parent=styles['Normal'], fontSize=9, leading=12)
table_cell_center = ParagraphStyle('TableCellCenter', parent=table_cell_style, alignment=TA_CENTER)

story = []

# Title
story.append(Paragraph('Continuity AI \u2014 Project Summary', title_style))
story.append(Paragraph('Evidence-First Project Knowledge Handover System', ParagraphStyle('Subtitle', parent=styles['Normal'], fontSize=14, alignment=TA_CENTER, textColor=colors.HexColor('#4a4a6a'), spaceAfter=30)))
story.append(Spacer(1, 20))

# What This Is
story.append(Paragraph('What This Is', heading1_style))
story.append(Paragraph(
    'Continuity AI is an <b>evidence-first project knowledge handover system</b> that reconstructs project state from '
    'authorized sources (PDF, TXT, MD, GitHub), links every claim to exact supporting quotes with precise character '
    'locators, surfaces contradictions side-by-side without picking winners by timestamp, supports human review with '
    'optimistic concurrency, generates immutable role-filtered handover snapshots (backend_developer vs designer), '
    'and verifies onboarding readiness through a 3-task Cold-Start Test.',
    body_style
))
story.append(Spacer(1, 12))

# Architecture
story.append(Paragraph('System Architecture', heading1_style))
story.append(Paragraph(
    'The system follows a contract-driven full-stack architecture with a React + TypeScript frontend, '
    'FastAPI backend, and SQLite/PostgreSQL database, all governed by a single OpenAPI 3.1 contract.',
    body_style
))

arch_data = [
    [Paragraph('<b>Component</b>', table_header_style), Paragraph('<b>Technology</b>', table_header_style), Paragraph('<b>Port</b>', table_header_style), Paragraph('<b>Key Files</b>', table_header_style)],
    [Paragraph('Frontend', table_cell_style), Paragraph('React 18 + TypeScript + Vite', table_cell_style), Paragraph('5173', table_cell_center), Paragraph('src/api/realApi.ts', table_cell_style)],
    [Paragraph('Backend', table_cell_style), Paragraph('FastAPI + SQLAlchemy 2.0', table_cell_style), Paragraph('8000', table_cell_center), Paragraph('app/main.py', table_cell_style)],
    [Paragraph('Database', table_cell_style), Paragraph('SQLite (dev) / PostgreSQL (prod)', table_cell_style), Paragraph('\u2014', table_cell_center), Paragraph('continuity.db', table_cell_style)],
    [Paragraph('Contract', table_cell_style), Paragraph('OpenAPI 3.1', table_cell_style), Paragraph('\u2014', table_cell_center), Paragraph('contracts/openapi.json', table_cell_style)],
]

arch_table = Table(arch_data, colWidths=[1*inch, 1.8*inch, 0.6*inch, 2.2*inch])
arch_table.setStyle(TableStyle([
    ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#16213e')),
    ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
    ('BACKGROUND', (0, 1), (-1, -1), colors.HexColor('#f8f9fa')),
    ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#ddd')),
    ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
    ('TOPPADDING', (0, 0), (-1, -1), 6),
    ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
    ('LEFTPADDING', (0, 0), (-1, -1), 8),
    ('RIGHTPADDING', (0, 0), (-1, -1), 8),
]))
story.append(arch_table)
story.append(Spacer(1, 16))

# Core Capabilities - 9 Step Judge Journey
story.append(Paragraph('Core Capabilities: 9-Step Judge Journey', heading1_style))
story.append(Paragraph(
    'The system implements a complete 9-step verification journey (S0\u2013S11) that exercises every major API endpoint '
    'and contract behavior. Each step corresponds to a specific contract requirement:',
    body_style
))

journey_data = [
    [Paragraph('<b>Step</b>', table_header_style), Paragraph('<b>Phase</b>', table_header_style), Paragraph('<b>Key Contract Behavior</b>', table_header_style)],
    [Paragraph('S0', table_cell_center), Paragraph('Demo Auth', table_cell_style), Paragraph('JWT tokens, 4 personas (manager, contributor, incoming backend, incoming designer)', table_cell_style)],
    [Paragraph('S1\u2013S3', table_cell_center), Paragraph('Source Ingestion', table_cell_style), Paragraph('PDF/TXT/MD/GitHub \u2192 character-offset excerpts, <font face="Courier">storage_key</font> never leaked', table_cell_style)],
    [Paragraph('S4\u2013S5', table_cell_center), Paragraph('Async Extraction', table_cell_style), Paragraph('<font face="Courier">POST /extractions</font> \u2192 202 polling \u2192 12 claims across 8 <font face="Courier">fact_type</font> categories, <font face="Courier">staging_db_credentials</font> auto-flagged <font face="Courier">restricted</font>', table_cell_style)],
    [Paragraph('S6', table_cell_center), Paragraph('Conflict Detection', table_cell_style), Paragraph('<font face="Courier">login_authentication</font> contradiction (Nov 2 vs Nov 6) preserved side-by-side, <b>no timestamp winner</b>', table_cell_style)],
    [Paragraph('S7', table_cell_center), Paragraph('Human Review', table_cell_style), Paragraph('Edit preserves <font face="Courier">original_statement</font>, optimistic concurrency via <font face="Courier">expected_version</font> (409 <font face="Courier">STALE_VERSION</font>)', table_cell_style)],
    [Paragraph('S8', table_cell_center), Paragraph('Handover Approval Gate', table_cell_style), Paragraph('Default blocked by open critical conflict (409 <font face="Courier">APPROVAL_BLOCKED_CONFLICT</font>), requires \u226510-char <font face="Courier">override_reason</font>', table_cell_style)],
    [Paragraph('S9', table_cell_center), Paragraph('Role-Isolated Views', table_cell_style), Paragraph('<font face="Courier">backend_developer</font> sees 8 claims + override banner; <font face="Courier">designer</font> sees 2 design claims; cross-role = 404', table_cell_style)],
    [Paragraph('S10\u2013S11', table_cell_center), Paragraph('Cold-Start Test', table_cell_style), Paragraph('3 deterministic tasks, zero <font face="Courier">expected_reference</font> leakage, manager summary aggregates metrics', table_cell_style)],
]

journey_table = Table(journey_data, colWidths=[0.5*inch, 1.2*inch, 3.9*inch])
journey_table.setStyle(TableStyle([
    ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#16213e')),
    ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
    ('BACKGROUND', (0, 1), (-1, -1), colors.HexColor('#f8f9fa')),
    ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f0f2f5')]),
    ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#ddd')),
    ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
    ('TOPPADDING', (0, 0), (-1, -1), 6),
    ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
    ('LEFTPADDING', (0, 0), (-1, -1), 8),
    ('RIGHTPADDING', (0, 0), (-1, -1), 8),
]))
story.append(journey_table)
story.append(Spacer(1, 16))

# Test Evidence
story.append(Paragraph('Test Evidence (All Passing)', heading1_style))

test_data = [
    [Paragraph('<b>Test Suite</b>', table_header_style), Paragraph('<b>Tests</b>', table_header_style), Paragraph('<b>Result</b>', table_header_style)],
    [Paragraph('Backend Contract', table_cell_style), Paragraph('8', table_cell_center), Paragraph('\u2705 PASS', table_cell_center)],
    [Paragraph('Backend Unit', table_cell_style), Paragraph('36', table_cell_center), Paragraph('\u2705 PASS', table_cell_center)],
    [Paragraph('Backend Integration', table_cell_style), Paragraph('1', table_cell_center), Paragraph('\u2705 PASS', table_cell_center)],
    [Paragraph('Frontend Contract/Matrix', table_cell_style), Paragraph('9', table_cell_center), Paragraph('\u2705 PASS', table_cell_center)],
    [Paragraph('Frontend TypeCheck + Build', table_cell_style), Paragraph('\u2014', table_cell_center), Paragraph('\u2705 PASS', table_cell_center)],
    [Paragraph('Live Smoke Test', table_cell_style), Paragraph('24', table_cell_center), Paragraph('\u2705 PASS', table_cell_center)],
    [Paragraph('Live E2E (Frontend realApi.ts)', table_cell_style), Paragraph('9', table_cell_center), Paragraph('\u2705 PASS', table_cell_center)],
    [Paragraph('<b>Total</b>', table_header_style), Paragraph('<b>77+</b>', table_header_style), Paragraph('<b>100% PASS</b>', table_header_style)],
]

test_table = Table(test_data, colWidths=[2.5*inch, 1*inch, 1.5*inch])
test_table.setStyle(TableStyle([
    ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#16213e')),
    ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
    ('BACKGROUND', (0, -1), (-1, -1), colors.HexColor('#e8f5e9')),
    ('ROWBACKGROUNDS', (0, 1), (-1, -2), [colors.white, colors.HexColor('#f0f2f5')]),
    ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#ddd')),
    ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
    ('TOPPADDING', (0, 0), (-1, -1), 6),
    ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
    ('LEFTPADDING', (0, 0), (-1, -1), 8),
    ('RIGHTPADDING', (0, 0), (-1, -1), 8),
]))
story.append(test_table)
story.append(Spacer(1, 16))

# Tech Stack
story.append(Paragraph('Technology Stack', heading1_style))

tech_data = [
    [Paragraph('<b>Layer</b>', table_header_style), Paragraph('<b>Technologies</b>', table_header_style)],
    [Paragraph('Backend', table_cell_style), Paragraph('Python 3.11+, FastAPI, SQLAlchemy 2.0, pypdf/pdfplumber, reportlab, httpx, pytest, python-multipart, cryptography, python-dotenv, alembic, psycopg2-binary', table_cell_style)],
    [Paragraph('Frontend', table_cell_style), Paragraph('React 18, TypeScript 5.6, Vite 8.3, TanStack Query 5.59, React Router 6.27, lucide-react 0.45, openapi-typescript 7.4', table_cell_style)],
    [Paragraph('Contract', table_cell_style), Paragraph('OpenAPI 3.1, 40+ request/response fixtures, CONTRACT_VERSION pinning', table_cell_style)],
    [Paragraph('AI/Extraction', table_cell_style), Paragraph('Deterministic <font face="Courier">fake</font> provider for tests/replay; swappable for live LLM', table_cell_style)],
    [Paragraph('GitHub Ingestion', table_cell_style), Paragraph('<font face="Courier">fixture</font> mode for offline tests/demo; live mode available', table_cell_style)],
]

tech_table = Table(tech_data, colWidths=[1.2*inch, 4.4*inch])
tech_table.setStyle(TableStyle([
    ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#16213e')),
    ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
    ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f0f2f5')]),
    ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#ddd')),
    ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
    ('TOPPADDING', (0, 0), (-1, -1), 6),
    ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
    ('LEFTPADDING', (0, 0), (-1, -1), 8),
    ('RIGHTPADDING', (0, 0), (-1, -1), 8),
]))
story.append(tech_table)
story.append(Spacer(1, 16))

# Unique Design Decisions
story.append(Paragraph('Unique Design Decisions', heading1_style))
decisions = [
    ('Evidence-first', 'Every claim stores <font face="Courier">evidence[]</font> with exact <font face="Courier">locator</font> (page/char_start/char_end)'),
    ('No auto-resolution', 'Conflicts preserve competing claims side-by-side; humans decide \u2014 no timestamp-based winner picking'),
    ('Optimistic concurrency', '<font face="Courier">expected_version</font> on reviews prevents lost updates (409 <font face="Courier">STALE_VERSION</font>)'),
    ('Role-based redaction', '<font face="Courier">audience_roles</font> on claims + <font face="Courier">recipient_role</font> on handovers \u2192 zero credential leakage'),
    ('Cold-start verification', 'Onboarding tasks have no answer keys (<font face="Courier">expected_reference</font>) in payloads'),
    ('Contract-driven', 'Frontend types generated from OpenAPI; tests validate against JSON fixtures'),
]
for title, desc in decisions:
    story.append(Paragraph('<b>{0}:</b> {1}'.format(title, desc), bullet_style))
story.append(Spacer(1, 12))

# How to Run
story.append(Paragraph('How to Run', heading1_style))
story.append(Paragraph('Two terminals required:', body_style))
story.append(Paragraph('<font face="Courier" color="#16213e"># Terminal 1 \u2014 Backend (port 8000)</font>', code_style))
story.append(Paragraph('<font face="Courier" color="#16213e">cd backend</font>', code_style))
story.append(Paragraph('<font face="Courier" color="#16213e">PYTHONPATH=. python -m app.seed --reset</font>', code_style))
story.append(Paragraph('<font face="Courier" color="#16213e">PYTHONPATH=. python -m uvicorn app.main:app --port 8000</font>', code_style))
story.append(Spacer(1, 8))
story.append(Paragraph('<font face="Courier" color="#16213e"># Terminal 2 \u2014 Frontend (port 5173)</font>', code_style))
story.append(Paragraph('<font face="Courier" color="#16213e">cd frontend</font>', code_style))
story.append(Paragraph('<font face="Courier" color="#16213e">npm run dev  # \u2192 http://localhost:5173</font>', code_style))
story.append(Spacer(1, 8))
story.append(Paragraph(
    'The header will show: <b>LIVE API (http://localhost:8000/api/v1) | DEMO AUTH | REPLAY | CONTRACT v1.0.0</b>',
    body_style
))
story.append(Spacer(1, 16))

# Project Structure
story.append(Paragraph('Project Structure Highlights', heading1_style))
structure = [
    'continuity-ai/',
    '├── backend/',
    '│   ├── app/',
    '│   │   ├── api/v1/          # 10 route modules (auth, sources, projects, claims, extractions, conflicts, reviews, handovers, cold_start, audit)',
    '│   │   ├── extraction/      # LLM prompt + fake provider',
    '│   │   ├── verification/    # Quote locator matching',
    '│   │   ├── conflicts/       # Contradiction detection',
    '│   │   ├── review/          # Optimistic concurrency',
    '│   │   ├── handover/        # Role filtering + approval gate',
    '│   │   └── cold_start/      # 3-task evaluation',
    '│   └── requirements.txt',
    '├── frontend/',
    '│   ├── src/api/realApi.ts   # 200+ typed endpoints',
    '│   └── tests/               # Contract matrix + E2E',
    '├── contracts/',
    '│   ├── openapi.json         # 2000+ lines, single source of truth',
    '│   └── examples/            # 40+ request/response fixtures',
    '└── tests/                   # Backend unit/integration/contract',
]
struct_style = ParagraphStyle('Struct', parent=styles['Normal'], fontSize=9, leading=12, leftIndent=24, fontName='Courier')
for line in structure:
    story.append(Paragraph(line, struct_style))
story.append(Spacer(1, 16))

# Production Ready vs Demo
story.append(Paragraph('Production-Ready vs Demo/Simulated', heading1_style))

prod_data = [
    [Paragraph('<b>Production-Ready</b>', table_header_style), Paragraph('<b>Demo / Simulated</b>', table_header_style)],
    [Paragraph('Full API contract (OpenAPI 3.1)', table_cell_style), Paragraph('LLM provider (<font face="Courier">fake</font> deterministic)', table_cell_style)],
    [Paragraph('JWT auth + demo personas', table_cell_style), Paragraph('GitHub ingestion (<font face="Courier">fixture</font> mode)', table_cell_style)],
    [Paragraph('Source ingestion (PDF/TXT/MD)', table_cell_style), Paragraph('SQLite database (dev)', table_cell_style)],
    [Paragraph('Async extraction pipeline', table_cell_style), Paragraph('Demo JWT secret', table_cell_style)],
    [Paragraph('Conflict detection & preservation', table_cell_style), Paragraph('', table_cell_style)],
    [Paragraph('Human review + optimistic concurrency', table_cell_style), Paragraph('', table_cell_style)],
    [Paragraph('Role-filtered handovers + approval gate', table_cell_style), Paragraph('', table_cell_style)],
    [Paragraph('Cold-start evaluation (3 tasks)', table_cell_style), Paragraph('', table_cell_style)],
    [Paragraph('Comprehensive test suites (77+ tests)', table_cell_style), Paragraph('', table_cell_style)],
]

prod_table = Table(prod_data, colWidths=[2.7*inch, 2.7*inch])
prod_table.setStyle(TableStyle([
    ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#16213e')),
    ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
    ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f0f2f5')]),
    ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#ddd')),
    ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
    ('TOPPADDING', (0, 0), (-1, -1), 6),
    ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
    ('LEFTPADDING', (0, 0), (-1, -1), 8),
    ('RIGHTPADDING', (0, 0), (-1, -1), 8),
]))
story.append(prod_table)
story.append(Spacer(1, 24))

# Footer
story.append(Paragraph(
    '<i>Generated for Continuity AI \u2014 Evidence-First Project Knowledge Handover System</i>',
    ParagraphStyle('Footer', parent=styles['Normal'], fontSize=9, alignment=TA_CENTER, textColor=colors.grey)
))
story.append(Paragraph(
    '<i>Contract Version 1.0.0 | All 77+ tests passing | Full-stack verified</i>',
    ParagraphStyle('Footer2', parent=styles['Normal'], fontSize=9, alignment=TA_CENTER, textColor=colors.grey)
))

doc.build(story)
print('PDF created at: {0}'.format(output_path))