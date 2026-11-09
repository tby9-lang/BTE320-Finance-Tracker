"""
budget.py - Daily expenses, income, monthly budgets and spending summaries.

Classes:
    Transaction - one expense or income entry
    Budget      - all of your transactions plus your monthly budget limits,
                  with methods that summarize your spending
"""

import calendar
from datetime import date, timedelta

import pandas as pd

import storage

EXPENSE_CATEGORIES = [
    "Groceries", "Dining Out", "Transportation", "Shopping", "Entertainment",
    "Health", "Education", "Housing", "Utilities", "Debt Payments", "Other",
]
INCOME_CATEGORIES = ["Paycheck", "Side Income", "Investment Income", "Gift", "Other Income"]

# Bills that cost about the same every month. Everything else is "flexible"
# spending - the part you control day to day.
FIXED_CATEGORIES = {"Housing", "Utilities", "Debt Payments"}

# Time periods the Spending Summary page can show.
PERIODS = ["Today", "This week", "This month", "Last 30 days", "This year", "All time"]

# A starting budget for brand-new users. They can change it on the Settings tab.
DEFAULT_LIMITS = {
    "Housing": 1200, "Utilities": 150, "Debt Payments": 300, "Groceries": 400,
    "Dining Out": 250, "Transportation": 200, "Entertainment": 100,
    "Shopping": 150, "Health": 75, "Education": 50, "Other": 100,
}


def days_in_month(day):
    """Number of days (28-31) in the month that `day` falls in."""
    return calendar.monthrange(day.year, day.month)[1]


def period_dates(period, today=None):
    """Turn a period name like "This month" into (start_date, end_date).
    For "All time" the start is None, meaning "from the very first entry"."""
    if today is None:
        today = date.today()
    if period == "Today":
        return today, today
    elif period == "This week":
        monday = today - timedelta(days=today.weekday())
        return monday, today
    elif period == "This month":
        return today.replace(day=1), today
    elif period == "Last 30 days":
        return today - timedelta(days=29), today
    elif period == "This year":
        return today.replace(month=1, day=1), today
    else:  # "All time"
        return None, today


class Transaction:
    """One expense or one income entry."""

    def __init__(self, when, kind, category, amount, note=""):
        self.date = when            # a datetime.date
        self.kind = kind            # "Expense" or "Income"
        self.category = category
        self.amount = round(float(amount), 2)
        self.note = note.strip()

    def check(self):
        """Return an error message if something is wrong, or None if it's valid."""
        if self.kind not in ("Expense", "Income"):
            return "Type must be Expense or Income."
        if self.kind == "Expense":
            valid_categories = EXPENSE_CATEGORIES
        else:
            valid_categories = INCOME_CATEGORIES
        if self.category not in valid_categories:
            return f"'{self.category}' is not a valid {self.kind.lower()} category."
        if self.amount <= 0:
            return "The amount must be more than $0."
        if self.date > date.today():
            return "The date can't be in the future."
        return None

    def __str__(self):
        sign = "-" if self.kind == "Expense" else "+"
        return f"{self.category} {sign}${self.amount:,.2f} on {self.date:%b %d}"


class Budget:
    """All transactions plus monthly budget limits, with summary methods."""

    def __init__(self):
        self.load()

    # ---------- Loading and saving ----------

    def load(self):
        """Read transactions, budget limits and starting cash from the data folder."""
        table = storage.load_table("transactions")
        table["id"] = pd.to_numeric(table["id"]).astype(int)
        table["date"] = pd.to_datetime(table["date"])
        table["amount"] = pd.to_numeric(table["amount"]).astype(float)
        table["note"] = table["note"].fillna("").astype(str)
        self.transactions = table

        # Monthly limits as a dictionary: {"Groceries": 400.0, ...}
        self.limits = {}
        for _, row in storage.load_table("budgets").iterrows():
            self.limits[row["category"]] = float(row["monthly_limit"])

        settings = storage.load_settings()
        self.starting_cash = float(settings.get("starting_cash", 0))

    def save(self):
        """Write the transactions back to transactions.csv (sorted by date)."""
        table = self.transactions.sort_values(["date", "id"]).copy()
        table["date"] = table["date"].dt.strftime("%Y-%m-%d")
        storage.save_table("transactions", table)

    # ---------- Changing data ----------

    def add(self, transaction):
        """Check and save a new Transaction. Returns (success, message)."""
        error = transaction.check()
        if error is not None:
            return False, error
        if self.transactions.empty:
            next_id = 1
        else:
            next_id = int(self.transactions["id"].max()) + 1
        new_row = pd.DataFrame([{
            "id": next_id,
            "date": pd.Timestamp(transaction.date),
            "type": transaction.kind,
            "category": transaction.category,
            "amount": transaction.amount,
            "note": transaction.note,
        }])
        if self.transactions.empty:
            self.transactions = new_row
        else:
            self.transactions = pd.concat([self.transactions, new_row], ignore_index=True)
        self.save()
        return True, f"Saved: {transaction}"

    def delete(self, ids):
        """Delete the transactions whose id is in the list `ids`. Returns how many were removed."""
        keep = ~self.transactions["id"].isin(ids)
        removed = len(self.transactions) - int(keep.sum())
        self.transactions = self.transactions[keep]
        self.save()
        return removed

    def set_limits(self, limits):
        """Save new monthly budget limits, e.g. {"Groceries": 400, ...}."""
        rows = []
        for category, limit in limits.items():
            rows.append({"category": category, "monthly_limit": float(limit)})
        storage.save_table("budgets", pd.DataFrame(rows, columns=storage.TABLE_COLUMNS["budgets"]))
        self.limits = dict(limits)

    def set_starting_cash(self, amount):
        """Save the cash you had when you started using the tracker."""
        settings = storage.load_settings()
        settings["starting_cash"] = float(amount)
        storage.save_settings(settings)
        self.starting_cash = float(amount)

    # ---------- Looking things up ----------

    def is_empty(self):
        return self.transactions.empty

    def first_date(self):
        """Date of the earliest transaction (or today if there are none)."""
        if self.transactions.empty:
            return date.today()
        return self.transactions["date"].min().date()

    def period_range(self, period, today=None):
        """Like period_dates(), but "All time" starts at the first transaction."""
        start, end = period_dates(period, today)
        if start is None:
            start = min(self.first_date(), end)
        return start, end

    def in_range(self, start, end, kind=None):
        """Transactions from start to end (both included), optionally only one kind."""
        table = self.transactions
        table = table[(table["date"] >= pd.Timestamp(start)) & (table["date"] <= pd.Timestamp(end))]
        if kind is not None:
            table = table[table["type"] == kind]
        return table

    # ---------- Summaries ----------

    def total(self, start, end, kind="Expense"):
        """Total expenses (or income) between two dates."""
        return float(self.in_range(start, end, kind)["amount"].sum())

    def flexible_total(self, start, end):
        """Total spending between two dates, leaving out fixed bills."""
        expenses = self.in_range(start, end, "Expense")
        flexible = expenses[~expenses["category"].isin(FIXED_CATEGORIES)]
        return float(flexible["amount"].sum())

    def by_category(self, start, end):
        """Total spending per category, largest first (a pandas Series)."""
        expenses = self.in_range(start, end, "Expense")
        totals = expenses.groupby("category")["amount"].sum()
        return totals.sort_values(ascending=False)

    def daily_spending(self, start, end, flexible_only=False):
        """Spending on every day in the range. Days with no spending show $0."""
        expenses = self.in_range(start, end, "Expense")
        if flexible_only:
            expenses = expenses[~expenses["category"].isin(FIXED_CATEGORIES)]
        per_day = expenses.groupby("date")["amount"].sum()
        all_days = pd.date_range(start, end, freq="D")
        return per_day.reindex(all_days, fill_value=0.0)

    def cash_on_hand(self):
        """Starting cash + all income - all expenses."""
        income = self.transactions[self.transactions["type"] == "Income"]["amount"].sum()
        spent = self.transactions[self.transactions["type"] == "Expense"]["amount"].sum()
        return self.starting_cash + float(income) - float(spent)

    def cash_history(self, today=None):
        """Your cash balance at the end of every day, from your first entry to today."""
        if today is None:
            today = date.today()
        if self.transactions.empty:
            return pd.Series(dtype=float, index=pd.DatetimeIndex([]))
        table = self.transactions
        # Income adds to your cash (+) and expenses take away from it (-).
        signed = table["amount"].where(table["type"] == "Income", -table["amount"])
        daily_change = signed.groupby(table["date"]).sum()
        all_days = pd.date_range(self.first_date(), today, freq="D")
        daily_change = daily_change.reindex(all_days, fill_value=0.0)
        return self.starting_cash + daily_change.cumsum()

    def total_budget(self):
        """Sum of all monthly limits."""
        total = 0.0
        for limit in self.limits.values():
            total += limit
        return total

    def budget_status(self, today=None):
        """This month's spending compared with each category's monthly limit."""
        start, end = period_dates("This month", today)
        spent = self.by_category(start, end)
        rows = []
        for category in EXPENSE_CATEGORIES:
            limit = self.limits.get(category, 0.0)
            amount = float(spent.get(category, 0.0))
            if limit <= 0 and amount <= 0:
                continue  # nothing budgeted and nothing spent
            if limit <= 0:
                percent = None
                status = "No budget set"
            else:
                percent = amount / limit * 100
                if amount > limit:
                    status = "Over budget"
                elif percent >= 85 and category not in FIXED_CATEGORIES:
                    status = "Near limit"   # fixed bills are supposed to use their whole budget
                else:
                    status = "On track"
            rows.append({
                "category": category, "budget": limit, "spent": amount,
                "remaining": limit - amount, "percent_used": percent, "status": status,
            })
        columns = ["category", "budget", "spent", "remaining", "percent_used", "status"]
        return pd.DataFrame(rows, columns=columns)

    def daily_allowance(self, today=None):
        """How much flexible spending fits in your budget for each day left this month.

            allowance = (flexible budget - flexible spending before today) / days left
        """
        if today is None:
            today = date.today()
        month_start = today.replace(day=1)
        flexible_budget = 0.0
        for category, limit in self.limits.items():
            if category not in FIXED_CATEGORIES:
                flexible_budget += limit
        spent_before_today = 0.0
        if today > month_start:
            spent_before_today = self.flexible_total(month_start, today - timedelta(days=1))
        spent_today = self.flexible_total(today, today)
        days_left = days_in_month(today) - today.day + 1  # including today
        allowance = max(flexible_budget - spent_before_today, 0.0) / days_left
        return {
            "flexible_budget": flexible_budget,
            "allowance": allowance,
            "spent_today": spent_today,
            "left_today": allowance - spent_today,
            "days_left": days_left,
            "remaining": flexible_budget - spent_before_today - spent_today,
        }

    def projected_month_spending(self, today=None):
        """Estimate this month's total spending if you keep your current pace.

            flexible spending: (spent so far / days passed) * days in the month
            fixed bills: the budgeted amount, or what you've already paid if that's more
        """
        if today is None:
            today = date.today()
        month_start = today.replace(day=1)
        flexible_so_far = self.flexible_total(month_start, today)
        flexible_estimate = flexible_so_far / today.day * days_in_month(today)
        spent = self.by_category(month_start, today)
        fixed_estimate = 0.0
        for category in FIXED_CATEGORIES:
            paid = float(spent.get(category, 0.0))
            fixed_estimate += max(paid, self.limits.get(category, 0.0))
        return fixed_estimate + flexible_estimate

    def savings_rate(self, start, end):
        """Percent of income you kept: (income - expenses) / income * 100."""
        income = self.total(start, end, "Income")
        if income <= 0:
            return None
        spent = self.total(start, end, "Expense")
        return (income - spent) / income * 100

    def average_monthly_spending(self, today=None):
        """Average spending per month, based on up to the last 90 days."""
        if today is None:
            today = date.today()
        if self.transactions.empty:
            return 0.0
        start = max(self.first_date(), today - timedelta(days=89))
        days = (today - start).days + 1
        return self.total(start, today) / days * 30.4  # 30.4 = average days per month

    # ---------- Tips ----------

    def insights(self, today=None):
        """Plain-English tips about your spending habits.
        Returns a list of (level, message) tuples; level is "good", "warning" or "info"."""
        if today is None:
            today = date.today()
        if self.transactions.empty:
            return [("info", "Add a few expenses and personalized tips will show up here.")]

        tips = []
        month_start = today.replace(day=1)
        month_passed = today.day / days_in_month(today)       # e.g. 0.5 = halfway through
        days_left = days_in_month(today) - today.day + 1
        spent_this_month = self.by_category(month_start, today)
        days_tracked = (today - self.first_date()).days + 1   # some tips need 2+ weeks of data

        if self.total_budget() == 0:
            tips.append(("info", "Set monthly budgets on the Settings tab to get budget alerts."))

        # 1. Categories that are over budget or being spent too fast.
        for category in EXPENSE_CATEGORIES:
            limit = self.limits.get(category, 0.0)
            if limit <= 0:
                continue
            amount = float(spent_this_month.get(category, 0.0))
            used = amount / limit
            if amount > limit:
                tips.append(("warning",
                             f"You're over your {category} budget by ${amount - limit:,.0f} this month."))
            elif category not in FIXED_CATEGORIES and used >= 0.5 and used > month_passed + 0.15:
                per_day = (limit - amount) / days_left
                tips.append(("warning",
                             f"{category} is at {used:.0%} of its budget with {month_passed:.0%} of the "
                             f"month gone. Keep it under ${per_day:,.0f} a day to stay on budget."))

        # 2. How much of your income you kept over the last 30 days.
        last30_start = today - timedelta(days=29)
        income = self.total(last30_start, today, "Income")
        spent = self.total(last30_start, today, "Expense")
        if income > 0:
            rate = (income - spent) / income
            if rate < 0:
                tips.append(("warning",
                             f"In the last 30 days you spent ${spent - income:,.0f} more than you earned."))
            elif rate < 0.20:
                extra = 0.20 * income - (income - spent)
                tips.append(("info",
                             f"You saved {rate:.0%} of your income in the last 30 days. Saving about "
                             f"${extra:,.0f} more a month would reach the common 20% goal."))
            else:
                tips.append(("good", f"Nice work - you saved {rate:.0%} of your income in the last 30 days."))

        # 3. Your biggest flexible category, and what a small cut would save.
        recent_totals = self.by_category(last30_start, today)
        flexible_totals = recent_totals[~recent_totals.index.isin(FIXED_CATEGORIES)]
        if not flexible_totals.empty:
            top_category = flexible_totals.index[0]
            top_amount = float(flexible_totals.iloc[0])
            tips.append(("info",
                         f"{top_category} was your biggest flexible expense in the last 30 days "
                         f"(${top_amount:,.0f}). Cutting it by 10% would save about "
                         f"${top_amount * 0.10 * 12:,.0f} a year."))

        # 4. Weekends vs. weekdays.
        daily = self.daily_spending(last30_start, today, flexible_only=True)
        weekend = daily[daily.index.dayofweek >= 5]   # Saturday = 5, Sunday = 6
        weekday = daily[daily.index.dayofweek < 5]
        if days_tracked >= 14 and len(weekend) > 0 and len(weekday) > 0 and weekday.mean() > 0:
            ratio = weekend.mean() / weekday.mean()
            if ratio >= 1.25:
                tips.append(("info",
                             f"You spend {ratio - 1:.0%} more per day on weekends "
                             f"(${weekend.mean():,.0f} vs. ${weekday.mean():,.0f} on weekdays). "
                             f"Planning weekend activities ahead of time can help."))

        # 5. Small purchases that add up.
        recent = self.in_range(last30_start, today, "Expense")
        small = recent[(recent["amount"] < 15) & (~recent["category"].isin(FIXED_CATEGORIES))]
        if len(small) >= 8:
            small_total = float(small["amount"].sum())
            tips.append(("info",
                         f"You made {len(small)} purchases under $15 in the last 30 days, adding up to "
                         f"${small_total:,.0f}. At that pace that's about ${small_total * 12:,.0f} a year."))

        # 6. Emergency fund: how many months of spending your cash would cover.
        monthly_spending = self.average_monthly_spending(today)
        cash = self.cash_on_hand()
        if cash <= 0:
            tips.append(("warning", "Your cash on hand is $0 or less. Check your starting cash on the Settings tab."))
        elif monthly_spending > 0 and days_tracked >= 14:
            months = cash / monthly_spending
            if months < 3:
                tips.append(("warning",
                             f"Your cash covers about {months:.1f} months of spending. Many experts "
                             f"suggest keeping 3-6 months saved for emergencies."))
            else:
                tips.append(("good",
                             f"Your cash covers about {months:.1f} months of spending - a solid emergency fund."))
        return tips
