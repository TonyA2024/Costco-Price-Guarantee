import os
from Backend.receipt_parser import parse_receipt
from Backend.save_to_dataset import write_to_database
from dotenv import load_dotenv

load_dotenv()


if __name__ == "__main__":
    api_key = os.environ["GOOGLE_VISION_API_KEY"]
    results = parse_receipt("Backend/costco_zoom_receipt.png", api_key)
    write_to_database(results)
    for r in results:
        print(f"{r.item_code!s:<10} {r.price!s:>10}  {r.description} ({r.purchase_date}) ({r.expiration_date})")