import os
import smtplib
from email.message import EmailMessage
from dotenv import load_dotenv
load_dotenv()

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
