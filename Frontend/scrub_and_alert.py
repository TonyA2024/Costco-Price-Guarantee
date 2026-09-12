import os
import smtplib
from datetime import timedelta, date
from email.message import EmailMessage
import pandas as pd
from dotenv import load_dotenv
from sqlalchemy import create_engine

load_dotenv()

RED = "\033[31m"
RESET = "\033[0m"
GREEN = "\033[32m"


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


def send_reminder_email(body: str):
    """"
    Send the reminder email with all the current items that are still within their 30 day window
    """
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

def prompt_choice(prompt: str, valid_choices: set[int]) -> int:
    """
    Keep asking for input until the input is one of the valid choices. This allows the program to keep running when
    bad input is entered instead of crashing
    """
    while True:
        raw = input(prompt)
        try:
            choice = int(raw)
        except ValueError:
            print(f"Please enter a number ({'/'.join(str(c) for c in sorted(valid_choices))}).")
            continue
        if choice not in valid_choices:
            print(f"Please enter one of: {','.join(str(c) for c in sorted(valid_choices))}.")
            continue
        return choice

def prompt_float(prompt: str) -> float:
    """
    Keep prompting user until the input parses as a number. This allows program to gracefully handle bad input
    """
    while True:
        raw = input(prompt)
        try:
            return float(raw)
        except ValueError:
            print("Please enter a valid number (e.g. 12.99).")

def record_price_observation(active: pd.DataFrame) -> pd.DataFrame:
    """
    For each item in active items, prompt for its current price and report whether a refund is owed.
    Returns a DataFrame of only the items with an actual refund found
    """
    refundable_records = []
    for _, item in active.iterrows():
        paid_price = item['price']
        print(f"\n{RED}Item {item['item_code']} {item['item_description']} was purchased for ${paid_price}{RESET}")
        cheaper_or_not = prompt_choice("Enter 1 if the price has dropped or 2 if it has not: ", {1,2})

        if cheaper_or_not == 1:
            observed_price = prompt_float("What is the current price: ")
            if observed_price < paid_price:
                refund = round(paid_price - observed_price, 2)
                print(
                    f"{GREEN}Price drop found! You are owed a ${refund:.2f} refund on item {item['item_code']}, {item['item_description']}{RESET}")
                refundable_records.append({"item_code" : item['item_code'],
                                         "item_description": item['item_description'],
                                         "paid_price": paid_price,
                                         "observed_price": observed_price,
                                         "refund": refund,
                                         "price_guarantee_expiration_date": item["price_guarantee_expiration_date"],
                                         })
            else:
                print(f"You entered a price that isn't actually lower. No refund for item {item['item_code']}.")

    return pd.DataFrame(refundable_records)

def send_refund_email(refundable_items: pd.DataFrame):
    """
    Send an email listing each item that we have found an eligible refund for
    """
    SENDER_EMAIL = os.environ.get("EMAIL_USER")
    SENDER_PWD = os.environ.get("EMAIL_PASS")
    RECIPIENT_EMAIL = os.environ.get("RECIPIENT_EMAIL")

    msg = EmailMessage()
    msg["Subject"] = "Costco Price Drop -- Refunds Owed"
    msg["From"] = SENDER_EMAIL
    msg["To"] = RECIPIENT_EMAIL

    lines = ["You're owed a refund on the following items:\n"]

    for _, row in refundable_items.iterrows():
        days_left = (row['price_guarantee_expiration_date'] - date.today()).days
        lines.append(f"- {row['item_description']} (item #{row['item_code']}. ) "
                     f"Paid ${row['paid_price']:.2f}, now ${row['observed_price']:.2f}"
                     f"\n--refund owed: ${row['refund']:.2f} -- {days_left} day(s) left to claim"
                     )

    body = "\n".join(lines)
    msg.set_content(body)

    # connect to the SMTP server for gmail
    try:
        with smtplib.SMTP("smtp.gmail.com", 587) as server:
            server.starttls()  # TLS connection
            server.login(SENDER_EMAIL, SENDER_PWD)
            server.send_message(msg)
            print("Refund Email sent successfully")
    except Exception as e:
        print(f"An error occurred: {e}")

def send_daily_reminder():
    """
    Will be called from cron on the raspberry pi
    """
    active = get_active_items()

    if active.empty:
        print("Currently no items")
        return
    else:
        message = format_reminder(active)
        send_reminder_email(message)

def check_prices_interactively():
    """
    Run personally over SSH when the user wants to log prices they found
    """
    active = get_active_items()

    if active.empty:
        print("Currently no items")
        return

    refundable_items = record_price_observation(active)
    if not refundable_items.empty:
        send_refund_email(refundable_items)
    else:
        print("No refunds found this run.")

if __name__ == "__main__":
    check_prices_interactively()