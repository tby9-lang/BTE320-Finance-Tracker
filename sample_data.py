"""
sample_data.py - Creates realistic example data so you can try the app right away.

The example person: a young professional who owns a condo, drives a financed
car, has student loans and a credit card balance, and invests in five stocks/ETFs.

The transactions always cover the 90 days up to TODAY, so the demo looks
current whenever you run it. random.seed() makes the "random" amounts come
out the same every time.
"""

import random
from datetime import date, timedelta

import pandas as pd

import storage

STARTING_CASH = 6500.00

SAMPLE_BUDGETS = {
    "Housing": 2000, "Utilities": 230, "Debt Payments": 740, "Groceries": 450,
    "Dining Out": 300, "Transportation": 320, "Entertainment": 150,
    "Shopping": 200, "Health": 100, "Education": 60, "Other": 100,
}

# (ticker, shares, average cost per share, purchase date)
SAMPLE_HOLDINGS = [
    ("VOO", 12, 412.50, "2024-03-11"),
    ("AAPL", 15, 185.20, "2024-01-22"),
    ("MSFT", 8, 371.40, "2023-11-06"),
    ("NVDA", 25, 48.30, "2023-06-05"),
    ("KO", 30, 59.80, "2023-09-18"),
]

# (name, type, balance, annual rate %, monthly payment)
SAMPLE_LOANS = [
    ("Condo mortgage", "Mortgage", 268000, 6.1, 1625),
    ("Car loan", "Auto", 12400, 6.9, 380),
    ("Student loan", "Student", 22000, 5.5, 240),
    ("Credit card", "Credit Card", 1850, 23.9, 120),
]

# (name, type, value, yearly change %)
SAMPLE_PROPERTIES = [
    ("Condo", "Home", 340000, 3.0),
    ("Car", "Vehicle", 19500, -12.0),
]

# Bills that arrive on the same day every month: (day, category, note, low, high)
MONTHLY_BILLS = [
    (1, "Housing", "Mortgage payment", 1625, 1625),
    (1, "Housing", "HOA fee", 350, 350),
    (2, "Health", "Gym membership", 40, 40),
    (3, "Entertainment", "Streaming subscription", 15.49, 15.49),
    (5, "Debt Payments", "Student loan payment", 240, 240),
    (8, "Utilities", "Electric bill", 95, 150),
    (10, "Entertainment", "Music subscription", 10.99, 10.99),
    (12, "Debt Payments", "Car loan payment", 380, 380),
    (14, "Other", "Haircut", 30, 35),
    (15, "Utilities", "Internet", 65, 65),
    (18, "Utilities", "Phone bill", 45, 45),
    (20, "Debt Payments", "Credit card payment", 120, 120),
]


def make_transactions(today):
    """Build a list of transaction dictionaries for the 90 days up to `today`."""
    random.seed(42)
    rows = []

    def add(day, kind, category, amount, note):
        rows.append({"date": day.isoformat(), "type": kind, "category": category,
                     "amount": round(amount, 2), "note": note})

    first_day = today - timedelta(days=89)

    # Paychecks every other Friday (Friday = weekday 4).
    payday = first_day + timedelta(days=(4 - first_day.weekday()) % 7)
    next_grocery_day = first_day + timedelta(days=1)
    next_gas_day = first_day + timedelta(days=2)

    day = first_day
    while day <= today:
        weekend = day.weekday() >= 5

        # Income
        if day == payday:
            add(day, "Income", "Paycheck", 2350.00, "Paycheck")
            payday += timedelta(days=14)
        if day.day == 25:
            add(day, "Income", "Side Income", random.uniform(150, 400), "Freelance project")
        if day.day == 15 and day.month in (3, 6, 9, 12):
            add(day, "Income", "Investment Income", 38.50, "Quarterly dividends")

        # Monthly bills
        for bill_day, category, note, low, high in MONTHLY_BILLS:
            if day.day == bill_day:
                add(day, "Expense", category, random.uniform(low, high), note)

        # Today only gets a morning coffee, so a live demo starts with a fresh day.
        if day == today:
            add(day, "Expense", "Dining Out", 5.25, "Coffee")
            break

        # Groceries every 5-7 days
        if day >= next_grocery_day:
            add(day, "Expense", "Groceries", random.uniform(55, 110), "Grocery store")
            next_grocery_day = day + timedelta(days=random.randint(5, 7))

        # Gas about once a week
        if day >= next_gas_day:
            add(day, "Expense", "Transportation", random.uniform(38, 55), "Gas")
            next_gas_day = day + timedelta(days=random.randint(6, 8))

        # Everyday spending (more likely - and pricier - on weekends)
        if random.random() < (0.30 if weekend else 0.50):
            add(day, "Expense", "Dining Out", random.uniform(4.50, 7.50), "Coffee")
        if weekend and random.random() < 0.70:
            add(day, "Expense", "Dining Out", random.uniform(28, 60), "Dinner out")
        elif not weekend and random.random() < 0.25:
            add(day, "Expense", "Dining Out", random.uniform(12, 28), "Lunch")
        if random.random() < 0.07:
            add(day, "Expense", "Transportation", random.uniform(12, 28), "Rideshare")
        if random.random() < 0.07:
            add(day, "Expense", "Transportation", random.uniform(8, 20), "Parking & tolls")
        if weekend and random.random() < 0.25:
            add(day, "Expense", "Entertainment", random.uniform(20, 60), "Movies & events")
        if random.random() < 0.08:
            add(day, "Expense", "Shopping", random.uniform(20, 120), "Shopping")
        if random.random() < 0.03:
            add(day, "Expense", "Health", random.uniform(10, 35), "Pharmacy")
        if random.random() < 0.02:
            add(day, "Expense", "Education", random.uniform(15, 30), "Books")
        if random.random() < 0.02:
            add(day, "Expense", "Other", random.uniform(25, 60), "Gift")

        day += timedelta(days=1)

    # Number the transactions 1, 2, 3, ...
    for number, row in enumerate(rows, start=1):
        row["id"] = number
    return rows


def create_sample_data(today=None):
    """Write every sample CSV file into the data folder (replacing what's there)."""
    if today is None:
        today = date.today()

    transactions = pd.DataFrame(make_transactions(today), columns=storage.TABLE_COLUMNS["transactions"])
    storage.save_table("transactions", transactions)

    budget_rows = []
    for category, limit in SAMPLE_BUDGETS.items():
        budget_rows.append({"category": category, "monthly_limit": limit})
    storage.save_table("budgets", pd.DataFrame(budget_rows))

    holding_rows = []
    for ticker, shares, avg_cost, bought in SAMPLE_HOLDINGS:
        # Until live prices are downloaded, the "last price" is what was paid.
        holding_rows.append({"ticker": ticker, "shares": shares, "avg_cost": avg_cost,
                             "purchase_date": bought, "last_price": avg_cost})
    storage.save_table("holdings", pd.DataFrame(holding_rows, columns=storage.TABLE_COLUMNS["holdings"]))

    loan_rows = []
    for name, kind, balance, rate, payment in SAMPLE_LOANS:
        loan_rows.append({"name": name, "kind": kind, "balance": balance,
                          "annual_rate": rate, "monthly_payment": payment})
    storage.save_table("loans", pd.DataFrame(loan_rows, columns=storage.TABLE_COLUMNS["loans"]))

    property_rows = []
    for name, kind, value, growth in SAMPLE_PROPERTIES:
        property_rows.append({"name": name, "kind": kind, "value": value, "annual_growth": growth})
    storage.save_table("properties", pd.DataFrame(property_rows, columns=storage.TABLE_COLUMNS["properties"]))

    storage.save_settings({"starting_cash": STARTING_CASH})


if __name__ == "__main__":
    # Running "python sample_data.py" directly also creates the sample files.
    create_sample_data()
    print("Sample data created in the data folder.")
