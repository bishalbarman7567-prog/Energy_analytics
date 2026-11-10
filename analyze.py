import csv
import json
from collections import defaultdict
from datetime import datetime
from pathlib import Path


def read_csv(path):
    with Path(path).open(newline='', encoding='utf-8') as f:
        return list(csv.DictReader(f))


def parse_ts(s):
    # keep naive local for comparisons
    try:
        return datetime.fromisoformat(s)
    except Exception:
        return None


def main(raw_dir='energy_analytics/raw', out_dir='energy_analytics/output'):
    raw = Path(raw_dir); out = Path(out_dir); out.mkdir(parents=True, exist_ok=True)
    readings = read_csv(raw/'EnergyReading.csv')
    batches = read_csv(raw/'ProductionBatch.csv')
    tariffs = {t['tariff_id']: t for t in read_csv(raw/'Tariff.csv')}
    weather = read_csv(raw/'WeatherObservation.csv')
    machines = {m['machine_id']: m for m in read_csv(raw/'Machine.csv')}
    meters = {m['meter_id']: m for m in read_csv(raw/'Meter.csv')}
    totals = read_csv(raw/'MeterDailyTotal.csv')

    # Cost calculation with tariff interval correctness (flag tz mismatch)
    tz_mismatch_tariffs = [tid for tid,t in tariffs.items() if t.get('timezone') and t['timezone'] != 'America/Chicago']
    energy_cost = 0.0
    peak_kwh = 0.0
    idle_kwh = 0.0
    total_kwh = 0.0
    by_machine = defaultdict(lambda: {"kwh":0.0,"idle_kwh":0.0,"peak_kwh":0.0,"cost":0.0})
    by_meter = defaultdict(lambda: {"kwh":0.0,"idle_kwh":0.0,"peak_kwh":0.0,"cost":0.0})
    quality_counts = defaultdict(int)
    for r in readings:
        try: kwh = float(r['kwh'])
        except: kwh = 0.0
        q = r.get('quality_flag','')
        quality_counts[q] += 1
        total_kwh += kwh
        tid = r.get('tariff_id','')
        rate = float(tariffs[tid]['rate_per_kwh']) if tid in tariffs else 0.0
        cost = kwh * rate
        energy_cost += cost
        if r.get('is_idle','').lower()=='true': idle_kwh += kwh
        if r.get('is_peak_window','').lower()=='true': peak_kwh += kwh
        mid = r.get('machine_id') or 'UNATTRIBUTED'
        met = r.get('meter_id') or 'UNKNOWN'
        by_machine[mid]["kwh"] += kwh; by_machine[mid]["cost"] += cost
        by_meter[met]["kwh"] += kwh; by_meter[met]["cost"] += cost
        if r.get('is_idle','').lower()=='true':
            by_machine[mid]["idle_kwh"] += kwh; by_meter[met]["idle_kwh"] += kwh
        if r.get('is_peak_window','').lower()=='true':
            by_machine[mid]["peak_kwh"] += kwh; by_meter[met]["peak_kwh"] += kwh

    # Intensity normalized by output per batch/machine (use completed batches with output>0)
    batch_output = defaultdict(float)
    batch_energy = defaultdict(float)
    reading_by_batch = defaultdict(float)
    for r in readings:
        b = r.get('batch_id','')
        if b:
            try: reading_by_batch[b] += float(r['kwh'])
            except: pass
    for b in batches:
        if b.get('status') == 'completed':
            try: outq = float(b.get('output_qty') or 0)
            except: outq = 0.0
            if outq > 0:
                batch_output[b['machine_id']] += outq
                batch_energy[b['machine_id']] += reading_by_batch.get(b['batch_id'], 0.0)
    intensity = []
    for mid, outq in batch_output.items():
        kwh = batch_energy.get(mid, 0.0)
        intensity.append({
            'machine_id': mid,
            'output_qty': round(outq,3),
            'kwh_assigned_to_batches': round(kwh,3),
            'kwh_per_unit': round(kwh/outq,6) if outq else None
        })
    intensity.sort(key=lambda x: (x['kwh_per_unit'] or 0), reverse=True)

    # Exceptions / decisions
    exceptions = []
    for row in totals:
        if str(row.get('reconciles','')).lower() == 'false':
            exceptions.append({
                'type':'reconciliation_mismatch','entity':'MeterDailyTotal','key':f"{row['meter_id']}|{row['day']}",
                'detail':f"reported {row['reported_total_kwh']} vs interval sum {row['interval_sum_kwh']}",
                'decision':'use_interval_sum_with_investigation'
            })
    for r in readings:
        if r.get('quality_flag') in ('unit_confusion','duplicate','hierarchy_mismatch'):
            exceptions.append({'type':r['quality_flag'],'entity':'EnergyReading','key':r['reading_id'],'detail':'labelled data quality issue','decision':'quarantine_or_correct_per_ground_truth'})
        # runtime hierarchy check
        mid = r.get('machine_id',''); met = r.get('meter_id','')
        if mid and mid in machines and met in meters:
            if machines[mid]['meter_id'] != met and r.get('quality_flag')!='hierarchy_mismatch':
                exceptions.append({'type':'hierarchy_inconsistency','entity':'EnergyReading','key':r['reading_id'],'detail':f'machine {mid} not under meter {met}','decision':'review_hierarchy'})
    if tz_mismatch_tariffs:
        for tid in tz_mismatch_tariffs:
            exceptions.append({'type':'tariff_timezone_mismatch','entity':'Tariff','key':tid,'detail':'tariff timezone differs from plant timezone','decision':'normalize_timezone_before_costing'})

    # Traceability: recommendations citing measurable baselines/expected savings
    recs = read_csv(raw/'Recommendation.csv')
    rec_trace = []
    for r in recs:
        rec_trace.append({
            'recommendation_id': r['recommendation_id'],
            'category': r['category'],
            'target_meter': r.get('meter_id',''),
            'target_machine': r.get('machine_id',''),
            'baseline_metric': r['baseline_metric'],
            'baseline_value': r['baseline_value'],
            'expected_savings_kwh': r['expected_savings_kwh'],
            'expected_savings_usd': r['expected_savings_usd'],
            'rationale': r['rationale'],
            'status': r['status']
        })

    # Correlation summaries (energy vs weather/production proxies)
    # simple: avg kwh by temperature bucket
    # map weather by plant-hour
    wmap = {}
    for w in weather:
        ts = parse_ts(w['timestamp_local'])
        if ts: wmap[ts.replace(minute=0, second=0, microsecond=0, tzinfo=None)] = float(w['temperature_c'])
    temp_bins = defaultdict(lambda: {'kwh':0.0,'count':0})
    for r in readings:
        ts = parse_ts(r['interval_start_ts'])
        if not ts: continue
        key = ts.replace(minute=0, second=0, microsecond=0, tzinfo=None)
        if key in wmap:
            t = wmap[key]
            b = int(t//5)*5
            label = f"{b}C_to_{b+5}C"
            try: kwh = float(r['kwh'])
            except: kwh = 0.0
            temp_bins[label]['kwh'] += kwh; temp_bins[label]['count'] += 1
    temp_corr = [{'temp_bucket':k,'total_kwh':round(v['kwh'],3),'intervals':v['count'],'avg_kwh_per_interval':round(v['kwh']/v['count'],6) if v['count'] else None} for k,v in sorted(temp_bins.items())]

    summary = {
        'totals': {
            'total_kwh': round(total_kwh,3),
            'idle_kwh': round(idle_kwh,3),
            'idle_share': round(idle_kwh/total_kwh,6) if total_kwh else None,
            'peak_window_kwh': round(peak_kwh,3),
            'peak_share': round(peak_kwh/total_kwh,6) if total_kwh else None,
            'energy_cost_usd_est': round(energy_cost,2),
            'readings': len(readings),
            'batches': len(batches),
            'quality_flag_counts': dict(quality_counts),
            'tariff_timezone_mismatch_tariffs': tz_mismatch_tariffs,
        },
        'top_idle_machines': sorted([{'machine_id':k, **{kk:round(vv,3) for kk,vv in v.items()}} for k,v in by_machine.items() if k!='UNATTRIBUTED'], key=lambda x: x['idle_kwh'], reverse=True)[:10],
        'top_peak_meters': sorted([{'meter_id':k, **{kk:round(vv,3) for kk,vv in v.items()}} for k,v in by_meter.items()], key=lambda x: x['peak_kwh'], reverse=True)[:10],
        'energy_intensity_by_machine': intensity[:15],
        'energy_vs_temperature_buckets': temp_corr,
        'exceptions_count': len(exceptions),
        'exceptions_sample': exceptions[:50],
        'recommendations_traceability': rec_trace,
    }
    with (out/'analysis_summary.json').open('w', encoding='utf-8') as f:
        json.dump(summary, f, indent=2)
    # flat exception output
    if exceptions:
        keys = sorted({k for e in exceptions for k in e.keys()})
        with (out/'exceptions.csv').open('w', newline='', encoding='utf-8') as f:
            w = csv.DictWriter(f, fieldnames=keys); w.writeheader(); w.writerows(exceptions)
    print(json.dumps({'analysis_written': str(out/'analysis_summary.json'), 'exceptions': len(exceptions)}, indent=2))

if __name__ == '__main__':
    main()