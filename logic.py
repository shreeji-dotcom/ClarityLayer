"""Rule-based processing for ClarityLayer (no external AI APIs)."""

from __future__ import annotations

import re
from collections import OrderedDict
from dataclasses import dataclass
from typing import Dict, List

from lingo_data import flattened_lingo, phrase_category_lookup

FILLER_PHRASES = [
    "just wanted to",
    "circle back",
    "touch base",
    "please advise",
    "for visibility",
    "kindly note",
    "as discussed",
    "moving forward",
    "at your earliest convenience",
    "per my last email",
    "friendly reminder",
    "quick note",
    "hope this finds you well",
    "reaching out to",
    "wanted to follow up",
]

ACTION_PATTERN = re.compile(
    r"\b(please|kindly)?\s*(review|send|share|confirm|complete|provide|update|approve|finalize|deliver|submit|prepare|draft|align|escalate)\b"
    r"|\bneed to\b|\bmust\b|\baction item\b|\bowner\s*:\s*\w+\b",
    re.IGNORECASE,
)
DEADLINE_PATTERN = re.compile(
    r"\bby\s+(eod|end of day|eow|cob|tomorrow|today|monday|tuesday|wednesday|thursday|friday|saturday|sunday|mon|tue|tues|wed|thu|thur|thurs|fri|sat|sun)\b"
    r"|\bnext\s+(monday|tuesday|wednesday|thursday|friday|saturday|sunday|mon|tue|tues|wed|thu|thur|thurs|fri|sat|sun)\b"
    r"|\bdue\s+(?:on|by)?\s*[a-z0-9\-/, ]+"
    r"|\b\d{1,2}/\d{1,2}(?:/\d{2,4})?\b"
    r"|\b(?:jan|feb|mar|apr|may|jun|jul|aug|sep|sept|oct|nov|dec)[a-z]*\s+\d{1,2}\b"
    r"|\bq[1-4]\b",
    re.IGNORECASE,
)
FOLLOW_UP_PATTERN = re.compile(r"\bfollow up\b|\bcircle back\b|\bcheck in\b|\breconnect\b|\bnext steps\b", re.IGNORECASE)
PRIORITY_PATTERN = re.compile(r"\burgent\b|\basap\b|\bcritical\b|\bhigh priority\b|\bimmediately\b|\bblocker\b|\btime-sensitive\b", re.IGNORECASE)
OWNER_PATTERN = re.compile(r"\b(?:owner|assignee)\s*:\s*([A-Za-z][A-Za-z\- ]+)\b", re.IGNORECASE)

WORKPLAN_KEYWORDS: Dict[str, List[str]] = {
    "Data / Dashboard / Analytics": ["data", "dashboard", "analytics", "kpi", "report", "insight", "metric"],
    "Finance / Budget / ROI": ["finance", "budget", "roi", "cost", "margin", "forecast", "savings"],
    "Marketing / Customer / Campaign": ["marketing", "customer", "campaign", "lead", "retention", "acquisition", "brand"],
    "Technology / System / Database / API": ["technology", "system", "database", "api", "integration", "platform", "pipeline"],
}


@dataclass
class LingoMatch:
    phrase: str
    translation: str
    category: str
    match_type: str


def normalize_text(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def _normalize_for_phrase_match(text: str) -> str:
    return re.sub(r"[^a-z0-9 ]+", " ", text.lower()).strip()


def _token_similarity(a: str, b: str) -> float:
    a_tokens = set(re.findall(r"\w+", a.lower()))
    b_tokens = set(re.findall(r"\w+", b.lower()))
    if not a_tokens or not b_tokens:
        return 0.0
    return len(a_tokens & b_tokens) / len(a_tokens | b_tokens)


def translate_lingo(user_phrase: str, custom_terms: Dict[str, str] | None = None) -> Dict[str, object]:
    phrase = normalize_text(user_phrase).lower()
    lingo = flattened_lingo()
    categories = phrase_category_lookup()

    if custom_terms:
        for term, meaning in custom_terms.items():
            term_norm = normalize_text(term).lower()
            if term_norm:
                lingo[term_norm] = meaning.strip()
                categories[term_norm] = "Custom"

    if not phrase:
        return {"input": user_phrase, "matches": [], "found": False}

    matches: List[LingoMatch] = []

    if phrase in lingo:
        matches.append(LingoMatch(phrase, lingo[phrase], categories.get(phrase, "Uncategorized"), "exact"))
    else:
        phrase_clean = _normalize_for_phrase_match(phrase)
        for known, translation in lingo.items():
            known_clean = _normalize_for_phrase_match(known)

            # Guard against false positives from very short acronyms (e.g., "ui" in "fruit").
            short_token = len(known_clean.replace(" ", "")) <= 3
            if short_token:
                continue

            if phrase_clean and (phrase_clean in known_clean or known_clean in phrase_clean):
                matches.append(LingoMatch(known, translation, categories.get(known, "Uncategorized"), "contains"))

    if not matches:
        scored: List[tuple[float, str, str]] = []
        for known, translation in lingo.items():
            score = _token_similarity(phrase, known)
            if score >= 0.25:
                scored.append((score, known, translation))
        scored.sort(key=lambda x: x[0], reverse=True)
        for score, known, translation in scored[:6]:
            matches.append(LingoMatch(known, translation, categories.get(known, "Uncategorized"), f"similar:{score:.2f}"))

    deduped = list(OrderedDict((m.phrase, m) for m in matches).values())
    return {"input": user_phrase, "found": len(deduped) > 0, "matches": [m.__dict__ for m in deduped]}


def detect_lingo_terms(text: str) -> List[str]:
    normalized = text.lower()
    found: List[str] = []
    for phrase in flattened_lingo().keys():
        if re.search(rf"\b{re.escape(phrase)}\b", normalized):
            found.append(phrase)
    return sorted(set(found))


def simplify_email(email_text: str, audience_mode: str = "For Team") -> Dict[str, object]:
    original = email_text.strip()

    # Keep wording intact to avoid choppy output; only normalize spacing.
    clean = re.sub(r"\s+", " ", original).strip()

    sentences = _split_sentences(original)
    action_items = _filter_sentences(sentences, ACTION_PATTERN)
    deadlines = _filter_sentences(sentences, DEADLINE_PATTERN)
    follow_ups = _filter_sentences(sentences, FOLLOW_UP_PATTERN)
    priority = _filter_sentences(sentences, PRIORITY_PATTERN)
    lingo_terms = detect_lingo_terms(original)
    owners = _extract_owners(original)

    action_registry = []
    for item in action_items:
        action_registry.append(
            {
                "action": item,
                "owner": _owner_for_sentence(item, owners),
                "deadline": _extract_deadline(item),
                "priority": "High" if PRIORITY_PATTERN.search(item) else "Normal",
            }
        )

    summary = _build_email_summary(sentences, action_items, deadlines, priority, follow_ups, audience_mode)
    action_plan = _build_action_plan(action_registry)
    clarification_questions = _build_clarification_questions(action_registry, deadlines, owners, priority)
    missing_info_flags = _email_missing_flags(action_registry, deadlines, owners, priority)

    explain_logic = []
    for item in action_items:
        explain_logic.append(f"Action verb found because sentence matched action pattern: '{item}'")
    for item in deadlines:
        explain_logic.append(f"Deadline detected because sentence includes timing language: '{item}'")
    for item in priority:
        explain_logic.append(f"Priority signal found because urgency term appeared: '{item}'")
    if not owners:
        explain_logic.append("Missing owner flag added because no explicit 'owner:' or 'assignee:' tag was detected.")

    objective_tags: List[str] = []
    if action_items:
        objective_tags.append("Action verb found")
    if deadlines:
        objective_tags.append("Deadline detected")
    if not owners:
        objective_tags.append("Missing owner")
    if priority:
        objective_tags.append("Priority signal found")

    return {
        "clean_email": clean,
        "email_summary": summary,
        "action_plan": action_plan,
        "clarification_questions": clarification_questions,
        "missing_info_flags": missing_info_flags,
        "action_items": action_items,
        "deadlines": deadlines,
        "follow_ups": follow_ups,
        "priority_signals": priority,
        "corporate_terms": lingo_terms,
        "owners": owners,
        "filler_removed": [],
        "explain_logic": explain_logic,
        "objective_tags": objective_tags,
        "action_registry": action_registry,
        "metrics": {
            "word_count": len(re.findall(r"\b\w+\b", original)),
            "sentence_count": len(sentences),
            "action_item_count": len(action_items),
            "deadline_count": len(deadlines),
            "follow_up_count": len(follow_ups),
            "priority_signal_count": len(priority),
            "corporate_term_count": len(lingo_terms),
            "owner_count": len(owners),
            "filler_removed_count": 0,
            "compression_percent": 0,
        },
    }


def _build_email_summary(
    sentences: List[str], action_items: List[str], deadlines: List[str], priority: List[str], follow_ups: List[str], audience_mode: str
) -> str:
    opening = sentences[0] if sentences else "No content provided."
    summary_parts = [opening]

    if action_items:
        summary_parts.append(f"Key ask: {action_items[0]}")
    if deadlines:
        summary_parts.append(f"Timing noted: {deadlines[0]}")
    if priority:
        summary_parts.append("Urgency is signaled in the message.")
    if follow_ups:
        summary_parts.append("Follow-up is expected.")

    base = " ".join(summary_parts)
    return _apply_audience_mode(base, audience_mode)


def _apply_audience_mode(text: str, audience_mode: str) -> str:
    if audience_mode == "For Leadership":
        return (
            "Executive Summary:\n"
            "- KPI focus: delivery speed, risk exposure, value realization\n"
            "- Decision needed: confirm owner, due date, and escalation path\n"
            "- Confidence: medium unless missing-info flags are resolved\n"
            f"- Next update: include progress against agreed KPI ({text})"
        )
    if audience_mode == "For Client":
        return (
            "Client Update:\n"
            f"- Summary: {text}\n"
            "- Assumptions: based on provided inputs and stated timelines\n"
            "- Actions: clear ownership and milestone tracking required\n"
            "- Risks: unresolved dependencies may impact delivery dates"
        )
    return f"Team execution view: {text}"


def _build_action_plan(action_registry: List[dict]) -> List[dict]:
    plan = []
    for idx, action in enumerate(action_registry, start=1):
        plan.append(
            {
                "step": idx,
                "what_to_do": action["action"],
                "owner": action["owner"],
                "due": action["deadline"],
                "priority": action["priority"],
            }
        )
    return plan


def _email_missing_flags(
    action_registry: List[dict], deadlines: List[str], owners: List[str], priority: List[str]
) -> List[str]:
    flags: List[str] = []
    if not owners:
        flags.append("Missing owner")
    if any(item["deadline"] == "Not specified" for item in action_registry) and not deadlines:
        flags.append("Missing due date")
    if not priority:
        flags.append("Missing priority level")
    if not action_registry:
        flags.append("Missing explicit action request")
    return flags


def _build_clarification_questions(
    action_registry: List[dict], deadlines: List[str], owners: List[str], priority: List[str]
) -> List[str]:
    questions: List[str] = []

    if not action_registry:
        questions.append("What exact action or decision is required from recipients?")
    if any(item["deadline"] == "Not specified" for item in action_registry) and not deadlines:
        questions.append("What is the exact due date/time for each action item?")
    if not owners:
        questions.append("Who is the owner for each action item?")
    if not priority:
        questions.append("What is the priority level and escalation path if delayed?")

    if not questions:
        questions.append("Are there any dependencies or approvals needed before execution?")

    return questions


def _compression_percent(before_text: str, after_text: str) -> int:
    before_words = max(1, len(re.findall(r"\b\w+\b", before_text)))
    after_words = len(re.findall(r"\b\w+\b", after_text))
    saved = max(0, before_words - after_words)
    return round((saved / before_words) * 100)


def _owner_for_sentence(sentence: str, owners: List[str]) -> str:
    for owner in owners:
        if owner.lower() in sentence.lower():
            return owner
    return owners[0] if owners else "Unspecified"


def _extract_deadline(sentence: str) -> str:
    match = DEADLINE_PATTERN.search(sentence)
    return match.group(0) if match else "Not specified"


def _extract_owners(text: str) -> List[str]:
    owners = [normalize_text(match.group(1)) for match in OWNER_PATTERN.finditer(text)]
    return list(OrderedDict((o, True) for o in owners).keys())


def _split_sentences(text: str) -> List[str]:
    chunks = re.split(r"[\n.!?]+", text)
    return [normalize_text(c) for c in chunks if normalize_text(c)]


def _filter_sentences(sentences: List[str], pattern: re.Pattern[str]) -> List[str]:
    return list(OrderedDict((s, True) for s in sentences if pattern.search(s)).keys())


def generate_workplan(project_description: str, audience_mode: str = "For Team") -> Dict[str, object]:
    normalized = project_description.lower()
    matched_categories: List[str] = []
    category_hits: Dict[str, int] = {}

    for category, keywords in WORKPLAN_KEYWORDS.items():
        hits = sum(1 for k in keywords if k in normalized)
        if hits > 0:
            matched_categories.append(category)
            category_hits[category] = hits

    if not matched_categories:
        matched_categories = ["General Business"]
        category_hits = {"General Business": 1}

    missing_flags = _project_missing_flags(project_description, matched_categories)
    dependency_map = _dependency_map(matched_categories)
    risks_watchouts = [
        "Ambiguous ownership can stall key decisions.",
        "Data inconsistency can undermine recommendation quality.",
        "Scope growth can delay launch timelines.",
        "Unclear success criteria can cause rework.",
    ]

    first_steps = [
        "Write one clear objective and target date.",
        "Confirm decision maker and working team.",
        "Collect current-state data and known blockers.",
        "Define one success metric everyone agrees on.",
        "Set first checkpoint meeting and action owners.",
    ]
    if "Technology / System / Database / API" in matched_categories:
        first_steps[2] = "Review system dependencies and access requirements."
    if "Finance / Budget / ROI" in matched_categories:
        first_steps[3] = "Define budget target and expected ROI metric."

    who_to_talk_to = [
        {"role": "Data / Technical owner", "recommended_contact": "Analytics or Engineering Lead"},
        {"role": "Business stakeholder", "recommended_contact": "Business Process Owner"},
        {"role": "Decision maker", "recommended_contact": "Department Head or Sponsor"},
        {"role": "Execution support", "recommended_contact": "Program/Project Manager"},
    ]

    project_start_summary = {
        "objective": (project_description.strip().split(".")[0] or "Define clear project objective.").strip(),
        "where_to_start": first_steps[0],
        "main_dependency": dependency_map[0]["dependency"] if dependency_map else "Stakeholder availability",
        "main_risk": risks_watchouts[0],
    }

    return {
        "matched_categories": matched_categories,
        "category_hits": category_hits,
        "project_start_summary": project_start_summary,
        "who_to_talk_to": who_to_talk_to,
        "first_5_steps": first_steps[:5],
        "watchouts": risks_watchouts[:4],
        "missing_info_flags": missing_flags,
        "dependency_map": dependency_map,
        "audience_note": _apply_audience_mode("Project starting assistant generated.", audience_mode),
    }


def _build_phase_plan(categories: List[str]) -> List[dict]:
    rows = [
        {"phase": "Phase 1", "workstream": "Clarify & Scope", "activity": "Kickoff, objectives, constraints", "output": "Signed project charter", "timing": "Week 1"},
        {"phase": "Phase 2", "workstream": "Gather & Validate", "activity": "Data/process collection and validation", "output": "Validated baseline", "timing": "Weeks 2-3"},
        {"phase": "Phase 3", "workstream": "Analyze & Recommend", "activity": "Synthesis, options, recommendation", "output": "Executive recommendation deck", "timing": "Weeks 4-5"},
    ]
    if "Technology / System / Database / API" in categories:
        rows.append({"phase": "Phase 2", "workstream": "Tech Assessment", "activity": "Integration and architecture review", "output": "Dependency register", "timing": "Week 3"})
    if "Finance / Budget / ROI" in categories:
        rows.append({"phase": "Phase 3", "workstream": "Business Case", "activity": "ROI and sensitivity modeling", "output": "Financial model", "timing": "Week 5"})
    return rows


def _workstreams(categories: List[str]) -> List[dict]:
    base = [
        {"workstream": "Program Management", "objective": "Drive delivery governance", "owner_role": "Program Lead", "phase": "1-3"},
        {"workstream": "Stakeholder Alignment", "objective": "Secure decisions and sign-offs", "owner_role": "Business Lead", "phase": "1-2"},
    ]
    if "Data / Dashboard / Analytics" in categories:
        base.append({"workstream": "Data Intelligence", "objective": "Standardize metrics and reporting", "owner_role": "Analytics Lead", "phase": "2-3"})
    if "Finance / Budget / ROI" in categories:
        base.append({"workstream": "Value Realization", "objective": "Quantify ROI and savings", "owner_role": "Finance Partner", "phase": "2-3"})
    if "Marketing / Customer / Campaign" in categories:
        base.append({"workstream": "Customer Performance", "objective": "Improve campaign efficiency", "owner_role": "Marketing Manager", "phase": "2-3"})
    if "Technology / System / Database / API" in categories:
        base.append({"workstream": "Technology Enablement", "objective": "Stabilize integrations and platforms", "owner_role": "Engineering Lead", "phase": "2-3"})
    return base


def _success_metrics(categories: List[str]) -> List[str]:
    metrics = ["Decision cycle time", "Milestone on-time rate"]
    if "Data / Dashboard / Analytics" in categories:
        metrics.append("KPI adoption rate")
    if "Finance / Budget / ROI" in categories:
        metrics.append("ROI uplift vs baseline")
    if "Marketing / Customer / Campaign" in categories:
        metrics.append("Conversion and retention improvement")
    if "Technology / System / Database / API" in categories:
        metrics.append("Integration failure rate reduction")
    return metrics


def _dependency_map(categories: List[str]) -> List[dict]:
    deps = [
        {"dependency": "Stakeholder availability", "impact_if_blocked": "Delays validation and approvals", "mitigation": "Weekly decision forums"},
        {"dependency": "Data/source access", "impact_if_blocked": "Limits analysis confidence", "mitigation": "Early access requests and owner assignment"},
    ]
    if "Technology / System / Database / API" in categories:
        deps.append({"dependency": "Integration environments", "impact_if_blocked": "Prevents technical validation", "mitigation": "Provision sandbox early"})
    return deps


def _project_missing_flags(project_description: str, categories: List[str]) -> List[str]:
    text = project_description.lower()
    flags: List[str] = []
    if "owner" not in text and "stakeholder" not in text:
        flags.append("Missing decision owner")
    if "by" not in text and "due" not in text and "week" not in text and "month" not in text:
        flags.append("Missing due date/timeline")
    if "kpi" not in text and "metric" not in text and "success" not in text:
        flags.append("Missing success metric")
    if "dependency" not in text and "depends on" not in text and "blocker" not in text:
        flags.append("Missing dependency")
    return flags


def _recommended_deliverables(categories: List[str]) -> List[str]:
    base = [
        "Project charter (objective, scope, timeline, owners)",
        "Stakeholder map with RACI",
        "Workstream plan with milestones",
        "Executive readout deck",
    ]

    by_category = {
        "Data / Dashboard / Analytics": ["KPI dictionary", "Dashboard wireframe and metric logic"],
        "Finance / Budget / ROI": ["Cost model", "ROI scenario analysis"],
        "Marketing / Customer / Campaign": ["Customer segment framework", "Campaign measurement plan"],
        "Technology / System / Database / API": ["System architecture snapshot", "Integration dependency register"],
        "General Business": ["Current-state process map", "Prioritized initiative backlog"],
    }

    for c in categories:
        base.extend(by_category.get(c, []))

    return list(OrderedDict((item, True) for item in base).keys())


def _key_questions(categories: List[str]) -> List[str]:
    base = [
        "What specific outcome must improve, and by what date?",
        "Who approves scope, budget, and final recommendations?",
        "What constraints are fixed (budget, timeline, compliance, tooling)?",
    ]

    by_category = {
        "Data / Dashboard / Analytics": [
            "Which metrics are mandatory for decisions versus informational only?",
            "What data quality gaps must be resolved first?",
        ],
        "Finance / Budget / ROI": [
            "Which baseline costs and benefits define the business case?",
            "Which assumptions create the largest ROI sensitivity?",
        ],
        "Marketing / Customer / Campaign": [
            "Which customer segments are highest-value targets?",
            "How will attribution and campaign success be measured?",
        ],
        "Technology / System / Database / API": [
            "Which systems are source-of-truth and where are integration risks?",
            "What performance, security, or reliability constraints apply?",
        ],
    }

    for c in categories:
        base.extend(by_category.get(c, []))

    return list(OrderedDict((q, True) for q in base).keys())
