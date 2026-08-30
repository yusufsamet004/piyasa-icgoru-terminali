import os
import logging
from datetime import datetime, timedelta
import ssl
import pandas as pd

import yfinance as yf
from dotenv import load_dotenv
from pymongo.mongo_client import MongoClient

try:
    _create_unverified_https_context = ssl._create_unverified_context
except AttributeError:
    pass
else:
    ssl._create_default_https_context = _create_unverified_https_context

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("TimeMachineBot")

def get_historical_minute_price(ticker_symbol: str, target_time_str: str) -> float:
    """Verilen dakikadaki hisse fiyatını bulur."""
    try:
        target_time = pd.to_datetime(target_time_str).tz_convert('UTC')
        ticker = yf.Ticker(ticker_symbol)
        hist_data = ticker.history(period='7d', interval='1m')
        
        if hist_data.empty: return None
            
        hist_data.index = hist_data.index.tz_convert('UTC')
        nearest_idx = hist_data.index.get_indexer([target_time], method='nearest', tolerance=pd.Timedelta('1min'))
        
        if nearest_idx[0] != -1: 
            return round(hist_data.iloc[nearest_idx[0]]['Close'], 2)
        return None
    except (KeyError, ValueError, ConnectionError) as e:
        return None

def main():
    load_dotenv()
    mongo_uri = os.getenv("MONGO_URI")
    
    if not mongo_uri:
        logger.error("MONGO_URI bulunamadı!")
        return

    logger.info("MongoDB'ye bağlanılıyor...")
    client = MongoClient(mongo_uri, tlsAllowInvalidCertificates=True)
    collection = client.MarketDataDB.SentimentLogs
    
    pending_records = list(collection.find({
        "$or": [
            {"price_15m": None},
            {"price_30m": None},
            {"price_60m": None},
            {"spy_price_at_news": {"$exists": False}},
            {"spy_price_at_news": None},
            {"spy_price_60m": {"$exists": False}}
        ]
    }))
    
    if not pending_records:
        logger.info("Güncellenecek yeni kayıt bulunamadı. Tüm zaman dilimleri (15, 30, 60) dolu.")
        return
        
    logger.info(f"{len(pending_records)} adet eksik kayıt bulundu. Çoklu tarama başlıyor...")
    
    for record in pending_records:
        ticker = record['ticker']
        published_at = record['published_at']
        news_time = pd.to_datetime(published_at)
        
        updates = {}
        intervals = {"price_15m": 15, "price_30m": 30, "price_60m": 60}
        
        for field, minutes in intervals.items():
            if record.get(field) is None:
                target_time = (news_time + timedelta(minutes=minutes)).strftime('%Y-%m-%dT%H:%M:%SZ')
                price = get_historical_minute_price(ticker, target_time)
                
                if price is not None:
                    updates[field] = price
                    logger.info(f"[{ticker}] BULUNDU: {minutes}. Dakika Fiyatı -> ${price}")
                    
            spy_field = f"spy_{field}"
            if record.get(spy_field) is None:
                target_time = (news_time + timedelta(minutes=minutes)).strftime('%Y-%m-%dT%H:%M:%SZ')
                spy_price = get_historical_minute_price("SPY", target_time)
                if spy_price is not None:
                    updates[spy_field] = spy_price
                    logger.info(f"[SPY] BULUNDU: {minutes}. Dakika Fiyatı -> ${spy_price}")
                    
        if record.get("spy_price_at_news") is None:
            spy_price_at_news = get_historical_minute_price("SPY", published_at)
            if spy_price_at_news is not None:
                updates["spy_price_at_news"] = spy_price_at_news
                logger.info(f"[SPY] BULUNDU: Anlık Fiyat -> ${spy_price_at_news}")
        
        if updates:
            collection.update_one({"_id": record["_id"]}, {"$set": updates})
            
    logger.info("Zaman Makinesi taraması tamamlandı!")

if __name__ == "__main__":
    main()