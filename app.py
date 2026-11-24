import streamlit as st
import pandas as pd
import sqlite3
import plotly.express as px
from datetime import date, datetime
import calendar

st.set_page_config(
    page_title="Smart Expense Tracker",
    page_icon="💰",
    layout="wide"
)

DB_NAME = "smart_expenses.db"

CATEGORIES = [
    "Food", "Travel", "Shopping", "Education",
    "Bills", "Entertainment", "Health", "Rent",
    "Personal", "Other"
]

# ---------- DARK THEME ----------
st.markdown("""
<style>
.stApp {
    background: #10131c;
    color: white;
}
[data-testid="stSidebar"] {
    background: #191f2e;
}
[data-testid="stMetric"] {
    background: #20283a;
    padding: 18px;
    border-radius: 12px;
}
h1, h2, h3 {
    color: #65b9ff;
}
.stButton button {
    background: #2878d0;
    color: white;
    border-radius: 8px;
}
</style>
""", unsafe_allow_html=True)


# ---------- DATABASE ----------
def connect_db():
    conn = sqlite3.connect(DB_NAME, check_same_thread=False)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS transactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            kind TEXT NOT NULL,
            amount REAL NOT NULL,
            category TEXT NOT NULL,
            description TEXT,
            tx_date TEXT NOT NULL
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS budgets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            month TEXT NOT NULL,
            category TEXT NOT NULL,
            amount REAL NOT NULL,
            UNIQUE(month, category)
        )
    """)
    conn.commit()
    return conn


conn = connect_db()


def get_transactions(month=None):
    query = "SELECT * FROM transactions"
    params = []

    if month:
        query += " WHERE substr(tx_date, 1, 7) = ?"
        params.append(month)

    query += " ORDER BY tx_date DESC, id DESC"

    return pd.read_sql_query(query, conn, params=params)


def money(value):
    return f"₹{value:,.2f}"


# ---------- HEADER ----------
st.title("💰 Smart Expense Tracker")
st.caption("Manage your income, expenses and monthly budget.")

current_month = date.today().strftime("%Y-%m")

page = st.sidebar.radio(
    "MAIN MENU",
    [
        "Dashboard",
        "Add Transaction",
        "Transactions",
        "Budget Manager",
        "Analytics",
        "Monthly Report"
    ]
)

selected_month = st.sidebar.text_input(
    "Month (YYYY-MM)",
    value=current_month
)

# ---------- DASHBOARD ----------
if page == "Dashboard":

    st.header("📊 Dashboard")

    df = get_transactions(selected_month)

    income = df.loc[df["kind"] == "Income", "amount"].sum()
    expenses = df.loc[df["kind"] == "Expense", "amount"].sum()
    balance = income - expenses

    c1, c2, c3 = st.columns(3)

    c1.metric("Total Income", money(income))
    c2.metric("Total Expenses", money(expenses))
    c3.metric("Balance", money(balance))

    st.subheader("Recent Transactions")

    if df.empty:
        st.info("No transactions yet. Add your first transaction!")
    else:
        st.dataframe(
            df[["kind", "amount", "category", "description", "tx_date"]],
            use_container_width=True,
            hide_index=True
        )

        expense_df = df[df["kind"] == "Expense"]

        if not expense_df.empty:
            st.subheader("Expense Breakdown")

            category_data = (
                expense_df.groupby("category")["amount"]
                .sum()
                .reset_index()
            )

            fig = px.pie(
                category_data,
                names="category",
                values="amount",
                hole=0.45,
                title="Expenses by Category"
            )

            fig.update_layout(
                paper_bgcolor="#10131c",
                plot_bgcolor="#10131c",
                font_color="white"
            )

            st.plotly_chart(fig, use_container_width=True)


# ---------- ADD TRANSACTION ----------
elif page == "Add Transaction":

    st.header("➕ Add Transaction")

    with st.form("transaction_form"):

        kind = st.selectbox(
            "Transaction Type",
            ["Expense", "Income"]
        )

        amount = st.number_input(
            "Amount (₹)",
            min_value=0.01,
            step=100.0
        )

        category = st.selectbox(
            "Category",
            CATEGORIES
        )

        description = st.text_input("Description")

        tx_date = st.date_input("Date", value=date.today())

        submitted = st.form_submit_button("Save Transaction")

        if submitted:
            conn.execute("""
                INSERT INTO transactions
                (kind, amount, category, description, tx_date)
                VALUES (?, ?, ?, ?, ?)
            """, (
                kind,
                amount,
                category,
                description,
                tx_date.isoformat()
            ))

            conn.commit()

            st.success("Transaction added successfully!")
            st.rerun()


# ---------- TRANSACTIONS ----------
elif page == "Transactions":

    st.header("📋 All Transactions")

    df = get_transactions()

    if not df.empty:

        search = st.text_input("Search description or category")

        kind_filter = st.selectbox(
            "Filter Type",
            ["All", "Income", "Expense"]
        )

        if search:
            mask = (
                df["description"].fillna("").str.contains(
                    search, case=False
                )
                |
                df["category"].str.contains(search, case=False)
            )
            df = df[mask]

        if kind_filter != "All":
            df = df[df["kind"] == kind_filter]

        st.dataframe(df, use_container_width=True, hide_index=True)

        csv_data = df.to_csv(index=False).encode("utf-8")

        st.download_button(
            "Download CSV",
            csv_data,
            file_name="transactions.csv",
            mime="text/csv"
        )

        st.subheader("Delete Transaction")

        transaction_id = st.number_input(
            "Transaction ID",
            min_value=1,
            step=1
        )

        if st.button("Delete Selected Transaction"):
            conn.execute(
                "DELETE FROM transactions WHERE id = ?",
                (transaction_id,)
            )
            conn.commit()
            st.success("Transaction deleted.")
            st.rerun()

    else:
        st.info("No transactions available.")


# ---------- BUDGET MANAGER ----------
elif page == "Budget Manager":

    st.header("🎯 Budget Manager")

    with st.form("budget_form"):

        category = st.selectbox("Category", CATEGORIES)

        amount = st.number_input(
            "Monthly Budget (₹)",
            min_value=1.0,
            step=100.0
        )

        save_budget = st.form_submit_button("Save Budget")

        if save_budget:
            conn.execute("""
                INSERT INTO budgets (month, category, amount)
                VALUES (?, ?, ?)
                ON CONFLICT(month, category)
                DO UPDATE SET amount = excluded.amount
            """, (selected_month, category, amount))

            conn.commit()
            st.success("Budget saved!")
            st.rerun()

    budgets = pd.read_sql_query(
        "SELECT category, amount FROM budgets WHERE month = ?",
        conn,
        params=(selected_month,)
    )

    expenses = get_transactions(selected_month)

    if not budgets.empty:

        st.subheader("Budget Overview")

        expense_totals = (
            expenses[expenses["kind"] == "Expense"]
            .groupby("category")["amount"]
            .sum()
        )

        for _, row in budgets.iterrows():

            spent = expense_totals.get(row["category"], 0)
            budget = row["amount"]

            st.write(
                f"**{row['category']}** — "
                f"{money(spent)} / {money(budget)}"
            )

            st.progress(
                min(float(spent / budget), 1.0)
            )

            if spent > budget:
                st.warning("Budget exceeded!")


# ---------- ANALYTICS ----------
elif page == "Analytics":

    st.header("📈 Analytics")

    df = get_transactions(selected_month)

    expenses = df[df["kind"] == "Expense"]

    if expenses.empty:
        st.info("Add expenses to view analytics.")
    else:

        category_data = (
            expenses.groupby("category")["amount"]
            .sum()
            .reset_index()
        )

        fig = px.bar(
            category_data,
            x="category",
            y="amount",
            color="category",
            title="Category-wise Expenses"
        )

        fig.update_layout(
            paper_bgcolor="#10131c",
            plot_bgcolor="#10131c",
            font_color="white"
        )

        st.plotly_chart(fig, use_container_width=True)


# ---------- MONTHLY REPORT ----------
elif page == "Monthly Report":

    st.header("📅 Monthly Report")

    df = get_transactions(selected_month)

    if df.empty:
        st.info("No transactions for this month.")
    else:

        income = df.loc[
            df["kind"] == "Income", "amount"
        ].sum()

        expenses = df.loc[
            df["kind"] == "Expense", "amount"
        ].sum()

        st.metric("Income", money(income))
        st.metric("Expenses", money(expenses))
        st.metric("Savings", money(income - expenses))

        st.subheader("Full Report")

        st.dataframe(
            df,
            use_container_width=True,
            hide_index=True
        )

        st.download_button(
            "Download Monthly Report",
            df.to_csv(index=False).encode("utf-8"),
            file_name=f"report_{selected_month}.csv",
            mime="text/csv"
        )


st.sidebar.divider()
st.sidebar.caption("Smart Expense Tracker | Python Project")
