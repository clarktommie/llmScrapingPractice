# ---
# Streamlit Book Browser (Modal-ready)
# ---

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

    # --- Fetch latest books ordered by updated_at ---
    response = (
        supabase.table("books")
        .select("*")
        .order("updated_at", desc=True)
        .execute()
    )
    books = response.data or []

    if not books:
        st.warning("No books in Supabase. Run loader script first.")
        return

    # --- Convert to DataFrame ---
    df = pd.DataFrame(books)

    # Ensure TIMESTAMPTZ field exists
    if "updated_at" in df.columns:
        df["updated_at"] = pd.to_datetime(df["updated_at"])

    # --- Rating mapping ---
    rating_map = {"One": 1, "Two": 2, "Three": 3, "Four": 4, "Five": 5}
    if "rating" in df.columns:
        df["rating_num"] = df["rating"].map(rating_map)

    # --- Sidebar filters ---
    st.sidebar.header("🔍 Filters")
    titles = ["All"] + df["title"].dropna().tolist()
    selected_title = st.sidebar.selectbox("Select a book", titles)

    # --- Display book cards ---
    for _, book in df.iterrows():
        if selected_title != "All" and book["title"] != selected_title:
            continue

        st.markdown(f"### {book['title']}")
        cols = st.columns(3)
        cols[0].metric("Price", book.get("price", "N/A"))
        cols[1].metric("Availability", book.get("availability", "N/A"))

        stars = "⭐" * int(book.get("rating_num", 0)) if pd.notna(book.get("rating_num")) else "N/A"
        cols[2].metric("Rating", f"{stars} ({book['rating_num']}/5)" if stars != "N/A" else "N/A")

        if "summary" in book and book["summary"]:
            with st.expander("📖 AI Summary"):
                st.write(book["summary"])

        if "updated_at" in book:
            st.caption(f"Last updated: {book['updated_at']}")

        st.divider()

    # --- Visualizations ---
    st.subheader("📊 Data Overview")

    if "rating_num" in df.columns:
        avg_rating = df["rating_num"].mean()
        st.metric("⭐ Average Rating", f"{avg_rating:.2f} / 5")

        fig_rating = px.histogram(
            df, x="rating_num", nbins=5, title="Book Rating Distribution (1–5 Stars)"
        )
        st.plotly_chart(fig_rating, use_container_width=True)

    if "price" in df.columns:
        df["price_num"] = df["price"].str.replace("£", "").astype(float)
        fig_price = px.histogram(
            df, x="price_num", nbins=10, title="Book Price Distribution (£)"
        )
        st.plotly_chart(fig_price, use_container_width=True)

    if "availability" in df.columns:
        df["in_stock"] = df["availability"].str.contains("In stock", case=False, na=False)
        stock_counts = df["in_stock"].value_counts().reset_index()
        stock_counts.columns = ["in_stock", "count"]
        stock_counts["in_stock"] = stock_counts["in_stock"].map({True: "In Stock", False: "Out of Stock"})
        fig_stock = px.pie(stock_counts, values="count", names="in_stock", title="Availability Breakdown")
        st.plotly_chart(fig_stock, use_container_width=True)

    # --- Raw Data Table ---
    st.subheader("📋 Raw Data Table")
    st.dataframe(df[["title", "price", "availability", "rating_num", "summary", "updated_at"]])


# --- Entrypoint ---
if __name__ == "__main__":
    main()
