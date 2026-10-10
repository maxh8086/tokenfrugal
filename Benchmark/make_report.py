"""Render a bench JSON (realworld section) to a self-contained HTML bar chart: python Benchmark/make_report.py bench/X.json"""
import json, sys, html
d = json.load(open(sys.argv[1], encoding="utf-8"))
rw = d["results"]["realworld"]
rows = []
for k, v in rw.items():
    a, b = map(int, v["verified"].split("/"))
    pct = 100 * a / b
    col = "#2e9e5b" if a == b else ("#d9a021" if a else "#d0453b")
    rows.append(f'<tr><td>{html.escape(k)}</td><td class="bar"><div style="width:{pct:.0f}%;background:{col}"></div></td>'
                f'<td>{v["verified"]}</td><td>{v["s"]["p50"]}s</td></tr>')
tot = sum(int(v["verified"].split("/")[0]) for v in rw.values()); n = sum(int(v["verified"].split("/")[1]) for v in rw.values())
open(sys.argv[2], "w", encoding="utf-8").write(f"""<!doctype html><meta charset=utf-8><title>TokenFrugal benchmark</title>
<style>body{{font:15px system-ui;margin:24px;width:760px;background:#fff;color:#222}}table{{border-collapse:collapse;width:100%}}
td{{padding:5px 8px;border-bottom:1px solid #eee}}.bar{{width:380px;background:#f2f2f2}}.bar div{{height:16px}}</style>
<h2>TokenFrugal real-world benchmark ({d['tag']}, n={d['n']}): {tot}/{n} verified ({100*tot//n}%)</h2>
<table><tr><th align=left>case</th><th align=left>verified</th><th></th><th>p50</th></tr>{''.join(rows)}</table>""")
