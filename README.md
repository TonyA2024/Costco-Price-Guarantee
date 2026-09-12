# Costco-Price-Guarantee
## Project overview

Automates Costco's 30-day price-adjustment policy: scan a receipt, get notified if any item's price drops within its refund window.
Built as a full pipeline: OCR → structured parsing → price monitoring → refund calculation.


## Architecture / pipeline
![Program Architecture](Backend/costco_price_tracker_architecture.png)

Receipt image → Google Cloud Vision OCR → word-level bounding-box reconstruction → structured item records (Postgres via SQLAlchemy/pandas).
Price monitoring → currently manual/semi-automated (see "Engineering findings" below) → refund-amount calculation on any detected drop.

## Current status

**Completed:**
- Full OCR pipeline: receipt image → Google Cloud Vision → word-level bounding-box reconstruction → structured item records (item code, description, price, purchase date).
- Discount-line merging and 30-day expiration-date calculation, persisted to Postgres.
- Manual price-check system: a daily reminder email listing items still in their refund window, an interactive CLI walkthrough for logging observed prices, and a refund email summarizing any drops found.
- Expired-item cleanup (removes rows past their 30-day window).
- Codebase split into a cron-safe path (no user input, safe to run unattended) and an interactive path (run manually, e.g. over SSH), so the reminder email can run on a schedule without blocking on input it'll never receive.
- Automated receipt intake pipeline (`process_incoming_receipts.py`): pulls newly Taildropped photos from a phone, runs each through OCR, and adds results to Postgres -- with per-file error handling so one bad photo doesn't stop the rest of a batch, and processed/failed files moved out of the incoming folder so nothing gets reprocessed on the next run.
- Tested end-to-end locally on Windows.

**Planned: Raspberry Pi deployment**
- Moving this system onto a dedicated Raspberry Pi, run entirely separately from my other Pi-based project (a Immich photo server on a different network).
- Configuring WiFi and SSH for the Pi.
- Using Tailscale for remote SSH access (to run the interactive price-check) and Taildrop for uploading new receipt photos from phone -- with `process_incoming_receipts.py` handling the Linux-specific step of pulling files out of Tailscale's staging area (`tailscale file get`) before processing them.
- Two cron schedules: `process_incoming_receipts.py` running frequently (e.g. every 15 minutes) to pick up new receipts soon after they're scanned, and `run_frontend.py` running once daily for the reminder email. The interactive price-logging step stays a manual SSH session by design, since it requires live input.

## Technical challenges solved
* Two-column OCR reconstruction: Vision's raw text output groups words by visual block, not physical row, and costco has two-column receipts. This was solved by reconstructing rows from word-level bounding-box coordinates found in the OCR json file.
* Photo skew correction: a tilted photo causes the same physical row to have different y-coordinates at different x-positions — solved by clustering left/right columns separately and pairing by order rather than absolute position.
* Print-layout quirks: tax-marker glyphs printed off-baseline from item text required filtering rather than tolerance-tuning.
* Data-boundary isolation: column/row detection had to be scoped to the item table specifically, since payment-summary text elsewhere on the receipt has a different layout and contaminates whole-document parsing.
* Discount-line reconciliation: Costco prints instant-savings as separate negative-price rows immediately following the discounted item — merged programmatically with an exception check.

## Engineering findings: Costco's anti-bot defenses

* I Systematically tested plain requests (blocked at the application layer and returned error code HTTP 403) and then tried Playwright across 4 configurations (headless/visible Chromium with/without HTTP/2, headless Firefox) to isolate the actual defense mechanism.
* After these tests I was able to track the block to Akamai Bot Manager (confirmed via the errors.edgesuite.net domain in the returned block page) — an enterprise-grade anti-bot system, and not one I could get around.
* Documented decision: rather than escalating farther past my skill level to try to get around the anti-bot system, I pivoted to a manual/semi-automated price-check design, a deliberate engineering tradeoff.

Tech stack: Python, Google Cloud Vision API, Postgres, SQLAlchemy, pandas, Playwright, Raspberry Pi, Tailscale