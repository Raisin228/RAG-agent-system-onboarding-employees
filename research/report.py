"""
Генератор HTML-отчёта по результатам оценки RAG-агента.

Использование:
  python report.py results/eval_20250609_123456.json
  python report.py results/eval_20250609_123456.json --open   # открыть в браузере

Атрошенко Б. С.
"""

import argparse
import json
import sys
import webbrowser
from pathlib import Path


def score_color(val: float | None) -> str:
    if val is None:
        return "#888"
    if val >= 0.7:
        return "#22c55e"
    if val >= 0.4:
        return "#f59e0b"
    return "#ef4444"


def ms_color(ms: float | None) -> str:
    if ms is None:
        return "#888"
    if ms < 3000:
        return "#22c55e"
    if ms < 8000:
        return "#f59e0b"
    return "#ef4444"


def avg(lst):
    return sum(lst) / len(lst) if lst else 0.0


def build_html(report: dict) -> str:
    results = report["results"]
    ts = report.get("timestamp", "—")
    api = report.get("api_url", "—")

    kb = [r for r in results if r.get("expected_intent") == "knowledge_base" and not r.get("error")]
    trap = [r for r in results if r.get("category") == "hallucination_trap" and not r.get("error")]
    errors = [r for r in results if r.get("error")]

    rel_vals = [r["relevance_score"] for r in kb if r.get("relevance_score") is not None]
    fact_kb = [r["factual_score"] for r in kb]
    ttft_all = [r["ttft_ms"] for r in results if r.get("ttft_ms")]
    total_all = [r["total_ms"] for r in results if r.get("total_ms") and not r.get("error")]
    hall_trap = sum(1 for r in trap if r.get("is_hallucination"))
    hall_other = sum(1 for r in results if r.get("is_hallucination") and r.get("category") != "hallucination_trap")

    avg_factual = avg(fact_kb)
    avg_rel = avg(rel_vals)
    avg_ttft = avg(ttft_all)
    avg_total = avg(total_all)

    categories = ["small_talk", "easy_factual", "medium", "complex", "hallucination_trap"]
    cat_rows = ""
    for cat in categories:
        cat_res = [r for r in results if r.get("category") == cat and not r.get("error")]
        if not cat_res:
            continue
        f = avg([r["factual_score"] for r in cat_res])
        rv = avg([r["relevance_score"] for r in cat_res if r.get("relevance_score") is not None])
        rv_str = f"{rv:.2f}" if any(r.get("relevance_score") is not None for r in cat_res) else "—"
        h = sum(1 for r in cat_res if r.get("is_hallucination"))
        cat_rows += f"""
        <tr>
          <td>{cat}</td>
          <td>{len(cat_res)}</td>
          <td style="color:{score_color(f)};font-weight:bold">{f:.2f}</td>
          <td style="color:{score_color(avg([r['relevance_score'] for r in cat_res if r.get('relevance_score') is not None]) if any(r.get('relevance_score') is not None for r in cat_res) else None)}">{rv_str}</td>
          <td style="color:{'#ef4444' if h > 0 else '#22c55e'}">{h}</td>
        </tr>"""

    rows = ""
    for r in results:
        f = r.get("factual_score", 0)
        rel = r.get("relevance_score")
        rel_str = f"{rel:.2f}" if rel is not None else "—"
        hall = "⚠" if r.get("is_hallucination") else "✓"
        hall_color = "#ef4444" if r.get("is_hallucination") else "#22c55e"
        ttft = r.get("ttft_ms")
        ttft_str = f"{ttft:.0f}ms" if ttft else "—"
        total = r.get("total_ms", 0)
        err = r.get("error", "")
        answer_preview = (r.get("answer") or err or "")[:300].replace("<", "&lt;").replace(">", "&gt;")
        docs_str = ", ".join(r.get("retrieved_doc_names", [])[:4])

        rows += f"""
        <tr>
          <td>{r['id']}</td>
          <td><span class="cat cat-{r['category']}">{r['category']}</span></td>
          <td class="q-text">{r['question'][:80]}</td>
          <td style="color:{score_color(f)};font-weight:bold">{f:.2f}</td>
          <td style="color:{score_color(rel) if rel is not None else '#888'}">{rel_str}</td>
          <td style="color:{hall_color};font-weight:bold">{hall}</td>
          <td style="color:{ms_color(ttft)}">{ttft_str}</td>
          <td style="color:{ms_color(total)}">{total:.0f}ms</td>
          <td class="answer-text">{answer_preview}{'...' if len(r.get('answer', '')) > 300 else ''}</td>
          <td class="docs-text">{docs_str}</td>
        </tr>"""

    return f"""<!DOCTYPE html>
<html lang="ru">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>RAG Evaluation Report — FinBridge</title>
<style>
  * {{ box-sizing: border-box; }}
  body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
         background: #0f172a; color: #e2e8f0; margin: 0; padding: 24px; font-size: 14px; }}
  h1 {{ color: #f1f5f9; font-size: 24px; margin-bottom: 4px; }}
  .meta {{ color: #64748b; font-size: 13px; margin-bottom: 24px; }}
  .grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 12px; margin-bottom: 32px; }}
  .card {{ background: #1e293b; border: 1px solid #334155; border-radius: 10px; padding: 16px; }}
  .card-label {{ color: #94a3b8; font-size: 12px; text-transform: uppercase; letter-spacing: .06em; margin-bottom: 6px; }}
  .card-value {{ font-size: 28px; font-weight: 700; }}
  h2 {{ color: #94a3b8; font-size: 16px; text-transform: uppercase; letter-spacing: .05em; margin: 24px 0 12px; }}
  table {{ width: 100%; border-collapse: collapse; background: #1e293b; border-radius: 10px; overflow: hidden; }}
  th {{ background: #0f172a; color: #94a3b8; padding: 10px 12px; text-align: left; font-size: 12px; text-transform: uppercase; }}
  td {{ padding: 8px 12px; border-bottom: 1px solid #1e293b; vertical-align: top; }}
  tr:hover td {{ background: #263348; }}
  .q-text {{ max-width: 240px; color: #cbd5e1; }}
  .answer-text {{ max-width: 320px; font-size: 12px; color: #94a3b8; }}
  .docs-text {{ max-width: 200px; font-size: 12px; color: #64748b; }}
  .cat {{ display: inline-block; padding: 2px 8px; border-radius: 4px; font-size: 11px; font-weight: 600; }}
  .cat-small_talk {{ background: #1e3a5f; color: #93c5fd; }}
  .cat-easy_factual {{ background: #14532d; color: #86efac; }}
  .cat-medium {{ background: #713f12; color: #fde68a; }}
  .cat-complex {{ background: #4c1d95; color: #c4b5fd; }}
  .cat-hallucination_trap {{ background: #7f1d1d; color: #fca5a5; }}
</style>
</head>
<body>
<h1>RAG Evaluation Report — FinBridge</h1>
<div class="meta">Дата: {ts} | API: {api} | Вопросов: {len(results)} (ошибок: {len(errors)})</div>

<div class="grid">
  <div class="card">
    <div class="card-label">Factual Score (avg)</div>
    <div class="card-value" style="color:{score_color(avg_factual)}">{avg_factual:.2f}</div>
  </div>
  <div class="card">
    <div class="card-label">Relevance Recall (avg)</div>
    <div class="card-value" style="color:{score_color(avg_rel)}">{avg_rel:.2f}</div>
  </div>
  <div class="card">
    <div class="card-label">Hallucination Rate (trap)</div>
    <div class="card-value" style="color:{score_color(1 - hall_trap / len(trap)) if trap else '#888'}">{hall_trap}/{len(trap)}</div>
  </div>
  <div class="card">
    <div class="card-label">TTFT (avg)</div>
    <div class="card-value" style="color:{ms_color(avg_ttft)}">{avg_ttft:.0f}ms</div>
  </div>
  <div class="card">
    <div class="card-label">Total Time (avg)</div>
    <div class="card-value" style="color:{ms_color(avg_total)}">{avg_total:.0f}ms</div>
  </div>
  <div class="card">
    <div class="card-label">Other Hallucinations</div>
    <div class="card-value" style="color:{'#ef4444' if hall_other > 0 else '#22c55e'}">{hall_other}</div>
  </div>
</div>

<h2>По категориям</h2>
<table>
  <thead>
    <tr><th>Категория</th><th>N</th><th>Factual</th><th>Relevance</th><th>Hallucinations</th></tr>
  </thead>
  <tbody>{cat_rows}</tbody>
</table>

<h2>Детальные результаты</h2>
<table>
  <thead>
    <tr>
      <th>#</th><th>Категория</th><th>Вопрос</th>
      <th>Factual</th><th>Relevance</th><th>Hall</th>
      <th>TTFT</th><th>Total</th><th>Ответ</th><th>Источники</th>
    </tr>
  </thead>
  <tbody>{rows}</tbody>
</table>
</body>
</html>"""


def main():
    parser = argparse.ArgumentParser(description="Генератор HTML-отчёта по оценке RAG-агента")
    parser.add_argument("results_json", help="Путь к JSON-файлу результатов")
    parser.add_argument("--open", action="store_true", help="Открыть отчёт в браузере")
    args = parser.parse_args()

    path = Path(args.results_json)
    if not path.exists():
        print(f"Файл не найден: {path}")
        sys.exit(1)

    with open(path, encoding="utf-8") as f:
        report = json.load(f)

    html = build_html(report)
    out = path.with_suffix(".html")
    with open(out, "w", encoding="utf-8") as f:
        f.write(html)

    print(f"Отчёт сохранён: {out}")
    if args.open:
        webbrowser.open(f"file://{out.resolve()}")


if __name__ == "__main__":
    main()
