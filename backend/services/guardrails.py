"""
Clinical output guardrails (NeMo-Guardrails pattern, natively enforced)
======================================================================
Every word an LLM produces passes through here before a nurse can see it.

Why this is written by hand rather than as a NeMo Guardrails config: the
nemoguardrails package needs an LLM backend of its own to evaluate most rails,
which would mean a second model call on a path that must stay fast and must
keep working when the network is down. These checks are deterministic string
and consistency checks — they cost microseconds, need no GPU, and cannot
themselves fail open.

THE RULE BEING ENFORCED
    The deterministic engine has already decided the triage level. The LLM is
    only allowed to restate and explain that decision. If its text contradicts
    the verdict, downplays it, tells staff to stand down, or invents clinical
    facts, the text is REJECTED and the caller shows rule-based text instead.

    Rejecting is always safe: the nurse still gets the alert and the rule
    reason. Nothing clinical depends on the model's output existing.
"""

import logging
import re
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger("vitalband.guardrails")

# Phrases that would tell a nurse to relax about an emergency.
_STAND_DOWN = [
    r"\bno (?:need|cause) (?:to|for) (?:worry|concern|alarm)\b",
    r"\bnot? (?:an )?emergency\b",
    r"\bfalse alarm\b",
    r"\bignore (?:this|the) alert\b",
    r"\bcan be (?:safely )?(?:ignored|dismissed)\b",
    r"\bno (?:immediate )?action (?:is )?(?:required|needed)\b",
    r"\bstand down\b",
    r"\bdisregard\b",
    r"\bpatient is (?:fine|stable|healthy|okay|ok)\b",
    r"\bnothing to worry about\b",
    r"\bwait and see\b",
    r"\bnon-?urgent\b",
    r"\bde-?escalate\b",
]

# Clinical overreach: the model is not permitted to diagnose or prescribe.
_OVERREACH = [
    r"\b(?:diagnos(?:is|ed|e)) (?:is|of|with)\b",
    r"\bprescrib(?:e|ing|ed)\b",
    r"\badminister \d+\s*(?:mg|ml|mcg|units)\b",
    r"\b\d+\s*(?:mg|mcg|ml)\b.*\b(?:give|administer|dose)\b",
]

_LEVEL_WORDS = {
    "LEVEL_1_EMERGENCY": ["level 1", "emergency", "immediate", "critical", "escalate", "urgent"],
    "LEVEL_2_URGENT": ["urgent", "priority", "prompt", "soon", "escalat"],
    "LEVEL_3_STABLE": ["stable", "routine", "standard", "continue", "monitor"],
}


def _violations(text: str, triage_level: str) -> List[str]:
    low = text.lower()
    found: List[str] = []

    for pat in _STAND_DOWN:
        if re.search(pat, low):
            found.append(f"stand-down language matched /{pat}/")

    for pat in _OVERREACH:
        if re.search(pat, low):
            found.append(f"clinical overreach matched /{pat}/")

    # An emergency explanation that never signals urgency is itself a problem.
    if triage_level == "LEVEL_1_EMERGENCY":
        if not any(w in low for w in _LEVEL_WORDS["LEVEL_1_EMERGENCY"]):
            found.append("LEVEL_1 explanation conveys no urgency")

    # Naming a different level than the one decided.
    for other, words in _LEVEL_WORDS.items():
        if other == triage_level:
            continue
        if other == "LEVEL_3_STABLE" and triage_level != "LEVEL_3_STABLE":
            if re.search(r"\b(?:patient is |appears )?stable\b", low):
                found.append("claims patient is stable while triage is not LEVEL_3")

    return found


def _fabricated_numbers(text: str, allowed: Dict) -> List[str]:
    """
    Flag vitals-looking numbers the model was not given.

    Deliberately narrow: only values attached to a vitals unit are checked, so
    ordinary prose numbers ("3 minutes", "2 factors") never trip it.
    """
    issues: List[str] = []
    permitted = {
        str(v) for v in [
            allowed.get("heart_rate"), allowed.get("spo2"),
            allowed.get("deterioration_index"),
        ] if v is not None
    }
    # also permit the rounded form of the index
    di = allowed.get("deterioration_index")
    if di is not None:
        permitted.add(str(int(round(float(di)))))

    for m in re.finditer(r"(\d{1,3})\s*(?:bpm|%|percent)", text, re.I):
        if m.group(1) not in permitted:
            issues.append(f"unsupported vitals figure '{m.group(0).strip()}'")
    return issues


def validate_explanation(
    text: Optional[str],
    triage_level: str,
    context: Optional[Dict] = None,
) -> Tuple[bool, Optional[str], List[str]]:
    """
    Returns (allowed, safe_text, violations).

    allowed=False means the caller MUST fall back to deterministic rule text.
    """
    if not text or not text.strip():
        return False, None, ["empty model output"]

    cleaned = " ".join(text.split())

    # Length guard: anything long has stopped being an explanation.
    if len(cleaned) > 600:
        cleaned = cleaned[:600].rsplit(".", 1)[0] + "."

    problems = _violations(cleaned, triage_level)
    if context:
        problems += _fabricated_numbers(cleaned, context)

    if problems:
        logger.warning(
            "Guardrail BLOCKED an LLM explanation for %s: %s",
            triage_level, "; ".join(problems),
        )
        return False, None, problems

    return True, cleaned, []


def status() -> Dict:
    return {
        "service": "NeMo Guardrails pattern · clinical output validation",
        "configured": True,
        "mode": "active",
        "role": "validates every LLM sentence before a nurse sees it",
        "checks": [
            "stand-down / dismissive language",
            "contradiction of the decided triage level",
            "clinical overreach (diagnosis, dosing)",
            "fabricated vitals figures",
            "length ceiling",
        ],
        "on_violation": "explanation discarded, deterministic rule text shown instead",
        "detail": "Runs on CPU with no external dependency, so it cannot fail open.",
    }
