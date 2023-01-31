import json
import time
import requests

def request_quote():
    url = "https://api.forismatic.com/api/1.0/?method=getQuote&lang=en&format=json"
    response = requests.get(url)

    if response.status_code == 200:
        try:
            data = response.json()
            quote = data.get("quoteText")
            print(quote)
        except json.decoder.JSONDecodeError:
            time.sleep(0.5)
            request_quote()
    else:
        print("Failed to get quote")

def main():
    request_quote()

main()