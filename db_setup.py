import sqlite3

conn = sqlite3.connect('database.db')
c = conn.cursor()

c.execute('''
CREATE TABLE IF NOT EXISTS transactions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    subject TEXT NOT NULL,
    sender TEXT NOT NULL,
    receiver TEXT NOT NULL,
    type TEXT NOT NULL,
    priority TEXT NOT NULL,
    secrecy TEXT NOT NULL,
    date TEXT NOT NULL,
    commander_signature TEXT
)
''')

conn.commit()
conn.close() 