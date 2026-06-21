import sqlite3
import pandas as pd

conn = sqlite3.connect("data/claims.db")

query = """
SELECT
    claim_status,
    COUNT(*) AS claim_count,
    SUM(billed_amount) AS total_billed,
    SUM(paid_amount) AS total_paid
FROM claims
GROUP BY claim_status
"""

df = pd.read_sql_query(query, conn)

print(df)

conn.close()