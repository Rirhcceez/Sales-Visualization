import streamlit as st
import pandas as pd
import plotly.express as px
from sqlalchemy import create_engine

# --- 1. SETUP & CONNECTION ---
st.set_page_config(page_title="Sales Analytics", layout="wide")

@st.cache_resource
def get_connection():
    db_config = st.secrets["connections"]["postgresql"]
    url = f"postgresql+psycopg2://{db_config['username']}:{db_config['password']}@{db_config['host']}:{db_config['port']}/{db_config['database']}"
    return create_engine(url)

engine = get_connection()

# --- 2. LOAD DATA (Smart Query) ---
# We fetch everything at the "Order Level" first to make basket analysis easy
def load_analytics_data():
    query = """
    SELECT 
        o.order_id,
        o.platform_name,
        o.order_date,
        -- Correct the Timezone if needed (Postgres defaults to UTC usually)
        o.total_amount as order_value,
        COUNT(oi.id) as unique_items,
        SUM(oi.quantity) as total_units
    FROM sales.orders o
    LEFT JOIN sales.order_items oi ON o.order_id = oi.order_id
    GROUP BY o.order_id, o.platform_name, o.order_date, o.total_amount
    ORDER BY o.order_date DESC
    """
    df = pd.read_sql(query, engine)
    df['order_date'] = pd.to_datetime(df['order_date'])
    return df

try:
    df = load_analytics_data()
except Exception as e:
    st.error(f"Could not load data. Have you imported orders yet? Error: {e}")
    st.stop()

if df.empty:
    st.warning("No sales data found. Please go to the Import page first.")
    st.stop()

# --- 3. SIDEBAR FILTERS ---
st.sidebar.header("Filters")
# Date Filter
min_date = df['order_date'].min()
max_date = df['order_date'].max()
date_range = st.sidebar.date_input("Date Range", [min_date, max_date])

# Platform Filter
selected_platform = st.sidebar.multiselect(
    "Platform", df['platform_name'].unique(), default=df['platform_name'].unique()
)

# Apply Filters
mask = (df['order_date'].dt.date >= date_range[0]) & \
       (df['order_date'].dt.date <= date_range[1]) & \
       (df['platform_name'].isin(selected_platform))
df_filtered = df[mask]

# --- 4. TOP KPI ROW ---
st.title("💰 Sales & Basket Analytics")
st.markdown("---")

total_revenue = df_filtered['order_value'].sum()
total_orders = len(df_filtered)
# AOV: Average Order Value (Basket Value)
aov = total_revenue / total_orders if total_orders > 0 else 0
# UPT: Units Per Transaction (Basket Size)
upt = df_filtered['total_units'].sum() / total_orders if total_orders > 0 else 0

col1, col2, col3, col4 = st.columns(4)
col1.metric("Total Revenue", f"{total_revenue:,.0f} THB")
col2.metric("Total Orders", f"{total_orders:,}")
col3.metric("AOV (Avg. Value)", f"{aov:,.0f} THB", help="Average money spent per order")
col4.metric("UPT (Avg. Units)", f"{upt:.1f} Items", help="Average physical items per order")

st.markdown("---")

# --- 5. VISUALIZATIONS ---

# ROW A: SALES TREND (Line Chart)
st.subheader("📈 Revenue Trend over Time")
# Group by Day (D) or Month (M) or Week (W)
freq = st.radio("Group By:", ["Daily", "Weekly"], horizontal=True)
freq_code = 'D' if freq == "Daily" else 'W'

sales_trend = df_filtered.set_index('order_date').resample(freq_code)['order_value'].sum().reset_index()

fig_sales = px.line(
    sales_trend, 
    x='order_date', 
    y='order_value', 
    markers=True,
    title=f"Total Sales ({freq})",
    labels={'order_value': 'Revenue (THB)', 'order_date': 'Date'}
)
st.plotly_chart(fig_sales, use_container_width=True)

# ROW B: BASKET SIZE DEEP DIVE
col_left, col_right = st.columns(2)

with col_left:
    st.subheader("🛒 Basket Value Distribution")
    # Histogram: How much do people usually spend?
    # This helps you define "Small", "Medium", and "Whale" customers
    fig_hist = px.histogram(
        df_filtered, 
        x="order_value", 
        nbins=20,
        color="platform_name",
        title="Distribution of Order Values (AOV)",
        labels={'order_value': 'Order Value (THB)'}
    )
    st.plotly_chart(fig_hist, use_container_width=True)

with col_right:
    st.subheader("📦 Items per Order (UPT)")
    # Bar Chart: Do people buy 1 item or 5 items?
    upt_counts = df_filtered['total_units'].value_counts().reset_index()
    upt_counts.columns = ['items_in_basket', 'order_count']
    
    fig_upt = px.bar(
        upt_counts, 
        x='items_in_basket', 
        y='order_count',
        text='order_count',
        title="How many items do customers buy at once?",
        labels={'items_in_basket': 'Number of Items', 'order_count': 'Count of Orders'}
    )
    st.plotly_chart(fig_upt, use_container_width=True)

# ROW C: SCATTER PLOT (Correlation)
st.subheader("🔍 Value vs. Volume")

df_filtered['order_value'] = df_filtered['order_value'].fillna(0).astype(float)
df_filtered['total_units'] = df_filtered['total_units'].fillna(0).astype(int)

st.caption("Are customers who buy *more items* actually spending *more money*? Or just buying cheap accessories?")
fig_scatter = px.scatter(
    df_filtered, 
    x="total_units", 
    y="order_value", 
    color="platform_name",
    size="order_value",
    hover_data=['order_id'],
    title="Order Value vs. Total Units",
    labels={'total_units': 'Items in Basket', 'order_value': 'Total Paid (THB)'}
)
st.plotly_chart(fig_scatter, use_container_width=True)