# -*- coding: utf-8 -*-
"""
VitalBand — finalist-round slides appended to the InstantZero deck.

Design intent: the existing slides are light, corporate and image-based. These
close the deck on a dark, premium run that reads as a product, not a poster.
Brand continuity is kept through the numbered section badge, the navy/teal/red
palette and the left rail motif — the treatment is elevated, not replaced.

Everything is native PowerPoint geometry, so every word stays editable.
"""
from pptx import Presentation
from pptx.util import Inches, Pt
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import PP_ALIGN, MSO_ANCHOR

# ── palette ─────────────────────────────────────────────────────────────────
BG      = RGBColor(0x0B, 0x25, 0x45)   # VitalBand deep navy (brand)
PANEL   = RGBColor(0x11, 0x33, 0x5C)
PANEL_2 = RGBColor(0x16, 0x3D, 0x6B)
RAIL    = RGBColor(0x07, 0x1A, 0x33)
TEAL    = RGBColor(0x22, 0xD3, 0xEE)
MINT    = RGBColor(0x10, 0xB9, 0x81)
AMBER   = RGBColor(0xF5, 0x9E, 0x0B)
RED     = RGBColor(0xEF, 0x44, 0x44)
WHITE   = RGBColor(0xFF, 0xFF, 0xFF)
MUTED   = RGBColor(0x9A, 0xB2, 0xCD)
DIM     = RGBColor(0x6B, 0x86, 0xA5)

FONT = "Calibri"
W, H = 13.333, 7.5


# ── primitives ──────────────────────────────────────────────────────────────

def shape(sl, kind, x, y, w, h, fill=None, line=None, lw=1.0, rot=None, adj=None):
    s = sl.shapes.add_shape(kind, Inches(x), Inches(y), Inches(w), Inches(h))
    if fill is None:
        s.fill.background()
    else:
        s.fill.solid()
        s.fill.fore_color.rgb = fill
    if line is None:
        s.line.fill.background()
    else:
        s.line.color.rgb = line
        s.line.width = Pt(lw)
    s.shadow.inherit = False
    if rot is not None:
        s.rotation = rot
    if adj is not None:
        try:
            s.adjustments[0] = adj
        except Exception:
            pass
    return s


def rect(sl, x, y, w, h, **kw):
    return shape(sl, MSO_SHAPE.RECTANGLE, x, y, w, h, **kw)


def card(sl, x, y, w, h, fill=PANEL):
    return shape(sl, MSO_SHAPE.ROUNDED_RECTANGLE, x, y, w, h, fill=fill, adj=0.055)


def txt(sl, x, y, w, h, body, size=12, color=WHITE, bold=False, align=PP_ALIGN.LEFT,
        anchor=MSO_ANCHOR.TOP, spacing=0.95, space_after=3, caps=False, char_space=None):
    tb = sl.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h))
    tf = tb.text_frame
    tf.word_wrap = True
    tf.margin_left = tf.margin_right = tf.margin_top = tf.margin_bottom = 0
    tf.vertical_anchor = anchor

    items = [body] if isinstance(body, str) else body
    for i, item in enumerate(items):
        s_, ov = (item, {}) if isinstance(item, str) else item
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.alignment = ov.get("align", align)
        p.space_after = Pt(ov.get("space_after", space_after))
        p.line_spacing = ov.get("spacing", spacing)
        r = p.add_run()
        r.text = s_.upper() if ov.get("caps", caps) else s_
        f = r.font
        f.size = Pt(ov.get("size", size))
        f.bold = ov.get("bold", bold)
        f.color.rgb = ov.get("color", color)
        f.name = FONT
        cs = ov.get("char_space", char_space)
        if cs:
            f._rPr.set("spc", str(int(cs * 100)))
    return tb


def chrome(sl, num, title, kicker):
    """Dark canvas + left rail + numbered badge + title."""
    rect(sl, 0, 0, W, H, fill=BG)
    rect(sl, 0, 0, 0.52, H, fill=RAIL)
    shape(sl, MSO_SHAPE.OVAL, 0.14, 0.30, 0.24, 0.24, fill=TEAL)

    shape(sl, MSO_SHAPE.ROUNDED_RECTANGLE, 0.86, 0.34, 0.86, 0.50, fill=TEAL, adj=0.18)
    txt(sl, 0.86, 0.44, 0.86, 0.32, num, size=21, color=BG, bold=True,
        align=PP_ALIGN.CENTER)

    txt(sl, 1.92, 0.30, 8.4, 0.40, title, size=27, color=WHITE, bold=True,
        anchor=MSO_ANCHOR.MIDDLE, char_space=0.4)
    txt(sl, 1.94, 0.74, 8.4, 0.26, kicker, size=11.5, color=TEAL, bold=True,
        char_space=0.8, caps=True)

    txt(sl, 10.0, 0.40, 2.95, 0.30, "VITALBAND", size=11, color=DIM, bold=True,
        align=PP_ALIGN.RIGHT, char_space=2.0)
    txt(sl, 10.0, 0.64, 2.95, 0.26, "Team InstantZero", size=10, color=DIM,
        align=PP_ALIGN.RIGHT)


def kpi(sl, x, y, w, value, label, sub, accent):
    """Oversized number with a hairline accent above it."""
    rect(sl, x, y, 0.42, 0.045, fill=accent)
    txt(sl, x, y + 0.20, w, 0.78, value, size=44, color=WHITE, bold=True, spacing=0.88)
    txt(sl, x, y + 1.02, w, 0.26, label, size=11, color=accent, bold=True,
        caps=True, char_space=0.8)
    txt(sl, x, y + 1.30, w, 0.44, sub, size=9.5, color=MUTED, spacing=1.0)


def bullet_block(sl, x, y, w, items, accent):
    """Small square marker + bold lead + supporting line."""
    cy = y
    for lead, rest in items:
        shape(sl, MSO_SHAPE.RECTANGLE, x, cy + 0.055, 0.075, 0.075, fill=accent)
        txt(sl, x + 0.22, cy, w - 0.22, 0.22, lead, size=11, color=WHITE, bold=True)
        txt(sl, x + 0.22, cy + 0.235, w - 0.22, 0.40, rest, size=10, color=MUTED,
            spacing=1.02)
        cy += 0.235 + 0.40 + 0.10
    return cy


def footer(sl, line, accent=TEAL):
    rect(sl, 0.86, 6.83, 0.055, 0.40, fill=accent)
    txt(sl, 1.08, 6.86, 11.9, 0.34, line, size=12.5, color=WHITE, bold=True,
        anchor=MSO_ANCHOR.MIDDLE)


def new_slide(prs):
    s = prs.slides.add_slide(prs.slide_layouts[6])
    for ph in list(s.placeholders):
        ph._element.getparent().remove(ph._element)
    return s


# ── 07 · BUILT & VERIFIED ───────────────────────────────────────────────────

def s_built(prs):
    s = new_slide(prs)
    chrome(s, "07", "Built, Running, Verified", "not a mockup — measured on the live system")

    xs = [0.86, 4.02, 7.18, 10.34]
    data = [
        ("22", "Live API endpoints", "Every one returning 200 on the running server.", TEAL),
        ("4", "Alert languages", "Tamil · Hindi · Kannada · English, cached offline.", MINT),
        ("₹2,000", "Per patient", "Against ₹11,000 for a basic vitals monitor.", AMBER),
        ("0", "Failed checks", "12/12 smoke tests · clean production build.", RED),
    ]
    for x, (v, l, sub, a) in zip(xs, data):
        kpi(s, x, 1.28, 2.75, v, l, sub, a)

    # signal path
    rect(s, 0.86, 3.30, 12.05, 0.02, fill=PANEL_2)
    txt(s, 0.86, 3.48, 5.0, 0.24, "The signal path, end to end", size=11,
        color=TEAL, bold=True, caps=True, char_space=0.8)

    steps = [
        ("WRIST PATCH", "MAX30102 + ESP32", TEAL),
        ("TELEMETRY", "HTTPS every 5s", TEAL),
        ("TRIAGE ENGINE", "Rules + JEV index", MINT),
        ("NURSE CONSOLE", "Floorplan + voice", AMBER),
    ]
    bx, bw, gap = 0.86, 2.86, 0.20
    for i, (t, sub, a) in enumerate(steps):
        x = bx + i * (bw + gap)
        card(s, x, 3.84, bw, 0.92, PANEL)
        rect(s, x, 3.84, 0.045, 0.92, fill=a)
        txt(s, x + 0.24, 4.02, bw - 0.40, 0.26, t, size=11.5, color=WHITE, bold=True,
            char_space=0.5)
        txt(s, x + 0.24, 4.31, bw - 0.40, 0.26, sub, size=9.5, color=MUTED)
        if i < 3:
            shape(s, MSO_SHAPE.ISOSCELES_TRIANGLE, x + bw + 0.045, 4.19, 0.11, 0.18,
                  fill=DIM, rot=90)

    # identified patient strip
    card(s, 0.86, 5.00, 12.05, 1.60, PANEL)
    rect(s, 0.86, 5.00, 0.045, 1.60, fill=MINT)
    txt(s, 1.14, 5.18, 6.0, 0.26, "One RFID tap → the full clinical record", size=13,
        color=WHITE, bold=True)
    txt(s, 1.14, 5.47, 11.4, 0.24,
        "The camera sees a body collapse. The tap turns it into a named patient before the nurse arrives.",
        size=10, color=MUTED)

    cols = [
        ("Demographics", "Name · age · gender · relation"),
        ("Clinical history", "Blood group · allergies · conditions"),
        ("Prior tests", "Blood · sugar · ECG · X-ray · MRI"),
        ("Attendant", "Who to call, with number"),
    ]
    cw = 11.5 / 4
    for i, (h_, b_) in enumerate(cols):
        x = 1.14 + i * cw
        txt(s, x, 5.88, cw - 0.25, 0.24, h_, size=10.5, color=MINT, bold=True)
        txt(s, x, 6.14, cw - 0.25, 0.34, b_, size=9.5, color=MUTED)

    footer(s, "Every figure here was measured on the running system — none of it is estimated.")
    s.notes_slide.notes_text_frame.text = (
        "Open with: this is a working system, not slideware. 22 endpoints live, 12/12 passing. "
        "Then the RFID line — it answers 'what does the camera actually know about the patient?'")
    return s


# ── 08 · THE LINE AI CANNOT CROSS ───────────────────────────────────────────

def s_safety(prs):
    s = new_slide(prs)
    chrome(s, "08", "The Line Our AI Cannot Cross", "two engines — only one may declare an emergency")

    # deterministic lane
    card(s, 0.86, 1.30, 5.85, 2.28, PANEL)
    rect(s, 0.86, 1.30, 0.045, 2.28, fill=RED)
    txt(s, 1.16, 1.50, 5.2, 0.26, "DETERMINISTIC PATH", size=12, color=RED, bold=True,
        char_space=1.0)
    txt(s, 1.16, 1.78, 5.2, 0.26, "Always fires. No AI anywhere in it.", size=10.5,
        color=MUTED)
    bullet_block(s, 1.16, 2.16, 5.3, [
        ("SOS button", "Instant, unconditional, no cooldown."),
        ("Fixed clinical limits", "HR outside 50–120, SpO2 below 92%. Not learned, not tunable."),
    ], RED)

    # ai lane
    card(s, 7.08, 1.30, 5.85, 2.28, PANEL)
    rect(s, 7.08, 1.30, 0.045, 2.28, fill=TEAL)
    txt(s, 7.38, 1.50, 5.2, 0.26, "JEV AI LAYER", size=12, color=TEAL, bold=True,
        char_space=1.0)
    txt(s, 7.38, 1.78, 5.2, 0.26, "May raise attention. May never lower it.", size=10.5,
        color=MUTED)
    bullet_block(s, 7.38, 2.16, 5.3, [
        ("Deterioration Index 0–100", "Weighted trend across the last 30 telemetry frames."),
        ("Explains every point", "Each one traces to a named factor a nurse can argue with."),
    ], TEAL)

    # the proof
    card(s, 0.86, 3.76, 12.05, 2.86, PANEL_2)
    txt(s, 1.16, 3.96, 6.0, 0.26, "PROVEN LIVE", size=11.5, color=TEAL, bold=True,
        char_space=1.0)

    # gauge
    gx, gy, gd = 1.20, 4.36, 1.82
    shape(s, MSO_SHAPE.OVAL, gx, gy, gd, gd, fill=None,
          line=RGBColor(0x1C, 0x4A, 0x7A), lw=9)
    shape(s, MSO_SHAPE.OVAL, gx, gy, gd, gd, fill=None, line=MINT, lw=9)
    shape(s, MSO_SHAPE.OVAL, gx + 0.09, gy - 0.02, gd - 0.18, 0.62, fill=PANEL_2)
    txt(s, gx, gy + 0.50, gd, 0.52, "0.0", size=36, color=MINT, bold=True,
        align=PP_ALIGN.CENTER)
    txt(s, gx, gy + 1.10, gd, 0.24, "AI INDEX · LOW", size=9, color=MUTED,
        align=PP_ALIGN.CENTER, char_space=0.6)

    # verdict
    vx = 3.42
    txt(s, vx, 4.40, 4.0, 0.24, "Same patient, same second", size=10.5, color=MUTED)
    shape(s, MSO_SHAPE.ROUNDED_RECTANGLE, vx, 4.70, 3.55, 0.62, fill=RED, adj=0.18)
    txt(s, vx, 4.84, 3.55, 0.36, "LEVEL 1 EMERGENCY", size=15, color=WHITE, bold=True,
        align=PP_ALIGN.CENTER, char_space=0.6)
    txt(s, vx, 5.46, 3.62, 0.86,
        "The AI scored this patient calm. The alert fired anyway, because the SOS button "
        "is deterministic — the model is never asked for permission.",
        size=10, color=MUTED, spacing=1.05)

    # divider
    rect(s, 7.30, 4.32, 0.02, 2.04, fill=RGBColor(0x1E, 0x45, 0x74))

    # trend contrast
    txt(s, 7.62, 4.36, 5.0, 0.26, "Why a trend beats a threshold", size=12,
        color=WHITE, bold=True)
    rows = [
        ("Recovering  142 → 78 BPM", "0.5", MINT),
        ("Crashing  78 → 142 BPM", "80.5", RED),
    ]
    ry = 4.76
    for label, score, col in rows:
        card(s, 7.62, ry, 5.00, 0.60, PANEL)
        rect(s, 7.62, ry, 0.045, 0.60, fill=col)
        txt(s, 7.90, ry + 0.17, 3.3, 0.26, label, size=10.5, color=WHITE)
        txt(s, 11.05, ry + 0.11, 1.42, 0.38, score, size=19, color=col, bold=True,
            align=PP_ALIGN.RIGHT)
        ry += 0.70
    txt(s, 7.62, 6.14, 5.00, 0.34,
        "Identical readings, opposite directions — a threshold cannot separate them.",
        size=10, color=MUTED, spacing=1.05)

    footer(s, "The AI is a second pair of eyes. It never holds the alarm.", TEAL)
    s.notes_slide.notes_text_frame.text = (
        "THE slide. Say: our AI can only ever raise attention, never lower it. Point at the gauge "
        "reading 0.0 beside LEVEL 1 EMERGENCY — that contradiction is the safety design working. "
        "Then the trend contrast: same vitals, opposite trajectory.")
    return s


# ── 09 · SELF-IMPROVING & SECURE ────────────────────────────────────────────

def s_ops(prs):
    s = new_slide(prs)
    chrome(s, "09", "It Improves Itself — and Proves It", "continuous retraining under a hard safety ceiling")

    # retrain cycle
    txt(s, 0.86, 1.26, 6.0, 0.26, "THE RETRAIN LOOP", size=11.5, color=TEAL, bold=True,
        char_space=1.0)
    cycle = [
        ("01", "Ingest", "Every wristband reading is stored."),
        ("02", "Refit", "Baseline recalculated every 50 readings."),
        ("03", "Score", "Flag rate and drift measured honestly."),
        ("04", "Promote", "Or roll back in one click."),
    ]
    cx, cw2, g2 = 0.86, 1.52, 0.17
    for i, (n, t, d) in enumerate(cycle):
        x = cx + i * (cw2 + g2)
        card(s, x, 1.60, cw2, 1.62, PANEL)
        txt(s, x, 1.76, cw2, 0.30, n, size=16, color=TEAL, bold=True, align=PP_ALIGN.CENTER)
        txt(s, x, 2.10, cw2, 0.24, t, size=11, color=WHITE, bold=True, align=PP_ALIGN.CENTER)
        txt(s, x + 0.12, 2.38, cw2 - 0.24, 0.70, d, size=9, color=MUTED,
            align=PP_ALIGN.CENTER, spacing=1.05)
        if i < 3:
            shape(s, MSO_SHAPE.ISOSCELES_TRIANGLE, x + cw2 + 0.035, 2.32, 0.10, 0.16,
                  fill=DIM, rot=90)

    # ceiling callout
    card(s, 7.62, 1.60, 5.30, 1.62, RGBColor(0x3A, 0x18, 0x18))
    rect(s, 7.62, 1.60, 0.045, 1.62, fill=RED)
    txt(s, 7.92, 1.80, 4.8, 0.26, "THE HARD CEILING", size=11.5, color=RED, bold=True,
        char_space=1.0)
    txt(s, 7.92, 2.10, 4.75, 1.00,
        "Retraining tunes only the secondary statistical signal. The clinical thresholds, "
        "the fall logic and the SOS button are never modified by any model — enforced in "
        "code, and stated in the API response itself.",
        size=10, color=RGBColor(0xF2, 0xC8, 0xC8), spacing=1.06)

    # security chain
    txt(s, 0.86, 3.46, 6.0, 0.26, "TAMPER-EVIDENT AUDIT TRAIL", size=11.5, color=MINT,
        bold=True, char_space=1.0)
    txt(s, 0.86, 3.74, 6.2, 0.24, "Each entry signs the one before it, HMAC-SHA256.",
        size=10, color=MUTED)

    link = ["LOGIN", "VIEW", "OVERRIDE", "EXPORT"]
    lx = 0.86
    for i, lab in enumerate(link):
        x = lx + i * 1.62
        card(s, x, 4.10, 1.42, 0.56, PANEL)
        txt(s, x, 4.26, 1.42, 0.26, lab, size=10, color=WHITE, bold=True,
            align=PP_ALIGN.CENTER, char_space=0.5)
        if i < 3:
            rect(s, x + 1.42, 4.37, 0.20, 0.025, fill=MINT)
    txt(s, 0.86, 4.78, 6.2, 0.34,
        "Alter any historical row and every signature after it fails verification.",
        size=10, color=MUTED)

    # compliance
    card(s, 7.62, 3.46, 5.30, 1.86, PANEL)
    rect(s, 7.62, 3.46, 0.045, 1.86, fill=MINT)
    txt(s, 7.92, 3.64, 4.8, 0.26, "DPDP ACT 2023", size=11.5, color=MINT, bold=True,
        char_space=1.0)
    bullet_block(s, 7.92, 3.92, 4.85, [
        ("Privacy mask", "Every name on screen becomes P-***1 in one click."),
        ("Role-based access", "Admin routes gated; per-hospital scoping."),
    ], MINT)

    # delivered roadmap
    card(s, 0.86, 5.44, 12.05, 1.16, PANEL_2)
    txt(s, 1.16, 5.60, 4.6, 0.24, "OUR SLIDE-06 ROADMAP — NOW SHIPPED", size=10.5,
        color=AMBER, bold=True, char_space=0.6)
    done = ["Multi-patient ward dashboard", "Tamil · Hindi · Kannada alerts",
            "Predictive AI risk scoring", "Patient history on demand"]
    dw = 11.5 / 4
    for i, d in enumerate(done):
        x = 1.16 + i * dw
        shape(s, MSO_SHAPE.OVAL, x, 5.98, 0.20, 0.20, fill=MINT)
        txt(s, x, 5.995, 0.20, 0.18, u"✓", size=9, color=BG, bold=True,
            align=PP_ALIGN.CENTER)
        txt(s, x + 0.30, 5.96, dw - 0.46, 0.44, d, size=10, color=WHITE, spacing=1.02)

    footer(s, "We did not just plan the next version. We shipped it.", MINT)
    s.notes_slide.notes_text_frame.text = (
        "If pushed on MLOps, show the ROLLBACK, not a green dashboard. Two of our runs genuinely "
        "hit the safety ceiling and are flagged amber — a pipeline that catches its own bad model "
        "is more convincing than one that has only ever seen good ones.")
    return s


# ── 10 · CLOSE ──────────────────────────────────────────────────────────────

def s_close(prs):
    s = new_slide(prs)
    rect(s, 0, 0, W, H, fill=BG)
    rect(s, 0, 0, 0.52, H, fill=RAIL)
    shape(s, MSO_SHAPE.OVAL, 0.14, 0.30, 0.24, 0.24, fill=TEAL)

    txt(s, 1.30, 1.30, 11.0, 0.30, "THE PRE-ADMISSION GAP", size=12, color=TEAL,
        bold=True, char_space=2.2)
    txt(s, 1.30, 1.74, 10.9, 1.70,
        "Nobody covers the minutes between walking\ninto a hospital and being admitted.",
        size=36, color=WHITE, bold=True, spacing=1.06)

    rect(s, 1.30, 3.62, 1.10, 0.05, fill=TEAL)

    txt(s, 1.30, 3.92, 10.6, 0.60,
        "VitalBand closes it for about ₹2,000 a patient — a rotating scan machine for the "
        "waiting room, a wristband once admitted, and an alert path no AI is allowed to silence.",
        size=14, color=MUTED, spacing=1.12)

    pillars = [
        ("₹2,000", "per patient", TEAL),
        ("4", "languages spoken", MINT),
        ("0", "AI veto over an alarm", RED),
    ]
    px = 1.30
    for i, (v, l, a) in enumerate(pillars):
        x = px + i * 3.85
        rect(s, x, 4.92, 0.42, 0.045, fill=a)
        txt(s, x, 5.10, 3.4, 0.62, v, size=34, color=WHITE, bold=True)
        txt(s, x, 5.76, 3.4, 0.28, l, size=11, color=a, bold=True, caps=True,
            char_space=0.7)

    rect(s, 1.30, 6.42, 11.4, 0.02, fill=RGBColor(0x1E, 0x45, 0x74))
    txt(s, 1.30, 6.62, 7.6, 0.30,
        "No patient should have to collapse before being noticed.",
        size=13, color=WHITE, bold=True)
    txt(s, 9.0, 6.62, 3.7, 0.30, "Team InstantZero  ·  CIT", size=11, color=DIM,
        align=PP_ALIGN.RIGHT)

    s.notes_slide.notes_text_frame.text = (
        "Close on the story, not the tech. Land the last line and stop talking.")
    return s


def main():
    prs = Presentation("original.pptx")
    s_built(prs)
    s_safety(prs)
    s_ops(prs)
    s_close(prs)

    lst = prs.slides._sldIdLst
    ids = list(lst)
    new = ids[-4:]
    for n in new:
        lst.remove(n)
    for i, n in enumerate(new[:3]):      # 07-09 before "Why Us"
        lst.insert(6 + i, n)
    lst.append(new[3])                   # closing slide last

    prs.save("InstantZero-final.pptx")
    print("saved InstantZero-final.pptx with %d slides" % len(lst))


if __name__ == "__main__":
    main()
