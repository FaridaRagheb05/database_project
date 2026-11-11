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

## Hosting on Aiven

The database is hosted on a free Aiven MySQL 8.4 server. Aiven only accepts encrypted connections, so the app checks the server against Aiven's CA certificate, `ca.pem`. The certificate is public (it only proves the server is really Aiven's), so it is committed. The password is not.

The connection settings live in a `.env` file in the project root, which git ignores:

```bash
export DB_HOST=<host from the Aiven Overview page>
export DB_PORT=<port from the Aiven Overview page>
export DB_USER=avnadmin
export DB_PASSWORD=<password from the Aiven Overview page>
export DB_SSL_CA=milestone3/ca.pem
```

The Milestone II dump was imported into Aiven with:

```bash
source .env
sed -E 's/DEFINER=`[^`]+`@`[^`]+`//' milestone2/properties_dump.sql | \
  mysql --host="$DB_HOST" --port="$DB_PORT" --user="$DB_USER" --password="$DB_PASSWORD" \
        --ssl-ca="$DB_SSL_CA" --ssl-mode=VERIFY_CA --default-character-set=utf8mb4
```

`sed` removes `DEFINER=root@localhost` from the `v_user` view. mysqldump records that the view was created by `root@localhost`, but Aiven has no `root` user and does not let `avnadmin` create objects on another user's behalf, so the import would fail. Without it, the view belongs to `avnadmin`. The dump file itself is left unchanged.

After the import, every table had the same number of rows as its Milestone II CSV (e.g. 8,574 properties, 4,551 developments, 31,649 amenity rows).

## Features

_To be filled in as each feature is added._
