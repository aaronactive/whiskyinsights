import streamlit as st
import duckdb
import pandas as pd
import altair as alt

DB_FILE = "whisky.db"

st.set_page_config(layout="wide")
st.title("🥃 Whisky Auction Overview")

# =========================
# FIX METRIC SIZE
# =========================
st.markdown("""
<style>
div[data-testid="stMetric"] {
    font-size: 0.8rem;
}
div[data-testid="stMetricValue"] {
    font-size: 1.3rem;
}
</style>
""", unsafe_allow_html=True)

# =========================
# DB
# =========================
@st.cache_resource
def get_connection():
    return duckdb.connect(DB_FILE)

con = get_connection()

# =========================
# LOAD DATA
# =========================
@st.cache_data
def load_data():
    return con.execute("SELECT * FROM auctions").fetchdf()

df = load_data()

# =========================
# CLEAN
# =========================
df["sold_date"] = pd.to_datetime(df["sold_date"])
df["month"] = df["sold_date"].dt.to_period("M").dt.to_timestamp()

# =========================
# MONTHLY + TOP 5
# =========================
monthly = df.groupby("month")["price"].sum().reset_index()

top_rows = []

for month in monthly["month"]:
    top5 = (
        df[df["month"] == month]
        .sort_values("price", ascending=False)
        .head(5)
    )

    row = {"month": month}

    for i, (_, r) in enumerate(top5.iterrows(), start=1):
        row[f"top{i}"] = f"{r['name'][:25]} (${r['price']:,.0f})"

    top_rows.append(row)

top_df = pd.DataFrame(top_rows)
monthly = monthly.merge(top_df, on="month", how="left")

# =========================
# LAYOUT
# =========================
left, right = st.columns([1, 1])

# =====================================
# LEFT — OVERALL
# =====================================
with left:
    st.header("📊 Overall Summary")

    total_sales = df["price"].sum()
    total_bottles = df["bottle_count"].sum()
    avg_per_bottle = total_sales / total_bottles if total_bottles else 0

    c1, c2, c3 = st.columns(3)

    c1.metric("Total Sales", f"${total_sales:,.0f}")
    c2.metric("Bottles Tracked", f"{int(total_bottles):,}")
    c3.metric("Avg Bottle", f"${avg_per_bottle:,.0f}")

    # =========================
    # SALES BY MONTH
    # =========================
    st.subheader("📈 Sales by Month")

    chart = alt.Chart(monthly).mark_line(point=True).encode(
        x=alt.X("month:T", title="Month"),
        y=alt.Y("price:Q", title="Total Sales"),
        tooltip=[
            alt.Tooltip("month:T", title="Month"),
            alt.Tooltip("price:Q", title="Sales", format=",.0f"),
            alt.Tooltip("top1:N", title="Top 1"),
            alt.Tooltip("top2:N", title="Top 2"),
            alt.Tooltip("top3:N", title="Top 3"),
            alt.Tooltip("top4:N", title="Top 4"),
            alt.Tooltip("top5:N", title="Top 5"),
        ]
    ).properties(height=300)

    st.altair_chart(chart, width="stretch")

# =====================================
# RIGHT — COMPARISON (RESTORED)
# =====================================
with right:
    st.header("🔍 Compare Whisky")

    colA, colB = st.columns(2)

    search_a = colA.text_input("Search A")
    search_b = colB.text_input("Search B")

    def match_search(name, search):
        words = search.lower().split()
        name = name.lower()
        return all(word in name for word in words)

    def clean_label(text, max_len=25):
        text = text.title().strip()
        return text[:max_len] + "..." if len(text) > max_len else text

    def process_search(search):
        if not search:
            return None

        filtered = df[df["name"].apply(lambda x: match_search(x, search))]

        if filtered.empty:
            return None

        total_sales = filtered["price"].sum()
        total_bottles = filtered["bottle_count"].sum()
        avg = total_sales / total_bottles if total_bottles else 0

        trend = filtered.groupby("month").agg(
            avg_price=("price", "mean")
        ).reset_index()

        return {
            "sales": total_sales,
            "bottles": total_bottles,
            "avg": avg,
            "trend": trend
        }

    data_a = process_search(search_a)
    data_b = process_search(search_b)

    label_a = clean_label(search_a) if search_a else "Search A"
    label_b = clean_label(search_b) if search_b else "Search B"

    # =========================
    # METRICS
    # =========================
    if data_a or data_b:
        st.subheader("📊 Comparison")

        m1, m2 = st.columns(2)

        if data_a:
            m1.metric(f"Sales ({label_a})", f"${data_a['sales']:,.0f}")
            m1.metric(f"Bottles ({label_a})", f"{int(data_a['bottles']):,}")
            m1.metric(f"Avg ({label_a})", f"${data_a['avg']:,.0f}")

        if data_b:
            m2.metric(f"Sales ({label_b})", f"${data_b['sales']:,.0f}")
            m2.metric(f"Bottles ({label_b})", f"{int(data_b['bottles']):,}")
            m2.metric(f"Avg ({label_b})", f"${data_b['avg']:,.0f}")

    # =========================
    # TREND CHART (COLOURED)
    # =========================
    st.subheader("📈 Price Trend Comparison")

    chart_df = pd.DataFrame()

    if data_a:
        df_a = data_a["trend"].copy()
        df_a["label"] = label_a
        chart_df = df_a

    if data_b:
        df_b = data_b["trend"].copy()
        df_b["label"] = label_b
        chart_df = pd.concat([chart_df, df_b]) if not chart_df.empty else df_b

    if not chart_df.empty:
        chart = alt.Chart(chart_df).mark_line(point=True).encode(
            x="month:T",
            y="avg_price:Q",
            color=alt.Color(
                "label:N",
                scale=alt.Scale(
                    domain=[label_a, label_b],
                    range=["#1f77b4", "#ff7f0e"]
                ),
                legend=alt.Legend(title="Search")
            ),
            tooltip=["month:T", "label:N", "avg_price:Q"]
        ).properties(height=300)

        st.altair_chart(chart, width="stretch")
