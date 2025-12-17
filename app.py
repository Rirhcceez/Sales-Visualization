import streamlit as st
import pandas as pd
import plotly.express as px
from sqlalchemy import create_engine

# --- 1. SETUP & CONNECTION ---
st.set_page_config(page_title="Sales Analytics", layout="wide")

@st.cache_resource

