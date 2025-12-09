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

    # Generate Pie Chart
    plt.figure(figsize=(6, 6))
    plt.pie(amounts, labels=categories, autopct='%1.1f%%', startangle=140, textprops={'color': 'white'})
    plt.title('Expense Breakdown', color='white')
    plt.gca().set_facecolor('#121212')  # Set the plot background
    plt.gcf().set_facecolor('#121212')  # Set the figure background
    plt.savefig('static/chart.png', dpi=300, bbox_inches='tight')
    plt.close()

    # Generate Bar Chart
    plt.figure(figsize=(8, 5))
    plt.bar(categories, amounts, color='skyblue')
    plt.title('Monthly Spending Trend', color='white')
    plt.xlabel('Category', color='white')
    plt.ylabel('Amount', color='white')
    plt.gca().set_facecolor('#121212')  # Set the plot background
    plt.gcf().set_facecolor('#121212')  # Set the figure background
    plt.xticks(color='white')  # Set x-axis label color
    plt.yticks(color='white')  # Set y-axis label color
    plt.savefig('static/bar_chart.png', dpi=300, bbox_inches='tight')
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
    app.run(debug=True)