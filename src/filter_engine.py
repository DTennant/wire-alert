"""
Filter engine: decides which filings/PRs are worth alerting on.

Two-pass filtering:
1. Keyword match on headline (fast, no API calls)
2. Market cap / float check via enrichment (slower, API call per ticker)
"""

import re
import logging
from typing import Optional

from .enrichment import enrich_ticker, passes_filters, format_enrichment
from .wire_monitor import TICKER_PATTERNS

logger = logging.getLogger(__name__)


class FilterEngine:
    def __init__(self, config: dict):
        self.config = config
        self.keywords = [kw.lower() for kw in config.get("filters", {}).get("keywords", [])]
        # Keywords that need word-boundary matching to avoid false positives
        self._short_keywords = {kw for kw in self.keywords if len(kw) <= 3}
        
    def _keyword_match(self, text: str) -> list[str]:
        """Match keywords with word-boundary awareness for short keywords."""
        matched = []
        for kw in self.keywords:
            if kw in self._short_keywords:
                # Use word boundary matching for short keywords like "ai", "fda"
                if re.search(r'\b' + re.escape(kw) + r'\b', text):
                    matched.append(kw)
            else:
                if kw in text:
                    matched.append(kw)
        return matched
    
    def evaluate(self, item: dict) -> Optional[dict]:
        """
        Evaluate a filing/PR item. Returns enriched item if it passes filters, None otherwise.
        
        item should have: headline, ticker, source, url, form_type
        """
        headline = (item.get("headline") or item.get("description") or "").lower()
        company = (item.get("company") or "").lower()
        text = f"{headline} {company}"
        
        # Pass 1: Keyword match (word-boundary aware)
        matched_keywords = self._keyword_match(text)
        if not matched_keywords:
            return None
        
        logger.info(f"Keyword match: {matched_keywords} in '{item.get('headline', '')[:80]}'")
        
        # Try to extract ticker from headline if not already present
        ticker = item.get("ticker")
        if not ticker:
            headline_raw = item.get("headline") or item.get("description") or ""
            for pattern in TICKER_PATTERNS:
                match = re.search(pattern, headline_raw)
                if match:
                    t = match.group(1).upper()
                    if t not in {"CEO", "CFO", "COO", "CTO", "IPO", "FDA", "SEC", "INC", "LLC", "ETF", "USA", "NYSE", "THE", "CIK"}:
                        ticker = t
                        item["ticker"] = ticker
                        break
        
        # Pass 2: Enrich ticker and check market cap
        enrichment = None
        
        if ticker:
            try:
                enrichment = enrich_ticker(ticker)
            except Exception as e:
                logger.debug(f"Enrichment error for {ticker}: {e}")
            if enrichment and not passes_filters(enrichment, self.config):
                logger.debug(f"Filtered out {ticker}: market cap too large or too small")
                return None
        
        # Build alert item
        alert = {
            **item,
            "matched_keywords": matched_keywords,
            "enrichment": enrichment if enrichment else {},
            "enrichment_text": format_enrichment(enrichment) if enrichment else "⚠️ No ticker data",
        }
        
        return alert
