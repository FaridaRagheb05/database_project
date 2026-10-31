# Step 3: generate sample data for the user tables

# user tables should be filled with sample test data because only the property tables come from the website

# What this script does:
#   1. Makes up users, their areas of focus, and their reviews of real development projects
#   2. Writes them to csv/app_user.csv, csv/user_focuses_location.csv and csv/review.csv

# Guide:
# Run after parser.py because it picks areas and projects from csv/location.csv and csv/development.csv -> need to create those first
# Run using python sample_users.py

import csv # to read and write the CSV files
import random # to generate random sample data
from datetime import date, datetime, timedelta # for birthdates and timestamps
from pathlib import Path # for building file paths


CSV_DIR = Path(__file__).parent / "csv"

NUM_USERS = 60 # how many sample users to create
MAX_FOCUS_AREAS = 3 # each user focuses on 1-3 areas
MAX_REVIEWS_PER_USER = 6 # each user reviews 0-6 projects

# A fixed seed so the CSVs don't change each time the script is run
random.seed(2026)

# Names used to build usernames like "mariam_hassan42"
FIRST_NAMES = ["ahmed", "mohamed", "omar", "youssef", "karim", "mostafa", "ali",
               "hassan", "mariam", "nour", "salma", "farida", "laila", "hana",
               "yasmin", "dina", "aya", "malak", "tarek", "sherif"]
LAST_NAMES = ["hassan", "ibrahim", "mahmoud", "ali", "fathy", "kamal", "saeed",
              "nabil", "adel", "samir", "gamal", "ragab", "zaki", "fouad"]

# Review texts grouped by how good the rating is
# Review texts generated using AI but I made sure they were realistic and not too generic
REVIEWS = {
    "good": ["Great project, delivered on time and well maintained.",
             "Very good location and the compound is quiet.",
             "Excellent amenities, worth the price.",
             "مشروع ممتاز والتسليم في الميعاد",
             "الخدمات كويسة جدا والكمبوند هادي"],
    "ok":   ["Decent project but the payment plan is long.",
             "Good location, finishing quality could be better.",
             "Average experience, some delays in construction.",
             "المشروع كويس بس فيه تأخير في التسليم"],
    "bad":  ["Delivery was delayed by more than a year.",
             "Customer service from the developer was poor.",
             "Not worth the price compared to nearby projects.",
             "تأخير كبير في التسليم وخدمة العملاء سيئة"],
}


# Helper functions

# Read csv/<name>.csv and return its rows as a list of dicts
def read_csv(name):

    # utf-8-sig because parser.py writes the CSVs that way so that Excel shows the Arabic correctly
    with open(CSV_DIR / f"{name}.csv", newline="", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))

# Write a list of dicts to csv/<name>.csv with a header row
def write_csv(name, columns, rows):

    with open(CSV_DIR / f"{name}.csv", "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)
    print(f"  {name}.csv: {len(rows)} rows")

# Return a random datetime between start and end
def random_datetime(start, end):

    seconds = int((end - start).total_seconds())
    return start + timedelta(seconds=random.randint(0, seconds))

# Format a datetime the way MySQL expects it: 2026-10-27 14:03:11
def fmt(dt):

    return dt.strftime("%Y-%m-%d %H:%M:%S")


def main():
    # Real areas and projects from the crawl so the foreign keys are valid
    areas = [row["area_name"] for row in read_csv("location")]
    development_ids = [row["development_id"] for row in read_csv("development")]

    users, focuses, reviews = [], [], []
    usernames = set() # to keep usernames unique (UNIQUE constraint)
    now = datetime(2026, 10, 27)

    for _ in range(NUM_USERS):
        # User
        # Build a username like "salma_kamal17" that isn't taken yet
        while True:
            username = f"{random.choice(FIRST_NAMES)}_{random.choice(LAST_NAMES)}{random.randint(1, 99)}"
            if username not in usernames:
                usernames.add(username)
                break
        
        # i foudn recommended to use example.com because it's reserved for examples so that emails can't belong to a real person
        email = f"{username}@example.com"
        # Users aged roughly 21 to 65
        birthdate = date(random.randint(1961, 2005), random.randint(1, 12), random.randint(1, 28))
        # Registered at some point in the last two years
        created_at = random_datetime(datetime(2024, 11, 1), now)
        users.append({
            "email": email,
            "username": username,
            # Has to be one of the ENUM values in the app_user table
            "gender": random.choices(["Male", "Female", "Other"], weights=[48, 48, 4])[0],
            "birthdate": birthdate.isoformat(), # for example 1998-04-17
            "created_at": fmt(created_at),
        })

        # Areas of focus
        # random.sample picks different areas so there are no duplicate (email, area) pairs (because those would break the primary key)
        for area in random.sample(areas, k=random.randint(1, min(MAX_FOCUS_AREAS, len(areas)))):
            focuses.append({"email": email, "area_name": area})

        # Reviews
        # Different projects per user since it's one review per user per project
        # to satisfy the UNIQUE (email, development_id) constraint
        k = random.randint(0, min(MAX_REVIEWS_PER_USER, len(development_ids)))
        for dev_id in random.sample(development_ids, k=k):
            rating = random.randint(1, 10) # CHECK: rating between 1 and 10
            # Pick a text that matches the rating 
            mood = "good" if rating >= 8 else "ok" if rating >= 5 else "bad"
            reviews.append({
                "review_id": len(reviews) + 1, # 1, 2, 3, ...
                "rating": rating,
                # Some users leave a rating with no text (review_text is NULL)
                "review_text": random.choice(REVIEWS[mood]) if random.random() < 0.8 else None,
                # A review is posted after the user registered
                "posted_at": fmt(random_datetime(created_at, now)),
                "development_id": dev_id,
                "email": email,
            })

    print("Writing sample user CSVs:")
    write_csv("app_user", ["email", "username", "gender", "birthdate", "created_at"], users)
    write_csv("user_focuses_location", ["email", "area_name"], focuses)
    write_csv("review", ["review_id", "rating", "review_text", "posted_at",
                         "development_id", "email"], reviews)

if __name__ == "__main__":
    main()
