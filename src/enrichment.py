"""
Ticker enrichment: market cap, float, current price, volume.

Uses yfinance for free data. Rate-limited but sufficient for alert filtering.
For production speed, consider Financial Modeling Prep API or Polygon.io.
"""

import logging
from typing import Optional
from functools import lru_cache
import time

logger = logging.getLogger(__name__)

try:
    import yfinance as yf
except ImportError:
    yf = None
    logger.warning("yfinance not installed, enrichment disabled")


# Cache enrichment data for 5 minutes to avoid hammering Yahoo
_cache: dict = {}
_cache_ttl = 300  # seconds


def enrich_ticker(ticker: str) -> Optional[dict]:
    """
    Get market cap, float, price, volume for a ticker.
    Returns None if ticker not found or data unavailable.
    """
    if not ticker or not yf:
        return None
    
    ticker = ticker.upper()
    
    # Check cache
    now = time.time()
    if ticker in _cache and (now - _cache[ticker]["_ts"]) < _cache_ttl:
        return _cache[ticker]
    
    try:
        stock = yf.Ticker(ticker)
        info = stock.info
        
        if not info or info.get("regularMarketPrice") is None:
            return None
        
        data = {
            "ticker": ticker,
            "price": info.get("regularMarketPrice") or info.get("currentPrice"),
            "market_cap": info.get("marketCap"),
            "float_shares": info.get("floatShares"),
            "volume": info.get("regularMarketVolume") or info.get("volume"),
            "avg_volume": info.get("averageDailyVolume10Day") or info.get("averageVolume"),
            "name": info.get("shortName") or info.get("longName", ""),
            "exchange": info.get("exchange", ""),
            "_ts": now,
        }
        
        _cache[ticker] = data
        return data
        
    except Exception as e:
        logger.debug(f"Enrichment failed for {ticker}: {e}")
        return None


def passes_filters(enrichment: dict, config: dict) -> bool:
    """Check if enriched ticker data passes configured filters."""
    filters = config.get("filters", {})
    
    mcap = enrichment.get("market_cap")
    if mcap is not None:
        max_mcap = filters.get("max_market_cap", 50_000_000)
        min_mcap = filters.get("min_market_cap", 1_000_000)
        if mcap > max_mcap or mcap < min_mcap:
            return False
    
    # Volume spike check
    vol = enrichment.get("volume")
    avg_vol = enrichment.get("avg_volume")
    if vol and avg_vol and avg_vol > 0:
        ratio = vol / avg_vol
        min_ratio = filters.get("min_volume_ratio", 2.0)
        # Don't filter OUT based on volume - just flag it
        enrichment["volume_ratio"] = round(ratio, 1)
    
    return True


def format_enrichment(data: dict) -> str:
    """Format enrichment data for display."""
    if not data:
        return "No data available"
    
    parts = []
    if data.get("name"):
        parts.append(f"📛 {data['name']}")
    if data.get("price"):
        parts.append(f"💰 ${data['price']:.2f}")
    if data.get("market_cap"):
        mcap = data["market_cap"]
        if mcap >= 1_000_000_000:
            parts.append(f"📊 Mcap: ${mcap/1e9:.1f}B")
        elif mcap >= 1_000_000:
            parts.append(f"📊 Mcap: ${mcap/1e6:.1f}M")
        else:
            parts.append(f"📊 Mcap: ${mcap:,.0f}")
    if data.get("float_shares"):
        fs = data["float_shares"]
        if fs >= 1_000_000:
            parts.append(f"🔄 Float: {fs/1e6:.1f}M")
        else:
            parts.append(f"🔄 Float: {fs:,.0f}")
    if data.get("volume_ratio"):
        parts.append(f"📈 Vol: {data['volume_ratio']}x avg")
    
    return " | ".join(parts)
