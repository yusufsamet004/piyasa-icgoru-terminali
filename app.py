import os
import ssl
import pandas as pd
import streamlit as st
import altair as alt
from pymongo.mongo_client import MongoClient
import certifi
from dotenv import load_dotenv

try:
    _create_unverified_https_context = ssl._create_unverified_context
except AttributeError:
    pass
else:
    ssl._create_default_https_context = _create_unverified_https_context

st.set_page_config(page_title="Piyasa İcgörü Terminali", layout="wide")

load_dotenv()
MONGO_URI = os.getenv("MONGO_URI")

@st.cache_data(ttl=300)
def get_data():
    if not MONGO_URI: return pd.DataFrame()
    try:
        client = MongoClient(MONGO_URI, tlsCAFile=certifi.where())
        collection = client.MarketDataDB.SentimentLogs
        cursor = collection.find({
            "$or": [{"price_15m": {"$ne": None}}, {"price_30m": {"$ne": None}}, {"price_60m": {"$ne": None}}]
        })
        data = list(cursor)
        if data:
            df = pd.DataFrame(data)
            df['_id'] = df['_id'].astype(str)
            return df
        return pd.DataFrame()
    except Exception as e:
        st.error(f"Veritabanı hatası: {e}")
        return pd.DataFrame()

st.title("Piyasa İçgörü Terminali")
st.markdown("Haber akışlarının hisse senedi fiyatları üzerindeki tarihsel etkisini ölçen analitik gösterge paneli.")
st.caption("Sinyal Kaynağı: FinBERT NLP Modeli | Yasal Uyarı: Yer alan veriler yatırım tavsiyesi değildir.")
st.divider()

df = get_data()

valid_df = df.copy()
if not valid_df.empty:
    valid_df['published_at'] = pd.to_datetime(valid_df['published_at'], utc=True)

st.sidebar.header("Araştırma Filtreleri")

if not valid_df.empty:
    all_tickers = ["Tümü"] + sorted(valid_df['ticker'].unique().tolist())
else:
    all_tickers = ["Tümü"]

selected_ticker = st.sidebar.selectbox("Hisse Senedi", all_tickers)

if not valid_df.empty:
    if selected_ticker == "Tümü":
        total_req = (len(all_tickers) - 1) * 125
        current = len(valid_df)
        if current < total_req:
            st.warning(f"**Kısıtlı Veri Uyarısı:** Terminalin tam tutarlılığa ulaşması için veritabanında toplam {total_req} haber bulunması önerilir. (Şu anki: {current}/{total_req}). Hedefe ulaşıldığında bu uyarı kalkacaktır.")
    else:
        current = len(valid_df[valid_df['ticker'] == selected_ticker])
        if current < 125:
            st.warning(f"**Kısıtlı Veri Uyarısı:** {selected_ticker} hissesi için tutarlı analizler yapabilmek adına en az 125 haber birikmesi önerilir. (Şu anki: {current}/125). Hedefe ulaşıldığında bu uyarı kalkacaktır.")

if df.empty:
    st.warning("Analiz edilecek veri bulunamadı.")
else:
    def categorize_signal(row):
        if 'sentiment_label' in row and pd.notna(row['sentiment_label']):
            label = row['sentiment_label']
            if label == 'positive': return "Pozitif"
            if label == 'negative': return "Negatif"
            return "Nötr"
        else:
            score = row['sentiment_score']
            if score >= 0.2: return "Pozitif"
            elif score <= -0.2: return "Negatif"
            else: return "Nötr"
            
    df['Sinyal'] = df.apply(categorize_signal, axis=1)
    
    
    if 'price_15m' in df.columns:
        df['15Dk_Degisim'] = ((df['price_15m'] - df['price_at_news']) / df['price_at_news']) * 100
        if 'spy_price_15m' in df.columns and 'spy_price_at_news' in df.columns:
            df['SPY_15Dk_Degisim'] = ((df['spy_price_15m'] - df['spy_price_at_news']) / df['spy_price_at_news']) * 100
            df['15Dk_Alpha'] = df['15Dk_Degisim'] - df['SPY_15Dk_Degisim']
            
    if 'price_30m' in df.columns:
        df['30Dk_Degisim'] = ((df['price_30m'] - df['price_at_news']) / df['price_at_news']) * 100
        if 'spy_price_30m' in df.columns and 'spy_price_at_news' in df.columns:
            df['SPY_30Dk_Degisim'] = ((df['spy_price_30m'] - df['spy_price_at_news']) / df['spy_price_at_news']) * 100
            df['30Dk_Alpha'] = df['30Dk_Degisim'] - df['SPY_30Dk_Degisim']
            
    if 'price_60m' in df.columns:
        df['60Dk_Degisim'] = ((df['price_60m'] - df['price_at_news']) / df['price_at_news']) * 100
        if 'spy_price_60m' in df.columns and 'spy_price_at_news' in df.columns:
            df['SPY_60Dk_Degisim'] = ((df['spy_price_60m'] - df['spy_price_at_news']) / df['spy_price_at_news']) * 100
            df['60Dk_Alpha'] = df['60Dk_Degisim'] - df['SPY_60Dk_Degisim']

    
    valid_df = df.copy()
    valid_df['published_at'] = pd.to_datetime(valid_df['published_at'], utc=True)
    
    time_filter = st.sidebar.radio("Haber Tarihi", ["Tümü", "Son 1 Hafta", "Son 1 Ay", "Son 3 Ay", "Son 6 Ay", "Son 1 Yıl"])
    
    analysis_timeframe = st.sidebar.radio(
        "Fiyat Etki Penceresi", 
        ["15 Dakikalık Reaksiyon", "30 Dakikalık Reaksiyon", "60 Dakikalık Reaksiyon"], 
        index=2,
        help="Haberin yayınlandığı andaki fiyat ile seçilen süre sonrasındaki fiyat arasındaki net yüzdelik değişimdir."
    )
    
    
    if analysis_timeframe == "15 Dakikalık Reaksiyon": 
        target_col = '15Dk_Degisim'
        alpha_col = '15Dk_Alpha'
    elif analysis_timeframe == "30 Dakikalık Reaksiyon": 
        target_col = '30Dk_Degisim'
        alpha_col = '30Dk_Alpha'
    else: 
        target_col = '60Dk_Degisim'
        alpha_col = '60Dk_Alpha'
    
    
    if target_col in valid_df.columns:
        filtered_df = valid_df.dropna(subset=[target_col]).copy()
    else:
        filtered_df = pd.DataFrame()
    
    if selected_ticker != "Tümü" and not filtered_df.empty:
        filtered_df = filtered_df[filtered_df['ticker'] == selected_ticker]
        
    now = pd.to_datetime("now", utc=True)
    if not filtered_df.empty:
        if time_filter == "Son 1 Hafta":
            filtered_df = filtered_df[filtered_df['published_at'] >= now - pd.Timedelta(weeks=1)]
        elif time_filter == "Son 1 Ay":
            filtered_df = filtered_df[filtered_df['published_at'] >= now - pd.Timedelta(days=30)]
        elif time_filter == "Son 3 Ay":
            filtered_df = filtered_df[filtered_df['published_at'] >= now - pd.Timedelta(days=90)]
        elif time_filter == "Son 6 Ay":
            filtered_df = filtered_df[filtered_df['published_at'] >= now - pd.Timedelta(days=180)]
        elif time_filter == "Son 1 Yıl":
            filtered_df = filtered_df[filtered_df['published_at'] >= now - pd.Timedelta(days=365)]
        
    if filtered_df.empty:
        st.info("Seçilen filtrelere uygun hesaplanmış veri bulunamadı. (Fiyatın güncellenmesi için zaman geçmesi gerekebilir).")
    else:
        st.subheader(f"Haber Etki Özeti ({selected_ticker} | {analysis_timeframe})", help="Seçilen zaman dilimi, haber yayınlandıktan tam X dakika sonrasını temsil eder.")
        
        col1, col2, col3, col4, col5 = st.columns(5)
        
        col1.metric("İncelenen Haber", len(filtered_df))
        
        pos_count = len(filtered_df[filtered_df['Sinyal'] == 'Pozitif'])
        col2.metric("Pozitif Sinyal", pos_count)
        
        neg_count = len(filtered_df[filtered_df['Sinyal'] == 'Negatif'])
        col3.metric("Negatif Sinyal", neg_count)
        
        notr_count = len(filtered_df[filtered_df['Sinyal'] == 'Nötr'])
        col4.metric("Nötr Sinyal", notr_count)
        
        if alpha_col in filtered_df.columns:
            avg_alpha = filtered_df[alpha_col].mean()
            col5.metric("S&P 500'e Göre Fark", f"%{avg_alpha:.2f}", help="Hissenin piyasaya (S&P 500) kıyasla nasıl bir performans gösterdiğini ölçer. Sayı pozitifse (+), hisse piyasadan daha çok kazandırmıştır. Negatifse (-), piyasanın gerisinde kalmıştır.")
        else:
            col5.metric("S&P 500'e Göre Fark", "Veri Yok")
        
        st.divider()
        
        st.subheader("Finansal İçgörü Özeti")
        
        total_directional = pos_count + neg_count
        avg_returns = filtered_df.groupby('Sinyal').agg(
            Ortalama_Degisim=(target_col, 'mean'),
            Adet=(target_col, 'count')
        ).reset_index()
        
        if total_directional > 0:
            pos_return = avg_returns[avg_returns['Sinyal'] == 'Pozitif']['Ortalama_Degisim'].values
            neg_return = avg_returns[avg_returns['Sinyal'] == 'Negatif']['Ortalama_Degisim'].values
            
            pos_val = float(pos_return[0]) if len(pos_return) > 0 else 0.0
            neg_val = float(neg_return[0]) if len(neg_return) > 0 else 0.0

            time_text = time_filter if time_filter != "Tümü" else "Tüm zamanlar"
            
            if selected_ticker == "Tümü":
                ticker_stats = filtered_df.groupby(['ticker', 'Sinyal'])[target_col].mean().unstack()
                contrarian_tickers = []
                linear_tickers = []
                for t in ticker_stats.index:
                    p = ticker_stats.loc[t, 'Pozitif'] if 'Pozitif' in ticker_stats.columns else 0
                    n = ticker_stats.loc[t, 'Negatif'] if 'Negatif' in ticker_stats.columns else 0
                    if pd.notna(p) and pd.notna(n):
                        if (p < 0 and n > 0) or (p < 0 and n < 0 and p < n):
                            contrarian_tickers.append(t)
                        elif p > 0 and n < 0:
                            linear_tickers.append(t)
                mixed_tickers = [t for t in ticker_stats.index if t not in contrarian_tickers and t not in linear_tickers]
                
                insight_text = f"**Portföy Dağılımı ({time_text}):**\n\n"
                
                if contrarian_tickers:
                    insight_text += f"- **Tersine Korelasyon (Contrarian):** {', '.join(contrarian_tickers)} (Haber yönü ile fiyat hareketi zıt yönlü. Önceden fiyatlanma ihtimali yüksek.)\n"
                if linear_tickers:
                    insight_text += f"- **Doğrusal Korelasyon:** {', '.join(linear_tickers)} (Haber yönü ile fiyat hareketi tam uyumlu.)\n"
                if mixed_tickers:
                    insight_text += f"- **Karmaşık Etki:** {', '.join(mixed_tickers)} (Piyasa trendi haberden daha baskın.)"
                    
                st.info(insight_text)
            else:
                if pos_val < 0 and neg_val > 0:
                    insight_text = f"**Tersine Korelasyon (Contrarian):** 'Pozitif' haberde %{pos_val:.2f} düşmüş, 'Negatif' haberde %{neg_val:.2f} yükselmiş. Hisse haberlere ZIT tepki veriyor."
                    st.warning(insight_text)
                elif pos_val > 0 and neg_val < 0:
                    insight_text = f"**Doğrusal Korelasyon:** 'Pozitif' haberde %{pos_val:.2f} yükselmiş, 'Negatif' haberde %{neg_val:.2f} düşmüş. Hisse haberlerle UYUMLU hareket ediyor."
                    st.success(insight_text)
                else:
                    insight_text = f"**Karmaşık Korelasyon:** Pozitif etki %{pos_val:.2f}, Negatif etki %{neg_val:.2f}. Piyasanın genel yönü, haberin önüne geçmiş olabilir."
                    st.info(insight_text)
        else:
            st.info(f"Yeterli veri hacmi sağlanamadı ({time_filter}).")
            
        st.divider()
        
        st.subheader(f"Kararlara Göre Ortalama Getiri ({analysis_timeframe})")
        st.markdown("Haberin karar yönüne (Pozitif / Negatif) göre hisselerdeki ortalama fiyat değişimi.")
        
        color_scale = alt.Scale(
            domain=['Pozitif', 'Negatif', 'Nötr'],
            range=['#2ecc71', '#e74c3c', '#95a5a6']
        )
        
        bar_chart = alt.Chart(avg_returns).mark_bar(size=80).encode(
            x=alt.X('Sinyal:N', title='Yapay Zeka Kararı', sort=['Pozitif', 'Nötr', 'Negatif']),
            y=alt.Y('Ortalama_Degisim:Q', title=f'Ortalama Fiyat Değişimi (%)'),
            color=alt.Color('Sinyal:N', scale=color_scale, legend=None),
            tooltip=[alt.Tooltip('Sinyal:N', title='Karar'), alt.Tooltip('Ortalama_Degisim:Q', title='Ortalama Değişim (%)', format='.2f'), alt.Tooltip('Adet:Q', title='Haber Sayısı')]
        ).properties(height=350).interactive()
        
        zero_rule = alt.Chart(pd.DataFrame({'y': [0]})).mark_rule(color='gray', strokeDash=[5, 5]).encode(y='y:Q')
        
        st.altair_chart(bar_chart + zero_rule, use_container_width=True)
        
        st.divider()
        
        st.subheader("Portföy ve Sinyal Dağılımı")
        st.markdown("Haberlerin hisseler üzerindeki sinyal dağılımı ve hisse bazlı ortalama fiyat etkileri.")
        
        col_chart1, col_chart2 = st.columns(2)
        
        with col_chart1:
            st.markdown("**Sinyal Dağılımı (Adet)**")
            signal_counts = filtered_df['Sinyal'].value_counts().reset_index()
            signal_counts.columns = ['Sinyal', 'Adet']
            
            donut_chart = alt.Chart(signal_counts).mark_arc(innerRadius=50).encode(
                theta=alt.Theta(field="Adet", type="quantitative"),
                color=alt.Color(field="Sinyal", type="nominal", scale=color_scale, legend=alt.Legend(title="Sinyal")),
                tooltip=['Sinyal', 'Adet']
            ).properties(height=350).interactive()
            st.altair_chart(donut_chart, use_container_width=True)
            
        with col_chart2:
            st.markdown("**Hisse Bazlı Ortalama Etki (%)**")
            ticker_returns = filtered_df.groupby(['ticker', 'Sinyal']).agg(
                Ortalama_Degisim=(target_col, 'mean'),
                Adet=(target_col, 'count')
            ).reset_index()
            
            
            all_combos = pd.MultiIndex.from_product(
                [filtered_df['ticker'].unique(), ['Pozitif', 'Nötr', 'Negatif']],
                names=['ticker', 'Sinyal']
            ).to_frame(index=False)
            
            ticker_returns = pd.merge(all_combos, ticker_returns, on=['ticker', 'Sinyal'], how='left').fillna({'Ortalama_Degisim': 0, 'Adet': 0})
            
            ticker_bar_chart = alt.Chart(ticker_returns).mark_bar(cornerRadiusTopLeft=3, cornerRadiusTopRight=3, size=20).encode(
                x=alt.X('ticker:N', title='Hisse', axis=alt.Axis(labelAngle=0)),
                y=alt.Y('Ortalama_Degisim:Q', title='Ortalama Değişim (%)'),
                color=alt.Color('Sinyal:N', scale=color_scale, legend=alt.Legend(title="Karar")),
                xOffset=alt.XOffset('Sinyal:N', sort=['Pozitif', 'Nötr', 'Negatif']),
                tooltip=['ticker', 'Sinyal', alt.Tooltip('Ortalama_Degisim:Q', title='Ortalama Değişim (%)', format='.2f'), alt.Tooltip('Adet:Q', title='Haber Sayısı')]
            ).properties(height=350).interactive()
            
            st.altair_chart(ticker_bar_chart, use_container_width=True)
            
        st.divider()

        st.subheader("Finansal Analiz Tablosu")
        st.markdown("""
        **Tablo Terimleri:**
        - **(Başlık Yok):** Haber başlığı yerine metnin gövdesinin (tamamının) analiz edildiğini belirtir.
        - **Karar:** Yapay zekanın haber metninden çıkardığı yön kararıdır (Pozitif, Negatif, Nötr).
        - **Model Güven Skoru:** Yapay zekanın kendi verdiği karardan ne kadar emin olduğunu gösterir (0 ile 1 arası).
        - **Duygu Skoru:** Haber metnindeki duygunun şiddetini gösterir (-1 aşırı negatif, +1 aşırı pozitif).
        - **Değişim (%):** Haberin çıktığı an ile seçilen süre (örneğin 15 dk) sonrasındaki gerçek fiyat değişimidir.
        - **S&P 500'e Göre Fark:** Hissenin getirisinden genel Amerikan piyasasının (S&P 500) getirisinin çıkarılmasıyla bulunur. Saf başarıyı gösterir.
        """)
        
        display_cols = ['ticker', 'published_at', 'title', 'Sinyal', 'sentiment_score']
        
        if 'sentiment_probability' in filtered_df.columns:
            display_cols.insert(4, 'sentiment_probability')
            
        display_cols.extend(['price_at_news', '15Dk_Degisim', '30Dk_Degisim', '60Dk_Degisim'])
        
        
        display_cols = [c for c in display_cols if c in display_cols and c in filtered_df.columns]
        
        display_df = filtered_df[display_cols].copy()
        display_df['title'] = display_df['title'].fillna("(Başlık Yok)")
        
        
        display_df['published_at'] = display_df['published_at'].dt.strftime('%Y-%m-%d %H:%M')
        if 'sentiment_probability' in display_df.columns:
            display_df['sentiment_probability'] = display_df['sentiment_probability'].apply(lambda x: f"%{x*100:.1f}" if pd.notnull(x) else "-")
            
        for col in ['sentiment_score', '15Dk_Degisim', '30Dk_Degisim', '60Dk_Degisim']:
            if col in display_df.columns:
                display_df[col] = display_df[col].apply(lambda x: f"{x:.2f}" if pd.notnull(x) else "-")
        
        display_df.rename(columns={
            'ticker': 'Hisse', 'published_at': 'Tarih', 'title': 'Haber Başlığı',
            'sentiment_probability': 'Model Güven Skoru', 'sentiment_score': 'Duygu Skoru',
            'price_at_news': 'Haber Fiyatı ($)', '15Dk_Degisim': '15Dk Değişim (%)',
            '30Dk_Degisim': '30Dk Değişim (%)', '60Dk_Degisim': '60Dk Değişim (%)'
        }, inplace=True)
        
        st.dataframe(
            display_df, 
            use_container_width=True,
            hide_index=True
        )