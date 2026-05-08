from screener.data_fetcher import fetch_ticker

data = fetch_ticker("AAPL")
if data:
    print(data["price"], data["pe"])
else:
    print("Erreur récupération")