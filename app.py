"""ClarityLayer Streamlit app: no-AI workplace clarity tool."""

from __future__ import annotations

import json
from io import StringIO

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
.block-card { border: 1px solid #E6EAF0; border-radius: 12px; padding: 14px; margin-bottom: 14px; background: #FFFFFF; }
.small-muted { color: #6B7280; font-size: 0.92rem; }
.badge { display: inline-block; padding: 4px 8px; margin-right: 8px; margin-bottom: 6px; border-radius: 999px; background: #F3F4F6; font-size: 0.82rem; }
</style>
"""

EMAIL_PLAYBOOKS = {
    "Blank": "",
    "Weekly status email": "Team, this week we completed milestones A and B. Owner: Alex. Next actions: finalize testing and share results by Friday. Risks: data dependency from vendor.",
    "Escalation email": "Hi Leadership, we have a blocker on API access. Owner: Priya. We need approval by EOD Thursday to avoid release delay.",
}

PROJECT_PLAYBOOKS = {
    "Blank": "",
    "Project kickoff brief": "Launch a cross-functional initiative to improve dashboard reliability, clarify ownership, and reduce reporting delays over the next 8 weeks.",
    "Budget request": "Request budget for analytics platform upgrades to improve KPI visibility, automate reporting, and deliver ROI through reduced manual effort.",
}
ROLE_VIEWS = ["Analyst", "Manager", "Executive"]
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




def merged_playbooks(tool_type: str, defaults: dict) -> dict:
    merged = dict(defaults)
    for row in get_playbooks(tool_type):
        merged[row["name"]] = row["default_text"]
    return merged


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
    uploaded_dict = st.file_uploader("Upload dictionary file (CSV or JSON)", type=["csv", "json"], key="dict_upload")
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
            else:
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
            st.success(f"Imported {imported} dictionary term(s).")
            st.rerun()
        except Exception as exc:
            st.error(f"Import failed: {exc}")

    st.download_button("Download custom dictionary CSV", data=get_custom_lingo_csv(), file_name="custom_dictionary.csv", mime="text/csv")
    st.download_button("Download custom dictionary JSON", data=get_custom_lingo_json(), file_name="custom_dictionary.json", mime="application/json")

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

    email_sources = merged_playbooks("email", EMAIL_PLAYBOOKS)
    email_playbook = st.selectbox("Email playbook", list(email_sources.keys()), key="email_playbook")
    audience_mode = st.radio("Output mode", ["For Leadership", "For Team", "For Client"], horizontal=True, key="email_audience")
    email_role_view = st.selectbox("Role-based view", ROLE_VIEWS, key="email_role_view")
    email_default = email_sources[email_playbook]
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

        card_start("Condensed Summary")
        st.write(result["email_summary"])
        card_end()

        st.markdown("#### Objective Communication Metrics")
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

        render_items("Action Items", result["action_items"])
        render_items("Deadlines / Timing", result["deadlines"])
        render_items("Follow-up Items", result["follow_ups"])
        render_items("Priority / Urgency Signals", result["priority_signals"])
        render_items("Corporate Lingo Detected", result["corporate_terms"])
        render_items("Detected Owners", result["owners"])

        card_start("Action Registry")
        st.dataframe(result["action_registry"], use_container_width=True)
        card_end()

        card_start("Action Plan")
        if result["action_plan"]:
            st.dataframe(result["action_plan"], use_container_width=True)
        else:
            st.caption("No concrete action plan could be formed from the email.")
        card_end()

        render_items("Clarification questions to ask", result["clarification_questions"])
        render_items("Missing-info flags", result.get("missing_info_flags", []))
        render_items("Objective Tags", result.get("objective_tags", []))
        render_items("Explain Logic", result.get("explain_logic", []))

        if email_role_view == "Analyst":
            render_items("Analyst View: KPIs/Dependencies", [f"Corporate terms: {', '.join(result['corporate_terms']) or 'None'}"])
        elif email_role_view == "Manager":
            render_items("Manager View: Owners/Deadlines/Blockers", result["owners"] + result["deadlines"] + result["priority_signals"])
        else:
            render_items("Executive View: Decisions/Risks/Next Steps", result["clarification_questions"][:3] + result["priority_signals"][:2])

        required_fields = ["Must have owner", "Must have due date"]
        gate_status, unresolved = quality_gate_status(result.get("missing_info_flags", []), required_fields)
        card_start("Quality Gates")
        st.write(f"Status: **{gate_status}**")
        if unresolved:
            for item in unresolved:
                st.write(f"- {item}")
        card_end()

        run_id = None
        if add_workflow_run is not None:
            decisions = {
                "missing_flags": result.get("missing_info_flags", []),
                "clarification_questions": result.get("clarification_questions", []),
                "quality_gate": gate_status,
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

        if run_id and update_workflow_review is not None:
            st.markdown("#### Review checkpoint")
            review_status = st.selectbox("Reviewer status", ["Draft", "Approve", "Needs Revision"], key=f"email_review_status_{run_id}")
            review_comments = st.text_input("Reviewer comments", key=f"email_review_comments_{run_id}")
            if st.button("Save review checkpoint", key=f"save_email_review_{run_id}"):
                update_workflow_review(run_id, review_status, review_comments)
                st.success("Review checkpoint saved.")

        email_brief_md = build_email_brief_markdown(result)
        st.download_button("Download Email Brief (Markdown)", data=email_brief_md, file_name="email_brief.md", mime="text/markdown")


def render_workplan_generator() -> None:
    st.subheader("Project Workplan Generator")
    st.caption("Consultant-style output with category hit diagnostics and phased execution plan.")

    project_sources = merged_playbooks("project", PROJECT_PLAYBOOKS)
    project_playbook = st.selectbox("Project playbook", list(project_sources.keys()), key="project_playbook")
    project_audience = st.radio("Output mode", ["For Leadership", "For Team", "For Client"], horizontal=True, key="project_audience")
    project_role_view = st.selectbox("Role-based view", ROLE_VIEWS, key="project_role_view")
    project_default = project_sources[project_playbook]
    project_text = st.text_area("Paste project description", value=project_default, height=230, placeholder="Describe project scope, goals, and constraints...")
    if st.button("Generate Workplan", key="workplan_btn", type="primary"):
        if not project_text.strip():
            st.warning("Please provide a project description.")
            return

        result = generate_workplan(project_text, audience_mode=project_audience)
        categories = ", ".join(result["matched_categories"])
        summary = f"Categories: {categories}; Deliverables: {', '.join(result['recommended_deliverables'][:3])}"
        save_project_history(project_text, summary, categories_text=categories)

        card_start("Detected Categories")
        for category, hits in result["category_hits"].items():
            st.markdown(f"<span class='badge'>{category}: {hits} keyword hits</span>", unsafe_allow_html=True)
        card_end()

        render_items("Recommended Deliverables", result["recommended_deliverables"])
        render_items("Phase 1: Clarify and Scope", result["phase_1"])
        render_items("Phase 2: Gather and Validate", result["phase_2"])
        render_items("Phase 3: Analyze and Recommend", result["phase_3"])

        card_start("Execution Timeline (Rule-Based)")
        st.dataframe(result["phase_plan"], use_container_width=True)
        card_end()

        card_start("Workstreams and Ownership")
        board_rows = []
        for row in result["workstreams"]:
            board_rows.append({**row, "rag_status": "Amber", "owner_assignment": row.get("owner_role", ""), "target_date": "", "progress_notes": ""})
        edited_board = st.data_editor(board_rows, use_container_width=True, key="execution_board")
        card_end()

        render_items("Success metrics to track", result["success_metrics"])

        card_start("Dependency Map")
        st.dataframe(result["dependency_map"], use_container_width=True)
        card_end()

        render_items("Key Questions to Ask", result["key_questions"])
        render_items("Risks / Watchouts", result["risks_watchouts"])
        render_items("Missing-info flags", result.get("missing_info_flags", []))
        render_items("Objective Tags", result.get("objective_tags", []))
        render_items("Explain Logic", result.get("explain_logic", []))

        if project_role_view == "Analyst":
            render_items("Analyst View: Data/KPI/Dependencies", result["success_metrics"] + [d["dependency"] for d in result["dependency_map"]])
        elif project_role_view == "Manager":
            render_items("Manager View: Owners/Blockers/Deadlines", [w["owner_role"] for w in result["workstreams"]] + result["missing_info_flags"])
        else:
            render_items("Executive View: Decisions/Risks/Next Steps", result["key_questions"][:3] + result["risks_watchouts"][:2])

        required_fields = ["Must have decision owner", "Must have due date", "Must have success metric", "Must have dependency"]
        gate_status, unresolved = quality_gate_status(result.get("missing_info_flags", []), required_fields)
        has_dependency = "yes" if result.get("dependency_map") else "no"
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
                add_execution_board_rows(run_id, edited_board)

        if run_id and update_workflow_review is not None:
            st.markdown("#### Review checkpoint")
            review_status = st.selectbox("Reviewer status", ["Draft", "Approve", "Needs Revision"], key=f"project_review_status_{run_id}")
            review_comments = st.text_input("Reviewer comments", key=f"project_review_comments_{run_id}")
            if st.button("Save project review checkpoint", key=f"save_project_review_{run_id}"):
                update_workflow_review(run_id, review_status, review_comments)
                st.success("Project review checkpoint saved.")

        project_pack_md = build_project_pack_markdown(result)
        st.download_button("Download Project Pack (Markdown)", data=project_pack_md, file_name="project_pack.md", mime="text/markdown")


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
        label=f"Download {title} CSV",
        data=to_csv(csv_rows, columns),
        file_name=csv_name,
        mime="text/csv",
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


def main() -> None:
    initialize_database()

    st.markdown(CARD_CSS, unsafe_allow_html=True)
    st.title("🧭 ClarityLayer")
    st.markdown("No-AI workplace clarity platform for lingo translation, communication simplification, and workplan structuring.")

    tab1, tab2, tab3, tab4 = st.tabs(
        [
            "Lingo Translator",
            "Email Simplifier",
            "Workplan Generator",
            "History",
        ]
    )

    with tab1:
        render_lingo_translator()
    with tab2:
        render_email_simplifier()
    with tab3:
        render_workplan_generator()
    with tab4:
        st.markdown("### History Analytics")
        lingo_rows = get_lingo_history()
        email_rows = rows_to_dicts(get_email_history())
        project_rows = rows_to_dicts(get_project_history())
        workflow_rows = rows_to_dicts(get_workflow_runs())

        analytics_cols = st.columns(4)
        analytics_cols[0].metric("Total lingo entries", len(lingo_rows))
        analytics_cols[1].metric("Avg action items/email", round(sum(row.get("action_count", 0) for row in email_rows) / max(1, len(email_rows)), 2))
        missing_flags_counter = {}
        for row in workflow_rows:
            try:
                decisions = json.loads(row.get("decisions_json", "{}"))
                for flag in decisions.get("missing_flags", []):
                    missing_flags_counter[flag] = missing_flags_counter.get(flag, 0) + 1
            except Exception:
                pass
        top_flag = max(missing_flags_counter, key=missing_flags_counter.get) if missing_flags_counter else "None"
        analytics_cols[2].metric("Top missing-info flag", top_flag)
        pack_map = getattr(db, "get_custom_lingo_pack_map", lambda: {})()
        top_pack = max(pack_map, key=pack_map.get) if pack_map else "General"
        analytics_cols[3].metric("Top dictionary pack", top_pack)
        if workflow_rows:
            common_tool = max({r["tool_type"]: sum(1 for x in workflow_rows if x["tool_type"] == r["tool_type"]) for r in workflow_rows}, key=lambda x: sum(1 for y in workflow_rows if y["tool_type"] == x))
        else:
            common_tool = "N/A"
        st.metric("History by workflow type (top)", common_tool)

        lingo_term_counts = {}
        for row in lingo_rows:
            key = row["input"]
            lingo_term_counts[key] = lingo_term_counts.get(key, 0) + 1
        top_lingo = max(lingo_term_counts, key=lingo_term_counts.get) if lingo_term_counts else "None"
        st.metric("Most common lingo searched", top_lingo)
        st.metric("Emails processed", len(email_rows))

        # 7/30 day trend from workflow runs
        last_7 = len([r for r in workflow_rows[:7]])
        last_30 = len([r for r in workflow_rows[:30]])
        clarity_values = []
        for row in workflow_rows:
            try:
                decisions = json.loads(row.get("decisions_json", "{}"))
                clarity_values.append(len(decisions.get("clarification_questions", [])))
            except Exception:
                continue
        time_to_clarity = round(sum(clarity_values) / max(1, len(clarity_values)), 2)
        trend_cols = st.columns(3)
        trend_cols[0].metric("Workflow runs (last 7)", last_7)
        trend_cols[1].metric("Workflow runs (last 30)", last_30)
        trend_cols[2].metric("Time-to-clarity (avg open questions)", time_to_clarity)

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

        with st.expander("Playbook Builder"):
            pb_tool = st.selectbox("Tool type", ["email", "project"], key="pb_tool")
            pb_name = st.text_input("Playbook name", key="pb_name")
            pb_text = st.text_area("Default text", key="pb_text")
            pb_audience = st.selectbox("Audience default", ["For Leadership", "For Team", "For Client"], key="pb_audience")
            pb_required = st.text_input("Required fields (comma separated)", placeholder="owner,due date,success metric", key="pb_required")
            if st.button("Save playbook", key="save_playbook_btn") and add_playbook is not None:
                add_playbook(pb_tool, pb_name, pb_text, pb_audience, pb_required)
                st.success("Playbook saved.")
                st.rerun()

            rows = rows_to_dicts(get_playbooks(pb_tool))
            if rows:
                st.dataframe(rows, use_container_width=True)
                if delete_playbook is not None:
                    del_id = st.selectbox("Delete playbook ID", [r["id"] for r in rows], key="delete_playbook_id")
                    if st.button("Delete selected playbook", key="delete_playbook_btn"):
                        delete_playbook(int(del_id))
                        st.success("Playbook deleted.")
                        st.rerun()

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


if __name__ == "__main__":
    main()
