# Step 2: turn the crawled listings into CSV files
# What this script does:
#   1. Reads every raw/<listing id>.json file saved by crawler.py
#   2. Pulls out each field from the listing text
#   3. Writes one CSV file per table into csv/:
#      location.csv, developer.csv, development.csv, property.csv, property_amenity.csv

# The column names in each CSV match the column names I used in Milestone1 so that loader.py can insert them straight into MySQL
# -> I found that method easier than writing a separate SQL script to insert the data
# Run using: python parser.py


import csv # to write the CSV files
import json # to read the raw .json files
import re # regular expressions -> to find values in the text
import unicodedata # to strip accents/diacritics when comparing names
from pathlib import Path # for building file paths


# Folder with the crawled listings and the folder the CSVs are written to
HERE = Path(__file__).parent
RAW_DIR = HERE / "raw"
CSV_DIR = HERE / "csv"

# Labels in the details box of a listing page
# Each label is on its own line and its value is on the next one e.g. "Bedrooms" then "3"
DETAIL_LABELS = ["Type", "Area", "Floor", "Bedrooms", "Bathrooms", "Finishing", "Completion", "Contract year", "Garden/Roof", "Price per m² (contract)"]

# Columns of the property table, in the same order as Milestone1.sql
# Much easier to keep them in sync than to write a separate SQL script to insert the data
PROPERTY_COLUMNS = [
    "listing_ref", "listing_url", "title", "description", "type", "area_name",
    "development_id", "area_sqm", "bedrooms", "bathrooms", "floor", "finishing",
    "completion_status", "garden_roof_sqm", "installments_left_years",
    "payment_method", "contract_year", "delivery_year", "down_payment",
    "remaining_amount", "installment_amount", "installment_freq", "market_price",
    "commission_pct", "gain_amount", "is_negotiable", "docs_verified",
    "is_featured", "scraped_at",
]

# Arabic digits mapped to English digits to handle cases where a number on the page is written in Arabic
ARABIC_DIGITS = str.maketrans("٠١٢٣٤٥٦٧٨٩", "0123456789")


# Helpers for cleaning values (and handling edge cases)

# Turn text like "EGP 3,409,865" or "184 م²" into a number string like "3409865" or "184"
# Returns None if there is no number
def to_number(s):

    if s is None:
        return None
    # Convert Arabic digits then find the first number (commas and a decimal point allowed)
    m = re.search(r"\d[\d,]*(?:\.\d+)?", s.translate(ARABIC_DIGITS))
    # Remove the thousands separators since MySQL accept values suh as 3409865 instead of 3,409,865
    return m.group().replace(",", "") if m else None

# Return value if low <= value <= high otherwise None
# This way a typo on the site (such as contract year 20025) doesn't break a CHECK constraint
# i.e. mirrors CHECK constaints in my SQL schema 
def in_range(value, low, high):
    return value if value is not None and low <= float(value) <= high else None

# Cut text to max_len characters so it fits its VARCHAR column
def fit(s, max_len):
    return s[:max_len].strip() if s else s

# Key used to decide whether two names are "the same"
# The site spells the same name in slightly different ways, e.g. "Palm Hills" / "palm hills" or مدينة / مدينه
# This key ignores case, extra spaces, accents and Arabic letter variants so that both spellings get the same key and are only stored once
def name_key(name):

    # Lowercase (used casefold because it also handles special letters)
    s = name.casefold()

    # NFKD splits letters from their accents/diacritics (for example: é becomes e + ´)
    s = unicodedata.normalize("NFKD", s)

    # Drops the accents or diacritics (Unicode category "Mn" = combining marks)
    s = "".join(ch for ch in s if unicodedata.category(ch) != "Mn")

    # Unify Arabic letter variants such as alef forms, ة -> ه, ى -> ي and remove the tatweel (ـ) used to stretch words
    s = s.translate(str.maketrans("أإآٱةى", "ااااهي", "ـ"))

    # Arabic digits become English digits so "ديجويا ٣" and "ديجويا 3" get the same key (MySQL also treats them as equal)
    s = s.translate(ARABIC_DIGITS)

    # Collapse multiple spaces into one and trim the ends
    return " ".join(s.split())


# Parsing one listing

# Return the first captured group of a regex in text else None if there is no match
def find(pattern, text):

    m = re.search(pattern, text)
    return m.group(1) if m else None

# Take one crawled listing (a dict from raw/*.json) and return its fields and its project, developer, and amenities
def parse_listing(record):

    # Remove invisible formatting characters (Unicode category "Cf") such as the right-to-left mark some sellers paste before Arabic text
    # MySQL ignores them when comparing, so "\u200Fالتجمع" and "التجمع" would count as the same primary key and break the insert
    # name hides an invisible right-to-left mark that Python treats as distinct from another row's identical text but MySQL ignores that mark causing a duplicate primary key
    text = "".join(ch for ch in record["text"] if unicodedata.category(ch) != "Cf")
    
    # Split the text into lines and drop the empty ones
    lines = [line.strip() for line in text.split("\n") if line.strip()]

    # Header
    # lines[0] is "Back to opportunities", lines[1] is the project name,
    # lines[2] is "developer" then "area" then "type" with "·" in between. for example: "Palm Hills · New Cairo · Apartment"
    project = lines[1]
    parts = [p.strip() for p in lines[2].split("·")]

    # The last two parts are always the area and the type
    # Anything before them is the developer (because I found that some listings don't have one)
    header_type = parts[-1]
    area = parts[-2] if len(parts) >= 2 else None
    developer = " · ".join(p for p in parts[:-2] if p) or None

    # The listing reference, for example, "U-123456" (used as the primary key in the property table)
    ref = find(r"(U-\d+)", text)

    # The badges ("Documents verified", "Featured") are shown between the header and the details box, which starts with the "Type" label
    badges = text.split("\nType\n")[0]

    # Details box (label is on one line and the value is on the next line)
    details = {} # label -> value
    last_detail = 0 # index of the last value line in the details box
    for i, line in enumerate(lines[:-1]):
        # Only take the first occurrence of each label
        # The details box comes first, so a later line with the same word (e.g. in the description) is not a detail
        if line in DETAIL_LABELS and line not in details:
            details[line] = lines[i + 1]
            last_detail = max(last_detail, i + 1)

    # Amenities -> Shown as one line
    amenities = []
    for line in lines:
        if "✓" in line:
            # Split on the ✓ and keep the names that aren't empty
            amenities += [a.strip() for a in line.split("✓") if a.strip()]

    # Description
    # The seller's free text sits between the details/amenities and the "Cash required now" box
    cash_index = lines.index("Cash required now") if "Cash required now" in lines else len(lines)
    description = "\n".join(line for line in lines[last_detail + 1:cash_index]
                            if "✓" not in line) or None

    # Money fields
    # Each regex finds a label and grabs the amount after it
    down_payment = to_number(find(r"Cash required now\s*\n\s*(EGP [\d,]+)", text))
    market_price = to_number(find(r"Market price today:?\s*(EGP [\d,]+)", text))
    remaining = to_number(find(r"Remaining with developer[^\n]*\n\s*(EGP [\d,]+)", text))
    installment = to_number(find(r"\nInstallment\s*\n\s*(EGP [\d,]+)", text))
    
    # The frequency comes after the installment amount(for example "EGP 285,555 · Quarterly")
    frequency = find(r"\nInstallment\s*\n\s*EGP [\d,]+\s*·\s*([^\n]+)", text)
    
    # The commission % is on the market price line
    commission = find(r"Market price today:[^\n]*?(\d+(?:\.\d+)?)\s*%", text)
    
    # Some listings have no market price but the % is also in the fee line (for example: "Aqar Exit buyer's fee (1.25%, on transfer completion)")
    if commission is None:
        commission = find(r"buyer's fee \((\d+(?:\.\d+)?)\s*%", text)
    
    # The gain can be positive (+) or negative (- or −) -> i found different minus signs so check for both
    gain_match = re.search(r"Your gain vs\. current market price:?\s*([+\-−])?\s*EGP ([\d,]+)", text)
    gain = None
    if gain_match:
        gain = to_number(gain_match.group(2))
        if gain_match.group(1) in ("-", "−"):
            gain = "-" + gain
    
    # Years of installments left. format found: "Instalments remaining\n9 years"
    years_left_text = find(r"Instalments remaining\s*\n\s*([^\n]+)", text)
    
    # "Fully paid" means there are no installments left
    years_left = "0" if years_left_text == "Fully paid" else to_number(years_left_text)
    
    # Delivery year. format found: "Delivery\n2029"
    delivery = to_number(find(r"\nDelivery\s*\n\s*([^\n]+)", text))

    # Build the row
    contract_year = to_number(details.get("Contract year"))
    # The <title> ends with " | Aqar Exit" so remove that part
    title = record["title"].replace(" | Aqar Exit", "")

    row = {
        "listing_ref": ref,
        "listing_url": record["url"],
        "title": fit(title, 255),
        "description": description,
        # Use the "Type" detail, or the type in the header if it's missing
        "type": fit(details.get("Type") or header_type, 50),
        "area_name": fit(area, 100),
        "development_id": None, # filled in later by main() (because the development_id is generated as we go through the listings -> surrogate key)
        "area_sqm": in_range(to_number(details.get("Area")), 0.01, 10**8),
        "bedrooms": in_range(to_number(details.get("Bedrooms")), 0, 255),
        "bathrooms": in_range(to_number(details.get("Bathrooms")), 0, 255),
        "floor": fit(details.get("Floor"), 20),
        "finishing": fit(details.get("Finishing"), 50),
        "completion_status": fit(details.get("Completion"), 50),
        "garden_roof_sqm": in_range(to_number(details.get("Garden/Roof")), 0.01, 10**8),
        "installments_left_years": in_range(years_left, 0, 255),
        # The site has no payment method field
        # Every unit is either paid off (nothing left with the developer) or still on installments
        "payment_method": None if remaining is None else
                          ("Installments" if float(remaining) > 0 else "Cash"),
        "contract_year": in_range(contract_year, 1990, 2100),
        "delivery_year": in_range(delivery, 1990, 2100),
        "down_payment": down_payment,
        "remaining_amount": remaining,
        "installment_amount": installment,
        "installment_freq": fit(frequency, 20),
        "market_price": market_price,
        "commission_pct": in_range(commission, 0, 100),
        "gain_amount": gain,
        # Booleans are stored as 1/0 which I found that MySQL reads as TRUE/FALSE
        "is_negotiable": int("Open to negotiation" in text),
        "docs_verified": int("Documents verified" in badges),
        "is_featured": int("Featured" in badges),
        # "2026-10-27T14:03:11" -> "2026-10-27 14:03:11" (from what i've seen, it's MySQL's format)
        "scraped_at": record["scraped_at"].replace("T", " "),
    }
    return row, fit(project, 150), fit(developer, 150), [fit(a, 100) for a in amenities]


# Writing the CSV files

# Write a list of dicts to csv/<name>.csv with a header row
def write_csv(name, columns, rows):

    # newline="" stops Python adding blank lines between rows
    # utf-8-sig keeps the Arabic text intact and makes Excel show it correctly
    with open(CSV_DIR / f"{name}.csv", "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=columns)
        writer.writeheader() # first line: the column names
        writer.writerows(rows) # one line per row, None becomes ""
    print(f"  {name}.csv: {len(rows)} rows")


def main():
    CSV_DIR.mkdir(exist_ok=True)

    # Lookup tables keyed by name_key() so spelling variants get merged
    # The value is the first spelling we saw which is what gets stored
    locations = {} # key -> area name
    developers = {} # key -> developer name
    developments = {} # (project key, area key) -> development row
    properties = {} # listing_ref -> property row
    amenity_rows = [] # one row per (listing, amenity) pair
    skipped = 0 # listings that couldn't be parsed

    # Read the listings in sorted order so the generated ids are the same every time the parser runs
    for path in sorted(RAW_DIR.glob("*.json")):
        record = json.loads(path.read_text(encoding="utf-8"))
        try:
            row, project, developer, amenities = parse_listing(record)
        except (IndexError, ValueError) as e:
            # A page with a layout we didn't expect so report it and move on
            print(f"  could not parse {path.name}: {e}")
            skipped += 1
            continue
        # Every property needs a reference and an area (NOT NULL in SQL)
        if not row["listing_ref"] or not row["area_name"] or row["listing_ref"] in properties:
            skipped += 1
            continue

        # Location: store each area once
        area_key = name_key(row["area_name"])
        locations.setdefault(area_key, row["area_name"])
        # Use the stored spelling so the foreign key matches exactly
        row["area_name"] = locations[area_key]

        # Developer: store each developer once (if the listing has one)
        if developer:
            developer = developers.setdefault(name_key(developer), developer)

        # Development: a project is identified by its name + area
        # (the UNIQUE (project_name, area_name) constraint)
        dev_key = (name_key(project), area_key)
        if dev_key not in developments:
            developments[dev_key] = {
                "development_id": len(developments) + 1, # 1, 2, 3, etc
                "project_name": project,
                "description": None, # the site has no project description
                "developer_name": developer,
                "area_name": row["area_name"],
            }
        # If an earlier listing of this project had no developer use this one's
        elif developments[dev_key]["developer_name"] is None:
            developments[dev_key]["developer_name"] = developer
        row["development_id"] = developments[dev_key]["development_id"]

        properties[row["listing_ref"]] = row

        # Amenities: one row per amenity without duplicates per listing
        seen = set()
        for amenity in amenities:
            if amenity and name_key(amenity) not in seen:
                seen.add(name_key(amenity))
                amenity_rows.append({"listing_ref": row["listing_ref"], "amenity": amenity})

    print(f"Parsed {len(properties)} listings ({skipped} skipped). Writing CSVs:")
    write_csv("location", ["area_name"],
              [{"area_name": a} for a in locations.values()])
    write_csv("developer", ["developer_name"],
              [{"developer_name": d} for d in developers.values()])
    write_csv("development", ["development_id", "project_name", "description",
                              "developer_name", "area_name"], developments.values())
    write_csv("property", PROPERTY_COLUMNS, properties.values())
    write_csv("property_amenity", ["listing_ref", "amenity"], amenity_rows)


if __name__ == "__main__":
    main()
