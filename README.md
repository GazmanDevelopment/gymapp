# Gym Session Tracker

A small Flask web app (single login) for running your workout sessions from
`Exercises_2.xlsx`. Browse routines, see last session's weights/reps, run a
routine and log weight + reps per set. Responsive for phone and desktop.

## What's in the spreadsheet
- **8 routines** ("sessions"): Lower Body 1/2/1b/2b, Upper Body 1/2/1b/2b
- Each routine has exercises (with notes), logged as 3 sets of weight × reps
- A Personal Best sheet → shown as a PB badge per exercise

On first boot the spreadsheet is imported into SQLite. After that, all logging
goes to the database (the xlsx is only the seed).

## Run with Docker (recommended)

From this `gymapp/` folder:

```bash
# Set your real credentials first (don't keep the defaults!)
export APP_USERNAME=gareth
export APP_PASSWORD='a-strong-password'
export SECRET_KEY="$(python -c 'import secrets; print(secrets.token_hex(32))')"

docker compose up --build
```

On Windows PowerShell:

```powershell
$env:APP_USERNAME = "gareth"
$env:APP_PASSWORD = "a-strong-password"
$env:SECRET_KEY   = (python -c "import secrets; print(secrets.token_hex(32))")
docker compose up --build
```

Then open http://localhost:8000 and log in.

- The database persists in the named volume `gym-data` (survives restarts/rebuilds).
- The source spreadsheet is mounted read-only at `/seed` for the one-time seed.
- To re-seed from scratch: `docker compose down -v` (deletes the volume), then `up`.

## Run locally without Docker

```powershell
# From the project root (where the venv Scripts/ lives)
.\Scripts\python.exe -m pip install -r gymapp\requirements.txt
$env:APP_PASSWORD = "changeme"
.\Scripts\python.exe gymapp\app.py
# open http://localhost:8000
```

## Config (environment variables)
| Var | Purpose | Default |
|-----|---------|---------|
| `APP_USERNAME` | Login username | `admin` |
| `APP_PASSWORD` | Login password (hashed at startup) | `changeme` |
| `APP_PASSWORD_HASH` | Pre-hashed password (overrides `APP_PASSWORD`) | — |
| `SECRET_KEY` | Flask session signing key | dev value |
| `GYM_DB_PATH` | SQLite file path | `gymapp/data/gym.db` |
| `GYM_XLSX_PATH` | Spreadsheet to seed from | `../Exercises_2.xlsx` |
| `PORT` | Port (local run) | `8000` |
```
