# wire-alert 🚨

Real-time SEC EDGAR filing monitor + PR wire tracker for nano-cap catalysts.

**The thesis:** Nano-cap stocks ($2-5, market cap < $50M) can 10-30x on a single press release. The edge is speed — whoever sees the PR first wins.

## Architecture

```
SEC EDGAR EFTS (free) ──┐
                        ├─→ Filter Engine ─→ Slack / Discord / Terminal
PR Wire RSS feeds    ───┘       │
                                ├─ Market cap < $50M?
                                ├─ Theme keywords hit? (quantum, AI, lunar, FDA, defense...)
                                ├─ Float < 10M shares?
                                └─ Volume anomaly?
```

## Data Sources

| Source | Latency | Cost | Method |
|--------|---------|------|--------|
| SEC EDGAR EFTS | ~seconds | Free | Polling (10 req/s limit) |
| GlobeNewswire RSS | ~1-2 min | Free | RSS polling |
| PR Newswire RSS | ~1-2 min | Free | RSS polling |
| BusinessWire RSS | ~1-2 min | Free | RSS polling |
| RTPR.io WebSocket | ~150-500ms | $139/mo | WebSocket (future upgrade) |

## Modules

- `edgar_monitor.py` — Real-time SEC 8-K filing monitor via EFTS API
- `wire_monitor.py` — PR wire RSS feed aggregator (GlobeNewswire, PR Newswire, BusinessWire, AccessWire)
- `filter_engine.py` — Configurable filters: market cap, keywords, float, volume
- `alert.py` — Multi-channel alerts (Slack webhook, Discord, terminal)
- `enrichment.py` — Ticker lookup, market cap, float, current price

## Quick Start

```bash
pip install -r requirements.txt
cp config.example.yaml config.yaml  # edit with your settings
python main.py
```

## Configuration

```yaml
filters:
  max_market_cap: 50_000_000  # $50M
  keywords:
    - quantum
    - AI
    - semiconductor
    - lunar
    - FDA
    - defense
    - contract
    - partnership
  min_volume_ratio: 3.0  # vs 30-day average

alerts:
  slack_webhook: ""  # optional
  discord_webhook: ""  # optional
  terminal: true

polling:
  edgar_interval_seconds: 5
  rss_interval_seconds: 30
```

## Roadmap

- [x] SEC EDGAR 8-K real-time monitor
- [x] PR wire RSS aggregator
- [x] Keyword + market cap filtering
- [x] Slack/Discord alerts
- [ ] RTPR.io WebSocket integration ($139/mo upgrade)
- [ ] Historical backtesting (would this filter have caught ASTC?)
- [ ] Auto price tracking after alert (did it actually move?)
- [ ] Options flow correlation

## License

MIT
