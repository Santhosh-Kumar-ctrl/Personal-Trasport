# Deployment readiness review

**Date:** 2026-10-04 · **Commit reviewed:** `35bcba0` (plus uncommitted `RUN.md` change and untracked `UI.md`)
**Scope:** whole repo: FastAPI backend (12 modules), Alembic migrations, scripts, Flutter app (web + Android).

## Verdict: not ready for production yet

The product works. Every automated test, the Day-30 acceptance scenario and all bus and report
simulations pass, and the codebase is clean, modular and well documented. It is ready for a
**supervised demo or a small pilot**.

It is **not ready for a production deployment** with real students. These issues were reproduced
during this review:

1. **Every login freezes the whole API** while it checks the password: about 3 logins per second,
   and every other request (GPS, boarding, alerts) waits behind them.
2. **A bus that never starts sends a "running late" alert every 5 minutes, all day**, to every
   rider and every admin (24 alerts each in 2 simulated hours).
3. **Any student can watch any bus live and see the names of other students as they board.**
   They do this by subscribing to another route's live channel. **Anonymous reports can be traced
   back to the student.**
4. **A double tap on "Start" or "Arrived" fires the event twice** (two "bus has left" alerts to
   every rider). One driver can also end up with two trips running at once.
5. **Unsafe production defaults:** a known JWT signing secret, simulation mode on (admins can
   forge trip timestamps), CORS `*`, Android cleartext HTTP and debug signing.
6. **There is nothing to deploy with yet:** no API container or service definition, no HTTPS or
   reverse proxy setup, and no CI. The architecture requires **exactly one API process**.

Fix the blockers (B1 to B6) before go-live and the high items (H1 to H4) before scaling past a
pilot. Everything else can follow.

> **Update, same day: every finding below has been fixed** on branch `review/fixes` (uncommitted,
> for review). See [§0 Status after the fixes](#0-status-after-the-fixes) for what changed and how
> it was re-verified. The production go-live steps that need you (DNS, secrets, a signing key, a
> map-tile key, a restore drill) are listed there too.

---

## 0. Status after the fixes

Re-verified on 2026-10-04 with the same checks as the original review, plus regression tests for
every finding:

| Check | Before | After |
|---|---|---|
| Backend tests | 93 passed | ✅ **148 passed**, including a regression test for each finding |
| `flutter analyze` / `flutter test` | clean / 12 passed | ✅ clean / **21 passed** (realtime auth, token renewal, session kept on network errors, admin board debounce, error messages) |
| Migrations: fresh upgrade, `alembic check`, full round trip | ✅ | ✅. New revision `c7a1e4f2b9d6` also tested on data with two running trips for one driver (it keeps the newest) |
| Acceptance scenario, 5 `simulate_bus` runs, `simulate_reports` (model on) | ✅ | ✅ all pass; 5 of 6 report drafts now come from the model and pass the new reply guard |
| Trip that never starts, watcher run for 3 h | 24 alerts per student in 2 h | **3** per student (+5, +15, +30), **4** for admins (+60 office-only), then none |
| Double tap on Start / Arrived; two trips for one driver at once | 2 events each; 2 running trips | 1 event (second tap gets 422 / 409); 409 `already_running` |
| Student subscribes to another route | positions + 9 names | refused (`forbidden`); own route: positions, **no names** |
| Anonymous report | boarding time matched the reporter on the roster | no time, no stop: nothing to match |
| Hub broadcast while a client connects | 94/200 wrong removals | 0/200 |
| Token in access log | yes (`/ws?token=…`) | no (`WebSocket /ws`) |
| `POST /auth/login`, 20 concurrent | 2.9 req/s, p50 6.5 s | **25 req/s**, p50 0.56 s |
| `GET /health` during 40 logins | 1358 ms | 263 ms |
| `GET /dashboard/admin`, 20 concurrent | 18 req/s, p50 1051 ms | 35 req/s, p50 535 ms (with more trips in the DB) |
| Production stack (`deploy/docker-compose.prod.yml`, `localhost` names) | didn't exist | ✅ refuses to start with the example secret; with real secrets: HTTPS web app + SPA routes, `/health`, login, WebSocket through Caddy, `/docs` hidden, HTTP → HTTPS redirect, CORS only for the web origin, backup script produces a full dump |

**Not verified here:** an Android build. This machine has no Android SDK, so the release-signing
and manifest changes were checked by reading only; run `flutter build appbundle` once before release.
The opt-in screenshot goldens differ on this machine by the same amounts with and without the
changes (fonts and time-dependent data), so they were left as they are.

**What only you can do before go-live** (all described in [docs/DEPLOY.md](docs/DEPLOY.md)):
1. Point two DNS names at the VM, then fill in `deploy/.env` with real secrets (`openssl rand`).
2. Create the Android upload key and `frontend/android/key.properties`.
3. Get a map-tile key (MapTiler, Stadia or your own server) and build the apps with `TILE_URL`.
4. Install the backup cron job and **try a restore** once.
5. Add `ALLOW_SIMULATION=true` to your local `backend/.env` (it now defaults to off), or
   `demo_scenario` and `simulate_reports` stop with `403 simulation_off`.

---

## 1. What was tested and the results

| Check | Result |
|---|---|
| Backend test suite (`pytest -q`) | ✅ **93 passed** in 65 s (README and RUN.md still say 91) |
| `flutter analyze` | ✅ No issues found |
| `flutter test` | ✅ 12 passed, 1 skipped (screenshot renders are opt-in) |
| Migrations on an empty DB: `alembic upgrade head` | ✅ All 5 revisions apply |
| `alembic check` (do the models match the migrations?) | ✅ No drift |
| `alembic downgrade base` then `upgrade head` | ✅ Round trip OK |
| `python -m scripts.seed` on a fresh DB | ✅ 3 routes, 4 buses, 3 drivers, 30 students |
| `python -m scripts.demo_scenario` (Day-30 acceptance) | ✅ All 7 steps |
| `simulate_bus`: routes 14, 7 and 22; pickup and drop; board rate 0.75, 1 and 0 (5 runs) | ✅ Every stop `ARRIVED` by GPS, 2 km alerts fired, attendance matched who boarded in every run |
| `simulate_reports` with Ollama **down** (rule-based fallback) | ✅ 6/6 expected verdicts |
| `simulate_reports` with Ollama **up** (`qwen3:4b`) | ✅ 6/6 expected verdicts, about 6 s per report |
| 26 targeted probe tests, a WebSocket privacy probe, a realtime-hub probe and a load probe | ❌ Found the issues below |

All live runs used a throwaway `transit_review` database on port 8001, so the dev data was not
touched. The probe tests ran against `transit_test`, like the normal suite.

**Load probe** (local machine, 8 trips in the DB, one uvicorn process):

| Endpoint | Concurrency | Throughput | p50 | p95 |
|---|---|---|---|---|
| `GET /dashboard/admin` | 20 | 18 req/s | 1051 ms | 1557 ms |
| `GET /dashboard/student` | 30 | 38 req/s | 748 ms | 958 ms |
| `GET /dashboard/driver` | 30 | 32 req/s | 886 ms | 1212 ms |
| `GET /history/trips` | 20 | 60 req/s | 276 ms | 667 ms |
| `POST /auth/login` | 20 | **2.9 req/s** | **6488 ms** | 8301 ms |
| `GET /health` while 40 logins are in flight | 1 | | **1358 ms** | |

---

## 2. Findings summary

| ID | Severity | Finding | Reproduced | Fix status (branch `review/fixes`) |
|---|---|---|---|---|
| B1 | Blocker | Password hashing runs on the event loop, so logins stall the whole API | ✅ load probe | ✅ Fixed: bcrypt in a worker thread; login releases its DB connection first; dummy check for unknown emails |
| B2 | Blocker | The delay watcher re-alerts every 5 min with no limit (not-started and forgotten trips) | ✅ 24 alerts in 2 h | ✅ Fixed: stepped alerts 5/15/30 (+60 office-only), then silence; buses in maintenance get no trip, one `ScheduleSkipped` a day |
| B3 | Blocker | Any user can subscribe to any route or trip live channel and receive other students' names and live positions | ✅ WS probe | ✅ Fixed: topic policies (`route`, `trip`); names stripped from topic messages |
| B4 | Blocker | Anonymous reports can be traced back to the student | ✅ probe | ✅ Fixed: no boarding time, no allocated stop in anonymous analyses or views |
| B5 | Blocker | Race conditions in start and arrive: duplicate events, two trips running for one driver | ✅ probe | ✅ Fixed: row lock on every trip change + partial unique indexes |
| B6 | Blocker | Unsafe production defaults, and no deployment setup at all | Config review | ✅ Fixed: production start-up checks, simulation off by default, Dockerfile, prod compose + Caddy, backups, CI, DEPLOY.md, Android release signing, no release cleartext |
| H1 | High | The realtime hub silently drops healthy WebSocket connections | ✅ 94/200 trials | ✅ Fixed: one snapshot per broadcast, 5 s send timeout |
| H2 | High | Events are not durable: a crash or failed handler loses attendance and notifications for good | Code review | ✅ Fixed for attendance (repair job every 5 min); other alerts can still be lost on a crash (documented; a full outbox was out of scope) |
| H3 | High | The admin board refetches the full dashboard on every GPS fix, and dashboards do one query per trip | ✅ load probe | ✅ Fixed: board ignores GPS + 2 s debounce; batched queries in dashboards and `GET /reports` |
| H4 | High | Report agent: "800m" makes the analysis fail; "keep in touch" is flagged CRITICAL | ✅ probe | ✅ Fixed: minutes-only regex + 600 cap; whole-phrase critical words; reply guard |
| M1 | Medium | Several inputs cause 500 errors (explicit nulls, duplicate roll no, negative paging, timestamps without a timezone) | ✅ probe | ✅ Fixed: 422 / 409 instead |
| M2 | Medium | Token handling: JWT logged in access logs, no revocation, client logs out on any network error | ✅ log | ✅ Fixed: token in first WS frame; `token_version` revocation; logout only on 401; encrypted storage on Android |
| M3 | Medium | No rate limiting (login brute force, report spam floods the AI queue) | Code review | ✅ Fixed: 10 logins/min per IP + email; 5 reports/h per student |
| M4 | Medium | A driver can start a trip scheduled for another day | ✅ probe | ✅ Fixed: 422 `wrong_day` |
| M5 | Medium | Cancelling a running trip never writes attendance for students who boarded | ✅ probe | ✅ Fixed |
| M6 | Medium | Deactivated students keep their allocation and seat | ✅ probe | ✅ Fixed; last active admin can't be deactivated |
| M7 | Medium | Release web builds show a "paste the code" box, which makes remote boarding easy | Code review | ✅ Fixed: debug builds only |
| M8 | Medium | Editing a schedule doesn't update today's already-generated trip | ✅ probe | ✅ Fixed (time, bus, driver). Deactivating a schedule still keeps an already-generated trip: that's how one-off runs are made |
| L1 to L10 | Low | See section 5 | | ✅ All fixed (L5 docs, L6 +9 Flutter tests, L9 13 packages upgraded; the rest are held back upstream) |

---

## 3. Blockers

### B1. Login freezes the whole API (bcrypt on the event loop)
- **Where:** [security.py:14-22](backend/app/core/security.py#L14-L22). It is called from async code
  at [auth/service.py:31](backend/app/modules/auth/service.py#L31), `:142` and `:168`.
- **What happens:** `bcrypt.checkpw` and `bcrypt.hashpw` with 12 rounds take about 250 to 300 ms
  of CPU each. They run synchronously inside `async def` handlers, so the single event loop is
  blocked for that time. Nothing else is served meanwhile: GPS ingest, boarding, WebSocket
  pushes, the delay watcher.
- **Measured:** 2.9 logins/s with a p50 of 6.5 s. `/health` took 1.36 s while 40 logins were in flight.
- **Impact:** the morning rush (students opening the app around 7:00 to 7:30) or a first-day
  login wave stalls the platform for everyone, including drivers' GPS.
- **Fix:** `await asyncio.to_thread(bcrypt.checkpw, ...)` (or Starlette's `run_in_threadpool`) for
  hashing and verification. Also always run a dummy `checkpw` when the email is unknown, so login
  time doesn't reveal which emails exist.

### B2. Alert storm: the delay watcher escalates every threshold, forever
- **Where:** [delay_monitor/service.py:85-88](backend/app/modules/delay_monitor/service.py#L85-L88)
  (`escalated = observed_delay - last_delay >= threshold`) together with the watcher at
  [:138-154](backend/app/modules/delay_monitor/service.py#L138-L154).
- **What happens:** for a trip that is still `scheduled` after its departure, a new
  `TripDelayed` is raised every `DELAY_THRESHOLD_MIN` (5) minutes for the rest of the day. Each
  one notifies every allocated rider, every admin and the driver. The same happens to a running
  trip whose next stop never gets checked in (GPS off and the driver forgot to tap), until the
  stale-trip closer runs after midnight. Trips whose bus is in maintenance are still generated
  ([trips/service.py:173-186](backend/app/modules/trips/service.py#L173-L186)) and can never
  start, so they always end up in this state.
- **Measured:** a trip that never started, with the watcher simulated for 2 hours, sent
  **24 `TripDelayed` notifications to the student and 24 to the admin**. A full day is about 150 each.
- **Fix:** cap escalations. For example, alert at +5, +15, +30 and +60 minutes, then stop telling
  students and leave one standing admin alert. Don't generate trips for buses that aren't
  `active`, or raise a single "trip can't run" alert for them.

### B3. Live channels have no access control: any student sees every bus and other students' names
- **Where:** `subscribe` accepts any topic string
  ([realtime.py:109-110](backend/app/core/realtime.py#L109-L110)). Route topics receive full
  event payloads ([dashboard/\_\_init\_\_.py:21-22](backend/app/modules/dashboard/__init__.py#L21-L22)),
  including `StudentBoarded` and `UnallocatedBoarding` with `student_id` and `student_name`. Trip
  topics also get boarding names
  ([boarding/\_\_init\_\_.py:17](backend/app/modules/boarding/__init__.py#L17)), and route topics
  get every GPS fix ([tracking/service.py:140](backend/app/modules/tracking/service.py#L140)).
- **Measured:** `student1` (route 14) subscribed to `route:2` (route 7) during a run. They received
  57 live positions of that bus and **the names of all 9 students who boarded it**. A student's
  own app already subscribes to its route, so every rider sees the names of everyone boarding
  their bus.
- **Impact:** a privacy leak about minors and young adults: who is on which bus, when, and where
  it is. It matters most for the safety and harassment reporting the product offers.
- **Fix:** authorise subscriptions in `websocket_endpoint`. Students may only subscribe to
  `route:{their allocated route}` and to trips on it; drivers to their own trips; admins to
  anything. Strip `student_id` and `student_name` from anything sent to route or trip topics
  (send `boarded_count` only); the driver and admins already get named events through their own
  channels.

### B4. Anonymous reports can be traced back to the student
- **Where:** [reports/evidence.py:91-92](backend/app/modules/reports/evidence.py#L91-L92). The
  `on_this_trip` finding stores the reporter's exact `boarded_at` time. Admins see it in the
  analysis, and the trip roster shows every student's `boarded_at`.
- **Measured:** three students boarded and one filed an anonymous safety report. The analysis said
  "The student boarded this trip at 21:30". Matching that time against the roster identified the
  reporter, with the correct id.
- **Impact:** students who use "anonymous" for harassment or conduct reports about a driver or
  staff member are identifiable. The admin view also shows the reporter's allocated stop.
- **Fix:** for anonymous reports, reduce the finding to "a rider on this trip" with no time, leave
  out `numbers.boarded_at`, and hide `stop_name`. Add a test that the analysis of an anonymous
  report contains no reporter-specific timestamps.

### B5. Race conditions in the trip workflow
- **Where:** `start_trip`, `arrive_at_stop` and `end_trip` read the state and then write it with
  no row lock ([trips/service.py:313-388](backend/app/modules/trips/service.py#L313-L388)). The
  "driver or bus already running" rule is a plain `SELECT`
  ([:324-331](backend/app/modules/trips/service.py#L324-L331)) with no database constraint
  behind it. GPS ingest takes `FOR UPDATE` on the trip, but a manual tap doesn't, so a tap and a
  GPS arrival can also collide.
- **Measured** (two concurrent requests, like a driver's double tap or a retry on a slow network):
  - start the same trip twice: **200 and 200**, and **2 `TripStarted` events**, so every rider gets
    "bus has left" twice;
  - arrive at the same stop twice: **200 and 200**, and **2 `StopArrived` events**;
  - one driver starts two different trips at once: **both in progress**.
- **Fix:** `SELECT ... FOR UPDATE` on the trip row at the start of start, arrive, end and cancel
  (the same pattern as `tracking.ingest`). Add partial unique indexes
  `ON trips (driver_id) WHERE status = 'in_progress'` and the same on `bus_id`, and map the
  `IntegrityError` to the existing `already_running` 409.

### B6. Unsafe defaults and no deployment setup
**Defaults that are unsafe if an `.env` value is missed**
([config.py](backend/app/core/config.py)):

| Setting | Default | Risk |
|---|---|---|
| `JWT_SECRET` | `dev-secret-change-me-...` (line 12) | Anyone who reads the repo can mint admin tokens. The app should **refuse to start** with the default outside dev. |
| `ALLOW_SIMULATION` | `True` (line 36) | Admins can post explicit `started_at` and `arrived_at` times (forging delay and attendance history) and post GPS for any bus. Must be `false` in production. Default it to `False`. |
| `CORS_ORIGINS` | `*` (line 49) | Set to the real web app origin. |
| `/docs` and `/openapi.json` | public | Fine for a pilot. Consider disabling them in production. |

**Android:** `usesCleartextTraffic="true"`
([AndroidManifest.xml:19](frontend/android/app/src/main/AndroidManifest.xml#L19)), and release
builds are signed with the **debug key**
([build.gradle.kts:36](frontend/android/app/build.gradle.kts#L36)), so they can't go on the
Play Store. Map tiles default to the public OSM server, which isn't allowed for production
traffic; set `TILE_URL`. The web `manifest.json` and `index.html` still say "A new Flutter
project." and use Flutter's default blue.

**No deployment setup exists in the repo.** `docker-compose.yml` only runs Postgres. Missing:
- an API container or service definition and a process manager;
- a reverse proxy with **TLS** and WebSocket upgrade;
- secrets handling, database backups, log shipping and monitoring;
- a CI pipeline (no `.github/` or other CI config).

`/health` doesn't check the database.

**Single-process constraint.** The WebSocket hub, the event bus and the background jobs are all
in-memory, per process ([realtime.py:14](backend/app/core/realtime.py#L14)). Running
`--workers 2` or two containers would:
- run the delay watcher, trip generator and report analyser twice;
- deliver pushes only to clients on the same worker.

Deploy with **exactly one uvicorn worker** until the hub and events move to Redis or Postgres
`LISTEN/NOTIFY`, and write this down in the deployment docs.

**Ollama** must run on a host the API can reach. The fallback rules work, but the server sizing
(about 3 GB of models, CPU or GPU) is not documented for production.

---

## 4. High

### H1. The realtime hub silently drops healthy connections
- **Where:** [realtime.py:61-70](backend/app/core/realtime.py#L61-L70). `_send` gathers sends over
  `list(sockets)` and then zips the results with a **second** `list(sockets)` of the *live* set.
  If a client connects or disconnects during the `await`, the lists differ: a dead socket is kept
  and a healthy one is removed.
- **Measured:** 94 of 200 simulated broadcasts removed the wrong socket.
- **Impact:** the removed client still answers pings, so the app never reconnects. It just stops
  receiving alerts and live updates. An admin board or a student's alerts go quiet with no error.
- **Fix:** `targets = list(sockets)` once, then gather over `targets` and zip with `targets`. Also
  add a send timeout so one slow client can't stall a broadcast.

### H2. Events are not durable
- **Where:** [events.py:138-157](backend/app/core/events.py#L138-L157). Subscribers run as
  fire-and-forget tasks after commit. If the process restarts between the commit and the
  handler, or a handler fails (DB blip, bug), the side effect is lost for good. Only the reports
  analyser has a retry loop.
- **Impact:** attendance is never written for a trip
  ([boarding/\_\_init\_\_.py:28](backend/app/modules/boarding/__init__.py#L28) is the only
  trigger). Delay alerts, approach alerts and allocation notices can also be dropped. A deploy
  during the morning run is enough to cause this.
- **Fix (smallest first):** a periodic reconciler that finalises attendance for `completed` trips
  that have no attendance rows. Longer term, a transactional outbox: dispatch from
  `domain_events` with a `processed_at` column.

### H3. Load from live refreshes, and one query per trip in dashboards
- **Where:** the admin board invalidates the whole dashboard on **every** live message with no
  filter ([admin_board_screen.dart:45](frontend/lib/modules/dashboard/screens/admin_board_screen.dart#L45)).
  Every GPS fix of every bus is pushed to all admins
  ([tracking/service.py:141](backend/app/modules/tracking/service.py#L141)). The dashboard then
  runs 2 or more queries per trip ([dashboard/service.py:59-76](backend/app/modules/dashboard/service.py#L59-L76)),
  plus one query per route for utilisation.
- **Measured:** the admin dashboard does 18 req/s at a p50 of about 1 s with only 8 trips today.
  With 20 buses sending a fix every 5 s, each open admin board triggers about 4 full refetches per
  second, so a handful of open boards saturates the API.
- **Fix:** ignore `position` messages on the admin board (the live map already handles them) and
  debounce refetches to about 2 s. Batch the per-trip queries (boarded counts and buses in one
  query each). Do the same for `GET /reports`, which runs 3 to 5 queries per report.

### H4. Report agent: crashes and false "critical" alarms
- **"800m" makes the analysis fail.** The minutes regex also matches metres: `m\b` in
  [llm.py:150](backend/app/modules/reports/llm.py#L150). "Driver stopped **800m** away" becomes
  `claimed_delay_min=800`. That is over the `le=600` limit in
  [schemas.py:51](backend/app/modules/reports/schemas.py#L51), so `rules_claims` raises a
  `ValidationError`, and with the model on it raises again in the fallback. **Measured:**
  `analysis_status = failed`. Values from 601 to 999 minutes fail the same way, and "500m" is
  silently read as a 500-minute delay.
  **Fix:** drop the bare `m`, clamp or ignore values over 600, and never let `rules_claims` raise.
- **Ordinary words trigger CRITICAL alerts.** `CRITICAL_WORDS` matches substrings
  ([llm.py:152](backend/app/modules/reports/llm.py#L152)): "please keep in **touch**", "the app
  **crash**ed", "it doesn't **hurt**". **Measured:** a lateness report saying "please keep in
  touch about the timing" became `severity=critical` and sent a critical alert to every admin.
  Too many false alarms train staff to ignore the real ones.
  **Fix:** match whole words or phrases ("touched me", "touching", "groped") and test against
  benign sentences.
- **The model's drafts break the prompt rules** (observed in the live run). Examples: "which is why
  you missed your class" (guessing a cause), "make sure it doesn't happen again" (a promise) and
  "follow up with the driver" (naming the driver). An admin reviews every draft before sending, so
  this is acceptable, but the screen should keep saying the text is a draft.

---

## 5. Medium and low

### M1. Inputs that cause 500 errors
Each of these was reproduced with a probe test:

| Request | Result |
|---|---|
| `PATCH /buses/{id}` `{"registration_no": null}` | 500 `AttributeError` ([master_data/service.py:60](backend/app/modules/master_data/service.py#L60)) |
| `PATCH /buses/{id}` `{"capacity": null}` (also `status`, `name`, `code`, `is_active` on routes) | 409 "Registration number already in use", which is misleading |
| `PATCH /stops/{id}` `{"name": null}` | 500 `IntegrityError` |
| `PATCH /schedules/{id}` `{"bus_id": null}` (also `driver_id`, `departure_time`, `is_active`) | 500 `IntegrityError` ([trips/service.py:102](backend/app/modules/trips/service.py#L102)) |
| `PATCH /users/{id}` with another student's `roll_no` (or a driver's `license_no`) | 500 `IntegrityError` ([auth/service.py:173](backend/app/modules/auth/service.py#L173)) |
| `?limit=-1` or `?offset=-1` on `/users`, `/notifications`, `/history/events`, `/boarding/me/attendance` | 500 `DBAPIError` (no `ge=` bound) |
| `POST /trips/{id}/positions` with `recorded_at` and no timezone | 500 `TypeError` ([tracking/service.py:93](backend/app/modules/tracking/service.py#L93)). The Flutter app sends UTC with `Z`, so this hits third-party GPS feeds (the planned Traccar integration) |
| Admin `arrived_at` or `started_at` with no timezone | 500 `TypeError` ([trips/service.py:297](backend/app/modules/trips/service.py#L297)) |

**Fix:**
- For non-nullable fields in `*Update` schemas, reject explicit nulls (a validator, or drop
  `None` values before applying).
- Add `ge=1` on `limit` and `ge=0` on `offset`.
- Use pydantic's `AwareDatetime` for timestamp inputs.
- Catch `IntegrityError` in `update_user` and return a 409.

### M2. Tokens and sessions
- The access token travels in the WebSocket URL (`/ws?token=…`), so uvicorn writes it **in plain
  text in the access log** (seen in the run log). Proxies log it too. Send it in the first
  WebSocket message instead, or redact query strings in logs.
- There is no revocation. Refresh tokens are valid for 7 days and reusable. Changing a password or
  deactivating a user doesn't end existing sessions. An open WebSocket stays authorised forever
  after its token expires.
- The app stores tokens in `shared_preferences`: plain prefs on Android, `localStorage` on web.
  On mobile, consider `flutter_secure_storage`.
- **The client logs the user out on *any* refresh failure**, including a timeout or a 502
  ([session.dart:117-118](frontend/lib/core/auth/session.dart#L117-L118)). A driver on patchy
  mobile data whose 30-minute token expires mid-trip can be signed out, which stops GPS
  reporting. Only log out on a 401 from `/auth/refresh`.

### M3. No rate limiting
Nothing limits `/auth/login` (password guessing) or `POST /reports`. Report spam queues an AI
analysis for each report (one at a time, about 6 s each) and sends a notification to every admin.
Add per-IP or per-user limits at the proxy or with middleware.

### M4. A driver can start a trip scheduled for another day
`start_trip` never checks `service_date`
([trips/service.py:313-322](backend/app/modules/trips/service.py#L313-L322)). **Measured:**
starting tomorrow's trip returned 200. It then blocks the driver's real trips (`already_running`)
and isn't auto-closed until the day after. Allow only today's (and yesterday's late-night) trips.

### M5. Cancelling a running trip loses attendance
Attendance is only finalised on `TripEnded`. **Measured:** after a rider boarded and an admin
cancelled the running trip (a breakdown), **0** attendance rows were written. Finalise on
`TripCancelled` too when there are boardings, or decide and document that cancelled runs don't
count.

### M6. Deactivated students keep their seat
Nothing reacts to `UserDeactivated`, and the seat count includes inactive students
([allocation/service.py:119-125](backend/app/modules/allocation/service.py#L119-L125)).
**Measured:** with capacity 1, after the only allocated student was deactivated, allocating
someone else returned **409 `route_full`**. End the allocation on deactivation, or exclude
inactive users from the count. A related gap: an admin can deactivate the last active admin.

### M7. The paste-the-code box ships in release web builds
[student_scan_screen.dart:129](frontend/lib/modules/boarding/screens/student_scan_screen.dart#L129)
shows it when `kDebugMode || kIsWeb`. Any QR reader turns the driver's code into text. Pasted into
a group chat, it lets a friend at home "board" within the 30 s window. Show the box in debug only,
and accept that the rotating QR deters cheating rather than proving presence. A later version
could compare the student's location with the bus's last fix.

### M8. Schedule edits don't reach generated trips
Changing a schedule's departure time, bus or driver leaves today's already-generated `scheduled`
trip unchanged. **Measured:** the departure stayed 23:50 after the schedule was edited to 23:55.
The watcher then alerts against the old time. Update the not-yet-started trips for the schedule,
as `reassign_bus_driver` already does for drivers.

### Low
- **L1.** Matching a lost-item report to a second found item leaves the first item `matched`
  forever ([reports/service.py:207](backend/app/modules/reports/service.py#L207)).
- **L2.** The report retry loop re-analyses reports that are still being analysed (it picks
  anything `pending` for over 30 s, but a model call takes up to 2 × 120 s). This duplicates LLM
  work under load.
- **L3.** `CapacityWarning` and `OverCapacity` check "already raised?" and then insert without a
  lock. Two simultaneous boardings can raise the alert twice. The same race exists for over-seat
  allocation by two admins.
- **L4.** `GET /history/trips/{id}/timeline` filters `domain_events.payload->>'trip_id'` with no
  index, so it scans the whole table. There is also no retention for `bus_positions` (about 720
  rows per bus per hour of driving), `domain_events` or `notifications`. Add an expression index
  and a retention job.
- **L5.** README and RUN.md say 91 backend tests; there are 93. `RUN.md` has an uncommitted change
  and `UI.md` is untracked.
- **L6.** Frontend test coverage is thin: 12 unit tests, no widget tests for screens or flows, and
  the screenshot tests are opt-in. Login, boarding and driver runs are only tested by hand.
- **L7.** `GET /buses/{id}` and `GET /trips/{id}` are open to any signed-in user, so students can
  read any driver's phone number. This may be intended for riders of that trip only.
- **L8.** `generate_trips` accepts any `service_date`, including past dates. It creates trips that
  can never run.
- **L9.** 19 Flutter packages have newer versions that are incompatible with the current
  constraints (`flutter pub outdated`). This is not a bug; plan an upgrade.
- **L10.** Login takes noticeably less time for unknown emails (no bcrypt call), which reveals
  which accounts exist (see B1).

---

## 6. What's already good
- The modular monolith is clean. Module boundaries are respected, and each module has a README
  and a DEVLOG.
- There is a consistent domain-error model with specific error codes the app reacts to.
- Migrations are complete and reversible, with no model drift.
- Tests build data through the real API, and the acceptance scenario is automated.
- The report agent keeps the model away from facts: verdicts come from code, and the model only
  reads and writes prose. There is a check for hallucinated numbers and a reliable rule-based
  fallback when Ollama is down.
- GPS ingest serialises per trip, clamps timestamps, ignores inaccurate fixes and only looks a
  couple of stops ahead.
- The app handles network drops (buffered GPS, WebSocket reconnect with backoff) and has a
  consistent design system.

---

## 7. Go-live checklist (suggested order)

1. **B1:** move bcrypt off the event loop.
2. **B5:** row locks plus partial unique indexes on running trips.
3. **B2:** cap delay escalations; skip or flag trips whose bus isn't active.
4. **B3, B4:** authorise WebSocket topics and strip names; anonymise the evidence in anonymous reports.
5. **H1:** fix the hub's `_send` snapshot.
6. **B6:** refuse to start with the default `JWT_SECRET`; `ALLOW_SIMULATION=false`; real
   `CORS_ORIGINS`; `TILE_URL`; Android release signing; remove cleartext traffic.
7. **B6:** add an API Dockerfile or service, a TLS reverse proxy with WebSocket upgrade, **one
   worker**, DB backups, monitoring, log redaction and a DB-aware `/health`. Add CI that runs
   `pytest`, `flutter analyze` and `flutter test`.
8. **H2:** attendance reconciler.
9. **H3, H4, M1 to M8:** in any order. Add a regression test for each, as CONTRIBUTING.md asks.
10. Run the full simulation set again (`demo_scenario`, three `simulate_bus` runs, `simulate_reports`)
    on the production-like setup before launch.
