"""
charts.py - Every chart in the app, drawn with matplotlib.

Each function takes data and returns a matplotlib Figure; app.py displays it
with st.pyplot(). Keeping the drawing code here keeps app.py easy to read.

Style rules used throughout:
    - one main color (blue); red only for money owed; gray for "context" lines
    - thin lines, light solid gridlines, no chart borders
    - text is always black/gray, never colored, so it stays readable
"""

import matplotlib

matplotlib.use("Agg")  # draw charts as images instead of opening windows

import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import pandas as pd
from matplotlib.ticker import FixedLocator, FuncFormatter

# ---------- Colors ----------
SURFACE = "#fcfcfb"    # chart background (same as the app background)
BLUE = "#2a78d6"       # main data color
RED = "#e34948"        # money owed
GRAY = "#898781"       # secondary lines and axis labels
TEXT = "#0b0b0b"       # main text
TEXT_2 = "#52514e"     # secondary text
GRID = "#e1e0d9"       # gridlines
BASELINE = "#c3c2b7"   # the line bars grow from

plt.rcParams.update({
    "font.family": "sans-serif",
    "font.sans-serif": ["Helvetica Neue", "Helvetica", "Arial", "DejaVu Sans"],
    "font.size": 10,
})


# ---------- Helpers ----------

def money_label(value, compact=False):
    """Format dollars for a chart: 1500 -> "$1,500", or compact: 25000 -> "$25K"."""
    sign = "-" if value < 0 else ""
    value = abs(value)
    if compact and value >= 1_000_000:
        text = f"{value / 1_000_000:.1f}M"
    elif compact and value >= 1_000:
        text = f"{value / 1_000:.0f}K"
    else:
        text = f"{value:,.0f}"
    return f"{sign}${text}"


def format_money_axis(axis, largest):
    """Put dollar labels on an axis. Axes that reach $10,000 use the compact style."""
    use_compact = largest >= 10_000

    def label(value, position):
        return money_label(value, compact=use_compact)

    axis.set_major_formatter(FuncFormatter(label))


def format_date_axis(axis, first_date, last_date):
    """About five date labels along the bottom, all inside the range of the data."""
    span_days = (last_date - first_date).days
    if span_days <= 7:
        ticks = pd.date_range(first_date, last_date, freq="D")
    else:
        ticks = pd.date_range(first_date, last_date, periods=5)
    axis.set_major_locator(FixedLocator(mdates.date2num(ticks.to_pydatetime())))
    if span_days > 400:
        axis.set_major_formatter(mdates.DateFormatter("%b %Y"))
    else:
        axis.set_major_formatter(mdates.DateFormatter("%b %d"))


def new_chart(height=3.0, width=5.5):
    """Create an empty, styled figure and axes."""
    fig, ax = plt.subplots(figsize=(width, height), dpi=150, layout="constrained")
    fig.patch.set_facecolor(SURFACE)
    ax.set_facecolor(SURFACE)
    for side in ["top", "right", "left"]:
        ax.spines[side].set_visible(False)
    ax.spines["bottom"].set_color(BASELINE)
    ax.tick_params(colors=GRAY, labelsize=9, length=0)
    ax.tick_params(axis="x", pad=6)   # a little space between the axis and the date labels
    return fig, ax


def add_gridlines(ax, axis="y"):
    """Light, solid gridlines drawn behind the data."""
    ax.grid(axis=axis, color=GRID, linewidth=0.8, linestyle="-")
    ax.set_axisbelow(True)


def add_note(ax, text):
    """A small gray note above the top-left corner of the chart (used to explain a reference line)."""
    ax.set_title(text, loc="left", fontsize=9, color=TEXT_2)


def end_label(ax, x, y, text, color):
    """A dot at the last point of a line, with its value printed to the right."""
    ax.plot([x], [y], marker="o", markersize=7, color=color,
            markeredgecolor=SURFACE, markeredgewidth=2)
    ax.annotate(text, (x, y), xytext=(8, 0), textcoords="offset points",
                va="center", fontsize=9, color=TEXT)


# ---------- Bar charts ----------

def ranked_bars(labels, values, value_format="money"):
    """Horizontal bars, largest at the top, with each value printed at the bar's end."""
    labels = list(labels)[::-1]   # matplotlib draws the first bar at the bottom,
    values = list(values)[::-1]   # so reverse the lists to put the largest on top
    fig, ax = new_chart(height=max(0.36 * len(labels) + 0.4, 1.3))
    positions = list(range(len(labels)))
    ax.barh(positions, values, height=0.6, color=BLUE)
    ax.set_yticks(positions)
    ax.set_yticklabels(labels)
    ax.tick_params(axis="y", labelcolor=TEXT_2, labelsize=10)

    largest = max(values) if len(values) > 0 else 0
    for position, value in enumerate(values):
        if value_format == "percent":
            text = f"{value:.1f}%"
        else:
            text = money_label(value)
        ax.text(value + largest * 0.01, position, " " + text, va="center", fontsize=9, color=TEXT)

    ax.set_xlim(0, largest * 1.2 if largest > 0 else 1)
    ax.xaxis.set_visible(False)            # every bar is labeled, so no x-axis needed
    ax.spines["bottom"].set_visible(False)
    ax.spines["left"].set_visible(True)    # the baseline the bars grow from
    ax.spines["left"].set_color(BASELINE)
    return fig


def spending_by_category(totals):
    """Spending per category (a pandas Series, largest first)."""
    return ranked_bars(totals.index, totals.values)


def allocation(tickers, weights):
    """What percent of the portfolio each holding makes up."""
    return ranked_bars(tickers, weights, value_format="percent")


def net_worth_breakdown(worth):
    """What you own (blue bars, to the right) vs. what you owe (red bar, to the left)."""
    labels = ["Cash", "Investments", "Property", "Loans & debt"]
    values = [worth["cash"], worth["investments"], worth["property"], -worth["debt"]]
    colors = [BLUE, BLUE, BLUE, RED]
    positions = [3, 2, 1, 0]   # top to bottom

    fig, ax = new_chart(height=2.2)
    ax.barh(positions, values, height=0.6, color=colors)
    ax.axvline(0, color=BASELINE, linewidth=1)
    ax.set_yticks(positions)
    ax.set_yticklabels(labels)
    ax.tick_params(axis="y", labelcolor=TEXT_2, labelsize=10)

    largest = max(abs(min(values)), max(values), 1)
    for position, value in zip(positions, values):
        if value >= 0:
            ax.text(value + largest * 0.01, position, " " + money_label(value),
                    va="center", ha="left", fontsize=9, color=TEXT)
        elif -value >= largest * 0.3:
            # Long red bar: print the amount inside it, in white.
            ax.text(value + largest * 0.02, position, money_label(value),
                    va="center", ha="left", fontsize=9, color="white")
        else:
            ax.text(value - largest * 0.01, position, money_label(value) + " ",
                    va="center", ha="right", fontsize=9, color=TEXT)

    ax.set_xlim(min(min(values), 0) - largest * 0.3, max(max(values), 0) + largest * 0.3)
    ax.xaxis.set_visible(False)
    ax.spines["bottom"].set_visible(False)
    return fig


def spending_over_time(series, reference=None, note="", last_day=None):
    """Columns of spending per day (or per week).
    reference - draws a gray line at that amount (e.g. the planned daily pace)
    last_day  - stretch the axis to this date (e.g. the end of the month) so the
                days still to come show as empty space"""
    fig, ax = new_chart(height=2.9)
    if len(series) > 1:
        step_days = (series.index[1] - series.index[0]).days   # 1 for daily, 7 for weekly
    else:
        step_days = 1
    ax.bar(series.index, series.values, width=0.7 * step_days, color=BLUE)
    add_gridlines(ax, "y")

    end = series.index[-1]
    if last_day is not None and pd.Timestamp(last_day) > end:
        end = pd.Timestamp(last_day)
    half_bar = pd.Timedelta(days=0.5 * step_days)
    ax.set_xlim(series.index[0] - half_bar, end + half_bar)
    format_date_axis(ax.xaxis, series.index[0], end)

    top = series.max() if len(series) > 0 else 0
    if reference is not None and reference > 0:
        ax.axhline(reference, color=TEXT_2, linewidth=1)
        add_note(ax, note)
        top = max(top, reference)
    ax.set_ylim(0, top * 1.15 if top > 0 else 1)
    format_money_axis(ax.yaxis, top)
    return fig


# ---------- Line charts ----------

def balance_over_time(series):
    """A single balance (like cash on hand) over time, with a light fill below it."""
    fig, ax = new_chart(height=2.9)
    ax.plot(series.index, series.values, color=BLUE, linewidth=2,
            solid_capstyle="round", solid_joinstyle="round")
    ax.fill_between(series.index, series.values, 0, color=BLUE, alpha=0.10, linewidth=0)
    add_gridlines(ax, "y")
    end_label(ax, series.index[-1], series.iloc[-1], money_label(series.iloc[-1]), BLUE)

    # Leave room on the right for the end label.
    extra_days = max(len(series) * 0.15, 2)
    ax.set_xlim(series.index[0], series.index[-1] + pd.Timedelta(days=extra_days))
    format_date_axis(ax.xaxis, series.index[0], series.index[-1])
    top = max(series.max(), 0)
    ax.set_ylim(min(series.min(), 0), top * 1.15 if top > 0 else 1)
    format_money_axis(ax.yaxis, top)
    return fig


def price_history(prices, avg_cost):
    """A stock's price over time, with a gray line at the average price you paid."""
    fig, ax = new_chart(height=2.9)
    ax.plot(prices.index, prices.values, color=BLUE, linewidth=2,
            solid_capstyle="round", solid_joinstyle="round")
    add_gridlines(ax, "y")
    end_label(ax, prices.index[-1], prices.iloc[-1], f"${prices.iloc[-1]:,.2f}", BLUE)

    ax.axhline(avg_cost, color=TEXT_2, linewidth=1)
    add_note(ax, f"Gray line = your average cost (${avg_cost:,.2f})")

    extra_days = max((prices.index[-1] - prices.index[0]).days * 0.15, 2)
    ax.set_xlim(prices.index[0], prices.index[-1] + pd.Timedelta(days=extra_days))
    format_date_axis(ax.xaxis, prices.index[0], prices.index[-1])
    low = min(prices.min(), avg_cost)
    high = max(prices.max(), avg_cost)
    padding = (high - low) * 0.12 if high > low else high * 0.1
    ax.set_ylim(max(low - padding, 0), high + padding)
    format_money_axis(ax.yaxis, high)
    return fig


def projection(expected_rows, low_rows, high_rows, rate, low_rate, high_rate):
    """Projected growth: the expected path, a shaded range of outcomes,
    and a gray line for the money you put in yourself."""
    years = []
    expected = []
    low = []
    high = []
    contributed = []
    for i in range(len(expected_rows)):
        years.append(expected_rows[i]["year"])
        expected.append(expected_rows[i]["balance"])
        low.append(low_rows[i]["balance"])
        high.append(high_rows[i]["balance"])
        contributed.append(expected_rows[i]["contributed"])

    fig, ax = new_chart(height=3.4, width=7.0)
    ax.fill_between(years, low, high, color=BLUE, alpha=0.10, linewidth=0,
                    label=f"Range if returns are {low_rate:g}%-{high_rate:g}%")
    ax.plot(years, contributed, color=GRAY, linewidth=2, label="Money you put in")
    end_label(ax, years[-1], contributed[-1], money_label(contributed[-1], compact=True), GRAY)
    ax.plot(years, expected, color=BLUE, linewidth=2, label=f"Expected at {rate:g}% a year")
    end_label(ax, years[-1], expected[-1], money_label(expected[-1], compact=True), BLUE)

    add_gridlines(ax, "y")
    ax.set_xlim(0, years[-1] * 1.12 + 0.5)
    ax.set_ylim(0, max(high) * 1.08 if max(high) > 0 else 1)
    format_money_axis(ax.yaxis, max(high))
    ax.set_xlabel("Years from now", color=GRAY, fontsize=9)
    ax.legend(loc="upper left", frameon=False, fontsize=9, labelcolor=TEXT_2)
    return fig


def loan_payoff(current_schedule, extra_schedule=None, extra_amount=0, current_label="Current payment"):
    """Loan balance over time. With an extra payment, the current plan is drawn
    in gray and the faster plan in blue."""
    fig, ax = new_chart(height=3.0, width=7.0)
    starting_balance = current_schedule[0]["balance"] + current_schedule[0]["principal"]

    plans = []
    if extra_schedule is not None and extra_amount > 0:
        plans.append((current_schedule, GRAY, current_label))
        plans.append((extra_schedule, BLUE, f"With ${extra_amount:,.0f} extra a month"))
    else:
        plans.append((current_schedule, BLUE, current_label))

    for schedule, color, label in plans:
        years = [0.0]
        balances = [starting_balance]
        for row in schedule:
            years.append(row["month"] / 12)
            balances.append(row["balance"])
        # The payoff time goes in the legend, so the two labels can never overlap.
        ax.plot(years, balances, color=color, linewidth=2, label=f"{label}: paid off in {years[-1]:.1f} years",
                solid_capstyle="round", solid_joinstyle="round")
        ax.plot([years[-1]], [0], marker="o", markersize=7, color=color,
                markeredgecolor=SURFACE, markeredgewidth=2)

    add_gridlines(ax, "y")
    longest = len(current_schedule) / 12
    ax.set_xlim(0, longest * 1.15 + 0.2)
    ax.set_ylim(0, starting_balance * 1.1)
    format_money_axis(ax.yaxis, starting_balance)
    ax.set_xlabel("Years from now", color=GRAY, fontsize=9)
    ax.legend(loc="upper right", frameon=False, fontsize=9, labelcolor=TEXT_2)
    return fig
