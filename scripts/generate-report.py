#!/usr/bin/env python3
"""
Generates HTML QA report from qa-result.json and updates index.html dashboard.
"""

import json
import sys
import os
import re
from datetime import datetime


def grade_color(grade):
    colors = {"A": "#22c55e", "B": "#3b82f6", "C": "#f59e0b", "D": "#f97316", "F": "#ef4444"}
    return colors.get(grade, "#94a3b8")


def grade_css_class(grade):
    return f"grade-{grade.lower()}"


def bar_color(score, max_score):
    pct = (score / max_score) * 100 if max_score else 0
    if pct >= 90: return "fill-green"
    if pct >= 70: return "fill-blue"
    if pct >= 50: return "fill-yellow"
    return "fill-red"


def generate_html_report(result, plugin_name, version, author):
    score = result["score"]
    max_score = result["max"]
    grade = result["grade"]
    date = result["date"]
    cats = result["categories"]

    checks_html = ""
    for cat_key, cat_data in cats.items():
        cat_label = cat_key.replace("_", " ").title()
        cat_score = cat_data["score"]
        cat_max = cat_data["max"]

        rows = ""
        for i, check in enumerate(cat_data["checks"], 1):
            badge_class = "badge-pass" if check["status"] == "PASS" else "badge-fail"
            rows += f"""            <tr><td>{i}</td><td>{check['name']}</td><td><span class="badge {badge_class}">{check['status']}</span></td><td>{check['details']}</td></tr>\n"""

        checks_html += f"""
    <h2>{cat_label} &mdash; {cat_score} / {cat_max}</h2>
    <table>
        <thead><tr><th>#</th><th>Check</th><th>Status</th><th>Details</th></tr></thead>
        <tbody>
{rows}        </tbody>
    </table>
"""

    pct = lambda s, m: int((s / m) * 100) if m else 0

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Shopware QA Report — {plugin_name}</title>
    <style>
        :root {{ --pass: #22c55e; --fail: #ef4444; --warn: #f59e0b; --bg: #0f172a; --card: #1e293b; --text: #e2e8f0; --muted: #94a3b8; --border: #334155; }}
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{ font-family: 'Segoe UI', system-ui, sans-serif; background: var(--bg); color: var(--text); line-height: 1.6; padding: 2rem; }}
        .container {{ max-width: 960px; margin: 0 auto; }}
        h2 {{ font-size: 1.2rem; margin: 2rem 0 1rem; padding-bottom: 0.5rem; border-bottom: 1px solid var(--border); }}
        .header {{ display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 2rem; padding: 1.5rem; background: var(--card); border-radius: 12px; border: 1px solid var(--border); }}
        .header-left h1 {{ color: #fff; font-size: 1.5rem; }}
        .header-left .meta {{ color: var(--muted); font-size: 0.85rem; margin-top: 0.5rem; }}
        .header-left .meta span {{ margin-right: 1.5rem; }}
        .grade-badge {{ width: 80px; height: 80px; border-radius: 50%; display: flex; align-items: center; justify-content: center; font-size: 2.5rem; font-weight: 700; color: #fff; background: {grade_color(grade)}; flex-shrink: 0; }}
        .score-text {{ text-align: center; margin-top: 0.5rem; font-size: 0.85rem; color: var(--muted); }}
        .categories {{ display: grid; grid-template-columns: 1fr 1fr; gap: 1rem; margin-bottom: 2rem; }}
        .cat-card {{ background: var(--card); border-radius: 8px; padding: 1rem 1.25rem; border: 1px solid var(--border); }}
        .cat-card .cat-label {{ display: flex; justify-content: space-between; font-size: 0.85rem; margin-bottom: 0.5rem; }}
        .cat-card .cat-label span:last-child {{ color: var(--muted); }}
        .progress-bar {{ height: 8px; background: var(--border); border-radius: 4px; overflow: hidden; }}
        .progress-bar .fill {{ height: 100%; border-radius: 4px; }}
        .fill-green {{ background: var(--pass); }} .fill-blue {{ background: #3b82f6; }} .fill-yellow {{ background: var(--warn); }} .fill-red {{ background: var(--fail); }}
        table {{ width: 100%; border-collapse: collapse; font-size: 0.85rem; margin-bottom: 1.5rem; }}
        th {{ text-align: left; padding: 0.6rem 0.75rem; background: var(--card); color: var(--muted); font-weight: 600; border-bottom: 1px solid var(--border); }}
        td {{ padding: 0.6rem 0.75rem; border-bottom: 1px solid var(--border); vertical-align: top; }}
        tr:hover td {{ background: rgba(255,255,255,0.02); }}
        .badge {{ display: inline-block; padding: 0.15rem 0.5rem; border-radius: 4px; font-size: 0.75rem; font-weight: 600; }}
        .badge-pass {{ background: rgba(34,197,94,0.15); color: var(--pass); }} .badge-fail {{ background: rgba(239,68,68,0.15); color: var(--fail); }}
        .footer {{ text-align: center; margin-top: 2rem; padding-top: 1.5rem; border-top: 1px solid var(--border); color: var(--muted); font-size: 0.8rem; }}
        @media (max-width: 640px) {{ .categories {{ grid-template-columns: 1fr; }} .header {{ flex-direction: column; align-items: center; text-align: center; }} }}
    </style>
</head>
<body>
<div class="container">
    <div class="header">
        <div class="header-left">
            <h1>{plugin_name}</h1>
            <div class="meta">
                <span>Version: {version}</span>
                <span>Shopware: 6.7+</span>
                <span>Date: {date}</span>
            </div>
            <div class="meta" style="margin-top:0.25rem">
                <span>Author: {author}</span>
                <span>Type: shopware-platform-plugin</span>
            </div>
        </div>
        <div>
            <div class="grade-badge">{grade}</div>
            <div class="score-text">{score} / {max_score}</div>
        </div>
    </div>

    <div class="categories">
        <div class="cat-card">
            <div class="cat-label"><span>Extension Structure</span><span>{cats['extension_structure']['score']} / {cats['extension_structure']['max']}</span></div>
            <div class="progress-bar"><div class="fill {bar_color(cats['extension_structure']['score'], cats['extension_structure']['max'])}" style="width:{pct(cats['extension_structure']['score'], cats['extension_structure']['max'])}%"></div></div>
        </div>
        <div class="cat-card">
            <div class="cat-label"><span>Store Review</span><span>{cats['store_review']['score']} / {cats['store_review']['max']}</span></div>
            <div class="progress-bar"><div class="fill {bar_color(cats['store_review']['score'], cats['store_review']['max'])}" style="width:{pct(cats['store_review']['score'], cats['store_review']['max'])}%"></div></div>
        </div>
        <div class="cat-card">
            <div class="cat-label"><span>Deprecated APIs</span><span>{cats['deprecated_apis']['score']} / {cats['deprecated_apis']['max']}</span></div>
            <div class="progress-bar"><div class="fill {bar_color(cats['deprecated_apis']['score'], cats['deprecated_apis']['max'])}" style="width:{pct(cats['deprecated_apis']['score'], cats['deprecated_apis']['max'])}%"></div></div>
        </div>
        <div class="cat-card">
            <div class="cat-label"><span>Coding Standards</span><span>{cats['coding_standards']['score']} / {cats['coding_standards']['max']}</span></div>
            <div class="progress-bar"><div class="fill {bar_color(cats['coding_standards']['score'], cats['coding_standards']['max'])}" style="width:{pct(cats['coding_standards']['score'], cats['coding_standards']['max'])}%"></div></div>
        </div>
    </div>

{checks_html}

    <div class="footer">
        Generated by Shopware QA Audit &mdash; {date} &mdash; {plugin_name} {version}
    </div>
</div>
</body>
</html>"""
    return html


def update_index(index_path, plugin_name, score, max_score, grade, date, report_filename, repo_url, version):
    content = open(index_path).read()

    # Check if plugin row already exists
    if plugin_name in content:
        # Update existing row
        pattern = rf'(<tr>\s*<td>{re.escape(plugin_name)}</td>.*?</tr>)'
        new_row = f"""<tr>
                <td>{plugin_name}</td>
                <td>Plugin</td>
                <td>{date}</td>
                <td><span class="version">{version}</span></td>
                <td><span class="compat">6.7+</span></td>
                <td>{score}/{max_score}</td>
                <td><span class="grade {grade_css_class(grade)}">{grade}</span></td>
                <td><a class="view-link" href="{report_filename}">View report</a></td>
                <td><a class="view-link" href="{repo_url}" target="_blank">View repo</a></td>
            </tr>"""
        content = re.sub(pattern, new_row, content, flags=re.DOTALL)
    else:
        # Add new row before </tbody>
        new_row = f"""            <tr>
                <td>{plugin_name}</td>
                <td>Plugin</td>
                <td>{date}</td>
                <td><span class="version">{version}</span></td>
                <td><span class="compat">6.7+</span></td>
                <td>{score}/{max_score}</td>
                <td><span class="grade {grade_css_class(grade)}">{grade}</span></td>
                <td><a class="view-link" href="{report_filename}">View report</a></td>
                <td><a class="view-link" href="{repo_url}" target="_blank">View repo</a></td>
            </tr>"""
        content = content.replace("        </tbody>", new_row + "\n        </tbody>")

    with open(index_path, 'w') as f:
        f.write(content)


def main():
    if len(sys.argv) < 2:
        print("Usage: generate-report.py <qa-result.json> [--plugin-name NAME] [--version VER] [--author AUTH] [--repo-url URL] [--index-path PATH]")
        sys.exit(1)

    result_file = sys.argv[1]
    with open(result_file) as f:
        result = json.load(f)

    # Parse args
    args = sys.argv[2:]
    plugin_name = "Unknown"
    version = "1.0.0"
    author = "iCreativetechnologies"
    repo_url = ""
    index_path = ""

    i = 0
    while i < len(args):
        if args[i] == "--plugin-name" and i + 1 < len(args):
            plugin_name = args[i + 1]; i += 2
        elif args[i] == "--version" and i + 1 < len(args):
            version = args[i + 1]; i += 2
        elif args[i] == "--author" and i + 1 < len(args):
            author = args[i + 1]; i += 2
        elif args[i] == "--repo-url" and i + 1 < len(args):
            repo_url = args[i + 1]; i += 2
        elif args[i] == "--index-path" and i + 1 < len(args):
            index_path = args[i + 1]; i += 2
        else:
            i += 1

    date = result["date"]
    score = result["score"]
    max_score = result["max"]
    grade = result["grade"]

    # Generate report filename
    safe_name = plugin_name.lower().replace("_", "-").replace(" ", "-")
    report_filename = f"SHOPWARE-QA-REPORT-{safe_name}-{date.replace('-', '')}.html"

    # Generate HTML report
    html = generate_html_report(result, plugin_name, version, author)
    with open(report_filename, 'w') as f:
        f.write(html)
    print(f"Report generated: {report_filename}")

    # Update index if path provided
    if index_path and os.path.exists(index_path):
        update_index(index_path, plugin_name, score, max_score, grade, date, report_filename, repo_url, version)
        print(f"Index updated: {index_path}")

    print(f"Score: {score}/{max_score} Grade: {grade}")


if __name__ == "__main__":
    main()
