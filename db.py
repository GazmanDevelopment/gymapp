"""SQLite access helpers and schema for the gym tracker."""
import os
import sqlite3

DB_PATH = os.environ.get("GYM_DB_PATH", os.path.join(os.path.dirname(__file__), "data", "gym.db"))

SCHEMA = """
CREATE TABLE IF NOT EXISTS routine (
    id       INTEGER PRIMARY KEY AUTOINCREMENT,
    name     TEXT NOT NULL UNIQUE,
    position INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS exercise (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    routine_id   INTEGER NOT NULL REFERENCES routine(id),
    name         TEXT NOT NULL,
    notes        TEXT,
    position     INTEGER NOT NULL,
    start_weight REAL,            -- seeded starting/target weight from the spreadsheet
    pb_weight    REAL,            -- seeded personal-best weight
    pb_reps      INTEGER
);

-- One logged workout = doing one routine on one day.
CREATE TABLE IF NOT EXISTS workout (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    routine_id INTEGER NOT NULL REFERENCES routine(id),
    date       TEXT NOT NULL,     -- ISO date the workout was performed
    created_at TEXT NOT NULL      -- ISO timestamp the record was saved
);

-- One row per (exercise, set) within a workout.
CREATE TABLE IF NOT EXISTS set_log (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    workout_id  INTEGER NOT NULL REFERENCES workout(id) ON DELETE CASCADE,
    exercise_id INTEGER NOT NULL REFERENCES exercise(id),
    set_number  INTEGER NOT NULL,
    weight      REAL,
    reps        INTEGER
);

CREATE INDEX IF NOT EXISTS idx_exercise_routine ON exercise(routine_id);
CREATE INDEX IF NOT EXISTS idx_workout_routine  ON workout(routine_id);
CREATE INDEX IF NOT EXISTS idx_setlog_workout   ON set_log(workout_id);
CREATE INDEX IF NOT EXISTS idx_setlog_exercise  ON set_log(exercise_id);
"""


def get_db():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    conn = get_db()
    conn.executescript(SCHEMA)
    conn.commit()
    conn.close()


def is_seeded():
    conn = get_db()
    try:
        row = conn.execute("SELECT COUNT(*) AS n FROM routine").fetchone()
        return row["n"] > 0
    except sqlite3.OperationalError:
        return False
    finally:
        conn.close()
