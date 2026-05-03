"""Tests for the I3 PostgreSQL schema migrations (WP-I3-003).

Covers:
  - Clean apply of 001..004 in order; schema_version rows present.
  - Idempotent re-apply.
  - Every CHECK constraint named with a rule_id rejects its forbidden
    state with the constraint name visible in the error.
  - `library.dedupe_check` returns expected overlap counts.
  - `library_target_card_counts` view aggregates correctly across all
    7 status values.

Reuses the `library_pg` fixture pattern from test_db_migrator.py:
skips cleanly when no system Postgres is available.
"""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from openrepose.db.migrator import Migrator

# ---------------------------------------------------------------------------
# pytest-postgresql wiring (mirrors test_db_migrator.py).
# ---------------------------------------------------------------------------

PG_AVAILABLE = shutil.which("pg_ctl") is not None
HAS_PYTEST_POSTGRESQL = False
try:  # pragma: no cover - import guard
    from pytest_postgresql import factories as _pg_factories  # noqa: F401

    HAS_PYTEST_POSTGRESQL = True
except ImportError:
    pass


if PG_AVAILABLE and HAS_PYTEST_POSTGRESQL:
    from pytest_postgresql import factories as _factories

    library_pg_proc_i3 = _factories.postgresql_proc(
        port=None,
        postgres_options="-c log_destination=stderr -c logging_collector=off",
    )
    library_pg = _factories.postgresql("library_pg_proc_i3")
else:  # pragma: no cover

    @pytest.fixture
    def library_pg():
        pytest.skip(
            "pytest-postgresql or system pg_ctl unavailable; "
            "skipping live-DB I3 migration tests"
        )


def _dsn(pg_conn) -> str:  # noqa: ANN001
    info = pg_conn.info
    parts = [
        f"host={info.host}",
        f"port={info.port}",
        f"user={info.user}",
        f"dbname={info.dbname}",
    ]
    if getattr(info, "password", ""):
        parts.append(f"password={info.password}")
    return " ".join(parts)


def _migrations_dir() -> Path:
    return Path(__file__).resolve().parent.parent.parent / ".product" / "migrations"


pytestmark = pytest.mark.skipif(
    not (PG_AVAILABLE and HAS_PYTEST_POSTGRESQL),
    reason="no system Postgres / pytest-postgresql",
)


# ---------------------------------------------------------------------------
# Apply + idempotency
# ---------------------------------------------------------------------------


def test_i3_migrations_apply_in_order(library_pg):
    """001..004 apply cleanly; schema_version reflects all four."""
    import psycopg

    with psycopg.connect(_dsn(library_pg)) as conn:
        migrator = Migrator(conn, migrations_dir=_migrations_dir())
        applied = migrator.apply_pending()
        assert applied == [1, 2, 3, 4]
        assert migrator.current_version() == 4

        # Idempotent re-apply.
        assert migrator.apply_pending() == []


def test_i3_creates_all_required_tables(library_pg):
    import psycopg

    with psycopg.connect(_dsn(library_pg)) as conn:
        Migrator(conn, migrations_dir=_migrations_dir()).apply_pending()
        with conn.cursor() as cur:
            cur.execute(
                "SELECT table_name FROM information_schema.tables "
                "WHERE table_schema = 'public'"
            )
            tables = {row[0] for row in cur.fetchall()}

    expected = {
        "library_projects",
        "library_tasks",
        "library_batches",
        "library_pose_guides",
        "library_runs",
        "library_outputs",
        "library_scorecards",
        "library_diagnostics",
        "library_diversity_audits",
        "library_target_groups",
        "library_target_cards",
        "library_rules",
    }
    missing = expected - tables
    assert not missing, f"missing tables: {missing}"


def test_library_entries_gains_amood_columns(library_pg):
    import psycopg

    with psycopg.connect(_dsn(library_pg)) as conn:
        Migrator(conn, migrations_dir=_migrations_dir()).apply_pending()
        with conn.cursor() as cur:
            cur.execute(
                "SELECT column_name FROM information_schema.columns "
                "WHERE table_name = 'library_entries'"
            )
            columns = {row[0] for row in cur.fetchall()}

    expected = {
        "batch_id",
        "status",
        "sexual_trigger",
        "kink_cue",
        "porn_archetype",
        "fantasy_mode",
        "explicit_family",
        "exposure_detail",
        "archetype_signal",
        "scene_engine",
        "shot_purpose",
        "dedupe_signature",
        "compatibility_signature",
        "parent_card_id",
        "variant_label",
        "stability_target",
        "target_promoted",
        "abandonment_reason",
        "abandoned_after_seeds",
    }
    missing = expected - columns
    assert not missing, f"missing library_entries columns: {missing}"


def test_view_and_function_exist(library_pg):
    import psycopg

    with psycopg.connect(_dsn(library_pg)) as conn:
        Migrator(conn, migrations_dir=_migrations_dir()).apply_pending()
        with conn.cursor() as cur:
            cur.execute(
                "SELECT 1 FROM information_schema.views "
                "WHERE table_name = 'library_target_card_counts'"
            )
            assert cur.fetchone() is not None, "view library_target_card_counts missing"

            cur.execute(
                "SELECT 1 FROM pg_proc p "
                "JOIN pg_namespace n ON n.oid = p.pronamespace "
                "WHERE n.nspname = 'library' AND p.proname = 'dedupe_check'"
            )
            assert cur.fetchone() is not None, "library.dedupe_check function missing"


# ---------------------------------------------------------------------------
# Helpers for synthetic data (used by CHECK / view / dedupe tests)
# ---------------------------------------------------------------------------


def _seed_minimal(conn) -> dict:  # noqa: ANN001
    """Insert one project + task + batch + card (library_entries) + run.

    Returns a dict of the inserted UUIDs for downstream tests to use.
    """
    with conn.cursor() as cur:
        cur.execute(
            "INSERT INTO library_projects (slug, name, owner_slug) "
            "VALUES ('exposure-120', 'Exposure 120', 'op') RETURNING id"
        )
        project_id = cur.fetchone()[0]

        cur.execute(
            "INSERT INTO library_tasks (project_id, slug, intake_dir, expected_count) "
            "VALUES (%s, 'T-001', '20260503-T001/', 80) RETURNING id",
            (project_id,),
        )
        task_id = cur.fetchone()[0]

        cur.execute(
            "INSERT INTO library_batches (project_id, task_id, slug) "
            "VALUES (%s, %s, 'B-001') RETURNING id",
            (project_id, task_id),
        )
        batch_id = cur.fetchone()[0]

        cur.execute(
            "INSERT INTO library_entries (avatar_slug, title, batch_id, status, "
            "                             dedupe_signature, compatibility_signature) "
            "VALUES ('aeri', 'SF-15', %s, 'pending', "
            "        'pussy|standing|frontal|robe-open|bed-edge|hotel|eye-level|warm', "
            "        'standing|frontal|hotel') RETURNING id",
            (batch_id,),
        )
        card_id = cur.fetchone()[0]

        cur.execute(
            "INSERT INTO library_runs (card_id, task_id) "
            "VALUES (%s, %s) RETURNING id",
            (card_id, task_id),
        )
        run_id = cur.fetchone()[0]
    conn.commit()
    return {
        "project_id": project_id,
        "task_id": task_id,
        "batch_id": batch_id,
        "card_id": card_id,
        "run_id": run_id,
    }


# ---------------------------------------------------------------------------
# CHECK constraint coverage
# ---------------------------------------------------------------------------


def test_library_outputs_status_enum_rejects_unknown(library_pg):
    import psycopg

    with psycopg.connect(_dsn(library_pg)) as conn:
        Migrator(conn, migrations_dir=_migrations_dir()).apply_pending()
        ids = _seed_minimal(conn)
        with conn.cursor() as cur, pytest.raises(psycopg.errors.CheckViolation) as ei:
            cur.execute(
                "INSERT INTO library_outputs (run_id, task_id, file_path, content_hash, "
                "                             width, height, status) "
                "VALUES (%s, %s, 'x.png', 'h', 1080, 1440, 'oops')",
                (ids["run_id"], ids["task_id"]),
            )
        assert "library_outputs_status_enum" in str(ei.value)


def test_intake_001_two_stage_acceptance_blocks_promote_without_finalizer(library_pg):
    """A direct SQL insert that sets status='promoted' without
    finalized_by must be rejected by the rule-named CHECK constraint."""
    import psycopg

    with psycopg.connect(_dsn(library_pg)) as conn:
        Migrator(conn, migrations_dir=_migrations_dir()).apply_pending()
        ids = _seed_minimal(conn)
        with conn.cursor() as cur, pytest.raises(psycopg.errors.CheckViolation) as ei:
            cur.execute(
                "INSERT INTO library_outputs (run_id, task_id, file_path, content_hash, "
                "                             width, height, status) "
                "VALUES (%s, %s, 'x.png', 'h', 1080, 1440, 'promoted')",
                (ids["run_id"], ids["task_id"]),
            )
        assert "lib_outputs_intake_001_two_stage_acceptance" in str(ei.value)


def test_intake_001_two_stage_allows_promote_with_finalizer(library_pg):
    """The same row with finalized_by set is allowed."""
    import psycopg

    with psycopg.connect(_dsn(library_pg)) as conn:
        Migrator(conn, migrations_dir=_migrations_dir()).apply_pending()
        ids = _seed_minimal(conn)
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO library_outputs (run_id, task_id, file_path, content_hash, "
                "                             width, height, status, finalized_by) "
                "VALUES (%s, %s, 'x.png', 'h', 1080, 1440, 'promoted', 'op') "
                "RETURNING id",
                (ids["run_id"], ids["task_id"]),
            )
            assert cur.fetchone() is not None
        conn.commit()


def _insert_scorecard_promote(cur, run_id, output_id, **scores):  # noqa: ANN001
    """Insert a scorecard with sensible defaults; tests override fields."""
    defaults = {
        "adult_gate_score": 5,
        "trigger_clarity_score": 4,
        "anatomy_score": 3,
        "artifact_score": 4,
        "explicit_target_score": 4,
        "arousal_score": 4,
        "beauty_score": 4,
        "promotion_decision": "promote",
        "primary_rejection_reason": None,
    }
    defaults.update(scores)
    cur.execute(
        "INSERT INTO library_scorecards "
        "(review_id, run_id, output_id, "
        " adult_gate_score, trigger_clarity_score, anatomy_score, artifact_score, "
        " explicit_target_score, arousal_score, beauty_score, "
        " promotion_decision, primary_rejection_reason) "
        "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
        (
            f"RV-{output_id.hex[:8]}",
            run_id,
            output_id,
            defaults["adult_gate_score"],
            defaults["trigger_clarity_score"],
            defaults["anatomy_score"],
            defaults["artifact_score"],
            defaults["explicit_target_score"],
            defaults["arousal_score"],
            defaults["beauty_score"],
            defaults["promotion_decision"],
            defaults["primary_rejection_reason"],
        ),
    )


def _seed_output(conn, ids, status="pending", finalized_by=None, suffix="a"):  # noqa: ANN001
    with conn.cursor() as cur:
        cur.execute(
            "INSERT INTO library_outputs (run_id, task_id, file_path, content_hash, "
            "                             width, height, status, finalized_by) "
            "VALUES (%s, %s, %s, %s, 1080, 1440, %s, %s) RETURNING id",
            (
                ids["run_id"],
                ids["task_id"],
                f"{suffix}.png",
                f"h-{suffix}",
                status,
                finalized_by,
            ),
        )
        output_id = cur.fetchone()[0]
    conn.commit()
    return output_id


def test_amood_003_fast_triage_blocks_promote_with_low_adult_gate(library_pg):
    import psycopg

    with psycopg.connect(_dsn(library_pg)) as conn:
        Migrator(conn, migrations_dir=_migrations_dir()).apply_pending()
        ids = _seed_minimal(conn)
        output_id = _seed_output(conn, ids, status="soft_accepted")
        with conn.cursor() as cur, pytest.raises(psycopg.errors.CheckViolation) as ei:
            _insert_scorecard_promote(
                cur, ids["run_id"], output_id, adult_gate_score=3
            )
        assert "lib_scorecards_amood_003_fast_triage" in str(ei.value)


def test_amood_004_promotion_thresholds_blocks_promote_with_low_arousal(library_pg):
    import psycopg

    with psycopg.connect(_dsn(library_pg)) as conn:
        Migrator(conn, migrations_dir=_migrations_dir()).apply_pending()
        ids = _seed_minimal(conn)
        output_id = _seed_output(conn, ids, status="soft_accepted")
        with conn.cursor() as cur, pytest.raises(psycopg.errors.CheckViolation) as ei:
            _insert_scorecard_promote(
                cur, ids["run_id"], output_id, arousal_score=3
            )
        assert "lib_scorecards_amood_004_promotion_thresholds" in str(ei.value)


@pytest.mark.parametrize(
    "reason,constraint",
    [
        ("juvenile_coded",     "lib_scorecards_safe_001_juvenile_block"),
        ("coercion_coded",     "lib_scorecards_safe_002_coercion_block"),
        ("hidden_camera_coded", "lib_scorecards_safe_003_hidden_camera_block"),
    ],
)
def test_safety_boundaries_block_promote(library_pg, reason, constraint):
    import psycopg

    with psycopg.connect(_dsn(library_pg)) as conn:
        Migrator(conn, migrations_dir=_migrations_dir()).apply_pending()
        ids = _seed_minimal(conn)
        output_id = _seed_output(
            conn, ids, status="soft_accepted", suffix=reason[:6]
        )
        with conn.cursor() as cur, pytest.raises(psycopg.errors.CheckViolation) as ei:
            _insert_scorecard_promote(
                cur, ids["run_id"], output_id, primary_rejection_reason=reason
            )
        assert constraint in str(ei.value)


def test_scorecard_non_promote_decisions_are_unrestricted(library_pg):
    """A reject/defer/abandon decision skips all promotion gates."""
    import psycopg

    with psycopg.connect(_dsn(library_pg)) as conn:
        Migrator(conn, migrations_dir=_migrations_dir()).apply_pending()
        ids = _seed_minimal(conn)
        output_id = _seed_output(conn, ids, status="rejected", suffix="rj")
        with conn.cursor() as cur:
            _insert_scorecard_promote(
                cur,
                ids["run_id"],
                output_id,
                adult_gate_score=1,
                trigger_clarity_score=1,
                anatomy_score=1,
                artifact_score=1,
                arousal_score=1,
                beauty_score=1,
                promotion_decision="reject",
                primary_rejection_reason="juvenile_coded",
            )
        conn.commit()


def test_library_rules_severity_enum_rejects_unknown(library_pg):
    import psycopg

    with psycopg.connect(_dsn(library_pg)) as conn:
        Migrator(conn, migrations_dir=_migrations_dir()).apply_pending()
        ids = _seed_minimal(conn)
        with conn.cursor() as cur, pytest.raises(psycopg.errors.CheckViolation) as ei:
            cur.execute(
                "INSERT INTO library_rules "
                "(rule_id, scope_type, scope_id, name, short, severity) "
                "VALUES ('TEST-001', 'project', %s, 'test', 'short', 'panic')",
                (ids["project_id"],),
            )
        assert "library_rules_severity_enum" in str(ei.value)


def test_library_rules_kind_enum_rejects_unknown(library_pg):
    import psycopg

    with psycopg.connect(_dsn(library_pg)) as conn:
        Migrator(conn, migrations_dir=_migrations_dir()).apply_pending()
        ids = _seed_minimal(conn)
        with conn.cursor() as cur, pytest.raises(psycopg.errors.CheckViolation) as ei:
            cur.execute(
                "INSERT INTO library_rules "
                "(rule_id, scope_type, scope_id, name, short, severity, kind) "
                "VALUES ('TEST-002', 'project', %s, 'test', 'short', 'warn', 'mood')",
                (ids["project_id"],),
            )
        assert "library_rules_kind_enum" in str(ei.value)


def test_batches_dedupe_threshold_range(library_pg):
    import psycopg

    with psycopg.connect(_dsn(library_pg)) as conn:
        Migrator(conn, migrations_dir=_migrations_dir()).apply_pending()
        ids = _seed_minimal(conn)
        with conn.cursor() as cur, pytest.raises(psycopg.errors.CheckViolation) as ei:
            cur.execute(
                "INSERT INTO library_batches (project_id, task_id, slug, dedupe_threshold) "
                "VALUES (%s, %s, 'B-x', 9)",
                (ids["project_id"], ids["task_id"]),
            )
        assert "library_batches_dedupe_threshold_range" in str(ei.value)


# ---------------------------------------------------------------------------
# library.dedupe_check
# ---------------------------------------------------------------------------


def _seed_card(conn, batch_id, slug, signature, status="promoted"):  # noqa: ANN001
    with conn.cursor() as cur:
        cur.execute(
            "INSERT INTO library_entries (avatar_slug, title, batch_id, status, "
            "                             dedupe_signature, compatibility_signature) "
            "VALUES ('aeri', %s, %s, %s, %s, '') RETURNING id",
            (slug, batch_id, status, signature),
        )
        return cur.fetchone()[0]


def test_dedupe_check_returns_overlap_at_threshold(library_pg):
    """3 cards with engineered signatures; threshold=6 returns the
    candidates that overlap on >= 6 axes."""
    import psycopg

    with psycopg.connect(_dsn(library_pg)) as conn:
        Migrator(conn, migrations_dir=_migrations_dir()).apply_pending()
        ids = _seed_minimal(conn)

        # Already-seeded card has signature:
        #   pussy|standing|frontal|robe-open|bed-edge|hotel|eye-level|warm
        # Add 3 more cards with controlled overlap.
        match_7 = "pussy|standing|frontal|robe-open|bed-edge|hotel|eye-level|cool"   # 7/8
        match_5 = "pussy|standing|frontal|robe-open|bed-edge|park|low-angle|cool"    # 5/8
        match_8 = "pussy|standing|frontal|robe-open|bed-edge|hotel|eye-level|warm"   # 8/8
        c7 = _seed_card(conn, ids["batch_id"], "C7", match_7, status="promoted")
        _ = _seed_card(conn, ids["batch_id"], "C5", match_5, status="promoted")
        c8 = _seed_card(conn, ids["batch_id"], "C8", match_8, status="soft_accepted")
        # Original card is still 'pending'; should be excluded by status filter.
        # Add an 'abandoned' card with full overlap to confirm exclusion.
        _ = _seed_card(
            conn, ids["batch_id"], "C-abandoned", match_8, status="abandoned"
        )

        new_signature = "pussy|standing|frontal|robe-open|bed-edge|hotel|eye-level|warm"
        with conn.cursor() as cur:
            cur.execute(
                "SELECT candidate_id, candidate_slug, overlap_count "
                "FROM library.dedupe_check(%s, %s, 6) "
                "ORDER BY overlap_count DESC, candidate_slug",
                (ids["project_id"], new_signature),
            )
            rows = cur.fetchall()

    # Expected: C8 (overlap 8) and C7 (overlap 7); C5 (5) below threshold;
    # 'pending' and 'abandoned' rows excluded by status filter.
    candidates = {r[1]: r[2] for r in rows}
    assert candidates == {"C8": 8, "C7": 7}


def test_dedupe_check_higher_threshold_filters_out_partial_match(library_pg):
    import psycopg

    with psycopg.connect(_dsn(library_pg)) as conn:
        Migrator(conn, migrations_dir=_migrations_dir()).apply_pending()
        ids = _seed_minimal(conn)
        match_7 = "pussy|standing|frontal|robe-open|bed-edge|hotel|eye-level|cool"
        _ = _seed_card(conn, ids["batch_id"], "C7", match_7, status="promoted")

        new_signature = "pussy|standing|frontal|robe-open|bed-edge|hotel|eye-level|warm"
        with conn.cursor() as cur:
            cur.execute(
                "SELECT candidate_slug FROM library.dedupe_check(%s, %s, 8)",
                (ids["project_id"], new_signature),
            )
            rows = cur.fetchall()
        assert rows == [], "threshold=8 must reject the 7/8-overlap candidate"


def test_dedupe_check_excludes_other_projects(library_pg):
    """Same signature in a different project must not be returned."""
    import psycopg

    with psycopg.connect(_dsn(library_pg)) as conn:
        Migrator(conn, migrations_dir=_migrations_dir()).apply_pending()
        ids = _seed_minimal(conn)

        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO library_projects (slug, name, owner_slug) "
                "VALUES ('other-project', 'Other', 'op2') RETURNING id"
            )
            other_project_id = cur.fetchone()[0]
            cur.execute(
                "INSERT INTO library_tasks (project_id, slug, intake_dir) "
                "VALUES (%s, 'T-X', 'tx/') RETURNING id",
                (other_project_id,),
            )
            other_task_id = cur.fetchone()[0]
            cur.execute(
                "INSERT INTO library_batches (project_id, task_id, slug) "
                "VALUES (%s, %s, 'B-X') RETURNING id",
                (other_project_id, other_task_id),
            )
            other_batch_id = cur.fetchone()[0]
        _ = _seed_card(
            conn,
            other_batch_id,
            "C-other",
            "pussy|standing|frontal|robe-open|bed-edge|hotel|eye-level|warm",
            status="promoted",
        )

        new_signature = "pussy|standing|frontal|robe-open|bed-edge|hotel|eye-level|warm"
        with conn.cursor() as cur:
            cur.execute(
                "SELECT candidate_slug FROM library.dedupe_check(%s, %s, 6)",
                (ids["project_id"], new_signature),
            )
            rows = cur.fetchall()
        assert rows == []


# ---------------------------------------------------------------------------
# library_target_card_counts view
# ---------------------------------------------------------------------------


def test_target_card_counts_aggregates_all_seven_status_values(library_pg):
    """Synthetic outputs across all 7 status enum values; view returns
    accurate per-status counts for the matching target card."""
    import psycopg

    with psycopg.connect(_dsn(library_pg)) as conn:
        Migrator(conn, migrations_dir=_migrations_dir()).apply_pending()
        ids = _seed_minimal(conn)

        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO library_target_groups "
                "(project_id, group_slug, group_name, expected_card_count, target_per_card) "
                "VALUES (%s, 'SF', 'Standing frontal', 20, 8) RETURNING id",
                (ids["project_id"],),
            )
            group_id = cur.fetchone()[0]
            cur.execute(
                "INSERT INTO library_target_cards "
                "(group_id, card_slug, card_id, target_promoted) "
                "VALUES (%s, 'SF-15', %s, 8) RETURNING id",
                (group_id, ids["card_id"]),
            )
            target_card_id = cur.fetchone()[0]
        conn.commit()

        # 1 pending, 2 triaging, 1 soft_accepted, 3 promoted, 4 rejected,
        # 5 diagnostic, 0 abandoned = 16 outputs total.
        plan = [
            ("pending",       None, 1),
            ("triaging",      None, 2),
            ("soft_accepted", None, 1),
            ("promoted",      "op", 3),
            ("rejected",      None, 4),
            ("diagnostic",    None, 5),
        ]
        suffix = 0
        for status, finalized_by, n in plan:
            for _i in range(n):
                _seed_output(
                    conn, ids, status=status, finalized_by=finalized_by,
                    suffix=f"{status[:3]}{suffix}",
                )
                suffix += 1

        with conn.cursor() as cur:
            cur.execute(
                "SELECT pending_count, triaging_count, soft_accepted_count, "
                "       promoted_count, rejected_count, diagnostic_count, "
                "       abandoned_count "
                "FROM library_target_card_counts WHERE target_card_id = %s",
                (target_card_id,),
            )
            row = cur.fetchone()

    assert row == (1, 2, 1, 3, 4, 5, 0)


def test_target_card_counts_empty_card_returns_zeros(library_pg):
    """A target card with no matching outputs reports zero on every status."""
    import psycopg

    with psycopg.connect(_dsn(library_pg)) as conn:
        Migrator(conn, migrations_dir=_migrations_dir()).apply_pending()
        ids = _seed_minimal(conn)

        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO library_target_groups "
                "(project_id, group_slug, group_name, expected_card_count, target_per_card) "
                "VALUES (%s, 'SF', 'Standing frontal', 20, 8) RETURNING id",
                (ids["project_id"],),
            )
            group_id = cur.fetchone()[0]
            cur.execute(
                "INSERT INTO library_target_cards "
                "(group_id, card_slug, target_promoted) "
                "VALUES (%s, 'SF-99', 8) RETURNING id",
                (group_id,),
            )
            target_card_id = cur.fetchone()[0]
            cur.execute(
                "SELECT pending_count, triaging_count, soft_accepted_count, "
                "       promoted_count, rejected_count, diagnostic_count, "
                "       abandoned_count "
                "FROM library_target_card_counts WHERE target_card_id = %s",
                (target_card_id,),
            )
            row = cur.fetchone()

    assert row == (0, 0, 0, 0, 0, 0, 0)
