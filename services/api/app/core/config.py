"""All settings come from environment variables (or services/api/.env). See .env.example."""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Postgres connection string, e.g. postgresql://user:pass@host:5432/db
    database_url: str = "postgresql://postgres@localhost:5432/gasolina"

    # "supabase" in production. "dev" lets you sign in by just sending an email in the
    # X-Dev-Email header. Never use "dev" on a public server.
    auth_mode: str = "supabase"

    # Supabase project URL (used to fetch the public keys that verify sign-in tokens)
    supabase_url: str = ""
    # Only for older Supabase projects that sign tokens with a shared secret (HS256)
    supabase_jwt_secret: str = ""

    # This email is created as an owner on startup, so the first person can sign in.
    bootstrap_owner_email: str = ""
    bootstrap_owner_name: str = "Owner"

    # App admins (the people who run the app, e.g. support). Comma-separated emails. They get every
    # owner power, are listed separately on the People page, and the owner can't change them.
    admin_emails: str = ""

    # Comma-separated list of web app origins allowed to call the API
    cors_origins: str = "http://localhost:5173"

    @property
    def admin_email_list(self) -> list[str]:
        return [e.strip().lower() for e in self.admin_emails.split(",") if e.strip()]

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
