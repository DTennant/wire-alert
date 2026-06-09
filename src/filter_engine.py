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

logger = logging.getLogger(__name__)


class FilterEngine:
    def __init__(self, config: dict):
        self.config = config
        self.keywords = [kw.lower() for kw in config.get("filters", {}).get("keywords", [])]
        
    def evaluate(self, item: dict) -> Optional[dict]:
        """
        Evaluate a filing/PR item. Returns enriched item if it passes filters, None otherwise.
        
        item should have: headline, ticker, source, url, form_type
        """
        headline = (item.get("headline") or item.get("description") or "").lower()
        company = (item.get("company") or "").lower()
        text = f"{headline} {company}"
        
        # Pass 1: Keyword match
        matched_keywords = [kw for kw in self.keywords if kw in text]
        if not matched_keywords:
            return None
        
        logger.info(f"Keyword match: {matched_keywords} in '{item.get('headline', '')[:80]}'")
        
        # Pass 2: Enrich ticker and check market cap
        ticker = item.get("ticker")
        enrichment = None
        
        if ticker:
            enrichment = enrich_ticker(ticker)
            if enrichment and not passes_filters(enrichment, self.config):
                logger.debug(f"Filtered out {ticker}: market cap too large or too small")
                return None
        
        # Build alert item
        alert = {
            **item,
            "matched_keywords": matched_keywords,
            "enrichment": enrichment,
            "enrichment_text": format_enrichment(enrichment) if enrichment else "⚠️ No ticker data",
        }
        
        return alert
