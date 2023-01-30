import requests

def request_quote():
    url = "https://api.forismatic.com/api/1.0/?method=getQuote&lang=en&format=json"
    response = requests.get(url)

    if response.status_code == 200:
        data = response.json()
        quote = data.get("quoteText")
        print(quote)
    else:
        print("Failed to get quote")

def main():
    request_quote()