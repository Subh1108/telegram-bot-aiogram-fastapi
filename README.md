# Telegram Bot — Control Room

A full-stack Telegram bot: async Python bot (aiogram) + FastAPI backend +
a custom dark-themed web dashboard. No Node.js needed — the dashboard is
plain HTML/CSS/JS served directly by FastAPI.

## What it can do

**Bot side**
- `/start` with referral tracking (`t.me/yourbot?start=CODE`)
- Inline menu: Profile, FAQ, Support, Invite Friends, Admin Panel
- Support tickets (user messages → tracked, admin replies from dashboard or bot)
- Broadcast messages (instant or scheduled, to all/active/new users)
- Maintenance mode (blocks non-admins with a notice)

**Dashboard side** (`http://localhost:8000`)
- Overview: live stats, 14-day signup chart, live activity feed
- Broadcast composer with audience targeting + scheduling + history
- Ticket inbox with reply-from-browser
- User table with search + ban/unban
- Settings: maintenance toggle, welcome-message editor

## Setup

```bash
# 1. Create a virtual environment
python3 -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate

# 2. Install dependencies
pip install -r requirements.txt

# 3. Configure
cp .env.example .env
# then edit .env:
#   BOT_TOKEN     -> from @BotFather
#   ADMIN_IDS     -> your Telegram user ID (from @userinfobot)
#   ADMIN_PASSWORD -> dashboard login password
#   SECRET_KEY    -> any long random string

# 4. Run everything (bot + scheduler + dashboard API) in one process
python run.py
```

Then open **http://localhost:8000** for the dashboard, and message your bot on Telegram.

## How it's structured — what is what

```
config.py               -> loads all settings from .env
database/
  models.py              -> table definitions (User, SupportTicket, BroadcastLog, Setting, ActivityEvent, FAQItem)
  db.py                  -> DB engine/session + reusable queries (get_or_create_user, search_users, etc.)
bot/
  keyboards.py           -> inline button layouts
  states.py              -> multi-step conversation states (FSM) for support & broadcast flows
  middlewares.py         -> injects a DB session into every update; blocks users during maintenance mode
  services.py            -> shared logic: send_broadcast(), reply_to_ticket() — used by BOTH the bot commands
                             and the dashboard, so there's one source of truth
  scheduler.py           -> background loop that checks every 30s for scheduled broadcasts and sends them
  handlers/
    start.py             -> /start command, referral capture, main menu
    menu.py              -> profile, FAQ, invite/referral screen
    support.py           -> support ticket conversation flow
    admin.py             -> admin-only in-chat panel (stats, broadcast)
api/
  auth.py                -> dashboard login: password -> signed session token (itsdangerous)
  routes.py              -> every dashboard API endpoint (/stats, /users, /tickets, /broadcast, /settings)
  main.py                -> FastAPI app: mounts routes + serves the dashboard's static files
frontend/
  index.html             -> dashboard markup (login screen + 5 views: overview/broadcast/tickets/users/settings)
  style.css              -> dark "control room" theme (see tokens at top of file)
  app.js                 -> all dashboard behaviour: login, fetch calls to /api/*, Chart.js, polling
run.py                   -> THE entrypoint — starts the bot (polling), the scheduler, and the FastAPI
                             server together in one asyncio event loop
```

## How the pieces connect

1. `run.py` builds the aiogram `Bot`/`Dispatcher`, then stores the `bot` object on
   `app.state.bot` so the FastAPI routes (e.g. sending a broadcast from the dashboard,
   or replying to a ticket) can use the *same* bot connection to actually send messages.
2. Every Telegram update passes through `DbSessionMiddleware` (opens a DB session) and
   `MaintenanceMiddleware` (checks the `maintenance_mode` setting) before reaching a handler.
3. `bot/services.py` is the shared logic layer — both the in-chat `/broadcast` flow
   (`bot/handlers/admin.py`) and the dashboard's "Send broadcast" button
   (`api/routes.py`) call the same `send_broadcast()` function, so behavior never
   drifts between the two entry points.
4. The dashboard is a single-page app: `app.js` swaps which `<section class="view">`
   is visible and calls the matching `/api/...` endpoint — no page reloads.

## Extending it yourself

- **New bot command** → add a handler function in the right file under `bot/handlers/`,
  register it with `@router.message(Command("yourcmd"))`.
- **New dashboard page** → add a `<section id="view-x">` in `index.html`, a nav button,
  a `loadX()` function in `app.js`, and (if needed) a new route in `api/routes.py`.
- **Postgres instead of SQLite** → just change `DATABASE_URL` in `.env`
  (e.g. `postgresql+asyncpg://user:pass@host/db`) and `pip install asyncpg`.
- **Payments, AI replies, more menu items** → add new tables to `database/models.py`,
  new handlers, new API routes — the pattern is the same throughout.

## Notes

- SQLite file (`bot_database.db`) is created automatically on first run.
- The dashboard has no user accounts — it's a single shared admin password.
  Fine for one operator; for a team, extend `api/auth.py` with per-user accounts.
- Broadcasts pause briefly between sends to respect Telegram's rate limits.
