import os
import pandas as pd
import yfinance as yf
from sqlalchemy import create_engine
from dotenv import load_dotenv
from google import genai
import matplotlib.pyplot as plt
import matplotlib
matplotlib.use('QtAgg')
import seaborn as sns

# --- Configuration ---
TICKER = "AAPL"  # Company symbol
DAYS = "5d"      # yfinance period

# Load environment variables (DB_URL and GEMINI_API_KEY)
load_dotenv()
db_url = os.getenv("DB_URL")
if not db_url:
    raise ValueError("DB_URL not set in .env file")
engine = create_engine(db_url) # Create database engine once

# --- Fetch live market data ---
print(f"Fetching data for {TICKER}...")
ticker_data = yf.Ticker(TICKER)
historical_data = ticker_data.history(period=DAYS)

# Data Cleaning: Remove unnecessary columns
clean_data = historical_data.drop(columns=['Dividends', 'Stock Splits'])
print("Extraction successful. Sending to database...")
clean_data.to_sql("market_data", engine, if_exists='replace', index=True)
print("Data sent to database.\n")

# --- Retrieve data for AI analysis ---
print("Retrieving market data for analysis...")
query = """
    SELECT * FROM market_data
    WHERE "Date" >= CURRENT_DATE - INTERVAL '5 days'
    ORDER BY "Date" DESC
"""
try:
    df_analysis = pd.read_sql(query, engine)
except Exception as e:
    print(f"Error reading data: {e}")
    exit(1)
if df_analysis.empty:
    print("No market data found for the last 5 days.")
    exit(0)
    
# Format data as clean Markdown for the AI
data_markdown = df_analysis.to_markdown(index=False)

# --- 3. Gemini analysis ---
print("Sending data to Gemini for marketing insights...\n")
client = genai.Client()  # auto-reads GEMINI_API_KEY from env
prompt = f"""
You are an expert Data-Driven Digital Marketer. 
I am going to provide you with the last 5 days of stock market data.

Here is the data:
{data_markdown}

Based on this data, please generate 3 short, punchy business insights. 
Write them in a professional but engaging tone, suitable for a ProMarketa LinkedIn post or a marketing newsletter. Keep it concise.
"""

try:
    response = client.models.generate_content(
        model='gemini-2.5-flash-lite',
        contents=prompt
    )
    print("--- AI GENERATED MARKETING INSIGHTS ---")
    print(response.text)
    print("---------------------------------------\n")
except Exception as e:
    print(f"Gemini API error: {e}")
    exit(1)

# --- 4. Visualization ---
print("Creating chart...")

# Load full data for visualization (no date filter needed)
df_viz = pd.read_sql("market_data", engine)
df_viz['Date'] = pd.to_datetime(df_viz['Date']).dt.strftime('%Y-%m-%d')

# Set style and plot
sns.set_theme(style="darkgrid")
plt.figure(figsize=(10, 6))
sns.lineplot(data=df_viz, x='Date', y='Close', marker='o',
             color='#2E86AB', linewidth=3, markersize=10)
plt.title('Market Performance - AAPL Closing Prices', fontsize=16,
          fontweight='bold', pad=20)
plt.xlabel('Trading Date', fontsize=12, labelpad=10)
plt.ylabel('Closing Price (USD)', fontsize=12, labelpad=10)
plt.xticks(rotation=45)
plt.tight_layout()

filename = 'promarketa_market_chart.png'
plt.savefig(filename, dpi=300)
print(f"Chart saved as '{filename}'.")
plt.show()  