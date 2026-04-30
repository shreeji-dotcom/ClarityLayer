"""SQLite persistence layer for ClarityLayer."""

from __future__ import annotations

import csv
import io
import json
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterable, List, Sequence

DB_FILE = Path("corporate_lingo.db")
ALLOWED_TABLES = {"lingo_history", "email_history", "project_history"}


@contextmanager
def _connect() -> Iterable[sqlite3.Connection]:
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()


def _ensure_column(conn: sqlite3.Connection, table_name: str, column_name: str, definition: str) -> None:
    columns = {row["name"] for row in conn.execute(f"PRAGMA table_info({table_name})").fetchall()}
    if column_name not in columns:
        conn.execute(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {definition}")


def _column_names(conn: sqlite3.Connection, table_name: str) -> set[str]:
    return {row["name"] for row in conn.execute(f"PRAGMA table_info({table_name})").fetchall()}


def _migrate_lingo_history_schema(conn: sqlite3.Connection) -> None:
    cols = _column_names(conn, "lingo_history")

    if "normalized_input" not in cols:
        conn.execute("ALTER TABLE lingo_history ADD COLUMN normalized_input TEXT")
    if "input_text" not in cols:
        conn.execute("ALTER TABLE lingo_history ADD COLUMN input_text TEXT")
    if "translation_text" not in cols:
        conn.execute("ALTER TABLE lingo_history ADD COLUMN translation_text TEXT")

    cols = _column_names(conn, "lingo_history")
    if "input_phrase" in cols:
        conn.execute(
            """
            UPDATE lingo_history
            SET input_text = COALESCE(NULLIF(input_text, ''), input_phrase)
            WHERE input_text IS NULL OR input_text = ''
            """
        )
    if "translation" in cols:
        conn.execute(
            """
            UPDATE lingo_history
            SET translation_text = COALESCE(NULLIF(translation_text, ''), translation)
            WHERE translation_text IS NULL OR translation_text = ''
            """
        )

    conn.execute(
        """
        UPDATE lingo_history
        SET normalized_input = lower(trim(input_text))
        WHERE (normalized_input IS NULL OR normalized_input = '')
          AND input_text IS NOT NULL
          AND trim(input_text) != ''
        """
    )


def _migrate_email_history_schema(conn: sqlite3.Connection) -> None:
    cols = _column_names(conn, "email_history")

    if "input_text" not in cols:
        conn.execute("ALTER TABLE email_history ADD COLUMN input_text TEXT")
    if "clean_text" not in cols:
        conn.execute("ALTER TABLE email_history ADD COLUMN clean_text TEXT")
    if "action_count" not in cols:
        conn.execute("ALTER TABLE email_history ADD COLUMN action_count INTEGER NOT NULL DEFAULT 0")
    if "deadline_count" not in cols:
        conn.execute("ALTER TABLE email_history ADD COLUMN deadline_count INTEGER NOT NULL DEFAULT 0")
    if "priority_count" not in cols:
        conn.execute("ALTER TABLE email_history ADD COLUMN priority_count INTEGER NOT NULL DEFAULT 0")

    cols = _column_names(conn, "email_history")
    if "original_email" in cols:
        conn.execute(
            """
            UPDATE email_history
            SET input_text = COALESCE(NULLIF(input_text, ''), original_email)
            WHERE input_text IS NULL OR input_text = ''
            """
        )
    if "clean_email" in cols:
        conn.execute(
            """
            UPDATE email_history
            SET clean_text = COALESCE(NULLIF(clean_text, ''), clean_email)
            WHERE clean_text IS NULL OR clean_text = ''
            """
        )


def _migrate_project_history_schema(conn: sqlite3.Connection) -> None:
    cols = _column_names(conn, "project_history")

    if "input_text" not in cols:
        conn.execute("ALTER TABLE project_history ADD COLUMN input_text TEXT")
    if "summary_text" not in cols:
        conn.execute("ALTER TABLE project_history ADD COLUMN summary_text TEXT")
    if "categories_text" not in cols:
        conn.execute("ALTER TABLE project_history ADD COLUMN categories_text TEXT NOT NULL DEFAULT ''")

    cols = _column_names(conn, "project_history")
    if "project_input" in cols:
        conn.execute(
            """
            UPDATE project_history
            SET input_text = COALESCE(NULLIF(input_text, ''), project_input)
            WHERE input_text IS NULL OR input_text = ''
            """
        )
    if "workplan_summary" in cols:
        conn.execute(
            """
            UPDATE project_history
            SET summary_text = COALESCE(NULLIF(summary_text, ''), workplan_summary)
            WHERE summary_text IS NULL OR summary_text = ''
            """
        )


def _migrate_common_timestamps(conn: sqlite3.Connection) -> None:
    _ensure_column(conn, "lingo_history", "created_at", "TEXT")
    _ensure_column(conn, "email_history", "created_at", "TEXT")
    _ensure_column(conn, "project_history", "created_at", "TEXT")


def initialize_database() -> None:
    with _connect() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS lingo_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                normalized_input TEXT NOT NULL UNIQUE,
                input_text TEXT NOT NULL,
                translation_text TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS email_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                input_text TEXT NOT NULL,
                clean_text TEXT NOT NULL,
                action_count INTEGER NOT NULL DEFAULT 0,
                deadline_count INTEGER NOT NULL DEFAULT 0,
                priority_count INTEGER NOT NULL DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS project_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                input_text TEXT NOT NULL,
                summary_text TEXT NOT NULL,
                categories_text TEXT NOT NULL DEFAULT '',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS custom_lingo (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                term TEXT NOT NULL UNIQUE,
                meaning TEXT NOT NULL,
                pack TEXT NOT NULL DEFAULT 'General',
                last_edited_by TEXT NOT NULL DEFAULT '',
                version_note TEXT NOT NULL DEFAULT '',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS workflow_runs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                tool_type TEXT NOT NULL,
                source_input TEXT NOT NULL,
                playbook_name TEXT NOT NULL,
                audience_mode TEXT NOT NULL,
                output_summary TEXT NOT NULL,
                decisions_json TEXT NOT NULL DEFAULT '{}',
                final_export_text TEXT NOT NULL DEFAULT '',
                reviewer_status TEXT NOT NULL DEFAULT 'Draft',
                reviewer_comments TEXT NOT NULL DEFAULT '',
                revision_history TEXT NOT NULL DEFAULT '',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS execution_board (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                run_id INTEGER NOT NULL,
                workstream TEXT NOT NULL,
                rag_status TEXT NOT NULL DEFAULT 'Amber',
                owner_assignment TEXT NOT NULL DEFAULT '',
                target_date TEXT NOT NULL DEFAULT '',
                progress_notes TEXT NOT NULL DEFAULT '',
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS playbooks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                tool_type TEXT NOT NULL,
                name TEXT NOT NULL,
                default_text TEXT NOT NULL,
                audience_default TEXT NOT NULL DEFAULT 'For Team',
                required_fields TEXT NOT NULL DEFAULT '',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS run_feedback (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                run_id INTEGER NOT NULL,
                tool_type TEXT NOT NULL,
                reviewer_role TEXT NOT NULL DEFAULT 'Manager',
                sentiment TEXT NOT NULL DEFAULT 'Approve',
                score INTEGER NOT NULL DEFAULT 3,
                comments TEXT NOT NULL DEFAULT '',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS communication_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                run_id INTEGER NOT NULL,
                tool_type TEXT NOT NULL,
                contact_name TEXT NOT NULL DEFAULT '',
                discussion_topic TEXT NOT NULL DEFAULT '',
                note_text TEXT NOT NULL DEFAULT '',
                changes_made TEXT NOT NULL DEFAULT '',
                next_steps TEXT NOT NULL DEFAULT '',
                channel TEXT NOT NULL DEFAULT '',
                happened_at TEXT NOT NULL DEFAULT '',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        )

        _migrate_lingo_history_schema(conn)
        _migrate_email_history_schema(conn)
        _migrate_project_history_schema(conn)
        _migrate_common_timestamps(conn)
        _ensure_column(conn, "custom_lingo", "pack", "TEXT NOT NULL DEFAULT 'General'")
        _ensure_column(conn, "custom_lingo", "last_edited_by", "TEXT NOT NULL DEFAULT ''")
        _ensure_column(conn, "custom_lingo", "version_note", "TEXT NOT NULL DEFAULT ''")
        _ensure_column(conn, "custom_lingo", "updated_at", "TEXT")
        _ensure_column(conn, "communication_log", "discussion_topic", "TEXT NOT NULL DEFAULT ''")
        _ensure_column(conn, "communication_log", "changes_made", "TEXT NOT NULL DEFAULT ''")
        _ensure_column(conn, "communication_log", "next_steps", "TEXT NOT NULL DEFAULT ''")
        _ensure_column(conn, "communication_log", "channel", "TEXT NOT NULL DEFAULT ''")
        conn.commit()


def upsert_lingo_history(input_text: str, translation_text: str) -> None:
    normalized = " ".join(input_text.lower().split())
    with _connect() as conn:
        _migrate_lingo_history_schema(conn)
        try:
            conn.execute(
                """
                INSERT INTO lingo_history (normalized_input, input_text, translation_text)
                VALUES (?, ?, ?)
                ON CONFLICT(normalized_input)
                DO UPDATE SET
                    input_text = excluded.input_text,
                    translation_text = excluded.translation_text,
                    created_at = CURRENT_TIMESTAMP
                """,
                (normalized, input_text.strip(), translation_text.strip()),
            )
        except sqlite3.OperationalError:
            row = conn.execute(
                "SELECT id FROM lingo_history WHERE lower(trim(input_text)) = ? LIMIT 1",
                (normalized,),
            ).fetchone()
            if row:
                conn.execute(
                    """
                    UPDATE lingo_history
                    SET input_text = ?, translation_text = ?, normalized_input = ?, created_at = CURRENT_TIMESTAMP
                    WHERE id = ?
                    """,
                    (input_text.strip(), translation_text.strip(), normalized, row["id"]),
                )
            else:
                conn.execute(
                    "INSERT INTO lingo_history (normalized_input, input_text, translation_text) VALUES (?, ?, ?)",
                    (normalized, input_text.strip(), translation_text.strip()),
                )
        conn.commit()


def add_email_history(
    input_text: str,
    clean_text: str,
    action_count: int = 0,
    deadline_count: int = 0,
    priority_count: int = 0,
) -> None:
    with _connect() as conn:
        _migrate_email_history_schema(conn)
        _migrate_common_timestamps(conn)
        conn.execute(
            """
            INSERT INTO email_history (input_text, clean_text, action_count, deadline_count, priority_count)
            VALUES (?, ?, ?, ?, ?)
            """,
            (input_text.strip(), clean_text.strip(), action_count, deadline_count, priority_count),
        )
        conn.commit()


def add_project_history(input_text: str, summary_text: str, categories_text: str = "") -> None:
    with _connect() as conn:
        _migrate_project_history_schema(conn)
        _migrate_common_timestamps(conn)
        conn.execute(
            "INSERT INTO project_history (input_text, summary_text, categories_text) VALUES (?, ?, ?)",
            (input_text.strip(), summary_text.strip(), categories_text.strip()),
        )
        conn.commit()


def get_lingo_history() -> List[sqlite3.Row]:
    with _connect() as conn:
        _migrate_lingo_history_schema(conn)
        _migrate_common_timestamps(conn)
        return conn.execute(
            """
            SELECT id,
                   COALESCE(NULLIF(input_text, ''), normalized_input) AS input,
                   COALESCE(NULLIF(translation_text, ''), '') AS translation
            FROM lingo_history
            ORDER BY LOWER(COALESCE(NULLIF(input_text, ''), normalized_input)) ASC
            """
        ).fetchall()


def get_email_history() -> List[sqlite3.Row]:
    with _connect() as conn:
        _migrate_email_history_schema(conn)
        _migrate_common_timestamps(conn)
        return conn.execute(
            """
            SELECT id,
                   COALESCE(NULLIF(input_text, ''), '') AS input,
                   COALESCE(NULLIF(clean_text, ''), '') AS cleaned,
                   COALESCE(action_count, 0) AS action_count,
                   COALESCE(deadline_count, 0) AS deadline_count,
                   COALESCE(priority_count, 0) AS priority_count
            FROM email_history
            ORDER BY id DESC
            """
        ).fetchall()


def get_project_history() -> List[sqlite3.Row]:
    with _connect() as conn:
        _migrate_project_history_schema(conn)
        _migrate_common_timestamps(conn)
        return conn.execute(
            """
            SELECT id,
                   COALESCE(NULLIF(input_text, ''), '') AS input,
                   COALESCE(NULLIF(summary_text, ''), '') AS summary,
                   COALESCE(NULLIF(categories_text, ''), '') AS categories
            FROM project_history
            ORDER BY id DESC
            """
        ).fetchall()


def delete_by_id(table: str, row_id: int) -> None:
    if table not in ALLOWED_TABLES:
        raise ValueError("Unsupported table")
    with _connect() as conn:
        conn.execute(f"DELETE FROM {table} WHERE id = ?", (row_id,))
        conn.commit()


def clear_table(table: str) -> None:
    if table not in ALLOWED_TABLES:
        raise ValueError("Unsupported table")
    with _connect() as conn:
        conn.execute(f"DELETE FROM {table}")
        conn.commit()


def rows_to_dicts(rows: Iterable[sqlite3.Row]) -> List[dict]:
    return [dict(row) for row in rows]


def to_csv(rows: Sequence[sqlite3.Row], columns: Sequence[str]) -> str:
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(columns)
    for row in rows:
        writer.writerow([row[col] for col in columns])
    return output.getvalue()


def add_custom_lingo(
    term: str,
    meaning: str,
    pack: str = "General",
    last_edited_by: str = "",
    version_note: str = "",
) -> None:
    term_norm = " ".join(term.lower().split())
    with _connect() as conn:
        _ensure_column(conn, "custom_lingo", "pack", "TEXT NOT NULL DEFAULT 'General'")
        _ensure_column(conn, "custom_lingo", "last_edited_by", "TEXT NOT NULL DEFAULT ''")
        _ensure_column(conn, "custom_lingo", "version_note", "TEXT NOT NULL DEFAULT ''")
        _ensure_column(conn, "custom_lingo", "updated_at", "TEXT")
        conn.execute(
            """
            INSERT INTO custom_lingo (term, meaning, pack, last_edited_by, version_note, updated_at)
            VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(term) DO UPDATE SET
                meaning = excluded.meaning,
                pack = excluded.pack,
                last_edited_by = excluded.last_edited_by,
                version_note = excluded.version_note,
                updated_at = CURRENT_TIMESTAMP
            """,
            (term_norm, meaning.strip(), pack.strip() or "General", last_edited_by.strip(), version_note.strip()),
        )
        conn.commit()


def get_custom_lingo_map() -> dict:
    with _connect() as conn:
        _ensure_column(conn, "custom_lingo", "pack", "TEXT NOT NULL DEFAULT 'General'")
        rows = conn.execute("SELECT term, meaning FROM custom_lingo ORDER BY term ASC").fetchall()
        return {row["term"]: row["meaning"] for row in rows}


def get_custom_lingo_rows() -> List[sqlite3.Row]:
    with _connect() as conn:
        _ensure_column(conn, "custom_lingo", "pack", "TEXT NOT NULL DEFAULT 'General'")
        _ensure_column(conn, "custom_lingo", "last_edited_by", "TEXT NOT NULL DEFAULT ''")
        _ensure_column(conn, "custom_lingo", "version_note", "TEXT NOT NULL DEFAULT ''")
        _ensure_column(conn, "custom_lingo", "updated_at", "TEXT")
        return conn.execute(
            "SELECT id, term, meaning, pack, last_edited_by, version_note, COALESCE(updated_at,'') AS updated_at FROM custom_lingo ORDER BY term ASC"
        ).fetchall()


def get_custom_lingo_pack_map() -> dict:
    with _connect() as conn:
        _ensure_column(conn, "custom_lingo", "pack", "TEXT NOT NULL DEFAULT 'General'")
        rows = conn.execute("SELECT pack, COUNT(*) AS count FROM custom_lingo GROUP BY pack ORDER BY pack ASC").fetchall()
        return {row["pack"]: row["count"] for row in rows}


def delete_custom_lingo(row_id: int) -> None:
    with _connect() as conn:
        conn.execute("DELETE FROM custom_lingo WHERE id = ?", (row_id,))
        conn.commit()


def get_custom_lingo_by_pack(pack: str) -> dict:
    with _connect() as conn:
        rows = conn.execute("SELECT term, meaning FROM custom_lingo WHERE pack = ? ORDER BY term ASC", (pack,)).fetchall()
        return {row["term"]: row["meaning"] for row in rows}


def get_custom_lingo_csv() -> str:
    rows = get_custom_lingo_rows()
    return to_csv(rows, ["id", "term", "meaning", "pack", "last_edited_by", "version_note", "updated_at"])


def get_custom_lingo_json() -> str:
    return json.dumps(rows_to_dicts(get_custom_lingo_rows()), indent=2)


def add_workflow_run(
    tool_type: str,
    source_input: str,
    playbook_name: str,
    audience_mode: str,
    output_summary: str,
    decisions_json: str = "{}",
    final_export_text: str = "",
) -> int:
    with _connect() as conn:
        cursor = conn.execute(
            """
            INSERT INTO workflow_runs (
                tool_type, source_input, playbook_name, audience_mode,
                output_summary, decisions_json, final_export_text
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (tool_type, source_input, playbook_name, audience_mode, output_summary, decisions_json, final_export_text),
        )
        conn.commit()
        return int(cursor.lastrowid)


def update_workflow_review(run_id: int, reviewer_status: str, reviewer_comments: str) -> None:
    with _connect() as conn:
        previous = conn.execute("SELECT revision_history FROM workflow_runs WHERE id = ?", (run_id,)).fetchone()
        history = previous["revision_history"] if previous else ""
        line = f"{reviewer_status}: {reviewer_comments}".strip()
        revision = f"{history}\n{line}".strip() if history else line
        conn.execute(
            """
            UPDATE workflow_runs
            SET reviewer_status = ?, reviewer_comments = ?, revision_history = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (reviewer_status, reviewer_comments, revision, run_id),
        )
        conn.commit()


def get_workflow_runs(limit: int = 200) -> List[sqlite3.Row]:
    with _connect() as conn:
        return conn.execute("SELECT * FROM workflow_runs ORDER BY id DESC LIMIT ?", (limit,)).fetchall()


def add_execution_board_rows(run_id: int, rows: List[dict]) -> None:
    with _connect() as conn:
        conn.execute("DELETE FROM execution_board WHERE run_id = ?", (run_id,))
        for row in rows:
            conn.execute(
                """
                INSERT INTO execution_board (run_id, workstream, rag_status, owner_assignment, target_date, progress_notes)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    run_id,
                    str(row.get("workstream", "")),
                    str(row.get("rag_status", "Amber")),
                    str(row.get("owner_assignment", "")),
                    str(row.get("target_date", "")),
                    str(row.get("progress_notes", "")),
                ),
            )
        conn.commit()


def get_execution_board_rows(run_id: int) -> List[sqlite3.Row]:
    with _connect() as conn:
        return conn.execute(
            "SELECT workstream, rag_status, owner_assignment, target_date, progress_notes FROM execution_board WHERE run_id = ?",
            (run_id,),
        ).fetchall()


def add_playbook(tool_type: str, name: str, default_text: str, audience_default: str, required_fields: str) -> None:
    with _connect() as conn:
        conn.execute(
            """
            INSERT INTO playbooks (tool_type, name, default_text, audience_default, required_fields)
            VALUES (?, ?, ?, ?, ?)
            """,
            (tool_type, name, default_text, audience_default, required_fields),
        )
        conn.commit()


def get_playbooks(tool_type: str) -> List[sqlite3.Row]:
    with _connect() as conn:
        return conn.execute(
            "SELECT id, name, default_text, audience_default, required_fields FROM playbooks WHERE tool_type = ? ORDER BY id DESC",
            (tool_type,),
        ).fetchall()


def delete_playbook(playbook_id: int) -> None:
    with _connect() as conn:
        conn.execute("DELETE FROM playbooks WHERE id = ?", (playbook_id,))
        conn.commit()


def add_run_feedback(
    run_id: int,
    tool_type: str,
    reviewer_role: str,
    sentiment: str,
    score: int,
    comments: str,
) -> None:
    with _connect() as conn:
        conn.execute(
            """
            INSERT INTO run_feedback (run_id, tool_type, reviewer_role, sentiment, score, comments)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (run_id, tool_type, reviewer_role, sentiment, int(score), comments.strip()),
        )
        conn.commit()


def get_run_feedback(run_id: int) -> List[sqlite3.Row]:
    with _connect() as conn:
        return conn.execute(
            """
            SELECT id, run_id, tool_type, reviewer_role, sentiment, score, comments, created_at
            FROM run_feedback
            WHERE run_id = ?
            ORDER BY id DESC
            """,
            (run_id,),
        ).fetchall()


def add_communication_log(
    run_id: int,
    tool_type: str,
    contact_name: str,
    note_text: str,
    happened_at: str,
    discussion_topic: str = "",
    changes_made: str = "",
    next_steps: str = "",
    channel: str = "",
) -> None:
    with _connect() as conn:
        conn.execute(
            """
            INSERT INTO communication_log (
                run_id, tool_type, contact_name, discussion_topic, note_text, changes_made, next_steps, channel, happened_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                run_id,
                tool_type,
                contact_name.strip(),
                discussion_topic.strip(),
                note_text.strip(),
                changes_made.strip(),
                next_steps.strip(),
                channel.strip(),
                happened_at.strip(),
            ),
        )
        conn.commit()


def get_communication_log(run_id: int, tool_type: str) -> List[sqlite3.Row]:
    with _connect() as conn:
        return conn.execute(
            """
            SELECT id, run_id, tool_type, contact_name, discussion_topic, note_text, changes_made, next_steps, channel, happened_at, created_at
            FROM communication_log
            WHERE run_id = ? AND tool_type = ?
            ORDER BY id DESC
            """,
            (run_id, tool_type),
        ).fetchall()


# Backward-compatible function aliases for older app imports

def insert_lingo_history(input_text: str, translation_text: str) -> None:
    upsert_lingo_history(input_text, translation_text)


def insert_email_history(input_text: str, clean_text: str) -> None:
    add_email_history(input_text, clean_text)


def insert_project_history(input_text: str, summary_text: str) -> None:
    add_project_history(input_text, summary_text)


def fetch_lingo_history() -> List[sqlite3.Row]:
    return get_lingo_history()


def fetch_email_history() -> List[sqlite3.Row]:
    return get_email_history()


def fetch_project_history() -> List[sqlite3.Row]:
    return get_project_history()


def delete_history_row(table: str, row_id: int) -> None:
    delete_by_id(table, row_id)


def clear_history_table(table: str) -> None:
    clear_table(table)
