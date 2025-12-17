import streamlit as st
import pandas as pd
from sqlalchemy import create_engine
from io import BytesIO

# --- DATABASE CONNECTION ---
def get_connection():
    db_config = st.secrets["connections"]["postgresql"]
    url = f"postgresql+psycopg2://{db_config['username']}:{db_config['password']}@{db_config['host']}:{db_config['port']}/{db_config['database']}"
    return create_engine(url)

engine = get_connection()

# --- HELPER: GENERATE SAMPLES (Updated for TikTok/Lazada) ---
def get_sample_file(platform_name):
    if platform_name == "TikTok":
        data = {
            "Order ID": ["5764332211", "5764332299"],
            "Created Time": ["01/01/2025 10:00:00", "01/01/2025 12:00:00"],
            "Seller SKU": ["001-IRC-MAXING-TT-27517-003", "IRC-SCT-FORZA"],
            "Quantity": [1, 2],
            "SKU Unit Original Price": [1400.00, 900.00]
        }
    elif platform_name == "Lazada":
        data = {
            "orderNumber": ["3957221001", "3957221002"],
            "createTime": ["01 Jan 2025 10:00", "02 Jan 2025 14:30"],
            "sellerSku": ["001-IRC-MAXING-TT-27517-003", "IRC-SCT-FORZA"],
            "unitPrice": [1400.00, 900.00],
            "shippingFee": [45.00, 0.00] # Lazada splits shipping often
        }
    else:
        return None

    df = pd.DataFrame(data)
    buffer = BytesIO()
    df.to_csv(buffer, index=False)
    buffer.seek(0)
    return buffer

# --- PROCESSING LOGIC ---

def process_tiktok(df):
    df_clean = pd.DataFrame()
    # TikTok Header Mapping
    df_clean['order_id'] = df['Order ID'].astype(str)
    df_clean['order_date'] = pd.to_datetime(df['Created Time'])
    df_clean['platform_sku_original'] = df['SKU ID']
    df_clean['quantity'] = df['Quantity']
    df_clean['unit_price'] = df['SKU Unit Original Price']
    df_clean['platform'] = 'Tiktok'
    return df_clean

def process_lazada(df):
    df_clean = pd.DataFrame()
    # Lazada Header Mapping (Note: Lazada headers are often camelCase)
    df_clean['order_id'] = df['orderNumber'].astype(str)
    df_clean['order_date'] = pd.to_datetime(df['createTime'])
    df_clean['platform_sku_original'] = df['lazadaSku']
    df_clean['unit_price'] = df['unitPrice']
        
    # Lazada usually implies Qty=1 per row in transaction reports, 
    # We assume 1 unless 'itemsCount' exists.
    df_clean['quantity'] = 1 
        
    df_clean['platform'] = 'Lazada'
    return df_clean

# --- MAIN UPLOAD LOGIC ---
def match_skus_and_upload(df_clean):
    # 1. Get Bindings from DB
    bindings_query = "SELECT platform_external_sku, selling_sku_id FROM product.platform_bindings"
    df_bindings = pd.read_sql(bindings_query, engine)

    df_clean['platform_sku_original'] = df_clean['platform_sku_original'].astype(str)
    df_bindings['platform_external_sku'] = df_bindings['platform_external_sku'].astype(str)
    
    # 2. Match (Excel SKU -> Database SKU)
    merged_df = pd.merge(
        df_clean, 
        df_bindings, 
        left_on='platform_sku_original', 
        right_on='platform_external_sku', 
        how='left'
    )
    
    # 3. Check Errors
    unmapped = merged_df[merged_df['selling_sku_id'].isna()]
    if not unmapped.empty:
        st.error(f"⚠️ Found {len(unmapped)} unknown SKUs! Check your Binding Table.")
        st.dataframe(unmapped[['platform_sku_original']].drop_duplicates())
        return False
    
    merged_df['unit_price'] = merged_df['unit_price'].fillna(0).astype(float)
    merged_df['quantity'] = merged_df['quantity'].fillna(0).astype(int)
    
    # Calculate line total
    merged_df['subtotal'] = merged_df['unit_price'] * merged_df['quantity']
    
    # Calculate ORDER HEADER TOTAL (Sum of items)
    # This groups by ID and sums the prices so the Header table gets the full value
    order_totals = merged_df.groupby('order_id')['subtotal'].sum().reset_index()
    order_totals.rename(columns={'subtotal': 'total_amount'}, inplace=True)
    
    # Merge the calculated total back to the main data
    merged_df = pd.merge(merged_df, order_totals, on='order_id', how='left')
    merged_df['platform_name'] = merged_df['platform']
        
    # 4. Save to DB
    try:
    # A. Save Headers
        orders_data = merged_df[['order_id', 'platform_name', 'order_date', 'total_amount']].drop_duplicates(subset='order_id')
        
        # REMOVE try/except temporarily to see the real error
        orders_data.to_sql('orders', engine, schema='sales', if_exists='append', index=False) 

        # B. Save Items
        items_data = merged_df[['order_id', 'selling_sku_id', 'platform_sku_original', 'quantity', 'unit_price', 'subtotal']]
        items_data.to_sql('order_items', engine, schema='sales', if_exists='append', index=False)
        
        return True
    except Exception as e:
        st.error(f"Upload Error: {e}")
        return False
    
    

# --- UI ---
st.title("📥 Import Orders (TikTok & Lazada)")

platform = st.selectbox("Select Platform", ["TikTok", "Lazada"])

# Download Sample
st.info(f"Need a template? Download the {platform} sample.")
sample_btn = st.download_button(
    label="📄 Download Sample CSV",
    data=get_sample_file(platform),
    file_name=f"sample_{platform.lower()}.csv",
    mime="text/csv"
)

st.divider()

uploaded_file = st.file_uploader("Upload Export File", type=['csv', 'xlsx'])

if uploaded_file and st.button("Process File"):
    # Load File
    if uploaded_file.name.endswith('.csv'):
        raw_df = pd.read_csv(uploaded_file)
    else:
        raw_df = pd.read_excel(uploaded_file, engine='openpyxl')
    
    # Process
    if platform == "TikTok":
        clean_df = process_tiktok(raw_df)
    elif platform == "Lazada":
        clean_df = process_lazada(raw_df)
        
    # Upload
    if match_skus_and_upload(clean_df):
        st.success("✅ Transaction Data Imported Successfully!")