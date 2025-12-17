import streamlit as st
import pandas as pd
from sqlalchemy import create_engine

# --- 1. SETUP PAGE ---
st.set_page_config(page_title="Inventory Analytics", layout="wide")
st.title("📊 Shop Inventory Intelligence")

# --- 2. DATABASE CONNECTION ---
# We use st.cache_resource so it doesn't reconnect every time you click a button
@st.cache_resource
def get_connection():
    # Construct the URL from secrets
    db_config = st.secrets["connections"]["postgresql"]
    url = f"postgresql+psycopg2://{db_config['username']}:{db_config['password']}@{db_config['host']}:{db_config['port']}/{db_config['database']}"
    return create_engine(url)

engine = get_connection()

# --- 3. LOAD DATA (The Analyst Logic) ---
def load_data():
    # We query the VIEW we created earlier. 
    # If you didn't create the view, you can paste the long SQL query here.
    query = """
    SELECT 
        pb.platform_name,
        sv.name as product_name,
        sv.is_bundle,
        sv.standard_price as selling_price,
        -- Calculate Dynamic Cost based on BOM
        (SELECT SUM(bi.current_cost * bom.quantity) 
         FROM product.bill_of_materials bom 
         JOIN product.base_items bi ON bom.base_sku_id = bi.base_sku_id 
         WHERE bom.selling_sku_id = sv.selling_sku_id) as total_cost
    FROM product.platform_bindings pb
    JOIN product.selling_variants sv ON pb.selling_sku_id = sv.selling_sku_id
    """
    return pd.read_sql(query, engine)

df = load_data()

# --- 4. DATA PROCESSING (Pandas Magic) ---
# Calculate Margin immediately
df['margin_thb'] = df['selling_price'] - df['total_cost']
df['margin_percent'] = (df['margin_thb'] / df['selling_price']) * 100

# --- 5. THE DASHBOARD LAYOUT ---

# Row A: High-Level Metrics (KPIs)
col1, col2, col3 = st.columns(3)
col1.metric("Total Listed SKUs", len(df))
col2.metric("Avg. Profit Margin", f"{df['margin_percent'].mean():.1f}%")
col3.metric("Highest Margin Item", f"{df['margin_thb'].max():,.0f} THB")

st.markdown("---")

# Row B: Drill-Down Analysis
col_left, col_right = st.columns([2, 1])

with col_left:
    st.subheader("🛠️ Margin Analysis by Platform")
    # Simple Bar Chart: Average Margin per Platform
    st.bar_chart(df.groupby("platform_name")["margin_percent"].mean())

with col_right:
    st.subheader("⚠️ Low Margin Alert")
    # Show items with < 10% margin
    low_margin = df[df['margin_percent'] < 10][['product_name', 'margin_percent']]
    st.dataframe(low_margin, hide_index=True)

# Row C: Full Data Table
st.subheader("📋 Master Inventory List")
st.dataframe(df, use_container_width=True)

# --- 6. INTERACTIVE SIDEBAR ---
st.sidebar.header("Filter Options")
selected_platform = st.sidebar.multiselect(
    "Select Platform", 
    options=df["platform_name"].unique(),
    default=df["platform_name"].unique()
)

# Apply Filter
filtered_df = df[df["platform_name"].isin(selected_platform)]