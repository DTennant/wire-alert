"""
SEC EDGAR real-time filing monitor.

Uses the free EFTS (full-text search) API to poll for new filings.
Rate limit: 10 requests/second.
No API key required, but must include User-Agent header.
"""

import re
import time
import requests
import logging
from datetime import datetime, timezone, timedelta
from typing import Optional

logger = logging.getLogger(__name__)

EDGAR_EFTS_URL = "https://efts.sec.gov/LATEST/search-index"


class EdgarMonitor:
    def __init__(self, config: dict):
        self.user_agent = config.get("edgar", {}).get("user_agent", "wire-alert admin@wire-alert.dev")
        self.form_types = config.get("filters", {}).get("edgar_form_types", ["8-K"])
        self.headers = {
            "User-Agent": self.user_agent,
            "Accept": "application/json",
            "Accept-Encoding": "gzip, deflate",
        }
        self.seen_ids: set = set()
        self.max_seen = 5000
        
    def poll(self) -> list[dict]:
        """Poll EDGAR for new filings. Returns list of new filing dicts."""
        results = []
        
        for form_type in self.form_types:
            try:
                filings = self._fetch_recent(form_type)
                for f in filings:
                    fid = f.get("id", "")
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
        now = datetime.now(timezone.utc)
        # Cover today and yesterday to avoid missing filings around midnight
        start = (now - timedelta(days=1)).strftime("%Y-%m-%d")
        end = now.strftime("%Y-%m-%d")
        
        params = {
            "forms": form_type,
            "dateRange": "custom",
            "startdt": start,
            "enddt": end,
        }
        
        resp = requests.get(
            EDGAR_EFTS_URL,
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
            names = source.get("display_names", [])
            company = names[0] if names else "Unknown"
            # Clean CIK from company name: "Company Name  (CIK 000123)" -> "Company Name"
            company_clean = re.sub(r'\s*\(CIK\s+\d+\)', '', company).strip()
            
            ticker = self._extract_ticker(source, names)
            
            filing = {
                "id": hit.get("_id", ""),
                "form_type": form_type,
                "company": company_clean,
                "ticker": ticker,
                "filed_at": source.get("file_date", ""),
                "headline": f"{company_clean} filed {form_type}",
                "description": source.get("display_description", "") or f"{company_clean} filed {form_type}",
                "url": self._build_url(hit),
                "source": "EDGAR",
            }
            filings.append(filing)
        
        return filings
    
    def _extract_ticker(self, source: dict, names: list) -> Optional[str]:
        """Try to extract ticker from filing source data."""
        tickers = source.get("tickers")
        if tickers and isinstance(tickers, list) and len(tickers) > 0:
            return tickers[0].upper()
        # Sometimes in display_names as "COMPANY  (TICK)  (CIK ...)"
        for name in names:
            # Match (TICK) but not (CIK ...)
            matches = re.findall(r'\(([A-Z]{1,5})\)', name)
            for m in matches:
                if m not in {"CIK"}:
                    return m
        return None
    
    def _build_url(self, hit: dict) -> str:
        """Build SEC filing URL from hit data."""
        file_id = hit.get("_id", "")
        if file_id and ":" in file_id:
            # ID format: "0001234567-26-000001:filename.htm"
            accession, filename = file_id.split(":", 1)
            accession_clean = accession.replace("-", "")
            cik = accession_clean[:10].lstrip("0")
            return f"https://www.sec.gov/Archives/edgar/data/{cik}/{accession}/{filename}"
        return ""
