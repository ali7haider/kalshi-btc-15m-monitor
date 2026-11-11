# Kalshi BTC 15-Minute Monitor

This program watches Kalshi's **"BTC price up in next 15 mins?"** markets (series `KXBTC15M`).
During the **final 6 minutes** of each market, whenever the **UP** or **DOWN** side reaches
**87% or higher**, it saves a row to `results.csv`. After the market settles, it updates that row
to **WIN** or **LOSS** on its own.

No Kalshi account or API key is needed. It only reads public market data.

## What gets recorded (`results.csv`)

| Column | Example | Meaning |
|---|---|---|
| Date | 2026-11-11 | Date in Eastern Time |
| Market | KXBTC15M-26NOV110200-00 | Kalshi market ticker |
| Side | UP / DOWN | Which side reached the threshold |
| Percentage | 91% | Price (chance) when first detected |
| Time Detected (ET) | 01:56:42 | Exact time it was detected |
| Seconds Before Close | 198 | How long before the market closed |
| Target Price | $73,572.67 | BTC price the market is measured against |
| Market Close (ET) | 2026-11-11 02:00 | When the 15-minute market closed |
| Result | WIN / LOSS / PENDING | Filled in after settlement |

The file opens directly in **Excel**, **Numbers** or **Google Sheets**.

## Setup (one time)

1. Open **Terminal** (press `Cmd + Space`, type `Terminal`, press Enter).
2. Check that Python 3 is installed:
   ```bash
   python3 --version
   ```
   If you see a version number (3.9 or newer), you're good. If not, install it from
   https://www.python.org/downloads/macos/ and reopen Terminal.
3. Go to the project folder (replace the path with where you put the folder):
   ```bash
   cd ~/Desktop/ks-script
   ```
4. Create a virtual environment and install the one dependency:
   ```bash
   python3 -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
   ```

## Run

```bash
cd ~/Desktop/ks-script
source venv/bin/activate
caffeinate -i python3 monitor.py
```

`caffeinate -i` stops your Mac from going to sleep while the monitor runs.
Keep the Terminal window open. To stop it, press **Ctrl + C**.

You'll see a status line every minute, plus a line whenever something is recorded or settled:

```
01:56 ET | KXBTC15M-26NOV110200-00 | UP 91.0% DOWN None% | 3m left
  >> RECORDED UP at 91% on KXBTC15M-26NOV110200-00 (198s before close)
  >> SETTLED KXBTC15M-26NOV110200-00: UP -> WIN
```

It's safe to stop and restart. Rows still marked `PENDING` are updated to WIN or LOSS the next
time the program runs.

## Viewing results live in Excel (recommended)

`results.csv` is the monitor's own file. **Don't open it directly and save it in Excel while the
monitor is running.** Excel shows a snapshot that doesn't update, and saving from Excel can overwrite
rows the monitor just added.

Instead, make a separate Excel workbook that *reads* the CSV and refreshes:

1. Open Excel and create a **new blank workbook**.
2. Go to **Data → Get Data → From Text/CSV** (on older Excel: **Data → From Text**).
3. Select `results.csv` in the project folder and click **Load**.
4. Save this workbook, for example as `Kalshi Dashboard.xlsx`. You can save it in the same folder.
5. To see the latest rows and WIN/LOSS updates, click **Data → Refresh All**.
6. Optional auto-refresh: right-click inside the table → **Table → External Data Properties**
   (or **Query Properties**) → tick **Refresh every 1 minute**. The exact menu name depends on your
   Excel version.

In this workbook you can sort, filter, colour WIN/LOSS or add charts. The monitor's data stays safe.

**Quick alternative:** open `results.csv` only to *look* (don't save it), and close and reopen it to
see new rows. Google Sheets and Numbers work the same way. They show a copy, not a live view.

The monitor writes the file safely: it writes a temporary file first and then swaps it in. If the
file is busy, it keeps retrying until the save works, so no rows are lost.

## Settings

Change these at the top of `monitor.py` if needed:

| Setting | Default | Meaning |
|---|---|---|
| `THRESHOLD` | `87` | Record when a side is at or above this % |
| `WATCH_WINDOW_SECONDS` | `360` | Only watch the last 6 minutes |
| `POLL_SECONDS` | `2` | How often to check prices |

## Notes

- **UP** = the market's YES side (BTC ends at or above the target price). **DOWN** = the NO side.
- The percentage is the **ask price** (the cost to buy that side), which matches what the Kalshi
  app shows as the price.
- Each side is recorded **once per market**, at the first moment it reaches the threshold.
