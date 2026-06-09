"""
SEC EDGAR real-time filing monitor.

Uses the free EFTS (full-text search) API to poll for new filings.
Rate limit: 10 requests/second.
No API key required, but must include User-Agent header.
"""

import time
import requests
import logging
from datetime import datetime, timezone
from typing import Optional

logger = logging.getLogger(__name__)

EDGAR_EFTS_URL = "https://efts.sec.gov/LATEST/search-index"
EDGAR_LATEST_URL = "https://efts.sec.gov/LATEST/search"

class EdgarMonitor:
    def __init__(self, config: dict):
        self.user_agent = config.get("edgar", {}).get("user_agent", "wire-alert bot@example.com")
        self.form_types = config.get("filters", {}).get("edgar_form_types", ["8-K"])
        self.headers = {
            "User-Agent": self.user_agent,
            "Accept": "application/json",
        }
        self.seen_ids: set = set()
        self.max_seen = 5000  # prevent unbounded memory
        
    def poll(self) -> list[dict]:
        """Poll EDGAR for new filings. Returns list of new filing dicts."""
        results = []
        
        for form_type in self.form_types:
            try:
                filings = self._fetch_recent(form_type)
                for f in filings:
                    fid = f.get("id") or f.get("file_num", "") + f.get("file_date", "")
                    if fid and fid not in self.seen_ids:
                        self.seen_ids.add(fid)
                        results.append(f)
            except Exception as e:
                logger.error(f"EDGAR poll error for {form_type}: {e}")
        
        # Trim seen set
        if len(self.seen_ids) > self.max_seen:
            self.seen_ids = set(list(self.seen_ids)[-2000:])
        
        return results
    
    def _fetch_recent(self, form_type: str) -> list[dict]:
        """Fetch recent filings of a given type from EDGAR EFTS."""
        params = {
            "q": "*",
            "dateRange": "custom",
            "startdt": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
            "enddt": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
            "forms": form_type,
        }
        
        resp = requests.get(
            EDGAR_LATEST_URL,
            params=params,
            headers=self.headers,
            timeout=10,
        )
        resp.raise_for_status()
        data = resp.json()
        
        hits = data.get("hits", {}).get("hits", [])
        filings = []
        for hit in hits:
            source = hit.get("_source", {})
            filing = {
                "id": hit.get("_id", ""),
                "form_type": source.get("form_type", form_type),
                "company": source.get("display_names", [""])[0] if source.get("display_names") else source.get("entity_name", "Unknown"),
                "ticker": self._extract_ticker(source),
                "filed_at": source.get("file_date", ""),
                "description": source.get("display_description", ""),
                "url": self._build_url(hit),
                "source": "EDGAR",
            }
            filings.append(filing)
        
        return filings
    
    def _extract_ticker(self, source: dict) -> Optional[str]:
        """Try to extract ticker from filing source data."""
        tickers = source.get("tickers", [])
        if tickers:
            return tickers[0].upper()
        # Sometimes in display_names as "COMPANY (TICK)"
        names = source.get("display_names", [])
        for name in names:
            if "(" in name and ")" in name:
                return name.split("(")[-1].replace(")", "").strip().upper()
        return None
    
    def _build_url(self, hit: dict) -> str:
        """Build SEC filing URL from hit data."""
        file_id = hit.get("_id", "")
        if file_id:
            # Convert ID format: 0001234567-24-000001 -> 000123456724000001
            clean_id = file_id.replace("-", "")
            return f"https://www.sec.gov/Archives/edgar/data/{clean_id[:10].lstrip('0')}/{file_id}.htm"
        return ""
