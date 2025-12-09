from flask import Flask, render_template, request, redirect, url_for, session, flash
import matplotlib
matplotlib.use('Agg')  # Use non-GUI backend for executables
import matplotlib.pyplot as plt
from datetime import datetime, timedelta
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
    expenses = [
        {'id': row[0], 'date': row[1], 'category': row[2], 'amount': row[3]}
        for row in cursor.fetchall()
    ]

    conn.close()
    return render_template('view.html', expenses=expenses)

# Route to analyze expenses
@app.route('/analyze')
def analyze_expenses():
    if not is_logged_in():
        flash("Please log in to analyze expenses.", "warning")
        return redirect(url_for('login'))

    conn = get_db_connection()
    cursor = conn.cursor()

    # Fetch data for analysis
    cursor.execute("SELECT category, SUM(amount) FROM expenses WHERE user_id = ? GROUP BY category", (session['user_id'],))
    data = cursor.fetchall()
    conn.close()

    categories = [row[0] for row in data]
    amounts = [row[1] for row in data]

    # Ensure static folder exists for charts
    if getattr(sys, 'frozen', False):
        # Running as executable - save charts to user data folder
        static_path = os.path.join(get_user_data_path(), 'static')
    else:
        # Running as script - use local static folder
        static_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'static')
    
    if not os.path.exists(static_path):
        os.makedirs(static_path)

    # Generate Pie Chart
    plt.figure(figsize=(6, 6))
    plt.pie(amounts, labels=categories, autopct='%1.1f%%', startangle=140, textprops={'color': 'white'})
    plt.title('Expense Breakdown', color='white')
    plt.gca().set_facecolor('#121212')
    plt.gcf().set_facecolor('#121212')
    chart_path = os.path.join(static_path, 'chart.png')
    plt.savefig(chart_path, dpi=300, bbox_inches='tight')
    plt.close()

    # Generate Bar Chart
    plt.figure(figsize=(8, 5))
    plt.bar(categories, amounts, color='skyblue')
    plt.title('Monthly Spending Trend', color='white')
    plt.xlabel('Category', color='white')
    plt.ylabel('Amount', color='white')
    plt.gca().set_facecolor('#121212')
    plt.gcf().set_facecolor('#121212')
    plt.xticks(color='white')
    plt.yticks(color='white')
    bar_chart_path = os.path.join(static_path, 'bar_chart.png')
    plt.savefig(bar_chart_path, dpi=300, bbox_inches='tight')
    plt.close()

    return render_template(
        'analyze.html',
        chart='chart.png',
        bar_chart='bar_chart.png',
        total=sum(amounts),
        highest=max(categories, key=lambda c: amounts[categories.index(c)]) if categories else None,
        start_date='Start Date',
        end_date='End Date'
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

        # Update the expense in the database
        cursor.execute(
            "UPDATE expenses SET expense_date = ?, category = ?, amount = ? WHERE id = ? AND user_id = ?",
            (date, category, amount, expense_id, session['user_id'])
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