import sqlite3



    # Connecting to the database file
conn = sqlite3.connect(r'db.sqlite')
c = conn.cursor()

# Creating a new SQLite table with 1 column
c.execute("""CREATE TABLE users
              (fullname TEXT, ID TEXT, email TEXT PRIMARY KEY , username TEXT NOT NULL, password TEXT, last INT DEFAULT 1 )""")

# Committing changes and closing the connection to the database file
conn.commit()
conn.close()
