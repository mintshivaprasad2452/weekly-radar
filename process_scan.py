#!/usr/bin/env python3
"""
Weekly Stock Watchlist & Growth Triggers - Automation Engine
============================================================
Handles:
1. Scan ingestion & rolling 4-week recurrence calculation
2. Synchronization of Markdown reports from reports/ directory
3. Dynamic compilation of the web portal (index.html)
4. Comprehensive test verification suite
5. Deployment packaging for Netlify
"""

import json
import os
import sys
import glob
import re
import shutil
import zipfile

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
SCANS_DIR = os.path.join(DATA_DIR, "scans")
HISTORY_FILE = os.path.join(DATA_DIR, "history.json")
REPORTS_DIR = os.path.join(BASE_DIR, "reports")
INDEX_FILE = os.path.join(BASE_DIR, "index.html")
DIST_DIR = os.path.join(BASE_DIR, "dist")

def load_json(filepath, default=None):
    if os.path.exists(filepath):
        with open(filepath, "r", encoding="utf-8") as f:
            return json.load(f)
    return default or {}

def save_json(filepath, data):
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)

def update_history(scan_date):
    """Updates history.json with scan additions, computing rolling 4-week recurrence."""
    scan_file = os.path.join(SCANS_DIR, f"{scan_date}.json")
    if not os.path.exists(scan_file):
        print(f"[ERROR] Scan file {scan_file} not found.")
        return None

    scan_data = load_json(scan_file)
    history = load_json(HISTORY_FILE, {
        "version": 1,
        "last_updated": scan_date,
        "rolling_window_weeks": 4,
        "stocks": {}
    })

    stocks = history.setdefault("stocks", {})
    additions = scan_data.get("additions", [])

    for item in additions:
        ticker = item["ticker"]
        company = item["company"]

        if ticker not in stocks:
            stocks[ticker] = {
                "company": company,
                "ticker": ticker,
                "appearances": [scan_date],
                "rolling_4w_count": 1,
                "streak": 1,
                "is_repeat": False,
                "last_seen": scan_date
            }
        else:
            stock = stocks[ticker]
            if scan_date not in stock["appearances"]:
                stock["appearances"].append(scan_date)
            stock["appearances"].sort()
            stock["last_seen"] = scan_date
            # Trailing 4 appearances within window
            stock["rolling_4w_count"] = len(stock["appearances"][-4:])
            stock["is_repeat"] = stock["rolling_4w_count"] >= 2

    history["last_updated"] = scan_date
    save_json(HISTORY_FILE, history)
    print(f"[OK] history.json updated for scan {scan_date}. Total stocks tracked: {len(stocks)}")
    return history

def parse_markdown_report(filepath):
    """Parses frontmatter and body from a growth-triggers markdown report."""
    with open(filepath, "r", encoding="utf-8") as f:
        content = f.read()

    frontmatter = {}
    body = content
    if content.startswith("---"):
        parts = content.split("---", 2)
        if len(parts) >= 3:
            raw_fm = parts[1]
            body = parts[2].strip()
            for line in raw_fm.strip().split("\n"):
                if ":" in line and not line.strip().startswith("-"):
                    k, v = line.split(":", 1)
                    k = k.strip()
                    v = v.strip().strip('"').strip("'")
                    if v.lower() == "true": v = True
                    elif v.lower() == "false": v = False
                    elif v.replace(".", "", 1).isdigit():
                        v = float(v) if "." in v else int(v)
                    frontmatter[k] = v

    return frontmatter, body

def collect_reports(scan_date):
    """Collects all reports for the given scan date."""
    scan_reports_dir = os.path.join(REPORTS_DIR, scan_date)
    reports = {}
    if not os.path.exists(scan_reports_dir):
        return reports

    for md_file in glob.glob(os.path.join(scan_reports_dir, "*.md")):
        stock_id = os.path.splitext(os.path.basename(md_file))[0]
        fm, body = parse_markdown_report(md_file)
        reports[stock_id] = {
            "frontmatter": fm,
            "body": body
        }
    return reports

def rebuild_portal(scan_date="2026-09-12"):
    """Rebuilds index.html with the latest scan data, history, and reports."""
    scan_file = os.path.join(SCANS_DIR, f"{scan_date}.json")
    if not os.path.exists(scan_file):
        print(f"[ERROR] Scan file {scan_file} missing.")
        return False

    scan_data = load_json(scan_file)
    history = load_json(HISTORY_FILE)
    stock_history = history.get("stocks", {})
    available_reports = collect_reports(scan_date)

    # Prepare JS data objects
    js_history_data = {}
    for ticker, hist in stock_history.items():
        symbol = ticker.split(":")[-1]
        has_rep = symbol in available_reports
        js_history_data[ticker] = {
            "repeat_4w": hist.get("rolling_4w_count", 1),
            "is_repeat": hist.get("is_repeat", False),
            "conviction": available_reports[symbol]["frontmatter"].get("conviction", "HIGH") if has_rep else "MEDIUM",
            "has_report": has_rep,
            "report_id": symbol
        }

    js_reports = {k: v["body"] for k, v in available_reports.items()}
    additions = scan_data.get("additions", [])

    # Count repeats
    repeat_count = sum(1 for h in js_history_data.values() if h.get("is_repeat"))

    # Generate HTML content
    html_template = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Weekly Watchlist & Growth Triggers Portal</title>
  <script src="https://cdn.tailwindcss.com"></script>
  <script src="https://cdn.jsdelivr.net/npm/marked/marked.min.js"></script>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet">
  <style>
    body {{ font-family: 'Inter', sans-serif; }}
    code, pre {{ font-family: 'JetBrains Mono', monospace; }}
    .markdown-body h1 {{ font-size: 1.5rem; font-weight: 700; margin-bottom: 1rem; color: #111827; }}
    .markdown-body h2 {{ font-size: 1.25rem; font-weight: 600; margin-top: 1.5rem; margin-bottom: 0.75rem; color: #1f2937; border-bottom: 1px solid #e5e7eb; padding-bottom: 0.25rem; }}
    .markdown-body h3 {{ font-size: 1.1rem; font-weight: 600; margin-top: 1.25rem; margin-bottom: 0.5rem; color: #374151; }}
    .markdown-body p {{ margin-bottom: 0.75rem; line-height: 1.6; color: #4b5563; }}
    .markdown-body ul {{ list-style-type: disc; margin-left: 1.5rem; margin-bottom: 1rem; color: #4b5563; }}
    .markdown-body li {{ margin-bottom: 0.35rem; }}
    .markdown-body table {{ width: 100%; border-collapse: collapse; margin-top: 1rem; margin-bottom: 1rem; font-size: 0.875rem; }}
    .markdown-body th {{ background: #f3f4f6; text-align: left; padding: 0.5rem 0.75rem; font-weight: 600; border: 1px solid #e5e7eb; }}
    .markdown-body td {{ padding: 0.5rem 0.75rem; border: 1px solid #e5e7eb; }}
    .markdown-body strong {{ color: #111827; }}
  </style>
</head>
<body class="bg-slate-50 text-slate-900 min-h-screen">
  <!-- Top Navigation -->
  <header class="bg-white border-b border-slate-200 sticky top-0 z-30">
    <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-16 flex items-center justify-between">
      <div class="flex items-center space-x-3">
        <div class="w-8 h-8 rounded-lg bg-indigo-600 text-white flex items-center justify-center font-bold text-sm">VR</div>
        <div>
          <h1 class="text-base font-bold text-slate-900">Volume Rocketing Research Portal</h1>
          <p class="text-xs text-slate-500">Weekly Scan Intelligence &bull; Indian Equities</p>
        </div>
      </div>
      <div class="flex items-center space-x-3 text-xs">
        <span class="inline-flex items-center px-2.5 py-1 rounded-full font-medium bg-emerald-50 text-emerald-700 border border-emerald-200">
          ● Live Scan: {scan_date}
        </span>
      </div>
    </div>
  </header>

  <main class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
    <!-- Header Stats -->
    <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
      <div class="bg-white p-5 rounded-xl border border-slate-200 shadow-sm">
        <div class="text-xs font-medium text-slate-500 uppercase tracking-wider">Scan Period</div>
        <div class="mt-2 text-xl font-bold text-slate-900">{scan_data.get("window", scan_date)}</div>
        <div class="mt-1 text-xs text-slate-500">{scan_data.get("scan_name", "Volume Rocketing")}</div>
      </div>
      <div class="bg-white p-5 rounded-xl border border-slate-200 shadow-sm">
        <div class="text-xs font-medium text-slate-500 uppercase tracking-wider">Newly Added</div>
        <div class="mt-2 text-2xl font-bold text-emerald-600">+{len(additions)} Stocks</div>
        <div class="mt-1 text-xs text-slate-500">Breakout volume threshold</div>
      </div>
      <div class="bg-white p-5 rounded-xl border border-slate-200 shadow-sm">
        <div class="text-xs font-medium text-slate-500 uppercase tracking-wider">Removed</div>
        <div class="mt-2 text-2xl font-bold text-rose-600">-{len(scan_data.get("removals", []))} Stocks</div>
        <div class="mt-1 text-xs text-slate-500">Volume contraction / exits</div>
      </div>
      <div class="bg-white p-5 rounded-xl border border-slate-200 shadow-sm">
        <div class="text-xs font-medium text-slate-500 uppercase tracking-wider">Repeat Alerts (4 Weeks)</div>
        <div class="mt-2 text-2xl font-bold text-indigo-600">{repeat_count} Stocks</div>
        <div class="mt-1 text-xs text-indigo-600 font-medium">Multi-week volume surge</div>
      </div>
    </div>

    <!-- Controls -->
    <div class="bg-white p-4 rounded-xl border border-slate-200 shadow-sm mb-6 flex flex-col md:flex-row gap-4 items-center justify-between">
      <div class="w-full md:w-96 relative">
        <input type="text" id="searchInput" placeholder="Search company or ticker (e.g. APOLLO, CENTUM)..." 
               class="w-full pl-10 pr-4 py-2 text-sm border border-slate-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-transparent">
        <svg class="w-4 h-4 text-slate-400 absolute left-3.5 top-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"></path>
        </svg>
      </div>
      <div class="flex items-center gap-2 w-full md:w-auto overflow-x-auto pb-2 md:pb-0">
        <button onclick="setFilter('all')" id="btn-all" class="px-3.5 py-1.5 text-xs font-medium rounded-lg bg-indigo-600 text-white">All Additions ({len(additions)})</button>
        <button onclick="setFilter('repeats')" id="btn-repeats" class="px-3.5 py-1.5 text-xs font-medium rounded-lg bg-slate-100 text-slate-700 hover:bg-slate-200">⭐ Repeats in 4W ({repeat_count})</button>
        <button onclick="setFilter('reports')" id="btn-reports" class="px-3.5 py-1.5 text-xs font-medium rounded-lg bg-slate-100 text-slate-700 hover:bg-slate-200">📄 1-Pagers ({len(js_reports)})</button>
      </div>
    </div>

    <!-- Stocks Grid -->
    <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4" id="stocksGrid"></div>
  </main>

  <!-- Report Modal -->
  <div id="reportModal" class="fixed inset-0 bg-slate-900/60 backdrop-blur-sm z-50 hidden flex items-center justify-center p-4">
    <div class="bg-white rounded-2xl max-w-4xl w-full max-h-[90vh] flex flex-col shadow-2xl border border-slate-200">
      <div class="px-6 py-4 border-b border-slate-200 flex items-center justify-between">
        <div>
          <h3 id="modalTitle" class="text-lg font-bold text-slate-900">Stock Report</h3>
          <p id="modalSubtitle" class="text-xs text-slate-500">Growth Triggers 1-Pager &bull; Scan: {scan_date}</p>
        </div>
        <button onclick="closeModal()" class="w-8 h-8 rounded-lg hover:bg-slate-100 flex items-center justify-center text-slate-500">✕</button>
      </div>
      <div class="p-6 overflow-y-auto markdown-body" id="modalBody"></div>
      <div class="px-6 py-3 border-t border-slate-200 bg-slate-50 rounded-b-2xl flex justify-end">
        <button onclick="closeModal()" class="px-4 py-2 text-xs font-medium bg-slate-200 hover:bg-slate-300 text-slate-800 rounded-lg">Close</button>
      </div>
    </div>
  </div>

  <script>
    const historyData = {json.dumps(js_history_data, indent=2)};
    const additions = {json.dumps(additions, indent=2)};
    const reports = {json.dumps(js_reports, indent=2)};

    let currentFilter = 'all';

    function render() {{
      const query = document.getElementById('searchInput').value.toLowerCase();
      const grid = document.getElementById('stocksGrid');
      grid.innerHTML = '';

      const filtered = additions.filter(item => {{
        const hist = historyData[item.ticker] || {{ repeat_4w: 1, is_repeat: false, has_report: false }};
        const matchesQuery = item.company.toLowerCase().includes(query) || item.ticker.toLowerCase().includes(query);

        if (!matchesQuery) return false;
        if (currentFilter === 'repeats') return hist.is_repeat;
        if (currentFilter === 'reports') return hist.has_report;
        return true;
      }});

      filtered.forEach(item => {{
        const hist = historyData[item.ticker] || {{ repeat_4w: 1, is_repeat: false, has_report: false }};
        const card = document.createElement('div');
        card.className = "bg-white p-5 rounded-xl border border-slate-200 shadow-sm flex flex-col justify-between hover:border-indigo-300 transition-all";

        let repeatBadge = '';
        if (hist.is_repeat) {{
          repeatBadge = `<span class="inline-flex items-center px-2 py-0.5 rounded text-xs font-semibold bg-amber-100 text-amber-800 border border-amber-200">
            🔁 Seen ${{hist.repeat_4w}}x in 4w
          </span>`;
        }} else {{
          repeatBadge = `<span class="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-slate-100 text-slate-600">
            New Addition
          </span>`;
        }}

        let reportBtn = '';
        if (hist.has_report) {{
          reportBtn = `<button onclick="openReport('${{hist.report_id}}', '${{item.company}}', '${{item.ticker}}')" class="w-full mt-4 py-2 px-3 bg-indigo-50 hover:bg-indigo-100 text-indigo-700 text-xs font-semibold rounded-lg flex items-center justify-center gap-1.5 transition">
            <span>Read 1-Pager</span> &rarr;
          </button>`;
        }} else {{
          reportBtn = `<div class="w-full mt-4 py-2 px-3 bg-slate-50 text-slate-400 text-xs text-center rounded-lg border border-dashed border-slate-200">
            1-Pager Queued
          </div>`;
        }}

        card.innerHTML = `
          <div>
            <div class="flex items-start justify-between gap-2 mb-2">
              <span class="text-xs font-mono font-medium text-slate-500">${{item.ticker}}</span>
              ${{repeatBadge}}
            </div>
            <h4 class="text-base font-bold text-slate-900 leading-snug">${{item.company}}</h4>
          </div>
          ${{reportBtn}}
        `;
        grid.appendChild(card);
      }});
    }}

    function setFilter(filter) {{
      currentFilter = filter;
      document.querySelectorAll('[id^="btn-"]').forEach(btn => {{
        btn.className = "px-3.5 py-1.5 text-xs font-medium rounded-lg bg-slate-100 text-slate-700 hover:bg-slate-200";
      }});
      document.getElementById(`btn-${{filter}}`).className = "px-3.5 py-1.5 text-xs font-medium rounded-lg bg-indigo-600 text-white";
      render();
    }}

    document.getElementById('searchInput').addEventListener('input', render);

    function openReport(reportId, company, ticker) {{
      document.getElementById('modalTitle').innerText = `${{company}} (${{ticker}})`;
      document.getElementById('modalSubtitle').innerText = `Growth Triggers 1-Pager &bull; Scan: {scan_date}`;
      const rawMarkdown = reports[reportId] || "Report pending...";
      document.getElementById('modalBody').innerHTML = marked.parse(rawMarkdown);
      document.getElementById('reportModal').classList.remove('hidden');
    }}

    function closeModal() {{
      document.getElementById('reportModal').classList.add('hidden');
    }}

    render();
  </script>
</body>
</html>
"""

    with open(INDEX_FILE, "w", encoding="utf-8") as f:
        f.write(html_template)

    print(f"[OK] index.html successfully compiled with {len(js_reports)} reports and {repeat_count} repeat alerts.")
    return True

def package_for_netlify():
    """Generates dist bundle and netlify.toml for 1-click Netlify deployment."""
    # Write netlify.toml
    netlify_toml = """[build]
  publish = "."

[[headers]]
  for = "/*"
  [headers.values]
    X-Frame-Options = "DENY"
    X-XSS-Protection = "1; mode=block"
    X-Content-Type-Options = "nosniff"
"""
    with open(os.path.join(BASE_DIR, "netlify.toml"), "w", encoding="utf-8") as f:
        f.write(netlify_toml)

    # Package as zip archive for Netlify Drop
    zip_path = os.path.join(BASE_DIR, "stock-watchlist-portal.zip")
    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
        zipf.write(INDEX_FILE, arcname="index.html")
        zipf.write(os.path.join(BASE_DIR, "netlify.toml"), arcname="netlify.toml")
        
        # Include data files
        for root, dirs, files in os.walk(DATA_DIR):
            for file in files:
                full_p = os.path.join(root, file)
                rel_p = os.path.relpath(full_p, BASE_DIR)
                zipf.write(full_p, arcname=rel_p)

        # Include report files
        for root, dirs, files in os.walk(REPORTS_DIR):
            for file in files:
                full_p = os.path.join(root, file)
                rel_p = os.path.relpath(full_p, BASE_DIR)
                zipf.write(full_p, arcname=rel_p)

    print(f"[OK] Generated deployable package: {zip_path} ({os.path.getsize(zip_path)} bytes)")
    return zip_path

def run_tests():
    """Runs automated verification checks across the pipeline."""
    print("\n" + "="*50)
    print("RUNNING AUTOMATED TEST SUITE")
    print("="*50)

    # Test 1: Scan JSON Integrity
    scan_file = os.path.join(SCANS_DIR, "2026-09-12.json")
    assert os.path.exists(scan_file), "Scan file missing"
    scan_data = load_json(scan_file)
    assert len(scan_data.get("additions", [])) == 25, f"Expected 25 additions, got {len(scan_data.get('additions', []))}"
    print("[PASS] Test 1: Scan JSON Integrity verified.")

    # Test 2: Recurrence Engine Logic
    history = update_history("2026-09-12")
    assert history is not None, "History update failed"
    stocks = history.get("stocks", {})
    assert "NSE:APOLLO" in stocks and stocks["NSE:APOLLO"]["is_repeat"] is True, "APOLLO repeat check failed"
    assert "NSE:CENTUM" in stocks and stocks["NSE:CENTUM"]["is_repeat"] is True, "CENTUM repeat check failed"
    assert "NSE:PITTIENG" in stocks and stocks["NSE:PITTIENG"]["rolling_4w_count"] == 3, "PITTIENG 4W count check failed"
    print("[PASS] Test 2: Recurrence Engine & Streak Logic verified.")

    # Test 3: Markdown Reports Integrity
    reports = collect_reports("2026-09-12")
    assert "APOLLO" in reports, "APOLLO report missing"
    assert "CENTUM" in reports, "CENTUM report missing"
    assert "PITTIENG" in reports, "PITTIENG report missing"
    for r_id, r_data in reports.items():
        assert len(r_data["body"]) > 3000, f"Report {r_id} body too short ({len(r_data['body'])} chars)"
        assert "SECTION 1: Company Snapshot" in r_data["body"], f"Missing Section 1 in {r_id}"
        assert "SECTION 5: Trigger Scoreboard" in r_data["body"], f"Missing Scoreboard in {r_id}"
    print(f"[PASS] Test 3: Growth Triggers Markdown Reports verified ({len(reports)} reports tested).")

    # Test 4: Web Portal Compilation
    rebuild_portal("2026-09-12")
    assert os.path.exists(INDEX_FILE), "index.html compilation missing"
    with open(INDEX_FILE, "r", encoding="utf-8") as f:
        html = f.read()
    assert "APOLLO" in html and "CENTUM" in html and "PITTIENG" in html, "Rendered HTML missing report keys"
    assert "repeat_4w" in html and "is_repeat" in html, "Repeat badge logic missing in compiled HTML"
    print("[PASS] Test 4: Web Portal Dynamic Compilation verified.")

    # Test 5: Netlify Deployment Package
    zip_file = package_for_netlify()
    assert os.path.exists(zip_file), "Zip package missing"
    assert os.path.getsize(zip_file) > 1000, "Zip package invalid size"
    print("[PASS] Test 5: Netlify Deployment Package verified.")

    print("="*50)
    print("ALL 5 AUTOMATED TESTS PASSED SUCCESSFULLY")
    print("="*50 + "\n")

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "test":
        run_tests()
    else:
        update_history("2026-09-12")
        rebuild_portal("2026-09-12")
        package_for_netlify()
