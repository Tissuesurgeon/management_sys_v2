# Pavilion management system — Workforce management 

**Pavilion management system** is a web application for organizations that schedule field work, assign it to staff, and track completion. This repository is a **server-rendered** implementation built with **Django 5**: HTML templates, **PostgreSQL when configured** (or **SQLite** in the project root when it is not), and **Tailwind CSS** (via CDN) for a responsive UI with a desktop sidebar and mobile bottom navigation.

The app was created as a successor to a React single-page app (`Management_sys`). It follows similar URL patterns and behavior where it makes sense, but it is a separate codebase and does not import code from that project.

---

## Who it is for

- **Facility managers** plan the calendar, see tasks by day, manage the technician roster, import schedules from spreadsheets, review a **task report** of saved work, pre-register field technicians with **invitation codes**, generate **password reset codes** for technicians who forgot their password, and maintain their own profile (including a photo).
- **Field technicians** (plumbers, electricians, general technicians) see their tasks for a given day, browse a monthly schedule, review completed history, update their profile, and open each assignment to update **status**, **notes**, **checklist**, and **photo count**—all persisted in the database. If they forget their password, they use **Forgot password?** on the sign-in page together with a **one-time code** from a facility manager (valid about 48 hours, single use).

Access is controlled by a `Profile` role: `org_admin` (shown in the UI as **Facility manager**) or `worker` (**Field technician**). Sign-up supports open registration or, for technicians, a **registration code** issued by a facility manager (optionally tied to an email, employee ID, and/or trade).

---

## What the system does

- **Calendar and recurrence** — Facility managers create **maintenance tasks** (title, time, location, assigned technician, recurrence, checklist, color). The app expands recurrence into **derived tasks** per day using rules aligned with the original React app.
- **Stable task identity** — Each derived occurrence has an ID of the form `{event_id}::{YYYY-MM-DD}` so the same logical task can be updated over time.
- **Persisted task state** — Workers’ progress (cleaners, trades, etc.) is stored in **`TaskState`** (status, notes, checklist completion, photo count, last saved time). List views merge generated tasks with this saved state.
- **Imports** — Facility managers can upload **CSV** or **XLSX** files to bulk-create calendar events (OpenPyXL).
- **Technician registration** — Facility managers create **`WorkerInvitation`** records with a generated **invite code** and optional email/employee ID/trade constraints; technicians enter the code (and matching details) at sign-up so roster data lines up with your records.
- **Reporting** — Facility managers can open a **detailed task report** with filters (date range, worker, status), pagination, and columns for activity, worker, status, checklist progress, photos, and notes.

Django’s built-in **admin site** is available at **`/django-admin/`** for staff and models. The **organization** admin UI lives under **`/admin/`** (not under `/django-admin/`) so those paths stay clear for operators.

---

## Tech stack

| Area | Choice |
|------|--------|
| Framework | Django 5 |
| Database | **PostgreSQL** if `DATABASE_URL` or `POSTGRES_*` is set; otherwise **SQLite** (`db.sqlite3`, gitignored) |
| Auth | Django sessions, `django.contrib.auth` |
| Uploads | User media (e.g. profile photos) under `media/`; import size limits in settings |
| Styling | Tailwind Play CDN, Inter font, `static/custom.css` |
| Spreadsheets | openpyxl for XLSX |
| Process / static (prod) | Gunicorn, WhiteNoise (`collectstatic` → `staticfiles/`) |

---

## Local setup

**1. Environment**

Copy the example env file and set a secret key (never commit `.env`):

```bash
cd management_sys_v2
cp .env.example .env
```

Generate a key and add `SECRET_KEY=...` on one line in `.env`:

```bash
python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
```

**2. Install and migrate**

```bash
python3 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python manage.py migrate
python manage.py createsuperuser   # optional; for /django-admin/
python manage.py runserver
```

**3. Use the app**

Open `http://127.0.0.1:8000/`. Log in or use **Sign up** as a facility manager or field technician, then add technicians through registration codes or open sign-up as needed.

The project **`.gitignore`** excludes `.env`, `db.sqlite3`, `media/`, virtual environments, and other local or sensitive files. Do not commit production secrets or databases.

---

## Purging technician accounts (destructive)

To remove all field technician accounts and related data in development (deletes `TaskState` rows, then all users with the technician role—which CASCADE-deletes their `Worker` rows and assigned `MaintenanceTask` rows; **facility manager accounts are kept**):

```bash
python manage.py purge_workers --yes
```

---

## Configuration

Settings load optional **`KEY=value`** entries from a **`.env`** file in the project root (see `.env.example`). Important variables:

- **`SECRET_KEY`** — Required.
- **`DJANGO_DEBUG`** — Defaults to on for local use; set to `False` in production.
- **`DJANGO_ALLOWED_HOSTS`** — Comma-separated hostnames when deploying.
- **Database** — Optional `DATABASE_URL` (e.g. `postgresql://user:pass@host:5432/dbname`) or `POSTGRES_DB` plus `POSTGRES_USER` / `POSTGRES_PASSWORD` / `POSTGRES_HOST` / `POSTGRES_PORT` (see `.env.example`). If none of these are set, the app uses **SQLite** at `db.sqlite3`.

---

## Deployment (summary)

- Set **`SECRET_KEY`**, **`DJANGO_DEBUG=False`**, and **`DJANGO_ALLOWED_HOSTS`** in the environment or a private `.env` on the server.
- Serve **static files** with `collectstatic` and your web server; serve **user uploads** from **`MEDIA_ROOT`** (not via Django in production when `DEBUG` is off).
- Use **PostgreSQL** in production (set `DATABASE_URL` or `POSTGRES_*`); **SQLite** is for quick local use when Postgres is not configured.
- Review upload limits in settings if you import large spreadsheets.

---

## Deploy on Render

[Render](https://render.com/) can run this app as a **Web Service** with **Gunicorn**, **WhiteNoise** for static assets, and a **Render PostgreSQL** database. The repo includes **`render.yaml`** (optional Blueprint) and **`runtime.txt`** (Python version).

### 1. Create a PostgreSQL database

1. In the Render dashboard: **New +** → **PostgreSQL**.
2. Choose a name, region, and instance type (see [Render Postgres](https://render.com/docs/postgresql-creating-connecting)).
3. After creation, copy the **Internal Database URL** (`postgresql://…`). You will attach it to the web service as `DATABASE_URL`.

### 2. Create the Web Service

1. **New +** → **Web Service** → connect this Git repository.
2. **Root directory**: use the repo root if `manage.py` is at the root (e.g. `management_sys_v2/` if the project lives in that folder only).
3. **Runtime**: Python.
4. **Build command**:

   ```bash
   pip install -r requirements.txt && python manage.py collectstatic --noinput
   ```

5. **Pre-deploy command** (migrations on each release):

   ```bash
   python manage.py migrate --noinput
   ```

6. **Start command**:

   ```bash
   gunicorn config.wsgi:application --bind 0.0.0.0:$PORT
   ```

7. Link the database: **Environment** → **Link database** → select the Postgres you created (Render injects **`DATABASE_URL`**).

### 3. Environment variables

Set these on the **Web Service** (not only locally):

| Variable | Example / note |
|----------|----------------|
| `SECRET_KEY` | Long random string (e.g. `python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"`). |
| `DJANGO_DEBUG` | `false` |
| `DJANGO_ALLOWED_HOSTS` | Your Render hostname only, e.g. `my-app.onrender.com` (no `https://`). |
| `DJANGO_CSRF_TRUSTED_ORIGINS` | `https://my-app.onrender.com` (matches the public URL). |
| `DJANGO_BEHIND_PROXY` | `true` (so Django trusts `X-Forwarded-Proto` from Render’s TLS terminator). |
| `DATABASE_URL` | Injected automatically when you link Postgres, or paste the **Internal Database URL**. |

`PYTHON_VERSION` is optional (defaults are fine); this project includes **`runtime.txt`** with `3.12.7`.

### 4. Superuser and media files

- Run a **shell** on the service (Render dashboard → **Shell**) and create an admin user:  
  `python manage.py createsuperuser`
- **User uploads** (profile photos, etc.) use `MEDIA_ROOT`. On Render’s ephemeral filesystem, files are lost on redeploy unless you add a [**Persistent Disk**](https://render.com/docs/disks) and set **`MEDIA_ROOT`** to the mount path (also set in Environment), or use external object storage (e.g. S3).

### 5. Optional: Blueprint

To define the web service from Git, use **`render.yaml`** at the repo root and [Render Blueprints](https://render.com/docs/infrastructure-as-code). You still need to create/link PostgreSQL and set `DJANGO_ALLOWED_HOSTS` / `DJANGO_CSRF_TRUSTED_ORIGINS` to your real hostname.

---

## Repository layout

| Path | Role |
|------|------|
| `render.yaml` | Optional [Render](https://render.com/) Blueprint (Web Service) |
| `runtime.txt` | Python version hint for Render / local |
| `config/` | Django settings, root URLconf |
| `workforce/` | App: models, views, forms, import parser, recurrence and task services |
| `templates/workforce/` | Admin and worker templates |
| `templates/base_auth.html` | Login and sign-up shell |
| `static/` | Shared CSS and assets |
