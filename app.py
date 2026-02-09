from flask import Flask, render_template, request, redirect, url_for, session, flash
import matplotlib
matplotlib.use('Agg')  # Use non-GUI backend for executables
import matplotlib.pyplot as plt
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta
from collections import defaultdict
import os
import sys
import pyodbc
import shutil
from flask_bcrypt import Bcrypt

# Configure paths for PyInstaller
def get_base_path():
    """Get the base path for resources (works for both dev and frozen)"""
    if getattr(sys, 'frozen', False):
        # Running as compiled executable
        return sys._MEIPASS
    else:
        # Running as script
        return os.path.dirname(os.path.abspath(__file__))

def get_user_data_path():
    """Get path for user data (persistent storage)"""
    if sys.platform == 'win32':
        # Windows: Use AppData\Local
        base = os.path.join(os.environ.get('LOCALAPPDATA', os.path.expanduser('~')), 'ExpenseTracker')
    else:
        # Mac/Linux: Use home directory
        base = os.path.join(os.path.expanduser('~'), '.expensetracker')
    
    if not os.path.exists(base):
        os.makedirs(base)
    return base

def initialize_database():
    """
    Initialize the database for the application.
    If running as executable, copy template database to user data folder.
    """
    if getattr(sys, 'frozen', False):
        # Running as executable - use persistent user data folder
        user_data_path = get_user_data_path()
        db_path = os.path.join(user_data_path, 'expenses.accdb')
        
        # If database doesn't exist in user folder, copy template from exe
        if not os.path.exists(db_path):
            template_db = os.path.join(sys._MEIPASS, 'Database', 'expenses.accdb')
            if os.path.exists(template_db):
                print(f"First run detected. Creating database at: {db_path}")
                shutil.copy2(template_db, db_path)
                print("Database initialized successfully!")
            else:
                raise FileNotFoundError("Template database not found in executable!")
        
        return db_path
    else:
        # Running as script - use local Database folder
        return os.path.join(os.getcwd(), 'Database', 'expenses.accdb')

base_path = get_base_path()
template_folder = os.path.join(base_path, 'templates')
static_folder = os.path.join(base_path, 'static')

app = Flask(__name__, template_folder=template_folder, static_folder=static_folder)
app.secret_key = 'your_secret_key_change_in_production'  # CHANGE THIS IN PRODUCTION
bcrypt = Bcrypt(app)

# Initialize database path
DB_PATH = initialize_database()

# Function to connect to the Access database
def get_db_connection():
    db_password = 'password'  # Replace with the actual password
    conn_str = (
        r"DRIVER={Microsoft Access Driver (*.mdb, *.accdb)};"
        f"DBQ={DB_PATH};"
        f"PWD={db_password};"
    )
    return pyodbc.connect(conn_str)

# Function to check if a user is logged in
def is_logged_in():
    return 'user_id' in session

# Middleware to restrict access to logged-in users
@app.before_request
def restrict_access():
    allowed_routes = ['login', 'signup', 'static']  # Allow login, signup, and static files
    if not is_logged_in() and request.endpoint not in allowed_routes:
        return redirect(url_for('login'))

# Route for sign-up
@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        hashed_password = bcrypt.generate_password_hash(password).decode('utf-8')

        conn = get_db_connection()
        cursor = conn.cursor()

        try:
            # Insert new user into the database
            cursor.execute("INSERT INTO users (username, password) VALUES (?, ?)", (username, hashed_password))
            conn.commit()
            conn.close()

            flash("Account created successfully! Please log in.", "success")
            return redirect(url_for('login'))
        except pyodbc.IntegrityError:
            # Handle duplicate username error
            flash("Username entered already exists, please choose another one.", "danger")
            conn.close()
            return redirect(url_for('signup'))

    return render_template('signup.html')

# Route for login
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        conn = get_db_connection()
        cursor = conn.cursor()

        # Fetch user from the database
        cursor.execute("SELECT id, password FROM users WHERE username = ?", (username,))
        user = cursor.fetchone()
        conn.close()

        if user and bcrypt.check_password_hash(user[1], password):
            session['user_id'] = user[0]
            session['username'] = username
            flash("Logged in successfully!", "success")
            return redirect(url_for('index'))
        else:
            flash("Invalid username or password.", "danger")

    return render_template('login.html')

# Route for logout
@app.route('/logout')
def logout():
    session.clear()
    flash("You have been logged out.", "info")
    return redirect(url_for('login'))

# Route to add expense
@app.route('/add', methods=['GET', 'POST'])
def add_expense():
    if not is_logged_in():
        flash("Please log in to add expenses.", "warning")
        return redirect(url_for('login'))

    conn = get_db_connection()
    cursor = conn.cursor()

    # Fetch existing categories for the dropdown
    cursor.execute("SELECT DISTINCT category FROM expenses WHERE user_id = ?", (session['user_id'],))
    categories = [row[0] for row in cursor.fetchall()]

    if request.method == 'POST':
        raw_date = request.form['date']
        try:
            date_obj = datetime.strptime(raw_date, "%Y-%m-%d")
            date = date_obj.strftime("%d-%m-%Y")
        except ValueError:
            date = raw_date

        selected_category = request.form['category']
        new_category = request.form.get('new_category', '').strip()
        amount = request.form['amount']
        rounded_amount = round(float(amount), 3)

        # Use the new category if provided
        category = new_category if selected_category == 'add_new' else selected_category

        # Insert the expense into the database
        cursor.execute(
            "INSERT INTO expenses (expense_date, category, amount, user_id) VALUES (?, ?, ?, ?)",
            (date, category, rounded_amount, session['user_id'])
        )
        conn.commit()
        conn.close()

        flash("Expense added successfully!", "success")
        return redirect(url_for('view_expenses'))

    conn.close()
    return render_template('add.html', categories=categories)

# Route to view expenses
@app.route('/view')
def view_expenses():
    if not is_logged_in():
        flash("Please log in to view expenses.", "warning")
        return redirect(url_for('login'))

    conn = get_db_connection()
    cursor = conn.cursor()

    # Fetch all expenses for the logged-in user
    cursor.execute("SELECT id, expense_date, category, amount FROM expenses WHERE user_id = ?", (session['user_id'],))
    rows = cursor.fetchall()

    expenses = []
    for row in rows:
        raw_date = row[1]
        # Normalize date: if it's a datetime object, or a string containing time, format to date-only string
        try:
            if isinstance(raw_date, datetime):
                date_str = raw_date.strftime("%d-%m-%Y")
            else:
                # Attempt to parse common datetime string formats and fall back to splitting
                raw_date_str = str(raw_date)
                try:
                    parsed = datetime.strptime(raw_date_str, "%Y-%m-%d %H:%M:%S")
                    date_str = parsed.strftime("%d-%m-%Y")
                except Exception:
                    # If it looks like YYYY-MM-DD, reformat; otherwise take up to first space (drop time)
                    if len(raw_date_str) >= 10 and raw_date_str[4] == '-' and raw_date_str[7] == '-':
                        try:
                            parsed = datetime.strptime(raw_date_str[:10], "%Y-%m-%d")
                            date_str = parsed.strftime("%d-%m-%Y")
                        except Exception:
                            date_str = raw_date_str.split(' ')[0]
                    else:
                        date_str = raw_date_str.split(' ')[0]
        except Exception:
            date_str = str(raw_date)

        # Format amount to always show 3 decimal places
        raw_amount = row[3]
        try:
            amount_val = float(raw_amount)
            amount_str = f"{amount_val:.3f}"
        except Exception:
            amount_str = str(raw_amount)

        expenses.append({'id': row[0], 'date': date_str, 'category': row[2], 'amount': amount_str})

    conn.close()
    return render_template('view.html', expenses=expenses)

# Route to analyze expenses
@app.route('/analyze')
def analyze_expenses():
    if not is_logged_in():
        flash("Please log in to analyze expenses.", "warning")
        return redirect(url_for('login'))

    # Determine selected range from query params
    selected_range = request.args.get('range')  # None means default behavior (year-to-date)
    start_date_arg = request.args.get('start_date')
    end_date_arg = request.args.get('end_date')

    today = datetime.now().date()

    # Compute current month window for pie chart and current-month stats
    first_of_month = today.replace(day=1)
    # compute last day of month by moving to next month and subtracting a day
    try:
        if first_of_month.month == 12:
            next_month = first_of_month.replace(year=first_of_month.year + 1, month=1, day=1)
        else:
            next_month = first_of_month.replace(month=first_of_month.month + 1, day=1)
        last_of_month = next_month - timedelta(days=1)
    except Exception:
        last_of_month = today

    # Fetch all user's expenses to compute both current month pie and selected range bar chart
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT category, amount, expense_date FROM expenses WHERE user_id = ?", (session['user_id'],))
    rows = cursor.fetchall()
    conn.close()

    # Helper to parse dates robustly
    def parse_date(raw_date):
        try:
            if isinstance(raw_date, datetime):
                return raw_date.date()
            s = str(raw_date)
            # Try common formats first
            for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d", "%d-%m-%Y", "%d/%m/%Y"):
                try:
                    return datetime.strptime(s[:10], fmt if '%H' not in fmt else fmt).date()
                except Exception:
                    continue
            # Last resort: parse first token as YYYY-MM-DD
            try:
                return datetime.strptime(s.split(' ')[0], "%Y-%m-%d").date()
            except Exception:
                return None
        except Exception:
            return None

    # Aggregate current month totals for pie and top category
    current_month_totals = defaultdict(float)
    for row in rows:
        cat = row[0]
        try:
            amt = float(row[1])
        except Exception:
            continue
        d = parse_date(row[2])
        if d and first_of_month <= d <= last_of_month:
            current_month_totals[cat] += amt

    # Generate pie chart for current month only
    pie_categories = list(current_month_totals.keys())
    pie_amounts = [current_month_totals[c] for c in pie_categories]

    # Determine selected range window for bar chart
    # Default: Year to date (resets each year automatically)
    if selected_range is None:
        # Year to date
        start_date = today.replace(month=1, day=1)
        end_date = today
        selected_range = 'ytd'
    else:
        try:
            if selected_range == 'custom' and start_date_arg and end_date_arg:
                start_date = datetime.strptime(start_date_arg, "%Y-%m-%d").date()
                end_date = datetime.strptime(end_date_arg, "%Y-%m-%d").date()
            elif selected_range == 'previous_year':
                start_date = today.replace(year=today.year - 1, month=1, day=1)
                end_date = today.replace(year=today.year - 1, month=12, day=31)
            elif selected_range == 'ytd':
                start_date = today.replace(month=1, day=1)
                end_date = today
            else:
                # treat numeric as months (use exact calendar months)
                months = int(selected_range)
                start_date = today - relativedelta(months=months)
                end_date = today
        except Exception:
            start_date = today.replace(month=1, day=1)
            end_date = today

    # Aggregate totals for bar chart range
    totals = defaultdict(float)
    for row in rows:
        cat = row[0]
        try:
            amt = float(row[1])
        except Exception:
            continue
        d = parse_date(row[2])
        if d and start_date <= d <= end_date:
            totals[cat] += amt

    bar_categories = list(totals.keys())
    bar_amounts = [totals[c] for c in bar_categories]

    # Ensure static folder exists for charts
    if getattr(sys, 'frozen', False):
        static_path = os.path.join(get_user_data_path(), 'static')
    else:
        static_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'static')
    if not os.path.exists(static_path):
        os.makedirs(static_path)

    pie_file = None
    bar_chart_file = None

    if pie_categories and sum(pie_amounts) > 0:
        plt.figure(figsize=(6, 6))
        plt.pie(pie_amounts, labels=pie_categories, autopct='%1.1f%%', startangle=140, textprops={'color': 'white'})
        plt.title('Current Month Breakdown', color='white')
        plt.gca().set_facecolor('#121212')
        plt.gcf().set_facecolor('#121212')
        pie_file = os.path.join(static_path, 'chart.png')
        plt.savefig(pie_file, dpi=300, bbox_inches='tight')
        plt.close()

    if bar_categories and sum(bar_amounts) > 0:
        plt.figure(figsize=(8, 5))
        plt.bar(bar_categories, bar_amounts, color='skyblue')
        plt.title('Selected Period Spending', color='white')
        plt.xlabel('Category', color='white')
        plt.ylabel('Amount', color='white')
        plt.gca().set_facecolor('#121212')
        plt.gcf().set_facecolor('#121212')
        plt.xticks(color='white')
        plt.yticks(color='white')
        bar_chart_file = os.path.join(static_path, 'bar_chart.png')
        plt.savefig(bar_chart_file, dpi=300, bbox_inches='tight')
        plt.close()

    # Compute year-to-date totals (current calendar year)
    year_totals = defaultdict(float)
    totals_by_year = defaultdict(float)
    for row in rows:
        cat = row[0]
        try:
            amt = float(row[1])
        except Exception:
            continue
        d = parse_date(row[2])
        if not d:
            continue
        totals_by_year[d.year] += amt
        if d.year == today.year:
            year_totals[cat] += amt

    year_categories = list(year_totals.keys())
    year_amounts = [year_totals[c] for c in year_categories]
    year_total = sum(year_amounts)
    year_highest = None
    if year_categories:
        year_highest = max(year_categories, key=lambda c: year_amounts[year_categories.index(c)])

    # If we have more than one year of data, generate a monthly trend line chart
    # that includes every month in the range (zeros included) so fluctuations are visible.
    yearly_trend_file = None
    if len(totals_by_year) > 1:
        # Build month-level totals keyed by the first day of the month
        month_totals = defaultdict(float)
        min_year = min(totals_by_year.keys())
        max_year = max(totals_by_year.keys())

        # Use start = Jan of min_year, end = Dec of max_year (show full years)
        start_month = datetime(min_year, 1, 1).date()
        end_month = datetime(max_year, 12, 1).date()

        # Initialize months list (every month between start and end inclusive)
        months = []
        cur = start_month
        while cur <= end_month:
            months.append(cur)
            cur = (cur + relativedelta(months=1))

        # Aggregate amounts into months
        for row in rows:
            try:
                amt = float(row[1])
            except Exception:
                continue
            d = parse_date(row[2])
            if not d:
                continue
            m_first = d.replace(day=1)
            month_totals[m_first] += amt

        month_vals = [month_totals.get(m, 0.0) for m in months]
        labels = [m.strftime('%b %Y') for m in months]

        plt.figure(figsize=(12, 4))
        plt.plot(range(len(months)), month_vals, marker='o', color='skyblue')
        plt.title('Monthly Spending Trend', color='white')
        plt.xlabel('Month', color='white')
        plt.ylabel('Total Spend', color='white')
        plt.gca().set_facecolor('#121212')
        plt.gcf().set_facecolor('#121212')
        # Show every month label (rotate for readability)
        plt.xticks(range(len(months)), labels, rotation=45, color='white')
        plt.yticks(color='white')
        yearly_trend_file = os.path.join(static_path, 'yearly_trend.png')
        plt.tight_layout()
        plt.savefig(yearly_trend_file, dpi=300, bbox_inches='tight')
        plt.close()

    # Compute current month totals and highest category
    current_month_total = sum(pie_amounts)
    current_month_highest = None
    if pie_categories:
        current_month_highest = max(pie_categories, key=lambda c: pie_amounts[pie_categories.index(c)])

    display_start = start_date.strftime("%d-%m-%Y")
    display_end = end_date.strftime("%d-%m-%Y")

    return render_template(
        'analyze.html',
        chart=os.path.basename(pie_file) if pie_file else None,
        bar_chart=os.path.basename(bar_chart_file) if bar_chart_file else None,
        total_period=sum(bar_amounts),
        highest_period=max(bar_categories, key=lambda c: bar_amounts[bar_categories.index(c)]) if bar_categories else None,
        start_date=display_start,
        end_date=display_end,
        selected_range=selected_range,
        current_month_total=current_month_total,
        current_month_highest=current_month_highest,
        year_total=year_total,
        year_highest=year_highest,
        yearly_trend=os.path.basename(yearly_trend_file) if yearly_trend_file else None
    )

# Route to serve chart images when running as executable
@app.route('/static/<path:filename>')
def serve_static(filename):
    if getattr(sys, 'frozen', False):
        # When running as executable, serve from user data folder
        static_path = os.path.join(get_user_data_path(), 'static')
        from flask import send_from_directory
        return send_from_directory(static_path, filename)
    else:
        # When running as script, use default Flask static handling
        return app.send_static_file(filename)

# Route to edit expense
@app.route('/edit/<int:expense_id>', methods=['GET', 'POST'])
def edit_expense(expense_id):
    if not is_logged_in():
        flash("Please log in to edit expenses.", "warning")
        return redirect(url_for('login'))
    conn = get_db_connection()
    cursor = conn.cursor()

    # Fetch the expense to edit
    cursor.execute("SELECT expense_date, category, amount FROM expenses WHERE id = ? AND user_id = ?", (expense_id, session['user_id']))
    expense = cursor.fetchone()

    if not expense:
        conn.close()
        flash("Expense not found.", "danger")
        return redirect(url_for('view_expenses'))

    if request.method == 'POST':
        date = request.form['date']
        category = request.form['category']
        amount = request.form['amount']

        # Normalize and format date like add_expense (store as DD-MM-YYYY when possible)
        try:
            date_obj = datetime.strptime(date, "%Y-%m-%d")
            date_to_store = date_obj.strftime("%d-%m-%Y")
        except Exception:
            date_to_store = date

        # Round amount to 3 decimal places before storing
        try:
            amount_to_store = round(float(amount), 3)
        except Exception:
            amount_to_store = amount

        # Update the expense in the database
        cursor.execute(
            "UPDATE expenses SET expense_date = ?, category = ?, amount = ? WHERE id = ? AND user_id = ?",
            (date_to_store, category, amount_to_store, expense_id, session['user_id'])
        )
        conn.commit()
        conn.close()

        flash("Expense updated successfully!", "success")
        return redirect(url_for('view_expenses'))

    conn.close()
    return render_template('edit.html', expense=expense)

# Route to delete expense
@app.route('/delete/<int:expense_id>', methods=['DELETE'])
def delete_expense(expense_id):
    if not is_logged_in():
        return {"error": "Unauthorized"}, 401

    conn = get_db_connection()
    cursor = conn.cursor()

    # Delete the expense from the database
    cursor.execute("DELETE FROM expenses WHERE id = ? AND user_id = ?", (expense_id, session['user_id']))
    conn.commit()
    conn.close()

    return {"success": True}, 200

# Home page
@app.route('/')
def index():
    return render_template('index.html')

if __name__ == '__main__':
    # For executable, you might want to automatically open the browser
    if getattr(sys, 'frozen', False):
        import webbrowser
        import threading
        
        def open_browser():
            import time
            time.sleep(1.5)
            webbrowser.open('http://127.0.0.1:5000')
        
        threading.Thread(target=open_browser).start()
    
    print("=" * 60)
    print("Expense Tracker Starting...")
    print("=" * 60)
    if getattr(sys, 'frozen', False):
        print(f"Database location: {DB_PATH}")
        print(f"Your data is safely stored at: {get_user_data_path()}")
    print("Open your browser and navigate to: http://127.0.0.1:5000")
    print("Press Ctrl+C to stop the server")
    print("=" * 60)
    
    app.run(debug=False, host='127.0.0.1', port=5000)