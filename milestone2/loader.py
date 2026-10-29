# Step 4: load the CSV files into MySQL

# What this script does:
#   1. Reads every CSV file in csv/*.csv
#   2. Inserts its rows into the matching table of the "properties" database using mysql.connector

# Before running this, create the schema:
#     mysql -u root -p < Milestone1.sql

# The script empties the tables first so it can be run again safely after re-crawling or re-parsing

# run using python loader.py
# (uses DB_PASSWORD if it's set, otherwise asks for the MySQL password
# B_HOST / DB_USER can be set to change the server or user -> i noticed that it will be needed in Milestone 3 when the database is on a different server than the code

import csv # to read the CSV files
import getpass # to ask for the password without showing it
import os # to read the DB_HOST / DB_USER / DB_PASSWORD settings
from pathlib import Path # for building file paths

import mysql.connector 


CSV_DIR = Path(__file__).parent / "csv"

# Tables in the order they have to be filled
# A table is only loaded after the tables its foreign keys point to
# (e.g. location before development and  development before property)
TABLES = ["location", "developer", "development", "property", "property_amenity",
          "app_user", "user_focuses_location", "review"]

# Insert this many rows per query
# I found that sending rows in batches is much faster than one query per row -> recommended by the mysql.connector documentation
BATCH_SIZE = 1000


def main():
    # Connect to MySQL
    # The password comes from the DB_PASSWORD environment variable and if that isn't set it gets typed in -> so that it's never stored in the code
    conn = mysql.connector.connect(
        host=os.environ.get("DB_HOST", "localhost"),
        user=os.environ.get("DB_USER", "root"),
        password=os.environ.get("DB_PASSWORD") or getpass.getpass("MySQL password: "),
        database="properties",
        charset="utf8mb4", # needed for the Arabic text
    )
    cursor = conn.cursor()

    # Empty the tables children first (the reverse of TABLES) so no foreign key ever points to a row that was already deleted
    for table in reversed(TABLES):
        cursor.execute(f"DELETE FROM {table}")
        # Commit after every DML statement as recommended in the hidden lab
        conn.commit()

    for table in TABLES:
        # Read the CSV for this table
        # utf-8-sig skips the marker at the start of the file that makes Excel show Arabic correctly
        with open(CSV_DIR / f"{table}.csv", newline="", encoding="utf-8-sig") as f:
            reader = csv.reader(f)
            columns = next(reader) # the first line is the column names
            # csv stores a missing value as an empty string but MySQL needs NULL -> mysql.connector writes NULL for Python's None
            rows = [[value if value != "" else None for value in row] for row in reader]

        # Build e.g. "INSERT INTO location (area_name) VALUES (%s)"
        # mysql.connector fills in each %s safely (to avoid SQL injection attacks as recommended by TA)
        placeholders = ", ".join(["%s"] * len(columns))
        sql = f"INSERT INTO {table} ({', '.join(columns)}) VALUES ({placeholders})"

        # Insert the rows with executemany (not a for loop with one execute per row) as recommended by TA as it is much faster
        # BATCH_SIZE rows at a time so that one query never gets too big for the server
        for start in range(0, len(rows), BATCH_SIZE):
            cursor.executemany(sql, rows[start:start + BATCH_SIZE])

            conn.commit()
        print(f"  {table}: {len(rows)} rows")

    cursor.close()
    conn.close()
    print("Done.")

if __name__ == "__main__":
    main()
