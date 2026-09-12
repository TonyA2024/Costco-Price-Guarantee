import os
import smtplib
from datetime import timedelta, date
from email.message import EmailMessage
import pandas as pd
from dotenv import load_dotenv
from sqlalchemy import create_engine

load_dotenv()

WINDOW_DAYS = 30


def get_active_items() -> pd.DataFrame:
    """
    Gets items still within their 30 day window from the postgresql server
    """
    engine = create_engine(os.environ["DATABASE_URL"])
    query = """
        SELECT item_code, item_description, price, price_guarantee_expiration_date
        FROM products 
        WHERE price_guarantee_expiration_date >= %(cutoff)s
            """

    cutoff = date.today()
    return pd.read_sql(query, engine, params={"cutoff": cutoff})

def format_reminder(items :pd.DataFrame) -> str:
    lines = ["Items still within eligible window for a refund:\n"]

    for _, row in items.iterrows():
        days_left = (row['price_guarantee_expiration_date'] - date.today()).days
        lines.append(f"- {row['item_description']} (item #{row['item_code']}) "
            f"paid ${row['price']:.2f} -- {days_left} day(s) left. "
            f"Search costco.com for this item number and compare."
        )

        return "\n".join(lines)


def send_email(body: str):
    SENDER_EMAIL = os.environ.get("EMAIL_USER")
    SENDER_PWD = os.environ.get("EMAIL_PASS")
    RECIPIENT_EMAIL = os.environ.get("RECIPIENT_EMAIL")

    msg = EmailMessage()
    msg["Subject"] = "Costco Check Email Reminder"
    msg["From"] = SENDER_EMAIL
    msg["To"] = RECIPIENT_EMAIL
    msg.set_content(body)

    # connect to the SMTP server for gmail
    try:
        with smtplib.SMTP("smtp.gmail.com", 587) as server:
            server.starttls() #TLS connection
            server.login(SENDER_EMAIL, SENDER_PWD)
            server.send_message(msg)
            print("Email sent successfully")
    except Exception as e:
        print(f"An error occurred: {e}")


def record_price_observation(active: pd.DataFrame):
    """
    For each item in active items, prompt for its current price and report whether a refund is owed
    """

    for _, item in active.iterrows():
        paid_price = item['price']
        print(f"Item {item['item_code']} {item['item_description']} was purchased for ${paid_price}")
        cheaper_or_not = int(input("Enter 1 if the price has dropped or 2 if it has not: "))

        if cheaper_or_not == 1:
            observed_price = float(input("What is the current price: "))
            if observed_price < paid_price:
                refund = round(paid_price - observed_price, 2)
                print(
                    f"Price drop found! You are owed a ${refund:.2f} refund on item {item['item_code']}, {item['item_description']}")
        elif cheaper_or_not == 2:
            pass
        else:
            print(f"Invalid input")
            pass

if __name__ == "__main__":
    active = get_active_items()

    if active.empty:
        print("Currently no items")
    else:
        message = format_reminder(active)
        send_email(message)
        record_price_observation(active)

