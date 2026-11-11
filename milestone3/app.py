# Step 1: the web app (the interface to the properties database on Aiven)

# What this script does:
#   1. Shows a sidebar menu with the 10 features the spec asks for
#   2. Runs the page that was picked, which reads from or writes to the database through db.py

# Run using: source .env && streamlit run milestone3/app.py
# (then open the link it prints, http://localhost:8501)

import datetime # for the birthdate limits

import mysql.connector # only used here to catch database errors and show a friendly message
import streamlit as st # builds the web pages

from db import run_query, run_changes, run_change # my helper functions for talking to MySQL


# The browser tab title and a wide layout so the tables have room
st.set_page_config(page_title="Resale Properties", layout="wide")


# Helper functions

# Turns a MySQL error into a message a user would understand
# The database already enforces the rules (UNIQUE, CHECK and FOREIGN KEY constraints in my Milestone 1 schema)
# so the app doesn't repeat those checks, it just explains which rule was broken

def friendly_error(err):

    message = err.msg

    # 1062 = duplicate value in a PRIMARY KEY or UNIQUE column
    # the message names the constraint, e.g. "Duplicate entry 'farida' for key 'app_user.uq_app_user_username'"
    if err.errno == 1062:
        if "uq_app_user_username" in message:
            return "That username is already taken"
        if "uq_review_app_user_dev" in message:
            return "You've already reviewed this project (one review per user per project)"
        if "app_user.PRIMARY" in message:
            return "An account with that email already exists"

    # 3819 = a CHECK constraint failed
    if err.errno == 3819:
        if "chk_user_email" in message:
            return "That doesn't look like a valid email address"
        if "chk_review_rating" in message:
            return "The rating has to be between 1 and 10"

    # 1452 = a FOREIGN KEY points to a row that doesn't exist (e.g. reviewing with an email that isn't registered)
    if err.errno == 1452:
        return "That email isn't registered yet, please register first"

    # Anything else is shown as MySQL wrote it
    return f"Database error: {message}"


# Area names for the focus-area picker
# @st.cache_data keeps the result for an hour so the list isn't fetched from Aiven on every click
# -> the areas only change if the site is crawled again

@st.cache_data(ttl=3600)
def load_areas():

    rows = run_query("SELECT area_name FROM location ORDER BY area_name")
    return [row["area_name"] for row in rows]


# Every development project as {development_id: "project name — area"}
# The area is shown next to the name because the same project name can appear in two areas (my UNIQUE is on project_name + area_name)

@st.cache_data(ttl=3600)
def load_developments():

    rows = run_query("SELECT development_id, project_name, area_name FROM development ORDER BY project_name")
    return {row["development_id"]: f"{row['project_name']} — {row['area_name']}" for row in rows}


# Pages

# Register a user
# The spec asks for email, username, gender, age, birthdate and main areas of focus
# Age isn't typed in -> it's worked out from the birthdate by the v_user view in my schema, so it never goes out of date

def page_register():

    st.header("Register a user")

    areas = load_areas()

    # st.form groups the inputs so the page only reruns when Register is clicked, not after every keystroke
    with st.form("register"):
        email = st.text_input("Email", max_chars=255) # max_chars mirrors VARCHAR(255) in my schema
        username = st.text_input("Username", max_chars=50) # VARCHAR(50)
        gender = st.selectbox("Gender", ["Male", "Female", "Other"]) # the same values as the ENUM in my schema
        # value=None starts it empty so nobody registers with today's date by accident
        # Streamlit's default earliest date is only 10 years ago, so I set it to 1920
        birthdate = st.date_input("Birthdate", value=None,
                                  min_value=datetime.date(1920, 1, 1), max_value=datetime.date.today())
        focus = st.multiselect("Main areas of focus", areas)
        submitted = st.form_submit_button("Register")

    # Nothing else to do until the button is clicked
    if not submitted:
        return

    # Remove spaces typed by accident at the start or end
    email = email.strip()
    username = username.strip()

    # Check the required fields here, because an empty text box is "" (not NULL) so NOT NULL wouldn't catch it
    if not email or not username or birthdate is None or not focus:
        st.error("Please fill in the email, username, birthdate and at least one area of focus")
        return

    # The user row first, then one row per focus area (the foreign key needs the user to exist first)
    statements = [("INSERT INTO app_user (email, username, gender, birthdate) VALUES (%s, %s, %s, %s)",
                   (email, username, gender, birthdate))]
    for area in focus:
        statements.append(("INSERT INTO user_focuses_location (email, area_name) VALUES (%s, %s)",
                           (email, area)))

    # run_changes saves all of them together or none of them
    try:
        run_changes(statements)
    except mysql.connector.Error as err:
        st.error(friendly_error(err))
        return

    # Read the new user back through v_user to show the age the database worked out
    user = run_query("SELECT username, age FROM v_user WHERE email = %s", (email,))[0]
    st.success(f"Registered {user['username']} (age {user['age']}) with {len(focus)} area(s) of focus")


# Add a new user review on a project
# There's no login -> the spec only asks for registration, so the user types the email they registered with

def page_add_review():

    st.header("Add a review")

    developments = load_developments()

    with st.form("add_review"):
        email = st.text_input("Your email (the one you registered with)")
        # options are the ids, format_func shows the name instead -> so two projects with the same label still stay separate
        # index=None starts it empty, and the user can type to search the 4,500+ projects
        development_id = st.selectbox("Project", list(developments), format_func=developments.get,
                                      index=None, placeholder="Type to search")
        rating = st.slider("Rating", min_value=1, max_value=10, value=5) # 1-10 as in the spec and my CHECK constraint
        review_text = st.text_area("Review (optional)")
        submitted = st.form_submit_button("Submit review")

    if not submitted:
        return

    email = email.strip()
    if not email or development_id is None:
        st.error("Please enter your email and pick a project")
        return

    # Check the email is registered first, so the user gets a clear message
    # (the foreign key would also reject it, friendly_error covers that too)
    user = run_query("SELECT username FROM app_user WHERE email = %s", (email,))
    if not user:
        st.error("That email isn't registered yet, please register first")
        return

    # An empty review box is stored as NULL, same as the sample reviews with no text from Milestone 2
    try:
        run_change("INSERT INTO review (rating, review_text, development_id, email) VALUES (%s, %s, %s, %s)",
                   (rating, review_text.strip() or None, development_id, email))
    except mysql.connector.Error as err:
        st.error(friendly_error(err))
        return

    st.success(f"Thanks {user[0]['username']}, your review of {developments[development_id]} was added")


# View existing reviews of a project

def page_view_reviews():

    st.header("View reviews of a project")

    developments = load_developments()

    # Most projects have no reviews yet, so by default only list the ones that do
    # This list isn't cached -> a review added a second ago should show up straight away
    only_reviewed = st.checkbox("Only list projects that have reviews", value=True)
    if only_reviewed:
        rows = run_query("SELECT DISTINCT development_id FROM review")
        options = sorted((row["development_id"] for row in rows), key=developments.get)
    else:
        options = list(developments)

    development_id = st.selectbox("Project", options, format_func=developments.get,
                                  index=None, placeholder="Type to search")
    if development_id is None:
        return

    # The project's developer and area, plus the review count and average rating worked out by MySQL
    # LEFT JOIN so a project with no reviews still comes back (with 0 reviews)
    summary = run_query("""
        SELECT d.project_name, d.area_name, d.developer_name,
               COUNT(r.review_id) AS reviews,
               ROUND(AVG(r.rating), 1) AS avg_rating
        FROM development d
        LEFT JOIN review r ON r.development_id = d.development_id
        WHERE d.development_id = %s
        GROUP BY d.development_id
    """, (development_id,))[0]

    st.subheader(summary["project_name"])
    st.caption(f"{summary['area_name']} · developer: {summary['developer_name'] or 'not listed'}")

    if summary["reviews"] == 0:
        st.info("No reviews yet")
        return

    # Show the two numbers side by side
    left, right = st.columns(2)
    left.metric("Average rating", f"{summary['avg_rating']} / 10")
    right.metric("Reviews", summary["reviews"])

    # The reviews themselves, newest first
    # I show the username and not the email -> other visitors shouldn't see people's emails
    reviews = run_query("""
        SELECT u.username, r.rating, r.review_text, r.posted_at
        FROM review r
        JOIN app_user u ON u.email = r.email
        WHERE r.development_id = %s
        ORDER BY r.posted_at DESC
    """, (development_id,))
    st.dataframe(reviews, hide_index=True, width="stretch") # width="stretch" makes the table fill the page


# Placeholder for the features that aren't built yet

def page_coming_soon():

    st.info("Coming soon")


# The sidebar menu: one entry per feature in the spec, in the same order
PAGES = {
    "Register a user": page_register,
    "Add a review": page_add_review,
    "View reviews of a project": page_view_reviews,
    "Top 10 projects by property type": page_coming_soon,
    "Development details": page_coming_soon,
    "Properties in an area": page_coming_soon,
    "Search by price and amenities": page_coming_soon,
    "Top 5 developers": page_coming_soon,
    "Properties by area, type and contract year": page_coming_soon,
    "Area and project averages": page_coming_soon,
}

st.sidebar.title("Resale Properties")
choice = st.sidebar.radio("Pick a feature", list(PAGES))

# Run the page that was picked
PAGES[choice]()
