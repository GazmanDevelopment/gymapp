"""Gym session tracker — Flask web app.

Single-user login. Browse routines, view last-session weights/reps, run a
routine and log weight + reps per set.
"""
import os
from datetime import date, datetime
from functools import wraps

from flask import (
    Flask, abort, flash, g, redirect, render_template,
    request, session, url_for,
)
from werkzeug.security import check_password_hash, generate_password_hash

import charts
from db import get_db, init_db, is_seeded

app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "dev-change-me")

# --- Single-user credentials (from env) ---------------------------------
APP_USERNAME = os.environ.get("APP_USERNAME", "admin")
# Provide either APP_PASSWORD_HASH (preferred) or APP_PASSWORD (plain, hashed on boot).
_pw_hash = os.environ.get("APP_PASSWORD_HASH")
if not _pw_hash:
    _pw_hash = generate_password_hash(os.environ.get("APP_PASSWORD", "changeme"))
APP_PASSWORD_HASH = _pw_hash


# --- Request lifecycle --------------------------------------------------
@app.before_request
def _open_db():
    g.db = get_db()


@app.teardown_request
def _close_db(exc):
    db = g.pop("db", None)
    if db is not None:
        db.close()


@app.template_filter("wt")
def _fmt_weight(v):
    """Render weights without a trailing .0 (37.0 -> 37, 32.5 stays 32.5)."""
    if v is None:
        return "—"
    f = float(v)
    return str(int(f)) if f == int(f) else str(f)


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not session.get("user"):
            return redirect(url_for("login", next=request.path))
        return view(*args, **kwargs)
    return wrapped


# --- Auth ---------------------------------------------------------------
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username", "")
        password = request.form.get("password", "")
        if username == APP_USERNAME and check_password_hash(APP_PASSWORD_HASH, password):
            session["user"] = username
            nxt = request.args.get("next") or url_for("routines")
            return redirect(nxt)
        flash("Invalid username or password.")
    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


# --- Data helpers -------------------------------------------------------
def get_last_workout(routine_id, before_id=None):
    """Return (workout_row, {exercise_id: {set_number: row}}) for the most
    recent workout of a routine, or (None, {}). `before_id` excludes a workout
    (used to show 'previous' relative to the one in progress)."""
    q = "SELECT * FROM workout WHERE routine_id = ?"
    params = [routine_id]
    if before_id is not None:
        q += " AND id < ?"
        params.append(before_id)
    q += " ORDER BY date DESC, id DESC LIMIT 1"
    w = g.db.execute(q, params).fetchone()
    if not w:
        return None, {}
    rows = g.db.execute(
        "SELECT * FROM set_log WHERE workout_id = ?", (w["id"],)
    ).fetchall()
    by_ex = {}
    for r in rows:
        by_ex.setdefault(r["exercise_id"], {})[r["set_number"]] = r
    return w, by_ex


def _short_date(iso):
    """'2026-06-23' -> '06-23' (fallback to the raw value)."""
    return iso[5:] if iso and len(iso) >= 10 else iso


def routine_volume_series(routine_id):
    """Total weight lifted (Σ weight×reps) per workout for a routine, oldest first."""
    rows = g.db.execute(
        """SELECT w.id, w.date, COALESCE(SUM(s.weight * s.reps), 0) AS volume
           FROM workout w
           LEFT JOIN set_log s ON s.workout_id = w.id
                              AND s.weight IS NOT NULL AND s.reps IS NOT NULL
           WHERE w.routine_id = ?
           GROUP BY w.id
           ORDER BY w.date ASC, w.id ASC""",
        (routine_id,),
    ).fetchall()
    return [{"workout_id": r["id"], "date": r["date"], "volume": r["volume"]} for r in rows]


def exercise_volume_map(routine_id):
    """Per-exercise list of volumes per workout (oldest first) for sparklines."""
    rows = g.db.execute(
        """SELECT s.exercise_id, w.id AS wid, w.date,
                  SUM(s.weight * s.reps) AS volume
           FROM set_log s
           JOIN workout w ON w.id = s.workout_id
           WHERE w.routine_id = ?
             AND s.weight IS NOT NULL AND s.reps IS NOT NULL
           GROUP BY s.exercise_id, w.id
           ORDER BY w.date ASC, w.id ASC""",
        (routine_id,),
    ).fetchall()
    out = {}
    for r in rows:
        out.setdefault(r["exercise_id"], []).append(r["volume"])
    return out


def compute_pbs(routine_id):
    """Live PB per exercise: heaviest logged set (reps from that set), falling
    back to the seeded PB/starting weight. Returns {ex_id: {weight, reps}}."""
    pbs = {}
    # Best logged set per exercise: order by weight desc, then reps desc.
    rows = g.db.execute(
        """SELECT s.exercise_id, s.weight, s.reps
           FROM set_log s
           JOIN workout w ON w.id = s.workout_id
           WHERE w.routine_id = ? AND s.weight IS NOT NULL
           ORDER BY s.weight DESC, COALESCE(s.reps, 0) DESC""",
        (routine_id,),
    ).fetchall()
    for r in rows:
        if r["exercise_id"] not in pbs:  # first row per exercise is the best
            pbs[r["exercise_id"]] = {"weight": r["weight"], "reps": r["reps"]}

    # Fill in exercises with no logged sets from the seeded baseline.
    for ex in g.db.execute(
        "SELECT id, pb_weight, pb_reps, start_weight FROM exercise WHERE routine_id = ?",
        (routine_id,),
    ).fetchall():
        if ex["id"] not in pbs:
            base = ex["pb_weight"] if ex["pb_weight"] is not None else ex["start_weight"]
            if base is not None:
                pbs[ex["id"]] = {"weight": base, "reps": ex["pb_reps"]}
    return pbs


# --- Views --------------------------------------------------------------
@app.route("/")
@login_required
def routines():
    routines = g.db.execute("SELECT * FROM routine ORDER BY position").fetchall()
    cards = []
    for r in routines:
        n = g.db.execute(
            "SELECT COUNT(*) AS n FROM exercise WHERE routine_id = ?", (r["id"],)
        ).fetchone()["n"]
        last = g.db.execute(
            "SELECT date FROM workout WHERE routine_id = ? ORDER BY date DESC, id DESC LIMIT 1",
            (r["id"],),
        ).fetchone()
        last_date = last["date"] if last else None
        days_since = None
        if last_date:
            try:
                days_since = (date.today() - date.fromisoformat(last_date)).days
            except ValueError:
                days_since = None
        cards.append({
            "id": r["id"], "name": r["name"], "exercise_count": n,
            "last_date": last_date, "days_since": days_since,
        })
    return render_template("routines.html", cards=cards)


@app.route("/routine/<int:routine_id>")
@login_required
def routine_detail(routine_id):
    r = g.db.execute("SELECT * FROM routine WHERE id = ?", (routine_id,)).fetchone()
    if not r:
        abort(404)
    exercises = g.db.execute(
        "SELECT * FROM exercise WHERE routine_id = ? ORDER BY position", (routine_id,)
    ).fetchall()
    last_w, last_sets = get_last_workout(routine_id)

    series = routine_volume_series(routine_id)
    volume_chart = charts.line_chart(
        [(_short_date(p["date"]), p["volume"]) for p in series],
        unit="Total weight lifted (kg×reps)",
    )
    ex_vol = exercise_volume_map(routine_id)
    sparklines = {
        ex_id: charts.sparkline(vols) for ex_id, vols in ex_vol.items() if len(vols) > 1
    }
    pbs = compute_pbs(routine_id)
    return render_template(
        "routine.html", routine=r, exercises=exercises,
        last_w=last_w, last_sets=last_sets, pbs=pbs,
        volume_chart=volume_chart, sparklines=sparklines,
        has_history=bool(series),
    )


@app.route("/routine/<int:routine_id>/run", methods=["GET", "POST"])
@login_required
def run_routine(routine_id):
    r = g.db.execute("SELECT * FROM routine WHERE id = ?", (routine_id,)).fetchone()
    if not r:
        abort(404)
    exercises = g.db.execute(
        "SELECT * FROM exercise WHERE routine_id = ? ORDER BY position", (routine_id,)
    ).fetchall()

    if request.method == "POST":
        workout_date = request.form.get("date") or date.today().isoformat()
        cur = g.db.cursor()
        cur.execute(
            "INSERT INTO workout (routine_id, date, created_at) VALUES (?, ?, ?)",
            (routine_id, workout_date, datetime.now().isoformat(timespec="seconds")),
        )
        workout_id = cur.lastrowid
        saved = 0
        for ex in exercises:
            for s in (1, 2, 3):
                w = request.form.get(f"w_{ex['id']}_{s}", "").strip()
                reps = request.form.get(f"r_{ex['id']}_{s}", "").strip()
                if not w and not reps:
                    continue
                cur.execute(
                    """INSERT INTO set_log (workout_id, exercise_id, set_number, weight, reps)
                       VALUES (?, ?, ?, ?, ?)""",
                    (workout_id, ex["id"], s,
                     float(w) if w else None,
                     int(float(reps)) if reps else None),
                )
                saved += 1
        if saved == 0:
            g.db.execute("DELETE FROM workout WHERE id = ?", (workout_id,))
            g.db.commit()
            flash("Nothing logged — enter at least one weight or rep count.")
            return redirect(url_for("run_routine", routine_id=routine_id))
        g.db.commit()
        flash(f"Workout saved ({saved} sets logged).")
        return redirect(url_for("routine_detail", routine_id=routine_id))

    # GET: prefill hints come from the last workout (or seeded starting weight).
    _, last_sets = get_last_workout(routine_id)
    return render_template(
        "run.html", routine=r, exercises=exercises, pbs=compute_pbs(routine_id),
        last_sets=last_sets, today=date.today().isoformat(),
    )


@app.route("/progress")
@login_required
def progress():
    routines = g.db.execute("SELECT * FROM routine ORDER BY position").fetchall()
    blocks = []
    for r in routines:
        series = routine_volume_series(r["id"])
        if not series:
            continue
        latest = series[-1]["volume"]
        best = max(p["volume"] for p in series)
        blocks.append({
            "id": r["id"], "name": r["name"], "sessions": len(series),
            "latest": latest, "best": best,
            "chart": charts.line_chart(
                [(_short_date(p["date"]), p["volume"]) for p in series],
                unit="Total weight lifted (kg×reps)",
            ),
        })
    return render_template("progress.html", blocks=blocks)


@app.route("/history")
@login_required
def history():
    workouts = g.db.execute(
        """SELECT w.*, r.name AS routine_name
           FROM workout w JOIN routine r ON r.id = w.routine_id
           ORDER BY w.date DESC, w.id DESC LIMIT 100"""
    ).fetchall()
    return render_template("history.html", workouts=workouts)


@app.route("/workout/<int:workout_id>")
@login_required
def workout_detail(workout_id):
    w = g.db.execute(
        """SELECT w.*, r.name AS routine_name
           FROM workout w JOIN routine r ON r.id = w.routine_id
           WHERE w.id = ?""", (workout_id,)
    ).fetchone()
    if not w:
        abort(404)
    rows = g.db.execute(
        """SELECT s.*, e.name AS exercise_name, e.position AS ex_pos
           FROM set_log s JOIN exercise e ON e.id = s.exercise_id
           WHERE s.workout_id = ?
           ORDER BY e.position, s.set_number""", (workout_id,)
    ).fetchall()
    by_ex = {}
    for r in rows:
        by_ex.setdefault(r["exercise_name"], []).append(r)
    return render_template("workout.html", w=w, by_ex=by_ex)


@app.route("/workout/<int:workout_id>/delete", methods=["POST"])
@login_required
def workout_delete(workout_id):
    g.db.execute("DELETE FROM set_log WHERE workout_id = ?", (workout_id,))
    g.db.execute("DELETE FROM workout WHERE id = ?", (workout_id,))
    g.db.commit()
    flash("Workout deleted.")
    return redirect(url_for("history"))


def bootstrap():
    """Ensure schema + seed data exist before serving."""
    init_db()
    if not is_seeded():
        try:
            from seed import seed
            seed()
        except Exception as exc:  # pragma: no cover
            app.logger.warning("Seeding skipped: %s", exc)


bootstrap()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8000)), debug=True)
