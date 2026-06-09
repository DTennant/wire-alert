"""
PR Wire RSS feed monitor.

Aggregates press releases from:
- GlobeNewswire
- PR Newswire
- BusinessWire
- AccessWire

These are free RSS feeds with ~1-2 min delay from actual wire publication.
For sub-second latency, upgrade to RTPR.io WebSocket ($139/mo).
"""

import re
import time
import logging
import feedparser
from datetime import datetime, timezone
from typing import Optional

logger = logging.getLogger(__name__)

# RSS feed URLs for major PR wires
WIRE_FEEDS = {
    "GlobeNewswire": "https://www.globenewswire.com/RssFeed/subjectcode/01-BUS/feedTitle/GlobeNewswire%20-%20News%20Releases",
    "PRNewswire": "https://www.prnewswire.com/rss/news-releases-list.rss",
    "BusinessWire": "https://feed.businesswire.com/rss/home/?rss=G1QFDERJXkJeEFpRWg==",
    "AccessWire": "https://www.accesswire.com/rss/news.xml",
}

# Regex to find tickers in PR headlines - common patterns
TICKER_PATTERNS = [
    r'\((?:NASDAQ|NYSE|NYSEAMERICAN|OTC|OTCQB|OTCQX|OTCBB|TSX|TSXV):\s*([A-Z]{1,5})\)',
    r'\(([A-Z]{1,5})\)',  # fallback: any (TICK) pattern
]


class WireMonitor:
    def __init__(self, config: dict):
        self.feeds = WIRE_FEEDS.copy()
        self.seen_ids: set = set()
        self.max_seen = 10000
        
    def poll(self) -> list[dict]:
        """Poll all RSS feeds for new press releases."""
        results = []
        
        for wire_name, feed_url in self.feeds.items():
            try:
                entries = self._fetch_feed(wire_name, feed_url)
                for entry in entries:
                    eid = entry.get("id")
                    if eid and eid not in self.seen_ids:
                        self.seen_ids.add(eid)
                        results.append(entry)
            except Exception as e:
                logger.error(f"Wire feed error ({wire_name}): {e}")
        
        # Trim seen set
        if len(self.seen_ids) > self.max_seen:
            self.seen_ids = set(list(self.seen_ids)[-5000:])
        
        return results
    
    def _fetch_feed(self, wire_name: str, feed_url: str) -> list[dict]:
        """Parse a single RSS feed."""
        feed = feedparser.parse(feed_url)
        entries = []
        
        for item in feed.entries[:50]:  # only check recent 50
            entry_id = item.get("id") or item.get("link", "")
            title = item.get("title", "")
            link = item.get("link", "")
            published = item.get("published", "")
            summary = item.get("summary", "")[:500]
            
            ticker = self._extract_ticker(title) or self._extract_ticker(summary)
            
            entries.append({
                "id": entry_id,
                "source": wire_name,
                "headline": title,
                "ticker": ticker,
                "url": link,
                "published": published,
                "summary": summary,
                "form_type": "PR",
            })
        
        return entries
    
    def _extract_ticker(self, text: str) -> Optional[str]:
        """Extract stock ticker from text using common PR patterns."""
        for pattern in TICKER_PATTERNS:
            match = re.search(pattern, text)
            if match:
                ticker = match.group(1).upper()
                # Filter out common false positives
                if ticker not in {"CEO", "CFO", "COO", "CTO", "IPO", "FDA", "SEC", "INC", "LLC", "ETF", "USA", "NYSE", "THE"}:
                    return ticker
        return None
