import os
import sys

import psycopg
from dotenv import load_dotenv

load_dotenv()

url = os.environ.get("DATABASE_URL")
if not url:
    sys.exit("DATABASE_URL is not set. Check your .env file.")

try:
    with psycopg.connect(url, connect_timeout=15) as conn:
        version = conn.execute("select version()").fetchone()[0]
        user, database = conn.execute("select current_user, current_database()").fetchone()
        print("Connected!")
        print("Server  :", version.split(",")[0])
        print("User/DB :", user, "/", database)
except psycopg.OperationalError as e:
    # Print only the first line of the message, never the URL (it contains the password).
    print("Could not connect:", str(e).strip().splitlines()[0])
    sys.exit(1)
except psycopg.Error:
    print("The connection string looks malformed. Check the password encoding and the format.")
    sys.exit(1)