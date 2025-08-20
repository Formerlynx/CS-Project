from flask import Flask, render_template, request, redirect, url_for, session, flash
import matplotlib.pyplot as plt
from datetime import datetime, timedelta
from collections import defaultdict
import os
import pyodbc
from flask_bcrypt import Bcrypt

app = Flask(__name__)
app.secret_key = 'your_secret_key'  # Replace with a secure key
bcrypt = Bcrypt(app)

# Function to connect to the Access database
def get_db_connection():
    db_path = os.path.join(os.getcwd(), 'database', 'expenses.accdb')
    db_password = 'password'  # Replace with the actual password
    conn_str = (
        r"DRIVER={Microsoft Access Driver (*.mdb, *.accdb)};"
        f"DBQ={db_path};"
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

    # Fetch existing categories
    cursor.execute("SELECT DISTINCT category FROM expenses WHERE user_id = ?", (session['user_id'],))
    categories = [row[0] for row in cursor.fetchall()]  # Fetch all categories for the logged-in user

    if request.method == 'POST':
        raw_date = request.form['date']  # YYYY-MM-DD from browser
        try:
            date_obj = datetime.strptime(raw_date, "%Y-%m-%d")
            date = date_obj.strftime("%d-%m-%Y")  # Convert to DD-MM-YYYY
        except ValueError:
            date = raw_date  # fallback if parsing fails
        selected_category = request.form['category']
        new_category = request.form['new_category'].strip()
        amount = request.form['amount']
        # Ensure amount is rounded to 3 decimal places
        rounded_amount = round(float(amount), 3)

        # Use new category if provided
        category = new_category if new_category else selected_category

        # Insert into database with user_id
        cursor.execute(
            "INSERT INTO expenses (expense_date, category, amount, user_id) VALUES (?, ?, ?, ?)",
            (date, category, rounded_amount, session['user_id'])
        )
        
        conn.commit()
        conn.close()
        return redirect(url_for('view_expenses'))

    conn.close()
    return render_template('add.html', categories=sorted(categories))

# Route to view expenses
@app.route('/view')
def view_expenses():
    if not is_logged_in():
        flash("Please log in to view expenses.", "warning")
        return redirect(url_for('login'))

    conn = get_db_connection()
    cursor = conn.cursor()

    grouped_expenses = defaultdict(list)

    # Fetch all expenses for the logged-in user
    cursor.execute("SELECT expense_date, category, amount FROM expenses WHERE user_id = ?", (session['user_id'],))
    for row in cursor.fetchall():
        date_obj, category, amount = row  # `expense_date` is already a datetime object
        if not date_obj:
            continue  # Skip rows with NULL dates

        # Format the date as DD-MM-YYYY
        date_str = date_obj.strftime("%d-%m-%Y")
        month_year = date_obj.strftime("%B %Y")  # e.g., "July 2025"
        grouped_expenses[month_year].append((date_str, category, round(float(amount), 3)))

    # Sort months in reverse chronological order
    sorted_expenses = dict(sorted(grouped_expenses.items(), key=lambda x: datetime.strptime(x[0], "%B %Y"), reverse=True))

    conn.close()
    return render_template('view.html', expenses=sorted_expenses)

# Route to analyze expenses
@app.route('/analyze', methods=['GET'])
def analyze_expenses():
    if not is_logged_in():
        flash("Please log in to analyze expenses.", "warning")
        return redirect(url_for('login'))

    conn = get_db_connection()
    cursor = conn.cursor()

    monthly_totals = defaultdict(float)
    current_month_expenses = {}

    # Get selected range from query parameter
    range_option = request.args.get('range', '12')
    months_back = int(range_option)

    today = datetime.today()
    start_dt = today.replace(day=1) - timedelta(days=30 * (months_back - 1))
    end_dt = today

    # Generate all month labels in the range
    month_labels = []
    for i in range(months_back):
        month = (today.replace(day=1) - timedelta(days=30 * i)).strftime("%b %Y")
        month_labels.append(month)
    month_labels.reverse()  # Oldest to newest

    # Initialize all months with zero
    for label in month_labels:
        monthly_totals[label] = 0.0

    # Fetch all expenses for the logged-in user
    cursor.execute("SELECT expense_date, category, amount FROM expenses WHERE user_id = ?", (session['user_id'],))
    for row in cursor.fetchall():
        date_obj, category, amount = row

        # Ensure date_obj is a datetime object
        if isinstance(date_obj, str):
            try:
                date_obj = datetime.strptime(date_obj, "%d-%m-%Y")
            except ValueError:
                continue

        # Bar chart: fill monthly totals
        if start_dt <= date_obj <= end_dt:
            label = date_obj.strftime("%b %Y")
            monthly_totals[label] += round(float(amount), 3)

        # Pie chart: current month only
        if date_obj.month == today.month and date_obj.year == today.year:
            current_month_expenses[category] = current_month_expenses.get(category, 0) + round(float(amount), 3)

    # Pie chart
    if current_month_expenses:
        categories = list(current_month_expenses.keys())
        amounts = list(current_month_expenses.values())

        def format_amount(pct, all_vals):
            absolute = int(round(pct / 100 * sum(all_vals)))
            return f"{absolute} BHD\n({pct:.1f}%)"

        plt.figure(figsize=(8, 5))
        plt.pie(amounts, labels=categories,
                autopct=lambda pct: format_amount(pct, amounts),
                startangle=90)
        plt.title(f"{today.strftime('%B %Y')} Expense Breakdown")
        plt.savefig("static/chart.png")
        plt.close()

    # Bar chart
    months = list(monthly_totals.keys())
    totals = list(monthly_totals.values())
    plt.figure(figsize=(8, 5))
    plt.bar(months, totals, color='skyblue')
    plt.xticks(rotation=45)
    plt.ylabel("Amount (BHD)")
    plt.title(f"Monthly Spending - Past {months_back} Months")
    plt.tight_layout()
    plt.savefig("static/bar_chart.png")
    plt.close()

    total = sum(current_month_expenses.values())
    highest = max(current_month_expenses, key=current_month_expenses.get) if current_month_expenses else None

    conn.close()
    return render_template('analyze.html',
                           total=total,
                           highest=highest,
                           chart='chart.png',
                           bar_chart='bar_chart.png',
                           selected_range=range_option,
                           start_date=start_dt.strftime("%d-%m-%Y"),
                           end_date=end_dt.strftime("%d-%m-%Y"))

# Home page
@app.route('/')
def index():
    return render_template('index.html')

if __name__ == '__main__':
    app.run(debug=True)