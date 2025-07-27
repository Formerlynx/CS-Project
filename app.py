from flask import Flask, render_template, request, redirect, url_for
import matplotlib.pyplot as plt
from datetime import datetime, timedelta
from collections import defaultdict
import os

app = Flask(__name__)

# Route to add expense
@app.route('/add', methods=['GET', 'POST'])
def add_expense():
    categories = set()

    # Extract existing categories from expenses.txt
    if os.path.exists("expenses.txt"):
        with open("expenses.txt", "r") as file:
            for line in file:
                parts = line.strip().split(",")
                if len(parts) == 3:
                    _, category, _ = parts
                    categories.add(category)

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

        # Use new category if provided
        category = new_category if new_category else selected_category

        with open("expenses.txt", "a") as file:
            file.write(f"{date},{category},{amount}\n")
        return redirect(url_for('view_expenses'))

    return render_template('add.html', categories=sorted(categories))


# Route to view expenses
@app.route('/view')
def view_expenses():
    grouped_expenses = defaultdict(list)

    if os.path.exists("expenses.txt"):
        with open("expenses.txt", "r") as file:
            for line in file:
                date_str, category, amount = line.strip().split(",")
                try:
                    date_obj = datetime.strptime(date_str, "%d-%m-%Y")
                except ValueError:
                    continue
                month_year = date_obj.strftime("%B %Y")  # e.g., "July 2025"
                grouped_expenses[month_year].append((date_str, category, amount))

    # Sort months in reverse chronological order
    sorted_expenses = dict(sorted(grouped_expenses.items(), key=lambda x: datetime.strptime(x[0], "%B %Y"), reverse=True))

    return render_template('view.html', expenses=sorted_expenses)


# Route to analyze expenses
@app.route('/analyze', methods=['GET'])
def analyze_expenses():

    expenses = {}
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

    if os.path.exists("expenses.txt"):
        with open("expenses.txt", "r") as file:
            lines = file.readlines()

        for line in lines:
            date_str, category, amount = line.strip().split(",")
            try:
                date_obj = datetime.strptime(date_str, "%d-%m-%Y")
            except ValueError:
                continue

            # Bar chart: fill monthly totals
            if start_dt <= date_obj <= end_dt:
                label = date_obj.strftime("%b %Y")
                monthly_totals[label] += float(amount)

            # Pie chart: current month only
            if date_obj.month == today.month and date_obj.year == today.year:
                current_month_expenses[category] = current_month_expenses.get(category, 0) + float(amount)

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

        return render_template('analyze.html',
                               total=total,
                               highest=highest,
                               chart='chart.png',
                               bar_chart='bar_chart.png',
                               selected_range=range_option,
                               start_date=start_dt.strftime("%d-%m-%Y"),
                               end_date=end_dt.strftime("%d-%m-%Y"))
    else:
        return render_template('analyze.html',
                               total=0,
                               highest=None,
                               chart=None,
                               bar_chart=None,
                               selected_range=range_option,
                               start_date=start_dt.strftime("%d-%m-%Y"),
                               end_date=end_dt.strftime("%d-%m-%Y"))
    

# Home page
@app.route('/')
def index():
    return render_template('index.html')

if __name__ == '__main__':
    app.run(debug=True)