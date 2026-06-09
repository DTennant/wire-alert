#!/usr/bin/env python3
"""
wire-alert: Real-time SEC EDGAR + PR wire monitoring for nano-cap catalysts.

Usage:
    python main.py                    # Run with config.yaml
    python main.py --config my.yaml   # Custom config
    python main.py --test             # Test mode: single poll, no loop
"""

import argparse
import logging
import signal
import sys
import time
from pathlib import Path

import yaml
from rich.console import Console
from rich.logging import RichHandler

from src.edgar_monitor import EdgarMonitor
from src.wire_monitor import WireMonitor
from src.filter_engine import FilterEngine
from src.alert import AlertDispatcher

console = Console()

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(message)s",
    handlers=[RichHandler(console=console, rich_tracebacks=True)],
)
logger = logging.getLogger("wire-alert")


def load_config(path: str = "config.yaml") -> dict:
    """Load YAML config file."""
    config_path = Path(path)
    if not config_path.exists():
        # Try example config
        example = Path("config.example.yaml")
        if example.exists():
            logger.warning(f"No {path} found, using config.example.yaml")
            config_path = example
        else:
            logger.error("No config file found. Copy config.example.yaml to config.yaml")
            sys.exit(1)
    
    with open(config_path) as f:
        return yaml.safe_load(f)


def run(config: dict, test_mode: bool = False):
    """Main monitoring loop."""
    edgar = EdgarMonitor(config)
    wire = WireMonitor(config)
    filter_engine = FilterEngine(config)
    alerter = AlertDispatcher(config)
    
    polling = config.get("polling", {})
    edgar_interval = polling.get("edgar_interval_seconds", 5)
    rss_interval = polling.get("rss_interval_seconds", 30)
    
    console.print("[bold green]🚀 wire-alert started[/]")
    console.print(f"  EDGAR polling: every {edgar_interval}s")
    console.print(f"  RSS polling: every {rss_interval}s")
    console.print(f"  Keywords: {', '.join(config.get('filters', {}).get('keywords', []))}")
    console.print(f"  Max market cap: ${config.get('filters', {}).get('max_market_cap', 50_000_000):,}")
    console.print()
    
    last_rss_poll = 0
    cycle = 0
    
    while True:
        try:
            cycle += 1
            now = time.time()
            
            # Always poll EDGAR (higher frequency)
            try:
                edgar_items = edgar.poll()
                for item in edgar_items:
                    alert = filter_engine.evaluate(item)
                    if alert:
                        alerter.send(alert)
            except Exception as e:
                logger.error(f"EDGAR cycle error: {e}")
            
            # Poll RSS less frequently
            if now - last_rss_poll >= rss_interval:
                try:
                    wire_items = wire.poll()
                    for item in wire_items:
                        alert = filter_engine.evaluate(item)
                        if alert:
                            alerter.send(alert)
                    last_rss_poll = now
                except Exception as e:
                    logger.error(f"Wire cycle error: {e}")
            
            if test_mode:
                console.print(f"\n[dim]Test mode: 1 cycle complete. "
                            f"EDGAR items: {len(edgar_items)}, "
                            f"Wire items: {len(wire_items)}, "
                            f"Alerts: {alerter.alert_count}[/]")
                break
            
            # Status heartbeat every 100 cycles
            if cycle % 100 == 0:
                console.print(f"[dim]💓 Cycle {cycle} | Alerts sent: {alerter.alert_count}[/]")
            
            time.sleep(edgar_interval)
            
        except KeyboardInterrupt:
            console.print("\n[yellow]Shutting down...[/]")
            break


def main():
    parser = argparse.ArgumentParser(description="wire-alert: nano-cap catalyst monitor")
    parser.add_argument("--config", default="config.yaml", help="Config file path")
    parser.add_argument("--test", action="store_true", help="Test mode: single poll cycle")
    args = parser.parse_args()
    
    config = load_config(args.config)
    run(config, test_mode=args.test)


if __name__ == "__main__":
    main()
