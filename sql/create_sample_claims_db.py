import sqlite3

conn = sqlite3.connect("data/claims.db")
cursor = conn.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS claims (
    claim_id TEXT PRIMARY KEY,
    member_id TEXT,
    provider_id TEXT,
    claim_type TEXT,
    product_type TEXT,
    service_month TEXT,
    claim_status TEXT,
    denial_reason TEXT,
    billed_amount REAL,
    paid_amount REAL
)
""")

sample_data = [
    ("C001", "M001", "P001", "Professional", "Medi-Cal", "2026-01", "Paid", None, 500, 420),
    ("C002", "M002", "P002", "Institutional", "Medi-Cal", "2026-01", "Denied", "Missing Authorization", 1200, 0),
    ("C003", "M003", "P001", "Professional", "Medicare", "2026-02", "Paid", None, 300, 250),
    ("C004", "M004", "P003", "Pharmacy", "Medi-Cal", "2026-02", "Denied", "Invalid NDC", 150, 0),
    ("C005", "M005", "P002", "Institutional", "Commercial", "2026-03", "Paid", None, 2000, 1600),
    ("C006", "M006", "P004", "Professional", "Medi-Cal", "2026-03", "Denied", "Member Not Eligible", 700, 0),
    ("C007", "M007", "P005", "Pharmacy", "Medicare", "2026-03", "Paid", None, 90, 75)
]

cursor.executemany("""
INSERT OR REPLACE INTO claims VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
""", sample_data)

conn.commit()
conn.close()

print("Sample claims database created successfully.")