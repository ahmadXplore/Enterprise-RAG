import sqlite3

conn = sqlite3.connect('enterprise_rag_dev.db')
tables = conn.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name").fetchall()
print('Tables:', [t[0] for t in tables])
roles = conn.execute('SELECT name, description FROM roles').fetchall()
print('Roles seeded:', roles)
conn.close()
