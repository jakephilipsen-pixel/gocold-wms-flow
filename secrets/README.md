# secrets/

Docker secrets for the stack. Files here are gitignored.

- `db_password.txt` — Postgres password (consumed via `POSTGRES_PASSWORD_FILE`
  and assembled into the backend's `DATABASE_URL` at run time). Set it BEFORE
  the first `docker compose up` — Postgres bakes the password on first init,
  so changing it later needs a DB volume reset. Generate one with:

      openssl rand -base64 32 > secrets/db_password.txt
