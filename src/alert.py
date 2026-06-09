"""
Alert dispatcher: sends filtered alerts to configured channels.

Supports:
- Terminal (rich console output)
- Slack (incoming webhook)
- Discord (webhook)
"""

import json
import logging
from datetime import datetime, timezone

import requests
from rich.console import Console
from rich.panel import Panel
from rich.text import Text

logger = logging.getLogger(__name__)
console = Console()


class AlertDispatcher:
    def __init__(self, config: dict):
        self.config = config
        alerts_config = config.get("alerts", {})
        self.slack_webhook = alerts_config.get("slack_webhook", "")
        self.discord_webhook = alerts_config.get("discord_webhook", "")
        self.terminal = alerts_config.get("terminal", True)
        self.alert_count = 0
    
    def send(self, alert: dict):
        """Dispatch alert to all configured channels."""
        self.alert_count += 1
        
        if self.terminal:
            self._send_terminal(alert)
        
        if self.slack_webhook:
            self._send_slack(alert)
        
        if self.discord_webhook:
            self._send_discord(alert)
    
    def _send_terminal(self, alert: dict):
        """Rich terminal output."""
        ticker = alert.get("ticker", "???")
        source = alert.get("source", "Unknown")
        headline = alert.get("headline", alert.get("description", ""))
        keywords = ", ".join(alert.get("matched_keywords", []))
        enrichment = alert.get("enrichment_text", "")
        url = alert.get("url", "")
        now = datetime.now(timezone.utc).strftime("%H:%M:%S UTC")
        
        title = f"🚨 [{source}] ${ticker} — {now}"
        body = f"""📰 {headline}

🔑 Keywords: {keywords}
{enrichment}
🔗 {url}"""
        
        mcap = (alert.get("enrichment") or {}).get("market_cap", float("inf"))
        style = "bold red" if mcap < 10_000_000 else "bold yellow"
        console.print(Panel(body, title=title, border_style=style))
    
    def _send_slack(self, alert: dict):
        """Send to Slack incoming webhook."""
        try:
            ticker = alert.get("ticker", "???")
            source = alert.get("source", "Unknown")
            headline = alert.get("headline", alert.get("description", ""))
            keywords = ", ".join(alert.get("matched_keywords", []))
            enrichment = alert.get("enrichment_text", "")
            url = alert.get("url", "")
            
            text = f"""🚨 *[{source}] ${ticker}*
📰 {headline}
🔑 Keywords: {keywords}
{enrichment}
🔗 <{url}>"""
            
            requests.post(
                self.slack_webhook,
                json={"text": text},
                timeout=5,
            )
        except Exception as e:
            logger.error(f"Slack alert failed: {e}")
    
    def _send_discord(self, alert: dict):
        """Send to Discord webhook."""
        try:
            ticker = alert.get("ticker", "???")
            source = alert.get("source", "Unknown")
            headline = alert.get("headline", alert.get("description", ""))
            keywords = ", ".join(alert.get("matched_keywords", []))
            enrichment = alert.get("enrichment_text", "")
            url = alert.get("url", "")
            
            content = f"""🚨 **[{source}] ${ticker}**
📰 {headline}
🔑 Keywords: {keywords}
{enrichment}
🔗 <{url}>"""
            
            requests.post(
                self.discord_webhook,
                json={"content": content},
                timeout=5,
            )
        except Exception as e:
            logger.error(f"Discord alert failed: {e}")
    
    def _format_text(self, alert: dict) -> str:
        """Plain text format for logging."""
        ticker = alert.get("ticker", "???")
        source = alert.get("source", "")
        headline = alert.get("headline", "")[:100]
        return f"[{source}] ${ticker}: {headline}"
