import sqlite3
import pandas as pd
import os

conn = sqlite3.connect("data/synthea.db")

csv_folder = "data/synthea_csv"

csv_files = [
    "allergies.csv",
    "careplans.csv",
    "claims_transactions.csv",
    "claims.csv",
    "conditions.csv",
    "devices.csv",
    "encounters.csv",
    "imaging_studies.csv",
    "immunizations.csv",
    "medications.csv",
    "observations.csv",
    "organizations.csv",
    "patients.csv",
    "payer_transitions.csv",
    "payers.csv",
    "procedures.csv",
    "providers.csv",
    "supplies.csv"
]

for file_name in csv_files:
    table_name = file_name.replace(".csv", "")
    file_path = os.path.join(csv_folder, file_name)

    print(f"Loading {table_name}...")

    df = pd.read_csv(file_path)

    df.to_sql(
        table_name,
        conn,
        if_exists="replace",
        index=False
    )

print("Enterprise healthcare database created successfully.")

conn.close()