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
        SELECT item_code, item_description, price, purchase_date FROM products
        WHERE purchase_date >= %(cutoff)s
    """

    cutoff = date.today() - timedelta(days=WINDOW_DAYS)
    return pd.read_sql(query, engine, param={"cutoff": cutoff})




def send_email():
    SENDER_EMAIL = os.environ.get("EMAIL_USER")
    SENDER_PWD = os.environ.get("EMAIL_PASS")
    RECIPIENT_EMAIL = os.environ.get("RECIPIENT_EMAIL")

    msg = EmailMessage()
    msg["Subject"] = "Testing From Python!"
    msg["From"] = SENDER_EMAIL
    msg["To"] = RECIPIENT_EMAIL
    msg.set_content("This is a test email sent automatically using a Python script.")

    # connect to the SMTP server for gmail
    try:
        with smtplib.SMTP("smtp.gmail.com", 587) as server:
            server.starttls() #TLS connection
            server.login(SENDER_EMAIL, SENDER_PWD)
            server.send_message(msg)
            print("Email sent successfully")
    except Exception as e:
        print(f"An error occured: {e}")

if __name__ == "main":
    #send_email()
    items = get_active_items()

    for i in items:
        print(f"Item 1: {i}")