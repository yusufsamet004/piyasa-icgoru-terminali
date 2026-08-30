# Market Sentiment Pipeline (Piyasa İçgörü Terminali)

[![Live Demo](https://img.shields.io/badge/Live_Demo-Click_Here-red?style=for-the-badge&logo=streamlit)](https://piyasa-icgoru-terminali-ly4ecrgfetxghore6l9ebw.streamlit.app)

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

2. Set up a free MongoDB Atlas cluster (or local MongoDB) and get your connection string. Create a `.env` file in the root folder and add it:
```
MONGO_URI=mongodb+srv://<username>:<password>@cluster...
```

3. Run the dashboard:
```bash
streamlit run app.py
```

Note: To keep the database updated automatically, you can set up a simple cron job to run `data_fetcher.py` and `price_updater.py` every few minutes.

## Cloud Automation (GitHub Actions)

This repository includes a fully automated CI/CD pipeline (`.github/workflows/pipeline.yml`) that runs on GitHub's servers for free. It is scheduled to:
- Run `data_fetcher.py` every 2 hours to collect new articles.
- Run `price_updater.py` at the 30th minute of every hour to lock in retroactive prices.

**Live Demo Limit:** To prevent API limits and database bloat for portfolio demonstrations, you can optionally set the `IS_LIVE_DEMO="true"` environment variable. When enabled, the fetcher will gracefully stop collecting new data once the MongoDB cluster hits 2000 documents. If you wish to use this system for continuous live trading, simply do not set this variable.
