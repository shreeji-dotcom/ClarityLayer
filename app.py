"""ClarityLayer Streamlit app: no-AI workplace clarity tool."""

from __future__ import annotations

import json
from io import BytesIO, StringIO

import pandas as pd
import streamlit as st

import database as db
from lingo_data import LINGO_CATEGORIES
from logic import generate_workplan, simplify_email, translate_lingo

# Compatibility bridge for mixed local file versions.
initialize_database = getattr(db, "initialize_database")
rows_to_dicts = getattr(db, "rows_to_dicts")
to_csv = getattr(db, "to_csv")

upsert_lingo_history = getattr(db, "upsert_lingo_history", getattr(db, "insert_lingo_history"))
add_email_history = getattr(db, "add_email_history", getattr(db, "insert_email_history"))
add_project_history = getattr(db, "add_project_history", getattr(db, "insert_project_history"))

get_lingo_history = getattr(db, "get_lingo_history", getattr(db, "fetch_lingo_history"))
get_email_history = getattr(db, "get_email_history", getattr(db, "fetch_email_history"))
get_project_history = getattr(db, "get_project_history", getattr(db, "fetch_project_history"))
get_custom_lingo_map = getattr(db, "get_custom_lingo_map", lambda: {})
get_custom_lingo_rows = getattr(db, "get_custom_lingo_rows", lambda: [])
add_custom_lingo = getattr(db, "add_custom_lingo", None)
delete_custom_lingo = getattr(db, "delete_custom_lingo", None)
get_custom_lingo_csv = getattr(db, "get_custom_lingo_csv", lambda: "")
get_custom_lingo_json = getattr(db, "get_custom_lingo_json", lambda: "[]")

add_workflow_run = getattr(db, "add_workflow_run", None)
update_workflow_review = getattr(db, "update_workflow_review", None)
get_workflow_runs = getattr(db, "get_workflow_runs", lambda limit=200: [])
add_execution_board_rows = getattr(db, "add_execution_board_rows", None)
get_execution_board_rows = getattr(db, "get_execution_board_rows", lambda run_id: [])
add_playbook = getattr(db, "add_playbook", None)
get_playbooks = getattr(db, "get_playbooks", lambda tool_type: [])
delete_playbook = getattr(db, "delete_playbook", None)
add_run_feedback = getattr(db, "add_run_feedback", None)
get_run_feedback = getattr(db, "get_run_feedback", lambda run_id: [])
add_communication_log = getattr(db, "add_communication_log", None)
get_communication_log = getattr(db, "get_communication_log", lambda run_id, tool_type: [])

delete_by_id = getattr(db, "delete_by_id", getattr(db, "delete_history_row"))
clear_table = getattr(db, "clear_table", getattr(db, "clear_history_table"))


def run_translate_lingo(user_phrase: str) -> dict:
    custom_map = get_custom_lingo_map()
    try:
        return translate_lingo(user_phrase, custom_terms=custom_map)
    except TypeError:
        # Compatibility for older logic.py versions without custom_terms argument.
        return translate_lingo(user_phrase)


def save_email_history(input_text: str, clean_text: str, action_count: int, deadline_count: int, priority_count: int) -> None:
    try:
        add_email_history(
            input_text,
            clean_text,
            action_count=action_count,
            deadline_count=deadline_count,
            priority_count=priority_count,
        )
    except TypeError:
        add_email_history(input_text, clean_text)


def save_project_history(input_text: str, summary_text: str, categories_text: str) -> None:
    try:
        add_project_history(input_text, summary_text, categories_text=categories_text)
    except TypeError:
        add_project_history(input_text, summary_text)

st.set_page_config(page_title="ClarityLayer", page_icon="🧭", layout="wide")

CARD_CSS = """
<style>
.stApp { background: linear-gradient(180deg, #F8FAFC 0%, #EEF4FF 100%); }
.block-card { border: 1px solid #DDE5F2; border-radius: 14px; padding: 16px; margin-bottom: 14px; background: #FFFFFF; box-shadow: 0 2px 8px rgba(15, 23, 42, 0.05); }
.small-muted { color: #64748B; font-size: 0.92rem; }
.badge { display: inline-block; padding: 5px 10px; margin-right: 8px; margin-bottom: 6px; border-radius: 999px; background: #EAF2FF; color: #1D4ED8; font-size: 0.80rem; border: 1px solid #C7DAFF; }
.hero { background: radial-gradient(120% 120% at 0% 0%, #1E3A8A 0%, #2563EB 45%, #3B82F6 100%); color: white; padding: 18px 20px; border-radius: 16px; margin-bottom: 14px; }
.hero h2 { margin: 0 0 6px 0; font-size: 1.35rem; }
.hero p { margin: 0; opacity: 0.95; }
.subpanel { border-left: 4px solid #3B82F6; background: #F8FBFF; border-radius: 10px; padding: 10px 12px; margin-bottom: 8px; }
[data-testid="stMetricValue"] { color: #0F172A; }
[data-testid="stMetricLabel"] { color: #334155; }
</style>
"""

EMAIL_PLAYBOOKS = {
    "Blank": "",
    "Weekly status email": "Team, this week we completed milestones A and B. Owner: Alex. Next actions: finalize testing and share results by Friday. Risks: data dependency from vendor.",
    "Escalation email": "Hi Leadership, we have a blocker on API access. Owner: Priya. We need approval by EOD Thursday to avoid release delay.",
}

PROJECT_PLAYBOOKS = {
    "Blank": "",
}
RELATED_LINGO = {
    "kpi": ["metric", "dashboard", "performance tracking"],
    "roi": ["business case", "payback period", "margin"],
    "roadmap": ["milestone", "workstream", "deliverable"],
}


def card_start(title: str) -> None:
    st.markdown(f"<div class='block-card'><h4>{title}</h4>", unsafe_allow_html=True)


def card_end() -> None:
    st.markdown("</div>", unsafe_allow_html=True)


def render_items(title: str, items: list[str]) -> None:
    card_start(title)
    if items:
        for item in items:
            st.markdown(f"- {item}")
    else:
        st.markdown("<div class='small-muted'>None detected.</div>", unsafe_allow_html=True)
    card_end()




def build_email_brief_markdown(result: dict) -> str:
    lines = [
        "# Email Brief",
        "",
        "## Summary",
        result.get("email_summary", ""),
        "",
        "## Action Plan",
    ]
    for row in result.get("action_plan", []):
        lines.append(f"- Step {row['step']}: {row['what_to_do']} (Owner: {row['owner']}, Due: {row['due']}, Priority: {row['priority']})")
    lines.extend(["", "## Clarification Questions"])
    for q in result.get("clarification_questions", []):
        lines.append(f"- {q}")
    return "\n".join(lines)


def build_project_pack_markdown(result: dict) -> str:
    lines = ["# Project Pack", "", "## Categories"]
    lines.append(", ".join(result.get("matched_categories", [])))
    lines.extend(["", "## Recommended Deliverables"])
    for d in result.get("recommended_deliverables", []):
        lines.append(f"- {d}")
    lines.extend(["", "## Risks"])
    for r in result.get("risks_watchouts", []):
        lines.append(f"- {r}")
    lines.extend(["", "## Dependencies"])
    for dep in result.get("dependency_map", []):
        lines.append(f"- {dep['dependency']}: {dep['mitigation']}")
    return "\n".join(lines)


def to_excel_bytes(rows: list[dict]) -> bytes:
    output = BytesIO()
    frame = pd.DataFrame(rows)
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        frame.to_excel(writer, index=False, sheet_name="Sheet1")
    return output.getvalue()


def text_to_excel_bytes(title: str, text_body: str) -> bytes:
    return to_excel_bytes([{"title": title, "content": text_body}])


def workbook_excel_bytes(sheets: dict[str, list[dict]]) -> bytes:
    output = BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        for name, rows in sheets.items():
            pd.DataFrame(rows).to_excel(writer, index=False, sheet_name=name[:31] or "Sheet")
    return output.getvalue()




def quality_gate_status(missing_flags: list[str], required_fields: list[str]) -> tuple[str, list[str]]:
    missing_lower = {flag.lower() for flag in missing_flags}
    unresolved = []

    checks = {
        "must have owner": "missing owner",
        "must have due date": "missing due date",
        "must have success metric": "missing success metric",
        "must have decision owner": "missing decision owner",
        "must have dependency": "missing dependency",
    }

    for req in required_fields:
        req_norm = req.strip().lower()
        expected_flag = checks.get(req_norm)
        if expected_flag and any(expected_flag in flag for flag in missing_lower):
            unresolved.append(req)

    status = "Ready to Send" if not unresolved else "Not Ready"
    return status, unresolved


def render_lingo_translator() -> None:
    st.subheader("Corporate Lingo Translator")
    st.caption("Dictionary-first translations with exact, partial, and similarity matching.")

    user_phrase = st.text_input("Enter phrase", placeholder="Example: circle back")
    lingo_filter = st.multiselect(
        "Filter categories",
        ["Finance", "Analytics", "Consulting", "HR", "Tech", "Marketing"],
        default=[],
        help="Filter displayed category reference terms by business area.",
    )
    if st.button("Translate", key="translate_btn", type="primary"):
        if not user_phrase.strip():
            st.warning("Please enter a phrase.")
            return

        result = run_translate_lingo(user_phrase)
        if not result["found"]:
            st.info("No dictionary match found.")
            return

        matches = result["matches"]
        concise_translation = " | ".join(dict.fromkeys(m["translation"] for m in matches))
        upsert_lingo_history(user_phrase, concise_translation)

        card_start("Plain-English Translations")
        for match in matches:
            st.markdown(f"**{match['phrase']}** · {match['category']} · *{match['match_type']}*")
            st.markdown(match["translation"])
        card_end()


    st.markdown("#### Add your own lingo (term: meaning)")
    st.caption("Example: runway: how long budget lasts at current spend")
    pack_name = st.selectbox("Dictionary pack", ["General", "Product Team", "Finance Team", "Operations Team"], key="custom_pack")
    edited_by = st.text_input("Edited by", key="custom_edited_by")
    version_note = st.text_input("Version note", key="custom_version_note", placeholder="v1.0 initial terms")
    custom_input = st.text_area(
        "Enter one or more custom terms",
        placeholder="term one: meaning\nterm two: meaning",
        height=120,
        key="custom_lingo_input",
    )

    if st.button("Save custom terms", key="save_custom_terms"):
        if add_custom_lingo is None:
            st.error("Custom lingo saving is not available in this database version.")
        else:
            saved = 0
            for line in custom_input.splitlines():
                if ":" not in line:
                    continue
                term, meaning = line.split(":", 1)
                term = term.strip()
                meaning = meaning.strip()
                if term and meaning:
                    try:
                        add_custom_lingo(term, meaning, pack=pack_name, last_edited_by=edited_by, version_note=version_note)
                    except TypeError:
                        add_custom_lingo(term, meaning)
                    saved += 1
            if saved:
                st.success(f"Saved {saved} custom term(s).")
                st.rerun()
            else:
                st.warning("No valid `term: meaning` lines found.")

    custom_rows = get_custom_lingo_rows()
    if custom_rows:
        with st.expander("Your custom lingo terms"):
            st.dataframe(rows_to_dicts(custom_rows), use_container_width=True)
            if delete_custom_lingo is not None:
                selected_custom_id = st.selectbox("Delete custom term by ID", [row["id"] for row in custom_rows], key="custom_delete_id")
                if st.button("Delete selected custom term", key="delete_custom_term_btn"):
                    delete_custom_lingo(int(selected_custom_id))
                    st.success(f"Deleted custom term #{selected_custom_id}")
                    st.rerun()



    st.markdown("#### Import / Export custom dictionary")
    st.caption(
        "Import format guide: use `word: definition` or `word - definition` for TXT/PDF files. "
        "For CSV/Excel exports, use column A/header `term` for the word and column B/header `meaning` for the definition."
    )
    uploaded_dict = st.file_uploader("Upload dictionary file (CSV, JSON, TXT, or PDF)", type=["csv", "json", "txt", "pdf"], key="dict_upload")
    if uploaded_dict is not None and st.button("Import dictionary file", key="import_dict_btn"):
        imported = 0
        try:
            if uploaded_dict.name.lower().endswith(".json"):
                data = json.loads(uploaded_dict.getvalue().decode("utf-8"))
                for item in data:
                    term = str(item.get("term", "")).strip()
                    meaning = str(item.get("meaning", "")).strip()
                    if term and meaning:
                        try:
                            add_custom_lingo(term, meaning, pack=str(item.get("pack", "General")), last_edited_by=str(item.get("last_edited_by", "")), version_note=str(item.get("version_note", "")))
                        except TypeError:
                            add_custom_lingo(term, meaning)
                        imported += 1
            elif uploaded_dict.name.lower().endswith(".csv"):
                data = uploaded_dict.getvalue().decode("utf-8").splitlines()
                if data:
                    headers = [h.strip().lower() for h in data[0].split(",")]
                    for line in data[1:]:
                        parts = [p.strip() for p in line.split(",")]
                        row = dict(zip(headers, parts))
                        term = row.get("term", "")
                        meaning = row.get("meaning", "")
                        if term and meaning:
                            try:
                                add_custom_lingo(term, meaning, pack=row.get("pack", "General"), last_edited_by=row.get("last_edited_by", ""), version_note=row.get("version_note", ""))
                            except TypeError:
                                add_custom_lingo(term, meaning)
                            imported += 1
            else:
                if uploaded_dict.name.lower().endswith(".pdf"):
                    import importlib
                    pypdf = importlib.import_module("pypdf")
                    PdfReader = getattr(pypdf, "PdfReader")
                    pdf_reader = PdfReader(BytesIO(uploaded_dict.getvalue()))
                    raw_text = "\n".join((page.extract_text() or "") for page in pdf_reader.pages)
                else:
                    raw_text = uploaded_dict.getvalue().decode("utf-8", errors="ignore")

                for line in raw_text.splitlines():
                    line = line.strip()
                    if not line:
                        continue
                    if ":" in line:
                        term, meaning = line.split(":", 1)
                    elif " - " in line:
                        term, meaning = line.split(" - ", 1)
                    else:
                        continue
                    term = term.strip()
                    meaning = meaning.strip()
                    if term and meaning:
                        try:
                            add_custom_lingo(term, meaning, pack=pack_name, last_edited_by=edited_by, version_note=version_note)
                        except TypeError:
                            add_custom_lingo(term, meaning)
                        imported += 1
            st.success(f"Imported {imported} dictionary term(s).")
            st.rerun()
        except Exception as exc:
            st.error(f"Import failed: {exc}")

    custom_rows_excel = rows_to_dicts(get_custom_lingo_rows())
    st.download_button(
        "Download custom dictionary (Excel)",
        data=to_excel_bytes(custom_rows_excel),
        file_name="custom_dictionary.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )

    show_categories = st.toggle("Show lingo category reference", value=False)
    if show_categories:
        st.markdown("#### Lingo Categories")
        alias_map = {
            "Finance": ["Finance"],
            "Analytics": ["Data", "Analytics"],
            "Consulting": ["Strategy", "Execution", "Planning"],
            "HR": ["People", "HR"],
            "Tech": ["Tech", "Product", "Acronyms", "System"],
            "Marketing": ["Marketing", "Customer", "Campaign"],
        }
        for category, terms in LINGO_CATEGORIES.items():
            if lingo_filter:
                if not any(any(token.lower() in category.lower() for token in alias_map[f]) for f in lingo_filter):
                    continue
            with st.expander(f"{category} ({len(terms)})"):
                st.write(", ".join(sorted(terms.keys())))
    if user_phrase.strip():
        related = RELATED_LINGO.get(user_phrase.strip().lower())
        if related:
            st.caption(f"Related terms: {', '.join(related)}")


def render_email_simplifier() -> None:
    st.subheader("Email Simplifier")
    st.caption("Summarize email intent and extract actionable plan + clarification questions.")

    email_playbook = st.selectbox("Email template", list(EMAIL_PLAYBOOKS.keys()), key="email_playbook")
    audience_mode = "For Team"
    email_default = EMAIL_PLAYBOOKS[email_playbook]
    email = st.text_area("Paste email", value=email_default, height=230, placeholder="Paste corporate email text...")
    if st.button("Simplify Email", key="simplify_btn", type="primary"):
        if not email.strip():
            st.warning("Please paste an email first.")
            return

        result = simplify_email(email, audience_mode=audience_mode)
        m = result["metrics"]
        save_email_history(
            email,
            result["clean_email"],
            action_count=m["action_item_count"],
            deadline_count=m["deadline_count"],
            priority_count=m["priority_signal_count"],
        )

        top_actions = [row.get("what_to_do", "") for row in result.get("action_plan", []) if row.get("what_to_do", "")]
        if not top_actions:
            top_actions = result.get("action_items", [])
        top_actions = top_actions[:3]
        top_deadline = result.get("deadlines", [None])[0] if result.get("deadlines") else None
        main_risk = (result.get("priority_signals") or result.get("missing_info_flags") or [None])[0]

        card_start("Condensed Summary")
        st.markdown("**Top actions:**")
        if top_actions:
            for action in top_actions:
                st.markdown(f"- {action}")
        else:
            st.markdown("- No concrete action detected.")
        st.markdown(f"**Deadline:** {top_deadline or 'Not specified'}")
        st.markdown(f"**Main risk:** {main_risk or 'No major risk signal detected'}")
        card_end()

        with st.expander("Action Plan", expanded=True):
            card_start("Action Plan")
            action_plan_rows = result.get("action_plan", [])[:5]
            if action_plan_rows:
                for row in action_plan_rows:
                    st.markdown(
                        f"- **Step {row.get('step')}**: {row.get('what_to_do')} "
                        f"(Owner: {row.get('owner')}, Due: {row.get('due')}, Priority: {row.get('priority')})"
                    )
            else:
                st.caption("No concrete action plan could be formed from the email.")
            card_end()

        with st.expander("Key Signals", expanded=True):
            card_start("Key Signals")
            st.markdown("**Deadlines / Timing**")
            for item in result.get("deadlines", []):
                st.markdown(f"- {item}")
            if not result.get("deadlines"):
                st.markdown("- None detected.")
            st.markdown("**Priority / Urgency Signals**")
            for item in result.get("priority_signals", []):
                st.markdown(f"- {item}")
            if not result.get("priority_signals"):
                st.markdown("- None detected.")
            st.markdown("**Missing Info Flags**")
            for item in result.get("missing_info_flags", []):
                st.markdown(f"- {item}")
            if not result.get("missing_info_flags"):
                st.markdown("- None detected.")
            card_end()

        with st.expander("Communication Metrics", expanded=False):
            card_start("Communication Metrics")
            st.markdown("<div class='small-muted'>Supporting metrics for governance; use summary + actions + key signals for decisions.</div>", unsafe_allow_html=True)
            row1 = st.columns(4)
            row1[0].metric("Word count", m["word_count"])
            row1[1].metric("Sentence count", m["sentence_count"])
            row1[2].metric("Action item count", m["action_item_count"])
            row1[3].metric("Deadline count", m["deadline_count"])
            row2 = st.columns(4)
            row2[0].metric("Follow-up count", m["follow_up_count"])
            row2[1].metric("Priority signal count", m["priority_signal_count"])
            row2[2].metric("Corporate term count", m["corporate_term_count"])
            row2[3].metric("Owner mentions", m["owner_count"])
            card_end()

        run_id = None
        if add_workflow_run is not None:
            decisions = {
                "missing_flags": result.get("missing_info_flags", []),
                "clarification_questions": result.get("clarification_questions", []),
            }
            run_id = add_workflow_run(
                tool_type="email",
                source_input=email,
                playbook_name=email_playbook,
                audience_mode=audience_mode,
                output_summary=result.get("email_summary", ""),
                decisions_json=json.dumps(decisions),
                final_export_text=build_email_brief_markdown(result),
            )
            st.session_state["email_active_run_id"] = run_id

        action_plan_rows = result.get("action_plan", [])[:5]
        st.download_button(
            "Download Action Plan (Excel)",
            data=to_excel_bytes(action_plan_rows),
            file_name="email_action_plan.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )

        email_brief_md = build_email_brief_markdown(result)
        st.download_button(
            "Download Email Brief (Excel)",
            data=text_to_excel_bytes("Email Brief", email_brief_md),
            file_name="email_brief.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )


def render_workplan_generator() -> None:
    st.subheader("Project Workplan Generator")
    st.caption("Consultant-style output with category hit diagnostics and phased execution plan.")

    project_playbook = "Blank"
    project_audience = "For Team"
    project_default = PROJECT_PLAYBOOKS[project_playbook]
    project_text = st.text_area("Paste project description", value=project_default, height=230, placeholder="Describe project scope, goals, and constraints...")
    if st.button("Generate Workplan", key="workplan_btn", type="primary"):
        if not project_text.strip():
            st.warning("Please provide a project description.")
            return

        result = generate_workplan(project_text, audience_mode=project_audience)
        categories = ", ".join(result["matched_categories"])
        summary = f"Categories: {categories}; Start: {result.get('project_start_summary', {}).get('where_to_start', '')}"
        save_project_history(project_text, summary, categories_text=categories)

        card_start("Detected Categories")
        for category, hits in result["category_hits"].items():
            st.markdown(f"<span class='badge'>{category}: {hits} keyword hits</span>", unsafe_allow_html=True)
        card_end()

        summary = result.get("project_start_summary", {})
        card_start("Project Start Summary")
        st.markdown(f"**Objective:** {summary.get('objective', 'Not specified')}")
        st.markdown(f"**Where to start:** {summary.get('where_to_start', 'Not specified')}")
        st.markdown(f"**Main dependency:** {summary.get('main_dependency', 'Not specified')}")
        st.markdown(f"**Main risk:** {summary.get('main_risk', 'Not specified')}")
        card_end()

        card_start("Who to Talk To")
        st.dataframe(result.get("who_to_talk_to", []), use_container_width=True)
        card_end()

        with st.expander("First 5 Steps", expanded=True):
            render_items("First 5 Steps", result.get("first_5_steps", []))
        with st.expander("Watchouts", expanded=True):
            render_items("Watchouts", result.get("watchouts", []))
        with st.expander("Missing-info flags", expanded=False):
            render_items("Missing-info flags", result.get("missing_info_flags", []))

        with st.expander("Execution Notes Board", expanded=False):
            card_start("Execution Notes Board")
            board_rows = st.data_editor(
                [{"workstream": "Project Start", "rag_status": "Amber", "owner_assignment": "", "target_date": "", "progress_notes": ""}],
                use_container_width=True,
                key="execution_board",
            )
            card_end()

        required_fields = ["Must have decision owner", "Must have due date", "Must have success metric", "Must have dependency"]
        gate_status, unresolved = quality_gate_status(result.get("missing_info_flags", []), required_fields)
        has_dependency = "yes" if result.get("dependency_map") else "no"
        with st.expander("Quality Gates", expanded=False):
            card_start("Quality Gates")
            st.write(f"Status: **{gate_status}**")
            st.write(f"- Has owner? {'no' if 'Missing decision owner' in result.get('missing_info_flags', []) else 'yes'}")
            st.write(f"- Has deadline? {'no' if any('due date' in f.lower() for f in result.get('missing_info_flags', [])) else 'yes'}")
            st.write(f"- Has success metric? {'no' if any('success metric' in f.lower() for f in result.get('missing_info_flags', [])) else 'yes'}")
            st.write(f"- Has dependency? {has_dependency}")
            if unresolved:
                for item in unresolved:
                    st.write(f"- {item}")
            card_end()

        run_id = None
        if add_workflow_run is not None:
            decisions = {
                "missing_flags": result.get("missing_info_flags", []),
                "quality_gate": gate_status,
            }
            run_id = add_workflow_run(
                tool_type="project",
                source_input=project_text,
                playbook_name=project_playbook,
                audience_mode=project_audience,
                output_summary=result.get("audience_note", ""),
                decisions_json=json.dumps(decisions),
                final_export_text=build_project_pack_markdown(result),
            )
            if add_execution_board_rows is not None:
                add_execution_board_rows(run_id, board_rows)
            st.session_state["project_active_run_id"] = run_id

        active_project_run_id = run_id or st.session_state.get("project_active_run_id")
        project_pack_md = build_project_pack_markdown(result)
        st.download_button(
            "Download Project Pack (Excel)",
            data=text_to_excel_bytes("Project Pack", project_pack_md),
            file_name="project_pack.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )


def render_history_tab(title: str, rows: list, table: str, columns: list[str], csv_name: str) -> None:
    st.subheader(title)
    if not rows:
        st.caption("No history yet.")
        return

    keyword = st.text_input(f"Filter {title} rows", key=f"filter_{table}").strip().lower()
    row_dicts = rows_to_dicts(rows)
    if keyword:
        filtered = []
        for row in row_dicts:
            if any(keyword in str(v).lower() for v in row.values()):
                filtered.append(row)
        row_dicts = filtered

    st.dataframe(row_dicts, use_container_width=True)

    csv_rows = rows if not keyword else [r for r in rows if any(keyword in str(v).lower() for v in dict(r).values())]
    st.download_button(
        label=f"Download {title} Excel",
        data=to_excel_bytes([dict(row) for row in csv_rows]),
        file_name=csv_name.replace(".csv", ".xlsx"),
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )

    ids = [row["id"] for row in rows]
    selected = st.selectbox("Select ID to delete", ids, key=f"delete_{table}")
    if st.button("Delete selected entry", key=f"delete_btn_{table}"):
        delete_by_id(table, int(selected))
        st.success(f"Deleted entry #{selected}")
        st.rerun()

    if st.button("Clear all history", key=f"clear_{table}"):
        clear_table(table)
        st.success("History cleared.")
        st.rerun()


def render_communication_log_tab() -> None:
    st.subheader("Communication Log")
    st.caption("Central place to capture and review conversation notes for email and project runs.")

    workflow_rows = rows_to_dicts(get_workflow_runs())
    tool_type = st.selectbox("Workflow type", ["email", "project"], key="comm_tool_type")
    run_ids = [row["id"] for row in workflow_rows if row.get("tool_type") == tool_type]

    if not run_ids:
        st.info(f"No {tool_type} workflow runs yet. Generate a {tool_type} output first.")
        return

    run_id = run_ids[0]
    st.caption(f"Logging against latest {tool_type} run: #{run_id}")
    col1, col2, col3 = st.columns(3)
    contact_name = col1.text_input("Who I talked to", key=f"comm_contact_{tool_type}_{run_id}")
    happened_at = col2.text_input("Date/time", key=f"comm_time_{tool_type}_{run_id}", placeholder="2026-04-30 14:30")
    channel = col3.selectbox("Channel", ["Email", "Slack/Chat", "Meeting", "Phone", "Other"], key=f"comm_channel_{tool_type}_{run_id}")
    discussion_topic = st.text_input("Topic", key=f"comm_topic_{tool_type}_{run_id}")
    note_text = st.text_area("What we discussed", key=f"comm_notes_{tool_type}_{run_id}")
    changes_made = st.text_area("Changes I made", key=f"comm_changes_{tool_type}_{run_id}")
    next_steps = st.text_area("Next steps", key=f"comm_next_steps_{tool_type}_{run_id}")

    if st.button("Add communication note", key=f"comm_add_{tool_type}_{run_id}") and add_communication_log is not None:
        add_communication_log(
            run_id,
            tool_type,
            contact_name,
            note_text,
            happened_at,
            discussion_topic=discussion_topic,
            changes_made=changes_made,
            next_steps=next_steps,
            channel=channel,
        )
        st.success("Communication note saved.")

    log_rows = rows_to_dicts(get_communication_log(run_id, tool_type))
    if log_rows:
        st.dataframe(log_rows, use_container_width=True)
        st.download_button(
            "Download Communication Log (Excel)",
            data=to_excel_bytes(log_rows),
            file_name=f"{tool_type}_communication_log.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )


def render_readme_tab() -> None:
    st.subheader("README")
    st.markdown(
        """
### What this app does
- **Lingo Translator**: Converts corporate phrases into plain language.
- **Email Simplifier**: Produces a concise action-oriented brief from email text.
- **Project Starting Assistant**: Gives a quick-start project summary, key stakeholders, first steps, and watchouts.
- **History + Communication Log**: Stores prior outputs and communication notes.

### How to use
1. Pick a tab based on your workflow.
2. Paste your input text.
3. Run the action button (`Translate`, `Simplify`, or `Generate`).
4. Download outputs as Excel where available.

### Communication logs
- Capture who you talked to, when, what changed, and next steps.
- Logs are saved by workflow type and linked to recent runs.

### Notes
- Rule-based and deterministic (no external AI APIs).
- Data is stored locally in SQLite (`corporate_lingo.db`).
        """
    )


def main() -> None:
    initialize_database()

    st.markdown(CARD_CSS, unsafe_allow_html=True)
    st.markdown(
        """
        <div class="hero">
            <h2>🧭 ClarityLayer</h2>
            <p>Rule-based workplace clarity platform for lingo translation, communication simplification, and project execution planning.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    tab1, tab2, tab3, tab4, tab5 = st.tabs(
        [
            "README",
            "Lingo Translator",
            "Email Simplifier",
            "Workplan Generator",
            "History + Communication Log",
        ]
    )

    with tab1:
        render_readme_tab()
    with tab2:
        st.markdown("<div class='subpanel'><strong>Lingo Translator</strong> · Decode jargon and build your team dictionary.</div>", unsafe_allow_html=True)
        render_lingo_translator()
    with tab3:
        st.markdown("<div class='subpanel'><strong>Email Simplifier</strong> · Extract actions, deadlines, owners, and review checkpoints.</div>", unsafe_allow_html=True)
        render_email_simplifier()
    with tab4:
        st.markdown("<div class='subpanel'><strong>Workplan Generator</strong> · Build phased plans, risks, dependencies, and quality gates.</div>", unsafe_allow_html=True)
        render_workplan_generator()
    with tab5:
        st.markdown("<div class='subpanel'><strong>History</strong> · Review each workflow history by section.</div>", unsafe_allow_html=True)
        lingo_rows = get_lingo_history()
        email_rows = rows_to_dicts(get_email_history())
        project_rows = rows_to_dicts(get_project_history())
        workflow_rows = rows_to_dicts(get_workflow_runs())

        with st.expander("Workflow Runs"):
            if workflow_rows:
                st.dataframe(workflow_rows, use_container_width=True)
                selected_run = st.selectbox("View execution board for run ID", [row["id"] for row in workflow_rows], key="run_board_view")
                board_rows = rows_to_dicts(get_execution_board_rows(int(selected_run)))
                if board_rows:
                    st.dataframe(board_rows, use_container_width=True)
                else:
                    st.caption("No execution board saved for this run.")
            else:
                st.caption("No workflow runs yet.")

        history_choice = st.selectbox(
            "Choose history type",
            ["Lingo History", "Email History", "Project History"],
            key="history_dropdown",
        )

        if history_choice == "Lingo History":
            render_history_tab(
                "Lingo History",
                get_lingo_history(),
                "lingo_history",
                ["id", "input", "translation"],
                "lingo_history.csv",
            )
        elif history_choice == "Email History":
            render_history_tab(
                "Email History",
                get_email_history(),
                "email_history",
                ["id", "input", "cleaned", "action_count", "deadline_count", "priority_count"],
                "email_history.csv",
            )
        else:
            render_history_tab(
                "Project History",
                get_project_history(),
                "project_history",
                ["id", "input", "summary", "categories"],
                "project_history.csv",
            )
        st.markdown("---")
        render_communication_log_tab()

        # Combined export workbook with separate sheets.
        lingo_export = [dict(r) for r in get_lingo_history()]
        email_export = [dict(r) for r in get_email_history()]
        project_export = [dict(r) for r in get_project_history()]
        workflow_export = rows_to_dicts(get_workflow_runs())
        email_comm = []
        project_comm = []
        for row in workflow_export:
            run_id = int(row["id"])
            tool = row.get("tool_type")
            if tool == "email":
                email_comm.extend(rows_to_dicts(get_communication_log(run_id, "email")))
            elif tool == "project":
                project_comm.extend(rows_to_dicts(get_communication_log(run_id, "project")))

        st.download_button(
            "Download Email History + Communication Log (Excel Workbook)",
            data=workbook_excel_bytes(
                {
                    "Email History": email_export,
                    "Email Comm Log": email_comm,
                }
            ),
            file_name="email_history_and_comm_log.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
        st.download_button(
            "Download Project History + Communication Log (Excel Workbook)",
            data=workbook_excel_bytes(
                {
                    "Project History": project_export,
                    "Project Comm Log": project_comm,
                }
            ),
            file_name="project_history_and_comm_log.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )


if __name__ == "__main__":
    main()
