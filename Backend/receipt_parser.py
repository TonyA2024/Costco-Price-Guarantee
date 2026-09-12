"""
Costco receipt parser built on Google Cloud Vision's word-level bounding boxes.

1. Item table must be bounded first (member-number line to SUBTOTAL) --
   otherwise price-shaped tokens from the payment-summary section (e.g.
   "AMOUNT: $308.78") contaminate column-boundary detection.
2. Left/right columns must be clustered into rows SEPARATELY, then paired
   by order.
3. The 'E' tax-marker glyphs on Costco receipts print off-baseline from the
   item text itself, so they're dropped before row-building rather than
   fought with tolerance tuning.
"""

import re
import base64
import requests
from dataclasses import dataclass, field
from datetime import date, timedelta
from dotenv import load_dotenv

load_dotenv()

# price regex
PRICE_RE = re.compile(r"^\$?\d+\.\d{2}-?$")
# member number regex, a Costco member number is 10 digits followed by ASCII characters
MEMBER_NUM_RE = re.compile(r"^\d{10,}$")
# date format regex
DATE_RE = re.compile(r"^\d{2}/\d{2}/\d{4}$")
#Item code regex to split item code from item desc
ITEM_CODE_RE = re.compile(r"^(\d+)\s+(.*)$")


@dataclass
class Word:
    text: str
    x_center: float
    y_center: float
    x_min: float
    x_max: float


def call_vision_api(image_path: str, api_key: str) -> dict:
    """
    Calls Google Cloud Vision API on the image. Returns a json dump file
    """
    with open(image_path, "rb") as f:
        content = base64.b64encode(f.read()).decode("utf-8")

    url = f"https://vision.googleapis.com/v1/images:annotate?key={api_key}"
    payload = {
        "requests": [{
            "image": {"content": content},
            "features": [{"type": "DOCUMENT_TEXT_DETECTION"}],
        }]
    }
    resp = requests.post(url, json=payload)
    resp.raise_for_status()
    return resp.json()


def extract_words(vision_response: dict) -> list[Word]:
    """Pull individual words with bounding box centers from the raw json response.

    textAnnotations[0] is the full concatenated text block so it gets skipped--
    every entry after that is a single word/token with its own boundingPoly.
    """
    annotations = vision_response["responses"][0].get("textAnnotations", [])[1:]
    words = []
    for feature in annotations:
        verts = feature["boundingPoly"]["vertices"]
        xs = [v.get("x", 0) for v in verts]
        ys = [v.get("y", 0) for v in verts]
        words.append(Word(
            text=feature["description"],
            x_center=sum(xs) / len(xs),
            y_center=sum(ys) / len(ys),
            x_min=min(xs),
            x_max=max(xs),
        ))
    return words


def find_item_table_bounds(words: list[Word]) -> tuple[float, float]:
    """
    Locate the y-range of the actual item table: from the member-number
    line down to SUBTOTAL.
    """
    header_candidates = [w.y_center for w in words if MEMBER_NUM_RE.match(w.text)]
    subtotal_ys = [w.y_center for w in words if w.text.upper() == "SUBTOTAL"]
    if not header_candidates or not subtotal_ys:
        raise ValueError("Couldn't find header or SUBTOTAL anchor to bound the item table")

    top = min(header_candidates) + 10
    bottom = min(subtotal_ys) - 15
    return top, bottom


def get_purchase_date(words: list[Word]) -> date:
    """
    Find and parse MM/DD/YYYY near the bottom of receipt
    """
    date_matches = [w.text for w in words if DATE_RE.match(w.text)]
    if not date_matches:
        raise ValueError("No date found on receipt")

    month, day, year = (int(p) for p in date_matches[0].split("/"))
    return date(year, month, day)


def find_column_boundary(words: list[Word]) -> float:
    """
    Auto-detect the x-position separating item info (left) from price
    (right), using the leftmost x of any price-shaped token. Must be
    called on words already restricted to the item-table y-range, or
    payment-summary prices elsewhere on the receipt will skew the result.
    """
    price_left_edges = [w.x_min for w in words if PRICE_RE.match(w.text)]
    if not price_left_edges:
        raise ValueError("No price-shaped tokens found in the item table region")
    return min(price_left_edges) - 10


def group_into_rows(words: list[Word], y_tolerance: float = 10) -> list[list[Word]]:
    """
    Cluster words into rows based on vertical position, sorted left-to-right.
    """
    words_sorted = sorted(words, key=lambda w: w.y_center)
    rows: list[list[Word]] = []
    current_row: list[Word] = []
    current_y = None

    for word in words_sorted:
        if current_y is None or abs(word.y_center - current_y) <= y_tolerance:
            current_row.append(word)
            current_y = sum(w.y_center for w in current_row) / len(current_row)
        else:
            rows.append(sorted(current_row, key=lambda w: w.x_center))
            current_row = [word]
            current_y = word.y_center

    if current_row:
        rows.append(sorted(current_row, key=lambda w: w.x_center))

    return rows


@dataclass
class ReceiptRow:
    description: str
    price: float | None
    item_code: str | None = None
    purchase_date: date | None = None
    expiration_date: date | None = None
    raw_words: list[str] = field(default_factory=list)


def parse_price_token(token: str) -> float | None:
    """
    Parse the price token into dollars
    Handle the special case where the sale is subtracted
    """
    try:
        if token.endswith("-"):
            return -float(token[:-1])
        return float(token.lstrip("$"))
    except ValueError:
        return None


def split_item_code(text: str) -> tuple[str | None, str]:
    """
    Split item code off from item description
    Item code will be saved as a separate column in the dataset
    """
    match = ITEM_CODE_RE.match(text)
    if match:
        return match.group(1), match.group(2)
    return None, text


def merge_discount_rows(rows: list[ReceiptRow]) -> list[ReceiptRow]:
    """
    Remove Costco sale savings from above row/item
    After subtracting the sale, remove that line entirely
    """
    merged: list[ReceiptRow] = []
    for row in rows:
        if row.price is not None and row.price < 0:
            if not merged:
                raise ValueError(f"Discount row {row.description} has no preceding item to apply it to")
            merged[-1].price = round(merged[-1].price + row.price,2)
            continue
        merged.append(row)
    return merged


def parse_receipt_words(words: list[Word]) -> list[ReceiptRow]:
    """
    Parse all the words in the image
    :param words:
    :return:
    """
    top, bottom = find_item_table_bounds(words)
    table_words = [w for w in words if top <= w.y_center <= bottom]
    purchase_date = get_purchase_date(words)

    # drop standalone tax-marker 'E' tokens -- printed off-baseline from
    table_words = [w for w in table_words if w.text != "E"]

    boundary_x = find_column_boundary(table_words)
    left_words = [w for w in table_words if w.x_center < boundary_x]
    right_words = [w for w in table_words if w.x_center >= boundary_x]

    left_rows = group_into_rows(left_words)
    right_rows = group_into_rows(right_words)

    if len(left_rows) != len(right_rows):
        raise ValueError(
            f"Row count mismatch: {len(left_rows)} left rows vs {len(right_rows)} "
            f"right rows -- pairing would be unreliable. Inspect both lists before trusting output."
        )

    raw_rows = []
    for lrow, rrow in zip(left_rows, right_rows):
        description = " ".join(w.text for w in lrow)
        price_text = rrow[-1].text if rrow else None
        price = parse_price_token(price_text) if price_text else None
        raw_rows.append(ReceiptRow(
            description=description,
            price=price,
            purchase_date=purchase_date,
            expiration_date= purchase_date + timedelta(days=30),
            raw_words=[w.text for w in lrow] + [w.text for w in rrow]
        ))
    merged_rows = merge_discount_rows(raw_rows)

    for row in merged_rows:
        item_code, description = split_item_code(row.description)
        row.item_code = item_code
        row.description = description

    return merged_rows


def parse_receipt(image_path: str, api_key: str) -> list[ReceiptRow]:
    """
    Parse the receipt by calling the Google Vision API OCR
    Extract the words to be formatted
    """
    response = call_vision_api(image_path, api_key)
    words = extract_words(response)
    return parse_receipt_words(words)

"""
if __name__ == "__main__":
    import os
    API_KEY = os.environ["GOOGLE_VISION_API_KEY"]
    results = parse_receipt("costco_test_zoom_receipt.png", API_KEY)
    for r in results:
        print(f"{r.item_code!s: <10} {r.price!s:>10}  {r.description} ({r.purchase_date}) ({r.expiration_date})")
"""