import sqlite3

con = sqlite3.connect('my_db.db')
cur = con.cursor()
cur.execute("SELECT COUNT(*) FROM tb_event WHERE UPPER(description) = 'TENIS'")
total = cur.fetchone()[0]
cur.execute("SELECT COUNT(*) FROM tb_event WHERE UPPER(description) = 'TENIS' AND (grouped IS NULL OR grouped = '')")
nulls = cur.fetchone()[0]
print(f"Total TENIS rows: {total}")
print(f"TENIS rows with NULL/empty grouped: {nulls}")
print()
cur.execute("SELECT grouped, COUNT(*) as n FROM tb_event WHERE UPPER(description) = 'TENIS' GROUP BY grouped ORDER BY n DESC")
for row in cur.fetchall():
    print(f"  grouped={repr(row[0])}  count={row[1]}")

print()
print("--- Overall NULL grouped ---")
cur.execute("SELECT COUNT(*) FROM tb_event WHERE grouped IS NULL OR grouped = ''")
print(f"Total rows with NULL/empty grouped: {cur.fetchone()[0]:,} out of 23,427")
con.close()
