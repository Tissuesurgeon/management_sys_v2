# FM OPS — Workforce management 

**FM OPS** is a web application for organizations that schedule field work, assign it to staff, and track completion. This repository is a **server-rendered** implementation built with **Django 5**: HTML templates, a SQLite database in development, and **Tailwind CSS** (via CDN) for a responsive UI with a desktop sidebar and mobile bottom navigation.

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
- **Persisted task state** — Technicians’ progress is stored in **`TaskState`** (status, notes, checklist completion, photo count, last saved time). List views merge generated tasks with this saved state.
- **Imports** — Facility managers can upload **CSV** or **XLSX** files to bulk-create calendar events (OpenPyXL).
- **Technician registration** — Facility managers create **`WorkerInvitation`** records with a generated **invite code** and optional email/employee ID/trade constraints; technicians enter the code (and matching details) at sign-up so roster data lines up with your records.
- **Reporting** — Facility managers can open a **detailed task report** with filters (date range, worker, status), pagination, and columns for activity, worker, status, checklist progress, photos, and notes.

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
