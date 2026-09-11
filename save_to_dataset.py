import os
import pandas as pd
from receipt_parser import ReceiptRow
from sqlalchemy import create_engine
from dotenv import load_dotenv
load_dotenv()


def write_to_database(rows: list[ReceiptRow]):
    if not rows:
        print("No rows to save")
        return
    data = {
        "Item_code" : [r.item_code for r in rows],
        "Item_description": [r.description for r in rows],
        "Item_price" : [r.price for r in rows],
        "Purchase_date" : [r.purchase_date for r in rows],
        "Price_Guarantee_Expiration_Date" : [r.expiration_date for r in rows]
    }

    df = pd.DataFrame(data)

    engine = create_engine(os.environ["DATABASE_URL"])
    df.to_sql('products', engine, if_exists='append', index=False)

    print(f'Saved {len(rows)} successfully')
