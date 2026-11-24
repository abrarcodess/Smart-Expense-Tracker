import csv
import sqlite3
from datetime import date, datetime
from tkinter import ttk, messagebox, filedialog

import customtkinter as ctk
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure


# ----------------------------- CONFIGURATION -----------------------------

APP_TITLE = "Smart Expense Tracker"
DB_NAME = "smart_expenses.db"

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

BG = "#101522"
PANEL = "#192235"
PANEL_LIGHT = "#202C42"
ACCENT = "#38BDF8"
GREEN = "#34D399"
RED = "#FB7185"
TEXT = "#F8FAFC"
MUTED = "#9AA8BD"

CATEGORIES = [
    "Food", "Travel", "Shopping", "Education", "Bills",
    "Entertainment", "Health", "Rent", "Personal", "Other"
]


# ----------------------------- DATABASE ----------------------------------

class Database:
    def __init__(self, filename=DB_NAME):
        self.conn = sqlite3.connect(filename)
        self.conn.row_factory = sqlite3.Row
        self.create_tables()

    def create_tables(self):
        self.conn.executescript("""
            CREATE TABLE IF NOT EXISTS transactions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                kind TEXT NOT NULL CHECK(kind IN ('Income', 'Expense')),
                amount REAL NOT NULL CHECK(amount > 0),
                category TEXT NOT NULL,
                description TEXT,
                tx_date TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS budgets (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                month TEXT NOT NULL,
                category TEXT NOT NULL,
                amount REAL NOT NULL CHECK(amount > 0),
                UNIQUE(month, category)
            );
        """)
        self.conn.commit()

    def add_transaction(self, kind, amount, category, description, tx_date):
        self.conn.execute(
            """INSERT INTO transactions(kind, amount, category, description, tx_date)
               VALUES (?, ?, ?, ?, ?)""",
            (kind, amount, category, description, tx_date)
        )
        self.conn.commit()

    def update_transaction(self, tx_id, kind, amount, category, description, tx_date):
        self.conn.execute(
            """UPDATE transactions
               SET kind=?, amount=?, category=?, description=?, tx_date=?
               WHERE id=?""",
            (kind, amount, category, description, tx_date, tx_id)
        )
        self.conn.commit()

    def delete_transaction(self, tx_id):
        self.conn.execute("DELETE FROM transactions WHERE id=?", (tx_id,))
        self.conn.commit()

    def get_transactions(self, month=None, kind=None, search=None):
        query = "SELECT * FROM transactions WHERE 1=1"
        params = []
        if month and month != "All":
            query += " AND substr(tx_date, 1, 7)=?"
            params.append(month)
        if kind and kind != "All":
            query += " AND kind=?"
            params.append(kind)
        if search:
            query += " AND (category LIKE ? OR description LIKE ?)"
            params.extend([f"%{search}%", f"%{search}%"])
        query += " ORDER BY tx_date DESC, id DESC"
        return self.conn.execute(query, params).fetchall()

    def totals(self, month=None):
        query = """
            SELECT
                COALESCE(SUM(CASE WHEN kind='Income' THEN amount ELSE 0 END), 0) income,
                COALESCE(SUM(CASE WHEN kind='Expense' THEN amount ELSE 0 END), 0) expenses
            FROM transactions
        """
        params = []
        if month:
            query += " WHERE substr(tx_date, 1, 7)=?"
            params.append(month)
        row = self.conn.execute(query, params).fetchone()
        return float(row["income"]), float(row["expenses"])

    def category_totals(self, month):
        return self.conn.execute("""
            SELECT category, SUM(amount) total
            FROM transactions
            WHERE kind='Expense' AND substr(tx_date, 1, 7)=?
            GROUP BY category ORDER BY total DESC
        """, (month,)).fetchall()

    def set_budget(self, month, category, amount):
        self.conn.execute("""
            INSERT INTO budgets(month, category, amount)
            VALUES (?, ?, ?)
            ON CONFLICT(month, category) DO UPDATE SET amount=excluded.amount
        """, (month, category, amount))
        self.conn.commit()

    def get_budgets(self, month):
        return self.conn.execute("""
            SELECT b.category, b.amount,
                   COALESCE(SUM(t.amount), 0) spent
            FROM budgets b
            LEFT JOIN transactions t
              ON t.category=b.category
             AND t.kind='Expense'
             AND substr(t.tx_date, 1, 7)=b.month
            WHERE b.month=?
            GROUP BY b.category, b.amount
            ORDER BY b.category
        """, (month,)).fetchall()

    def close(self):
        self.conn.close()


# ----------------------------- MAIN APP ----------------------------------

class ExpenseTracker(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.db = Database()
        self.title(APP_TITLE)
        self.geometry("1200x780")
        self.minsize(1000, 650)
        self.configure(fg_color=BG)
        self.selected_id = None

        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        self.build_sidebar()
        self.content = ctk.CTkFrame(self, fg_color=BG, corner_radius=0)
        self.content.grid(row=0, column=1, sticky="nsew", padx=20, pady=18)
        self.content.grid_columnconfigure(0, weight=1)
        self.content.grid_rowconfigure(1, weight=1)

        self.show_dashboard()
        self.protocol("WM_DELETE_WINDOW", self.on_close)

    def clear_content(self):
        for widget in self.content.winfo_children():
            widget.destroy()

    def build_sidebar(self):
        side = ctk.CTkFrame(self, width=215, corner_radius=0, fg_color="#151E2F")
        side.grid(row=0, column=0, sticky="nsew")
        side.grid_propagate(False)

        ctk.CTkLabel(
            side, text="◈ SMART\n   FINANCE",
            font=ctk.CTkFont(size=23, weight="bold"),
            text_color=ACCENT, justify="left"
        ).pack(anchor="w", padx=22, pady=(28, 35))

        items = [
            ("▦   Dashboard", self.show_dashboard),
            ("＋   Add Transaction", self.show_add),
            ("≡   Transactions", self.show_transactions),
            ("◎   Budgets", self.show_budgets),
            ("▥   Analytics", self.show_analytics),
            ("▤   Monthly Report", self.show_report),
        ]
        for label, command in items:
            ctk.CTkButton(
                side, text=label, command=command, anchor="w",
                fg_color="transparent", hover_color=PANEL_LIGHT,
                text_color=TEXT, height=43,
                font=ctk.CTkFont(size=14)
            ).pack(fill="x", padx=12, pady=4)

        ctk.CTkLabel(
            side, text="PERSONAL FINANCE\nMade with Python",
            text_color=MUTED, font=ctk.CTkFont(size=11),
            justify="left"
        ).pack(side="bottom", anchor="w", padx=22, pady=22)

    def page_header(self, title, subtitle="Manage your money smarter"):
        head = ctk.CTkFrame(self.content, fg_color="transparent")
        head.grid(row=0, column=0, sticky="ew", pady=(0, 18))
        ctk.CTkLabel(
            head, text=title, font=ctk.CTkFont(size=27, weight="bold"),
            text_color=TEXT
        ).pack(anchor="w")
        ctk.CTkLabel(
            head, text=subtitle, font=ctk.CTkFont(size=13),
            text_color=MUTED
        ).pack(anchor="w", pady=(3, 0))

    def card(self, parent, title, value, color=TEXT):
        frame = ctk.CTkFrame(parent, fg_color=PANEL, corner_radius=14)
        ctk.CTkLabel(frame, text=title, text_color=MUTED,
                     font=ctk.CTkFont(size=13)).pack(anchor="w", padx=16, pady=(14, 4))
        ctk.CTkLabel(frame, text=value, text_color=color,
                     font=ctk.CTkFont(size=23, weight="bold")).pack(anchor="w", padx=16, pady=(0, 14))
        return frame

    def current_month(self):
        return date.today().strftime("%Y-%m")

    def money(self, amount):
        return f"₹{amount:,.2f}"

    # ------------------------- DASHBOARD ---------------------------------

    def show_dashboard(self):
        self.clear_content()
        self.page_header("Dashboard", "Your financial overview at a glance")
        month = self.current_month()
        income, expenses = self.db.totals(month)
        balance = income - expenses

        cards = ctk.CTkFrame(self.content, fg_color="transparent")
        cards.grid(row=1, column=0, sticky="new")
        for col in range(3):
            cards.grid_columnconfigure(col, weight=1)
        self.card(cards, "TOTAL INCOME THIS MONTH", self.money(income), GREEN).grid(
            row=0, column=0, sticky="ew", padx=(0, 9), pady=4)
        self.card(cards, "TOTAL EXPENSES THIS MONTH", self.money(expenses), RED).grid(
            row=0, column=1, sticky="ew", padx=9, pady=4)
        self.card(cards, "AVAILABLE BALANCE", self.money(balance),
                  GREEN if balance >= 0 else RED).grid(
            row=0, column=2, sticky="ew", padx=(9, 0), pady=4)

        lower = ctk.CTkFrame(self.content, fg_color="transparent")
        lower.grid(row=2, column=0, sticky="nsew", pady=(18, 0))
        lower.grid_columnconfigure((0, 1), weight=1)
        lower.grid_rowconfigure(0, weight=1)

        chart_box = ctk.CTkFrame(lower, fg_color=PANEL, corner_radius=14)
        chart_box.grid(row=0, column=0, sticky="nsew", padx=(0, 8))
        ctk.CTkLabel(chart_box, text="Spending by category",
                     font=ctk.CTkFont(size=16, weight="bold")).pack(anchor="w", padx=16, pady=12)
        self.draw_category_chart(chart_box, month)

        recent = ctk.CTkFrame(lower, fg_color=PANEL, corner_radius=14)
        recent.grid(row=0, column=1, sticky="nsew", padx=(8, 0))
        ctk.CTkLabel(recent, text="Recent transactions",
                     font=ctk.CTkFont(size=16, weight="bold")).pack(anchor="w", padx=16, pady=12)
        for tx in self.db.get_transactions(month=month)[:7]:
            row = ctk.CTkFrame(recent, fg_color="transparent")
            row.pack(fill="x", padx=14, pady=5)
            ctk.CTkLabel(row, text=f"{tx['category']}  ·  {tx['tx_date']}",
                         text_color=TEXT).pack(side="left")
            amount_color = GREEN if tx["kind"] == "Income" else RED
            sign = "+" if tx["kind"] == "Income" else "-"
            ctk.CTkLabel(row, text=f"{sign}{self.money(tx['amount'])}",
                         text_color=amount_color).pack(side="right")
        if not self.db.get_transactions(month=month):
            ctk.CTkLabel(recent, text="No transactions this month yet.",
                         text_color=MUTED).pack(pady=30)

        self.add_insight_banner()

    def draw_category_chart(self, parent, month):
        rows = self.db.category_totals(month)
        fig = Figure(figsize=(4.5, 3.0), dpi=90, facecolor=PANEL)
        ax = fig.add_subplot(111)
        ax.set_facecolor(PANEL)
        if rows:
            labels = [r["category"] for r in rows]
            values = [r["total"] for r in rows]
            ax.pie(values, labels=labels, autopct="%1.0f%%",
                   textprops={"color": TEXT, "fontsize": 8}, startangle=90)
        else:
            ax.text(0.5, 0.5, "No expense data yet", color=MUTED,
                    ha="center", va="center")
            ax.axis("off")
        fig.tight_layout()
        canvas = FigureCanvasTkAgg(fig, master=parent)
        canvas.draw()
        canvas.get_tk_widget().pack(fill="both", expand=True, padx=8, pady=(0, 8))

    def add_insight_banner(self):
        month = self.current_month()
        rows = self.db.category_totals(month)
        if not rows:
            message = "Smart insight: Add a few expenses to discover your spending patterns."
        else:
            top = rows[0]
            income, expenses = self.db.totals(month)
            share = (top["total"] / expenses * 100) if expenses else 0
            message = (f"Smart insight: Your highest spending category is {top['category']} "
                       f"({share:.1f}% of this month's expenses).")
        banner = ctk.CTkFrame(self.content, fg_color="#173047", corner_radius=12)
        banner.grid(row=3, column=0, sticky="ew", pady=(15, 0))
        ctk.CTkLabel(banner, text=message, text_color="#CDEBFF",
                     font=ctk.CTkFont(size=13)).pack(anchor="w", padx=16, pady=13)

    # ------------------------- ADD TRANSACTION ----------------------------

    def show_add(self):
        self.clear_content()
        self.page_header("Add Transaction", "Record income or an expense")
        form = ctk.CTkFrame(self.content, fg_color=PANEL, corner_radius=14)
        form.grid(row=1, column=0, sticky="new", padx=4, pady=4)
        form.grid_columnconfigure(1, weight=1)

        self.kind_var = ctk.StringVar(value="Expense")
        self.amount_var = ctk.StringVar()
        self.category_var = ctk.StringVar(value=CATEGORIES[0])
        self.description_var = ctk.StringVar()
        self.date_var = ctk.StringVar(value=date.today().isoformat())

        fields = [
            ("Transaction type", ctk.CTkOptionMenu(form, variable=self.kind_var,
                                                   values=["Expense", "Income"])),
            ("Amount (₹)", ctk.CTkEntry(form, textvariable=self.amount_var,
                                        placeholder_text="e.g. 250")),
            ("Category", ctk.CTkOptionMenu(form, variable=self.category_var,
                                           values=CATEGORIES)),
            ("Description", ctk.CTkEntry(form, textvariable=self.description_var,
                                         placeholder_text="e.g. Lunch with friends")),
            ("Date (YYYY-MM-DD)", ctk.CTkEntry(form, textvariable=self.date_var)),
        ]
        for i, (label, widget) in enumerate(fields):
            ctk.CTkLabel(form, text=label, text_color=MUTED).grid(
                row=i, column=0, sticky="w", padx=22, pady=13)
            widget.grid(row=i, column=1, sticky="ew", padx=22, pady=13)

        ctk.CTkButton(form, text="Save Transaction", height=42,
                      fg_color=ACCENT, text_color="#07111F",
                      font=ctk.CTkFont(weight="bold"),
                      command=self.save_transaction).grid(
            row=5, column=0, columnspan=2, sticky="ew", padx=22, pady=22)

    def save_transaction(self):
        try:
            amount = float(self.amount_var.get().strip())
            if amount <= 0:
                raise ValueError
            tx_date = datetime.strptime(self.date_var.get().strip(), "%Y-%m-%d").date()
        except ValueError:
            messagebox.showerror("Invalid input",
                                 "Enter an amount greater than zero and a valid date (YYYY-MM-DD).")
            return

        self.db.add_transaction(
            self.kind_var.get(), amount, self.category_var.get(),
            self.description_var.get().strip(), tx_date.isoformat()
        )
        messagebox.showinfo("Saved", "Transaction added successfully.")
        self.show_dashboard()

    # ------------------------- TRANSACTION HISTORY -----------------------

    def show_transactions(self):
        self.clear_content()
        self.page_header("Transactions", "Search, filter, edit and delete records")

        controls = ctk.CTkFrame(self.content, fg_color="transparent")
        controls.grid(row=1, column=0, sticky="ew", pady=(0, 10))
        self.search_var = ctk.StringVar()
        self.filter_kind = ctk.StringVar(value="All")
        self.filter_month = ctk.StringVar(value="All")
        ctk.CTkEntry(controls, textvariable=self.search_var,
                     placeholder_text="Search category or description",
                     width=250).pack(side="left", padx=(0, 8))
        ctk.CTkOptionMenu(controls, variable=self.filter_kind,
                         values=["All", "Income", "Expense"],
                         command=lambda _: self.refresh_transactions()).pack(side="left", padx=5)
        months = ["All"] + sorted({
            tx["tx_date"][:7] for tx in self.db.get_transactions()
        }, reverse=True)
        ctk.CTkOptionMenu(controls, variable=self.filter_month, values=months,
                         command=lambda _: self.refresh_transactions()).pack(side="left", padx=5)
        ctk.CTkButton(controls, text="Search", command=self.refresh_transactions,
                      width=90).pack(side="left", padx=5)
        ctk.CTkButton(controls, text="Export CSV", command=self.export_csv,
                      fg_color=GREEN, text_color="#07111F", width=105).pack(side="right")

        table_frame = ctk.CTkFrame(self.content, fg_color=PANEL, corner_radius=12)
        table_frame.grid(row=2, column=0, sticky="nsew")
        self.content.grid_rowconfigure(2, weight=1)

        style = ttk.Style()
        style.theme_use("default")
        style.configure("Treeview", background=PANEL, foreground=TEXT,
                        fieldbackground=PANEL, rowheight=30, borderwidth=0)
        style.configure("Treeview.Heading", background=PANEL_LIGHT,
                        foreground=TEXT, font=("Arial", 10, "bold"))
        style.map("Treeview", background=[("selected", "#245B7A")])

        columns = ("ID", "Date", "Type", "Category", "Description", "Amount")
        self.tree = ttk.Treeview(table_frame, columns=columns, show="headings")
        widths = [50, 105, 90, 125, 300, 120]
        for col, width in zip(columns, widths):
            self.tree.heading(col, text=col)
            self.tree.column(col, width=width, anchor="w")
        self.tree.pack(fill="both", expand=True, padx=8, pady=8)
        self.tree.bind("<<TreeviewSelect>>", self.on_select_transaction)

        actions = ctk.CTkFrame(self.content, fg_color="transparent")
        actions.grid(row=3, column=0, sticky="ew", pady=12)
        ctk.CTkButton(actions, text="Edit selected", command=self.edit_selected).pack(side="left", padx=4)
        ctk.CTkButton(actions, text="Delete selected", command=self.delete_selected,
                      fg_color="#9F3348", hover_color="#7F2638").pack(side="left", padx=4)
        self.refresh_transactions()

    def refresh_transactions(self):
        if not hasattr(self, "tree") or not self.tree.winfo_exists():
            return
        for item in self.tree.get_children():
            self.tree.delete(item)
        rows = self.db.get_transactions(
            month=self.filter_month.get(),
            kind=self.filter_kind.get(),
            search=self.search_var.get().strip()
        )
        for tx in rows:
            sign = "+" if tx["kind"] == "Income" else "-"
            self.tree.insert("", "end", values=(
                tx["id"], tx["tx_date"], tx["kind"], tx["category"],
                tx["description"], f"{sign}{self.money(tx['amount'])}"
            ))

    def on_select_transaction(self, _event=None):
        selected = self.tree.selection()
        self.selected_id = int(self.tree.item(selected[0], "values")[0]) if selected else None

    def edit_selected(self):
        if not self.selected_id:
            messagebox.showwarning("Select a transaction", "Choose a row first.")
            return
        tx = next((x for x in self.db.get_transactions()
                   if x["id"] == self.selected_id), None)
        if not tx:
            return

        win = ctk.CTkToplevel(self)
        win.title("Edit transaction")
        win.geometry("430x470")
        win.transient(self)
        win.grab_set()

        kind = ctk.StringVar(value=tx["kind"])
        amount = ctk.StringVar(value=str(tx["amount"]))
        category = ctk.StringVar(value=tx["category"])
        description = ctk.StringVar(value=tx["description"] or "")
        tx_date = ctk.StringVar(value=tx["tx_date"])

        widgets = [
            ("Type", ctk.CTkOptionMenu(win, variable=kind, values=["Expense", "Income"])),
            ("Amount", ctk.CTkEntry(win, textvariable=amount)),
            ("Category", ctk.CTkOptionMenu(win, variable=category, values=CATEGORIES)),
            ("Description", ctk.CTkEntry(win, textvariable=description)),
            ("Date YYYY-MM-DD", ctk.CTkEntry(win, textvariable=tx_date)),
        ]
        for label, widget in widgets:
            ctk.CTkLabel(win, text=label).pack(anchor="w", padx=24, pady=(12, 2))
            widget.pack(fill="x", padx=24)

        def save():
            try:
                val = float(amount.get())
                if val <= 0:
                    raise ValueError
                parsed_date = datetime.strptime(tx_date.get(), "%Y-%m-%d").date()
            except ValueError:
                messagebox.showerror("Invalid input", "Check the amount and date.")
                return
            self.db.update_transaction(self.selected_id, kind.get(), val,
                                       category.get(), description.get(),
                                       parsed_date.isoformat())
            win.destroy()
            self.refresh_transactions()
            messagebox.showinfo("Updated", "Transaction updated.")

        ctk.CTkButton(win, text="Save changes", command=save).pack(fill="x", padx=24, pady=22)

    def delete_selected(self):
        if not self.selected_id:
            messagebox.showwarning("Select a transaction", "Choose a row first.")
            return
        if messagebox.askyesno("Confirm delete", "Delete this transaction permanently?"):
            self.db.delete_transaction(self.selected_id)
            self.selected_id = None
            self.refresh_transactions()

    def export_csv(self):
        rows = self.db.get_transactions(
            month=self.filter_month.get(),
            kind=self.filter_kind.get(),
            search=self.search_var.get().strip()
        )
        if not rows:
            messagebox.showinfo("No data", "There are no transactions to export.")
            return
        path = filedialog.asksaveasfilename(
            defaultextension=".csv", filetypes=[("CSV files", "*.csv")],
            initialfile="expense_report.csv"
        )
        if not path:
            return
        with open(path, "w", newline="", encoding="utf-8-sig") as file:
            writer = csv.writer(file)
            writer.writerow(["ID", "Type", "Amount", "Category", "Description", "Date"])
            for tx in rows:
                writer.writerow([tx["id"], tx["kind"], tx["amount"],
                                 tx["category"], tx["description"], tx["tx_date"]])
        messagebox.showinfo("Export complete", f"CSV saved to:\n{path}")

    # ------------------------- BUDGET MANAGER -----------------------------

    def show_budgets(self):
        self.clear_content()
        self.page_header("Budget Manager", "Set monthly limits and monitor your spending")
        month_var = ctk.StringVar(value=self.current_month())
        category_var = ctk.StringVar(value=CATEGORIES[0])
        amount_var = ctk.StringVar()

        form = ctk.CTkFrame(self.content, fg_color=PANEL, corner_radius=12)
        form.grid(row=1, column=0, sticky="ew", pady=(0, 14))
        ctk.CTkLabel(form, text="Month (YYYY-MM)").grid(row=0, column=0, padx=10, pady=14)
        ctk.CTkEntry(form, textvariable=month_var, width=120).grid(row=0, column=1, padx=8)
        ctk.CTkLabel(form, text="Category").grid(row=0, column=2, padx=8)
        ctk.CTkOptionMenu(form, variable=category_var, values=CATEGORIES).grid(row=0, column=3, padx=8)
        ctk.CTkLabel(form, text="Budget (₹)").grid(row=0, column=4, padx=8)
        ctk.CTkEntry(form, textvariable=amount_var, width=120).grid(row=0, column=5, padx=8)
        ctk.CTkButton(form, text="Save budget",
                      command=lambda: self.save_budget(month_var.get(), category_var.get(),
                                                       amount_var.get())).grid(
            row=0, column=6, padx=12)

        list_frame = ctk.CTkScrollableFrame(self.content, fg_color=PANEL, corner_radius=12)
        list_frame.grid(row=2, column=0, sticky="nsew")
        self.content.grid_rowconfigure(2, weight=1)

        def refresh(*_):
            for child in list_frame.winfo_children():
                child.destroy()
            try:
                datetime.strptime(month_var.get(), "%Y-%m")
            except ValueError:
                ctk.CTkLabel(list_frame, text="Enter month in YYYY-MM format.",
                             text_color=RED).pack(pady=20)
                return
            rows = self.db.get_budgets(month_var.get())
            if not rows:
                ctk.CTkLabel(list_frame, text="No budgets set for this month.",
                             text_color=MUTED).pack(pady=25)
            for row in rows:
                spent = float(row["spent"])
                limit = float(row["amount"])
                ratio = min(spent / limit, 1) if limit else 0
                color = RED if spent > limit else GREEN
                item = ctk.CTkFrame(list_frame, fg_color=PANEL_LIGHT, corner_radius=10)
                item.pack(fill="x", padx=8, pady=7)
                top = ctk.CTkFrame(item, fg_color="transparent")
                top.pack(fill="x", padx=12, pady=(10, 4))
                ctk.CTkLabel(top, text=row["category"],
                             font=ctk.CTkFont(weight="bold")).pack(side="left")
                ctk.CTkLabel(top, text=f"{self.money(spent)} / {self.money(limit)}",
                             text_color=color).pack(side="right")
                bar = ctk.CTkProgressBar(item, progress_color=color)
                bar.pack(fill="x", padx=12, pady=(4, 12))
                bar.set(ratio)
                if spent > limit:
                    ctk.CTkLabel(item, text="Budget exceeded!",
                                 text_color=RED).pack(anchor="w", padx=12, pady=(0, 8))
        month_var.trace_add("write", refresh)
        refresh()

    def save_budget(self, month, category, amount_text):
        try:
            datetime.strptime(month, "%Y-%m")
            amount = float(amount_text)
            if amount <= 0:
                raise ValueError
        except ValueError:
            messagebox.showerror("Invalid budget", "Enter a valid month (YYYY-MM) and amount above zero.")
            return
        self.db.set_budget(month, category, amount)
        messagebox.showinfo("Saved", "Monthly budget saved.")
        self.show_budgets()

    # ------------------------- ANALYTICS ----------------------------------

    def show_analytics(self):
        self.clear_content()
        self.page_header("Analytics", "Understand where your money goes")
        month_var = ctk.StringVar(value=self.current_month())
        controls = ctk.CTkFrame(self.content, fg_color="transparent")
        controls.grid(row=1, column=0, sticky="ew", pady=(0, 10))
        ctk.CTkLabel(controls, text="Month (YYYY-MM)").pack(side="left", padx=5)
        ctk.CTkEntry(controls, textvariable=month_var, width=130).pack(side="left", padx=5)

        chart_area = ctk.CTkFrame(self.content, fg_color=PANEL, corner_radius=12)
        chart_area.grid(row=2, column=0, sticky="nsew")
        self.content.grid_rowconfigure(2, weight=1)

        def draw(*_):
            for child in chart_area.winfo_children():
                child.destroy()
            try:
                datetime.strptime(month_var.get(), "%Y-%m")
            except ValueError:
                ctk.CTkLabel(chart_area, text="Use YYYY-MM format.",
                             text_color=RED).pack(pady=20)
                return
            rows = self.db.category_totals(month_var.get())
            fig = Figure(figsize=(8, 4.5), dpi=100, facecolor=PANEL)
            ax = fig.add_subplot(111)
            ax.set_facecolor(PANEL)
            if rows:
                names = [r["category"] for r in rows]
                values = [r["total"] for r in rows]
                bars = ax.bar(names, values)
                ax.set_ylabel("Amount (₹)", color=TEXT)
                ax.tick_params(axis="x", rotation=25, labelcolor=TEXT)
                ax.tick_params(axis="y", labelcolor=TEXT)
                ax.spines["bottom"].set_color(MUTED)
                ax.spines["left"].set_color(MUTED)
                ax.spines["top"].set_visible(False)
                ax.spines["right"].set_visible(False)
                ax.set_title("Monthly expenses by category", color=TEXT)
                ax.grid(axis="y", alpha=0.15)
            else:
                ax.text(0.5, 0.5, "No expense data for this month",
                        color=MUTED, ha="center", va="center")
                ax.axis("off")
            fig.tight_layout()
            canvas = FigureCanvasTkAgg(fig, master=chart_area)
            canvas.draw()
            canvas.get_tk_widget().pack(fill="both", expand=True, padx=12, pady=12)
        month_var.trace_add("write", draw)
        draw()

    # ------------------------- MONTHLY REPORT -----------------------------

    def show_report(self):
        self.clear_content()
        self.page_header("Monthly Report", "Summary, trends and downloadable records")
        month_var = ctk.StringVar(value=self.current_month())
        controls = ctk.CTkFrame(self.content, fg_color="transparent")
        controls.grid(row=1, column=0, sticky="ew", pady=(0, 12))
        ctk.CTkLabel(controls, text="Month (YYYY-MM)").pack(side="left", padx=5)
        ctk.CTkEntry(controls, textvariable=month_var, width=130).pack(side="left", padx=5)
        report = ctk.CTkFrame(self.content, fg_color=PANEL, corner_radius=12)
        report.grid(row=2, column=0, sticky="nsew")
        self.content.grid_rowconfigure(2, weight=1)

        def refresh(*_):
            for child in report.winfo_children():
                child.destroy()
            try:
                datetime.strptime(month_var.get(), "%Y-%m")
            except ValueError:
                ctk.CTkLabel(report, text="Use YYYY-MM format.",
                             text_color=RED).pack(pady=20)
                return
            income, expenses = self.db.totals(month_var.get())
            balance = income - expenses
            ctk.CTkLabel(report, text=f"REPORT FOR {month_var.get()}",
                         font=ctk.CTkFont(size=20, weight="bold")).pack(pady=(22, 14))
            for label, value, color in [
                ("Income", income, GREEN), ("Expenses", expenses, RED),
                ("Net balance", balance, GREEN if balance >= 0 else RED)
            ]:
                line = ctk.CTkFrame(report, fg_color="transparent")
                line.pack(fill="x", padx=30, pady=8)
                ctk.CTkLabel(line, text=label, text_color=MUTED).pack(side="left")
                ctk.CTkLabel(line, text=self.money(value), text_color=color,
                             font=ctk.CTkFont(size=16, weight="bold")).pack(side="right")
            ctk.CTkLabel(report, text="Category breakdown",
                         font=ctk.CTkFont(size=16, weight="bold")).pack(anchor="w", padx=30, pady=(20, 8))
            rows = self.db.category_totals(month_var.get())
            if not rows:
                ctk.CTkLabel(report, text="No expenses recorded.",
                             text_color=MUTED).pack(anchor="w", padx=30)
            for row in rows:
                ctk.CTkLabel(report, text=f"• {row['category']}: {self.money(row['total'])}",
                             text_color=TEXT).pack(anchor="w", padx=38, pady=3)
            ctk.CTkButton(report, text="Export this month's CSV",
                          command=lambda: self.export_month_csv(month_var.get())).pack(
                anchor="w", padx=30, pady=25)
        month_var.trace_add("write", refresh)
        refresh()

    def export_month_csv(self, month):
        rows = self.db.get_transactions(month=month)
        if not rows:
            messagebox.showinfo("No data", "No transactions for this month.")
            return
        path = filedialog.asksaveasfilename(
            defaultextension=".csv", initialfile=f"report_{month}.csv",
            filetypes=[("CSV files", "*.csv")]
        )
        if not path:
            return
        with open(path, "w", newline="", encoding="utf-8-sig") as file:
            writer = csv.writer(file)
            writer.writerow(["ID", "Type", "Amount", "Category", "Description", "Date"])
            for tx in rows:
                writer.writerow([tx["id"], tx["kind"], tx["amount"],
                                 tx["category"], tx["description"], tx["tx_date"]])
        messagebox.showinfo("Export complete", "Monthly CSV report exported.")

    def on_close(self):
        self.db.close()
        self.destroy()


if __name__ == "__main__":
    app = ExpenseTracker()
    app.mainloop()
