import os
import sqlite3
import argparse
import datetime
import matplotlib.pyplot as plt
import numpy as np
from sklearn.linear_model import LinearRegression
from pathlib import Path
from weights import prev_weights  # Import the prev_weights dictionary

# Get the directory of the current script
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(SCRIPT_DIR, 'weight_tracker.db')
DOWNLOADS_FOLDER = str(Path.home() / "Downloads")

def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS weights
                 (date TEXT PRIMARY KEY, weight REAL)''')
    c.execute('''CREATE TABLE IF NOT EXISTS preferences
                 (key TEXT PRIMARY KEY, value TEXT)''')
    conn.commit()
    conn.close()

def log_weight(date, weight):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("INSERT OR REPLACE INTO weights VALUES (?, ?)", (date, weight))
    conn.commit()
    conn.close()

def get_weights(start_date=None):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    if start_date:
        c.execute("SELECT date, weight FROM weights WHERE date >= ? ORDER BY date", (start_date,))
    else:
        c.execute("SELECT date, weight FROM weights ORDER BY date")
    
    results = c.fetchall()
    conn.close()
    
    dates = [datetime.datetime.strptime(r[0], '%Y-%m-%d').date() for r in results]
    weights = [r[1] for r in results]
    return dates, weights

def set_preference(key, value):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("INSERT OR REPLACE INTO preferences VALUES (?, ?)", (key, value))
    conn.commit()
    conn.close()

def get_preference(key, default=None):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT value FROM preferences WHERE key = ?", (key,))
    result = c.fetchone()
    conn.close()
    return result[0] if result else default

def generate_graph(dates, weights, save_path):
    date_ordinals = np.array([date.toordinal() for date in dates]).reshape(-1, 1)
    weights_array = np.array(weights).reshape(-1, 1)

    model = LinearRegression()
    model.fit(date_ordinals, weights_array)

    trend_line = model.predict(date_ordinals)
    slope = model.coef_[0][0]

    # Calculate total weight change
    total_change = weights[-1] - weights[0]
    change_sign = '+' if total_change >= 0 else ''

    plt.figure(figsize=(10, 6))
    plt.plot(dates, weights, marker='o', linestyle='-', color='blue', label=f'Weight (lbs)\nTotal change: {change_sign}{total_change:.1f} lbs / {change_sign}{total_change/2.2:.1f} kg')
    plt.plot(dates, trend_line, color='red', linestyle='--', label=f'Trend Line (Slope: {slope:.2f} lbs/day)')

    # Add labels for start and end weights
    plt.annotate(f'{weights[0]:.1f}', (dates[0], weights[0]), textcoords="offset points", xytext=(10,0), ha='left')
    plt.annotate(f'{weights[-1]:.1f}', (dates[-1], weights[-1]), textcoords="offset points", xytext=(0,10), ha='left')

    # Calculate number of ticks (about 20)
    n_ticks = min(20, len(dates))
    
    # Generate tick positions
    tick_indices = np.linspace(0, len(dates) - 1, n_ticks, dtype=int)
    tick_dates = [dates[i] for i in tick_indices]
    
    plt.xticks(tick_dates, rotation=45, ha='right')
    plt.gca().xaxis.set_major_formatter(plt.matplotlib.dates.DateFormatter('%Y-%m-%d'))

    plt.title('Weight Progress Over Time with Trend Line')
    plt.xlabel('Date')
    plt.ylabel('Weight (lbs)')
    plt.grid(True)
    plt.legend()

    plt.tight_layout()
    plt.savefig(save_path)
    plt.show()

def import_historical_data():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    for date, weight in prev_weights.items():
        c.execute("INSERT OR REPLACE INTO weights VALUES (?, ?)", (date, weight))
    
    conn.commit()
    conn.close()
    print(f"Imported {len(prev_weights)} historical weight entries.")

def main():
    parser = argparse.ArgumentParser(description='Weight Tracker')
    parser.add_argument('weight', type=float, nargs='?', help='Weight to log')
    parser.add_argument('-d', '--date', help='Date to log weight (YYYY-MM-DD), defaults to today')
    parser.add_argument('-r', '--range', choices=['1m', '6m', '1y', 'all'], help='Graph range')
    parser.add_argument('-f', '--from-date', help='Start date for graph (YYYY-MM-DD)')
    parser.add_argument('-s', '--set-default', action='store_true', help='Set the current range as default')
    parser.add_argument('--import-history', action='store_true', help='Import historical data from weights.py')
    parser.add_argument('-g', '--graph-only', action='store_true', help='Generate graph without logging weight')
    args = parser.parse_args()

    init_db()

    if args.import_history:
        import_historical_data()
        return

    if args.weight and not args.graph_only:
        date = args.date if args.date else datetime.date.today().isoformat()
        log_weight(date, args.weight)
        print(f"Logged weight: {args.weight} lbs on {date}")

    graph_range = args.range if args.range else get_preference('default_range', 'all')
    
    if args.from_date:
        start_date = datetime.datetime.strptime(args.from_date, '%Y-%m-%d').date()
        if args.set_default:
            set_preference('default_range', f'from:{args.from_date}')
            print(f"Set default graph range to start from: {args.from_date}")
    elif graph_range.startswith('from:'):
        start_date = datetime.datetime.strptime(graph_range.split(':')[1], '%Y-%m-%d').date()
    elif graph_range == '1m':
        start_date = datetime.date.today() - datetime.timedelta(days=30)
    elif graph_range == '6m':
        start_date = datetime.date.today() - datetime.timedelta(days=180)
    elif graph_range == '1y':
        start_date = datetime.date.today() - datetime.timedelta(days=365)
    else:
        start_date = None

    if args.set_default and args.range:
        set_preference('default_range', graph_range)
        print(f"Set default graph range to: {graph_range}")

    if args.graph_only or args.weight:
        dates, weights = get_weights(start_date)
        
        if dates:
            save_path = os.path.join(DOWNLOADS_FOLDER, 'weight_progress.png')
            generate_graph(dates, weights, save_path)
            print(f"Graph saved to: {save_path}")
        else:
            print("No weight data available for the selected range.")
    elif not args.set_default:
        print("No action specified. Use -h for help.")

if __name__ == "__main__":
    main()