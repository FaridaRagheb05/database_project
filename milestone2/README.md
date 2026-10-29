# Milestone II: Web Crawling and Data Population

Libraries: Playwright (crawling), `csv` (CSV files), `mysql.connector` (loading into MySQL).

## How to run

```bash
# one-time setup (from the project folder)
python3 -m venv .venv
.venv/bin/pip install playwright mysql-connector-python
.venv/bin/python -m playwright install chromium

# 1. crawl all listings into milestone2/raw/ (about 4 hours; can be stopped and resumed)
.venv/bin/python milestone2/crawler.py

# 2. parse them into milestone2/csv/
.venv/bin/python milestone2/parser.py

# 3. generate sample users, focus areas and reviews
.venv/bin/python milestone2/sample_users.py

# 4. create the schema, then load every CSV into MySQL
mysql -u root -p < Milestone1.sql
.venv/bin/python milestone2/loader.py

# 5. dump the populated database (--set-gtid-purged=OFF so the dump can be imported on another server)
mysqldump -u root -p --databases properties --routines --triggers --default-character-set=utf8mb4 \
  --set-gtid-purged=OFF --single-transaction > milestone2/properties_dump.sql
```

## Files

| File | What it does |
|---|---|
| `crawler.py` | Reads every listing URL from the site's sitemap and saves each listing's text to `raw/` |
| `parser.py` | Extracts the fields from `raw/` and writes the listing tables to `csv/` |
| `sample_users.py` | Generates sample data for the user tables (`app_user`, `user_focuses_location`, `review`) |
| `loader.py` | Inserts every CSV in `csv/` into the `properties` database |
| `csv/` | One CSV file per table (deliverable) |
| `properties_dump.sql` | Populated MySQL dump, made with `mysqldump` (deliverable) |

## Assumptions

**Crawling**
- The listing URLs come from `https://aqarexit.com/sitemap.xml`, which lists every listing. The opportunities page only shows about 200 listings unless you sign in, and the site's robots.txt allows crawling `/buy/opportunity/`.
- Requests are spaced 1–2 seconds apart to respect Cloudflare's rate limits. If the site rate-limits a request, the crawler waits longer before retrying.
- Listings that return 404 (removed since the sitemap was generated) are skipped.

**New columns added to `property` in Milestone II**
The listing pages show these fields, which were not in the Milestone I schema. The spec asks to store all the information on the page, so they were added as nullable columns:
- `floor`: the floor as written on the site ("Ground", "4", ...). It's text because the site sometimes uses words instead of numbers.
- `finishing`: the finishing level, e.g. تشطيب كامل (fully finished), نص تشطيب (semi-finished), على الطوب (core and shell).
- `completion_status`: whether the unit is under construction (تحت الإنشاء) or ready to move into (جاهزة للاستلام).
- `garden_roof_sqm`: the size of a private garden or roof in m², if the unit has one.
- `installments_left_years`: years of installments remaining. "Fully paid" is stored as 0.

**Parsing**
- `payment_method` isn't shown on the site. It is stored as "Installments" when there is a remaining amount with the developer, and "Cash" when the remaining amount is 0.
- `development.description` isn't shown on the site, so it is NULL.
- `title` is the page title (e.g. "Bloomfields — شقة 184 m² · 3 BR · المستقبل سيتي · cash EGP 3.4M").
- `commission_pct` is taken from the market-price line. When a listing has no market price, it is taken from the buyer's-fee line instead.
- Values that would break a CHECK constraint (e.g. a contract year outside 1990–2100, an area of 0) are treated as typos on the site and stored as NULL.
- Invisible formatting characters (e.g. the right-to-left mark some sellers paste before Arabic text) are removed from the listing text.
- Names that differ only in case, spacing, accents, Arabic letter forms (أ/ا, ة/ه, ى/ي) or Arabic vs English digits (٣/3) count as the same location, developer or project, and the first spelling seen is stored. A name written in English and in Arabic ("Mountain view" / "ماونتن فيو") is stored as two different names, because there's no reliable way to match the two automatically.
- A development is identified by its project name and area, as in the Milestone I schema.
- "This unit has overdue instalments" appears on some listings but is not stored.

**Sample user data**
- 60 users with made-up usernames and `@example.com` emails, each focusing on 1–3 real areas from the crawl.
- Each user reviews 0–6 real development projects. Ratings are 1–10, the review text matches the rating, and about 20% of reviews have no text.
- The random generator uses a fixed seed, so running the script again produces the same data.
