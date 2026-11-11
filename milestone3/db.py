# Database connection used by every page of the app

# What this file does:
#   1. Connects to the "properties" database using the settings in DB_HOST / DB_PORT / DB_USER / DB_PASSWORD / DB_SSL_CA
#   2. Gives the app run_query() for SELECTs, run_change() for one INSERT and run_changes() for several INSERTs that belong together

# Not run directly -> app.py imports it
# With no settings it connects to the local database (handy while building the app before it's moved to Aiven)

import os # to read the DB_HOST / DB_PORT / DB_USER / DB_PASSWORD / DB_SSL_CA settings

import mysql.connector
from mysql.connector import pooling # keeps a few connections open so they can be reused
import streamlit as st # only used here for st.cache_resource


# Helper functions

# Builds the connection settings from the environment variables
# The password is never written in the code, same as loader.py in Milestone 2

def connection_settings():

    settings = {
        "host": os.environ.get("DB_HOST", "localhost"),
        "port": int(os.environ.get("DB_PORT", "3306")), # Aiven uses its own port, not the usual 3306
        "user": os.environ.get("DB_USER", "root"),
        "password": os.environ.get("DB_PASSWORD", ""),
        "database": "properties",
        "charset": "utf8mb4", # needed for the Arabic text
    }

    # Aiven only accepts encrypted connections
    # DB_SSL_CA is the path to Aiven's CA certificate, which lets the app check it is really talking to Aiven's server
    ca_file = os.environ.get("DB_SSL_CA")
    if ca_file:
        settings["ssl_ca"] = ca_file
        settings["ssl_verify_cert"] = True # refuse to connect if the server's certificate doesn't match

    return settings


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
