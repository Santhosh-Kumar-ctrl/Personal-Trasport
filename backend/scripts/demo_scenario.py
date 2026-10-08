"""Day-30 acceptance scenario against a RUNNING API (run `python -m scripts.seed` first).

    python -m scripts.demo_scenario                  # full run, trip ends at the finish
    python -m scripts.demo_scenario --keep-running   # leave the trip live to explore in the app
    python -m scripts.demo_scenario --api http://localhost:8000

Steps: admin assigns students -> driver starts trip -> student scans driver's QR ->
delay simulated at stop 2 -> waiting student + admin notified -> live board shows it ->
trip ends -> attendance + timeline.
"""

import argparse
import sys
import time
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import httpx

PASSWORD = "transit123"
TZ = ZoneInfo("Asia/Kolkata")


def step(n: int, text: str) -> None:
    print(f"\n\033[1m[{n}] {text}\033[0m")


def ok(text: str) -> None:
    print(f"    \033[32m✓\033[0m {text}")


class Api:
    def __init__(self, base: str):
        self.c = httpx.Client(base_url=base, timeout=15)

    def login(self, email: str) -> dict:
        r = self.c.post("/auth/login", json={"email": email, "password": PASSWORD})
        r.raise_for_status()
        return {"Authorization": f"Bearer {r.json()['access_token']}"}

    def call(self, method: str, url: str, who: dict, **kw):
        r = self.c.request(method, url, headers=who, **kw)
        if r.status_code >= 400:
            sys.exit(f"    ✗ {method} {url} -> {r.status_code} {r.text}")
        return r.json() if r.content else None


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--api", default="http://localhost:8000")
    ap.add_argument("--keep-running", action="store_true")
    ap.add_argument("--delay", type=int, default=12, help="minutes late at stop 2")
    args = ap.parse_args()
    api = Api(args.api)

    step(1, "Administrator assigns students to route 14")
    admin = api.login("admin@college.edu")
    route = next(r for r in api.call("GET", "/routes", admin) if r["code"] == "14")
    driver_user = api.call("GET", "/users", admin, params={"role": "driver", "q": "driver1@"})[0]
    rider = api.call("GET", "/users", admin, params={"q": "student1@"})[0]
    waiting = api.call("GET", "/users", admin, params={"q": "student27@"})[0]
    api.call("POST", "/allocations", admin, json={"student_id": rider["id"], "route_id": route["id"],
                                                  "stop_id": route["stops"][0]["stop_id"], "force": True})
    res = api.call("POST", "/allocations", admin, json={"student_id": waiting["id"], "route_id": route["id"],
                                                        "stop_id": route["stops"][2]["stop_id"], "force": True})
    ok(f"{rider['full_name']} -> {route['stops'][0]['stop']['name']}")
    ok(f"{waiting['full_name']} -> {res['allocation']['stop']['name']}")

    # A one-off schedule departing now, so the demo works at any time of day.
    bus = next(b for b in api.call("GET", "/buses", admin) if b["registration_no"] == "TN09AB0904")
    now_local = datetime.now(TZ)
    sched = api.call("POST", "/schedules", admin, json={
        "route_id": route["id"], "bus_id": bus["id"], "driver_id": driver_user["id"], "direction": "pickup",
        "departure_time": now_local.strftime("%H:%M:00"), "days_of_week": [now_local.isoweekday()]})
    api.call("POST", "/trips/generate", admin, json={})
    trip = next(t for t in api.call("GET", "/trips", admin) if t["schedule_id"] == sched["id"])
    ok(f"Demo trip #{trip['id']} scheduled {now_local:%H:%M} on bus {bus['registration_no']}")

    step(2, "Driver starts the trip")
    driver = api.login("driver1@college.edu")
    trip = api.call("POST", f"/trips/{trip['id']}/start", driver)
    ok(f"Trip {trip['status']}, next stop: {trip['next_stop']['stop_name']}")

    step(3, "Student scans the QR shown on the driver's phone")
    qr = api.call("GET", f"/boarding/trips/{trip['id']}/qr", driver)
    ok(f"Driver QR issued (rotates every {qr['ttl_seconds']}s)")
    student = api.login("student1@college.edu")
    receipt = api.call("POST", "/boarding/check-in", student, json={"token": qr["token"]})
    ok(f"{receipt['student_name']}: {receipt['message']} ({receipt['boarded_count']} on board)")

    step(4, f"Delay simulated: bus reaches stop 2 {args.delay} min late")
    stop2 = trip["stops"][1]
    late = (datetime.fromisoformat(stop2["scheduled_at"]) + timedelta(minutes=args.delay)).isoformat()
    api.call("POST", f"/trips/{trip['id']}/stops/2/arrive", admin, json={"arrived_at": late})
    ok(f"Arrival at {stop2['stop_name']} recorded")
    time.sleep(1.0)  # let event handlers finish

    step(5, "System detects impact and notifies users")
    waiting_h = api.login("student27@college.edu")
    note = next((n for n in api.call("GET", "/notifications", waiting_h) if n["type"] == "TripDelayed"), None)
    if not note:
        sys.exit("    ✗ waiting student was not notified")
    ok(f"{waiting['full_name']} got: \"{note['title']}\"; {note['body']}")
    admin_note = next(n for n in api.call("GET", "/notifications", admin) if n["type"] == "TripDelayed")
    ok(f"Admin got: \"{admin_note['title']}\"; {admin_note['body']}")

    step(6, "Administrator's live board")
    board = api.call("GET", "/dashboard/admin", admin)
    row = next(r for r in board["board"] if r["trip_id"] == trip["id"])
    ok(f"Route {row['route']['code']} | +{row['delay_min']} min | {row['boarded']}/{row['capacity']} seats | "
       f"next: {row['next_stop']['name'] if row['next_stop'] else '-'}")
    print("    (Corrective recommendation + alternate allocation = Team B's Transport Operations Agent, P1)")

    if args.keep_running:
        print(f"\nTrip #{trip['id']} left running. End it from the driver app, or:\n"
              f"  POST {args.api}/trips/{trip['id']}/end")
        return

    step(7, "Trip ends: attendance finalised, history recorded")
    api.call("POST", f"/trips/{trip['id']}/end", driver)
    time.sleep(1.0)
    att = api.call("GET", "/history/attendance", admin, params={"route_id": route["id"]})
    mine = [a for a in att if a["trip_id"] == trip["id"]]
    present = sum(a["status"] != "absent" for a in mine)
    ok(f"Attendance: {present} present, {len(mine) - present} absent")
    timeline = api.call("GET", f"/history/trips/{trip['id']}/timeline", admin)
    ok("Timeline: " + " → ".join(dict.fromkeys(e["type"] for e in timeline)))
    api.call("PATCH", f"/schedules/{sched['id']}", admin, json={"is_active": False})
    print("\n\033[32mAcceptance scenario complete.\033[0m")


if __name__ == "__main__":
    # ✓/✗ crash a cp1252 Windows console when output is piped or redirected
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
    main()
