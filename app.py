import streamlit as st
import pandas as pd
import requests
import os
import time
from datetime import datetime
# 1. Config
st.set_page_config(page_title="Debug Mode", layout="wide")
st.title("🚧 Debug Mode 🚧")
st.write("1. Application starting...")
# 2. Check File
st.write("2. Checking CSV file...")
SUPPLY_FILE = "TotalSupply_20260107.csv"
if os.path.exists(SUPPLY_FILE):
    st.success(f"Found {SUPPLY_FILE}")
else:
    st.error(f"Missing {SUPPLY_FILE} (Did you upload it?)")
# 3. API Test
st.write("3. Attempting API connection (Timeout 5s)...")
API_URL = "https://omni-client-api.prod.ap-northeast-1.variational.io/metadata/stats"
try:
    headers = {"User-Agent": "Mozilla/5.0"}
    st.write(f"   Connecting to: {API_URL}")
    response = requests.get(API_URL, headers=headers, timeout=5)
    st.write(f"   Status Code: {response.status_code}")
    if response.status_code == 200:
        data = response.json()
        st.success("4. API Fetch Successful! ✅")
        st.json(data) # Show raw data to prove it works
    else:
        st.error(f"API Failed: {response.status_code}")
except Exception as e:
    st.error(f"💥 API CRASHED: {e}")
st.write("5. End of Script.")