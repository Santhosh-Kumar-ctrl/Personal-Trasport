"""Drive a bus along its route by sending GPS fixes, as the driver's phone would.

Needs a RUNNING API and seeded data (`python -m scripts.seed`). Stops need coordinates.

    python -m scripts.simulate_bus                         # driver1, pickup run departing now, 10x speed
    python -m scripts.simulate_bus --driver driver2@college.edu --direction drop
    python -m scripts.simulate_bus --speedup 1 --interval 5  # real time, a fix every 5 s
    python -m scripts.simulate_bus --end                   # end the trip at the last stop
    python -m scripts.simulate_bus --end --board-rate 1     # every allocated student boards

If the driver has a trip in progress it is used; otherwise a one-off trip departing now is
created on the driver's usual route and bus (so no "started 7 hours late" alerts) and started.
Watch it in the app as a student of that route, or on the admin Live map.

Students board by scanning the driver's QR, as the student app does: on a pickup run each one
boards when the bus reaches their stop, on a drop run everyone boards at campus. `--board-rate`
picks the share who turn up (the rest are absent). With `--end`, the attendance written for the
trip is checked against who actually boarded, and the script exits non-zero on a mismatch.
"""

import argparse
import math
import random
import sys
import time
from datetime import datetime
from zoneinfo import ZoneInfo

import httpx

PASSWORD = "transit123"
TZ = ZoneInfo("Asia/Kolkata")


class Api:
    def __init__(self, base: str):
        self.c = httpx.Client(base_url=base, timeout=15)

    def login(self, email: str) -> dict:
        r = self.c.post("/auth/login", json={"email": email, "password": PASSWORD})
        if r.status_code != 200:
            sys.exit(f"Can't sign in as {email}: {r.status_code} {r.text}")
        return {"Authorization": f"Bearer {r.json()['access_token']}"}

    def call(self, method: str, url: str, who: dict, **kw):
        r = self.c.request(method, url, headers=who, **kw)
        if r.status_code >= 400:
            sys.exit(f"✗ {method} {url} -> {r.status_code} {r.text}")
        return r.json() if r.content else None


def bearing(a: tuple[float, float], b: tuple[float, float]) -> float:
    lat1, lat2 = math.radians(a[0]), math.radians(b[0])
    dl = math.radians(b[1] - a[1])
    x = math.sin(dl) * math.cos(lat2)
    y = math.cos(lat1) * math.sin(lat2) - math.sin(lat1) * math.cos(lat2) * math.cos(dl)
    return (math.degrees(math.atan2(x, y)) + 360) % 360


def metres(a: tuple[float, float], b: tuple[float, float]) -> float:
    p1, p2 = math.radians(a[0]), math.radians(b[0])
    dp, dl = p2 - p1, math.radians(b[1] - a[1])
    h = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * 6_371_000 * math.asin(math.sqrt(h))


def pick_riders(api: Api, driver: dict, admin: dict, trip_id: int, rate: float) -> tuple[dict[int, list[dict]], set[int]]:
    """Allocated students who will turn up, by stop id, and who is already on board (a resumed trip).
    Seeded, so reruns pick the same people."""
    roster = api.call("GET", f"/boarding/trips/{trip_id}/roster", driver)
    emails = {u["id"]: u["email"] for u in api.call("GET", "/users", admin, params={"role": "student"})}
    rng = random.Random(trip_id)
    riders: dict[int, list[dict]] = {}
    for e in roster["entries"]:
        if e["allocated"] and not e["boarded"] and rng.random() < rate:
            riders.setdefault(e["stop_id"], []).append({**e, "email": emails[e["student_id"]]})
    return riders, {e["student_id"] for e in roster["entries"] if e["boarded"]}


def board(api: Api, driver: dict, trip_id: int, students: list[dict]) -> list[int]:
    """Each student scans the QR currently on the driver's screen. Returns who boarded."""
    boarded = []
    for st in students:
        qr = api.call("GET", f"/boarding/trips/{trip_id}/qr", driver)
        receipt = api.call("POST", "/boarding/check-in", api.login(st["email"]), json={"token": qr["token"]})
        boarded.append(st["student_id"])
        print(f"    boarded {st['full_name']} ({receipt['boarded_count']} on board)")
    return boarded


def check_attendance(api: Api, admin: dict, trip: dict, boarded: set[int]) -> None:
    """Attendance is written when TripEnded is handled, just after /end returns, so poll briefly."""
    for _ in range(20):
        rows = [r for r in api.call("GET", "/history/attendance", admin,
                                    params={"route_id": trip["route_id"], "date_from": trip["service_date"],
                                            "date_to": trip["service_date"]})
                if r["trip_id"] == trip["id"]]
        if rows:
            break
        time.sleep(0.5)
    else:
        sys.exit(f"✗ No attendance was written for trip #{trip['id']}.")
    present = {r["student_id"] for r in rows if r["status"] != "absent"}
    absent = len(rows) - len(present)
    print(f"Attendance: {len(present)} present, {absent} absent.")
    if present != boarded:
        sys.exit(f"✗ Attendance doesn't match boarding: marked present but didn't board "
                 f"{sorted(present - boarded)}, boarded but not marked present {sorted(boarded - present)}.")
    print("✓ Attendance matches who boarded.")


def running_or_new_trip(api: Api, driver_email: str, direction: str) -> tuple[dict, dict]:
    driver = api.login(driver_email)
    mine = api.call("GET", "/trips/mine", driver)
    running = next((t for t in mine if t["status"] == "in_progress"), None)
    if running:
        print(f"Using trip #{running['id']} already in progress (route {running['route']['code']}).")
        return driver, running

    admin = api.login("admin@college.edu")
    me = api.call("GET", "/users", admin, params={"role": "driver", "q": driver_email})[0]
    schedules = api.call("GET", "/schedules", admin, params={"driver_id": me["id"]})
    if not schedules:
        sys.exit(f"{driver_email} has no schedules to take a route and bus from.")
    base = schedules[0]
    now = datetime.now(TZ)
    sched = api.call("POST", "/schedules", admin, json={
        "route_id": base["route_id"], "bus_id": base["bus_id"], "driver_id": me["id"], "direction": direction,
        "departure_time": now.strftime("%H:%M:00"), "days_of_week": [now.isoweekday()]})
    api.call("POST", "/trips/generate", admin, json={})
    api.call("PATCH", f"/schedules/{sched['id']}", admin, json={"is_active": False})  # one-off
    trip = next(t for t in api.call("GET", "/trips", admin) if t["schedule_id"] == sched["id"])
    trip = api.call("POST", f"/trips/{trip['id']}/start", driver)
    print(f"Started one-off {direction} trip #{trip['id']} on route {trip['route']['code']} "
          f"(bus {trip['bus']['registration_no']}).")
    return driver, trip


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--api", default="http://localhost:8000")
    ap.add_argument("--driver", default="driver1@college.edu")
    ap.add_argument("--direction", choices=["pickup", "drop"], default="pickup")
    ap.add_argument("--speed", type=float, default=30, help="bus speed in km/h")
    ap.add_argument("--interval", type=float, default=2, help="real seconds between fixes")
    ap.add_argument("--speedup", type=float, default=10, help="simulated seconds per real second")
    ap.add_argument("--dwell", type=int, default=2, help="fixes sent while standing at each stop")
    ap.add_argument("--noise", type=float, default=6, help="GPS jitter in metres")
    ap.add_argument("--end", action="store_true", help="end the trip at the last stop")
    ap.add_argument("--board-rate", type=float, default=0.75,
                    help="share of allocated students who scan the QR and board (0 = nobody)")
    args = ap.parse_args()

    api = Api(args.api)
    driver, trip = running_or_new_trip(api, args.driver, args.direction)
    admin = api.login("admin@college.edu")
    live = api.call("GET", f"/trips/{trip['id']}/live", driver)
    stops = [s for s in live["stops"] if s["latitude"] is not None]
    if len(stops) < 2:
        sys.exit("This route's stops have no coordinates. Re-seed (`python -m scripts.seed --reset`) or add them.")
    missing = [s["name"] for s in live["stops"] if s["latitude"] is None]
    if missing:
        print(f"No coordinates for {', '.join(missing)}: the bus drives past them and the driver must tap Arrived.")

    step_m = args.speed / 3.6 * args.interval * args.speedup
    rng = random.Random(1)

    def send(lat: float, lng: float, heading: float, speed: float) -> None:
        jitter = args.noise / 111_000
        fix = {"latitude": lat + rng.uniform(-jitter, jitter), "longitude": lng + rng.uniform(-jitter, jitter),
               "speed_kmph": speed, "heading_deg": round(heading, 1), "accuracy_m": max(args.noise, 5)}
        out = api.call("POST", f"/trips/{trip['id']}/positions", driver, json={"positions": [fix]})
        notes = []
        names = {s["sequence"]: s["name"] for s in live["stops"]}
        if out["arrived"]:
            notes.append("ARRIVED " + ", ".join(names[q] for q in out["arrived"]))
        if out["approaching"]:
            notes.append("2 km alert " + ", ".join(names[q] for q in out["approaching"]))
        print(f"  {lat:.5f},{lng:.5f}  {speed:>4.0f} km/h  {'  '.join(notes)}")
        time.sleep(args.interval)

    riders, boarded = pick_riders(api, driver, admin, trip["id"], args.board_rate)
    if trip["direction"] == "drop":  # everyone gets on at campus
        riders = {stops[0]["stop_id"]: [st for group in riders.values() for st in group]}
    print(f"{sum(map(len, riders.values()))} students will board.")
    boarded.update(board(api, driver, trip["id"], riders.get(stops[0]["stop_id"], [])))

    print(f"Driving {len(stops)} stops at {args.speed:.0f} km/h, {args.speedup:g}x speed. Ctrl+C to stop.")
    try:
        for a, b in zip(stops, stops[1:]):
            pa, pb = (a["latitude"], a["longitude"]), (b["latitude"], b["longitude"])
            heading, dist = bearing(pa, pb), metres(pa, pb)
            print(f"{a['name']} -> {b['name']} ({dist / 1000:.1f} km)")
            n = max(1, int(dist // step_m))
            for i in range(1, n):
                f = i / n
                send(pa[0] + (pb[0] - pa[0]) * f, pa[1] + (pb[1] - pa[1]) * f, heading, args.speed)
            for _ in range(max(1, args.dwell)):
                send(pb[0], pb[1], heading, 0)
            if trip["direction"] == "pickup":
                boarded.update(board(api, driver, trip["id"], riders.get(b["stop_id"], [])))
    except KeyboardInterrupt:
        print("\nStopped. The trip is still running.")
        return

    if args.end:
        api.call("POST", f"/trips/{trip['id']}/end", driver)
        print(f"Trip #{trip['id']} ended.")
        check_attendance(api, admin, trip, boarded)
    else:
        print(f"Reached the last stop. Trip #{trip['id']} is still running; end it from the driver app or with --end.")


if __name__ == "__main__":
    # ✓/✗ crash a cp1252 Windows console when output is piped or redirected
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
    main()
