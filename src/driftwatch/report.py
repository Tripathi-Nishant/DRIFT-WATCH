"""Self-contained offline HTML report renderer."""

from __future__ import annotations

import html
import json
from typing import Any


def _histogram(item: dict[str, Any]) -> str:
    metrics = item.get("metrics") or {}
    reference = metrics.get("reference_histogram")
    current = metrics.get("current_histogram")
    if not reference or not current:
        return "<span class='muted'>No numeric histogram available</span>"
    maximum = max(max(reference), max(current), 1)
    bars = []
    for before, after in zip(reference, current):
        before_height = max(3, before / maximum * 48)
        after_height = max(3, after / maximum * 48)
        bars.append(
            f"<span class='bar-pair'><i class='bar ref' style='height:{before_height:.1f}px'></i>"
            f"<i class='bar cur' style='height:{after_height:.1f}px'></i></span>"
        )
    return (
        "<span class='histogram'>"
        + "".join(bars)
        + "</span><small class='muted'>ref / current</small>"
    )


def render_html(report: dict[str, Any]) -> str:
    summary = report["summary"]
    rows = "".join(
        f"<tr><td><b>{html.escape(item['name'])}</b>"
        f"<small>{html.escape(item.get('explanation', ''))}</small></td>"
        f"<td>{item['kind']}</td><td>{item['drift_score']:.3f}</td>"
        f"<td><span class='pill {str(item['drifted']).lower()}'>"
        f"{'Drift detected' if item['drifted'] else 'Within range'}</span></td>"
        f"<td>{_histogram(item)}</td>"
        f"<td><code>{html.escape(json.dumps(item.get('metrics', {}), sort_keys=True))}</code></td></tr>"
        for item in report.get("features", [])
    )
    findings = (
        "".join(
            f"<li><b>{html.escape(item.get('severity', 'INFO'))}</b> — "
            f"{html.escape(item['message'])}</li>"
            for item in report.get("quality", {}).get("findings", [])
        )
        or "<li>No quality findings.</li>"
    )
    performance = (
        json.dumps(report.get("performance"), indent=2)
        if report.get("performance")
        else "No labels supplied for this run."
    )
    impact = (
        json.dumps(summary.get("impact_estimate"), indent=2)
        if summary.get("impact_estimate")
        else "No business assumptions supplied; impact is not estimated."
    )
    multivariate = json.dumps(report.get("multivariate"), indent=2)
    subgroups = json.dumps(report.get("subgroups", {}), indent=2)
    quality_metrics = json.dumps(report.get("quality_metrics", {}), indent=2)
    text_report = json.dumps(report.get("text_metrics", {}), indent=2)
    advanced_report = json.dumps(
        {
            key: report[key]
            for key in (
                "semantic_text",
                "image_metrics",
                "ranking_metrics",
                "llm_metrics",
                "rag_metrics",
            )
            if key in report
        },
        indent=2,
    )
    tests = report.get("tests", [])
    test_rows = (
        "".join(
            f"<tr><td>{html.escape(item['id'])}</td><td>{html.escape(item['description'])}</td>"
            f"<td><span class='pill {str(not item['passed']).lower()}'>{'PASS' if item['passed'] else 'FAIL'}</span></td>"
            f"<td>{item.get('value')}</td><td>{item.get('threshold')}</td></tr>"
            for item in tests
        )
        or "<tr><td colspan='5'>No assertions configured.</td></tr>"
    )
    payload = json.dumps(report, indent=2).replace("</", "<\\/")
    return f"""<!doctype html>
<html><head><meta charset="utf-8"><title>DriftWatch report</title>
<style>
body{{font:15px system-ui;margin:40px auto;max-width:1350px;color:#202132;background:#fafafd}}
header,.card{{background:#fff;border:1px solid #e8e8ef;border-radius:14px;padding:24px;margin-bottom:18px}}
h1{{margin:0 0 4px}}h2{{font-size:18px}}.muted{{color:#777}}small{{display:block;color:#777;margin-top:4px}}
.summary{{display:flex;gap:12px;flex-wrap:wrap}}.metric{{background:#f5f3ff;padding:16px;border-radius:10px;min-width:130px}}
.metric b{{display:block;font-size:25px}}table{{width:100%;border-collapse:collapse}}
th,td{{padding:12px;text-align:left;border-bottom:1px solid #eee;vertical-align:top}}
th{{font-size:10px;color:#999;text-transform:uppercase}}code{{font-size:10px;word-break:break-word;color:#666}}
.pill{{padding:4px 8px;border-radius:5px;background:#eaf7ef;color:#258255;font-size:12px;white-space:nowrap}}
.pill.true{{background:#fff0f1;color:#c14d5c}}li{{margin:8px 0}}
.histogram{{display:flex;align-items:end;gap:2px;height:52px;min-width:120px;border-bottom:1px solid #ddd}}
.bar-pair{{display:flex;align-items:end;gap:1px;height:50px}}.bar{{display:block;width:5px;border-radius:2px 2px 0 0}}
.bar.ref{{background:#bdb2ff}}.bar.cur{{background:#e27783}}
pre{{background:#171827;color:#e9e9f3;padding:16px;border-radius:9px;overflow:auto}}
</style></head><body>
<header><p class="muted">DRIFTWATCH OFFLINE REPORT</p>
<h1>{html.escape(summary.get("model", "model"))}</h1>
<p class="muted">Decision: <b>{summary["decision"]}</b> · Severity: <b>{summary["severity"]}</b> · Confidence: <b>{summary.get("confidence", "UNKNOWN")}</b></p>
<p>{html.escape(summary["recommendation"])}</p></header>
<section class="summary"><div class="metric"><b>{summary["drifted_features"]}</b> drifted features</div>
<div class="metric"><b>{summary["quality_score"]}</b> quality score</div>
<div class="metric"><b>{summary["reference_rows"]}</b> reference rows</div>
<div class="metric"><b>{summary["current_rows"]}</b> current rows</div></section>
<section class="card"><h2>Feature drift and distributions</h2>
<table><thead><tr><th>Feature</th><th>Type</th><th>Score</th><th>Status</th><th>Distribution</th><th>Statistics</th></tr></thead>
<tbody>{rows}</tbody></table></section>
<section class="card"><h2>Data quality</h2><p>Score: <b>{report.get("quality", {}).get("score", summary["quality_score"])}</b></p><ul>{findings}</ul></section>
<section class="card"><h2>Metric families</h2><h3>Dataset and column quality</h3><pre>{html.escape(quality_metrics)}</pre><h3>Text statistics</h3><pre>{html.escape(text_report)}</pre></section>
<section class="card"><h2>Advanced-domain monitoring</h2><pre>{html.escape(advanced_report or "No advanced-domain inputs supplied.")}</pre></section>
<section class="card"><h2>Monitoring tests</h2><table><thead><tr><th>Test</th><th>Description</th><th>Result</th><th>Value</th><th>Threshold</th></tr></thead><tbody>{test_rows}</tbody></table></section>
<section class="card"><h2>Joint and subgroup drift</h2><h3>Domain classifier</h3><pre>{html.escape(multivariate)}</pre><h3>Subgroups</h3><pre>{html.escape(subgroups)}</pre></section>
<section class="card"><h2>Decision trace</h2><p>Recommendation: <b>{summary.get("recommendation_type", "UNSPECIFIED")}</b></p><pre>{html.escape(json.dumps(summary.get("rule_trace", []), indent=2))}</pre></section>
<section class="card"><h2>Performance</h2><pre>{html.escape(performance)}</pre></section>
<section class="card"><h2>Business impact</h2><pre>{html.escape(impact)}</pre></section>
<section class="card"><h2>Caveat</h2><p>{html.escape(summary["honesty_note"])}</p></section>
<details><summary>Raw JSON</summary><pre>{html.escape(payload)}</pre></details></body></html>"""
