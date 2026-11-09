"""
portfolio.py - Stock investments, with live prices from the yfinance library.

Functions:
    fetch_price_history - download past prices from Yahoo Finance using yfinance
    price_summary       - latest price, previous close and growth rate (CAGR)
    lookup              - both of the above in one call
Classes:
    Holding   - shares of one stock or fund that you own
    Portfolio - all of your holdings
"""

import logging

import pandas as pd
import yfinance as yf

import projections
import storage

# yfinance prints its own error messages (for example when you're offline).
# The app handles those cases itself, so we hide yfinance's messages.
logging.getLogger("yfinance").setLevel(logging.CRITICAL)


def fetch_price_history(ticker, period="5y"):
    """Download daily closing prices for one ticker using yfinance.

    Returns a pandas Series (date -> closing price), or None if the ticker
    doesn't exist or there's no internet connection.
    """
    try:
        history = yf.Ticker(ticker).history(period=period)
    except Exception:
        # Network problems (offline, blocked, too many requests) end up here.
        return None
    if history is None or history.empty or "Close" not in history.columns:
        return None  # yfinance returns an empty table for tickers that don't exist
    prices = history["Close"].dropna()
    if prices.empty:
        return None
    if getattr(prices.index, "tz", None) is not None:
        prices.index = prices.index.tz_localize(None)  # drop the time zone so dates are simple
    return prices


def price_summary(prices):
    """Summarize a price history (a pandas Series) as a dictionary with:
        price          - the latest price
        previous_close - the price one trading day earlier (for the daily change)
        cagr           - compound annual growth rate over the whole history, in percent
        years          - how many years of history there are
    """
    latest = float(prices.iloc[-1])
    if len(prices) > 1:
        previous = float(prices.iloc[-2])
    else:
        previous = latest
    years = (prices.index[-1] - prices.index[0]).days / 365.25
    growth = None
    if years >= 1:  # less than a year of history is too short to judge growth
        growth = projections.cagr(float(prices.iloc[0]), latest, years)
    return {"price": latest, "previous_close": previous, "cagr": growth, "years": years}


def lookup(ticker, period="5y"):
    """Download and summarize one ticker. Returns None if it can't be found."""
    prices = fetch_price_history(ticker, period)
    if prices is None:
        return None
    summary = price_summary(prices)
    summary["history"] = prices
    return summary


class Holding:
    """Shares of one stock or fund."""

    def __init__(self, ticker, shares, avg_cost, purchase_date="", last_price=None):
        self.ticker = str(ticker).upper().strip()
        self.shares = float(shares)
        self.avg_cost = float(avg_cost)          # average price paid per share
        if purchase_date is None or pd.isna(purchase_date):
            purchase_date = ""
        self.purchase_date = str(purchase_date)
        # The latest price we know. Until a live price arrives, use the last saved one.
        if last_price is None or pd.isna(last_price):
            last_price = avg_cost
        self.price = float(last_price)
        self.previous_close = self.price
        self.cagr = None        # filled in when live data arrives
        self.is_live = False    # True once a live price came from yfinance

    def cost_basis(self):
        """Total amount paid: shares * average cost."""
        return self.shares * self.avg_cost

    def market_value(self):
        """What the shares are worth now: shares * current price."""
        return self.shares * self.price

    def gain(self):
        """Profit or loss in dollars."""
        return self.market_value() - self.cost_basis()

    def gain_percent(self):
        """Profit or loss as a percent of what you paid."""
        if self.cost_basis() == 0:
            return 0.0
        return self.gain() / self.cost_basis() * 100

    def day_change_percent(self):
        """Change since the previous trading day, in percent."""
        if self.previous_close == 0:
            return 0.0
        return (self.price - self.previous_close) / self.previous_close * 100

    def buy_more(self, shares, price):
        """Add shares. The new average cost is a weighted average:
            new average = (old shares * old average + new shares * new price) / total shares
        """
        total_cost = self.cost_basis() + shares * price
        self.shares += shares
        self.avg_cost = total_cost / self.shares

    def __str__(self):
        return f"{self.shares:g} shares of {self.ticker} at ${self.avg_cost:,.2f}"


class Portfolio:
    """All of your stock holdings."""

    def __init__(self):
        self.holdings = []   # a list of Holding objects
        for _, row in storage.load_table("holdings").iterrows():
            self.holdings.append(Holding(row["ticker"], row["shares"], row["avg_cost"],
                                         row["purchase_date"], row["last_price"]))

    def save(self):
        rows = []
        for holding in self.holdings:
            rows.append({
                "ticker": holding.ticker,
                "shares": holding.shares,
                "avg_cost": round(holding.avg_cost, 4),
                "purchase_date": holding.purchase_date,
                "last_price": round(holding.price, 4),
            })
        storage.save_table("holdings", pd.DataFrame(rows, columns=storage.TABLE_COLUMNS["holdings"]))

    def tickers(self):
        """List of the ticker symbols you own."""
        symbols = []
        for holding in self.holdings:
            symbols.append(holding.ticker)
        return symbols

    def find(self, ticker):
        """The Holding for a ticker, or None if you don't own it."""
        ticker = ticker.upper().strip()
        for holding in self.holdings:
            if holding.ticker == ticker:
                return holding
        return None

    def add(self, ticker, shares, price, purchase_date=""):
        """Record a purchase. Buying a stock you already own combines the two
        into one holding with a new average cost. Returns (success, message)."""
        ticker = ticker.upper().strip()
        if ticker == "":
            return False, "Enter a ticker symbol, like AAPL."
        if shares <= 0:
            return False, "Shares must be more than 0."
        if price <= 0:
            return False, "The price per share must be more than $0."
        existing = self.find(ticker)
        if existing is not None:
            existing.buy_more(shares, price)
            message = (f"Added {shares:g} more shares of {ticker}. "
                       f"Your new average cost is ${existing.avg_cost:,.2f}.")
        else:
            self.holdings.append(Holding(ticker, shares, price, str(purchase_date), price))
            message = f"Added {shares:g} shares of {ticker}."
        self.save()
        return True, message

    def update_from_table(self, table):
        """Replace the holdings with an edited table (columns: ticker, shares,
        avg_cost, purchase_date). Prices already known are kept."""
        new_holdings = []
        for _, row in table.iterrows():
            if row["shares"] <= 0:
                continue  # 0 shares means you sold everything
            old = self.find(row["ticker"])
            holding = Holding(row["ticker"], row["shares"], row["avg_cost"], row["purchase_date"])
            if old is not None:
                holding.price = old.price
                holding.previous_close = old.previous_close
                holding.cagr = old.cagr
                holding.is_live = old.is_live
            new_holdings.append(holding)
        self.holdings = new_holdings
        self.save()

    def update_prices(self, price_data):
        """Apply live data. `price_data` is a dictionary {ticker: summary or None}.
        Returns a list of the tickers that couldn't be updated."""
        missing = []
        changed = False
        for holding in self.holdings:
            info = price_data.get(holding.ticker)
            if info is None:
                missing.append(holding.ticker)
                continue
            if round(info["price"], 4) != round(holding.price, 4):
                changed = True
            holding.price = info["price"]
            holding.previous_close = info["previous_close"]
            holding.cagr = info["cagr"]
            holding.is_live = True
        if changed:
            self.save()  # remember the latest prices in case you're offline next time
        return missing

    # ---------- Totals ----------

    def total_value(self):
        total = 0.0
        for holding in self.holdings:
            total += holding.market_value()
        return total

    def total_cost(self):
        total = 0.0
        for holding in self.holdings:
            total += holding.cost_basis()
        return total

    def total_gain(self):
        return self.total_value() - self.total_cost()

    def day_change(self):
        """Dollar change in the portfolio's value since the previous trading day."""
        change = 0.0
        for holding in self.holdings:
            change += holding.shares * (holding.price - holding.previous_close)
        return change

    def expected_return(self):
        """Average past growth rate (CAGR) of your holdings, weighted by value:
            expected return = sum(value * CAGR) / sum(value)
        Returns None if no holding has enough price history."""
        weighted_sum = 0.0
        value_with_data = 0.0
        for holding in self.holdings:
            if holding.cagr is not None:
                weighted_sum += holding.market_value() * holding.cagr
                value_with_data += holding.market_value()
        if value_with_data == 0:
            return None
        return weighted_sum / value_with_data

    def to_table(self):
        """A table of your holdings, ready to display."""
        total = self.total_value()
        rows = []
        for holding in self.holdings:
            if total > 0:
                weight = holding.market_value() / total * 100
            else:
                weight = 0.0
            rows.append({
                "Ticker": holding.ticker,
                "Shares": holding.shares,
                "Avg cost": holding.avg_cost,
                "Price": holding.price,
                "Value": holding.market_value(),
                "Gain/Loss": holding.gain(),
                "Gain/Loss %": holding.gain_percent(),
                "Day change %": holding.day_change_percent(),
                "Weight %": weight,
                "Price source": "Live" if holding.is_live else "Last saved",
            })
        return pd.DataFrame(rows)
