# -*- coding: utf-8 -*-
"""
Append new slides to InstantZero deck, matching the existing template.

The existing content slides are flat images, so their text cannot be edited.
These new slides are NATIVE PowerPoint shapes — fully editable — drawn in the
same visual language sampled from the template:
    navy  #1F4E79   teal #028090   red #C62828
    card tints: blue #EBF3FB, teal #F0FDF9, green #F0FDF4, amber #FFF8E1
Layout motif copied from slides 04-06: navy left rail with a teal dot, a
numbered badge, a navy rule under the header, and cards with coloured header
bars.
"""
from pptx import Presentation
from pptx.util import Inches, Pt, Emu
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import PP_ALIGN, MSO_ANCHOR

NAVY   = RGBColor(0x1F, 0x4E, 0x79)
TEAL   = RGBColor(0x02, 0x80, 0x90)
RED    = RGBColor(0xC6, 0x28, 0x28)
GREEN  = RGBColor(0x1B, 0x7F, 0x3B)
AMBER  = RGBColor(0xB8, 0x6E, 0x00)
WHITE  = RGBColor(0xFF, 0xFF, 0xFF)
INK    = RGBColor(0x1A, 0x1A, 0x1A)
MUTED  = RGBColor(0x55, 0x65, 0x75)
BORDER = RGBColor(0xD6, 0xDF, 0xEA)

TINT = {
    "navy":  RGBColor(0xEB, 0xF3, 0xFB),
    "teal":  RGBColor(0xF0, 0xFD, 0xF9),
    "green": RGBColor(0xF0, 0xFD, 0xF4),
    "amber": RGBColor(0xFF, 0xF8, 0xE1),
    "grey":  RGBColor(0xF8, 0xFA, 0xFC),
    "red":   RGBColor(0xFD, 0xF0, 0xF0),
}
HEAD = {"navy": NAVY, "teal": TEAL, "green": GREEN, "amber": AMBER, "red": RED}

BODY_FONT = "Calibri"
HEAD_FONT = "Calibri"

W, H = 13.333, 7.5


# ── primitives ──────────────────────────────────────────────────────────────

def rect(slide, x, y, w, h, fill=None, line=None, line_w=0.75, shape=MSO_SHAPE.RECTANGLE):
    s = slide.shapes.add_shape(shape, Inches(x), Inches(y), Inches(w), Inches(h))
    if fill is None:
        s.fill.background()
    else:
        s.fill.solid()
        s.fill.fore_color.rgb = fill
    if line is None:
        s.line.fill.background()
    else:
        s.line.color.rgb = line
        s.line.width = Pt(line_w)
    s.shadow.inherit = False
    return s


def text(slide, x, y, w, h, runs, size=12, color=INK, bold=False, align=PP_ALIGN.LEFT,
         font=BODY_FONT, anchor=MSO_ANCHOR.TOP, space_after=3, line_spacing=0.95):
    """runs: a string, or a list of (text, {overrides}) paragraphs."""
    tb = slide.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h))
    tf = tb.text_frame
    tf.word_wrap = True
    tf.margin_left = tf.margin_right = tf.margin_top = tf.margin_bottom = 0
    tf.vertical_anchor = anchor

    items = [runs] if isinstance(runs, str) else runs
    for i, item in enumerate(items):
        if isinstance(item, str):
            body, ov = item, {}
        else:
            body, ov = item
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.alignment = ov.get("align", align)
        p.space_after = Pt(ov.get("space_after", space_after))
        p.line_spacing = ov.get("line_spacing", line_spacing)
        r = p.add_run()
        r.text = body
        f = r.font
        f.size = Pt(ov.get("size", size))
        f.bold = ov.get("bold", bold)
        f.color.rgb = ov.get("color", color)
        f.name = ov.get("font", font)
    return tb


def header(slide, number, title, subtitle=None):
    """Navy left rail + teal dot + numbered badge + title + rule."""
    rect(slide, 0, 0, 0.62, H, fill=NAVY)
    dot = rect(slide, 0.13, 0.20, 0.36, 0.36, fill=TEAL, shape=MSO_SHAPE.OVAL)
    rect(slide, 0.22, 0.29, 0.18, 0.18, fill=WHITE, shape=MSO_SHAPE.OVAL)

    rect(slide, 0.88, 0.16, 0.78, 0.44, fill=NAVY)
    text(slide, 0.88, 0.24, 0.78, 0.30, number, size=19, color=WHITE, bold=True,
         align=PP_ALIGN.CENTER, font=HEAD_FONT)

    text(slide, 1.78, 0.19, 8.6, 0.40,
         [("/  ", {"color": MUTED}), ], size=20)  # placeholder, replaced below
    # title (single run keeps kerning tidy)
    slide.shapes._spTree.remove(slide.shapes[-1]._element)
    text(slide, 1.78, 0.18, 9.2, 0.42, "/  " + title, size=21, color=NAVY, bold=True,
         font=HEAD_FONT, anchor=MSO_ANCHOR.MIDDLE)

    if subtitle:
        text(slide, 10.6, 0.24, 2.45, 0.32, subtitle, size=10.5, color=TEAL, bold=True,
             align=PP_ALIGN.RIGHT)

    rect(slide, 0.88, 0.70, 12.05, 0.035, fill=NAVY)


def card(slide, x, y, w, h, heading, tone="navy"):
    """White card with a coloured header bar, matching template slides 04-06."""
    rect(slide, x, y, w, h, fill=WHITE, line=BORDER)
    rect(slide, x, y, w, 0.34, fill=HEAD[tone])
    text(slide, x + 0.14, y + 0.075, w - 0.28, 0.22, heading, size=11, color=WHITE,
         bold=True, font=HEAD_FONT)
    return y + 0.34


def bullets(slide, x, y, w, items, size=10.5, gap=0.005, tone=TEAL):
    """items: list of (bold_lead, rest) or plain strings."""
    paras = []
    for it in items:
        if isinstance(it, tuple):
            lead, rest = it
            paras.append((lead, {"bold": True, "color": tone, "size": size, "space_after": 1}))
            paras.append((rest, {"size": size, "color": INK, "space_after": 7}))
        else:
            paras.append((it, {"size": size, "color": INK, "space_after": 7}))
    text(slide, x, y, w, 0.2, paras, size=size)


def stat(slide, x, y, w, h, value, label, sub, fill, value_color=WHITE, label_color=WHITE):
    rect(slide, x, y, w, h, fill=fill)
    text(slide, x + 0.18, y + 0.16, w - 0.36, 0.52, value, size=27, color=value_color,
         bold=True, font=HEAD_FONT)
    text(slide, x + 0.18, y + 0.72, w - 0.36, 0.26, label, size=10.5, color=label_color,
         bold=True)
    text(slide, x + 0.18, y + 0.99, w - 0.36, 0.26, sub, size=8.5,
         color=RGBColor(0xD5, 0xE2, 0xEE))


def footer(slide, message, tone=NAVY):
    rect(slide, 0.88, 6.92, 12.05, 0.42, fill=tone)
    text(slide, 1.10, 7.00, 11.6, 0.28, message, size=11.5, color=WHITE, bold=True,
         anchor=MSO_ANCHOR.MIDDLE)


def new_slide(prs):
    s = prs.slides.add_slide(prs.slide_layouts[6])   # Blank
    for ph in list(s.placeholders):                  # drop inherited placeholders
        ph._element.getparent().remove(ph._element)
    rect(s, 0, 0, W, H, fill=WHITE)
    return s


# ── slides ──────────────────────────────────────────────────────────────────

def slide_built(prs):
    s = new_slide(prs)
    header(s, "07", "BUILT & VERIFIED", "working system, not a mockup")

    stat(s, 0.88, 0.95, 2.86, 1.40, "22", "LIVE API ENDPOINTS", "all returning 200 on the running server", NAVY)
    stat(s, 3.94, 0.95, 2.86, 1.40, "4", "ALERT LANGUAGES", "Tamil · Hindi · Kannada · English", TEAL)
    stat(s, 7.00, 0.95, 2.86, 1.40, "~Rs 2,000", "PER PATIENT", "vs Rs 11,000 for a basic vitals monitor", GREEN)
    stat(s, 10.06, 0.95, 2.87, 1.40, "0", "FAILED CHECKS", "12/12 smoke tests, clean production build", RED)

    top = card(s, 0.88, 2.55, 3.86, 2.12, "PLATFORM  ·  RUNNING NOW", "navy")
    bullets(s, 1.04, top + 0.14, 3.54, [
        ("FastAPI + React / TypeScript", "Live nurse dashboard over WebSocket."),
        ("Role-based login", "Separate nurse and admin consoles, JWT secured."),
        ("SQLite + SQLAlchemy", "Permanent event history, never overwritten."),
    ])

    top = card(s, 4.94, 2.55, 3.86, 2.12, "WHAT THE NURSE SEES", "teal")
    bullets(s, 5.10, top + 0.14, 3.54, [
        ("Interactive ward floorplan", "Waiting room and beds 101-108, live ECG per bed."),
        ("Scan-machine camera", "MediaPipe pose overlay streaming in the dashboard."),
        ("Hover any bed", "HR, SpO2, RFID tag and link status instantly."),
    ], tone=TEAL)

    top = card(s, 9.00, 2.55, 3.93, 2.12, "DEVICE LAYER", "green")
    bullets(s, 9.16, top + 0.14, 3.61, [
        ("ESP32 + MAX30102 firmware", "Compiles clean; LCD shows live HR and SpO2."),
        ("SOS on a hardware interrupt", "Never missed, even mid-WiFi call."),
        ("RFID check-in", "A tag resolves to the full clinical record."),
    ], tone=GREEN)

    top = card(s, 0.88, 4.85, 12.05, 1.70, "IDENTIFIED PATIENT  ·  WHAT APPEARS THE MOMENT A TAG IS SCANNED", "amber")
    cols = [
        ("Demographics", "Name, age, gender, relation to attendant"),
        ("Clinical history", "Blood group, allergies, ongoing conditions, medications"),
        ("Prior tests", "Blood, sugar, ECG, X-ray, MRI, urine - flagged when abnormal"),
        ("Attendant contact", "Who to call, with phone number"),
    ]
    cw = 12.05 / 4
    for i, (h_, b_) in enumerate(cols):
        x = 0.88 + i * cw
        text(s, x + 0.16, top + 0.20, cw - 0.32, 0.24, h_, size=11, color=AMBER, bold=True)
        text(s, x + 0.16, top + 0.50, cw - 0.32, 0.70, b_, size=10, color=INK)

    footer(s, "Every number on this slide was measured on the running system, not estimated.")
    s.notes_slide.notes_text_frame.text = (
        "Lead with: this is a working system. 22 endpoints live, 12/12 smoke tests passing. "
        "The identified-patient row is the answer to 'what does the camera actually know about the patient?'"
    )
    return s


def slide_safety(prs):
    s = new_slide(prs)
    header(s, "08", "AI SAFETY ARCHITECTURE", "why our AI cannot cause harm")

    text(s, 0.88, 0.92, 12.05, 0.34,
         "Two engines run side by side. Only one of them is allowed to decide an emergency.",
         size=13, color=MUTED)

    top = card(s, 0.88, 1.42, 5.85, 2.10, "DETERMINISTIC PATH  ·  ALWAYS FIRES", "red")
    bullets(s, 1.04, top + 0.16, 5.53, [
        ("SOS button", "Instant, unconditional, no cooldown. Zero AI in this path."),
        ("Fixed clinical limits", "HR outside 50-120, SpO2 below 92%. Not learned, not tunable by any model."),
        ("Confirmed fall", "Drop detected, then 2 seconds of stillness before it counts."),
    ], tone=RED)

    top = card(s, 7.08, 1.42, 5.85, 2.10, "JEV AI LAYER  ·  CAN ONLY RAISE ATTENTION", "teal")
    bullets(s, 7.24, top + 0.16, 5.53, [
        ("Deterioration Index 0-100", "Weighted trend score over the last 30 telemetry frames."),
        ("Explains itself", "Every point traces to a named clinical factor a nurse can argue with."),
        ("Never suppresses", "It cannot lower a triage level or stand an alert down."),
    ], tone=TEAL)

    top = card(s, 0.88, 3.78, 12.05, 2.92, "PROVEN ON THE LIVE SYSTEM", "navy")

    text(s, 1.10, top + 0.22, 5.6, 0.28, "Case 1  -  SOS pressed, vitals calm", size=12, color=NAVY, bold=True)
    text(s, 1.10, top + 0.58, 5.6, 1.30, [
        ("AI Deterioration Index:  0.0  (LOW)", {"size": 11, "color": TEAL, "bold": True, "space_after": 4}),
        ("Verdict:  LEVEL 1 EMERGENCY", {"size": 11, "color": RED, "bold": True, "space_after": 6}),
        ("The score said the patient looked fine. The alert fired anyway, because the button is deterministic.",
         {"size": 10.5, "color": INK, "space_after": 8}),
        ("This is the safety path working exactly as designed.", {"size": 10.5, "color": NAVY, "bold": True}),
    ])

    rect(s, 6.92, top + 0.22, 0.02, 2.20, fill=BORDER)

    text(s, 7.24, top + 0.22, 5.5, 0.28, "Case 2  -  identical vitals, opposite trajectory", size=12, color=NAVY, bold=True)
    text(s, 7.24, top + 0.58, 5.5, 1.30, [
        ("Recovering patient  (142 -> 78 BPM):   0.5", {"size": 11, "color": GREEN, "bold": True, "space_after": 4}),
        ("Crashing patient  (78 -> 142 BPM):   80.5", {"size": 11, "color": RED, "bold": True, "space_after": 6}),
        ("Same instantaneous readings. A fixed threshold cannot tell these two patients apart - the trend engine can.",
         {"size": 10.5, "color": INK, "space_after": 8}),
        ("A threshold sees a number. The index sees a direction.", {"size": 10.5, "color": NAVY, "bold": True}),
    ])

    footer(s, "The AI is a second pair of eyes, never the one holding the alarm.", NAVY)
    s.notes_slide.notes_text_frame.text = (
        "This is the strongest slide. Demo it live: press SOS with calm vitals, show the gauge reading LOW "
        "while the header says LEVEL 1 EMERGENCY. Then the recovering-vs-crashing contrast."
    )
    return s


def slide_ops(prs):
    s = new_slide(prs)
    header(s, "09", "MLOPS, SECURITY & ROADMAP", "it improves itself, and proves it")

    top = card(s, 0.88, 0.95, 3.86, 2.95, "SELF-IMPROVING MODEL", "teal")
    bullets(s, 1.04, top + 0.16, 3.54, [
        ("Retrains every 50 readings", "Refits the baseline from stored vitals."),
        ("Versioned with rollback", "Append-only registry; one click restores a model."),
        ("Measures its own drift", "Flags when the cohort stops matching the model."),
        ("Admits when it is wrong", "A miscalibrated model is marked, not hidden."),
    ], tone=TEAL)

    top = card(s, 4.94, 0.95, 3.86, 2.95, "SECURITY  ·  DPDP ACT 2023", "navy")
    bullets(s, 5.10, top + 0.16, 3.54, [
        ("Tamper-evident audit trail", "HMAC-SHA256 chain; each entry signs the previous."),
        ("One-click privacy mask", "Every name on screen becomes P-***1."),
        ("Role-based access", "Admin routes gated; queries scoped per hospital."),
        ("Data minimisation", "Only triage vitals kept. No face or audio data."),
    ], tone=NAVY)

    top = card(s, 9.00, 0.95, 3.93, 2.95, "SAFETY BOUNDARY", "red")
    text(s, 9.16, top + 0.20, 3.61, 2.40, [
        ("Retraining tunes ONLY the secondary statistical signal.",
         {"size": 11.5, "color": RED, "bold": True, "space_after": 9}),
        ("The deterministic clinical thresholds, the fall logic and the SOS button are never modified by any model, ever.",
         {"size": 10.5, "color": INK, "space_after": 9}),
        ("A retrained model can raise extra attention. It can never stand down an alert the rules would have raised.",
         {"size": 10.5, "color": INK, "space_after": 9}),
        ("That boundary is enforced in code and stated in the API response itself.",
         {"size": 10, "color": MUTED}),
    ])

    top = card(s, 0.88, 4.10, 12.05, 2.35, "OUR OWN ROADMAP  -  NOW DELIVERED", "green")
    text(s, 1.10, top + 0.20, 11.6, 0.26,
         "Every item below was listed as a Future Enhancement on slide 06. All four are now built and running.",
         size=10.5, color=MUTED)

    done = [
        ("Multi-patient ward dashboard", "Interactive SVG floorplan, beds 101-108 plus waiting room."),
        ("Multilingual voice alerts", "Tamil, Hindi, Kannada and English - cached audio, works offline."),
        ("Predictive AI risk scoring", "JEV Deterioration Index with a full reasoning breakdown."),
        ("Patient history on demand", "RFID check-in pulls the full clinical record and prior tests."),
    ]
    cw = 12.05 / 4
    for i, (h_, b_) in enumerate(done):
        x = 0.88 + i * cw
        rect(s, x + 0.16, top + 0.62, 0.22, 0.22, fill=GREEN, shape=MSO_SHAPE.OVAL)
        text(s, x + 0.185, top + 0.625, 0.19, 0.22, u"✓", size=10, color=WHITE,
             bold=True, align=PP_ALIGN.CENTER)
        text(s, x + 0.46, top + 0.60, cw - 0.64, 0.50, h_, size=11, color=GREEN, bold=True)
        text(s, x + 0.46, top + 0.94, cw - 0.64, 0.80, b_, size=10, color=INK)

    footer(s, "We did not just plan the next version. We shipped it.", GREEN)
    s.notes_slide.notes_text_frame.text = (
        "Best MLOps answer if pushed: show the ROLLBACK, not a green dashboard. Two of our training runs "
        "genuinely hit the safety ceiling and are flagged amber - a pipeline that catches its own bad model "
        "is more convincing than one that has only seen good ones."
    )
    return s


def main():
    prs = Presentation("original.pptx")
    before = len(prs.slides.__iter__.__self__._sldIdLst)

    slide_built(prs)
    slide_safety(prs)
    slide_ops(prs)

    # Move the three new slides to sit before "Why Us" (slide 7) and References (8).
    sldIdLst = prs.slides._sldIdLst
    ids = list(sldIdLst)
    new_ids = ids[-3:]
    for n in new_ids:
        sldIdLst.remove(n)
    # insert after index 5 (slides 1-6 stay put)
    for offset, n in enumerate(new_ids):
        sldIdLst.insert(6 + offset, n)

    prs.save("InstantZero-updated.pptx")
    print("saved InstantZero-updated.pptx with %d slides" % len(sldIdLst))


if __name__ == "__main__":
    main()
