# Market Sentiment Pipeline

This is a personal project I built to see how financial news *actually* affects stock prices. There's a common saying in the market to "buy the rumor, sell the news", and I wanted to build a data pipeline to test if that's true.

The system fetches recent news for tech stocks (like AAPL, MSFT, TSLA, NVDA), runs the text through an NLP model (FinBERT) to figure out if the sentiment is positive or negative, and then tracks the stock's price 15, 30, and 60 minutes later. It also compares the stock's movement against the S&P 500 (SPY) so we can see the real alpha (did the stock go up because of the news, or just because the whole market went up?).

## Project Structure

* `data_fetcher.py`: Grabs the latest news from Yahoo Finance, gets the sentiment using HuggingFace's FinBERT, and saves the initial data to MongoDB.
* `price_updater.py`: A background script that checks the database for recent news and retroactively fetches the 15m, 30m, and 60m price data once enough time has passed.
* `app.py`: The Streamlit dashboard that visualizes the data. It shows win rates, average returns, and highlights stocks that have a contrarian reaction to news.

## Local Setup

1. Install the requirements:
```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

2. Create a `.env` file in the root folder and add your MongoDB connection string:
```
MONGO_URI=mongodb+srv://<username>:<password>@cluster...
```

3. Run the dashboard:
```bash
streamlit run app.py
```

Note: To keep the database updated automatically, you can set up a simple cron job to run `data_fetcher.py` and `price_updater.py` every few minutes.
