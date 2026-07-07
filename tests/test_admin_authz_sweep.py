# synthetic-test-data
"""Router-wide admin authorization sweep (E-254-05).

Enumerates every route on ``reports_admin.router`` via introspection (NOT a
hand-maintained list) and asserts, through the full middleware stack, that:

- unauthenticated requests are redirected to login (302);
- authenticated NON-admin sessions are denied (403) -- POSTs carry a valid CSRF
  token so the 403 attributes to the ADMIN gate, not the CSRF gate;
- an authenticated ADMIN session (positive control) gets the route's EXPECTED
  success status (303 for the mutation-redirect routes, 200 for GET routes),
  using fixture-backed EXISTING ids so ``{user_id}``/``{report_id}`` resolve
  (an arbitrary dummy id would 404 after the gate passes and satisfy
  "not 403" vacuously).

Because the sweep enumerates ``router.routes``, a future admin route added
without ``_require_admin`` fails the non-admin 403 assertion (and a route not yet
registered in ``_ROUTE_SPECS`` fails the coverage assertion) -- a standing
regression guard, not a one-time fix. See Technical Notes TN-9.
"""

from __future__ import annotations

import secrets
import sqlite3
import sys
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

# ---------------------------------------------------------------------------
# Path setup
# ---------------------------------------------------------------------------

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from migrations.apply_migrations import run_migrations  # noqa: E402
from src.api.auth import hash_token  # noqa: E402
from src.api.main import app  # noqa: E402
from src.api.routes import reports_admin  # noqa: E402

_CSRF = "test-csrf-token"


# ---------------------------------------------------------------------------
# Route introspection + per-route specs
# ---------------------------------------------------------------------------


# Methods the sweep knows how to exercise. GET is a plain read; every other
# entry is treated as state-changing (valid CSRF + expected mutation status).
# A discovered route whose method is OUTSIDE this set fails the coverage test
# loudly (fail-closed) -- extend the sweep before adding such a route so the
# non-admin->403 guard stays method-complete (E-254-05 AC-5).
_SWEEP_HANDLED_METHODS = frozenset({"GET", "POST", "PUT", "PATCH", "DELETE"})

# Preference order for choosing a route's primary method when it declares more
# than one real (non-HEAD/OPTIONS) method: a state-changing verb wins over GET
# so the route is swept as a mutation, not a read.
_METHOD_PRIORITY = ("DELETE", "PATCH", "PUT", "POST", "GET")


def _discover_admin_routes() -> list[tuple[str, str, str]]:
    """Enumerate (method, path, name) for each admin route via introspection.

    Reads ``reports_admin.router.routes`` so a newly-added route is covered
    automatically (AC-1). Only the auto-added HEAD/OPTIONS methods are dropped;
    EVERY real HTTP method is surfaced (NOT just GET/POST) so a route registered
    as PUT/PATCH/DELETE cannot silently escape the sweep -- the coverage test
    then rejects any method the sweep does not handle (fail-closed, AC-5).
    """
    discovered: list[tuple[str, str, str]] = []
    for route in reports_admin.router.routes:
        methods = {m for m in route.methods if m not in ("HEAD", "OPTIONS")}
        if not methods:
            continue
        method = next((m for m in _METHOD_PRIORITY if m in methods), sorted(methods)[0])
        discovered.append((method, route.path, route.name))
    return discovered


_DISCOVERED = _discover_admin_routes()

# Per-route metadata for the admin positive control and for supplying minimal
# valid POST bodies so each route MATCHES its handler (FastAPI validates Form
# params before the handler runs, so a missing required field would 422 before
# the admin gate). Keyed by (method, path). `id_param` names the path parameter
# to substitute with a fixture-backed existing id for the admin control.
_ROUTE_SPECS: dict[tuple[str, str], dict] = {
    ("GET", "/admin/users"): {"admin_status": 200},
    ("POST", "/admin/users"): {
        "admin_status": 303,
        "form": {"email": "swept-new-user@example.com"},
    },
    ("GET", "/admin/users/{user_id}/edit"): {"admin_status": 200, "id_param": "user_id"},
    ("POST", "/admin/users/{user_id}/edit"): {
        "admin_status": 303,
        "id_param": "user_id",
        "form": {"role": "user"},
    },
    ("POST", "/admin/users/{user_id}/delete"): {"admin_status": 303, "id_param": "user_id"},
    ("GET", "/admin/reports"): {"admin_status": 200},
    ("POST", "/admin/reports/generate"): {
        "admin_status": 303,
        "form": {"gc_url": "https://web.gc.com/teams/abc123/test"},
        "mock_generate": True,
    },
    ("POST", "/admin/reports/{report_id}/delete"): {"admin_status": 303, "id_param": "report_id"},
}


def _params() -> list:
    return [
        pytest.param(method, path, id=f"{method} {path}")
        for (method, path, _name) in _DISCOVERED
    ]


def _substitute(path: str, id_param: str | None, id_value: object) -> str:
    if id_param:
        return path.replace("{" + id_param + "}", str(id_value))
    # Any remaining path param (unknown route) -> a dummy integer so it matches.
    return path


def _exercise(client: TestClient, method: str, url: str, form: dict) -> object:
    """Issue the request at the given method through the middleware stack.

    GET is a plain read; every other (state-changing) method carries the CSRF
    cookie/field so a resulting 403 attributes to the ADMIN gate, not CSRF.
    """
    if method == "GET":
        return client.get(url, follow_redirects=False)
    data = dict(form)
    data["csrf_token"] = _CSRF
    return client.request(method, url, data=data, follow_redirects=False)


# ---------------------------------------------------------------------------
# Seeded auth environment: admin + non-admin sessions, a target user, a report
# ---------------------------------------------------------------------------


class _Env:
    def __init__(
        self,
        db_path: Path,
        admin_token: str,
        nonadmin_token: str,
        target_user_id: int,
        report_id: int,
    ) -> None:
        self.db_path = db_path
        self.admin_token = admin_token
        self.nonadmin_token = nonadmin_token
        self.target_user_id = target_user_id
        self.report_id = report_id


def _insert_user(conn: sqlite3.Connection, email: str, role: str) -> int:
    cur = conn.execute(
        "INSERT INTO users (email, role, hashed_password) VALUES (?, ?, '')",
        (email, role),
    )
    return int(cur.lastrowid)


def _insert_session(conn: sqlite3.Connection, user_id: int) -> str:
    raw_token = secrets.token_hex(32)
    conn.execute(
        "INSERT INTO sessions (session_id, user_id, expires_at) "
        "VALUES (?, ?, datetime('now', '+7 days'))",
        (hash_token(raw_token), user_id),
    )
    return raw_token


@pytest.fixture()
def env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> _Env:
    """Fresh DB (function-scoped so mutation controls do not cross-contaminate)
    with an admin session, a non-admin session, a distinct target user, and a
    ready report -- routed to via DATABASE_PATH so every get_connection() lands
    here. ADMIN_EMAIL / DEV_USER_EMAIL are cleared so admin-ness comes solely
    from the DB role and non-admins are genuinely denied.
    """
    db_path = tmp_path / "sweep.db"
    run_migrations(db_path=db_path)
    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA foreign_keys=ON;")
    admin_id = _insert_user(conn, "sweep-admin@example.com", "admin")
    nonadmin_id = _insert_user(conn, "sweep-nonadmin@example.com", "user")
    target_id = _insert_user(conn, "sweep-target@example.com", "user")
    admin_token = _insert_session(conn, admin_id)
    nonadmin_token = _insert_session(conn, nonadmin_id)
    team_cur = conn.execute(
        "INSERT INTO teams (name, membership_type) VALUES ('Sweep Team', 'tracked')"
    )
    team_id = int(team_cur.lastrowid)
    report_cur = conn.execute(
        "INSERT INTO reports (slug, team_id, title, status, generated_at, expires_at, report_path) "
        "VALUES ('sweep-report', ?, 'Sweep Report', 'ready', "
        "datetime('now'), datetime('now', '+14 days'), 'reports/sweep-nonexistent.html')",
        (team_id,),
    )
    report_id = int(report_cur.lastrowid)
    conn.commit()
    conn.close()

    monkeypatch.setenv("DATABASE_PATH", str(db_path))
    monkeypatch.delenv("ADMIN_EMAIL", raising=False)
    monkeypatch.delenv("DEV_USER_EMAIL", raising=False)
    return _Env(db_path, admin_token, nonadmin_token, target_id, report_id)


# ---------------------------------------------------------------------------
# AC-1 / AC-5: every discovered route is covered by the sweep specs
# ---------------------------------------------------------------------------


def test_sweep_covers_every_admin_route() -> None:
    """AC-1/AC-5: every route on reports_admin.router is registered in the sweep
    specs. A newly-added admin route lands here first, forcing it into the
    non-admin 403 sweep (so an unguarded new route cannot slip through)."""
    assert _DISCOVERED, "no admin routes discovered -- introspection broke"
    # Fail-closed method completeness: a route whose method the sweep does not
    # know how to exercise (e.g. a novel verb) must fail LOUDLY here rather than
    # be silently skipped -- otherwise it could ship without _require_admin and
    # escape the non-admin->403 guard. Extend _SWEEP_HANDLED_METHODS (and the
    # dispatch) before adding such a route.
    unhandled = [
        (method, path)
        for (method, path, _name) in _DISCOVERED
        if method not in _SWEEP_HANDLED_METHODS
    ]
    assert not unhandled, (
        f"admin routes use methods the sweep does not exercise: {unhandled}. "
        f"Extend _SWEEP_HANDLED_METHODS/dispatch so they are swept for 403."
    )
    missing = [
        (method, path)
        for (method, path, _name) in _DISCOVERED
        if (method, path) not in _ROUTE_SPECS
    ]
    assert not missing, (
        f"admin routes not covered by the authz sweep specs: {missing}. "
        "Add each to _ROUTE_SPECS (and ensure the handler calls _require_admin)."
    )


# ---------------------------------------------------------------------------
# AC-2: unauthenticated -> 302 redirect to login
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(("method", "path"), _params())
def test_unauthenticated_redirects_to_login(env: _Env, method: str, path: str) -> None:
    """AC-2: every admin route redirects an unauthenticated caller to login."""
    spec = _ROUTE_SPECS.get((method, path))
    assert spec is not None, f"no spec for {method} {path}"
    url = _substitute(path, spec.get("id_param"), 1)

    # csrf cookie/field present so a state-changing method passes CSRF and reaches
    # SessionMiddleware, which issues the 302 (no session) rather than a CSRF 403.
    with TestClient(app, cookies={"csrf_token": _CSRF}) as client:
        resp = _exercise(client, method, url, spec.get("form", {}))

    assert resp.status_code == 302
    assert resp.headers["location"] == "/auth/login"


# ---------------------------------------------------------------------------
# AC-3: authenticated non-admin -> 403 (the admin gate, not CSRF)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(("method", "path"), _params())
def test_non_admin_forbidden(env: _Env, method: str, path: str) -> None:
    """AC-3: every admin route denies an authenticated non-admin with 403."""
    spec = _ROUTE_SPECS.get((method, path))
    assert spec is not None, f"no spec for {method} {path}"
    url = _substitute(path, spec.get("id_param"), 1)

    cookies = {"session": env.nonadmin_token, "csrf_token": _CSRF}
    with TestClient(app, cookies=cookies) as client:
        resp = _exercise(client, method, url, spec.get("form", {}))

    assert resp.status_code == 403, (
        f"{method} {path} returned {resp.status_code}, not 403 -- is _require_admin "
        "guarding this route?"
    )


# ---------------------------------------------------------------------------
# AC-4 / AC-4a: authenticated admin positive control -> expected success status
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(("method", "path"), _params())
def test_admin_gets_expected_success(env: _Env, method: str, path: str) -> None:
    """AC-4: an admin session gets the route's EXPECTED success status (303 for
    mutation-redirects, 200 for GETs), using fixture-backed existing ids so the
    handler resolves them (not a vacuous 404). AC-4a: the generate control mocks
    the background generate_report so no live crawl fires."""
    spec = _ROUTE_SPECS.get((method, path))
    assert spec is not None, f"no spec for {method} {path}"

    id_param = spec.get("id_param")
    if id_param == "user_id":
        id_value: object = env.target_user_id
    elif id_param == "report_id":
        id_value = env.report_id
    else:
        id_value = 1
    url = _substitute(path, id_param, id_value)

    cookies = {"session": env.admin_token, "csrf_token": _CSRF}
    with TestClient(app, cookies=cookies) as client:
        if spec.get("mock_generate"):
            # AC-4a: mock the report-generation entrypoint so the 303 is asserted
            # without a live GameChanger crawl (BackgroundTasks run after the
            # response under TestClient).
            with patch("src.reports.generator.generate_report"):
                resp = _exercise(client, method, url, spec.get("form", {}))
        else:
            resp = _exercise(client, method, url, spec.get("form", {}))

    assert resp.status_code == spec["admin_status"], (
        f"{method} {path} admin control returned {resp.status_code}, "
        f"expected {spec['admin_status']} (not 403, and not a vacuous 404)"
    )
