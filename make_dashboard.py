import json, html

s = json.load(open('energy_analytics/output/analysis_summary.json', encoding='utf-8'))
t = s['totals']

def rows(items, cols):
    h = '<tr>' + ' '.join(f'<th>{c}</th>' for c in cols) + '</tr>'
    for it in items:
        h += '<tr>' + ' '.join(f'<td>{html.escape(str(it.get(c, "")))}</td>' for c in cols) + '</tr>'
    return h

page = f"""<!doctype html><html><head><meta charset='utf-8'><title>Energy Waste & Peak Demand Analytics</title>
<style>body{{font-family:Segoe UI,Arial,sans-serif;margin:24px;color:#222}} .cards{{display:flex;gap:12px;flex-wrap:wrap}} .card{{border:1px solid #ddd;border-radius:8px;padding:12px 16px;min-width:180px;background:#fafafa}} .v{{font-size:20px;font-weight:700}} table{{border-collapse:collapse;margin:8px 0 20px;width:100%;max-width:1100px}} th,td{{border:1px solid #ddd;padding:6px 8px;font-size:13px;text-align:left}} th{{background:#f3f3f3}} h2{{margin-top:28px}} .small{{color:#555;font-size:12px}}</style></head><body>
<h1>Energy Waste &amp; Peak Demand Analytics</h1>
<p class='small'>Correlated machine telemetry, production output, tariffs and weather (synthetic, seed 20261022). Local generated report.</p>
<div class='cards'>
<div class='card'><div>Total Energy</div><div class='v'>{t['total_kwh']:,.0f} kWh</div></div>
<div class='card'><div>Idle Energy</div><div class='v'>{t['idle_kwh']:,.0f} kWh ({t['idle_share']*100:.1f}%)</div></div>
<div class='card'><div>Peak-Window Energy</div><div class='v'>{t['peak_window_kwh']:,.0f} kWh ({t['peak_share']*100:.1f}%)</div></div>
<div class='card'><div>Est. Energy Cost</div><div class='v'>${t['energy_cost_usd_est']:,.2f}</div></div>
<div class='card'><div>Readings / Batches</div><div class='v'>{t['readings']:,} / {t['batches']:,}</div></div>
<div class='card'><div>Exceptions</div><div class='v'>{s['exceptions_count']}</div></div>
</div>
<p><b>Quality flags:</b> {html.escape(str(t['quality_flag_counts']))} &nbsp; <b>Tariff TZ mismatch:</b> {html.escape(str(t['tariff_timezone_mismatch_tariffs']))}</p>
<h2>Top Idle Machines</h2><table>{rows(s['top_idle_machines'][:10], ['machine_id','kwh','idle_kwh','peak_kwh','cost'])}</table>
<h2>Top Peak Meters</h2><table>{rows(s['top_peak_meters'][:10], ['meter_id','kwh','idle_kwh','peak_kwh','cost'])}</table>
<h2>Energy Intensity by Machine (kWh/unit)</h2><table>{rows(s['energy_intensity_by_machine'][:15], ['machine_id','output_qty','kwh_assigned_to_batches','kwh_per_unit'])}</table>
<h2>Energy vs Temperature Buckets</h2><table>{rows(s['energy_vs_temperature_buckets'], ['temp_bucket','total_kwh','intervals','avg_kwh_per_interval'])}</table>
<h2>Recommendations (traceable baselines &amp; expected savings)</h2><table>{rows(s['recommendations_traceability'], ['recommendation_id','category','target_meter','target_machine','baseline_metric','baseline_value','expected_savings_kwh','expected_savings_usd','status'])}</table>
<h2>Exceptions (sample)</h2><table>{rows(s['exceptions_sample'][:30], ['type','entity','key','detail','decision'])}</table>
<p class='small'>Files: <a href='output/analysis_summary.json'>analysis_summary.json</a> · <a href='output/exceptions.csv'>exceptions.csv</a> · <a href='output/ground_truth.csv'>ground_truth.csv</a> · <a href='data_dictionary.md'>data_dictionary.md</a> · <a href='README.md'>README.md</a> · <a href='raw/'>raw/</a></p>
</body></html>"""

open('energy_analytics/dashboard.html', 'w', encoding='utf-8').write(page)
print('wrote dashboard.html')
