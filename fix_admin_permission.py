import sqlite3

conn = sqlite3.connect('database.db')
c = conn.cursor()
c.execute("UPDATE users SET can_view_reports=1 WHERE username='admin'")
conn.commit()
conn.close()
print("تم إصلاح صلاحية الأدمن بنجاح!") 