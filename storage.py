"""
storage.py - Saving and loading the app's data.

Each part of the app keeps its data in its own CSV file inside the "data"
folder. pandas reads a CSV into a DataFrame (a table) and writes it back out.
Keeping the file handling here means the other modules never deal with paths.
"""

import os

import pandas as pd

# The data folder sits next to this file, so the app finds its data no
# matter which folder you launch it from.
APP_FOLDER = os.path.dirname(os.path.abspath(__file__))
DATA_FOLDER = os.path.join(APP_FOLDER, "data")

# Every table the app uses, and the columns each one has.
TABLE_COLUMNS = {
    "transactions": ["id", "date", "type", "category", "amount", "note"],
    "budgets": ["category", "monthly_limit"],
    "holdings": ["ticker", "shares", "avg_cost", "purchase_date", "last_price"],
    "loans": ["name", "kind", "balance", "annual_rate", "monthly_payment"],
    "properties": ["name", "kind", "value", "annual_growth"],
    "settings": ["setting", "value"],
}


def file_path(table_name):
    """Return the full path of a table's CSV file."""
    return os.path.join(DATA_FOLDER, table_name + ".csv")


def data_exists():
    """True once the app has been set up (the transactions file exists)."""
    return os.path.exists(file_path("transactions"))


def load_table(table_name):
    """Read one table from its CSV file.
    Returns an empty table (with the right columns) if the file doesn't exist yet."""
    columns = TABLE_COLUMNS[table_name]
    path = file_path(table_name)
    if not os.path.exists(path):
        return pd.DataFrame(columns=columns)
    table = pd.read_csv(path)
    # If a column is missing (for example, an older file), add it as blank.
    for column in columns:
        if column not in table.columns:
            table[column] = None
    return table[columns]


def save_table(table_name, table):
    """Write one table to its CSV file (creating the data folder if needed)."""
    os.makedirs(DATA_FOLDER, exist_ok=True)
    table.to_csv(file_path(table_name), index=False)


def load_settings():
    """Return the settings as a dictionary, e.g. {"starting_cash": "2500"}."""
    table = load_table("settings")
    settings = {}
    for _, row in table.iterrows():
        settings[row["setting"]] = row["value"]
    return settings


def save_settings(settings):
    """Save a settings dictionary back to settings.csv."""
    rows = []
    for name, value in settings.items():
        rows.append({"setting": name, "value": value})
    save_table("settings", pd.DataFrame(rows, columns=TABLE_COLUMNS["settings"]))


def delete_all_data():
    """Delete every data file so the app shows its welcome screen again."""
    for table_name in TABLE_COLUMNS:
        path = file_path(table_name)
        if os.path.exists(path):
            os.remove(path)


def create_empty_files(starting_cash=0.0, budget_limits=None):
    """Set up a brand-new, empty tracker (used by "Start with a blank tracker")."""
    for table_name in ["transactions", "holdings", "loans", "properties"]:
        save_table(table_name, pd.DataFrame(columns=TABLE_COLUMNS[table_name]))
    if budget_limits is None:
        budget_limits = {}
    rows = []
    for category, limit in budget_limits.items():
        rows.append({"category": category, "monthly_limit": limit})
    save_table("budgets", pd.DataFrame(rows, columns=TABLE_COLUMNS["budgets"]))
    save_settings({"starting_cash": starting_cash})
