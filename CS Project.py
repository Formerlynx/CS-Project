import matplotlib.pyplot as plt
import matplotlib

# Function to add an expense
def add_expense(category, amount, date):
    with open("expenses.txt", "a") as file:
        # Add newline after each expense for proper formatting
        file.write(f"{date},{category},{amount}\n")
    print(f"Expense of {amount} BHD in '{category}' category on {date} added successfully!")


# Function to view all expenses
def view_expenses():
    print("Your Expenses:")
    with open("expenses.txt", "r") as file:
        for line in file:
            date, category, amount = line.strip().split(",")
            print(f"{date} - {category}: {amount} BHD")

# Function to analyze expenses
def analyze_expenses():
    expenses = {}
    with open("expenses.txt", "r") as file:
        for line in file:
            _, category, amount = line.strip().split(",")
            expenses[category] = expenses.get(category, 0) + float(amount)
    
    # Calculate total and identify highest spending category
    total = sum(expenses.values())
    highest_category = max(expenses, key=expenses.get)
    print("Expense Analysis:")
    print(f"Total Expenses: {total} BHD")
    print(f"Highest Spending Category: {highest_category} ({expenses[highest_category]} BHD)")
    
    # Add a pie chart
    categories = list(expenses.keys())
    amounts = list(expenses.values())
   
    plt.figure(figsize=(8, 8))
    plt.pie(amounts, labels=categories, autopct='%1.1f%%', startangle=0)
    plt.suptitle("Expense Distribution by Category")
    plt.title(f"Total expense: {sum(amounts)}")
    plt.show()
    
# Calculate total and identify highest spending category
    total = sum(expenses.values())
    highest_category = max(expenses, key=expenses.get)
    print("Expense Analysis:")
    print(f"Total Expenses: {total} BHD")
    print(f"Highest Spending Category: {highest_category} ({expenses[highest_category]} BHD)")

# Main menu for the program
def main():
    while True:
        print("--- Personal Expense Tracker ---")
        print("1. Add Expense")
        print("2. View Expenses")
        print("3. Analyze Expenses")
        print("4. Exit")
        choice = input("Enter your choice: ")
        
        if choice == "1":
            date = input("Enter the date (DD-MM-YYYY): ")
            category = input("Enter the expense category (In sentence case): ")
            amount = input("Enter the amount (In BHD): ") # Change currency as necessary
            add_expense(category, amount, date)
        elif choice == "2":
            view_expenses()
        elif choice == "3":
            analyze_expenses()
        elif choice == "4":
            print("Goodbye!")
            break
        else:
            print("Invalid choice! Please try again.")

# Run the program
if __name__ == "__main__":
    main()