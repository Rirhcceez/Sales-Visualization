import streamlit as st
import pandas as pd
import plotly.express as px
import numpy as np
from itertools import combinations
from collections import Counter

# --- 1. Page Configuration & Definitions ---
st.set_page_config(page_title="Moto Parts Sales Analytics", layout="wide")

st.title("🏍️ Motorcycle Parts Sales Dashboard")
st.markdown("Analytic overview of Sales Performance, Trends, and Product consistency.")

# Define Category Mapping
CATEGORY_MAP = {
    "001": "Tire",
    "002": "Rubber",
    "003": "Motor Oil",
    "004": "Battery",
    "005": "Spark Plug",
    "006": "Sprocket",
    "007": "Motorcycle Belt",
    "008": "Etc",
    "009": "Brake"
}

# --- 2. Data Loading & Preprocessing ---
@st.cache_data
def load_data():
    try:
        # NOTE: Update these paths if your files are in a different folder
        df_items = pd.read_csv('postgresql_order_items_exported.csv')
        df_orders = pd.read_csv('postgresql_orders_exported.csv')
    except FileNotFoundError:
        st.error("CSV files not found. Please ensure 'postgresql_order_items_exported.csv' and 'postgresql_orders_exported.csv' are in the same folder.")
        return None, None, None

    # -- Cleaning & Merging --
    # Filter columns
    df_items = df_items[['order_id', 'selling_sku_id', 'quantity', 'unit_price', 'subtotal']]
    df_orders = df_orders[['order_id', 'platform_name', 'order_date', 'total_amount']]

    # Add category_id and map to Category Name
    df_items['category_id'] = df_items['selling_sku_id'].str[:3]
    df_items['category_name'] = df_items['category_id'].map(CATEGORY_MAP).fillna("Unknown")

    # Date conversion
    df_orders['order_date'] = pd.to_datetime(df_orders['order_date'])
    df_orders['order_month'] = df_orders['order_date'].dt.to_period('M').astype(str)

    # Merge for full dataset
    df_merged = df_items.merge(df_orders, on='order_id', how='left')
    
    return df_items, df_orders, df_merged

df_items, df_orders, df_merged = load_data()

if df_merged is not None:

    # --- 3. Sidebar Filters ---
    st.sidebar.header("Filter Data")
    
    # Platform Filter
    available_platforms = df_orders['platform_name'].unique()
    selected_platforms = st.sidebar.multiselect("Select Platform", available_platforms, default=available_platforms)
    
    # Month Filter
    available_months = sorted(df_orders['order_month'].unique())
    selected_month = st.sidebar.select_slider("Select Month Range", options=available_months, value=(available_months[0], available_months[-1]))

    # Filter Logic
    start_month, end_month = selected_month
    
    # Apply filters
    mask_orders = (
        (df_orders['platform_name'].isin(selected_platforms)) & 
        (df_orders['order_month'] >= start_month) & 
        (df_orders['order_month'] <= end_month)
    )
    df_orders_filtered = df_orders[mask_orders]

    mask_merged = (
        (df_merged['platform_name'].isin(selected_platforms)) & 
        (df_merged['order_month'] >= start_month) & 
        (df_merged['order_month'] <= end_month)
    )
    df_merged_filtered = df_merged[mask_merged]

    # --- 4. Overview Section (KPIs) ---
    st.header("1. Sales Overview")
    
    total_revenue = df_orders_filtered['total_amount'].sum()
    total_orders = df_orders_filtered['order_id'].nunique()
    
    if total_orders > 0:
        aov = total_revenue / total_orders
        basket_size = df_merged_filtered['quantity'].sum() / total_orders
    else:
        aov = 0
        basket_size = 0

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Total Revenue", f"฿{total_revenue:,.0f}")
    col2.metric("Total Orders", f"{total_orders:,}")
    col3.metric("Avg Order Value (AOV)", f"฿{aov:,.2f}")
    col4.metric("Avg Basket Size", f"{basket_size:,.2f} items")

    st.divider()

    # --- 5. Tabs for Detailed Analysis ---
    tab1, tab2, tab3 = st.tabs(["📈 Trends & Platform", "🏆 Hero Products", "🔗 Correlations"])

    # === TAB 1: Trends & Platform ===
    with tab1:
        col_t1, col_t2 = st.columns(2)
        
        with col_t1:
            st.subheader("Monthly Sales Trend")
            sales_by_month = df_orders_filtered.groupby(['order_month', 'platform_name'])['total_amount'].sum().reset_index()
            fig_trend = px.line(sales_by_month, x='order_month', y='total_amount', color='platform_name', 
                                color_discrete_map={"Tiktok": "#FE2C55", "Shopee": "#EE4D2D", "Lazada": "#0f146d"},
                                markers=True, title="Revenue over Time")
            st.plotly_chart(fig_trend, use_container_width=True)

        with col_t2:
            st.subheader("Platform Share")
            
            # -- Toggle Button Logic --
            view_metric = st.radio(
                "View Share By:", 
                ["Orders", "Sales"], 
                horizontal=True,
                label_visibility="collapsed"
            )

            if view_metric == "Orders":
                platform_data = df_orders_filtered['platform_name'].value_counts().reset_index()
                platform_data.columns = ['platform_name', 'value']
                chart_title = "Share of Orders by Platform"
                text_info = "percent+label"
            else:
                platform_data = df_orders_filtered.groupby('platform_name')['total_amount'].sum().reset_index()
                platform_data.columns = ['platform_name', 'value']
                chart_title = "Share of Sales (Revenue) by Platform"
                text_info = "percent+label+value"

            fig_pie = px.pie(
                platform_data, 
                values='value', 
                names='platform_name', 
                color='platform_name',
                color_discrete_map={"Tiktok": "#FE2C55", "Shopee": "#EE4D2D", "Lazada": "#0f146d"},
                title=chart_title,
                hole=0.4
            )
            fig_pie.update_traces(textposition='inside', textinfo=text_info)
            st.plotly_chart(fig_pie, use_container_width=True)
        
        # -- Category Chart (Updated with Names) --
        st.subheader("Category Performance")
        
        # Group by 'category_name' instead of ID
        cat_sales = df_merged_filtered.groupby('category_name')['subtotal'].sum().reset_index().sort_values('subtotal', ascending=False)
        
        fig_cat = px.bar(
            cat_sales, 
            x='category_name', 
            y='subtotal', 
            text_auto='.2s', 
            title="Best Selling Categories (Revenue)",
            color='subtotal',
            color_continuous_scale='Blues'
        )
        st.plotly_chart(fig_cat, use_container_width=True)

    # === TAB 2: Product Analysis (Hero & Consistency) ===
    with tab2:
        st.subheader("Top Products & Consistency Streak")
        st.markdown("The **Current Streak** shows how many recent consecutive months this product has been sold. High streak = Consistent Demand.")

        # 1. Total Sales per SKU
        sku_stats = df_merged_filtered.groupby(['selling_sku_id', 'category_name']).agg({
            'subtotal': 'sum',
            'quantity': 'sum',
            'order_id': 'nunique'
        }).reset_index()

        # 2. Logic for Streak Count
        pivot_monthly = df_merged.pivot_table(index='selling_sku_id', columns='order_month', values='subtotal', aggfunc='sum').fillna(0)
        latest_months = sorted(df_merged['order_month'].unique(), reverse=True)
        
        streaks = {}
        for sku, row in pivot_monthly.iterrows():
            current_streak = 0
            for month in latest_months:
                if row[month] > 0:
                    current_streak += 1
                else:
                    break 
            streaks[sku] = current_streak

        df_streaks = pd.DataFrame(list(streaks.items()), columns=['selling_sku_id', 'current_streak'])
        final_product_df = sku_stats.merge(df_streaks, on='selling_sku_id')

        # Interactive Table
        st.dataframe(
            final_product_df.sort_values(by='subtotal', ascending=False).style.format({'subtotal': "฿{:,.0f}"}),
            column_config={
                "category_name": "Category",
                "current_streak": st.column_config.ProgressColumn(
                    "Consistency Streak (Months)",
                    format="%d",
                    min_value=0,
                    max_value=len(latest_months),
                ),
                "subtotal": "Total Revenue",
                "quantity": "Units Sold"
            },
            use_container_width=True,
            hide_index=True
        )

    # === TAB 3: Correlation (Market Basket) ===
    with tab3:
        st.subheader("Product Correlation (Frequently Bought Together)")
        st.markdown("Which products usually appear in the same order?")

        order_counts = df_merged_filtered.groupby('order_id')['selling_sku_id'].count()
        multi_item_orders = order_counts[order_counts > 1].index
        df_basket = df_merged_filtered[df_merged_filtered['order_id'].isin(multi_item_orders)]

        if not df_basket.empty:
            baskets = df_basket.groupby('order_id')['selling_sku_id'].apply(list)
            pair_counts = Counter()
            for products in baskets:
                products = sorted(products)
                pair_counts.update(combinations(products, 2))
            
            df_pairs = pd.DataFrame(pair_counts.most_common(20), columns=['Product Pair', 'Frequency'])
            df_pairs['Product A'] = df_pairs['Product Pair'].apply(lambda x: x[0])
            df_pairs['Product B'] = df_pairs['Product Pair'].apply(lambda x: x[1])
            
            st.write("#### Top 20 Co-occurring Pairs")
            
            # Simple Bubble Chart
            fig_corr = px.scatter(
                df_pairs, 
                x='Product A', 
                y='Product B', 
                size='Frequency', 
                color='Frequency', 
                title="Correlation Strength",
                height=600,
                color_continuous_scale='Viridis'
            )
            # Adjust layout for better label reading
            fig_corr.update_xaxes(tickangle=45)
            st.plotly_chart(fig_corr, use_container_width=True)
            
        else:
            st.info("Not enough multi-item orders to calculate correlations for this filtered selection.")