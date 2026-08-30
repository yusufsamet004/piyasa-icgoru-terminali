import os
import json
import logging
from datetime import datetime, timedelta, timezone
import ssl

import yfinance as yf
from transformers import pipeline
from dotenv import load_dotenv
from pymongo.mongo_client import MongoClient

try:
    _create_unverified_https_context = ssl._create_unverified_context
except AttributeError:
    pass
else:
    ssl._create_default_https_context = _create_unverified_https_context


logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("MarketPipeline")

class MarketDataPipeline:
    def __init__(self):
        logger.info("Yapay Zeka Modeli (FinBERT) yükleniyor...")
        self.sentiment_pipeline = pipeline("sentiment-analysis", model="ProsusAI/finbert")
        logger.info("Model başarıyla yüklendi.")
        
    def get_stock_price(self, ticker_symbol: str) -> float:
        try:
            ticker = yf.Ticker(ticker_symbol)
            data = ticker.history(period='1d', interval='1m')
            if not data.empty:
                return round(data['Close'].iloc[-1], 2)
            return None
        except (KeyError, ValueError, ConnectionError) as e:
            logger.error(f"Failed to fetch price for {ticker_symbol}: {e}")
            return None

    def get_news_and_sentiment(self, ticker_symbol: str) -> list:
        try:
            ticker = yf.Ticker(ticker_symbol)
            articles = ticker.news
            
            processed_news = []
            for article in articles[:15]:
                if 'content' in article:
                    title = article['content'].get('title', '')
                    summary = article['content'].get('summary', '') or article['content'].get('description', '')
                    pub_date_raw = article['content'].get('pubDate', '')
                    published_at = pub_date_raw if pub_date_raw else datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
                else:
                    title = article.get('title', '')
                    summary = article.get('summary', '') or article.get('description', '')
                    pub_time = article.get('providerPublishTime')
                    if pub_time:
                        published_at = datetime.fromtimestamp(pub_time, tz=timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
                    else:
                        published_at = datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')

                if title:
                    text_to_analyze = title
                    if summary:
                        text_to_analyze += ". " + summary
                        
                    text_to_analyze = text_to_analyze[:1000] 
                        
                    result = self.sentiment_pipeline(text_to_analyze)[0]
                    label = result['label']
                    score = result['score']
                    
                    if label == 'positive':
                        final_score = score
                    elif label == 'negative':
                        final_score = -score
                    else:
                        final_score = 0.0

                    processed_news.append({
                        "title": title,
                        "published_at": published_at,
                        "sentiment_score": final_score,
                        "sentiment_label": label,
                        "sentiment_probability": score
                    })
            return processed_news
        except (KeyError, ValueError, ConnectionError) as e:
            logger.error(f"Failed to fetch news for {ticker_symbol}: {e}")
            return []

def main():
    load_dotenv()
    mongo_uri = os.getenv("MONGO_URI")
    
    if not mongo_uri:
        logger.error("MONGO_URI missing.")
        return
        
    try:
        logger.info("Connecting to MongoDB Atlas...")
        client = MongoClient(mongo_uri, tlsAllowInvalidCertificates=True)
        collection = client.MarketDataDB.SentimentLogs
        
        doc_count = collection.count_documents({})
        is_live_demo = os.getenv("IS_LIVE_DEMO", "false").lower() == "true"
        
        if is_live_demo and doc_count >= 2000:
            logger.info(f"Canlı demo limitine (2000) ulaşıldı. Mevcut kayıt: {doc_count}. Yeni haber çekimi durduruldu.")
            return
            
    except (KeyError, ValueError, ConnectionError) as e:
        logger.error(f"MongoDB Error: {e}")
        return
    
    pipeline = MarketDataPipeline()
    target_portfolio = {"AAPL": "Apple", "TSLA": "Tesla", "NVDA": "Nvidia", "MSFT": "Microsoft"}
    pipeline_records = []
    
    logger.info("Starting market data pipeline execution...")
    spy_current_price = pipeline.get_stock_price("SPY")
    
    for ticker, company_name in target_portfolio.items():
        logger.info(f"Processing data for {ticker}...")
        current_price = pipeline.get_stock_price(ticker)
        news_items = pipeline.get_news_and_sentiment(ticker_symbol=ticker)
        
        for news in news_items:
            existing = collection.find_one({"ticker": ticker, "title": news['title']})
            if existing:
                logger.info(f"Duplicate news found for {ticker}, skipping: {news['title'][:30]}...")
                continue
                
            record = {
                "ticker": ticker,
                "title": news['title'],
                "price_at_news": current_price,
                "spy_price_at_news": spy_current_price,
                "sentiment_score": news['sentiment_score'],
                "sentiment_label": news['sentiment_label'],
                "sentiment_probability": news['sentiment_probability'],
                "published_at": news['published_at'],
                "price_15m": None, "price_30m": None, "price_60m": None,
                "spy_price_15m": None, "spy_price_30m": None, "spy_price_60m": None
            }
            pipeline_records.append(record)
            
    if pipeline_records:
        collection.insert_many(pipeline_records)
        logger.info(f"SUCCESS! {len(pipeline_records)} new records successfully inserted into MongoDB.")
    else:
        logger.info("No new records to insert.")

if __name__ == "__main__":
    main()