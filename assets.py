"""
assets.py - Loans (money you owe), properties (things you own) and net worth.

Classes:
    Loan     - a mortgage, car loan, student loan, credit card balance, ...
    Property - a home, rental property, land, vehicle, ...
"""

import calendar
from datetime import date

import pandas as pd

import projections
import storage

LOAN_TYPES = ["Mortgage", "Auto", "Student", "Credit Card", "Personal", "Other"]
PROPERTY_TYPES = ["Home", "Rental Property", "Land", "Vehicle", "Other"]


def add_months(start, months):
    """The date a number of months after `start` (Jan 31 + 1 month = Feb 28)."""
    month_index = start.month - 1 + months
    year = start.year + month_index // 12
    month = month_index % 12 + 1
    day = min(start.day, calendar.monthrange(year, month)[1])
    return date(year, month, day)


class Loan:
    """Money you owe and pay back monthly."""

    def __init__(self, name, kind, balance, annual_rate, monthly_payment):
        self.name = str(name)
        self.kind = str(kind)
        self.balance = float(balance)
        self.annual_rate = float(annual_rate)          # percent per year, e.g. 6.5
        self.monthly_payment = float(monthly_payment)

    def monthly_interest(self):
        """Interest charged this month: balance * monthly rate."""
        return self.balance * projections.monthly_rate(self.annual_rate)

    def months_left(self, extra_payment=0.0):
        """Months until paid off (None if the payment is too small)."""
        return projections.months_to_payoff(self.balance, self.annual_rate,
                                            self.monthly_payment + extra_payment)

    def payoff_date(self, extra_payment=0.0, today=None):
        """The month the loan will be paid off (None if never)."""
        if today is None:
            today = date.today()
        months = self.months_left(extra_payment)
        if months is None:
            return None
        return add_months(today, months)

    def interest_left(self, extra_payment=0.0):
        """Total interest still to pay (None if the loan would never be paid off)."""
        return projections.total_interest(self.balance, self.annual_rate,
                                          self.monthly_payment + extra_payment)

    def schedule(self, extra_payment=0.0):
        """Month-by-month payment schedule (list of dicts)."""
        return projections.amortization_schedule(self.balance, self.annual_rate,
                                                 self.monthly_payment + extra_payment)

    def __str__(self):
        return f"{self.name}: ${self.balance:,.0f} at {self.annual_rate:g}%"


class Property:
    """Something valuable you own, like a home or a car."""

    def __init__(self, name, kind, value, annual_growth):
        self.name = str(name)
        self.kind = str(kind)
        self.value = float(value)
        self.annual_growth = float(annual_growth)   # percent per year; negative = loses value

    def value_in(self, years):
        """Estimated value after some years: value * (1 + growth)^years."""
        return projections.compound_growth(self.value, self.annual_growth, years)

    def __str__(self):
        return f"{self.name}: ${self.value:,.0f}"


# ---------- Checking input ----------

def check_loan(name, balance, annual_rate, monthly_payment):
    """Return an error message, or None if the loan details look valid."""
    if name.strip() == "":
        return "Give the loan a name, like 'Car loan'."
    if balance <= 0:
        return "The balance must be more than $0."
    if annual_rate < 0 or annual_rate > 100:
        return "The interest rate must be between 0% and 100%."
    if monthly_payment <= 0:
        return "The monthly payment must be more than $0."
    return None


def check_property(name, value):
    """Return an error message, or None if the property details look valid."""
    if name.strip() == "":
        return "Give the property a name, like 'My condo'."
    if value <= 0:
        return "The value must be more than $0."
    return None


# ---------- Loading and saving ----------

def load_loans():
    loans = []
    for _, row in storage.load_table("loans").iterrows():
        loans.append(Loan(row["name"], row["kind"], row["balance"],
                          row["annual_rate"], row["monthly_payment"]))
    return loans


def save_loans(loans):
    rows = []
    for loan in loans:
        rows.append({"name": loan.name, "kind": loan.kind, "balance": loan.balance,
                     "annual_rate": loan.annual_rate, "monthly_payment": loan.monthly_payment})
    storage.save_table("loans", pd.DataFrame(rows, columns=storage.TABLE_COLUMNS["loans"]))


def load_properties():
    properties = []
    for _, row in storage.load_table("properties").iterrows():
        properties.append(Property(row["name"], row["kind"], row["value"], row["annual_growth"]))
    return properties


def save_properties(properties):
    rows = []
    for item in properties:
        rows.append({"name": item.name, "kind": item.kind, "value": item.value,
                     "annual_growth": item.annual_growth})
    storage.save_table("properties", pd.DataFrame(rows, columns=storage.TABLE_COLUMNS["properties"]))


# ---------- Tables and totals ----------

def loans_table(loans, today=None):
    """A table of your loans with payoff dates, ready to display."""
    rows = []
    for loan in loans:
        months = loan.months_left()
        payoff = loan.payoff_date(today=today)
        rows.append({
            "Name": loan.name,
            "Type": loan.kind,
            "Balance": loan.balance,
            "Rate %": loan.annual_rate,
            "Monthly payment": loan.monthly_payment,
            "Monthly interest": loan.monthly_interest(),
            "Months left": months,
            "Paid off by": payoff.strftime("%b %Y") if payoff is not None else "Never - payment too low",
            "Interest left": loan.interest_left(),
        })
    return pd.DataFrame(rows)


def properties_table(properties):
    """A table of your properties, ready to display."""
    rows = []
    for item in properties:
        rows.append({
            "Name": item.name,
            "Type": item.kind,
            "Value": item.value,
            "Yearly change %": item.annual_growth,
            "Value in 5 years": item.value_in(5),
        })
    return pd.DataFrame(rows)


def net_worth(cash, investments, properties, loans):
    """Net worth = everything you own - everything you owe."""
    property_total = 0.0
    for item in properties:
        property_total += item.value
    debt_total = 0.0
    for loan in loans:
        debt_total += loan.balance
    assets_total = cash + investments + property_total
    return {
        "cash": cash,
        "investments": investments,
        "property": property_total,
        "assets": assets_total,
        "debt": debt_total,
        "net_worth": assets_total - debt_total,
    }


def debt_insights(loans):
    """Tips about your loans. Returns a list of (level, message) tuples."""
    tips = []
    for loan in loans:
        if loan.balance > 0 and loan.months_left() is None:
            tips.append(("warning",
                         f"Your {loan.name} payment (${loan.monthly_payment:,.0f}) doesn't cover its "
                         f"monthly interest (${loan.monthly_interest():,.0f}), so the balance will keep growing."))

    # Find the loan with the highest interest rate.
    highest = None
    for loan in loans:
        if loan.balance > 0 and (highest is None or loan.annual_rate > highest.annual_rate):
            highest = loan
    if highest is not None and highest.months_left() is not None:
        interest_saved = highest.interest_left() - highest.interest_left(50)
        months_sooner = highest.months_left() - highest.months_left(50)
        tips.append(("info",
                     f"{highest.name} has your highest interest rate ({highest.annual_rate:g}%). "
                     f"Paying an extra $50 a month on it would save about ${interest_saved:,.0f} in "
                     f"interest and pay it off {months_sooner} months sooner. Putting extra money "
                     f"toward your highest-rate debt first (the 'avalanche' method) saves the most."))
    return tips
