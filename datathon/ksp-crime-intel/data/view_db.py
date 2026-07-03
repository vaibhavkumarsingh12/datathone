import sqlite3
import pandas as pd

conn = sqlite3.connect('output/crime.db')
tables = pd.read_sql("SELECT name FROM sqlite_master WHERE type='table';", conn)

print('## Tables in crime.db')
for table in tables['name']:
    c = pd.read_sql(f"SELECT count(*) as c FROM {table}", conn).iloc[0]['c']
    print(f'- **{table}**: {c} rows')

print('\n## Sample from CaseMaster (first 3 rows)')
print(pd.read_sql("SELECT CaseMasterID, CrimeNo, CrimeRegisteredDate, CrimeMinorHeadID, BriefFacts FROM CaseMaster LIMIT 3", conn).to_markdown(index=False))

print('\n## Sample from Accused (first 3 rows)')
print(pd.read_sql("SELECT AccusedMasterID, CaseMasterID, AccusedName, AgeYear, PersonID FROM Accused LIMIT 3", conn).to_markdown(index=False))

print('\n## Sample from ArrestSurrender (first 3 rows)')
print(pd.read_sql("SELECT * FROM ArrestSurrender LIMIT 3", conn).to_markdown(index=False))
