import os
import json
import re
import time
from urllib.parse import urljoin
from requests import Session
from bs4 import BeautifulSoup
import pandas as pd
from openai import OpenAI

# --- OpenAI Setup (replace with env var in production) ---
endpoint = "https://cdong1--azure-proxy-web-app.modal.run"
api_key = "supersecretkey"  # <-- replace with os.getenv("OPENAI_API_KEY")
deployment_name = "gpt-4o"
client = OpenAI(base_url=endpoint, api_key=api_key)

# --- Requests session for efficiency ---
session = Session()
session.headers.update({'User-Agent': 'Mozilla/5.0'})

# --- Scraper Functions (keeps your extraction logic, improved URL building) ---
def scrape_book_info(url):
    try:
        response = session.get(url, timeout=10)
        response.raise_for_status()
    except Exception as e:
        print(f"Failed to fetch {url}: {e}")
        return None

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
    try:
        response = session.get(url, timeout=10)
        response.raise_for_status()
    except Exception as e:
        print(f"Failed to fetch category page {url}: {e}")
        return []

    soup = BeautifulSoup(response.content, 'html.parser')

    books = []
    for article in soup.find_all('article', class_='product_pod'):
        href = article.find('h3').find('a')['href']
        book_url = urljoin(url, href)  # safer absolute URL building
        info = scrape_book_info(book_url)
        if info:
            books.append(info)
        # small polite delay to avoid hammering the site
        time.sleep(0.1)
    return books


# --- Local fallback helpers (price cleaning & rating mapping) ---
def clean_price_local(price_str):
    if not price_str:
        return None
    # Capture numeric portion like 51.77 or 51,77
    m = re.search(r"([0-9]+(?:[.,][0-9]{1,2})?)", price_str.replace(",", ""))
    if not m:
        return None
    try:
        return float(m.group(1).replace(",", ""))
    except Exception:
        return None

RATING_MAP = {
    "One": 1, "Two": 2, "Three": 3, "Four": 4, "Five": 5,
    "one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
    "1": 1, "2": 2, "3": 3, "4": 4, "5": 5
}

def rating_word_to_num_local(rating):
    if rating is None:
        return None
    return RATING_MAP.get(rating, None)


# --- LLM wrapper expecting JSON (uses your prompt) ---
SYSTEM_PROMPT = "You are a concise assistant. Return ONLY valid JSON with no extra text."

def call_llm_for_book(book: dict, max_retries: int = 2):
    """
    Sends structured book dict to the LLM and expects valid JSON:
    { "summary": <str>, "price_clean": <float|null>, "rating_numeric": <int|null> }
    Returns normalized dict with safe fallbacks applied.
    """
    user_prompt = (
        "Input: a JSON object with keys: Title, Price, Availability, Rating.\n"
        "Return valid JSON (no extra text) with keys: summary, price_clean, rating_numeric.\n"
        " - summary: 1-2 sentence product summary suitable for a catalog (use ONLY the supplied fields).\n"
        " - price_clean: numeric price as float.\n"
        " - rating_numeric: integer 1-5 corresponding to the star-rating.\n"
        "Do NOT invent facts beyond the provided fields. Output only parsable JSON.\n\n"
        f"Input JSON:\n{json.dumps(book, ensure_ascii=False)}"
    )

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_prompt}
    ]

    attempt = 0
    while attempt <= max_retries:
        try:
            resp = client.chat.completions.create(
                model=deployment_name,
                messages=messages,
                temperature=0.2,  # low for consistency
                max_tokens=150
            )
            text = resp.choices[0].message.content.strip()
            parsed = json.loads(text)  # expect valid JSON only

            summary = parsed.get("summary", "")
            price_clean = parsed.get("price_clean", None)
            rating_numeric = parsed.get("rating_numeric", None)

            # Validate/coerce or fallback to local parsing
            if price_clean is None:
                price_clean = clean_price_local(book.get("Price"))
            else:
                try:
                    price_clean = float(price_clean)
                except Exception:
                    price_clean = clean_price_local(book.get("Price"))

            if rating_numeric is None:
                rating_numeric = rating_word_to_num_local(book.get("Rating"))
            else:
                try:
                    rating_numeric = int(rating_numeric)
                except Exception:
                    rating_numeric = rating_word_to_num_local(book.get("Rating"))

            return {
                "summary": summary if summary is not None else "",
                "price_clean": price_clean,
                "rating_numeric": rating_numeric
            }

        except json.JSONDecodeError:
            # model didn't return valid JSON — retry a bit
            attempt += 1
            time.sleep(0.6 * attempt)
            continue
        except Exception as e:
            # API/network error — retry with backoff
            attempt += 1
            time.sleep(0.6 * attempt)
            if attempt > max_retries:
                # final deterministic fallback
                return {
                    "summary": "",
                    "price_clean": clean_price_local(book.get("Price")),
                    "rating_numeric": rating_word_to_num_local(book.get("Rating"))
                }


# --- Main Logic: scrape category, enrich with LLM, save CSV ---
if __name__ == "__main__":
    category_url = "https://books.toscrape.com/catalogue/category/books/travel_2/index.html"
    all_books = scrape_category_page(category_url)

    enriched_books = []
    for book in all_books:
        # call LLM to get summary + cleaned price + numeric rating
        llm_out = call_llm_for_book(book)
        enriched = {**book, **llm_out}
        enriched_books.append(enriched)
        # polite delay to avoid hitting rate limits
        time.sleep(0.25)

    # create DataFrame and save
    df = pd.DataFrame(enriched_books)
    df.to_csv("books_with_summaries.csv", index=False)
    print(df.head())
