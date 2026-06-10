"""Pure risk-scoring logic: controlled vocabularies, matrices, deterministic
scoring, output validation, and prompt construction.

No I/O, no framework, no Azure — just functions over strings. This is the
auditable core (mirrors the role of ``domain/heuristics.py``). The LLM produces
only qualitative judgments; everything derived is computed here so the scoring
is repeatable and tunable against your risk appetite without re-prompting.
"""

from __future__ import annotations

from typing import Any, Dict, List

# --------------------------------------------------------------------------- #
# Controlled vocabularies                                                      #
# --------------------------------------------------------------------------- #
LIKELIHOOD = ["Rare", "Unlikely", "Possible", "Likely", "Almost Certain"]
CONSEQUENCE = ["Insignificant", "Minor", "Moderate", "Major", "Severe"]
VELOCITY = ["Very Slow", "Slow", "Moderate", "Fast", "Immediate"]
EFFECTIVENESS = ["Effective", "Partially Effective", "Ineffective", "Uncontrolled"]
RISK_LEVELS = ["Low", "Medium", "High", "Extreme"]
RESPONSES = ["Accept", "Mitigate", "Transfer", "Avoid"]
RISK_TYPES = [
    "Strategic", "Operational", "Financial", "Compliance", "Regulatory",
    "Reputational", "Information Security", "Cyber Security", "Legal",
    "Third Party", "Business Continuity", "Other",
]

# --------------------------------------------------------------------------- #
# Scoring matrices (tune these to your appetite — they are the policy)         #
# --------------------------------------------------------------------------- #
# Inherent risk = INHERENT_MATRIX[consequence][likelihood index]
INHERENT_MATRIX: Dict[str, List[str]] = {
    "Insignificant": ["Low",    "Low",    "Low",    "Medium",  "Medium"],
    "Minor":         ["Low",    "Low",    "Medium", "Medium",  "High"],
    "Moderate":      ["Low",    "Medium", "Medium", "High",    "High"],
    "Major":         ["Medium", "Medium", "High",   "High",    "Extreme"],
    "Severe":        ["Medium", "High",   "High",   "Extreme", "Extreme"],
}

# Velocity policy: Immediate velocity escalates an already-High risk one band.
APPLY_VELOCITY_ESCALATION = True
VELOCITY_ESCALATES = {"Immediate"}
VELOCITY_ESCALATE_FROM = {"High"}

# Residual risk = RESIDUAL_MATRIX[inherent][overall effectiveness]
RESIDUAL_MATRIX: Dict[str, Dict[str, str]] = {
    "Low":     {"Effective": "Low",    "Partially Effective": "Low",    "Ineffective": "Low",     "Uncontrolled": "Medium"},
    "Medium":  {"Effective": "Low",    "Partially Effective": "Medium", "Ineffective": "Medium",  "Uncontrolled": "High"},
    "High":    {"Effective": "Medium", "Partially Effective": "High",   "Ineffective": "High",    "Uncontrolled": "Extreme"},
    "Extreme": {"Effective": "High",   "Partially Effective": "High",   "Ineffective": "Extreme", "Uncontrolled": "Extreme"},
}

EFFECTIVENESS_SCORE = {"Effective": 3, "Partially Effective": 2, "Ineffective": 1, "Uncontrolled": 0}


# --------------------------------------------------------------------------- #
# Deterministic scoring                                                        #
# --------------------------------------------------------------------------- #
def compute_inherent_risk(likelihood: str, consequence: str, velocity: str) -> str:
    level = INHERENT_MATRIX[consequence][LIKELIHOOD.index(likelihood)]
    if (APPLY_VELOCITY_ESCALATION
            and velocity in VELOCITY_ESCALATES
            and level in VELOCITY_ESCALATE_FROM):
        level = RISK_LEVELS[min(RISK_LEVELS.index(level) + 1, len(RISK_LEVELS) - 1)]
    return level


def compute_overall_effectiveness(control_effs: List[str]) -> str:
    """Aggregate per-control ratings (rounded mean). Switch to weakest-link by
    returning the worst rating if you want a more conservative posture."""
    if not control_effs:
        return "Uncontrolled"
    avg = sum(EFFECTIVENESS_SCORE[e] for e in control_effs) / len(control_effs)
    if avg >= 2.5:
        return "Effective"
    if avg >= 1.5:
        return "Partially Effective"
    if avg >= 0.5:
        return "Ineffective"
    return "Uncontrolled"


def compute_residual_risk(inherent_risk: str, overall_effectiveness: str) -> str:
    return RESIDUAL_MATRIX[inherent_risk][overall_effectiveness]


def recommend_response(residual_risk: str, risk_type: str) -> str:
    insurable = risk_type in {"Financial", "Third Party", "Business Continuity"}
    if residual_risk == "Low":
        return "Accept"
    if residual_risk in ("Medium", "High"):
        return "Transfer" if insurable else "Mitigate"
    return "Mitigate"  # Extreme -> always treat; owner decides Avoid vs Mitigate


# --------------------------------------------------------------------------- #
# LLM output validation                                                        #
# --------------------------------------------------------------------------- #
def _validate(value: Any, allowed: List[str], field: str) -> str:
    s = str(value).strip().lower()
    for a in allowed:
        if s == a.lower():
            return a
    raise ValueError(f"{field}={value!r} not in {allowed}")


def normalize_llm_output(data: Dict[str, Any]) -> Dict[str, Any]:
    """Validate the model's qualitative judgment and return a clean dict.
    Raises ValueError on any out-of-vocabulary value."""
    controls = []
    for c in data.get("controls", []) or []:
        controls.append({
            "control": str(c.get("control", "")).strip(),
            "effectiveness": _validate(c.get("effectiveness"), EFFECTIVENESS, "effectiveness"),
            "explanation": str(c.get("explanation", "")).strip(),
        })
    return {
        "primary_risk": str(data.get("primary_risk", "")).strip(),
        "risk_domain": str(data.get("risk_domain", "")).strip(),
        "risk_type": _validate(data.get("risk_type"), RISK_TYPES, "risk_type"),
        "likelihood": _validate(data.get("likelihood"), LIKELIHOOD, "likelihood"),
        "consequence": _validate(data.get("consequence"), CONSEQUENCE, "consequence"),
        "velocity": _validate(data.get("velocity"), VELOCITY, "velocity"),
        "controls": controls,
    }


def score_from_judgment(judgment: Dict[str, Any]) -> Dict[str, Any]:
    """Take a normalized LLM judgment and add the four derived fields."""
    inherent = compute_inherent_risk(
        judgment["likelihood"], judgment["consequence"], judgment["velocity"])
    overall = compute_overall_effectiveness([c["effectiveness"] for c in judgment["controls"]])
    residual = compute_residual_risk(inherent, overall)
    return {
        **judgment,
        "inherent_risk": inherent,
        "overall_control_effectiveness": overall,
        "residual_risk": residual,
        "risk_response": recommend_response(residual, judgment["risk_type"]),
    }


# --------------------------------------------------------------------------- #
# Prompts (system/user split, for chat_json_object)                            #
# --------------------------------------------------------------------------- #
SYSTEM_PROMPT = (
    "You are a senior ISO 31000 / ISO 27001 enterprise risk assessor. "
    "Assess the issue against the listed controls and return a single JSON object. "
    "Use ONLY these allowed values: "
    f"likelihood {LIKELIHOOD}; consequence {CONSEQUENCE}; velocity {VELOCITY}; "
    f"risk_type {RISK_TYPES}; control effectiveness {EFFECTIVENESS}. "
    "Keys: primary_risk (string), risk_domain (string), risk_type, likelihood, "
    "consequence, velocity, and controls (array of objects with keys control, "
    "effectiveness, explanation — assess EVERY control). "
    "Do NOT compute inherent, residual, or response; those are derived downstream."
)


def build_user_prompt(issue_text: str, controls: List[str]) -> str:
    block = "\n".join(f"- {c}" for c in controls) if controls else "- (none provided)"
    return f"ISSUE:\n{issue_text}\n\nEXISTING CONTROLS:\n{block}\n\nRespond with JSON only."
