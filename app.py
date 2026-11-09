"""
app.py - The Stock & Budget Tracker web app, built with Streamlit.

Start it from this folder with:
    streamlit run app.py

How Streamlit works: every time you click a button or change an input,
Streamlit runs this whole file again from top to bottom. Each run reloads
the data from the CSV files and redraws the page, so the screen always
matches what's saved.
"""

from datetime import date, timedelta

import matplotlib.pyplot as plt
import pandas as pd
import streamlit as st

import assets
import budget
import charts
import portfolio
import projections
import sample_data
import storage

st.set_page_config(page_title="Stock & Budget Tracker", page_icon=":material/savings:", layout="wide")


# =====================================================================
# Small helpers used by every page
# =====================================================================

def money(amount, decimals=0):
    """Format dollars: 1234.5 -> "$1,235" and -50 -> "-$50"."""
    sign = "-" if amount < 0 else ""
    return f"{sign}${abs(amount):,.{decimals}f}"


def md(text):
    """Streamlit treats text between two $ signs as a math formula, so
    escape every $ before showing text that contains dollar amounts."""
    return text.replace("$", "\\$")


def show_chart(fig):
    """Display a matplotlib figure, then close it to free memory."""
    st.pyplot(fig, width="stretch")
    plt.close(fig)


def show_tips(tips):
    """Show a list of (level, message) tips: warnings first, then ideas, then good news."""
    for level in ["warning", "info", "good"]:
        for tip_level, message in tips:
            if tip_level != level:
                continue
            if level == "warning":
                st.warning(md(message), icon=":material/warning:")
            elif level == "good":
                st.success(md(message), icon=":material/check_circle:")
            else:
                st.info(md(message), icon=":material/lightbulb:")


def flash(message):
    """Remember a message so it can be shown after the page reloads."""
    st.session_state["flash"] = message


def show_flash():
    """Show (and forget) the remembered message as a pop-up."""
    if "flash" in st.session_state:
        st.toast(md(st.session_state.pop("flash")), icon=":material/check_circle:")


def editor_version(name):
    """A number that changes whenever a table's rows are saved, so the table
    editor starts fresh instead of keeping old checkboxes."""
    return st.session_state.get(name, 0)


def bump_version(name):
    st.session_state[name] = editor_version(name) + 1


def is_blank(value):
    """True if a table cell was left empty."""
    return value is None or pd.isna(value)


@st.cache_data(ttl=900, show_spinner="Getting the latest stock prices...")
def get_stock_data(ticker):
    """Download one ticker's price history with yfinance.
    Streamlit caches (remembers) the result for 15 minutes, so clicking
    around the app doesn't download the same prices again and again."""
    return portfolio.lookup(ticker)


def suggested_monthly_savings(my_budget, today):
    """Average (income - spending) per month over up to the last 90 days, rounded to $50."""
    start = max(my_budget.first_date(), today - timedelta(days=89))
    days = (today - start).days + 1
    income = my_budget.total(start, today, "Income") / days * 30.4
    spending = my_budget.total(start, today, "Expense") / days * 30.4
    if income - spending <= 0:
        return 200.0
    return float(round((income - spending) / 50) * 50)


# =====================================================================
# Welcome screen (first run, before any data exists)
# =====================================================================

def show_welcome():
    st.title("Welcome to your Stock & Budget Tracker")
    st.write("Track your daily spending, investments, loans and property in one place. "
             "How would you like to start?")
    left, right = st.columns(2, gap="large")
    with left:
        with st.container(border=True):
            st.subheader("Explore with sample data")
            st.write("Loads 90 days of example spending and income, five stocks, "
                     "four loans and two properties. You can erase it any time on the Settings tab.")
            if st.button("Load sample data", type="primary", icon=":material/play_arrow:"):
                sample_data.create_sample_data()
                flash("Sample data loaded. Have a look around!")
                st.rerun()
    with right:
        with st.container(border=True):
            st.subheader("Start fresh")
            cash = st.number_input("How much cash do you have right now (checking + savings)?",
                                   min_value=0.0, step=100.0, format="%.2f")
            st.caption("You'll get a starter monthly budget that you can change on the Settings tab.")
            if st.button("Start my tracker", icon=":material/add:"):
                storage.create_empty_files(cash, budget.DEFAULT_LIMITS)
                flash("Your tracker is ready. Add your first expense!")
                st.rerun()


# =====================================================================
# Sidebar: quick add + today's allowance (visible on every tab)
# =====================================================================

def show_sidebar(my_budget, today):
    with st.sidebar:
        st.header("Quick add")
        with st.form("quick_add", clear_on_submit=True):
            amount = st.number_input("Amount ($)", min_value=0.0, step=1.0, format="%.2f")
            category = st.selectbox("Category", budget.EXPENSE_CATEGORIES,
                                    index=budget.EXPENSE_CATEGORIES.index("Dining Out"))
            note = st.text_input("Note (optional)", placeholder="e.g. Coffee")
            submitted = st.form_submit_button("Add today's expense", type="primary", width="stretch")
        if submitted:
            ok, message = my_budget.add(budget.Transaction(today, "Expense", category, amount, note))
            if ok:
                flash(message)
                st.rerun()
            else:
                st.error(md(message))

        allowance = my_budget.daily_allowance(today)
        if allowance["flexible_budget"] > 0:
            st.divider()
            if allowance["left_today"] >= 0:
                st.metric("Left to spend today", money(allowance["left_today"], 2))
            else:
                st.metric("Over today's allowance by", money(-allowance["left_today"], 2))
            st.caption(md(f"Daily allowance: {money(allowance['allowance'], 2)} for flexible spending "
                          f"(everything except housing, utilities and debt payments)."))


# =====================================================================
# Tab 1: Overview
# =====================================================================

def show_overview(my_budget, my_portfolio, loans, worth, today):
    allowance = my_budget.daily_allowance(today)
    month_start = today.replace(day=1)
    spent_this_month = my_budget.total(month_start, today)
    monthly_budget = my_budget.total_budget()
    projected = my_budget.projected_month_spending(today)
    savings_rate = my_budget.savings_rate(today - timedelta(days=29), today)

    st.subheader("Your money at a glance")
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Net worth", money(worth["net_worth"]), border=True,
                help="Everything you own (cash, investments, property) minus everything you owe.")
    col2.metric("Cash on hand", money(worth["cash"]), border=True,
                help="Starting cash + all income - all expenses.")
    day_change = None
    for holding in my_portfolio.holdings:
        if holding.is_live:
            day_change = f"{money(my_portfolio.day_change())} today"
    col3.metric("Investments", money(worth["investments"]), delta=day_change, border=True)
    col4.metric("Total debt", money(worth["debt"]), border=True)

    st.subheader(f"{today:%B} so far")
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        if allowance["flexible_budget"] <= 0:
            st.metric("Daily allowance", "Not set", border=True)
            st.caption("Set budgets on the Settings tab.")
        elif allowance["left_today"] >= 0:
            st.metric("You can still spend today", money(allowance["left_today"]), border=True,
                      help="Your flexible budget left this month, spread evenly over the days left, "
                           "minus what you've spent today.")
        else:
            st.metric("Over today's allowance by", money(-allowance["left_today"]), border=True)
    with col2:
        st.metric("Spent this month", money(spent_this_month), border=True)
        if monthly_budget > 0:
            used = spent_this_month / monthly_budget
            st.progress(min(used, 1.0), text=md(f"{used:.0%} of your {money(monthly_budget)} budget"))
    with col3:
        st.metric("Projected for the month", money(projected), border=True,
                  help="Fixed bills at their budgeted amount plus your flexible spending "
                       "pace so far, extended to the end of the month.")
        if monthly_budget > 0:
            difference = monthly_budget - projected
            if difference >= 0:
                st.caption(md(f"On pace to finish {money(difference)} under budget."))
            else:
                st.caption(md(f"On pace to go {money(-difference)} over budget."))
    with col4:
        if savings_rate is None:
            st.metric("Savings rate (30 days)", "No income yet", border=True)
        else:
            st.metric("Savings rate (30 days)", f"{savings_rate:.0f}%", border=True,
                      help="(Income - spending) / income over the last 30 days. 20% is a common goal.")

    left, right = st.columns(2, gap="large")
    with left:
        st.markdown("**Cash on hand, last 90 days**")
        history = my_budget.cash_history(today)
        history = history[history.index >= pd.Timestamp(today - timedelta(days=89))]
        if len(history) > 1:
            show_chart(charts.balance_over_time(history))
        else:
            st.info("This chart appears once you've logged a few days of transactions.")
    with right:
        st.markdown("**What you own vs. what you owe**")
        show_chart(charts.net_worth_breakdown(worth))

    st.subheader("Tips for you")
    show_tips(my_budget.insights(today) + assets.debt_insights(loans))


# =====================================================================
# Tab 2: Daily Log
# =====================================================================

def show_daily_log(my_budget, today):
    left, right = st.columns([1, 1.3], gap="large")
    with left:
        st.subheader("Add a transaction")
        kind = st.radio("Type", ["Expense", "Income"], horizontal=True, key="log_kind")
        if kind == "Expense":
            categories = budget.EXPENSE_CATEGORIES
        else:
            categories = budget.INCOME_CATEGORIES
        with st.form("add_transaction", clear_on_submit=True):
            when = st.date_input("Date", value=today, max_value=today, format="MM/DD/YYYY")
            category = st.selectbox("Category", categories)
            amount = st.number_input("Amount ($)", min_value=0.0, step=1.0, format="%.2f")
            note = st.text_input("Note (optional)", placeholder="e.g. Lunch with a friend")
            submitted = st.form_submit_button(f"Save {kind.lower()}", type="primary", width="stretch")
        if submitted:
            ok, message = my_budget.add(budget.Transaction(when, kind, category, amount, note))
            if ok:
                flash(message)
                st.rerun()
            else:
                st.error(md(message))

    with right:
        st.subheader(f"Today, {today:%B} {today.day}")
        allowance = my_budget.daily_allowance(today)
        col1, col2 = st.columns(2)
        col1.metric("Spent today", money(my_budget.total(today, today), 2), border=True)
        if allowance["flexible_budget"] <= 0:
            col2.metric("Left to spend today", "Not set", border=True)
        elif allowance["left_today"] >= 0:
            col2.metric("Left to spend today", money(allowance["left_today"], 2), border=True)
        else:
            col2.metric("Over today's allowance", money(-allowance["left_today"], 2), border=True)
        if allowance["flexible_budget"] > 0:
            st.caption(md(f"Your flexible budget allows about {money(allowance['allowance'], 2)} a day for "
                          f"the {allowance['days_left']} days left this month. Fixed bills (housing, "
                          f"utilities, debt payments) aren't counted here."))
        todays = my_budget.in_range(today, today)
        if todays.empty:
            st.info("Nothing logged today yet.")
        else:
            st.dataframe(
                todays[["type", "category", "amount", "note"]].rename(columns={
                    "type": "Type", "category": "Category", "amount": "Amount", "note": "Note"}),
                hide_index=True, width="stretch",
                column_config={"Amount": st.column_config.NumberColumn(format="dollar")},
            )

    st.divider()
    st.subheader("Transaction history")
    col1, col2, col3, col4 = st.columns([1, 1, 2, 2])
    period = col1.selectbox("Period", budget.PERIODS, index=3, key="log_period")
    kind_filter = col2.selectbox("Type", ["All", "Expense", "Income"], key="log_kind_filter")
    chosen_categories = col3.multiselect("Categories", budget.EXPENSE_CATEGORIES + budget.INCOME_CATEGORIES,
                                         placeholder="All categories", key="log_categories")
    search = col4.text_input("Search notes", placeholder="e.g. coffee", key="log_search")

    start, end = my_budget.period_range(period, today)
    view = my_budget.in_range(start, end)
    if kind_filter != "All":
        view = view[view["type"] == kind_filter]
    if len(chosen_categories) > 0:
        view = view[view["category"].isin(chosen_categories)]
    if search.strip() != "":
        view = view[view["note"].str.contains(search.strip(), case=False, regex=False)]
    view = view.sort_values(["date", "id"], ascending=False)

    if view.empty:
        st.info("No transactions match these filters.")
        return

    table = pd.DataFrame({
        "Delete": False,
        "Date": view["date"].dt.date,
        "Type": view["type"],
        "Category": view["category"],
        "Amount": view["amount"],
        "Note": view["note"],
    })
    table.index = view["id"].values   # each row is labeled with its transaction id

    # The editor's key includes the filters, so changing a filter clears old checkboxes.
    editor_key = (f"history_{editor_version('history_version')}_{period}_{kind_filter}_"
                  f"{'-'.join(chosen_categories)}_{search}")
    edited = st.data_editor(
        table, key=editor_key, hide_index=True, width="stretch",
        disabled=["Date", "Type", "Category", "Amount", "Note"],
        column_config={
            "Delete": st.column_config.CheckboxColumn("Delete?", width="small",
                                                      help="Tick rows, then press the Delete button below."),
            "Date": st.column_config.DateColumn(format="MMM D, YYYY"),
            "Amount": st.column_config.NumberColumn(format="dollar"),
        },
    )

    selected_ids = []
    for transaction_id, row in edited.iterrows():
        if row["Delete"]:
            selected_ids.append(int(transaction_id))

    spent = float(view[view["type"] == "Expense"]["amount"].sum())
    earned = float(view[view["type"] == "Income"]["amount"].sum())
    st.caption(md(f"{len(view)} transactions  ·  {money(spent, 2)} spent  ·  {money(earned, 2)} income"))

    col1, col2, _ = st.columns([1, 1, 3])
    if col1.button(f"Delete {len(selected_ids)} selected", disabled=len(selected_ids) == 0,
                   icon=":material/delete:", width="stretch"):
        removed = my_budget.delete(selected_ids)
        bump_version("history_version")
        flash(f"Deleted {removed} transaction(s).")
        st.rerun()
    col2.download_button("Download CSV", data=table.drop(columns="Delete").to_csv(index=False),
                         file_name="transactions.csv", mime="text/csv",
                         icon=":material/download:", width="stretch")


# =====================================================================
# Tab 3: Spending Summary
# =====================================================================

def show_summary(my_budget, today):
    period = st.radio("Show", budget.PERIODS, index=2, horizontal=True, key="summary_period")
    start, end = my_budget.period_range(period, today)
    days = (end - start).days + 1
    spent = my_budget.total(start, end)
    earned = my_budget.total(start, end, "Income")
    st.caption(f"{start:%b %d, %Y} to {end:%b %d, %Y}  ({days} days)")

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Spent", money(spent), border=True)
    col2.metric("Income", money(earned), border=True)
    col3.metric("Income - spending", money(earned - spent), border=True,
                help="Positive means you earned more than you spent.")
    col4.metric("Average spent per day", money(spent / days), border=True)

    left, right = st.columns(2, gap="large")
    with left:
        st.markdown("**Spending by category**")
        totals = my_budget.by_category(start, end)
        if totals.empty:
            st.info("No spending in this period.")
        else:
            show_chart(charts.spending_by_category(totals))
            with st.expander("See as a table"):
                category_table = pd.DataFrame({
                    "Category": totals.index,
                    "Spent": totals.values,
                    "Share of spending": totals.values / totals.sum() * 100,
                })
                st.dataframe(category_table, hide_index=True, width="stretch", column_config={
                    "Spent": st.column_config.NumberColumn(format="dollar"),
                    "Share of spending": st.column_config.NumberColumn(format="%.1f%%"),
                })
    with right:
        st.markdown("**Day-to-day spending**")
        if days < 2:
            st.info("Pick a longer period to see spending over time.")
        else:
            daily = my_budget.daily_spending(start, end, flexible_only=True)
            flexible_budget = my_budget.daily_allowance(today)["flexible_budget"]
            daily_pace = flexible_budget / 30.4      # planned flexible spending per day
            if days > 62:
                series = daily.resample("W").sum()   # long periods: show weekly totals
                reference = daily_pace * 7
                note = f"Gray line = planned pace ({money(reference)} a week)"
            else:
                series = daily
                reference = daily_pace
                note = f"Gray line = planned pace ({money(reference)} a day)"
            if flexible_budget <= 0:
                reference = None
            # For "This week" and "This month", show the whole week/month so the
            # days still ahead appear as empty space.
            last_day = None
            if period == "This week":
                last_day = start + timedelta(days=6)
            elif period == "This month":
                last_day = today.replace(day=budget.days_in_month(today))
            show_chart(charts.spending_over_time(series, reference, note, last_day))
            st.caption("Fixed bills (housing, utilities, debt payments) are left out "
                       "so everyday spending is easier to see.")

    st.subheader(f"{today:%B} budget")
    status = my_budget.budget_status(today)
    if status.empty:
        st.info("No budgets yet. Add them on the Settings tab.")
    else:
        st.dataframe(
            status.rename(columns={"category": "Category", "budget": "Budget", "spent": "Spent",
                                   "remaining": "Remaining", "percent_used": "Used", "status": "Status"}),
            hide_index=True, width="stretch", height="content",
            column_config={
                "Budget": st.column_config.NumberColumn(format="dollar"),
                "Spent": st.column_config.NumberColumn(format="dollar"),
                "Remaining": st.column_config.NumberColumn(format="dollar"),
                "Used": st.column_config.ProgressColumn(format="%.0f%%", min_value=0, max_value=100),
            },
        )
        st.caption("Personalized tips are on the Overview tab.")


# =====================================================================
# Tab 4: Investments
# =====================================================================

def show_investments(my_portfolio, offline_tickers, today):
    title_col, button_col = st.columns([4, 1])
    title_col.subheader("Your investments")
    if button_col.button("Refresh prices", icon=":material/refresh:", width="stretch"):
        get_stock_data.clear()   # forget the cached prices so they download again
        st.rerun()

    if len(offline_tickers) > 0:
        st.warning(f"Couldn't download live prices for {', '.join(offline_tickers)}, so the last saved "
                   f"prices are shown. Check your internet connection, then press Refresh prices.",
                   icon=":material/wifi_off:")

    if len(my_portfolio.holdings) == 0:
        st.info("You haven't added any stocks yet. Use **Add a stock** below.")
    else:
        value = my_portfolio.total_value()
        cost = my_portfolio.total_cost()
        gain = my_portfolio.total_gain()
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Portfolio value", money(value), border=True)
        col2.metric("Total gain/loss", money(gain), border=True,
                    delta=f"{gain / cost * 100:+.1f}%" if cost > 0 else None)
        col3.metric("Change today", money(my_portfolio.day_change()), border=True)
        expected = my_portfolio.expected_return()
        col4.metric("Average yearly growth", f"{expected:.1f}%" if expected is not None else "Not available",
                    border=True,
                    help="Compound annual growth rate (CAGR) of your holdings over up to 5 years, weighted "
                         "by how much of each you own. Past growth doesn't guarantee future returns.")

        holdings_table = my_portfolio.to_table()
        st.dataframe(holdings_table, hide_index=True, width="stretch", column_config={
            "Shares": st.column_config.NumberColumn(format="%.2f"),
            "Avg cost": st.column_config.NumberColumn(format="dollar"),
            "Price": st.column_config.NumberColumn(format="dollar"),
            "Value": st.column_config.NumberColumn(format="dollar"),
            "Gain/Loss": st.column_config.NumberColumn(format="dollar"),
            "Gain/Loss %": st.column_config.NumberColumn(format="%.1f%%"),
            "Day change %": st.column_config.NumberColumn(format="%.2f%%"),
            "Weight %": st.column_config.NumberColumn(format="%.1f%%"),
        })

        left, right = st.columns(2, gap="large")
        with left:
            st.markdown("**How your portfolio is divided**")
            by_weight = holdings_table.sort_values("Weight %", ascending=False)
            show_chart(charts.allocation(by_weight["Ticker"], by_weight["Weight %"]))
        with right:
            st.markdown("**Price history**")
            col1, col2 = st.columns(2)
            ticker = col1.selectbox("Stock", my_portfolio.tickers(), key="stock_ticker")
            span = col2.selectbox("Time span", ["6 months", "1 year", "5 years"], index=1, key="stock_span")
            data = get_stock_data(ticker)
            if data is None:
                st.info("Price history needs an internet connection.")
            else:
                span_months = {"6 months": 6, "1 year": 12, "5 years": 60}
                prices = data["history"]
                cutoff = prices.index[-1] - pd.DateOffset(months=span_months[span])
                show_chart(charts.price_history(prices[prices.index >= cutoff],
                                                my_portfolio.find(ticker).avg_cost))

    with st.expander("Add a stock", icon=":material/add:", expanded=len(my_portfolio.holdings) == 0):
        with st.form("add_stock", clear_on_submit=True):
            col1, col2, col3, col4 = st.columns(4)
            symbol = col1.text_input("Ticker symbol", placeholder="e.g. AAPL")
            shares = col2.number_input("Shares", min_value=0.0, step=1.0, format="%.2f")
            price = col3.number_input("Price paid per share ($)", min_value=0.0, step=1.0, format="%.2f",
                                      help="Leave at 0 to use today's price.")
            bought = col4.date_input("Purchase date", value=today, max_value=today, format="MM/DD/YYYY")
            submitted = st.form_submit_button("Add stock", type="primary")
        if submitted:
            symbol = symbol.upper().strip()
            if symbol == "":
                st.error("Enter a ticker symbol, like AAPL.")
            elif shares <= 0:
                st.error("Shares must be more than 0.")
            else:
                data = get_stock_data(symbol)   # check that the ticker really exists
                if data is None:
                    st.error(f"Couldn't find '{symbol}'. Check the symbol (for example, AAPL for Apple) "
                             f"and your internet connection.")
                else:
                    if price <= 0:
                        price = data["price"]
                    ok, message = my_portfolio.add(symbol, shares, price, bought.isoformat())
                    if ok:
                        flash(message)
                        st.rerun()
                    else:
                        st.error(md(message))

    if len(my_portfolio.holdings) > 0:
        with st.expander("Edit or remove holdings", icon=":material/edit:"):
            st.caption("Change shares or average cost, or tick Delete to remove a holding. Then press Save.")
            rows = []
            for holding in my_portfolio.holdings:
                rows.append({"Delete": False, "Ticker": holding.ticker, "Shares": holding.shares,
                             "Avg cost": holding.avg_cost, "Purchase date": holding.purchase_date})
            edited = st.data_editor(
                pd.DataFrame(rows), key=f"holdings_{editor_version('holdings_version')}",
                hide_index=True, width="stretch", disabled=["Ticker"],
                column_config={
                    "Delete": st.column_config.CheckboxColumn("Delete?", width="small"),
                    "Shares": st.column_config.NumberColumn(min_value=0.0, format="%.2f"),
                    "Avg cost": st.column_config.NumberColumn("Avg cost ($)", min_value=0.01, format="%.2f"),
                    "Purchase date": st.column_config.TextColumn(help="YYYY-MM-DD"),
                },
            )
            if st.button("Save changes", key="save_holdings", type="primary"):
                kept = []
                for _, row in edited.iterrows():
                    if row["Delete"] or is_blank(row["Shares"]) or is_blank(row["Avg cost"]):
                        continue
                    kept.append({"ticker": row["Ticker"], "shares": row["Shares"],
                                 "avg_cost": row["Avg cost"], "purchase_date": row["Purchase date"]})
                my_portfolio.update_from_table(pd.DataFrame(kept, columns=["ticker", "shares",
                                                                           "avg_cost", "purchase_date"]))
                bump_version("holdings_version")
                flash("Holdings updated.")
                st.rerun()


# =====================================================================
# Tab 5: Loans & Property
# =====================================================================

def show_loans(loans, today):
    st.subheader("Loans")
    if len(loans) == 0:
        st.info("No loans added yet.")
    else:
        total_owed = 0.0
        total_payments = 0.0
        total_interest = 0.0
        for loan in loans:
            total_owed += loan.balance
            total_payments += loan.monthly_payment
            total_interest += loan.monthly_interest()
        col1, col2, col3 = st.columns(3)
        col1.metric("Total owed", money(total_owed), border=True)
        col2.metric("Monthly payments", money(total_payments), border=True)
        col3.metric("Interest this month", money(total_interest), border=True,
                    help="The part of this month's payments that goes to interest instead of "
                         "lowering what you owe.")

        st.dataframe(assets.loans_table(loans, today), hide_index=True, width="stretch", column_config={
            "Balance": st.column_config.NumberColumn(format="dollar"),
            "Rate %": st.column_config.NumberColumn(format="%.2f%%"),
            "Monthly payment": st.column_config.NumberColumn(format="dollar"),
            "Monthly interest": st.column_config.NumberColumn(format="dollar"),
            "Months left": st.column_config.NumberColumn(format="%d"),
            "Interest left": st.column_config.NumberColumn(format="dollar"),
        })

        st.markdown("**Payoff planner: see what an extra payment does**")
        left, right = st.columns([1, 2], gap="large")
        with left:
            names = []
            for loan in loans:
                names.append(loan.name)
            chosen = st.selectbox("Loan", names, key="planner_loan")
            loan = loans[names.index(chosen)]
            extra = st.slider("Extra payment per month ($)", 0, 1000, 100, step=25, key="planner_extra")
            months_now = loan.months_left()
            months_new = loan.months_left(extra)
            if months_new is None:
                st.error(md(f"Even with ${extra:,} extra, the payment doesn't cover the "
                            f"{money(loan.monthly_interest())} of interest charged each month."))
            elif months_now is None:
                st.warning("Your current payment doesn't cover the monthly interest, so this loan "
                           "would never be paid off.")
                st.metric("With the extra payment, paid off by",
                          loan.payoff_date(extra, today).strftime("%b %Y"))
            else:
                sooner = months_now - months_new
                st.metric("Paid off by", loan.payoff_date(extra, today).strftime("%b %Y"),
                          delta=f"{sooner} months sooner" if sooner > 0 else None)
                st.metric("Interest saved", money(loan.interest_left() - loan.interest_left(extra)))
        with right:
            if months_now is not None:
                show_chart(charts.loan_payoff(loan.schedule(), loan.schedule(extra), extra))
            elif months_new is not None:
                show_chart(charts.loan_payoff(loan.schedule(extra),
                                              current_label=f"With ${extra:,} extra a month"))
        with st.expander("Show the math"):
            st.latex(r"\text{Months left} = \frac{-\ln\left(1 - \frac{r \times B}{M}\right)}{\ln(1 + r)}")
            st.markdown("B = balance, M = monthly payment, r = yearly rate ÷ 12. "
                        "Each month, interest = balance × r; the rest of the payment lowers the balance.")

    with st.expander("Add a loan", icon=":material/add:", expanded=len(loans) == 0):
        with st.form("add_loan", clear_on_submit=True):
            col1, col2 = st.columns(2)
            name = col1.text_input("Name", placeholder="e.g. Car loan")
            kind = col2.selectbox("Type", assets.LOAN_TYPES)
            col1, col2, col3 = st.columns(3)
            balance = col1.number_input("Balance owed ($)", min_value=0.0, step=100.0, format="%.2f")
            rate = col2.number_input("Interest rate (% per year)", min_value=0.0, max_value=100.0,
                                     step=0.1, format="%.2f")
            payment = col3.number_input("Monthly payment ($)", min_value=0.0, step=10.0, format="%.2f")
            submitted = st.form_submit_button("Add loan", type="primary")
        if submitted:
            error = assets.check_loan(name, balance, rate, payment)
            if error is not None:
                st.error(md(error))
            else:
                loans.append(assets.Loan(name.strip(), kind, balance, rate, payment))
                assets.save_loans(loans)
                flash(f"Added {name.strip()}.")
                st.rerun()

    if len(loans) > 0:
        with st.expander("Edit or remove loans", icon=":material/edit:"):
            st.caption("Update balances as you pay them down. Tick Delete (or set the balance to 0) "
                       "to remove a loan. Then press Save.")
            rows = []
            for loan in loans:
                rows.append({"Delete": False, "Name": loan.name, "Type": loan.kind, "Balance": loan.balance,
                             "Rate %": loan.annual_rate, "Monthly payment": loan.monthly_payment})
            edited = st.data_editor(
                pd.DataFrame(rows), key=f"loans_{editor_version('loans_version')}",
                hide_index=True, width="stretch",
                column_config={
                    "Delete": st.column_config.CheckboxColumn("Delete?", width="small"),
                    "Type": st.column_config.SelectboxColumn(options=assets.LOAN_TYPES),
                    "Balance": st.column_config.NumberColumn(min_value=0.0, format="dollar"),
                    "Rate %": st.column_config.NumberColumn(min_value=0.0, max_value=100.0, format="%.2f"),
                    "Monthly payment": st.column_config.NumberColumn(min_value=0.0, format="dollar"),
                },
            )
            if st.button("Save changes", key="save_loans", type="primary"):
                new_loans = []
                for _, row in edited.iterrows():
                    if row["Delete"] or is_blank(row["Balance"]) or row["Balance"] <= 0:
                        continue
                    if is_blank(row["Rate %"]) or is_blank(row["Monthly payment"]):
                        continue
                    new_loans.append(assets.Loan(row["Name"], row["Type"], row["Balance"],
                                                 row["Rate %"], row["Monthly payment"]))
                assets.save_loans(new_loans)
                bump_version("loans_version")
                flash("Loans updated.")
                st.rerun()


def show_property(properties):
    st.subheader("Property")
    if len(properties) == 0:
        st.info("No property added yet.")
    else:
        total_now = 0.0
        total_later = 0.0
        for item in properties:
            total_now += item.value
            total_later += item.value_in(5)
        col1, col2, _ = st.columns(3)
        col1.metric("Total value", money(total_now), border=True)
        col2.metric("Estimated value in 5 years", money(total_later), border=True,
                    delta=money(total_later - total_now))
        st.dataframe(assets.properties_table(properties), hide_index=True, width="stretch", column_config={
            "Value": st.column_config.NumberColumn(format="dollar"),
            "Yearly change %": st.column_config.NumberColumn(format="%.1f%%"),
            "Value in 5 years": st.column_config.NumberColumn(format="dollar"),
        })
        st.caption("Estimated value = value × (1 + yearly change)^years")

    with st.expander("Add property", icon=":material/add:", expanded=len(properties) == 0):
        with st.form("add_property", clear_on_submit=True):
            col1, col2 = st.columns(2)
            name = col1.text_input("Name", placeholder="e.g. My condo")
            kind = col2.selectbox("Type", assets.PROPERTY_TYPES)
            col1, col2 = st.columns(2)
            value = col1.number_input("Current value ($)", min_value=0.0, step=1000.0, format="%.2f")
            growth = col2.number_input("Yearly change in value (%)", min_value=-50.0, max_value=50.0,
                                       value=3.0, step=0.5, format="%.1f",
                                       help="Homes often gain a few percent a year; cars usually "
                                            "lose 10-20% a year (use a negative number).")
            submitted = st.form_submit_button("Add property", type="primary")
        if submitted:
            error = assets.check_property(name, value)
            if error is not None:
                st.error(md(error))
            else:
                properties.append(assets.Property(name.strip(), kind, value, growth))
                assets.save_properties(properties)
                flash(f"Added {name.strip()}.")
                st.rerun()

    if len(properties) > 0:
        with st.expander("Edit or remove property", icon=":material/edit:"):
            rows = []
            for item in properties:
                rows.append({"Delete": False, "Name": item.name, "Type": item.kind,
                             "Value": item.value, "Yearly change %": item.annual_growth})
            edited = st.data_editor(
                pd.DataFrame(rows), key=f"property_{editor_version('property_version')}",
                hide_index=True, width="stretch",
                column_config={
                    "Delete": st.column_config.CheckboxColumn("Delete?", width="small"),
                    "Type": st.column_config.SelectboxColumn(options=assets.PROPERTY_TYPES),
                    "Value": st.column_config.NumberColumn(min_value=0.0, format="dollar"),
                    "Yearly change %": st.column_config.NumberColumn(min_value=-50.0, max_value=50.0,
                                                                     format="%.1f"),
                },
            )
            if st.button("Save changes", key="save_property", type="primary"):
                new_properties = []
                for _, row in edited.iterrows():
                    if row["Delete"] or is_blank(row["Value"]) or row["Value"] <= 0:
                        continue
                    growth = 0.0 if is_blank(row["Yearly change %"]) else row["Yearly change %"]
                    new_properties.append(assets.Property(row["Name"], row["Type"], row["Value"], growth))
                assets.save_properties(new_properties)
                bump_version("property_version")
                flash("Property updated.")
                st.rerun()


# =====================================================================
# Tab 6: Projections
# =====================================================================

def show_projections(my_budget, my_portfolio, today):
    st.subheader("Grow your money")
    st.caption("See how savings and investments could grow with compound interest.")
    inputs, results = st.columns([1, 2], gap="large")
    with inputs:
        start_amount = st.number_input("Starting amount ($)", min_value=0.0, step=500.0, format="%.0f",
                                       value=float(round(my_portfolio.total_value(), -2)), key="grow_start",
                                       help="Starts with your current portfolio value.")
        monthly = st.number_input("Add each month ($)", min_value=0.0, step=50.0, format="%.0f",
                                  value=suggested_monthly_savings(my_budget, today), key="grow_monthly",
                                  help="Starts with what you saved per month, on average, over the last 90 days.")
        years = st.slider("Years", 1, 40, 10, key="grow_years")
        expected = my_portfolio.expected_return()
        options = ["Standard estimate (7%)"]
        if expected is not None:
            options.append(f"My stocks' past growth ({expected:.1f}%)")
        options.append("Choose my own")
        choice = st.radio("Yearly return", options, key="grow_choice",
                          help="7% is a common planning assumption for a diversified stock portfolio. "
                               "Real returns go up and down from year to year.")
        if choice.startswith("Standard"):
            rate = 7.0
        elif choice.startswith("My stocks"):
            rate = round(expected, 1)
        else:
            rate = st.slider("Your yearly return (%)", 0.0, 15.0, 7.0, step=0.5, key="grow_rate")
        if rate > 12:
            st.caption("Heads up: growth this high rarely lasts for decades. Try a lower rate too.")
        inflation = st.slider("Inflation (% per year)", 0.0, 6.0, 3.0, step=0.5, key="grow_inflation",
                              help="Used to show what the future amount would buy in today's dollars.")

    low_rate = max(rate - 3, 0.0)
    high_rate = rate + 3
    rows = projections.growth_by_year(start_amount, monthly, rate, years)
    low_rows = projections.growth_by_year(start_amount, monthly, low_rate, years)
    high_rows = projections.growth_by_year(start_amount, monthly, high_rate, years)
    final = rows[-1]

    with results:
        col1, col2, col3 = st.columns(3)
        col1.metric(f"In {years} years", money(final["balance"]), border=True)
        col2.metric("Money you put in", money(final["contributed"]), border=True)
        col3.metric("Growth earned", money(final["growth"]), border=True)
        show_chart(charts.projection(rows, low_rows, high_rows, rate, low_rate, high_rate))
        today_dollars = projections.real_value(final["balance"], inflation, years)
        notes = f"After {inflation:g}% yearly inflation, that's about **{money(today_dollars)} in today's dollars**."
        doubling = projections.years_to_double(rate)
        if doubling is not None:
            notes += f" At {rate:g}% a year, money doubles about every {doubling:.1f} years (Rule of 72)."
        st.markdown(md(notes))

    with st.expander("Show the math"):
        st.latex(r"FV = PV(1+r)^n + PMT \times \frac{(1+r)^n - 1}{r}")
        st.markdown(md(f"- **PV** (starting amount) = {money(start_amount)}\n"
                       f"- **PMT** (added each month) = {money(monthly)}\n"
                       f"- **r** (monthly rate) = {rate:g}% ÷ 12 = {rate / 12:.3f}%\n"
                       f"- **n** (months) = {years} × 12 = {years * 12}"))
        st.latex(r"\text{Today's dollars} = \frac{FV}{(1 + \text{inflation})^{\text{years}}}")
    with st.expander("Year-by-year table"):
        st.dataframe(
            pd.DataFrame(rows).rename(columns={"year": "Year", "balance": "Balance",
                                               "contributed": "Money put in", "growth": "Growth"}),
            hide_index=True, width="stretch",
            column_config={
                "Balance": st.column_config.NumberColumn(format="dollar"),
                "Money put in": st.column_config.NumberColumn(format="dollar"),
                "Growth": st.column_config.NumberColumn(format="dollar"),
            },
        )

    st.divider()
    st.subheader("Savings goal planner")
    average_spending = my_budget.average_monthly_spending(today)
    default_goal = float(round(average_spending * 6 / 500) * 500)   # 6 months of spending
    if default_goal < 500:
        default_goal = 10000.0
    inputs, results = st.columns([1, 2], gap="large")
    with inputs:
        goal_name = st.text_input("What are you saving for?", value="Emergency fund", key="goal_name")
        goal = st.number_input("Goal amount ($)", min_value=1.0, value=default_goal, step=500.0,
                               format="%.0f", key="goal_amount",
                               help="Starts at 6 months of your average spending - a common emergency fund size.")
        saved = st.number_input("Already saved ($)", min_value=0.0, step=100.0, format="%.0f",
                                value=float(max(round(my_budget.cash_on_hand(), -2), 0)), key="goal_saved")
        monthly_saving = st.number_input("Save each month ($)", min_value=0.0, step=50.0, format="%.0f",
                                         value=suggested_monthly_savings(my_budget, today), key="goal_monthly")
        goal_rate = st.number_input("Interest earned (% per year)", min_value=0.0, max_value=15.0, value=4.0,
                                    step=0.25, format="%.2f", key="goal_rate",
                                    help="Use your savings account's rate, or 0 if it doesn't earn interest.")
        deadline = st.date_input("Target date", value=assets.add_months(today, 24),
                                 min_value=today + timedelta(days=31), format="MM/DD/YYYY",
                                 key="goal_deadline")
    with results:
        if goal_name.strip() != "":
            label = f"your {goal_name.strip().lower()} goal"
        else:
            label = "your goal"
        st.progress(min(saved / goal, 1.0), text=md(f"{min(saved / goal, 1.0):.0%} of the way to {money(goal)}"))
        months = projections.months_to_goal(saved, goal, monthly_saving, goal_rate)
        months_until_deadline = (deadline.year - today.year) * 12 + (deadline.month - today.month)
        needed = projections.monthly_savings_needed(saved, goal, goal_rate, months_until_deadline)
        col1, col2 = st.columns(2)
        with col1:
            if months == 0:
                st.metric("Time to reach it", "Done!", border=True)
                st.caption(f"You've already saved enough for {label}.")
            elif months is None:
                st.metric("Time to reach it", "Not reachable", border=True)
                st.caption("Add a monthly amount to reach this goal.")
            else:
                st.metric("Time to reach it", f"{months} months", border=True)
                st.caption(md(f"Saving {money(monthly_saving)} a month, you'd reach {label} around "
                              f"{assets.add_months(today, months):%B %Y}."))
        with col2:
            if months_until_deadline <= 0 or needed is None:
                st.metric("Needed per month", "-", border=True)
            else:
                st.metric(f"To finish by {deadline:%b %Y}", f"{money(needed)}/month", border=True)
                if needed > monthly_saving:
                    st.caption(md(f"That's {money(needed - monthly_saving)} more a month than you're saving now."))
                else:
                    st.caption("You're saving enough to make it on time.")
        with st.expander("Show the math"):
            st.markdown("Months to reach the goal (the future value formula solved for n):")
            st.latex(r"n = \frac{\ln\left(\frac{FV \times r + PMT}{PV \times r + PMT}\right)}{\ln(1 + r)}")
            st.markdown("Monthly saving needed to finish by the target date (solved for PMT):")
            st.latex(r"PMT = \frac{(FV - PV(1+r)^n) \times r}{(1+r)^n - 1}")

    st.divider()
    st.subheader("How your stocks have grown")
    growth_rows = []
    for holding in my_portfolio.holdings:
        data = get_stock_data(holding.ticker)
        if data is not None:
            growth_rows.append({
                "Ticker": holding.ticker,
                "Years of data": data["years"],
                "Price then": float(data["history"].iloc[0]),
                "Price now": data["price"],
                "Average yearly growth (CAGR)": data["cagr"],
            })
    if len(growth_rows) == 0:
        st.info("Add stocks (and connect to the internet) to see their past growth.")
    else:
        st.dataframe(pd.DataFrame(growth_rows), hide_index=True, width="stretch", column_config={
            "Years of data": st.column_config.NumberColumn(format="%.1f"),
            "Price then": st.column_config.NumberColumn(format="dollar"),
            "Price now": st.column_config.NumberColumn(format="dollar"),
            "Average yearly growth (CAGR)": st.column_config.NumberColumn(format="%.1f%%"),
        })
        st.latex(r"CAGR = \left(\frac{\text{price now}}{\text{price then}}\right)^{1/\text{years}} - 1")
        st.caption("Prices are adjusted for stock splits and dividends. Past growth doesn't guarantee future returns.")


# =====================================================================
# Tab 7: Settings
# =====================================================================

def show_settings(my_budget):
    left, right = st.columns([1.3, 1], gap="large")
    with left:
        st.subheader("Monthly budget")
        st.caption("How much you plan to spend in each category per month. Housing, Utilities and "
                   "Debt Payments are fixed bills; the rest is flexible, everyday spending.")
        rows = []
        for category in budget.EXPENSE_CATEGORIES:
            if category in budget.FIXED_CATEGORIES:
                kind = "Fixed"
            else:
                kind = "Flexible"
            rows.append({"Category": category, "Kind": kind,
                         "Monthly budget": my_budget.limits.get(category, 0.0)})
        edited = st.data_editor(
            pd.DataFrame(rows), key=f"budget_{editor_version('budget_version')}",
            hide_index=True, width="stretch", height="content", disabled=["Category", "Kind"],
            column_config={"Monthly budget": st.column_config.NumberColumn(min_value=0.0, step=10.0,
                                                                           format="dollar")},
        )
        st.caption(md(f"Total monthly budget: {money(edited['Monthly budget'].fillna(0).sum())}"))
        if st.button("Save budget", type="primary", icon=":material/save:"):
            limits = {}
            for _, row in edited.iterrows():
                limits[row["Category"]] = 0.0 if is_blank(row["Monthly budget"]) else float(row["Monthly budget"])
            my_budget.set_limits(limits)
            bump_version("budget_version")
            flash("Budget saved.")
            st.rerun()

    with right:
        st.subheader("Starting cash")
        st.caption("The cash (checking + savings) you had when you started tracking. "
                   "Cash on hand = starting cash + income - expenses.")
        with st.form("starting_cash_form"):
            cash = st.number_input("Starting cash ($)", value=float(my_budget.starting_cash),
                                   step=100.0, format="%.2f")
            if st.form_submit_button("Save starting cash"):
                my_budget.set_starting_cash(cash)
                flash("Starting cash saved.")
                st.rerun()

        st.subheader("Your data")
        st.caption(f"Everything is saved automatically as CSV files in: `{storage.DATA_FOLDER}`")
        confirm = st.checkbox("I understand this replaces all my current data",
                              key=f"confirm_{editor_version('reset_version')}")
        col1, col2 = st.columns(2)
        if col1.button("Load sample data", disabled=not confirm, width="stretch"):
            sample_data.create_sample_data()
            get_stock_data.clear()
            bump_version("reset_version")
            flash("Sample data loaded.")
            st.rerun()
        if col2.button("Erase everything", disabled=not confirm, width="stretch"):
            storage.delete_all_data()
            get_stock_data.clear()
            bump_version("reset_version")
            flash("All data erased.")
            st.rerun()


# =====================================================================
# Main program
# =====================================================================

def main():
    show_flash()
    if not storage.data_exists():
        show_welcome()
        return

    today = date.today()

    # Load everything from the data folder.
    my_budget = budget.Budget()
    my_portfolio = portfolio.Portfolio()
    loans = assets.load_loans()
    properties = assets.load_properties()

    # Get live stock prices (cached for 15 minutes).
    price_data = {}
    for ticker in my_portfolio.tickers():
        price_data[ticker] = get_stock_data(ticker)
    offline_tickers = my_portfolio.update_prices(price_data)

    worth = assets.net_worth(my_budget.cash_on_hand(), my_portfolio.total_value(), properties, loans)

    show_sidebar(my_budget, today)
    st.title("Stock & Budget Tracker")
    st.caption(f"{today:%A, %B} {today.day}, {today.year}")

    tabs = st.tabs(["Overview", "Daily Log", "Spending Summary", "Investments",
                    "Loans & Property", "Projections", "Settings"])
    with tabs[0]:
        show_overview(my_budget, my_portfolio, loans, worth, today)
    with tabs[1]:
        show_daily_log(my_budget, today)
    with tabs[2]:
        show_summary(my_budget, today)
    with tabs[3]:
        show_investments(my_portfolio, offline_tickers, today)
    with tabs[4]:
        show_loans(loans, today)
        st.divider()
        show_property(properties)
    with tabs[5]:
        show_projections(my_budget, my_portfolio, today)
    with tabs[6]:
        show_settings(my_budget)


if __name__ == "__main__":
    main()
