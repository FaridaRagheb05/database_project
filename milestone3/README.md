# Milestone III: Application Layer

A Streamlit web app that works as an interface to the `properties` database, which is hosted on a remote MySQL server (Aiven), not on localhost.

**Live app:** https://resale-properties.streamlit.app/

Libraries: Streamlit (web interface), `mysql.connector` (talking to MySQL).

## How to run

```bash
# one-time setup (from the project folder)
python3 -m venv .venv
.venv/bin/pip install -r milestone3/requirements.txt

# start the app, then open the link it prints (http://localhost:8501)
# the database settings are read from .env automatically (see "Hosting on Aiven")
.venv/bin/streamlit run milestone3/app.py
```

## Files

| File | What it does |
|---|---|
| `app.py` | The web app: a sidebar menu with one page per feature |
| `db.py` | Connects to MySQL and runs queries for the app |
| `merge_developers.py` | One-time fix that merged the different spellings of the top developers (see `ASSUMPTIONS.txt`). Runs as a dry run unless given `--apply` |
| `ca.pem` | Aiven's CA certificate, used to verify the encrypted connection |
| `requirements.txt` | The Python libraries the app needs |
| `ASSUMPTIONS.txt` | Every assumption made in this milestone (deliverable) |
| `properties_dump.sql` | Latest dump of the database, taken from Aiven (deliverable) |

## Connecting to the database

`db.py` reads the connection settings from the `.env` file in the project folder, so the password is never stored in the code. Settings that are already environment variables take priority over the file (this is how they are given on a hosting service such as Streamlit Cloud). All five are required. If any is missing, the app shows which one instead of trying to connect.

| Variable | Meaning |
|---|---|
| `DB_HOST` | Server address |
| `DB_PORT` | Server port |
| `DB_USER` | MySQL user |
| `DB_PASSWORD` | MySQL password |
| `DB_SSL_CA` | Path to the server's CA certificate, relative to the project folder (Aiven only accepts encrypted connections) |

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

## Deployment

The app is deployed on Streamlit Community Cloud at https://resale-properties.streamlit.app/, so it can be used from any browser without installing anything. Both the website and the database are in the cloud.

| Setting | Value |
|---|---|
| Repository / branch | `FaridaRagheb05/database_project` / `main` |
| Main file path | `milestone3/app.py` |
| Python version | 3.11 |
| Libraries | Installed from `milestone3/requirements.txt` |

The five `DB_` settings are entered in the app's **Secrets** on Streamlit Cloud, not in the repository:

```toml
DB_HOST = "<host from the Aiven Overview page>"
DB_PORT = "<port>"
DB_USER = "avnadmin"
DB_PASSWORD = "<password>"
DB_SSL_CA = "milestone3/ca.pem"
```

Streamlit Cloud passes these to the app as environment variables, which `db.py` reads in the same way as the `.env` file locally. Every push to `main` redeploys the app automatically.

## Database dump

`properties_dump.sql` is the latest dump, taken from Aiven:

```bash
source .env
mysqldump --host="$DB_HOST" --port="$DB_PORT" --user="$DB_USER" -p --ssl-ca="$DB_SSL_CA" --ssl-mode=VERIFY_CA \
  --databases properties --routines --triggers --default-character-set=utf8mb4 \
  --set-gtid-purged=OFF --single-transaction --no-tablespaces > milestone3/properties_dump.sql
sed -i '' -E 's/DEFINER=`[^`]+`@`[^`]+`//' milestone3/properties_dump.sql
```

- `--no-tablespaces` is needed because Aiven doesn't give `avnadmin` the permission to read tablespace information.
- `sed` removes `DEFINER=avnadmin@%` from the `v_user` view, so the dump can be imported on a server that has no `avnadmin` user (e.g. `mysql -u root -p < milestone3/properties_dump.sql`).

To check the dump, it was imported into a temporary database on Aiven: every table had the same row count as the live database and `v_user` worked. The temporary database was then deleted.

## Features

| Feature | Page | How it works |
|---|---|---|
| Register a user | Register a user | Inserts into `app_user` and one row per focus area into `user_focuses_location`, as one transaction (all saved or none). The age is read back from the `v_user` view |
| Add a new user review on a project | Add a review | Checks the email is registered, then inserts into `review` |
| View existing reviews of a project | View reviews of a project | Shows the project's developer and area, its review count and average rating (`COUNT` / `AVG` with a `LEFT JOIN`), and its reviews newest first |
| Top 10 projects with highest resale inventory, resale amount and gain over market value by property type | Top 10 projects by property type | Pick a type to get three top-10 lists of projects (`GROUP BY` development): most listings (`COUNT`), highest total price (`SUM`) and highest average gain per listing (`AVG(gain_amount)`). The gain list only ranks projects with at least a chosen number of listings (`HAVING COUNT(*) >= n`, 3 by default) |
| Location of a development, with avg price / m² and number of listings for each unit type | Development details | Shows the project's area and developer, then `COUNT` and `AVG(price / area_sqm)` grouped by unit type |
| All properties in an area, with avg price / m² for each unit type | Properties in an area | The same per-type summary for the area, then every listing in it, cheapest first |
| Properties in an area in a price range with a set of amenities | Search by area, price and amenities | Filters by area and `price BETWEEN min AND max`. For amenities, a subquery on `property_amenity` with `GROUP BY listing_ref HAVING COUNT(*) = <number picked>` keeps only listings that have all of them |
| Top 5 developers by resale listings, with avg price / m², avg down payment and gain over market value | Top 5 developers | Joins property to development and groups by `developer_name`, ordered by `COUNT(*)` |
| All properties by area, property type and contract year | Properties by area, type and contract year | Three optional filters. Only the picked ones are added to the `WHERE` clause |
| Avg installment, avg down payment, number of properties, avg discount over market price, avg contract age and avg market price by area and development project | Averages by area and project | Groups by area and project. Discount is `(market_price − price) / market_price × 100` and contract age is `YEAR(CURDATE()) − contract_year`. An optional area filter narrows it to one area |

Price is `down_payment + remaining_amount` and price / m² is price ÷ `area_sqm` (see `ASSUMPTIONS.txt`). Listing tables link to each listing's page on AqarExit.

## Assumptions

All the assumptions for this milestone (hosting, users and reviews, and how terms like price per m² and gain over market value are calculated) are in [`ASSUMPTIONS.txt`](ASSUMPTIONS.txt).
