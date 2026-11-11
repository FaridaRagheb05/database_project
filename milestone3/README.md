# Milestone III: Application Layer

A Streamlit web app that works as an interface to the `properties` database, which is hosted on a remote MySQL server (Aiven), not on localhost.

Libraries: Streamlit (web interface), `mysql.connector` (talking to MySQL).

## How to run

```bash
# one-time setup (from the project folder)
python3 -m venv .venv
.venv/bin/pip install -r milestone3/requirements.txt

# start the app, then open the link it prints (http://localhost:8501)
.venv/bin/streamlit run milestone3/app.py
```

## Connecting to the database

`db.py` reads the connection settings from environment variables, so the password is never stored in the code:

| Variable | Meaning | Default |
|---|---|---|
| `DB_HOST` | Server address | `localhost` |
| `DB_PORT` | Server port | `3306` |
| `DB_USER` | MySQL user | `root` |
| `DB_PASSWORD` | MySQL password | empty |
| `DB_SSL_CA` | Path to the server's CA certificate (needed for Aiven, which only accepts encrypted connections) | not set |

The app keeps a small pool of connections open and reuses them, because Streamlit reruns the script on every click. All values typed into the app are passed to MySQL as `%s` parameters, never pasted into the SQL text, to prevent SQL injection.

## Features

_To be filled in as each feature is added._
