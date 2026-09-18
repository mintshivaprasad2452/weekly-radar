# Weekly Radar — Volume Rocketing Research Portal

Automated stock watchlist research pipeline for Indian Equities (NSE/BSE). Ingests weekly scan alerts, identifies rolling 4-week repeat stocks, and compiles institutional-grade Growth Triggers 1-Pager reports.

## Features
- **Rolling 4-Week Recurrence Engine:** Automatically detects stocks appearing across multiple scan weeks (`data/history.json`).
- **Growth Triggers 1-Pagers:** Institutional-quality research notes covering company snapshot, 5–7 core catalysts with quantified P&L impact, valuation expectations, downside risks, and trigger scoreboard.
- **Web Portal:** Self-contained, responsive dashboard with search, repeat badges, conviction filters, and in-browser report viewer.
- **Netlify Ready:** Deploys automatically on push.

## Project Structure
```
weekly-radar/
├── data/
│   ├── scans/
│   │   └── 2026-09-12.json       # Weekly scan snapshot (+additions, -removals)
│   └── history.json              # 4-week recurrence & streak registry
├── reports/
│   └── 2026-09-12/
│       ├── APOLLO.md             # Apollo Micro Systems Ltd
│       ├── CENTUM.md             # Centum Electronics Ltd
│       └── PITTIENG.md           # Pitti Engineering Ltd
├── index.html                    # Web research portal UI
├── netlify.toml                  # Netlify deployment configuration
└── process_scan.py               # Ingestion, history update, and portal compilation engine
```

## Running Locally / Testing
```bash
python3 process_scan.py test
```
To run the automated suite and regenerate `index.html`.
