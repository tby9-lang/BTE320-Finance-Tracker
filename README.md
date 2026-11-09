# Stock & Budget Tracker

**BTE 320 Group Project, Fall 2026**
Team: Brandon Weiss, Tyler Yang, Lucas Loxam, Kevin McDonough

A web app that keeps your daily spending, income, budget, stocks, loans and
property in one place. It gives plain-English tips for handling day-to-day
spending, and it uses finance formulas to project how your savings and
investments could grow.

---

## What it does

| Tab | Features |
|---|---|
| **Overview** | Net worth, cash on hand, investments and debt at a glance; how much you can still spend today; month-to-date spending and a month-end projection; cash balance chart; personalized tips |
| **Daily Log** | Add an expense or income in seconds; see what's left of today's allowance; search, filter and delete past transactions; download them as a CSV file |
| **Spending Summary** | Totals for today, this week, this month, the last 30 days, this year or all time; spending by category; day-to-day spending against your planned pace; this month's budget for each category |
| **Investments** | Live prices from Yahoo Finance; gain/loss and daily change; how the portfolio is divided; price history; your average cost when you buy more shares; average yearly growth (CAGR) |
| **Loans & Property** | Payoff dates, monthly interest and interest left for each loan; a payoff planner that shows what an extra payment saves; property values projected 5 years ahead |
| **Projections** | Compound-growth calculator with a range of outcomes and an inflation adjustment; savings goal planner; past growth of each stock |
| **Settings** | Monthly budget for each category, starting cash, load sample data, erase everything |

The sidebar has a **Quick add** box, so you can log an expense from any tab.

---

## How to run it

1. **Install Python 3.10 or newer** from [python.org](https://www.python.org/downloads/).
2. **Unzip this folder**, open Terminal (Mac) or Command Prompt (Windows), and move into the folder:
   ```
   cd path/to/stock_budget_tracker
   ```
3. **Install the libraries** (one time only):
   ```
   pip install -r requirements.txt
   ```
   On a Mac, use `python3 -m pip install -r requirements.txt` if `pip` isn't found.
4. **Start the app:**
   ```
   streamlit run app.py
   ```
   If `streamlit` isn't found, use `python3 -m streamlit run app.py` (Mac) or `py -m streamlit run app.py` (Windows).
   Your browser opens at http://localhost:8501. If Streamlit asks for an email the first time, just press Enter.
5. On the welcome screen, choose **Load sample data** (best for a demo) or **Start my tracker** to begin with a blank tracker.

To stop the app, press `Ctrl + C` in the terminal.

**Internet:** live stock prices need an internet connection. Without one, the app
still works and shows the last saved prices.

| Item | Details |
|---|---|
| Main Python file | `app.py` |
| Python version | 3.10 or newer, on your own computer (Streamlit apps don't run inside Google Colab) |
| Required libraries | streamlit, pandas, yfinance, matplotlib (see `requirements.txt`) |
| Install command | `pip install -r requirements.txt` |
| Launch command | `streamlit run app.py` |
| Sample data | Click **Load sample data** on the welcome screen (or run `python sample_data.py`). It creates 90 days of example transactions ending today, five stocks, four loans and two properties. |

---

## Running the tests

```
python tests.py
```

This runs 18 automated checks: the finance formulas, adding and deleting
transactions, budget alerts, the daily allowance, average cost, net worth and
several error cases (an amount of $0, a future date, a stock ticker that doesn't
exist, a loan payment too small to cover the interest). The tests use a
temporary folder, so your real data isn't touched.

---

## Files

| File | What it does | Python concepts it shows |
|---|---|---|
| `app.py` | The Streamlit interface: the welcome screen, the sidebar and the 7 tabs | functions, if/elif/else, loops, `if __name__ == "__main__"` |
| `budget.py` | `Transaction` and `Budget` classes: adding transactions, summaries, budget status, daily allowance, tips | classes, `__init__`, `__str__`, lists, dictionaries, sets, pandas |
| `portfolio.py` | `Holding` and `Portfolio` classes: live prices, gain/loss, average cost, CAGR | classes, try/except, lists, the yfinance library |
| `assets.py` | `Loan` and `Property` classes: payoff dates, interest, net worth | classes, modules, the calendar module |
| `projections.py` | The finance formulas (see below) | the math module, functions with return values |
| `charts.py` | Every chart in the app | matplotlib, list slicing, nested functions |
| `storage.py` | Saves and loads every table as a CSV file | pandas, the os module, dictionaries |
| `sample_data.py` | Creates 90 days of realistic demo data | the random and datetime modules, while loops |
| `tests.py` | Automated tests | assert, functions as values |
| `data/` | Your saved data (CSV files, created when you start the app) | |
| `.streamlit/config.toml` | The app's colors | |

---

## Python libraries and how we use them

| Library | How the app uses it |
|---|---|
| **pandas** | Holds every table of data; filters transactions by date, type and category; `groupby` totals spending by category and by day; `resample` makes weekly totals; `cumsum` builds the cash balance over time; reads and writes the CSV files |
| **yfinance** | Downloads up to 5 years of daily prices for each stock from Yahoo Finance. We use them for the current price, the daily change, the CAGR, the price history chart, and to check that a ticker exists before it's added |
| **matplotlib** | Draws every chart: spending by category, day-to-day spending, cash balance, own vs. owe, portfolio split, price history, growth projection and loan payoff |
| **streamlit** | Turns the Python script into a web app with tabs, forms, tables and metric cards, and caches stock prices for 15 minutes so the app stays fast |

---

## Finance formulas

All of these are in `projections.py` (r = monthly rate = yearly rate ÷ 12, n = number of months).

| What it calculates | Formula |
|---|---|
| Future value of savings with monthly deposits | FV = PV(1 + r)^n + PMT × ((1 + r)^n − 1) / r |
| Value in today's dollars | FV / (1 + inflation)^years |
| Monthly loan payment | M = P × r / (1 − (1 + r)^−n) |
| Months to pay off a loan | n = −ln(1 − r × B / M) / ln(1 + r) |
| Months to reach a savings goal | n = ln((FV × r + PMT) / (PV × r + PMT)) / ln(1 + r) |
| Monthly saving needed to hit a goal by a date | PMT = (FV − PV(1 + r)^n) × r / ((1 + r)^n − 1) |
| Compound annual growth rate | CAGR = (end price / start price)^(1 / years) − 1 |
| Rule of 72 | years to double ≈ 72 / yearly rate |
| Property value | value × (1 + yearly change)^years |

Budget math in `budget.py`:

- **Daily allowance** = (flexible budget − flexible spending before today) ÷ days left in the month
- **Month-end projection** = fixed bills + (flexible spending so far ÷ days passed) × days in the month
- **Savings rate** = (income − spending) ÷ income
- **Average cost after buying more** = (old shares × old cost + new shares × new price) ÷ total shares

---

## Troubleshooting

- **"streamlit: command not found"**: run `python3 -m streamlit run app.py` (Mac) or `py -m streamlit run app.py` (Windows).
- **Prices say "Last saved"**: there's no internet connection, or Yahoo Finance is busy. Wait a minute, then press **Refresh prices** on the Investments tab.
- **"Port 8501 is already in use"**: the app is already running in another terminal. Close it or run `streamlit run app.py --server.port 8502`.
- **Start over**: Settings tab → tick the box → **Erase everything**.
