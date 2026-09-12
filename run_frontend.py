import os
import sys
from datetime import date
from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from Frontend import scrub_and_alert

load_dotenv()


def delete_expired_items():
    """
    Deletes any expired rows from the postgres database
    :return:
    """
    engine = create_engine(os.environ["DATABASE_URL"])
    query = text("""
        DELETE FROM products
        WHERE price_guarantee_expiration_date < :cutoff
        """)

    cutoff = date.today()

    with engine.begin() as conn:
        result = conn.execute(query, {"cutoff": cutoff})
    print(f"Deleted {result.rowcount} expired row(s)")


if __name__ == "__main__":
    delete_expired_items()

    if "--check" in sys.argv:
        # this will be run only when the user requests it over SSH
        scrub_and_alert.check_prices_interactively()
    else:
        # cron will run this once daily
        scrub_and_alert.send_daily_reminder()