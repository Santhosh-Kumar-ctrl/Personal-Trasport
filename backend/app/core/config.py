from pydantic_settings import BaseSettings, SettingsConfigDict

DEV_JWT_SECRET = "dev-secret-change-me-dev-secret-change-me"


class Settings(BaseSettings):
    """All runtime configuration. Values come from env vars or backend/.env."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # "production" turns on the start-up safety checks (see `production_problems`) and hides /docs.
    environment: str = "development"  # development | production

    database_url: str = "postgresql+asyncpg://transit:transit@localhost:5433/transit"
    test_database_url: str = "postgresql+asyncpg://transit:transit@localhost:5433/transit_test"

    jwt_secret: str = DEV_JWT_SECRET
    access_token_minutes: int = 30
    refresh_token_days: int = 7
    bcrypt_rounds: int = 12  # tests lower this for speed

    # College-local timezone: schedules ("07:30 departure") are interpreted in it.
    timezone: str = "Asia/Kolkata"

    qr_ttl_seconds: int = 30
    delay_threshold_min: int = 5
    # A delayed trip is announced again only when it crosses the next step (minutes late), then
    # never again. Steps above DELAY_STUDENT_ALERT_MAX_MIN go to the transport office only.
    delay_alert_steps: str = "5,15,30,60"
    delay_student_alert_max_min: int = 30  # (the first alert of a delay always reaches riders)
    capacity_warn_pct: int = 90
    delay_watch_interval_seconds: int = 60
    trip_generation_interval_seconds: int = 900
    # A trip still in progress after its service day is closed automatically once it has had no
    # start/stop activity for this long (covers drivers who forget to tap End).
    stale_trip_grace_hours: int = 3
    # Writes attendance for finished trips whose TripEnded handler never ran (crash, restart).
    attendance_reconcile_interval_seconds: int = 300

    # Live tracking (GPS from the driver's phone).
    arrival_radius_m: int = 100  # a stop is auto-marked arrived inside this radius
    approach_radius_m: int = 2000  # riders of a stop are told when the bus is this close
    max_fix_accuracy_m: int = 100  # fixes less accurate than this are stored but never trigger anything
    arrival_lookahead_stops: int = 2  # auto-arrival considers only the next N unreached stops

    # Lets admins pass explicit timestamps (e.g. arrived_at) and post GPS for any bus, to simulate
    # runs in demos. Never in production.
    allow_simulation: bool = False
    enable_background_tasks: bool = True

    # Rate limits (per process; the API runs as one worker).
    login_attempts_per_minute: int = 10  # per IP + email
    reports_per_hour: int = 5  # per student

    # Housekeeping: GPS fixes and read notifications older than this are deleted daily.
    position_retention_days: int = 90
    notification_retention_days: int = 180

    # Student reports: the triage agent calls NVIDIA NIM (OpenAI-compatible).
    # "rules" skips the model (keyword rules and templates; tests use it).
    # NIM being unreachable falls back to rules automatically.
    report_ai: str = "nim"  # nim | rules
    nim_api_key: str = ""  # set via NIM_API_KEY env var
    nim_base_url: str = "https://integrate.api.nvidia.com/v1"
    nim_model: str = "nvidia/llama-3.1-nemotron-70b-instruct"
    nim_embed_model: str = "nvidia/nv-embedqa-mistral-7b-v2"
    nim_timeout_seconds: float = 30
    report_speed_limit_kmph: int = 60  # GPS readings above this support an unsafe-driving report
    report_lookback_days: int = 3  # trips a report can be about; found items a lost item can match

    cors_origins: str = "*"

    @property
    def is_production(self) -> bool:
        return self.environment.lower() == "production"

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def delay_steps(self) -> list[int]:
        """Alert steps in minutes, starting at the delay threshold."""
        steps = {int(s) for s in self.delay_alert_steps.split(",") if s.strip()}
        return sorted({self.delay_threshold_min, *(s for s in steps if s > self.delay_threshold_min)})

    def production_problems(self) -> list[str]:
        """Settings that must not reach production. The app refuses to start while any remain."""
        problems = []
        if self.jwt_secret == DEV_JWT_SECRET or len(self.jwt_secret) < 32:
            problems.append("JWT_SECRET must be a random string of at least 32 characters")
        if self.allow_simulation:
            problems.append("ALLOW_SIMULATION must be false")
        if not self.cors_origin_list or "*" in self.cors_origin_list:
            problems.append("CORS_ORIGINS must list the web app's origin(s), not *")
        return problems


settings = Settings()
