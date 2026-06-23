# Deploying Gym Tracker on Synology + Portainer

Portainer's web editor can't *build* an image (it has no build context), so the
flow is: **build the image once on the NAS, then deploy a stack that runs it.**
The workout spreadsheet is baked into the image, so the only thing you bind-mount
is the database folder (so it survives updates and is visible in File Station).

You handle DNS / reverse proxy; these steps just get the container running.

---

## 1. Copy the app to the NAS

Put the **contents of this `gymapp` folder** into a folder on the NAS, e.g.
`/volume1/docker/gymtracker/`, and **copy `Exercises_2.xlsx` into that same
folder** (it lives one level up in the source repo — it must sit next to the
`Dockerfile` so the build picks it up).

When done, the NAS folder should contain:

```
/volume1/docker/gymtracker/
├── Dockerfile
├── app.py
├── charts.py
├── db.py
├── seed.py
├── requirements.txt
├── Exercises_2.xlsx        ← copied in from the repo root
├── static/
└── templates/
```

Use File Station, an SMB share, or `scp`. Also create the data folder now:

```bash
mkdir -p /volume1/docker/gymtracker/data
```

---

## 2. Build the image on the NAS (one-time, via SSH)

Enable SSH on the Synology (Control Panel ▸ Terminal & SNMP ▸ Enable SSH), then:

```bash
ssh youradmin@your-nas
cd /volume1/docker/gymtracker
sudo docker build -t gymtracker:latest .
```

(`sudo docker` is correct on DSM with Container Manager.) When it finishes,
the image `gymtracker:latest` is in the local store and Portainer can see it
under **Images**.

> No SSH? Use the Git alternative at the bottom instead.

---

## 3. Generate a secret key

```bash
openssl rand -hex 32
```

Copy the output — you'll paste it as `SECRET_KEY` in the next step.

---

## 4. Deploy the stack in Portainer

1. Portainer ▸ **Stacks** ▸ **Add stack**.
2. Name it `gymtracker`.
3. Build method: **Web editor**.
4. Paste the contents of [`portainer-stack.yml`](portainer-stack.yml).
5. Edit the three values:
   - `APP_USERNAME` — your login name
   - `APP_PASSWORD` — a strong password
   - `SECRET_KEY` — the hex string from step 3
   - (optional) change the host port `8800` if it's in use.
6. **Deploy the stack.**

On first start the container creates the SQLite DB in
`/volume1/docker/gymtracker/data/gym.db` and seeds it from the spreadsheet
(8 routines, 50 exercises). Open `http://your-nas-ip:8800` and log in.

---

## Updating later

When you change the app code:

```bash
cd /volume1/docker/gymtracker        # after copying in the new files
sudo docker build -t gymtracker:latest .
```

Then in Portainer open the stack and click **Update the stack** (or **Recreate**
the container). Your database is untouched — it lives in the bind-mounted
`data/` folder, not in the image.

## Re-seeding from scratch

The app only seeds when the DB is empty. To start over, stop the stack and
delete `/volume1/docker/gymtracker/data/gym.db`, then start it again.

---

## Notes

- **Port:** the container listens on `8000`; the stack maps it to host `8800`.
  Point your reverse proxy at `8800` (or whatever you chose).
- **Permissions:** the container runs as root, so it can write to the
  bind-mounted `data/` folder without UID/GID tweaks.
- **Backups:** back up `data/gym.db` — that's your entire workout history.

---

## Alternative: no SSH — build from Git in Portainer

If you'd rather not use SSH, push this `gymapp` folder (with `Exercises_2.xlsx`
copied in next to the `Dockerfile`) to a Git repo, then:

1. Portainer ▸ Stacks ▸ Add stack ▸ **Repository**.
2. Repository URL + reference (branch), Compose path: `docker-compose.yml`.
3. In the stack's environment variables set `APP_USERNAME`, `APP_PASSWORD`,
   `SECRET_KEY`.
4. Edit `docker-compose.yml` first so it points the seed at the baked-in
   spreadsheet and uses a NAS bind-mount: set
   `GYM_XLSX_PATH: /app/Exercises_2.xlsx` and the volume to
   `/volume1/docker/gymtracker/data:/data`.

Portainer clones the repo and builds the image with full context, so the
`build:` directive works here (unlike the web editor).
