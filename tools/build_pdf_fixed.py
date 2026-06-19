#!/usr/bin/env python3
"""
build_pdf.py — Markdown/HTML to PDF converter for QNFO publications.
Uses reportlab for PDF generation, markdown for MD→HTML conversion.
v1.2 — 2026-06-06 — Added markdown table rendering + LaTeX math pre-processing.

Usage:
  python build_pdf.py --input paper.md --output paper.pdf
  python build_pdf.py --input paper.html --output paper.pdf --title "Paper Title"
  python build_pdf.py --input paper.md --output paper.pdf --author "Rowan Quni-Gudzinas" --date "2026-05-31"
  python build_pdf.py --input paper.md --output paper.pdf --no-math   # Skip math rendering
"""

import argparse
import re
import sys
import os
import io
import json
import textwrap
import tempfile
import atexit
from datetime import datetime
from pathlib import Path

# --- Matplotlib for math rendering ---
import matplotlib
matplotlib.use('Agg')  # Non-interactive backend
import matplotlib.pyplot as plt

# --- PDF generation with reportlab ---
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch, cm
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_JUSTIFY
from reportlab.lib.colors import black, grey, white
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, PageBreak,
    Table, TableStyle, HRFlowable, Image, KeepTogether
)
from reportlab.platypus.flowables import Flowable

# --- TTF Font Registration (for Unicode glyph coverage) ---
FONT_MAPPING = {}

# --- Math rendering state ---
_MATH_TEMP_FILES = []  # Track temp files for cleanup
_MATH_NO_RENDER = False  # --no-math flag

def _discover_and_register_fonts():
    """Discover available TTF fonts and register with reportlab."""
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    import os as _os

    registered = {}

    calibri_paths = [
        r'C:\Windows\Fonts\calibri.ttf',
        r'C:\Windows\Fonts\calibrib.ttf',
        r'C:\Windows\Fonts\calibrii.ttf',
        r'C:\Windows\Fonts\calibriz.ttf',
    ]

    if _os.path.exists(calibri_paths[0]):
        try:
            pdfmetrics.registerFont(TTFont('CalibriTTF', calibri_paths[0]))
            registered['sans'] = 'CalibriTTF'
            registered['sans_bold'] = 'CalibriTTF'
            registered['sans_italic'] = 'CalibriTTF'
            print(f"[FONTS] Registered Calibri TTF from {calibri_paths[0]}")
            return registered
        except Exception as e:
            print(f"[FONTS] Calibri registration failed: {e}")

    dejavu_paths = [
        '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',
        '/usr/share/fonts/TTF/DejaVuSans.ttf',
        '/System/Library/Fonts/DejaVuSans.ttf',
    ]
    for dp in dejavu_paths:
        if _os.path.exists(dp):
            try:
                pdfmetrics.registerFont(TTFont('DejaVuTTF', dp))
                registered['sans'] = 'DejaVuTTF'
                registered['sans_bold'] = 'DejaVuTTF'
                registered['sans_italic'] = 'DejaVuTTF'
                print(f"[FONTS] Registered DejaVu Sans TTF from {dp}")
                return registered
            except Exception as e:
                print(f"[FONTS] DejaVu registration failed: {e}")

    print("[FONTS] No TTF fonts found. Using standard PDF fonts (limited Unicode support).")
    registered['sans'] = 'Helvetica'
    registered['sans_bold'] = 'Helvetica-Bold'
    registered['sans_italic'] = 'Helvetica-Oblique'
    return registered

FONT_MAPPING = _discover_and_register_fonts()

def _font(name):
    return FONT_MAPPING.get(name, name)


# ═══════════════════════════════════════════════════════════════
# YAML FRONTMATTER HANDLING (v1.2 — 2026-06-05)
# ═══════════════════════════════════════════════════════════════

def strip_yaml_frontmatter(text):
    """Strip YAML frontmatter (--- delimited) from markdown text.
    
    Returns (metadata_dict, content_text).
    Handles multi-line values (YAML '>' and '|' blocks), quoted strings,
    and nested mappings. Falls back gracefully if PyYAML is unavailable.
    """
    if not text.startswith('---'):
        return {}, text
    
    # Find the closing ---
    end = text.find('\n---', 3)
    if end == -1:
        end = text.find('---', 3)
        if end == -1:
            return {}, text
    
    yaml_text = text[3:end].strip()
    content = text[end:].strip()
    # Remove the closing --- line
    if content.startswith('---'):
        content = content[3:].strip()
    
    # Try PyYAML first (handles complex YAML correctly)
    try:
        import yaml as pyyaml
        metadata = pyyaml.safe_load(yaml_text)
        if isinstance(metadata, dict):
            return metadata, content
    except ImportError:
        pass
    except Exception:
        pass
    
    # Fallback: simple regex-based YAML parser
    metadata = {}
    current_key = None
    current_value = []
    fold_mode = None  # None, 'literal', 'folded', or 'quoted'
    
    for line in yaml_text.split('\n'):
        stripped = line.strip()
        if not stripped or stripped.startswith('#'):
            continue
        
        # Check for key: value (at root level — no indentation)
        if ':' in line and not line.startswith(' ') and not line.startswith('\t'):
            # Save previous key
            if current_key:
                val = '\n'.join(current_value).strip()
                if fold_mode == 'folded':
                    val = ' '.join(val.split())  # Fold newlines to spaces (YAML >)
                metadata[current_key] = val.strip('"').strip("'")
            
            key, _, value = line.partition(':')
            current_key = key.strip()
            value = value.strip()
            
            if value in ('>', '|'):
                fold_mode = 'literal' if value == '|' else 'folded'
                current_value = []
            elif value.startswith('"') and value.endswith('"'):
                metadata[current_key] = value[1:-1]
                current_key = None
                current_value = []
            elif value.startswith("'") and value.endswith("'"):
                metadata[current_key] = value[1:-1]
                current_key = None
                current_value = []
            elif value:
                metadata[current_key] = value.strip('"').strip("'")
                current_key = None
                current_value = []
            else:
                # Key with no value — might be a mapping start
                current_value = []
        else:
            # Continuation of previous value
            if current_key:
                current_value.append(stripped)
    
    # Save last key
    if current_key and current_value:
        val = '\n'.join(current_value).strip()
        if fold_mode == 'folded':
            val = ' '.join(val.split())
        metadata[current_key] = val.strip('"').strip("'")
    
    return metadata, content


# --- Markdown to reportlab flowables ---
try:
    import markdown as md_lib
    HAS_MARKDOWN = True
except ImportError:
    HAS_MARKDOWN = False


def strip_html_tags(text):
    """Remove HTML tags, leaving plain text."""
    return re.sub(r'<[^>]+>', '', text)


def sanitize_unicode_escapes(text, source_label=""):
    """Detect and fix literal \\uXXXX escape sequences in text."""
    pattern = re.compile(r'\\u[0-9a-fA-F]{4}')
    matches = pattern.findall(text)

    if not matches:
        return text, 0, []

    from collections import Counter as _Counter
    fix_counts = _Counter()
    replacements = {}
    for m in set(matches):
        try:
            decoded = m.encode('ascii').decode('unicode_escape')
            replacements[m] = decoded
        except (UnicodeDecodeError, UnicodeEncodeError):
            pass

    fixed = text
    for escape_seq, real_char in replacements.items():
        count = fixed.count(escape_seq)
        fix_counts[escape_seq] = count
        fixed = fixed.replace(escape_seq, real_char)

    report = []
    label = f" [{source_label}]" if source_label else ""
    report.append(f"[UNICODE-FIX{label}] Found {len(matches)} literal Unicode escape sequences:")
    for seq, count in fix_counts.most_common():
        real = replacements.get(seq, '?')
        report.append(f"  {count:4d}x {seq} -> {real!r} (U+{ord(real):04X})")
    report.append(f"[UNICODE-FIX{label}] All sequences resolved. Sanitized text ready for PDF generation.")

    return fixed, len(matches), report


# ═══════════════════════════════════════════════════════════════
# MATH RENDERING — v1.1
# ═══════════════════════════════════════════════════════════════

# LaTeX-to-Unicode fallback map for --no-math mode
_LATEX_UNICODE_MAP = {
    # Greek lowercase
    r'\alpha': '\u03B1', r'\beta': '\u03B2', r'\gamma': '\u03B3',
    r'\delta': '\u03B4', r'\epsilon': '\u03B5', r'\varepsilon': '\u03B5',
    r'\zeta': '\u03B6', r'\eta': '\u03B7', r'\theta': '\u03B8',
    r'\vartheta': '\u03D1', r'\iota': '\u03B9', r'\kappa': '\u03BA',
    r'\lambda': '\u03BB', r'\mu': '\u03BC', r'\nu': '\u03BD',
    r'\xi': '\u03BE', r'\pi': '\u03C0', r'\varpi': '\u03D6',
    r'\rho': '\u03C1', r'\varrho': '\u03F1', r'\sigma': '\u03C3',
    r'\varsigma': '\u03C2', r'\tau': '\u03C4', r'\upsilon': '\u03C5',
    r'\phi': '\u03C6', r'\varphi': '\u03C6', r'\chi': '\u03C7',
    r'\psi': '\u03C8', r'\omega': '\u03C9',
    # Greek uppercase
    r'\Gamma': '\u0393', r'\Delta': '\u0394', r'\Theta': '\u0398',
    r'\Lambda': '\u039B', r'\Xi': '\u039E', r'\Pi': '\u03A0',
    r'\Sigma': '\u03A3', r'\Upsilon': '\u03A5', r'\Phi': '\u03A6',
    r'\Psi': '\u03A8', r'\Omega': '\u03A9',
    # Operators
    r'\times': '\u00D7', r'\cdot': '\u22C5', r'\pm': '\u00B1',
    r'\mp': '\u2213', r'\div': '\u00F7', r'\ast': '\u2217',
    r'\star': '\u22C6', r'\circ': '\u2218', r'\bullet': '\u2022',
    r'\oplus': '\u2295', r'\ominus': '\u2296', r'\otimes': '\u2297',
    r'\oslash': '\u2298', r'\odot': '\u2299',
    # Relations
    r'\leq': '\u2264', r'\geq': '\u2265', r'\neq': '\u2260',
    r'\approx': '\u2248', r'\equiv': '\u2261', r'\sim': '\u223C',
    r'\simeq': '\u2243', r'\propto': '\u221D', r'\ll': '\u226A',
    r'\gg': '\u226B', r'\prec': '\u227A', r'\succ': '\u227B',
    r'\preceq': '\u2AAF', r'\succeq': '\u2AB0',
    # Arrows
    r'\to': '\u2192', r'\rightarrow': '\u2192', r'\Rightarrow': '\u21D2',
    r'\leftarrow': '\u2190', r'\Leftarrow': '\u21D0',
    r'\leftrightarrow': '\u2194', r'\Leftrightarrow': '\u21D4',
    r'\mapsto': '\u21A6', r'\longrightarrow': '\u27F6',
    # Sets
    r'\infty': '\u221E', r'\partial': '\u2202', r'\nabla': '\u2207',
    r'\emptyset': '\u2205', r'\varnothing': '\u2205',
    r'\in': '\u2208', r'\notin': '\u2209', r'\ni': '\u220B',
    r'\subset': '\u2282', r'\subseteq': '\u2286',
    r'\supset': '\u2283', r'\supseteq': '\u2287',
    r'\cup': '\u222A', r'\cap': '\u2229', r'\setminus': '\u2216',
    # Quantifiers
    r'\forall': '\u2200', r'\exists': '\u2203', r'\nexists': '\u2204',
    # Misc symbols
    r'\hbar': '\u0127', r'\ell': '\u2113', r'\imath': '\u0131',
    r'\jmath': '\u0237', r'\wp': '\u2118', r'\Re': '\u211C',
    r'\Im': '\u2111', r'\aleph': '\u2135',
    r'\angle': '\u2220', r'\measuredangle': '\u2221',
    r'\triangle': '\u25B3', r'\square': '\u25A1',
    r'\nabla': '\u2207', r'\int': '\u222B', r'\iint': '\u222C',
    r'\iiint': '\u222D', r'\oint': '\u222E', r'\sum': '\u2211',
    r'\prod': '\u220F', r'\coprod': '\u2210',
    # Big operators (same Unicode as small)
    r'\bigcup': '\u22C3', r'\bigcap': '\u22C2',
    r'\bigvee': '\u22C1', r'\bigwedge': '\u22C0',
    # Dots
    r'\dots': '\u2026', r'\cdots': '\u22EF', r'\vdots': '\u22EE',
    r'\ddots': '\u22F1', r'\ldots': '\u2026',
    # Superscripts/subscripts (common)
    r'\^0': '\u2070', r'\^1': '\u00B9', r'\^2': '\u00B2', r'\^3': '\u00B3',
    r'\^4': '\u2074', r'\^5': '\u2075', r'\^6': '\u2076', r'\^7': '\u2077',
    r'\^8': '\u2078', r'\^9': '\u2079', r'\^n': '\u207F',
    r'_0': '\u2080', r'_1': '\u2081', r'_2': '\u2082', r'_3': '\u2083',
    r'_4': '\u2084', r'_5': '\u2085', r'_6': '\u2086', r'_7': '\u2087',
    r'_8': '\u2088', r'_9': '\u2089',
    # Blackboard bold
    r'\mathbb{N}': '\u2115', r'\mathbb{Z}': '\u2124',
    r'\mathbb{Q}': '\u211A', r'\mathbb{R}': '\u211D',
    r'\mathbb{C}': '\u2102', r'\mathbb{H}': '\u210D',
    r'\mathbb{P}': '\u2119',
}


def _latex_to_unicode(latex_str):
    """Convert LaTeX math to Unicode approximations (for --no-math mode)."""
    result = latex_str
    # Apply longest patterns first
    sorted_keys = sorted(_LATEX_UNICODE_MAP.keys(), key=len, reverse=True)
    for key in sorted_keys:
        result = result.replace(key, _LATEX_UNICODE_MAP[key])
    # Handle simple superscripts: x^2 -> x\xc2\xb2
    result = re.sub(r'\^(\d)', lambda m: '^' + m.group(1), result)
    return result



# ═══════════════════════════════════════════════════════════════
# LATEX PRE-PROCESSOR FOR MATHTEXT (v1.2)
# ═══════════════════════════════════════════════════════════════

# Patterns to fix before passing to mathtext
_LATEX_PREPROC_PATTERNS = [
    # \\text{...} double-backslash -> \text{...} single
    (re.compile(r'\\\\text\{'), r'\\text{'),
    # \operatorname{...} -> \mathrm{...}
    (re.compile(r'\\operatorname\{'), r'\\mathrm{'),
    # \bmod -> \ \mathrm{mod}\  (requires spaces for mathtext)
    (re.compile(r'\\bmod'), r'\\ \\mathrm{mod}\\ '),
    # \pmod{...} -> (\mathrm{mod}\ ...)
    (re.compile(r'\\pmod\{(.+?)\}'), r'(\\mathrm{mod}\\ \1)'),
    # \begin{align}...\end{align} -> multi-line warning (can't auto-fix)
    # \begin{cases} -> \left\{ \begin{array}... (best-effort)
    (re.compile(r'\\begin\{cases\}'), r'\\left\\{ \\begin{array}{l}'),
    (re.compile(r'\\end\{cases\}'), r'\\end{array} \\right.'),
    # \bm{...} -> \mathbf{...}
    (re.compile(r'\\bm\{'), r'\\mathbf{'),
    # \tfrac -> \frac (mathtext doesn't distinguish)
    (re.compile(r'\\tfrac'), r'\\frac'),
    # \dfrac -> \frac
    (re.compile(r'\\dfrac'), r'\\frac'),
    # \dbinom -> \binom
    (re.compile(r'\\dbinom'), r'\\binom'),
    # \tbinom -> \binom
    (re.compile(r'\\tbinom'), r'\\binom'),
    # \mathbb{...} -> \mathbf{...} (mathtext does NOT support \mathbb, 
    # but \mathbf renders correctly and conveys blackboard-bold intent)
    # Prior attempt: Unicode chars (ℚ,ℝ,ℤ) — not extractable from math images
    (re.compile(r'\\mathbb\{'), r'\\mathbf{'),
]

_UNSUPPORTED_ENVS = [
    'align', 'align*', 'equation', 'equation*', 'gather', 'gather*',
    'multline', 'multline*', 'split', 'flalign', 'flalign*',
    'alignat', 'alignat*', 'matrix', 'pmatrix', 'bmatrix', 'Bmatrix',
    'vmatrix', 'Vmatrix', 'smallmatrix',
]

def _preprocess_latex_for_mathtext(expr):
    """Apply compatibility transforms to make LaTeX work with mathtext.
    
    Returns (processed_expr, warnings_list).
    """
    warnings = []
    result = expr
    
    # Check for unsupported environments
    for env in _UNSUPPORTED_ENVS:
        if f'\\begin{{{env}}}' in result:
            warnings.append(f'Unsupported environment: \\begin{{{env}}} — rendered as raw text')
    
    # Apply pattern replacements
    for pattern, replacement in _LATEX_PREPROC_PATTERNS:
        old = result
        result = pattern.sub(replacement, result)
        if old != result:
            # Count replacements
            count = len(pattern.findall(old))
            if count > 0:
                warnings.append(f'Auto-fixed {count}x {pattern.pattern[:60]}...')
    
    return result, warnings

# END LATEX PRE-PROCESSOR

def render_math_to_image(latex_str, font_size=11, dpi=150):
    """Render a LaTeX math expression to a PNG image using matplotlib mathtext.

    Args:
        latex_str: LaTeX math expression (without $ delimiters)
        font_size: Base font size in points
        dpi: Output resolution

    Returns:
        tuple of (image_path, width_pts, height_pts)
        width_pts and height_pts are the image dimensions in PDF points (1/72 inch)
    """
    global _MATH_TEMP_FILES

    # Pre-process LaTeX for mathtext compatibility (v1.2)
    expr, _preproc_warnings = _preprocess_latex_for_mathtext(latex_str.strip())
    if _preproc_warnings:
        for w in _preproc_warnings:
            print(f"  [MATH-PREPROC] {w}", file=sys.stderr)

    # Create figure and render
    fig, ax = plt.subplots(figsize=(6, 0.5))
    ax.axis('off')

    try:
        text_obj = ax.text(0.5, 0.5, f'${expr}$',
                           fontsize=font_size,
                           ha='center', va='center',
                           transform=ax.transAxes)

        # Get bounding box
        fig.canvas.draw()
        renderer = fig.canvas.get_renderer()
        bbox = text_obj.get_window_extent(renderer=renderer)

        # Convert bbox from display coords to inches
        bbox_inches = bbox.transformed(fig.dpi_scale_trans.inverted())

        plt.close(fig)

        # Add padding
        pad = 0.08
        width_in = bbox_inches.width + pad * 2
        height_in = bbox_inches.height + pad * 2

        # Render with exact bounding box
        fig2, ax2 = plt.subplots(figsize=(max(width_in, 0.3), max(height_in, 0.2)))
        ax2.axis('off')
        ax2.text(0.5, 0.5, f'${expr}$',
                 fontsize=font_size,
                 ha='center', va='center',
                 transform=ax2.transAxes)

        # Save to temp file
        tmp = tempfile.NamedTemporaryFile(suffix='.png', delete=False)
        fig2.savefig(tmp.name, dpi=dpi, bbox_inches='tight',
                     pad_inches=0.03, transparent=True, format='png')
        plt.close(fig2)

        _MATH_TEMP_FILES.append(tmp.name)

        # Dimensions in points
        width_pts = width_in * 72
        height_pts = height_in * 72

        return (tmp.name, width_pts, height_pts)

    except Exception as e:
        plt.close('all')
        # Fallback: render as plain text
        print(f"  [MATH-WARN] Could not render: ${latex_str[:60]}... — {e}", file=sys.stderr)
        fig_fb, ax_fb = plt.subplots(figsize=(3, 0.3))
        ax_fb.axis('off')
        display_text = f'${latex_str}$' if len(latex_str) < 80 else f'${latex_str[:77]}...$'
        ax_fb.text(0.5, 0.5, display_text,
                   fontsize=8, ha='center', va='center',
                   transform=ax_fb.transAxes,
                   fontfamily='monospace', color='red')
        tmp = tempfile.NamedTemporaryFile(suffix='.png', delete=False)
        fig_fb.savefig(tmp.name, dpi=dpi, bbox_inches='tight',
                       pad_inches=0.03, transparent=True, format='png')
        plt.close(fig_fb)
        _MATH_TEMP_FILES.append(tmp.name)
        return (tmp.name, 200, 14)


def _cleanup_math_tempfiles():
    """Remove temporary math image files. Registered with atexit."""
    global _MATH_TEMP_FILES
    for f in _MATH_TEMP_FILES:
        try:
            if os.path.exists(f):
                os.unlink(f)
        except OSError:
            pass
    _MATH_TEMP_FILES = []


atexit.register(_cleanup_math_tempfiles)


# Math delimiter patterns
_RE_DISPLAY_MATH = re.compile(r'\$\$(.+?)\$\$', re.DOTALL)
_RE_INLINE_MATH = re.compile(r'(?<!\$)\$(?!\$)(.+?)(?<!\$)\$(?!\$)')


def _contains_math(text):
    """Check if text contains math delimiters."""
    return bool(_RE_INLINE_MATH.search(text)) or bool(_RE_DISPLAY_MATH.search(text))


def _split_inline_math(text):
    """Split text at inline math ($...$) boundaries.

    Returns list of dicts: [{'type': 'text', 'content': '...'}, {'type': 'math', 'content': '...'}]
    """
    parts = []
    last_end = 0

    for m in _RE_INLINE_MATH.finditer(text):
        # Text before math
        if m.start() > last_end:
            parts.append({'type': 'text', 'content': text[last_end:m.start()]})
        # Math expression
        parts.append({'type': 'math', 'content': m.group(1).strip()})
        last_end = m.end()

    # Remaining text
    if last_end < len(text):
        parts.append({'type': 'text', 'content': text[last_end:]})

    return parts


def _make_math_inline_flowables(text, styles, base_style='BodyText'):
    """Create flowables for a paragraph containing inline math.

    Uses a 1-row Table to simulate inline rendering: text segments are
    Paragraph cells, math expressions are Image cells.
    """
    parts = _split_inline_math(text)
    if not parts:
        return [Paragraph(text, styles[base_style])]

    if _MATH_NO_RENDER:
        # --no-math mode: convert to Unicode approximations
        no_math_text = text
        for m in _RE_INLINE_MATH.finditer(text):
            unicode_math = _latex_to_unicode(m.group(1))
            no_math_text = no_math_text.replace(m.group(0), unicode_math)
        return [Paragraph(_format_inline_markdown(no_math_text), styles[base_style])]

    # Build cells for 1-row table
    cells = []
    for part in parts:
        if part['type'] == 'text':
            formatted = _format_inline_markdown(part['content'])
            if formatted.strip():
                cells.append(Paragraph(formatted, styles[base_style]))
        else:  # math
            try:
                img_path, w_pts, h_pts = render_math_to_image(part['content'],
                                                               font_size=10, dpi=150)
                # Scale image to fit inline — cap height at ~14pt
                max_h = 14
                if h_pts > max_h:
                    scale = max_h / h_pts
                    w_pts *= scale
                    h_pts = max_h
                cells.append(Image(img_path, width=w_pts, height=h_pts))
            except Exception as e:
                print(f"  [MATH-ERR] Inline math render failed: {e}", file=sys.stderr)
                cells.append(Paragraph(f'<font color="red">${part["content"]}$</font>',
                                       styles[base_style]))

    if len(cells) == 0:
        return [Paragraph('', styles[base_style])]
    if len(cells) == 1:
        return [cells[0]]

    # Build single-row table for true inline rendering
    table = Table([cells])
    table.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('LEFTPADDING', (0, 0), (-1, -1), 1),
        ('RIGHTPADDING', (0, 0), (-1, -1), 1),
        ('TOPPADDING', (0, 0), (-1, -1), 0),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 0),
    ]))

    return [table]


def _make_display_math_flowable(latex_str, styles):
    """Create a centered display math flowable from a LaTeX expression."""
    if _MATH_NO_RENDER:
        unicode_math = _latex_to_unicode(latex_str)
        return [Paragraph(f'<i>{unicode_math}</i>', ParagraphStyle(
            'DisplayMathText', parent=styles['BodyText'],
            alignment=TA_CENTER, fontName=_font('sans_italic'),
            fontSize=11, spaceBefore=8, spaceAfter=8
        ))]

    try:
        img_path, w_pts, h_pts = render_math_to_image(latex_str, font_size=12, dpi=150)

        # Build centered image with spacing
        result = []
        result.append(Spacer(1, 8))
        # Center the image using a 1x1 table
        img = Image(img_path, width=w_pts, height=h_pts)
        center_table = Table([[img]], colWidths=[A4[0] - 4 * cm])
        center_table.setStyle(TableStyle([
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('TOPPADDING', (0, 0), (-1, -1), 4),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ]))
        result.append(center_table)
        result.append(Spacer(1, 8))
        return result
    except Exception as e:
        print(f"  [MATH-ERR] Display math render failed: {e}", file=sys.stderr)
        return [Paragraph(f'<font color="red">$${latex_str}$$</font>',
                          ParagraphStyle('DisplayMathErr', parent=styles['BodyText'],
                                        alignment=TA_CENTER, fontSize=10))]


# ═══════════════════════════════════════════════════════════════
# END MATH RENDERING
# ═══════════════════════════════════════════════════════════════



# ═══════════════════════════════════════════════════════════════
# MARKDOWN TABLE RENDERING (v1.2)
# ═══════════════════════════════════════════════════════════════

_RE_TABLE_LINE = re.compile(r'^\|(.+)\|$')
_RE_TABLE_SEPARATOR = re.compile(r'^\|[\s:-]+\|$')

def _is_table_line(line):
    """Check if a line is a markdown table row."""
    return bool(_RE_TABLE_LINE.match(line.strip()))

def _is_table_separator(line):
    """Check if a line is a markdown table separator (e.g., |---|:---:|---:|)."""
    stripped = line.strip()
    if not stripped.startswith('|') or not stripped.endswith('|'):
        return False
    inner = stripped[1:-1]
    parts = inner.split('|')
    for p in parts:
        p = p.strip()
        if not p:
            return False
        # Must be dashes, colons, and optional whitespace
        if not re.match(r'^:?-{3,}:?$', p):
            return False
    return True

def _detect_table_align(sep_line):
    """Parse alignment from separator line.
    
    Returns list of 'LEFT', 'CENTER', or 'RIGHT' per column.
    """
    stripped = sep_line.strip()
    inner = stripped[1:-1]  # Remove leading/trailing |
    parts = inner.split('|')
    aligns = []
    for p in parts:
        p = p.strip()
        if p.startswith(':') and p.endswith(':'):
            aligns.append('CENTER')
        elif p.endswith(':'):
            aligns.append('RIGHT')
        else:
            aligns.append('LEFT')
    return aligns

def _parse_table_cells(line):
    """Extract cell contents from a table row line."""
    stripped = line.strip()
    inner = stripped[1:-1]  # Remove leading/trailing |
    return [c.strip() for c in inner.split('|')]

def _create_table_flowable(headers, rows, aligns, styles):
    """Create a reportlab Table flowable from parsed markdown table data.
    
    Args:
        headers: list of header cell strings
        rows: list of lists of cell strings
        aligns: list of alignment strings ('LEFT', 'CENTER', 'RIGHT')
        styles: paragraph styles dict
    
    Returns:
        reportlab.platypus.Table object
    """
    from reportlab.lib.colors import HexColor
    
    num_cols = len(headers)
    
    # Ensure aligns covers all columns
    while len(aligns) < num_cols:
        aligns.append('LEFT')
    
    # Build cell paragraphs
    def _cell_para(text, is_header=False):
        """Convert cell text to Paragraph with appropriate styling.
        Handles inline math ($...$) by passing through the math renderer.
        """
        if _contains_math(text) and not _MATH_NO_RENDER:
            # Cell contains inline math — use math rendering pipeline
            # For table cells, we build a simplified inline flowable
            parts = _split_inline_math(text)
            cell_parts = []
            for part in parts:
                if part['type'] == 'text':
                    formatted = _format_inline_markdown(part['content'])
                    if formatted.strip():
                        cell_parts.append(Paragraph(formatted,
                            ParagraphStyle('TableCellText', parent=styles['BodyText'],
                                fontSize=9, leading=12, alignment=TA_LEFT,
                                fontName=_font('sans_bold' if is_header else 'sans'))))
                else:  # math
                    try:
                        img_path, w_pts, h_pts = render_math_to_image(part['content'],
                                                                       font_size=9, dpi=120)
                        max_h = 12
                        if h_pts > max_h:
                            scale = max_h / h_pts
                            w_pts *= scale
                            h_pts = max_h
                        cell_parts.append(Image(img_path, width=w_pts, height=h_pts))
                    except Exception as e:
                        print(f"  [TABLE-MATH-ERR] {e}", file=sys.stderr)
                        cell_parts.append(Paragraph(f'${part["content"]}$',
                            ParagraphStyle('TableCellErr', parent=styles['BodyText'],
                                fontSize=8, textColor=HexColor('#e74c3c'))))
            if len(cell_parts) == 1:
                return cell_parts[0]
            # Build mini single-row table for inline math in cell
            mini_table = Table([cell_parts])
            mini_table.setStyle(TableStyle([
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                ('LEFTPADDING', (0, 0), (-1, -1), 1),
                ('RIGHTPADDING', (0, 0), (-1, -1), 1),
                ('TOPPADDING', (0, 0), (-1, -1), 0),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 0),
            ]))
            return mini_table
        else:
            # No math — simple markdown formatting
            formatted = _format_inline_markdown(text)
            if is_header:
                return Paragraph(f'<b>{formatted}</b>', 
                    ParagraphStyle('TableCellHeader', parent=styles['BodyText'],
                        fontSize=9, leading=12, alignment=TA_LEFT,
                        fontName=_font('sans_bold')))
            else:
                return Paragraph(formatted,
                    ParagraphStyle('TableCell', parent=styles['BodyText'],
                        fontSize=9, leading=12, alignment=TA_LEFT))
    
    # Build table data
    table_data = []
    table_data.append([_cell_para(h, is_header=True) for h in headers])
    for row in rows:
        # Pad row if shorter than header
        padded = list(row) + [''] * (num_cols - len(row))
        table_data.append([_cell_para(c) for c in padded[:num_cols]])
    
    # Calculate column widths (equal distribution based on available width)
    usable_width = A4[0] - 5 * cm  # Account for margins
    col_width = usable_width / num_cols
    
    # Build style commands
    style_cmds = [
        # Header styling
        ('BACKGROUND', (0, 0), (-1, 0), HexColor('#2c3e50')),
        ('TEXTCOLOR', (0, 0), (-1, 0), white),
        ('FONTNAME', (0, 0), (-1, 0), _font('sans_bold')),
        ('FONTSIZE', (0, 0), (-1, 0), 9),
        # Grid
        ('GRID', (0, 0), (-1, -1), 0.5, HexColor('#bdc3c7')),
        ('LINEBELOW', (0, 0), (-1, 0), 1.5, HexColor('#2c3e50')),
        # Padding
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ('LEFTPADDING', (0, 0), (-1, -1), 6),
        ('RIGHTPADDING', (0, 0), (-1, -1), 6),
        # Vertical alignment
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
    ]
    
    # Alternating row colors for readability
    for row_idx in range(1, len(table_data)):
        if row_idx % 2 == 0:
            style_cmds.append(
                ('BACKGROUND', (0, row_idx), (-1, row_idx), HexColor('#f8f9fa'))
            )
    
    # Column alignment
    align_map = {'LEFT': 'LEFT', 'CENTER': 'CENTER', 'RIGHT': 'RIGHT'}
    for col_idx, align in enumerate(aligns[:num_cols]):
        style_cmds.append(
            ('ALIGN', (col_idx, 0), (col_idx, -1), align_map.get(align, 'LEFT'))
        )
    
    table = Table(table_data, colWidths=[col_width] * num_cols)
    table.setStyle(TableStyle(style_cmds))
    
    return table

def _extract_markdown_table(lines, start_idx):
    """Try to extract a markdown table starting at lines[start_idx].
    
    Returns (table_flowable, end_idx, num_lines_consumed) or (None, start_idx, 0)
    if no table detected.
    """
    if start_idx >= len(lines):
        return None, start_idx, 0
    
    # Table needs at minimum: header + separator + 1 data row = 3 lines
    if start_idx + 2 >= len(lines):
        return None, start_idx, 0
    
    line0 = lines[start_idx].strip()
    line1 = lines[start_idx + 1].strip() if start_idx + 1 < len(lines) else ''
    
    if not _is_table_line(line0) or not _is_table_separator(line1):
        return None, start_idx, 0
    
    # We have a table header + separator
    headers = _parse_table_cells(line0)
    aligns = _detect_table_align(line1)
    
    # Collect data rows
    rows = []
    idx = start_idx + 2
    while idx < len(lines):
        line = lines[idx].strip()
        if not _is_table_line(line):
            break
        cells = _parse_table_cells(line)
        if cells:
            rows.append(cells)
        idx += 1
    
    # Require at least 1 data row
    if not rows:
        return None, start_idx, 0
    
    return (headers, rows, aligns), idx, idx - start_idx

# END TABLE RENDERING

def md_to_plain_flowables(text, styles):
    """Parse markdown text into reportlab flowables (paragraphs, headings, math)."""
    flowables = []

    if HAS_MARKDOWN and not _contains_math(text):
        # Use markdown library for text without math
        md = md_lib.Markdown(extensions=['extra', 'codehilite', 'toc'])
        html = md.convert(text)
        html = re.sub(r'\s+class="[^"]*"', '', html)
        html = re.sub(r'\s+id="[^"]*"', '', html)
        return html_to_flowables(html, styles)

    # Regex-based markdown parsing with math support (v1.2: + table support)
    lines = text.split('\n')
    i = 0
    in_code_block = False
    in_display_math = False
    code_lines = []
    math_lines = []
    _SKIP_LINES = 0  # Number of lines to skip (consumed by sub-parsers like tables)

    while i < len(lines):
        # Handle skip-lines from sub-parsers (e.g., tables consumed multiple lines)
        if _SKIP_LINES > 0:
            i += _SKIP_LINES
            _SKIP_LINES = 0
            if i >= len(lines):
                break
        
        line = lines[i]

        # === TABLE DETECTION (v1.2) ===
        table_result = _extract_markdown_table(lines, i)
        if table_result[0] is not None:
            headers, rows, aligns = table_result[0]
            _SKIP_LINES = table_result[2]
            try:
                table_flowable = _create_table_flowable(headers, rows, aligns, styles)
                flowables.append(Spacer(1, 4))
                flowables.append(table_flowable)
                flowables.append(Spacer(1, 4))
                print(f"  [TABLE] Rendered {len(rows)} row(s), {len(headers)} column(s)")
            except Exception as e:
                print(f"  [TABLE-ERR] Table render failed: {e}", file=sys.stderr)
                # Fallback: render as preformatted text
                raw_table = '\n'.join(lines[i:i + table_result[2]])
                flowables.append(Paragraph(
                    f'<pre><font face="Courier" size="7">{raw_table}</font></pre>',
                    styles['Code']
                ))
            continue

        # Code block toggle (takes priority over math)
        if line.strip().startswith('```'):
            if in_display_math:
                # Close math first
                math_text = '\n'.join(math_lines).strip()
                if math_text:
                    flowables.extend(_make_display_math_flowable(math_text, styles))
                math_lines = []
                in_display_math = False

            if in_code_block:
                code_text = '\n'.join(code_lines)
                flowables.append(Paragraph(
                    f'<pre><font face="Courier" size="8">{code_text}</font></pre>',
                    styles['Code']
                ))
                code_lines = []
                in_code_block = False
            else:
                in_code_block = True
            i += 1
            continue

        if in_code_block:
            code_lines.append(line)
            i += 1
            continue

        stripped = line.strip()

        # Display math toggle: $$ on its own line or $$ at start/end
        if stripped.startswith('$$') and stripped.endswith('$$') and len(stripped) > 4:
            # Single-line display math: $$...$$
            if in_display_math:
                math_lines.append(stripped[2:-2])
                math_text = '\n'.join(math_lines).strip()
                flowables.extend(_make_display_math_flowable(math_text, styles))
                math_lines = []
                in_display_math = False
            else:
                math_text = stripped[2:-2].strip()
                flowables.extend(_make_display_math_flowable(math_text, styles))
            i += 1
            continue

        if stripped == '$$':
            if in_display_math:
                # End display math block
                math_text = '\n'.join(math_lines).strip()
                if math_text:
                    flowables.extend(_make_display_math_flowable(math_text, styles))
                math_lines = []
                in_display_math = False
            else:
                # Start display math block
                in_display_math = True
            i += 1
            continue

        if in_display_math:
            math_lines.append(stripped)
            i += 1
            continue

        # Blank line
        if not stripped:
            flowables.append(Spacer(1, 6))
            i += 1
            continue

        # Headings
        if stripped.startswith('# '):
            heading_text = strip_html_tags(stripped[2:])
            if _contains_math(heading_text):
                flowables.extend(_make_math_inline_flowables(heading_text, styles, 'Heading1'))
            else:
                flowables.append(Paragraph(heading_text, styles['Heading1']))
        elif stripped.startswith('## '):
            heading_text = strip_html_tags(stripped[3:])
            if _contains_math(heading_text):
                flowables.extend(_make_math_inline_flowables(heading_text, styles, 'Heading2'))
            else:
                flowables.append(Paragraph(heading_text, styles['Heading2']))
        elif stripped.startswith('### '):
            heading_text = strip_html_tags(stripped[4:])
            if _contains_math(heading_text):
                flowables.extend(_make_math_inline_flowables(heading_text, styles, 'Heading3'))
            else:
                flowables.append(Paragraph(heading_text, styles['Heading3']))
        elif stripped.startswith('#### '):
            heading_text = strip_html_tags(stripped[5:])
            if _contains_math(heading_text):
                flowables.extend(_make_math_inline_flowables(heading_text, styles, 'Heading4'))
            else:
                flowables.append(Paragraph(heading_text, styles['Heading4']))
        # Horizontal rule
        elif stripped in ('---', '***', '___', '* * *'):
            flowables.append(HRFlowable(width="100%", thickness=0.5, color=grey))
        # Unordered list
        elif re.match(r'^[\*\-\+]\s', stripped):
            item_text = stripped[2:]
            if _contains_math(item_text):
                # For list items with math, prepend bullet text
                bullet = Paragraph('&bull;', styles['BodyText'])
                math_flowables = _make_math_inline_flowables(item_text, styles)
                if len(math_flowables) == 1:
                    flowables.append(Paragraph(
                        f'&bull; {_format_inline_markdown(item_text)}',
                        styles['BodyText']))
                else:
                    # Build table with bullet cell + content
                    cells = [bullet] + math_flowables
                    table = Table([cells])
                    table.setStyle(TableStyle([
                        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                        ('LEFTPADDING', (0, 0), (0, 0), 8),
                        ('RIGHTPADDING', (0, 0), (0, 0), 4),
                    ]))
                    flowables.append(table)
            else:
                flowables.append(Paragraph(
                    f'&bull; {_format_inline_markdown(item_text)}',
                    styles['BodyText']))
        # Ordered list
        elif re.match(r'^\d+\.\s', stripped):
            m_num = re.match(r'^(\d+)\.', stripped)
            num = m_num.group(1)
            item_text = stripped[stripped.index(". ")+2:]
            if _contains_math(item_text):
                flowables.append(Paragraph(
                    f'{num}. {_format_inline_markdown(item_text)}',
                    styles['BodyText']))
            else:
                flowables.append(Paragraph(
                    f'{num}. {_format_inline_markdown(item_text)}',
                    styles['BodyText']))
        # Regular paragraph
        else:
            if _contains_math(stripped):
                flowables.extend(_make_math_inline_flowables(stripped, styles))
            else:
                flowables.append(Paragraph(_format_inline_markdown(stripped), styles['BodyText']))

        i += 1

    # Close any open display math block at end of file
    if in_display_math and math_lines:
        math_text = '\n'.join(math_lines).strip()
        if math_text:
            flowables.extend(_make_display_math_flowable(math_text, styles))

    return flowables


def _format_inline_markdown(text):
    """Convert inline markdown to HTML for reportlab Paragraph."""
    # Bold: **text** or __text__
    text = re.sub(r'\*\*(.+?)\*\*', r'<b>\1</b>', text)
    text = re.sub(r'__(.+?)__', r'<b>\1</b>', text)
    # Italic: *text* or _text_
    text = re.sub(r'\*(.+?)\*', r'<i>\1</i>', text)
    text = re.sub(r'_(.+?)_', r'<i>\1</i>', text)
    # Inline code: `text`
    text = re.sub(r'`(.+?)`', r'<font face="Courier">\1</font>', text)
    # Links: [text](url)
    text = re.sub(r'\[(.+?)\]\((.+?)\)', r'<a href="\2" color="blue">\1</a>', text)
    return text


def html_to_flowables(html_text, styles):
    """Parse HTML into reportlab flowables (simplified)."""
    flowables = []

    blocks = re.split(r'(</?h[1-4][^>]*>|</?p>|</?pre>|</?blockquote>|<hr\s*/?>)', html_text)

    current_tag = None
    buffer_text = ""

    for block in blocks:
        if re.match(r'<h([1-4])[^>]*>', block):
            current_tag = f'h{re.match(r"<h([1-4])[^>]*>", block).group(1)}'
            buffer_text = ""
        elif re.match(r'</h[1-4]>', block):
            if buffer_text.strip():
                style_key = f'Heading{current_tag[1]}'
                flowables.append(Paragraph(strip_html_tags(buffer_text), styles[style_key]))
            current_tag = None
            buffer_text = ""
        elif block == '<p>':
            current_tag = 'p'
            buffer_text = ""
        elif block == '</p>':
            if buffer_text.strip():
                flowables.append(Paragraph(buffer_text.strip(), styles['BodyText']))
            current_tag = None
            buffer_text = ""
        elif block == '<pre>':
            current_tag = 'pre'
            buffer_text = ""
        elif block == '</pre>':
            flowables.append(Paragraph(
                f'<font face="Courier" size="8">{buffer_text}</font>',
                styles['Code']
            ))
            current_tag = None
            buffer_text = ""
        elif re.match(r'<hr\s*/?>', block):
            flowables.append(HRFlowable(width="100%", thickness=0.5, color=grey))
        else:
            buffer_text += block

    if buffer_text.strip():
        flowables.append(Paragraph(buffer_text.strip(), styles['BodyText']))

    return flowables


def build_styles():
    """Create publication-quality paragraph styles."""
    base = getSampleStyleSheet()

    styles = {
        'Title': ParagraphStyle(
            'CustomTitle', parent=base['Title'],
            fontName=_font('sans_bold'), fontSize=20, leading=26,
            spaceAfter=6, alignment=TA_CENTER
        ),
        'Author': ParagraphStyle(
            'Author', parent=base['Normal'],
            fontName=_font('sans'), fontSize=12, leading=16,
            spaceAfter=24, alignment=TA_CENTER, textColor=grey
        ),
        'Heading1': ParagraphStyle(
            'CustomH1', parent=base['Heading1'],
            fontName=_font('sans_bold'), fontSize=16, leading=22,
            spaceBefore=18, spaceAfter=8
        ),
        'Heading2': ParagraphStyle(
            'CustomH2', parent=base['Heading2'],
            fontName=_font('sans_bold'), fontSize=14, leading=19,
            spaceBefore=14, spaceAfter=6
        ),
        'Heading3': ParagraphStyle(
            'CustomH3', parent=base['Heading3'],
            fontName=_font('sans_italic'), fontSize=12, leading=16,
            spaceBefore=10, spaceAfter=4
        ),
        'Heading4': ParagraphStyle(
            'CustomH4', parent=base['Heading4'],
            fontName=_font('sans_italic'), fontSize=11, leading=14,
            spaceBefore=8, spaceAfter=3
        ),
        'BodyText': ParagraphStyle(
            'CustomBody', parent=base['BodyText'],
            fontName=_font('sans'), fontSize=10, leading=15,
            spaceBefore=2, spaceAfter=8, alignment=TA_JUSTIFY
        ),
        'Code': ParagraphStyle(
            'CodeBlock', parent=base['Code'],
            fontName='Courier', fontSize=8, leading=10,
            leftIndent=12, rightIndent=12, spaceBefore=6, spaceAfter=6,
            backColor='#f5f5f5'
        ),
        'Bullet': ParagraphStyle(
            'BulletItem', parent=base['BodyText'],
            fontName=_font('sans'), fontSize=10, leading=15,
            leftIndent=20, bulletIndent=10, spaceBefore=1, spaceAfter=4
        ),
    }
    return styles


def add_page_number(canvas, doc):
    """Add page number to footer."""
    canvas.saveState()
    canvas.setFont(_font('sans'), 8)
    canvas.setFillColor(grey)
    canvas.drawCentredString(A4[0] / 2.0, 0.75 * cm, f"— {canvas.getPageNumber()} —")
    canvas.restoreState()


def add_header_footer(canvas, doc):
    """Add header line and page number."""
    canvas.saveState()
    canvas.setStrokeColor(grey)
    canvas.setLineWidth(0.3)
    canvas.line(2 * cm, A4[1] - 1.5 * cm, A4[0] - 2 * cm, A4[1] - 1.5 * cm)
    canvas.setFont(_font('sans'), 8)
    canvas.setFillColor(grey)
    canvas.drawCentredString(A4[0] / 2.0, 1 * cm, f"— {canvas.getPageNumber()} —")
    canvas.restoreState()


def build_pdf(input_path, output_path, title=None, author=None, date_str=None, stylesheet=None):
    """Main PDF builder. Converts input .md or .html to PDF."""
    input_path = Path(input_path)
    output_path = Path(output_path)

    if not input_path.exists():
        print(f"[ERROR] Input file not found: {input_path}")
        sys.exit(1)

    text = input_path.read_text(encoding='utf-8')

    # --- Unicode escape sanitization ---
    text, fix_count, fix_report = sanitize_unicode_escapes(text, source_label=input_path.name)
    if fix_count > 0:
        for line in fix_report:
            print(f"  {line}", file=sys.stderr)
        print(f"  [UNICODE-FIX] Auto-corrected {fix_count} escape sequences in source. "
              f"Regenerate the source file to prevent this warning in future builds.",
              file=sys.stderr)

    # --- YAML frontmatter stripping (v1.2) ---
    frontmatter, content_text = strip_yaml_frontmatter(text)
    if frontmatter:
        print(f"[FRONTMATTER] Extracted {len(frontmatter)} metadata fields from YAML frontmatter")
        # Use frontmatter as fallback for CLI args
        if not title and 'title' in frontmatter:
            title = frontmatter['title'].strip('"').strip("'")
        if not author and 'author' in frontmatter:
            author = frontmatter['author'].strip('"').strip("'")
        if not date_str and 'date' in frontmatter:
            date_str = frontmatter['date'].strip('"').strip("'")
        abstract = frontmatter.get('abstract', '').strip()
        if abstract:
            print(f"[FRONTMATTER] Abstract extracted ({len(abstract)} chars)")
    else:
        content_text = text  # No frontmatter found
        abstract = ''

    styles = build_styles()
    
    # Merge stylesheet overrides if provided (v1.2)
    if stylesheet:
        typo = stylesheet.get('typography', {})
        for style_name, overrides in typo.items():
            if style_name in styles:
                # Update existing style properties
                s = styles[style_name]
                if 'font_size' in overrides:
                    s.fontSize = overrides['font_size']
                if 'leading' in overrides:
                    s.leading = overrides['leading']
                if 'space_before' in overrides:
                    s.spaceBefore = overrides['space_before']
                if 'space_after' in overrides:
                    s.spaceAfter = overrides['space_after']
                if 'alignment' in overrides:
                    align_map = {'LEFT': 0, 'CENTER': 1, 'RIGHT': 2, 'JUSTIFY': 4}
                    s.alignment = align_map.get(overrides['alignment'], 0)
        print(f"[STYLESHEET] Merged style overrides")

    # Build flowables list
    flowables = []

    # Title page
    if title:
        flowables.append(Spacer(1, 1.5 * inch))
        flowables.append(Paragraph(title, styles['Title']))
        if author or date_str:
            author_line = []
            if author:
                author_line.append(author)
            if date_str:
                author_line.append(date_str)
            flowables.append(Paragraph(' | '.join(author_line), styles['Author']))
        flowables.append(Spacer(1, 0.3 * inch))
        flowables.append(HRFlowable(width="60%", thickness=1, color=black))
        flowables.append(Spacer(1, 0.3 * inch))
        
        # Abstract block (v1.2 — extracted from YAML frontmatter)
        if abstract:
            # Abstract label
            flowables.append(Paragraph('<b>Abstract</b>', 
                ParagraphStyle('AbstractLabel', parent=styles['BodyText'],
                              fontSize=10, leading=14, spaceBefore=4, spaceAfter=2,
                              textColor=black)))
            # Abstract body in grey box
            abstract_style = ParagraphStyle(
                'AbstractBody', parent=styles['BodyText'],
                fontSize=9.5, leading=14.5, alignment=TA_JUSTIFY,
                leftIndent=12, rightIndent=12,
                spaceBefore=2, spaceAfter=4,
                borderPadding=8,
                backColor='#f7f7f7'
            )
            flowables.append(Paragraph(abstract, abstract_style))
            flowables.append(Spacer(1, 0.3 * inch))
        
        # License note
        flowables.append(Paragraph(
            '<i>License: QNFO Unified License Agreement (QNFO-ULA) &bull; https://legal.qnfo.org/</i>',
            ParagraphStyle('LicenseNote', parent=styles['BodyText'],
                          fontSize=9, alignment=TA_CENTER, textColor=grey)
        ))
        flowables.append(PageBreak())

    # Parse and append content — use content_text (YAML stripped)
    suffix = input_path.suffix.lower()
    if suffix == '.md':
        content_flowables = md_to_plain_flowables(content_text, styles)
    elif suffix in ('.html', '.htm'):
        content_flowables = html_to_flowables(content_text, styles)
    else:
        content_flowables = []
        for para in content_text.split('\n\n'):
            if para.strip():
                content_flowables.append(Paragraph(para.strip(), styles['BodyText']))

    flowables.extend(content_flowables)

    # Build the PDF
    doc = SimpleDocTemplate(
        str(output_path),
        pagesize=A4,
        leftMargin=2.5 * cm,
        rightMargin=2.5 * cm,
        topMargin=2 * cm,
        bottomMargin=2 * cm,
        title=title or input_path.stem,
        author=author or 'QNFO Research',
    )

    doc.build(flowables, onFirstPage=add_header_footer, onLaterPages=add_header_footer)
    print(f"[OK] PDF built: {output_path} ({output_path.stat().st_size:,} bytes)")

    # Print math rendering summary
    if _MATH_TEMP_FILES:
        print(f"[MATH] Rendered {len(_MATH_TEMP_FILES)} math expression(s) as images")
    elif not _MATH_NO_RENDER:
        pass  # No math found


def main():
    global _MATH_NO_RENDER

    parser = argparse.ArgumentParser(description="Build PDF from Markdown or HTML")
    parser.add_argument('--input', '-i', required=True, help='Input file (.md or .html)')
    parser.add_argument('--output', '-o', help='Output PDF file path')
    parser.add_argument('--title', '-t', help='Publication title (auto-detected from first H1 if omitted)')
    parser.add_argument('--author', '-a', help='Author name')
    parser.add_argument('--date', '-d', help='Publication date (YYYY-MM-DD, defaults to today)')
    parser.add_argument('--check-unicode', action='store_true',
                        help='Scan input for literal \\uXXXX escape sequences and report (no PDF build)')
    parser.add_argument('--fix-unicode', action='store_true',
                        help='Auto-correct \\uXXXX sequences in the source file IN PLACE')
    parser.add_argument('--stylesheet', '-s',
                        help='Path to publication stylesheet JSON (default: built-in styles)')
    parser.add_argument('--no-math', action='store_true',
                        help='Skip math rendering — convert LaTeX to Unicode approximations instead')
    args = parser.parse_args()

    _MATH_NO_RENDER = args.no_math

    if _MATH_NO_RENDER:
        print("[MATH] Math rendering DISABLED (--no-math). Using Unicode approximations.")

    # Load stylesheet if provided
    stylesheet = None
    if args.stylesheet:
        stylesheet_path = Path(args.stylesheet)
        if stylesheet_path.exists():
            with open(stylesheet_path, 'r', encoding='utf-8') as f:
                stylesheet = json.load(f)
            print(f"[STYLESHEET] Loaded from {args.stylesheet}")
        else:
            print(f"[STYLESHEET] WARNING: Stylesheet not found: {args.stylesheet}")

    input_path = Path(args.input)

    # --- Unicode pre-flight check ---
    if args.check_unicode:
        if not input_path.exists():
            print(f"[ERROR] Input file not found: {input_path}")
            sys.exit(1)
        text = input_path.read_text(encoding='utf-8')
        _, fix_count, fix_report = sanitize_unicode_escapes(text, source_label=input_path.name)
        if fix_count > 0:
            for line in fix_report:
                print(line)
            print(f"\n[RESULT] {fix_count} escape sequences found in source file.")
            print("[ACTION] Run with --fix-unicode to auto-correct the source file, or rebuild the source.")
            sys.exit(1)
        else:
            print(f"[OK] No Unicode escape sequences found in {input_path.name}")
            sys.exit(0)

    # --- Unicode fix-in-place ---
    if args.fix_unicode:
        if not input_path.exists():
            print(f"[ERROR] Input file not found: {input_path}")
            sys.exit(1)
        text = input_path.read_text(encoding='utf-8')
        fixed, fix_count, fix_report = sanitize_unicode_escapes(text, source_label=input_path.name)
        if fix_count > 0:
            input_path.write_text(fixed, encoding='utf-8')
            for line in fix_report:
                print(line)
            print(f"[FIXED] {fix_count} escape sequences corrected in {input_path.name}")
        else:
            print(f"[OK] No Unicode escape sequences found in {input_path.name}")
        sys.exit(0)

    # Auto-detect title: prefer YAML frontmatter, fall back to first H1
    title = args.title
    if not title:
        try:
            text = input_path.read_text(encoding='utf-8')
            text, _, _ = sanitize_unicode_escapes(text, source_label=input_path.name)
            # Try YAML frontmatter first
            frontmatter, _ = strip_yaml_frontmatter(text)
            if frontmatter and 'title' in frontmatter:
                title = frontmatter['title'].strip('"').strip("'")
                print(f"[TITLE] Using title from YAML frontmatter: {title}")
            else:
                # Fall back to first H1
                m = re.search(r'^#\s+(.+)$', text, re.MULTILINE)
                if m:
                    title = m.group(1).strip()
                    print(f"[TITLE] Using title from first H1: {title}")
        except Exception:
            pass

    if not args.output:
        print("[ERROR] --output/-o is required for PDF generation")
        sys.exit(1)

    date_str = args.date or datetime.now().strftime('%Y-%m-%d')

    build_pdf(args.input, args.output, title=title, author=args.author, date_str=date_str, stylesheet=stylesheet)


if __name__ == '__main__':
    main()
