import os
import pandas as pd
from Backend.receipt_parser import ReceiptRow
from sqlalchemy import create_engine
from dotenv import load_dotenv
load_dotenv()


def write_to_database(rows: list[ReceiptRow]):
    """
    Write all the data to postgresql server
    """
    if not rows:
        print("No rows to save")
        return
    data = {
        'item_code' : [r.item_code for r in rows],
        'item_description': [r.description for r in rows],
        'price' : [r.price for r in rows],
        'purchase_date' : [r.purchase_date for r in rows],
        'price_guarantee_expiration_date' : [r.expiration_date for r in rows]
    }

    df = pd.DataFrame(data)

    engine = create_engine(os.environ["DATABASE_URL"])
    df.to_sql('products', engine, if_exists='append', index=False)

    print(f'Saved {len(rows)} successfully')
