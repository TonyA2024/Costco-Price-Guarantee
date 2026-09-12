import os
import pandas as pd
from datetime import timedelta, date
from Frontend import scrub_and_alert
from dotenv import load_dotenv
from sqlalchemy import create_engine, text

load_dotenv()

if __name__ == "__main__":
    engine = create_engine(os.environ["DATABASE_URL"])
    query = text("""
                    DELETE FROM products
                    WHERE price_guarantee_expiration_date < :cutoff
                    """)

    cutoff = date.today()
    with engine.begin() as conn:
        result = conn.execute(query, {"cutoff": cutoff})
    print(f"Deleted {result.rowcount} expired row(s)")

    scrub_and_alert.main()
