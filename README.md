# Resale Properties Database

CSCE 2501 Fundamentals of Database Systems project, Fall 2026. A MySQL database of the resale properties listed on [AqarExit](https://aqarexit.com/en/opportunities), with a web app for searching and analysing the resale market.

## Milestones

| Milestone | What it is | Deliverables |
|---|---|---|
| I: Database design | The ERD, relational model and schema | `Milestone 1.pdf` (ERD and relational model), `Milestone1.sql` (schema) |
| II: Database population | A crawler and parser that collected 8,574 listings from AqarExit, plus sample user data | [`milestone2/`](milestone2/): `crawler.py`, `parser.py`, `loader.py`, `csv/` (one CSV per table), `properties_dump.sql`, `ASSUMPTIONS.txt` |
| III: Application | A Streamlit web app connected to the database hosted on Aiven | [`milestone3/`](milestone3/): `app.py`, `db.py`, `properties_dump.sql` (latest dump), `ASSUMPTIONS.txt` |

Each milestone folder has a README explaining how to run it.

## Database

The `properties` database has 8 tables and 1 view:

| Table | Rows | What it holds |
|---|---|---|
| `location` | 182 | Areas (e.g. التجمع الخامس) |
| `developer` | 2,412 | Developers (e.g. Palm Hills Developments) |
| `development` | 4,551 | Development projects, each in an area and by a developer |
| `property` | 8,574 | Resale listings: type, size, rooms, payment details, market price, gain etc |
| `property_amenity` | 31,649 | The amenities of each listing |
| `app_user` | 60 | Registered users (sample data) |
| `user_focuses_location` | 120 | Each user's areas of focus |
| `review` | 178 | Users' ratings (1-10) and reviews of development projects |
| `v_user` (view) | | Users with their age worked out from their birthdate |

Row counts are as of the Milestone III dump.
