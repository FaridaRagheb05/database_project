# Database connection used by every page of the app

# What this file does:
#   1. Reads the database settings from the .env file in the project folder
#   2. Connects to the "properties" database on Aiven using DB_HOST / DB_PORT / DB_USER / DB_PASSWORD / DB_SSL_CA
#   3. Gives the app run_query() for SELECTs, run_change() for one INSERT and run_changes() for several INSERTs that belong together

# Not run directly -> app.py imports it

import os # to read the DB_HOST / DB_PORT / DB_USER / DB_PASSWORD / DB_SSL_CA settings
from pathlib import Path # for building file paths

import mysql.connector
from mysql.connector import pooling # keeps a few connections open so they can be reused
import streamlit as st # for st.cache_resource and for showing an error if the settings are missing


# The project folder (one level up from milestone3/) where .env lives
PROJECT_DIR = Path(__file__).parent.parent
ENV_FILE = PROJECT_DIR / ".env"

# The settings the app can't connect without
REQUIRED = ["DB_HOST", "DB_PORT", "DB_USER", "DB_PASSWORD", "DB_SSL_CA"]


# Helper functions

# Reads the .env file and puts each setting into the environment variables
# -> so the app works without running "source .env" first, from any terminal or VS Code's Run button
# Each line looks like "export DB_HOST=..." (the export is there so "source .env" still works too)
# A setting that already exists in the environment is not replaced
# -> e.g. on Streamlit Cloud the settings come from its secrets page instead of a .env file

def load_env_file():

    # No .env file is fine here, the check in connection_settings() explains what's missing
    if not ENV_FILE.exists():
        return

    for line in ENV_FILE.read_text().splitlines():
        line = line.strip()
        # Skip empty lines and comments
        if not line or line.startswith("#"):
            continue
        # Remove "export " from the start if it's there
        if line.startswith("export "):
            line = line[len("export "):]
        # Split at the first = only, in case the password itself contains an =
        name, _, value = line.partition("=")
        # Remove quotes around the value if there are any
        value = value.strip().strip("'\"")
        os.environ.setdefault(name.strip(), value) # setdefault only sets it if it isn't already set


# Builds the connection settings from the environment variables
# The password is never written in the code, same as loader.py in Milestone 2

def connection_settings():

    load_env_file()

    # Stop with a clear message if a setting is missing
    # -> before this, a missing setting made the app try MySQL on localhost and fail with a confusing "Access denied for user 'root'@'localhost'"
    missing = [name for name in REQUIRED if not os.environ.get(name)]
    if missing:
        st.error(f"Database settings not found: {', '.join(missing)}. "
                 f"Check that the .env file exists in the project folder ({PROJECT_DIR}) and has these lines.")
        st.stop() # stops the page here so nothing else tries to use the database

    # DB_SSL_CA is a path like milestone3/ca.pem, relative to the project folder
    # I join it to the project folder so it's found even when the app is started from a different folder
    ca_file = Path(os.environ["DB_SSL_CA"])
    if not ca_file.is_absolute():
        ca_file = PROJECT_DIR / ca_file

    return {
        "host": os.environ["DB_HOST"],
        "port": int(os.environ["DB_PORT"]), # Aiven uses its own port, not the usual 3306
        "user": os.environ["DB_USER"],
        "password": os.environ["DB_PASSWORD"],
        "database": "properties",
        "charset": "utf8mb4", # needed for the Arabic text
        # Aiven only accepts encrypted connections
        # ssl_ca is Aiven's CA certificate, which lets the app check it is really talking to Aiven's server
        "ssl_ca": str(ca_file),
        "ssl_verify_cert": True, # refuse to connect if the server's certificate doesn't match
    }


# Opens a small pool of connections once and reuses it for the whole app
# -> Streamlit reruns the whole script on every click, and reconnecting to Aiven every time would be slow
# @st.cache_resource makes Streamlit run this function only once and hand back the same pool after that
# I used a pool instead of one shared connection because Streamlit serves each visitor in a separate thread
# and one connection can't safely be used by two threads at the same time

@st.cache_resource
def get_pool():

    return pooling.MySQLConnectionPool(pool_name="app_pool", pool_size=5, **connection_settings())


# Runs a SELECT and returns the rows as a list of dictionaries, e.g. [{"area_name": "الشيخ زايد", "listings": 120}, etc]
# Streamlit's st.dataframe can show that directly as a table
# params fills in each %s in the SQL safely (to avoid SQL injection attacks, same as loader.py)

def run_query(sql, params=()):

    # Borrow a connection from the pool
    # If Aiven closed it because it was idle for too long, the pool reconnects it first
    conn = get_pool().get_connection()
    try:
        cursor = conn.cursor(dictionary=True) # dictionary=True gives each row with its column names
        cursor.execute(sql, params)
        rows = cursor.fetchall()
        cursor.close()
        return rows
    finally:
        # close() on a pooled connection gives it back to the pool instead of disconnecting
        # it's in finally so the connection is given back even if the query fails
        conn.close()


# Runs an INSERT / UPDATE / DELETE and commits it
# Returns the number of rows it changed
# Used for registering users and adding reviews

def run_change(sql, params=()):

    conn = get_pool().get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(sql, params)
        # Commit after every DML statement as recommended in the hidden lab
        conn.commit()
        changed = cursor.rowcount
        cursor.close()
        return changed
    except Exception:
        # Undo the half-done change if something went wrong (e.g. the username is already taken)
        # then pass the error on so the page can show it to the user
        conn.rollback()
        raise
    finally:
        conn.close()


# Runs several INSERT / UPDATE / DELETE statements as one transaction
# statements is a list of (sql, params) pairs
# Either all of them are saved or none of them are
# -> e.g. registering a user inserts into app_user and user_focuses_location, and I don't want a user saved without their focus areas if the second insert fails

def run_changes(statements):

    conn = get_pool().get_connection()
    try:
        cursor = conn.cursor()
        for sql, params in statements:
            cursor.execute(sql, params)
        # Commit only once at the end, so the statements are saved together
        conn.commit()
        cursor.close()
    except Exception:
        # If any statement fails, undo the ones before it too
        conn.rollback()
        raise
    finally:
        conn.close()
