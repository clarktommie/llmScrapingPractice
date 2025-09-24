import requests
from bs4 import BeautifulSoup
import pandas as pd
from openai import OpenAI

# --- OpenAI Setup ---
endpoint = "https://cdong1--azure-proxy-web-app.modal.run"
api_key = "supersecretkey"
deployment_name = "gpt-4o"

client = OpenAI(base_url=endpoint, api_key=api_key)

# --- Scraper Functions ---
def scrape_book_info(url):
    headers = {'User-Agent': 'Mozilla/5.0'}
    response = requests.get(url, headers=headers)
    soup = BeautifulSoup(response.content, 'html.parser')

    book_info = {
        'Title': None,
        'Price': None,
        'Availability': None,
        'Rating': None
    }

    title = soup.find('h1')
    if title:
        book_info['Title'] = title.text.strip()

    price = soup.find('p', class_='price_color')
    if price:
        book_info['Price'] = price.text.strip()

    availability = soup.find('p', class_='instock availability')
    if availability:
        book_info['Availability'] = availability.get_text(strip=True)

    rating = soup.find('p', class_='star-rating')
    if rating and 'class' in rating.attrs:
        classes = rating['class']
        if len(classes) > 1:
            book_info['Rating'] = classes[1]

    return book_info


def scrape_category_page(url):
    headers = {'User-Agent': 'Mozilla/5.0'}
    response = requests.get(url, headers=headers)
    soup = BeautifulSoup(response.content, 'html.parser')

    books = []
    for article in soup.find_all('article', class_='product_pod'):
        link = article.find('h3').find('a')['href']
        book_url = "https://books.toscrape.com/catalogue/" + link.replace('../../../', '')
        books.append(scrape_book_info(book_url))
    return books


# --- Main Logic ---
category_url = "https://books.toscrape.com/catalogue/category/books/travel_2/index.html"
all_books = scrape_category_page(category_url)

# Generate summaries for each book
summaries = []
for book in all_books:
    response = client.chat.completions.create(
        model=deployment_name,
        messages=[
            {"role": "system", "content": "You are a helpful assistant that summarizes book product information."},
            {"role": "user", "content": f"Book Info: {book}"}
        ],
        temperature=0.7
    )
    summaries.append(response.choices[0].message.content)

# --- Create DataFrame ---
df = pd.DataFrame(all_books)
df["Summary"] = summaries

print(df.head())   # preview in terminal
df.to_csv("books_with_summaries.csv", index=False)  # save to CSV
