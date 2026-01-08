import os
import json
import requests
import pandas as pd
import streamlit as st
import time
from datetime import datetime
# Configuration
API_URL = "https://omni-client-api.prod.ap-northeast-1.variational.io/metadata/stats"
SUPPLY_FILE = "TotalSupply_20260107.csv"

st.set_page_config(page_title="Variational Omni Stats", layout="wide")

@st.cache_data(ttl=3600)
def load_supply_data():
    """Reads the total supply CSV into a dictionary {Ticker: Supply}."""
    try:
        if not os.path.exists(SUPPLY_FILE):
            print(f"Warning: {SUPPLY_FILE} not found.")
            return {}
        
        df = pd.read_csv(SUPPLY_FILE)
        # Ensure Ticker is stripped and upper case
        df['Ticker'] = df['Ticker'].astype(str).str.strip().str.upper()
        # Ensure Supply is numeric, coercing errors to NaN
        df['Supply'] = pd.to_numeric(df['Supply'], errors='coerce').fillna(0)
        
        return dict(zip(df['Ticker'], df['Supply']))
    except Exception as e:
        print(f"Error reading supply CSV: {e}")
        return {}

def format_fdv(val):
    """Formats FDV value to T/B/M with 1 decimal."""
    if pd.isna(val) or val <= 0:
        return "-"
    
    if val >= 1_000_000_000_000:
        return f"${val / 1_000_000_000_000:.1f}T"
    elif val >= 1_000_000_000:
        return f"${val / 1_000_000_000:.1f}B"
    elif val >= 1_000_000:
        return f"${val / 1_000_000:.1f}M"
    else:
        return f"${val:,.1f}"

# Removed caching to force fresh data every time
def fetch_api_data():
    """Fetches key stats from the Variational Omni API."""
    try:
        # Add cache buster to URL to force fresh fetch
        params = {"_": int(time.time())}
        response = requests.get(API_URL, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()
        timestamp = datetime.now()
            
        return data, timestamp
    except Exception as e:
        st.error(f"Error fetching data from API: {e}")
        return None, None

def main():
    st.title("Variational Omni Dashboard")
    
    # Refresh button
    if st.button("Refresh Data"):
        st.cache_data.clear()
        
    # 1. Fetch Data
    with st.spinner("Fetching latest data from API..."):
        data, timestamp = fetch_api_data()
        
    supply_map = load_supply_data()
    
    if not data:
        st.error(f"Error fetching data: {timestamp}")
        return

    # Display Metadata
    st.write(f"**Last Updated:** {timestamp}")
    
    # --- Global Stats ---
    st.header("Global Stats")
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("Total Volume 24h", f"${float(data.get('total_volume_24h', 0)):,.0f}")
    with col2:
        st.metric("Cumulative Volume", f"${float(data.get('cumulative_volume', 0)):,.0f}")
    with col3:
        st.metric("TVL", f"${float(data.get('tvl', 0)):,.0f}")
    with col4:
        st.metric("Open Interest", f"${float(data.get('open_interest', 0)):,.0f}")

    # --- Pre-calculate All Data ---
    listings = data.get("listings", [])
    if listings:
        all_data = []
        for item in listings:
            ticker = item.get("ticker", "").strip().upper()
            price = float(item.get("mark_price", 0))
            vol_24h = float(item.get("volume_24h", 0))
            
            # Calculate FDV
            supply = supply_map.get(ticker, 0)
            fdv = price * supply if supply > 0 else 0
            
            # OI
            oi_data = item.get("open_interest", {})
            if isinstance(oi_data, dict):
                long_oi = float(oi_data.get("long_open_interest", 0))
                short_oi = float(oi_data.get("short_open_interest", 0))
            else:
                 long_oi = 0
                 short_oi = 0
            total_oi = long_oi + short_oi

            # Funding Rate Calculation (Hourly)
            # User clarification: funding_rate is Annual Funding Rate.
            # Hourly = (Annual / 365 / 24)
            # User correction: Multiply by 100 for display (or rather, don't divide raw % by 100)
            raw_funding = float(item.get("funding_rate", 0))
            hourly_funding = raw_funding / 365 / 24

            # Ratios (Raw)
            # Use safe division helper inline or pre-calc
            def safe_div(n, d): return n / d if d and d > 0 else 0
            
            row = {
                "Ticker": ticker,
                "Name": item.get("name"),
                "Price": price,
                "Volume 24h": vol_24h,
                "Hourly Funding Rate": hourly_funding,
                "Base Spread (bps)": float(item.get("base_spread_bps", 0)),
                "Long OI": long_oi,
                "Short OI": short_oi,
                "FDV_Raw": fdv,
                "FDV": format_fdv(fdv),
                # Metrics for sorting/analysis
                "FDV / Volume 24h": safe_div(fdv, vol_24h),
                "FDV / Total OI": safe_div(fdv, total_oi),
                "FDV / Long OI": safe_div(fdv, long_oi),
                "FDV / Short OI": safe_div(fdv, short_oi),
            }
            all_data.append(row)
            
        df_master = pd.DataFrame(all_data)
        
        # --- Top 10 Lists ---
        st.header("Top 10 Metrics")
        
        # Filter for meaningful metrics (e.g. Volume > 0 to avoid huge ratios or divide by zero artifacts)
        # Using the same logic as Analysis table: Volume > 0
        df_metrics = df_master[df_master["Volume 24h"] > 0].copy()
        
        c1, c2, c3 = st.columns(3)
        
        with c1:
            st.subheader("Highest FDV / Volume 24H")
            top_fdv_vol = df_metrics.sort_values(by="FDV / Volume 24h", ascending=False).head(10)
            st.dataframe(
                top_fdv_vol[["Ticker", "FDV / Volume 24h"]].style.format({
                    "FDV / Volume 24h": "{:,.2f}"
                }),
                use_container_width=True,
                hide_index=True
            )
            
        with c2:
            st.subheader("Highest FDV / Total OI")
            top_fdv_oi = df_metrics.sort_values(by="FDV / Total OI", ascending=False).head(10)
            st.dataframe(
                top_fdv_oi[["Ticker", "FDV / Total OI"]].style.format({
                     "FDV / Total OI": "{:,.2f}"
                }),
                use_container_width=True,
                hide_index=True
            )

        with c3:
            st.subheader("Highest Hourly Funding Rate")
            # Sort by absolute magnitude of Hourly Funding Rate
            # We want furthest from 0
            df_metrics["Abs Funding"] = df_metrics["Hourly Funding Rate"].abs()
            top_funding = df_metrics.sort_values(by="Abs Funding", ascending=False).head(10)
            
            st.dataframe(
                top_funding[["Ticker", "Hourly Funding Rate"]].style.format({
                     "Hourly Funding Rate": "{:.4%}" # Display with precision since we have small numbers
                }),
                use_container_width=True,
                hide_index=True
            )

        # --- Listings Table ---
        st.header("Market Listings")
        # Main Listings shows EVERYONE (even 0 volume)
        df_display = df_master.sort_values(by="Volume 24h", ascending=False)
        
        st.dataframe(
            df_display.style.format({
                "Price": "${:,.4f}",
                "Volume 24h": "${:,.0f}",
                "Hourly Funding Rate": "{:.6%}",
                "Long OI": "${:,.0f}",
                "Short OI": "${:,.0f}",
            }, na_rep="-"),
            column_order=["Ticker", "Name", "Price", "Volume 24h", "Hourly Funding Rate", "Base Spread (bps)", "FDV", "Long OI", "Short OI"],
            use_container_width=True,
            height=600,
            hide_index=True
        )

        # --- Analysis Table ---
        st.header("Analysis")
        # Analysis filters out 0 volume
        df_analysis = df_master[df_master["Volume 24h"] > 0].sort_values(by="Volume 24h", ascending=False)
        
        st.dataframe(
            df_analysis.style.format({
                "FDV / Volume 24h": "{:,.2f}",
                "FDV / Long OI": "{:,.2f}",
                "FDV / Short OI": "{:,.2f}",
                "FDV / Total OI": "{:,.2f}"
            }, na_rep="-"),
            column_order=["Ticker", "FDV / Volume 24h", "FDV / Long OI", "FDV / Short OI", "FDV / Total OI"],
            use_container_width=True,
            hide_index=True
        )

    else:
        st.warning("No listings found in the data.")


if __name__ == "__main__":
    main()
