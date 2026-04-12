# FRx OPS — Workforce management 

**FRx OPS** is a web application for organizations that schedule field work, assign it to staff, and track completion. This repository is a **server-rendered** implementation built with **Django 5**: HTML templates, a SQLite database in development, and **Tailwind CSS** (via CDN) for a responsive UI with a desktop sidebar and mobile bottom navigation.

The app was created as a successor to a React single-page app (`Management_sys`). It follows similar URL patterns and behavior where it makes sense, but it is a separate codebase and does not import code from that project.

---

## Who it is for

- **Organization admins** plan the calendar, see tasks by day, manage the worker roster, import schedules from spreadsheets, review a **task report** of saved work, pre-register workers with **invitation codes**, and maintain their own profile (including a photo).
- **Workers** see their tasks for a given day, browse a monthly schedule, review completed history, update their profile, and open each assignment to update **status**, **notes**, **checklist**, and **photo count**—all persisted in the database.

Access is controlled by a `Profile` role: `org_admin` or `worker`. Sign-up supports open registration or, for workers, a **registration code** issued by an admin (optionally tied to an email and/or employee ID).

---

## What the system does

- **Calendar and recurrence** — Admins create **calendar events** (title, time, location, assigned worker, recurrence, checklist, color). The app expands recurrence into **derived tasks** per day using rules aligned with the original React app.
- **Stable task identity** — Each derived occurrence has an ID of the form `{event_id}::{YYYY-MM-DD}` so the same logical task can be updated over time.
- **Persisted task state** — Workers’ progress is stored in **`TaskState`** (status, notes, checklist completion, photo count, last saved time). List views merge generated tasks with this saved state.
- **Imports** — Admins can upload **CSV** or **XLSX** files to bulk-create calendar events (OpenPyXL).
- **Worker registration** — Admins create **`WorkerInvitation`** records with a generated **invite code** and optional email/employee ID constraints; workers enter the code (and matching details) at sign-up so roster data lines up with HR records.
- **Reporting** — Admins can open a **detailed task report** with filters (date range, worker, status), pagination, and columns for activity, worker, status, checklist progress, photos, and notes.

Django’s built-in **admin site** is available at **`/django-admin/`** for staff and models. The **organization** admin UI lives under **`/admin/`** (not under `/django-admin/`) so those paths stay clear for operators.

---

## Tech stack

| Area | Choice |
|------|--------|
| Framework | Django 5 |
| Database (dev) | SQLite (`db.sqlite3`, gitignored) |
| Auth | Django sessions, `django.contrib.auth` |
| Uploads | User media (e.g. profile photos) under `media/`; import size limits in settings |
| Styling | Tailwind Play CDN, Inter font, `static/custom.css` |
| Spreadsheets | openpyxl for XLSX |

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

Open `http://127.0.0.1:8000/`. Log in or use **Sign up** as an organization admin or worker. Optional demo data:

```bash
python manage.py seed_demo
```

The project **`.gitignore`** excludes `.env`, `db.sqlite3`, `media/`, virtual environments, and other local or sensitive files. Do not commit production secrets or databases.

---

## Configuration

Settings load optional **`KEY=value`** entries from a **`.env`** file in the project root (see `.env.example`). Important variables:

- **`SECRET_KEY`** — Required.
- **`DJANGO_DEBUG`** — Defaults to on for local use; set to `False` in production.
- **`DJANGO_ALLOWED_HOSTS`** — Comma-separated hostnames when deploying.

---

## Deployment (summary)

- Set **`SECRET_KEY`**, **`DJANGO_DEBUG=False`**, and **`DJANGO_ALLOWED_HOSTS`** in the environment or a private `.env` on the server.
- Serve **static files** with `collectstatic` and your web server; serve **user uploads** from **`MEDIA_ROOT`** (not via Django in production when `DEBUG` is off).
- Prefer **PostgreSQL** (or similar) instead of SQLite when you need concurrent writes and managed backups.
- Review upload limits in settings if you import large spreadsheets.

---

## Repository layout

| Path | Role |
|------|------|
| `config/` | Django settings, root URLconf |
| `workforce/` | App: models, views, forms, import parser, recurrence and task services |
| `templates/workforce/` | Admin and worker templates |
| `templates/base_auth.html` | Login and sign-up shell |
| `static/` | Shared CSS and assets |
