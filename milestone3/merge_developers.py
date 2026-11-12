# Merge the different spellings of the top developers into one name each

# What this script does:
#   1. For each developer in MERGES, makes sure the developer table has the one name I picked for it
#   2. Points every development that uses one of its other spellings to that name
#   3. Deletes the other spellings from the developer table
#   4. Shows the top developers before and after

# Why: sellers type the developer name themselves, so the same developer appears as e.g. "Palm hills", "بالم هيلز", "Palmhills"
# Milestone 2 merged names that only differ in case, spacing, letter forms etc but couldn't match English to Arabic or typos
# -> the Top 5 developers page showed Palm Hills and Mountain View twice each (once in English and once in Arabic)

# Only names that clearly are that developer are merged: any spelling or language, with or without "شركة" / "Developments" etc,
# or with one of its projects or its owner's name added
# Left out on purpose:
#   - different companies with similar names (Orascom is not Ora, Arkan Palm / Palmier are not Palm Hills, Mountain Valley is not Mountain View)
#   - subsidiaries ("one of Talaat Moustafa's companies") and joint ventures ("Al Ahly Sabbour and Founders")
#   - names on their own that could be more than one company ("صبور", "عامر")

# Run using: python milestone3/merge_developers.py           (dry run: shows the result then undoes everything)
#            python milestone3/merge_developers.py --apply   (saves the changes)

import sys # to read --apply

from db import get_pool # my connection pool from db.py (it reads the settings from .env)


# The name I picked for each developer: every other spelling of it found in the data
# The picked name is the developer's usual English name
# The spellings are copied exactly from the database (SELECT developer_name FROM developer)
MERGES = {
    "Talaat Moustafa Group": [
        "طلعت مصطفى", "TMG", "مجموعة طلعت مصطفى", "هشام طلعت مصطفي", "طلعت مصطفى جروب", "طلعت مصطفي TMG",
        "TMG طلعت مصطفي", "Talaat Mostafa", "طلعت مصطفى للانشاءات", "Talaat Mostafa Group", "Talaat Mustafa",
        "مجموعة طلعت مصطفى (TMG)", "TMG - طلعت مصطفي", "مجموعة هشام طلعت مصطفى TMG", "Talaat Moustafa Group",
        "شركة طلعت مصطفى", "طلعت مصطفي - TMG", "طلعت مطفي", "مجموعة طلعت مصطفى TMG", "طلعت مصطفى عياده",
    ],
    "Palm Hills Developments": [
        "بالم هيلز", "Palm hills", "Palm hills developments", "Palmhills", "Palm Hills Development",
        "بالم هيلز الشرق الاوسط للاستثمار العقاري", "بالم هيلز - Palm Hills", "Palm hill", "Palm hills new cairo",
        "Palm hills بالم هيلز", "Palm hils", "بالم هيلز للتطوير العقاري", "شركة بالم هيلز", "ياسين منصور/بالم هيلز",
        "New Cairo Palm hills", "Palm hilles", "Palm Hills Development (PHD)", "Palm hills PHNC", "PalmHils", "Palmhilss",
        "باديا بالم هيلز", "بالم عيلز", "بالم هاليز", "بالم هلز", "بالم هليز", "بالم هيبز", "بالم هيلز Palm Hills",
        "بالم هيلز للتطوير والتنمية", "بالم هيلز نيو كايرو", "بالم هيلز نيو كيرو", "بالم هيلز. شركه جوده التجاريه",
        "بالمي هيلز", "شركة بالم هيلز الشرق الأوسط للاستثمار العقاري", "شركة بالم هيلز للتنمية السياحية والعقارية",
        "ياسين منصور - بالم هيلز",
    ],
    "Mountain View": [
        "Mountain View", "ماونتن فيو", "ماونتن ڤيو", "ماونتين فيو", "ماونت فيو", "Mountain view icity october",
        "ماونتن فيو اى سيتى التجمع", "ماونتن ڤيو - Mountain View", "mountain veiw", "ماونتن فيو راس الحكمة",
        "ماونتن فيو للتنميه والاستثمار العقاري", "ماونتين فيو - stm", "مونتين فيو - Mountain View", "Mountain Vew",
        "Mountain View I City 6 October", "Mountain View ماونتن فيو", "Mountain View ماونتن ڤيو", "Mountain view- ماونتن فيو",
        "ماوتتن ڤيو - Mountain View", "ماونتن فيو ١.١", "ماونتن فيو Mountain View", "ماونتن فيو للتطوير العقاري",
        "شركة ماونتن فيو", "شركة ماونتن فيو للتطوير العقاري (Mountain View).", "عمر سليمان شركه ماونتن فيو",
    ],
    "Madinet Masr": [
        "مدينة مصر", "شركه مدينة مصر للإسكان والتعمير", "شركة مدينة مصر", "Madinet Masr", "عبدالله سلام - مدينة مصر",
        "مدينة مصر للإسكان و التعمير", "مدينة مصر للإسكان والتعمير", "Madinet misr", "،شركة مدينة مصر",
        "Madinet Masr مدينة مصر", "Madinet Mast", "شركة مدينة مصر الإسكان والتعمير", "شركة مدينة مصر للإسكان و التعمير",
        "شركة مدينة مصر للإنشاء والتعمير", "مدينة مصر سراي", "مدينه مصر للإسكان و التعمير - Masr city",
    ],
    "Tatweer Misr": [
        "تطوير مصر", "Tatweer Misr", "شركة تطوير مصر", "شركة تطوير مصر للاستثمار السياحي واستصلاح الاراضي", "Tatweer",
        "Tatweer Mirs", "Tatweer masr", "تطوير مصر العقاري", "تطوير مصر للاستثمار السياحي", "تطوير مصر-Tateweer Misr",
        "Tatweer mast",
    ],
    "Hyde Park Developments": [
        "هايد بارك", "Hyde park", "Hdp", "Hydepark", "هايد بارك Hyde park", "هايدبارك", "Hyde Park developments",
        "هايد بارك سنترال", "شركة هايد بارك", "HHYDE PARK هايد بارك", "Hyde park development", "HydePark Developments",
        "شركة هايد بارك العقارية للتطوير", "شركه هايد بارك للتطوير العقارى", "هايد بارك سى شور", "Seashore Hyde park",
        "هايد بارك العقارية للتطوير",
    ],
    "Al Ahly Sabbour": [
        "الأهلي صبور", "Al Ahly Sabbour", "Al Ahly Sabbour Developments", "الأهلي صبور للتطوير العقاري",
        "Al Ahly Sabbour الأهلي صبور", "اهلي صبور", "الاهلى للتنمية العقارية- صبور", "شركه التطويرللاهلي صبور",
    ],
    "Ora Developers": [
        "Ora", "Ora Developers", "اورا", "اورا نجيب ساويرس", "شركة اورا للتطوير العقاري", "شركه اورا",
        "ora develovers egypt for real estate investment", "ora أورا", "اورا ايچبت", "اورا ديفلوبرز ايجيبت للاستثمار العقاري",
        "شركة اورا ديفلوبرز ايجيبت للاستثمار العقاري",
    ],
    "Orascom Development": [
        "Orascom Development", "Orascom", "اوراسكوم", "Orascom Developments", "Orascom Development Egypt", "اوراسكوم Orascom",
        "شركه اوراسكوم العقاريه ش ذ م م",
    ],
    "City Edge Developments": [
        "City Edge", "سيتي ايدج", "City Edge Developments", "شركة سيتي ايدج للتطوير العقاري", "سيتي ايدج للتطوير العقاري",
        "City Edge Development", "City Edge Devlopments- سيتي ايدج", "شركة سيتى ايدج", "سيتي ايدج العلمين الجديدة",
    ],
    "Al Marasem": [
        "المراسم", "Almarasem", "Al Marasem", "شركة المراسم", "المراسم للتطوير العقاري", "Marasem",
        "شركة المراسم الدولية للتطوير العمراني", "Al marasem development", "المراسم الدوليه للتطوير العمراني",
        "شركة المراسم للتطوير العقاري", "بن لادن المراسم", "بن لادن المراسم العقاريه",
    ],
    "IL Cazar Developments": [
        "il Cazar", "الكازار", "Ilcazar", "Ilzcazar", "El cazar", "شركة الكازار", "شركه الكازار للتطوير العقاري", "Al Cazar",
        "Elcazar", "IL Cazar Developments", "il cazar الكازار", "الكازار CAZAR",
        "الكازار للتطوير العمراني-IL Cazar Developments", "شركة الكازار للتطوير العمراني",
    ],
    "Misr Italia Properties": [
        "مصر ايطاليا", "MISR ITALIA", "شركة مصر ايطاليا", "Misr Italia Properties", "Misr Italia for Real Estate Investment",
        "Misr italis", "شركة مصر ايطاليا للاستثمار العقاري",
    ],
    "Amer Group": [
        "عامر جروب", "Amer Group", "العامر جروب", "عامر حروب", "عامرجروب",
    ],
    "Hassan Allam Properties": [
        "حسن علام", "Hassan Allam", "Hassan Allam Properties", "Hasan allam", "حسن علام - سوان ليك", "حسن علام العقاريه",
        "حسن علام شقه186 متر",
    ],
    "SODIC": [
        "Sodic", "سوديك", "Sodic east", "sodic سوديك", "سوديك استات",
    ],
    "Taj Misr": [
        "تاج مصر", "Taj Misr", "شركة تاج مصر", "تاج مصر للتطوير العقارى", "تاج مصر للتنمية العقارية", "تاج مصر taj misr",
        "شركة تاج مصر للتنمية العقارية", "Taj Misr Developments",
    ],
    "PRE Developments": [
        "pre", "PRE Development", "PRE Group", "PRE العقارية", "Pre للتطوير العقارى", "Pre (مشارق للتطوير العقاري )",
    ],
}

# The same query as the Top 5 developers page in app.py, but showing the top 10
TOP_DEVELOPERS = """
    SELECT d.developer_name, COUNT(*) AS listings
    FROM property p
    JOIN development d ON d.development_id = p.development_id
    WHERE d.developer_name IS NOT NULL
    GROUP BY d.developer_name
    ORDER BY listings DESC
    LIMIT 10
"""


# Helper functions

# Prints the top developers as a small numbered list

def print_top(cursor, title):

    cursor.execute(TOP_DEVELOPERS)
    print(title)
    for rank, (name, listings) in enumerate(cursor.fetchall(), start=1):
        print(f"  {rank:2}. {name} ({listings} listings)")


def main():

    apply = "--apply" in sys.argv

    conn = get_pool().get_connection()
    cursor = conn.cursor()

    # Check every spelling in MERGES really is in the developer table
    # -> a spelling that isn't found would just be skipped silently, so I list them to catch typos in this file
    missing = []
    for spellings in MERGES.values():
        for name in spellings:
            # BINARY compares the exact characters (my collation would also match e.g. "palm hills" to "Palm hills")
            cursor.execute("SELECT 1 FROM developer WHERE BINARY developer_name = %s", (name,))
            if not cursor.fetchall():
                missing.append(name)
    if missing:
        print("Not found in the developer table (check the spelling):", missing)

    # How many rows the tables had before, to compare at the end
    cursor.execute("SELECT COUNT(*) FROM developer")
    developers_before = cursor.fetchone()[0]

    print_top(cursor, "Top developers before:")

    # Everything from here is one transaction (mysql.connector starts one automatically, and nothing is saved until commit)
    # -> so a dry run can make all the changes, show the result, and then undo all of them with rollback
    try:
        for name, spellings in MERGES.items():
            # 1. Make sure the picked name is in the developer table
            # INSERT IGNORE does nothing if it's already there (my collation ignores case, so "SODIC" matches "Sodic")
            cursor.execute("INSERT IGNORE INTO developer (developer_name) VALUES (%s)", (name,))
            # If it was already there with different capitals, change it to the exact picked spelling
            # ON UPDATE CASCADE (from my schema) changes it in development too
            cursor.execute("UPDATE developer SET developer_name = %s WHERE developer_name = %s", (name, name))

            # 2. Point every development that uses one of the other spellings to the picked name
            # One %s per spelling, the names themselves still go through %s
            placeholders = ", ".join(["%s"] * len(spellings))
            cursor.execute(f"UPDATE development SET developer_name = %s WHERE BINARY developer_name IN ({placeholders})",
                           [name] + spellings)

            # 3. Delete the other spellings from the developer table, nothing points to them anymore
            # "developer_name <> %s" stops it from deleting the picked name itself
            # (e.g. "Sodic" is in the list but it's the same as "SODIC" in my collation)
            cursor.execute(f"DELETE FROM developer WHERE BINARY developer_name IN ({placeholders}) AND developer_name <> %s",
                           spellings + [name])

        cursor.execute("SELECT COUNT(*) FROM developer")
        developers_after = cursor.fetchone()[0]

        print_top(cursor, "Top developers after:")
        print(f"Developer table: {developers_before} rows before, {developers_after} after")

        if apply:
            conn.commit()
            print("Saved")
        else:
            conn.rollback()
            print("Dry run: nothing was saved (run with --apply to save)")
    except Exception:
        # If anything fails, undo everything so the database is never left half merged
        conn.rollback()
        raise
    finally:
        cursor.close()
        conn.close() # gives the connection back to the pool


main()
