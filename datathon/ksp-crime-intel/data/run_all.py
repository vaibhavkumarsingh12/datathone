# run_all.py — runs phases 1-4 in order, then packs all public CSVs into one SQLite file.
import sqlite3, glob, os
import pandas as pd
import config as C
import phase1_world, phase2_people, phase3_cases, phase4_accused

def main():
    phase1_world.build_world()
    phase2_people.build_people()
    phase3_cases.build_cases()
    phase4_accused.build_accused()

    # pack PUBLIC csvs -> crime.db (this is what the Streamlit app will read)
    db = C.OUT / "crime.db"
    if db.exists(): os.remove(db)
    conn = sqlite3.connect(db)
    for path in glob.glob(str(C.OUT / "*.csv")):
        name = os.path.splitext(os.path.basename(path))[0]
        pd.read_csv(path).to_sql(name, conn, if_exists="replace", index=False)
    conn.close()
    print(f"\nAll done. Public DB: {db}")
    print("Reminder: ground_truth/ is your SECRET answer key — never load it into the app.")

if __name__ == "__main__":
    main()
