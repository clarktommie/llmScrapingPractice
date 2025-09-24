# ---
# lambda-test: false  # auxiliary-file
# ---
# ## Book Browser Streamlit Application
#
# This app pulls book data (scraped + summarized) from Supabase
# and displays it in Streamlit with filters and visualizations.

def main():
    import os
    from dotenv import load_dotenv
    from supabase import create_client
    import pandas as pd
    import plotly.express as px
    import streamlit as st

    # --- Load Supabase ---
    load_dotenv()
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_KEY")
    supabase = create_client(url, key)

    st.set_page_config(page_title="Book Browser", page_icon="📚", layout="wide")
    st.title("📚 Book Browser by Tommie Clark")

    # Fetch books from Supabase
    response = supabase.table("books").select("*").execute()
    books = response.data or []

    if not books:
        st.warning("No books in Supabase. Run llmPractice.py first.")
        return

    # Convert to DataFrame
    df = pd.DataFrame(books)

    # Map rating words -> numbers
    rating_map = {"One": 1, "Two": 2, "Three": 3, "Four": 4, "Five": 5}
    df["rating_num"] = df["rating"].map(rating_map)

    # Sidebar filters
    st.sidebar.header("🔍 Filters")
    titles = ["All"] + df["title"].dropna().tolist()
    selected_title = st.sidebar.selectbox("Select a book", titles)

    # Display books
    for _, book in df.iterrows():
        if selected_title != "All" and book["title"] != selected_title:
            continue

        st.markdown(f"### {book['title']}")
        cols = st.columns(3)
        cols[0].metric("Price", book.get("price", "N/A"))
        cols[1].metric("Availability", book.get("availability", "N/A"))

        # ⭐ Show stars instead of "Three"
        stars = "⭐" * int(book["rating_num"]) if pd.notna(book["rating_num"]) else "N/A"
        cols[2].metric("Rating", f"{stars} ({book['rating_num']}/5)" if stars != "N/A" else "N/A")

        if "summary" in book and book["summary"]:
            with st.expander("📖 AI Summary"):
                st.write(book["summary"])

        st.divider()

    # --- Visualizations ---
    st.subheader("📊 Data Overview")

    # Average rating
    avg_rating = df["rating_num"].mean()
    st.metric("⭐ Average Rating", f"{avg_rating:.2f} / 5")

    # Rating distribution
    fig_rating = px.histogram(
        df,
        x="rating_num",
        nbins=5,
        title="Book Rating Distribution (1–5 Stars)"
    )
    fig_rating.update_layout(
        xaxis_title="Rating (Stars)",
        yaxis_title="Count",
        xaxis=dict(tickmode="array", tickvals=[1, 2, 3, 4, 5])
    )
    st.plotly_chart(fig_rating, use_container_width=True)

    # Price distribution (strip £ and convert to float)
    if "price" in df.columns:
        df["price_num"] = df["price"].str.replace("£", "").astype(float)
        fig_price = px.histogram(
            df,
            x="price_num",
            nbins=10,
            title="Book Price Distribution (£)"
        )
        st.plotly_chart(fig_price, use_container_width=True)

    # Availability breakdown
    if "availability" in df.columns:
        df["in_stock"] = df["availability"].str.contains("In stock", case=False, na=False)
        stock_counts = df["in_stock"].value_counts().reset_index()
        stock_counts.columns = ["in_stock", "count"]
        stock_counts["in_stock"] = stock_counts["in_stock"].map({True: "In Stock", False: "Out of Stock"})
        fig_stock = px.pie(
            stock_counts,
            values="count",
            names="in_stock",
            title="Availability Breakdown"
        )
        st.plotly_chart(fig_stock, use_container_width=True)

    # Raw data table
    st.subheader("📋 Raw Data Table")
    st.dataframe(df[["title", "price", "availability", "rating_num", "summary"]])


# --- Entrypoint ---
if __name__ == "__main__":
    main()
