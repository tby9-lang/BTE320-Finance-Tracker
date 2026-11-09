"""
projections.py - The finance formulas behind the app's forecasts.

Every function here is a plain math function: numbers in, numbers out.
That makes them easy to test (see tests.py) and easy to explain.

Conventions used in this file:
    - Rates are ANNUAL PERCENTAGES. 7 means 7% per year.
    - Savings and loan payments happen MONTHLY, so we convert the annual
      rate to a monthly rate:  r = annual_rate / 100 / 12
    - n is the number of months.
"""

import math


def monthly_rate(annual_rate):
    """Convert an annual percentage (like 6) into a monthly decimal rate (0.005)."""
    return annual_rate / 100 / 12


def future_value(present_value, monthly_contribution, annual_rate, years):
    """How much money you will have after saving/investing for some years.

    Formula (monthly compounding, deposit at the end of each month):
        FV = PV * (1 + r)^n  +  PMT * ((1 + r)^n - 1) / r

    PV  = money you start with
    PMT = money you add every month
    """
    r = monthly_rate(annual_rate)
    n = round(years * 12)
    if r == 0:
        # No growth: you just end up with what you put in.
        return present_value + monthly_contribution * n
    growth = (1 + r) ** n
    return present_value * growth + monthly_contribution * (growth - 1) / r


def growth_by_year(present_value, monthly_contribution, annual_rate, years):
    """A year-by-year table showing the balance, the money you put in,
    and the growth (interest/returns) you earned. Returns a list of dicts."""
    rows = []
    for year in range(years + 1):
        balance = future_value(present_value, monthly_contribution, annual_rate, year)
        contributed = present_value + monthly_contribution * 12 * year
        rows.append({
            "year": year,
            "balance": balance,
            "contributed": contributed,
            "growth": balance - contributed,
        })
    return rows


def real_value(future_amount, inflation_rate, years):
    """What a future amount of money is worth in TODAY'S dollars.

    Formula:  real value = future amount / (1 + inflation)^years
    """
    return future_amount / (1 + inflation_rate / 100) ** years


def compound_growth(value, annual_rate, years):
    """Grow (or shrink) a value once per year, e.g. a home that gains 3% a year
    or a car that loses 12% a year.

    Formula:  value * (1 + rate)^years
    """
    return value * (1 + annual_rate / 100) ** years


def loan_payment(principal, annual_rate, years):
    """The monthly payment that pays off a loan in a set number of years.

    Formula:  M = P * r / (1 - (1 + r)^-n)
    """
    r = monthly_rate(annual_rate)
    n = round(years * 12)
    if n <= 0:
        return principal
    if r == 0:
        return principal / n
    return principal * r / (1 - (1 + r) ** -n)


def months_to_payoff(balance, annual_rate, monthly_payment):
    """How many months until a loan is fully paid off.

    Formula:  n = -ln(1 - r * B / M) / ln(1 + r)

    Returns None when the payment is too small to ever pay off the loan
    (it doesn't even cover the interest charged each month).
    """
    if balance <= 0:
        return 0
    if monthly_payment <= 0:
        return None
    r = monthly_rate(annual_rate)
    if r == 0:
        return math.ceil(balance / monthly_payment - 1e-9)
    if monthly_payment <= balance * r:
        return None
    n = -math.log(1 - r * balance / monthly_payment) / math.log(1 + r)
    # Round UP: a partial month still needs one more (smaller) payment.
    # The tiny 1e-9 stops rounding errors like 36.0000001 from becoming 37.
    return math.ceil(n - 1e-9)


def amortization_schedule(balance, annual_rate, monthly_payment, max_months=1200):
    """Month-by-month breakdown of a loan: how much of each payment goes to
    interest and how much actually lowers the balance (principal).
    Returns a list of dicts, one per month."""
    r = monthly_rate(annual_rate)
    rows = []
    month = 0
    while balance > 0.005 and month < max_months:
        month += 1
        interest = balance * r
        payment = min(monthly_payment, balance + interest)  # the last payment is smaller
        principal = payment - interest
        if principal <= 0:
            break  # the payment doesn't cover the interest - the loan never shrinks
        balance -= principal
        rows.append({
            "month": month,
            "payment": payment,
            "interest": interest,
            "principal": principal,
            "balance": max(balance, 0.0),
        })
    return rows


def total_interest(balance, annual_rate, monthly_payment):
    """Total interest you will pay over the rest of a loan.
    Returns None if the loan would never be paid off."""
    if months_to_payoff(balance, annual_rate, monthly_payment) is None:
        return None
    total = 0.0
    for row in amortization_schedule(balance, annual_rate, monthly_payment):
        total += row["interest"]
    return total


def months_to_goal(current, goal, monthly_contribution, annual_rate):
    """How many months of saving it takes to reach a savings goal.

    Solving the future value formula for n gives:
        n = ln((FV * r + PMT) / (PV * r + PMT)) / ln(1 + r)

    Returns 0 if the goal is already reached, or None if it can never be
    reached (nothing saved and nothing being added).
    """
    if current >= goal:
        return 0
    r = monthly_rate(annual_rate)
    if r == 0:
        if monthly_contribution <= 0:
            return None
        return math.ceil((goal - current) / monthly_contribution - 1e-9)
    if monthly_contribution <= 0 and current <= 0:
        return None
    n = math.log((goal * r + monthly_contribution) / (current * r + monthly_contribution)) / math.log(1 + r)
    return math.ceil(n - 1e-9)


def monthly_savings_needed(current, goal, annual_rate, months):
    """How much you need to save each month to reach a goal by a deadline.

    Solving the future value formula for PMT gives:
        PMT = (FV - PV * (1 + r)^n) * r / ((1 + r)^n - 1)
    """
    if months <= 0:
        return None
    r = monthly_rate(annual_rate)
    if r == 0:
        return max((goal - current) / months, 0.0)
    growth = (1 + r) ** months
    needed = (goal - current * growth) * r / (growth - 1)
    return max(needed, 0.0)  # 0 means your current savings will get there on their own


def cagr(start_value, end_value, years):
    """Compound Annual Growth Rate - the steady yearly growth that would turn
    start_value into end_value. Returned as a percent.

    Formula:  CAGR = (end / start)^(1 / years) - 1
    """
    if start_value <= 0 or years <= 0:
        return None
    return ((end_value / start_value) ** (1 / years) - 1) * 100


def years_to_double(annual_rate):
    """The Rule of 72: money doubles in roughly 72 / rate years."""
    if annual_rate <= 0:
        return None
    return 72 / annual_rate
