# Step 1: the web app (the interface to the properties database on Aiven)

# What this script does:
#   1. Shows a sidebar menu with the 10 features the spec asks for
#   2. Runs the page that was picked, which reads from or writes to the database through db.py

# Run using: streamlit run milestone3/app.py
# (then open the link it prints, http://localhost:8501)
# The database settings are read from .env by db.py

import datetime # for the birthdate limits

import mysql.connector # only used here to catch database errors and show a friendly message
import streamlit as st # builds the web pages

from db import run_query, run_changes, run_change # my helper functions for talking to MySQL


# The browser tab title and a wide layout so the tables have room
st.set_page_config(page_title="Resale Properties", layout="wide")


# SQL pieces reused by the analytics pages
# p is the property table in every query that uses them
# These are fixed text written by me, never typed in by a user, so putting them into the SQL with an f-string is safe
# (anything a user types still goes through %s)

# Price and price per m2 as defined in ASSUMPTIONS.txt
# -> my schema doesn't store the total price, it's down payment + remaining with the developer (Milestone 2 assumptions)
PRICE = "(p.down_payment + p.remaining_amount)"
PRICE_PER_SQM = f"({PRICE} / p.area_sqm)"

# The columns shown for each listing on the pages that list properties
# The names in backticks are the column headings shown in the app
# -> backticks and not double quotes, because Aiven runs MySQL in ANSI mode where "..." means a column name not text
LISTING_COLUMNS = f"""
    p.listing_ref AS `Ref`,
    d.project_name AS `Project`,
    p.type AS `Type`,
    p.area_sqm AS `Area (m²)`,
    p.bedrooms AS `Beds`,
    p.bathrooms AS `Baths`,
    {PRICE} AS `Price (EGP)`,
    ROUND({PRICE_PER_SQM}) AS `Price / m² (EGP)`,
    p.down_payment AS `Down payment (EGP)`,
    p.contract_year AS `Contract year`,
    p.listing_url AS `Listing`
"""

# property joined to its development, for the project name
# LEFT JOIN because development_id is allowed to be NULL in my schema (a property that isn't in a project would still show)
LISTINGS_FROM = """
    FROM property p
    LEFT JOIN development d ON d.development_id = p.development_id
"""


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


# Shows query results as a table
# Prices get thousands separators (e.g. 3,132,700) and the listing link becomes clickable

def show_table(rows):

    if not rows:
        st.info("Nothing matches")
        return

    config = {}
    for column in rows[0]:
        # Find the first row where this column has a value (it can be NULL in some rows)
        value = next((row[column] for row in rows if row[column] is not None), None)
        # Decimal numbers (prices, areas, averages) are floats here, see run_query in db.py
        if isinstance(value, float):
            config[column] = st.column_config.NumberColumn(format="localized")
        # Whole numbers (contract year, beds, etc) are shown with no separators and no decimals
        # -> so 2024 doesn't show as 2,024, and a column with some NULLs doesn't show as 2024.0
        # (bool is left out because Python counts True / False as whole numbers too)
        elif isinstance(value, int) and not isinstance(value, bool):
            config[column] = st.column_config.NumberColumn(format="%d")

    if "Listing" in rows[0]:
        config["Listing"] = st.column_config.LinkColumn(display_text="Open on AqarExit")

    st.dataframe(rows, hide_index=True, width="stretch", column_config=config)


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


# Every property type with its number of listings, e.g. {"شقة": 4551, "شاليه": 1382, etc}, most common first

@st.cache_data(ttl=3600)
def load_types():

    rows = run_query("SELECT type, COUNT(*) AS listings FROM property GROUP BY type ORDER BY listings DESC")
    return {row["type"]: row["listings"] for row in rows}


# Every area that has listings, with its number of listings, most listings first
# Different from load_areas() -> that one is every location, including ones only used for users' focus areas

@st.cache_data(ttl=3600)
def load_listing_areas():

    rows = run_query("SELECT area_name, COUNT(*) AS listings FROM property GROUP BY area_name ORDER BY listings DESC")
    return {row["area_name"]: row["listings"] for row in rows}


# Every amenity with its number of listings, most common first
# HAVING COUNT(*) > 1 leaves out 2 entries that are really pieces of a listing's description
# that ended up in the amenities list in Milestone 2 (each appears on only one listing, see ASSUMPTIONS.txt)

@st.cache_data(ttl=3600)
def load_amenities():

    rows = run_query("""
        SELECT amenity, COUNT(*) AS listings
        FROM property_amenity
        GROUP BY amenity
        HAVING COUNT(*) > 1
        ORDER BY listings DESC
    """)
    return {row["amenity"]: row["listings"] for row in rows}


# Average price per m2 and number of listings for each unit type
# where is the condition (e.g. "p.area_name = %s") and params fills its %s
# Used by the development page and the area page

def type_summary(where, params):

    return run_query(f"""
        SELECT p.type AS `Unit type`,
               COUNT(*) AS `Listings`,
               ROUND(AVG({PRICE_PER_SQM})) AS `Avg price / m² (EGP)`
        FROM property p
        WHERE {where}
        GROUP BY p.type
        ORDER BY `Listings` DESC
    """, params)


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


# Top 10 projects with the highest resale inventory, resale amount and gain over market value, by property type
# Three separate top 10 lists for the type that is picked

def page_top_projects():

    st.header("Top 10 projects by property type")

    types = load_types()
    property_type = st.selectbox("Property type", list(types),
                                 format_func=lambda t: f"{t} ({types[t]:,} listings)")

    # Highest resale inventory = the most listings of this type
    # GROUP BY d.development_id and not project_name -> the same project name can exist in two areas
    # MySQL allows selecting project_name etc while grouping by development_id because development_id is the primary key
    # Ties are broken by project name so the order is always the same
    st.subheader("Highest resale inventory")
    show_table(run_query("""
        SELECT d.project_name AS `Project`, d.area_name AS `Area`, d.developer_name AS `Developer`,
               COUNT(*) AS `Listings`
        FROM property p
        JOIN development d ON d.development_id = p.development_id
        WHERE p.type = %s
        GROUP BY d.development_id
        ORDER BY `Listings` DESC, d.project_name
        LIMIT 10
    """, (property_type,)))

    # Highest resale amount = the total price of all the project's listings of this type
    st.subheader("Highest resale amount")
    show_table(run_query(f"""
        SELECT d.project_name AS `Project`, d.area_name AS `Area`, d.developer_name AS `Developer`,
               SUM({PRICE}) AS `Resale amount (EGP)`,
               COUNT(*) AS `Listings`
        FROM property p
        JOIN development d ON d.development_id = p.development_id
        WHERE p.type = %s
        GROUP BY d.development_id
        ORDER BY `Resale amount (EGP)` DESC, d.project_name
        LIMIT 10
    """, (property_type,)))

    # Highest gain over market value = the highest AVERAGE gain per listing, not the total
    # -> a total would mostly repeat the inventory list above (see ASSUMPTIONS.txt)
    # Listings with no market price have no gain, so they are left out here
    st.subheader("Highest gain over market value (average per listing)")
    show_table(run_query("""
        SELECT d.project_name AS `Project`, d.area_name AS `Area`, d.developer_name AS `Developer`,
               ROUND(AVG(p.gain_amount)) AS `Avg gain (EGP)`,
               COUNT(*) AS `Listings with a market price`
        FROM property p
        JOIN development d ON d.development_id = p.development_id
        WHERE p.type = %s AND p.gain_amount IS NOT NULL
        GROUP BY d.development_id
        ORDER BY `Avg gain (EGP)` DESC, d.project_name
        LIMIT 10
    """, (property_type,)))


# The location of a given development, with the average price per m2 and number of listings for each unit type

def page_development():

    st.header("Development details")

    developments = load_developments()
    development_id = st.selectbox("Project", list(developments), format_func=developments.get,
                                  index=None, placeholder="Type to search")
    if development_id is None:
        return

    # The project's location and developer, plus its total number of listings
    # LEFT JOIN so a project with no listings still comes back (with 0)
    info = run_query("""
        SELECT d.project_name, d.area_name, d.developer_name, COUNT(p.listing_ref) AS listings
        FROM development d
        LEFT JOIN property p ON p.development_id = d.development_id
        WHERE d.development_id = %s
        GROUP BY d.development_id
    """, (development_id,))[0]

    st.subheader(info["project_name"])
    location, developer, listings = st.columns(3)
    location.metric("Location", info["area_name"])
    developer.metric("Developer", info["developer_name"] or "Not listed")
    listings.metric("Listings", info["listings"])

    st.subheader("By unit type")
    show_table(type_summary("p.development_id = %s", (development_id,)))


# All the properties in a certain area, with the average price per m2 for each unit type

def page_area():

    st.header("Properties in an area")

    areas = load_listing_areas()
    area = st.selectbox("Area", list(areas), format_func=lambda a: f"{a} ({areas[a]:,} listings)",
                        index=None, placeholder="Type to search")
    if area is None:
        return

    st.subheader("Average price per m² by unit type")
    show_table(type_summary("p.area_name = %s", (area,)))

    # Every listing in the area, cheapest first
    st.subheader(f"All {areas[area]:,} properties")
    show_table(run_query(f"""
        SELECT {LISTING_COLUMNS}
        {LISTINGS_FROM}
        WHERE p.area_name = %s
        ORDER BY `Price (EGP)`
    """, (area,)))


# All the properties in a certain area in a given price range, with a given set of amenities

def page_search():

    st.header("Search by area, price and amenities")

    areas = load_listing_areas()
    area = st.selectbox("Area", list(areas), format_func=lambda a: f"{a} ({areas[a]:,} listings)",
                        index=None, placeholder="Type to search")
    if area is None:
        return

    # Start the price range at the area's cheapest and most expensive listing so nothing is cut off at first
    limits = run_query(f"SELECT MIN({PRICE}) AS low, MAX({PRICE}) AS high FROM property p WHERE p.area_name = %s",
                       (area,))[0]
    low_col, high_col = st.columns(2)
    # step=100000 makes the + / - buttons move in 100K steps, since prices are in the millions
    min_price = low_col.number_input("Min price (EGP)", min_value=0.0, value=limits["low"], step=100000.0, format="%.0f")
    max_price = high_col.number_input("Max price (EGP)", min_value=0.0, value=limits["high"], step=100000.0, format="%.0f")

    amenities_list = load_amenities()
    amenities = st.multiselect("Must have all of these amenities", list(amenities_list),
                               format_func=lambda a: f"{a} ({amenities_list[a]:,} listings)")

    # The area and price range
    # BETWEEN includes both ends, so a listing at exactly the max price is included
    sql = f"""
        SELECT {LISTING_COLUMNS}
        {LISTINGS_FROM}
        WHERE p.area_name = %s AND {PRICE} BETWEEN %s AND %s
    """
    params = [area, min_price, max_price]

    # Only listings that have ALL the picked amenities
    # The subquery finds the listings that have any of them, then HAVING keeps the ones that matched every one
    # COUNT(*) works because my primary key (listing_ref, amenity) means a listing can't have the same amenity twice
    # I build one %s per amenity -> the number of %s is the only thing that changes, the amenity names still go through %s
    if amenities:
        placeholders = ", ".join(["%s"] * len(amenities))
        sql += f"""
          AND p.listing_ref IN (
              SELECT pa.listing_ref
              FROM property_amenity pa
              WHERE pa.amenity IN ({placeholders})
              GROUP BY pa.listing_ref
              HAVING COUNT(*) = %s
          )
        """
        params += amenities + [len(amenities)]

    sql += " ORDER BY `Price (EGP)`"

    rows = run_query(sql, params)
    st.subheader(f"{len(rows):,} properties found")
    show_table(rows)


# Placeholder for the features that aren't built yet

def page_coming_soon():

    st.info("Coming soon")


# The sidebar menu: one entry per feature in the spec, in the same order
PAGES = {
    "Register a user": page_register,
    "Add a review": page_add_review,
    "View reviews of a project": page_view_reviews,
    "Top 10 projects by property type": page_top_projects,
    "Development details": page_development,
    "Properties in an area": page_area,
    "Search by area, price and amenities": page_search,
    "Top 5 developers": page_coming_soon,
    "Properties by area, type and contract year": page_coming_soon,
    "Area and project averages": page_coming_soon,
}

st.sidebar.title("Resale Properties")
choice = st.sidebar.radio("Pick a feature", list(PAGES))

# Run the page that was picked
PAGES[choice]()
