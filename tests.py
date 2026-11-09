"""
tests.py - Automated checks for the Stock & Budget Tracker.

Run with:   python tests.py

Each test function checks one feature and uses `assert` to compare the
expected result with the actual result. The tests use a temporary data
folder, so your real data is never touched.
"""

import shutil
import tempfile
from datetime import date, timedelta

import storage

# Point the app at a temporary folder before any data is loaded or saved.
TEST_FOLDER = tempfile.mkdtemp()
storage.DATA_FOLDER = TEST_FOLDER

import assets       # noqa: E402  (imported after changing the data folder on purpose)
import budget       # noqa: E402
import portfolio    # noqa: E402
import projections  # noqa: E402
import sample_data  # noqa: E402


def close(actual, expected, tolerance=0.01):
    """True if two numbers are equal to within `tolerance`."""
    return abs(actual - expected) <= tolerance


def fresh_tracker(starting_cash=1000.0, limits=None):
    """Start each test with an empty tracker."""
    if limits is None:
        limits = {}
    storage.create_empty_files(starting_cash, limits)
    return budget.Budget()


# ---------- Finance formulas ----------

def test_future_value():
    # $1,000 plus $100 a month at 6% for 10 years
    result = projections.future_value(1000, 100, 6, 10)
    assert close(result, 18207.33), f"expected about $18,207.33, got {result:,.2f}"


def test_future_value_with_zero_rate():
    # With no growth you end up with exactly what you put in.
    assert projections.future_value(1000, 100, 0, 1) == 2200


def test_loan_payment():
    # A $200,000, 30-year mortgage at 6% costs about $1,199.10 a month.
    result = projections.loan_payment(200000, 6, 30)
    assert close(result, 1199.10), f"expected about $1,199.10, got {result:,.2f}"


def test_months_to_payoff_matches_schedule():
    months = projections.months_to_payoff(12400, 6.9, 380)
    schedule = projections.amortization_schedule(12400, 6.9, 380)
    assert months == 37, f"expected 37 months, got {months}"
    assert len(schedule) == months, "the formula and the month-by-month schedule disagree"


def test_payment_too_small_is_handled():
    # ERROR CASE: $10,000 at 24% charges $200 interest a month, so a $150
    # payment never pays it off. The app should say so instead of crashing.
    assert projections.months_to_payoff(10000, 24, 150) is None
    assert projections.total_interest(10000, 24, 150) is None


def test_cagr():
    # Doubling in 5 years is about 14.87% a year.
    assert close(projections.cagr(100, 200, 5), 14.87)


def test_savings_goal_formulas_agree():
    # Saving the "needed" amount each month should reach the goal right on time.
    needed = projections.monthly_savings_needed(0, 10000, 5, 24)
    months = projections.months_to_goal(0, 10000, needed, 5)
    assert months == 24, f"expected 24 months, got {months}"


def test_rule_of_72():
    assert projections.years_to_double(8) == 9


# ---------- Budget and transactions ----------

def test_add_transactions_and_cash():
    my_budget = fresh_tracker(starting_cash=1000)
    today = date.today()
    ok, _ = my_budget.add(budget.Transaction(today, "Expense", "Dining Out", 12.50, "Lunch"))
    assert ok
    ok, _ = my_budget.add(budget.Transaction(today, "Income", "Paycheck", 500, ""))
    assert ok
    assert my_budget.total(today, today, "Expense") == 12.50
    assert my_budget.total(today, today, "Income") == 500
    assert close(my_budget.cash_on_hand(), 1000 + 500 - 12.50)
    # The new transactions were saved to the CSV file and load back correctly.
    assert len(budget.Budget().transactions) == 2


def test_bad_transactions_are_rejected():
    # ERROR CASE: invalid input gets a clear message and nothing is saved.
    my_budget = fresh_tracker()
    today = date.today()
    ok, message = my_budget.add(budget.Transaction(today, "Expense", "Groceries", 0))
    assert not ok and "more than $0" in message
    ok, message = my_budget.add(budget.Transaction(today + timedelta(days=1), "Expense", "Groceries", 20))
    assert not ok and "future" in message
    ok, message = my_budget.add(budget.Transaction(today, "Expense", "Paycheck", 20))
    assert not ok and "not a valid" in message
    assert my_budget.is_empty()


def test_delete_transaction():
    my_budget = fresh_tracker()
    today = date.today()
    my_budget.add(budget.Transaction(today, "Expense", "Shopping", 40))
    my_budget.add(budget.Transaction(today, "Expense", "Shopping", 60))
    first_id = int(my_budget.transactions["id"].iloc[0])
    assert my_budget.delete([first_id]) == 1
    assert my_budget.total(today, today) == 60


def test_over_budget_is_flagged():
    my_budget = fresh_tracker(limits={"Dining Out": 50})
    today = date.today()
    my_budget.add(budget.Transaction(today, "Expense", "Dining Out", 60))
    status = my_budget.budget_status(today)
    dining = status[status["category"] == "Dining Out"].iloc[0]
    assert dining["status"] == "Over budget"
    messages = []
    for level, message in my_budget.insights(today):
        messages.append(message)
    assert any("over your Dining Out budget" in message for message in messages)


def test_daily_allowance():
    my_budget = fresh_tracker(limits={"Groceries": 310, "Housing": 1000})
    today = date.today()
    my_budget.add(budget.Transaction(today, "Expense", "Groceries", 10))
    my_budget.add(budget.Transaction(today, "Expense", "Housing", 1000))   # fixed bills don't count
    days_left = budget.days_in_month(today) - today.day + 1
    allowance = my_budget.daily_allowance(today)
    assert close(allowance["allowance"], 310 / days_left)
    assert close(allowance["left_today"], 310 / days_left - 10)


# ---------- Investments ----------

def test_average_cost_when_buying_more():
    fresh_tracker()
    my_portfolio = portfolio.Portfolio()
    my_portfolio.add("aapl", 10, 100)
    ok, message = my_portfolio.add("AAPL", 10, 200)
    holding = my_portfolio.find("AAPL")
    assert ok and holding.shares == 20
    assert holding.avg_cost == 150, f"expected $150 average cost, got {holding.avg_cost}"
    holding.price = 180
    assert holding.gain() == 20 * 180 - 20 * 150


def test_bad_stock_input_is_rejected():
    # ERROR CASE: missing ticker or zero shares.
    fresh_tracker()
    my_portfolio = portfolio.Portfolio()
    assert my_portfolio.add("", 5, 100)[0] is False
    assert my_portfolio.add("MSFT", 0, 100)[0] is False
    assert len(my_portfolio.holdings) == 0


def test_unknown_ticker_returns_none():
    # ERROR CASE: a ticker that doesn't exist (or no internet) returns None
    # instead of crashing the app.
    assert portfolio.lookup("NOT-A-REAL-TICKER-123") is None


# ---------- Loans, property and net worth ----------

def test_loan_and_net_worth():
    car_loan = assets.Loan("Car loan", "Auto", 12400, 6.9, 380)
    assert car_loan.months_left() == 37
    assert car_loan.months_left(extra_payment=100) < 37
    car = assets.Property("Car", "Vehicle", 5000, -10)
    assert close(car.value_in(1), 4500)
    worth = assets.net_worth(1000, 2000, [car], [car_loan])
    assert worth["net_worth"] == 1000 + 2000 + 5000 - 12400


def test_sample_data_loads():
    sample_data.create_sample_data()
    my_budget = budget.Budget()
    assert len(my_budget.transactions) > 100
    assert len(portfolio.Portfolio().holdings) == 5
    assert len(assets.load_loans()) == 4
    assert len(my_budget.insights()) > 0


# ---------- Run everything ----------

def run_all_tests():
    tests = [
        test_future_value, test_future_value_with_zero_rate, test_loan_payment,
        test_months_to_payoff_matches_schedule, test_payment_too_small_is_handled, test_cagr,
        test_savings_goal_formulas_agree, test_rule_of_72, test_add_transactions_and_cash,
        test_bad_transactions_are_rejected, test_delete_transaction, test_over_budget_is_flagged,
        test_daily_allowance, test_average_cost_when_buying_more, test_bad_stock_input_is_rejected,
        test_unknown_ticker_returns_none, test_loan_and_net_worth, test_sample_data_loads,
    ]
    passed = 0
    for test in tests:
        try:
            test()
            print(f"PASS   {test.__name__}")
            passed += 1
        except AssertionError as error:
            print(f"FAIL   {test.__name__}: {error}")
        except Exception as error:
            print(f"ERROR  {test.__name__}: {error!r}")
    print(f"\n{passed} of {len(tests)} tests passed.")
    shutil.rmtree(TEST_FOLDER, ignore_errors=True)


if __name__ == "__main__":
    run_all_tests()
