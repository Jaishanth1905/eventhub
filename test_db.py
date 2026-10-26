import mysql.connector

try:
    conn = mysql.connector.connect(
        host="127.0.0.1",
        port=3306,
        user="root",
        password="",
        database="eventhub"
    )

    print("MySQL connected successfully!")
    print("Connected database:", conn.database)
    conn.close()

except mysql.connector.Error as err:
    print("Database connection failed:", err)