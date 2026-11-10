import argparse
import csv
import hashlib
import json
import math
import os
import random
import sqlite3
from collections import defaultdict
from datetime import datetime, timedelta, date, time, timezone
from pathlib import Path

SEED = 20261022
PLANT_ID = "PLANT-001"
PLANT_TZ = "America/Chicago"  # documented; naive local timestamps used consistently, offsets noted where relevant
START_DATE = date(2026, 1, 1)
DAYS = 90
INTERVAL_MIN = 15
INTERVALS_PER_DAY = 24 * 60 // INTERVAL_MIN
METER_COUNT = 20
BATCH_TARGET = 2000

# Simple fixed-offset handling for plant local time (CST -06:00 in Jan-Mar for simplicity/determinism)
PLANT_OFFSET_HOURS = -6


def local_dt(d: date, t: time) -> datetime:
    return datetime.combine(d, t)


def dt_to_iso(dt: datetime) -> str:
    # ISO with fixed offset for traceability
    sign = "+" if PLANT_OFFSET_HOURS >= 0 else "-"
    hh = abs(PLANT_OFFSET_HOURS)
    return dt.strftime("%Y-%m-%dT%H:%M:%S") + f"{sign}{hh:02d}:00"


def ensure_dir(p: Path):
    p.mkdir(parents=True, exist_ok=True)


def write_csv(path: Path, rows, fieldnames):
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k, "") for k in fieldnames})


def sha256_file(path: Path):
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


class Generator:
    def __init__(self, out_dir: Path, seed=SEED, meters=METER_COUNT, days=DAYS, batches=BATCH_TARGET):
        self.out_dir = out_dir
        self.seed = seed
        self.meters_n = meters
        self.days = days
        self.batches_n = batches
        self.rng = random.Random(seed)
        self.data = {}
        self.ground_truth = []
        self.validation = {"errors": [], "warnings": [], "checks": {}}

    def run(self):
        self.generate_master()
        self.generate_shifts_tariffs_weather()
        self.generate_batches_and_maintenance()
        self.generate_energy_readings()
        self.inject_edge_cases()
        self.generate_recommendations()
        self.derive_meter_totals_view()
        self.validate()
        self.export_all()
        return self.data, self.validation

    def generate_master(self):
        plants = [{
            "plant_id": PLANT_ID,
            "plant_name": "Riverbend Manufacturing Plant",
            "timezone": PLANT_TZ,
            "location_city": "Springfield",
            "status": "active",
            "effective_from": "2020-01-01",
        }]
        meters = []
        machines = []
        machine_types = ["press", "cnc", "oven", "conveyor", "compressor", "mixer"]
        for i in range(1, self.meters_n + 1):
            mid = f"MTR-{PLANT_ID}-{i:03d}"
            mtype = "main" if i == 1 else ("feeder" if i <= 4 else "sub")
            meters.append({
                "meter_id": mid,
                "plant_id": PLANT_ID,
                "meter_name": f"Meter {i:03d}",
                "meter_type": mtype,
                "unit_power": "kW",
                "unit_energy": "kWh",
                "sampling_interval_min": INTERVAL_MIN,
                "install_date": "2023-01-01",
                "retire_date": "",
                "status": "active",
            })
            # 1-2 machines per sub/feeder meter; main meter has no direct machine except monitoring (still assign one virtual)
        # Assign machines to non-main meters mostly; ensure hierarchy
        assignable_meters = [m for m in meters if m["meter_type"] != "main"]
        mch_idx = 1
        for m in assignable_meters:
            count = 2 if self.rng.random() < 0.5 else 1
            # cap roughly to have enough machines
            for _ in range(count):
                if mch_idx > 35:  # reasonable machine count
                    break
                mt = machine_types[(mch_idx - 1) % len(machine_types)]
                rated = round(self.rng.uniform(20, 150), 2)
                idle = round(rated * self.rng.uniform(0.05, 0.25), 2)
                machines.append({
                    "machine_id": f"MCH-{PLANT_ID}-{mch_idx:03d}",
                    "plant_id": PLANT_ID,
                    "meter_id": m["meter_id"],
                    "machine_name": f"{mt.title()} {mch_idx:03d}",
                    "machine_type": mt,
                    "rated_kw": rated,
                    "idle_kw_baseline": idle,
                    "commission_date": f"202{self.rng.randint(0,4)}-{self.rng.randint(1,12):02d}-01",
                    "status": "active",
                })
                mch_idx += 1
        # ensure at least some machines
        if not machines:
            m = assignable_meters[0]
            machines.append({"machine_id": f"MCH-{PLANT_ID}-001", "plant_id": PLANT_ID, "meter_id": m["meter_id"], "machine_name": "Press 001", "machine_type": "press", "rated_kw": 50.0, "idle_kw_baseline": 5.0, "commission_date": "2022-01-01", "status": "active"})
        self.data["Plant"] = plants
        self.data["Meter"] = meters
        self.data["Machine"] = machines
        self.meter_machine_map = defaultdict(list)
        for mach in machines:
            self.meter_machine_map[mach["meter_id"]].append(mach)
        self.machine_by_id = {m["machine_id"]: m for m in machines}
        self.meter_by_id = {m["meter_id"]: m for m in meters}

    def generate_shifts_tariffs_weather(self):
        shifts = [
            {"shift_id": f"SHF-{PLANT_ID}-A", "plant_id": PLANT_ID, "shift_name": "Day", "start_time_local": "06:00", "end_time_local": "14:00", "days_of_week": "Mon-Sun"},
            {"shift_id": f"SHF-{PLANT_ID}-B", "plant_id": PLANT_ID, "shift_name": "Evening", "start_time_local": "14:00", "end_time_local": "22:00", "days_of_week": "Mon-Sun"},
            {"shift_id": f"SHF-{PLANT_ID}-C", "plant_id": PLANT_ID, "shift_name": "Night", "start_time_local": "22:00", "end_time_local": "06:00", "days_of_week": "Mon-Sun"},
        ]
        tariffs = []
        # Time-of-use windows (plant local). Weekend off-peak all day.
        specs = [
            ("peak", 0.22, 12.0, "weekday", "14:00", "20:00"),
            ("shoulder", 0.14, 8.0, "weekday", "06:00", "14:00"),
            ("offpeak", 0.08, 4.0, "weekday", "20:00", "06:00"),
            ("offpeak", 0.08, 4.0, "weekend", "00:00", "23:59"),
        ]
        for i, (name, rate, demand, day_type, st, et) in enumerate(specs, start=1):
            tariffs.append({
                "tariff_id": f"TAR-2026-{i:03d}",
                "plant_id": PLANT_ID,
                "name": name,
                "rate_per_kwh": rate,
                "demand_charge_per_kw": demand,
                "day_type": day_type,
                "start_time_local": st,
                "end_time_local": et,
                "timezone": PLANT_TZ,
                "effective_start": START_DATE.isoformat(),
                "effective_end": (START_DATE + timedelta(days=self.days - 1)).isoformat(),
            })
        weather = []
        for d in range(self.days):
            day = START_DATE + timedelta(days=d)
            base_temp = 5 + 10 * math.sin(2 * math.pi * d / 30.0)  # seasonal-ish variation
            for h in range(24):
                ts = local_dt(day, time(h, 0))
                temp = base_temp + 6 * math.sin(2 * math.pi * (h - 6) / 24.0) + self.rng.uniform(-1.5, 1.5)
                hum = max(20, min(100, 55 + self.rng.uniform(-20, 20) - temp * 0.3))
                cond = self.rng.choices(["clear", "cloudy", "rain", "snow"], weights=[0.45, 0.3, 0.2, 0.05])[0]
                if temp > 2 and cond == "snow":
                    cond = "rain"
                weather.append({
                    "weather_id": f"WTH-{PLANT_ID}-{day.strftime('%Y%m%d')}{h:02d}",
                    "plant_id": PLANT_ID,
                    "timestamp_local": dt_to_iso(ts),
                    "temperature_c": round(temp, 2),
                    "humidity_pct": round(hum, 2),
                    "condition": cond,
                })
        self.data["Shift"] = shifts
        self.data["Tariff"] = tariffs
        self.data["WeatherObservation"] = weather

    def shift_for_ts(self, ts: datetime):
        mins = ts.hour * 60 + ts.minute
        if 6*60 <= mins < 14*60:
            return f"SHF-{PLANT_ID}-A"
        if 14*60 <= mins < 22*60:
            return f"SHF-{PLANT_ID}-B"
        return f"SHF-{PLANT_ID}-C"

    def generate_batches_and_maintenance(self):
        batches = []
        maint = []
        # distribute batches across days and machines
        machines = self.data["Machine"]
        for i in range(1, self.batches_n + 1):
            mach = machines[self.rng.randrange(len(machines))]
            day_offset = self.rng.randrange(self.days)
            day = START_DATE + timedelta(days=day_offset)
            start_hour = self.rng.choice([6,7,8,9,10,14,15,16,18,22,23,0,2])
            start_min = self.rng.choice([0,15,30,45])
            actual_start = local_dt(day, time(start_hour % 24, start_min))
            duration_min = self.rng.choice([60,90,120,180,240,300,360,480])
            actual_end = actual_start + timedelta(minutes=duration_min)
            planned_start = actual_start - timedelta(minutes=self.rng.choice([0,15,30]))
            planned_end = planned_start + timedelta(minutes=duration_min + self.rng.choice([0,15]))
            output = round(max(0, self.rng.gauss(500, 120)), 2)
            scrap = round(max(0, output * self.rng.uniform(0.0, 0.05)), 2)
            status = self.rng.choices(["completed", "completed", "completed", "running", "cancelled"], weights=[0.88,0.05,0.03,0.02,0.02])[0]
            if actual_end.date() > (START_DATE + timedelta(days=self.days-1)):
                status = "running"
            batches.append({
                "batch_id": f"BATCH-2026-{i:06d}",
                "plant_id": PLANT_ID,
                "machine_id": mach["machine_id"],
                "shift_id": self.shift_for_ts(actual_start),
                "planned_start_ts": dt_to_iso(planned_start),
                "planned_end_ts": dt_to_iso(planned_end),
                "actual_start_ts": dt_to_iso(actual_start),
                "actual_end_ts": dt_to_iso(actual_end),
                "output_qty": output if status != "cancelled" else 0.0,
                "output_unit": "units",
                "scrap_qty": scrap if status == "completed" else 0.0,
                "status": status,
            })
        # maintenance events
        mnt_id = 1
        for mach in machines:
            if self.rng.random() < 0.6:
                d = START_DATE + timedelta(days=self.rng.randrange(5, self.days-5))
                st = local_dt(d, time(self.rng.choice([6,14,22]), 0))
                et = st + timedelta(hours=self.rng.choice([2,4,6,8]))
                ev = {
                    "maintenance_id": f"MNT-{mach['machine_id']}-{mnt_id:03d}",
                    "plant_id": PLANT_ID,
                    "machine_id": mach["machine_id"],
                    "event_type": self.rng.choice(["preventive","corrective","inspection"]),
                    "start_ts": dt_to_iso(st),
                    "end_ts": dt_to_iso(et),
                    "description": "Scheduled/service maintenance activity",
                    "impact": self.rng.choice(["downtime","reduced_output","none"]),
                }
                maint.append(ev)
                mnt_id += 1
        self.data["ProductionBatch"] = batches
        self.data["MaintenanceEvent"] = maint
        # index batches by machine and day for alignment
        self.batch_intervals = []  # (start,end,batch)
        for b in batches:
            if b["status"] == "cancelled":
                continue
            try:
                s = datetime.fromisoformat(b["actual_start_ts"])
                e = datetime.fromisoformat(b["actual_end_ts"])
            except Exception:
                continue
            self.batch_intervals.append((s.replace(tzinfo=None), e.replace(tzinfo=None), b))

    def find_batch_for(self, machine_id, ts):
        # ts naive local
        for s,e,b in self.batch_intervals:
            if b["machine_id"] == machine_id and s <= ts < e:
                return b
        return None

    def resolve_tariff(self, ts: datetime):
        # ts naive local
        is_weekend = ts.weekday() >= 5
        mins = ts.hour*60 + ts.minute
        candidates = []
        for t in self.data["Tariff"]:
            if t.get("_tz_mismatch_flag"):  # injected later maybe; baseline none
                pass
            day_type = t["day_type"]
            if day_type == "weekday" and is_weekend:
                continue
            if day_type == "weekend" and not is_weekend:
                continue
            st_h, st_m = map(int, t["start_time_local"].split(":"))
            et_h, et_m = map(int, t["end_time_local"].split(":"))
            st = st_h*60+st_m
            et = et_h*60+et_m
            if st <= et:
                ok = st <= mins < et
            else:
                ok = mins >= st or mins < et  # wrap
            if ok:
                candidates.append(t)
        # prefer weekday/weekend specific
        if candidates:
            return candidates[0]
        # fallback offpeak
        for t in self.data["Tariff"]:
            if t["name"] == "offpeak":
                return t
        return self.data["Tariff"][0]

    def is_idle_period(self, machine, ts: datetime, in_batch: bool):
        # idle periods: nights/weekends low production windows and explicit idle stretches
        hour = ts.hour
        weekend = ts.weekday() >= 5
        # simulate planned idle blocks
        idle_window = (hour >= 1 and hour <= 4) or (weekend and hour < 6)
        random_idle = self.rng.random() < 0.08
        return (not in_batch) and (idle_window or random_idle or hour == 0)

    def generate_energy_readings(self):
        readings = []
        total_intervals = self.days * INTERVALS_PER_DAY
        # create meter gap scenarios: choose some meter-day gaps (labelled)
        gap_slots = set()
        gap_meters = self.rng.sample([m["meter_id"] for m in self.data["Meter"] if m["meter_type"] != "main"], k=min(3, max(1, self.meters_n//6)))
        for gm in gap_meters:
            for _ in range(self.rng.randint(1,3)):
                d = self.rng.randrange(2, self.days-2)
                start_idx = d * INTERVALS_PER_DAY + self.rng.randrange(0, INTERVALS_PER_DAY-8)
                for k in range(self.rng.randint(4, 16)):  # 1-4 hours
                    gap_slots.add((gm, start_idx + k))

        # peak spike scenarios
        spike_slots = set()
        for _ in range(12):
            m = self.rng.choice([x["meter_id"] for x in self.data["Meter"] if self.meter_machine_map.get(x["meter_id"])])
            d = self.rng.randrange(5, self.days-5)
            idx = d*INTERVALS_PER_DAY + self.rng.choice([56,60,64,68]) # around peak hours
            for k in range(self.rng.randint(2,6)):
                spike_slots.add((m, idx+k))

        # track interval sums per meter per day for reconciliation metadata (and deliberate disagreement case)
        self.meter_interval_sums = defaultdict(float)
        self.meter_reported_totals = defaultdict(float)

        for meter in self.data["Meter"]:
            meter_id = meter["meter_id"]
            machs = self.meter_machine_map.get(meter_id, [])
            # main meter: aggregate-like synthetic baseline if no direct machines
            for day_i in range(self.days):
                day = START_DATE + timedelta(days=day_i)
                for slot in range(INTERVALS_PER_DAY):
                    global_idx = day_i * INTERVALS_PER_DAY + slot
                    ts = local_dt(day, time(0,0)) + timedelta(minutes=slot*INTERVAL_MIN)
                    interval_start = ts
                    interval_end = ts + timedelta(minutes=INTERVAL_MIN)
                    if (meter_id, global_idx) in gap_slots:
                        # represent gap as missing record? better create explicit missing-quality record in some cases, but gaps requested;
                        # we'll omit some records to create meter gaps and label in ground truth via summary entries
                        continue
                    if machs:
                        mach = machs[(global_idx // 4 + hash(meter_id)) % len(machs)]  # rotate attribution over blocks
                        batch = self.find_batch_for(mach["machine_id"], ts)
                        in_batch = batch is not None and batch["status"] in ("completed","running")
                        idle = self.is_idle_period(mach, ts, in_batch)
                        base_kw = mach["idle_kw_baseline"] if idle or not in_batch else mach["rated_kw"] * self.rng.uniform(0.45, 0.85)
                        if not idle and in_batch:
                            # production variability
                            base_kw += mach["rated_kw"] * self.rng.uniform(-0.05, 0.15)
                        # energy intensity shift over time (efficiency drift/improvement)
                        drift = 1.0 + (day_i / max(1,self.days-1)) * self.rng.uniform(-0.08, 0.12)
                        base_kw *= drift
                        if (meter_id, global_idx) in spike_slots:
                            base_kw *= self.rng.uniform(1.6, 2.4)  # peak demand spike
                        kw_avg = max(0.1, round(base_kw, 4))
                        kwh = round(kw_avg * (INTERVAL_MIN/60.0), 6)
                        machine_id = mach["machine_id"]
                        batch_id = batch["batch_id"] if batch else ""
                    else:
                        # meters without machines: low monitoring load
                        kw_avg = round(self.rng.uniform(1.0, 8.0), 4)
                        if (meter_id, global_idx) in spike_slots:
                            kw_avg = round(kw_avg * self.rng.uniform(2.0,3.0), 4)
                        kwh = round(kw_avg * 0.25, 6)
                        machine_id = ""
                        batch_id = ""
                        idle = True
                    tariff = self.resolve_tariff(ts)
                    is_peak = tariff["name"] == "peak"
                    rid = f"ENG-{meter_id}-{ts.strftime('%Y%m%dT%H%M')}"
                    rec = {
                        "reading_id": rid,
                        "meter_id": meter_id,
                        "plant_id": PLANT_ID,
                        "machine_id": machine_id,
                        "batch_id": batch_id,
                        "tariff_id": tariff["tariff_id"],
                        "interval_start_ts": dt_to_iso(interval_start),
                        "interval_end_ts": dt_to_iso(interval_end),
                        "kwh": kwh,
                        "kw_avg": kw_avg,
                        "is_idle": str(bool(idle)).lower(),
                        "is_peak_window": str(bool(is_peak)).lower(),
                        "quality_flag": "ok",
                        "source": "scada",
                    }
                    readings.append(rec)
                    self.meter_interval_sums[(meter_id, day.isoformat())] += kwh
                # reported total normally equals sum of intervals (can be altered in edge cases)
                self.meter_reported_totals[(meter_id, day.isoformat())] = self.meter_interval_sums[(meter_id, day.isoformat())]
        self.data["EnergyReading"] = readings
        self.gap_slots = gap_slots
        self.spike_slots = spike_slots

    def inject_edge_cases(self):
        readings = self.data["EnergyReading"]
        if not readings:
            return
        # 1) kW confused with kWh (labelled)
        idxs = self.rng.sample(range(len(readings)), k=min(30, len(readings)//200 + 10))
        for i in idxs:
            r = readings[i]
            # store kw value into kwh field mistakenly (classic confusion)
            r["kwh"] = r["kw_avg"]
            r["quality_flag"] = "unit_confusion"
            self.ground_truth.append({"case_id": f"GT-UNIT-{len(self.ground_truth)+1:04d}", "entity": "EnergyReading", "record_id": r["reading_id"], "issue_type": "kw_confused_with_kwh", "expected_detection": "kwh inconsistent with kw_avg*interval_hours", "expected_action": "recompute kwh or flag/exclude", "notes": "kWh field set to kW average value"})

        # 2) Reading duplicates (labelled)
        dup_src = self.rng.sample(range(len(readings)), k=min(20, len(readings)//300 + 8))
        for i in dup_src:
            r = dict(readings[i])
            # duplicate with same reading_id would break PK in clean table; create duplicate record id variant but mark as duplicate event/case
            r["reading_id"] = r["reading_id"] + "-DUP"
            r["quality_flag"] = "duplicate"
            readings.append(r)
            self.ground_truth.append({"case_id": f"GT-DUP-{len(self.ground_truth)+1:04d}", "entity": "EnergyReading", "record_id": r["reading_id"], "issue_type": "reading_duplicate", "expected_detection": "duplicate interval/meter key", "expected_action": "deduplicate keeping canonical record", "notes": f"Duplicate of interval/meter context; original in source window"})

        # 3) Energy assigned to machine outside meter hierarchy (labelled)
        foreign_candidates = [i for i,r in enumerate(readings) if r.get("machine_id")]
        pick = self.rng.sample(foreign_candidates, k=min(25, len(foreign_candidates)//150 + 10)) if foreign_candidates else []
        all_machine_ids = [m["machine_id"] for m in self.data["Machine"]]
        for i in pick:
            r = readings[i]
            wrong = self.rng.choice(all_machine_ids)
            if wrong == r["machine_id"] and len(all_machine_ids) > 1:
                wrong = [x for x in all_machine_ids if x != r["machine_id"]][0]
            r["machine_id"] = wrong
            r["quality_flag"] = "hierarchy_mismatch"
            self.ground_truth.append({"case_id": f"GT-HIER-{len(self.ground_truth)+1:04d}", "entity": "EnergyReading", "record_id": r["reading_id"], "issue_type": "machine_outside_meter_hierarchy", "expected_detection": "machine.meter_id != reading.meter_id", "expected_action": "reattribute or quarantine record", "notes": "machine assigned not under meter hierarchy"})

        # 4) Tariff timezone mismatch (labelled) - mark tariff config issue
        if self.data["Tariff"]:
            t = self.data["Tariff"][0]
            t["timezone"] = "UTC"  # plant is America/Chicago
            t["_tz_mismatch_flag"] = True
            self.ground_truth.append({"case_id": f"GT-TZ-{len(self.ground_truth)+1:04d}", "entity": "Tariff", "record_id": t["tariff_id"], "issue_type": "tariff_timezone_mismatch", "expected_detection": "tariff timezone differs from plant/local interval interpretation", "expected_action": "normalize to plant timezone before costing", "notes": "Tariff window timezone set to UTC"})

        # 5) Meter total disagrees with interval sums (labelled) - create reconciliation table entries
        self.data["MeterDailyTotal"] = []
        for (meter_id, day), s in sorted(self.meter_interval_sums.items()):
            reported = round(s, 6)
            self.data["MeterDailyTotal"].append({"meter_id": meter_id, "day": day, "interval_sum_kwh": round(s,6), "reported_total_kwh": reported, "reconciles": "true"})
        # inject disagreements
        disagree_keys = self.rng.sample(list(self.meter_interval_sums.keys()), k=min(15, len(self.meter_interval_sums)//120 + 5))
        for (meter_id, day) in disagree_keys:
            for row in self.data["MeterDailyTotal"]:
                if row["meter_id"] == meter_id and row["day"] == day:
                    row["reported_total_kwh"] = round(row["interval_sum_kwh"] * self.rng.uniform(1.05, 1.25), 6)
                    row["reconciles"] = "false"
                    self.ground_truth.append({"case_id": f"GT-REC-{len(self.ground_truth)+1:04d}", "entity": "MeterDailyTotal", "record_id": f"{meter_id}|{day}", "issue_type": "meter_total_disagrees_with_interval_sums", "expected_detection": "reported_total_kwh != sum(interval kWh)", "expected_action": "investigate meter/aggregation, use interval sum with caveats", "notes": "Reported daily total inflated vs interval sum"})
                    break

        # 6) Meter gaps ground truth (omitted intervals)
        for (meter_id, idx) in list(self.gap_slots)[:40]:  # sample entries
            day_i = idx // INTERVALS_PER_DAY
            slot = idx % INTERVALS_PER_DAY
            day = START_DATE + timedelta(days=day_i)
            ts = local_dt(day, time(0,0)) + timedelta(minutes=slot*INTERVAL_MIN)
            self.ground_truth.append({"case_id": f"GT-GAP-{len(self.ground_truth)+1:04d}", "entity": "EnergyReading", "record_id": f"ENG-{meter_id}-{ts.strftime('%Y%m%dT%H%M')}", "issue_type": "meter_gap_missing_interval", "expected_detection": "missing timestamp in 15-min sequence", "expected_action": "estimate or flag coverage gap", "notes": "Interval omitted to simulate meter gap"})

        # 7) Idle load / high idle consumption labels as waste scenarios in ground truth summary
        self.ground_truth.append({"case_id": f"GT-WASTE-IDLE-0001", "entity": "Machine", "record_id": "aggregate", "issue_type": "high_idle_consumption", "expected_detection": "kWh during idle periods with no batch output", "expected_action": "shutdown/standby recommendation", "notes": "Derived from is_idle=true intervals; see analysis outputs"})
        self.ground_truth.append({"case_id": f"GT-WASTE-PEAK-0001", "entity": "Meter", "record_id": "aggregate", "issue_type": "peak_demand_spike", "expected_detection": "kw_avg spikes in peak tariff windows", "expected_action": "load shifting/demand management", "notes": "Spike slots injected; see analysis outputs"})

    def generate_recommendations(self):
        recs = []
        # derive measurable baselines from generated readings
        readings = self.data["EnergyReading"]
        idle_kwh = defaultdict(float)
        peak_kwh = defaultdict(float)
        for r in readings:
            if r.get("machine_id"):
                if r.get("is_idle") == "true" and r.get("quality_flag") in ("ok","duplicate"):
                    try: idle_kwh[r["machine_id"]] += float(r["kwh"])
                    except: pass
                if r.get("is_peak_window") == "true" and r.get("quality_flag") in ("ok","duplicate"):
                    try: peak_kwh[r.get("meter_id","")] += float(r["kwh"])
                    except: pass
        ridx = 1
        for mach_id, val in sorted(idle_kwh.items(), key=lambda x: -x[1])[:8]:
            mach = self.machine_by_id.get(mach_id)
            if not mach: continue
            savings_kwh = round(val * 0.3, 3)
            savings_usd = round(savings_kwh * 0.12, 2)
            recs.append({
                "recommendation_id": f"REC-2026-{ridx:06d}",
                "plant_id": PLANT_ID,
                "meter_id": mach["meter_id"],
                "machine_id": mach_id,
                "category": "idle_load",
                "baseline_metric": "Idle energy (kWh, 90 days, idle intervals)",
                "baseline_value": round(val,3),
                "expected_savings_kwh": savings_kwh,
                "expected_savings_usd": savings_usd,
                "confidence": round(self.rng.uniform(0.6,0.9),2),
                "status": "open",
                "created_ts": dt_to_iso(local_dt(START_DATE + timedelta(days=self.days), time(8,0))),
                "rationale": f"Machine {mach_id} shows measurable idle consumption baseline of {round(val,2)} kWh over 90 days during non-productive/idle periods; standby/shutdown procedure can reduce waste.",
            })
            ridx += 1
        for meter_id, val in sorted(peak_kwh.items(), key=lambda x: -x[1])[:5]:
            if not meter_id: continue
            savings_kwh = round(val * 0.1, 3)
            savings_usd = round(savings_kwh * 0.22, 2)
            recs.append({
                "recommendation_id": f"REC-2026-{ridx:06d}",
                "plant_id": PLANT_ID,
                "meter_id": meter_id,
                "machine_id": "",
                "category": "peak_demand",
                "baseline_metric": "Peak-window energy (kWh, 90 days)",
                "baseline_value": round(val,3),
                "expected_savings_kwh": savings_kwh,
                "expected_savings_usd": savings_usd,
                "confidence": round(self.rng.uniform(0.55,0.85),2),
                "status": "open",
                "created_ts": dt_to_iso(local_dt(START_DATE + timedelta(days=self.days), time(8,30))),
                "rationale": f"Meter {meter_id} peak-window baseline {round(val,2)} kWh indicates demand spikes; load shifting/sequence optimization can reduce peak exposure and demand charges.",
            })
            ridx += 1
        self.data["Recommendation"] = recs

    def derive_meter_totals_view(self):
        # ensure MeterDailyTotal exists even if edge injection changed; recompute interval sums from final readings? easier keep consistent
        if "MeterDailyTotal" not in self.data:
            sums = defaultdict(float)
            for r in self.data["EnergyReading"]:
                try:
                    day = r["interval_start_ts"][:10]
                    sums[(r["meter_id"], day)] += float(r["kwh"])
                except: pass
            self.data["MeterDailyTotal"] = [{"meter_id":k[0],"day":k[1],"interval_sum_kwh":round(v,6),"reported_total_kwh":round(v,6),"reconciles":"true"} for k,v in sorted(sums.items())]

    def validate(self):
        errors = []
        warnings = []
        checks = {}
        def pk_unique(table, pk):
            seen = set(); dups = 0
            for r in self.data.get(table, []):
                k = r.get(pk)
                if k in seen: dups += 1
                seen.add(k)
            checks[f"{table}.pk_unique"] = dups == 0
            if dups: errors.append(f"{table} duplicate PKs: {dups}")
        for t, pk in [("Plant","plant_id"),("Meter","meter_id"),("Machine","machine_id"),("Shift","shift_id"),("Tariff","tariff_id"),("WeatherObservation","weather_id"),("ProductionBatch","batch_id"),("Recommendation","recommendation_id")]:
            pk_unique(t, pk)
        # EnergyReading PK uniqueness except intentional duplicate-labelled records included (they have -DUP ids) so still unique
        pk_unique("EnergyReading", "reading_id")

        plant_ids = {r["plant_id"] for r in self.data.get("Plant",[])}
        meter_ids = {r["meter_id"] for r in self.data.get("Meter",[])}
        machine_ids = {r["machine_id"] for r in self.data.get("Machine",[])}
        batch_ids = {r["batch_id"] for r in self.data.get("ProductionBatch",[])}
        tariff_ids = {r["tariff_id"] for r in self.data.get("Tariff",[])}
        shift_ids = {r["shift_id"] for r in self.data.get("Shift",[])}

        def fk_ok(table, field, refset, allow_blank=False):
            bad = 0
            for r in self.data.get(table,[]):
                v = r.get(field, "")
                if allow_blank and v == "": continue
                if v not in refset: bad += 1
            checks[f"{table}.{field}.fk"] = bad == 0
            if bad: errors.append(f"{table}.{field} invalid refs: {bad}")
        fk_ok("Meter","plant_id",plant_ids)
        fk_ok("Machine","plant_id",plant_ids)
        fk_ok("Machine","meter_id",meter_ids)
        fk_ok("Shift","plant_id",plant_ids)
        fk_ok("Tariff","plant_id",plant_ids)
        fk_ok("WeatherObservation","plant_id",plant_ids)
        fk_ok("ProductionBatch","plant_id",plant_ids)
        fk_ok("ProductionBatch","machine_id",machine_ids)
        fk_ok("ProductionBatch","shift_id",shift_ids, allow_blank=True)
        fk_ok("EnergyReading","meter_id",meter_ids)
        fk_ok("EnergyReading","plant_id",plant_ids)
        fk_ok("EnergyReading","tariff_id",tariff_ids, allow_blank=True)
        fk_ok("EnergyReading","batch_id",batch_ids, allow_blank=True)
        fk_ok("MaintenanceEvent","plant_id",plant_ids)
        fk_ok("MaintenanceEvent","machine_id",machine_ids)
        fk_ok("Recommendation","plant_id",plant_ids)
        fk_ok("Recommendation","meter_id",meter_ids, allow_blank=True)
        fk_ok("Recommendation","machine_id",machine_ids, allow_blank=True)

        # enum checks (sample key ones)
        def enum_ok(table, field, allowed):
            bad = 0
            for r in self.data.get(table,[]):
                if r.get(field) not in allowed: bad += 1
            checks[f"{table}.{field}.enum"] = bad == 0
            if bad: errors.append(f"{table}.{field} invalid enum: {bad}")
        enum_ok("Meter","sampling_interval_min",{15})
        enum_ok("EnergyReading","quality_flag",{"ok","missing","estimated","duplicate","unit_confusion","hierarchy_mismatch"})
        enum_ok("ProductionBatch","status",{"planned","running","completed","cancelled"})

        # date ordering for batches
        bad_dates = 0
        for b in self.data.get("ProductionBatch",[]):
            try:
                if b["planned_start_ts"] > b["planned_end_ts"] or b["actual_start_ts"] > b["actual_end_ts"]:
                    bad_dates += 1
            except Exception:
                bad_dates += 1
        checks["ProductionBatch.date_order"] = bad_dates == 0
        if bad_dates: errors.append(f"ProductionBatch date ordering issues: {bad_dates}")

        # arithmetic reconciliation summary (expected disagreements labelled)
        rec_rows = self.data.get("MeterDailyTotal", [])
        mismatches = sum(1 for r in rec_rows if r.get("reconciles") == "false")
        checks["MeterDailyTotal.has_labelled_mismatches"] = mismatches > 0
        checks["MeterDailyTotal.rows"] = len(rec_rows) > 0

        # hierarchy mismatches present and labelled
        hm = sum(1 for r in self.data.get("EnergyReading",[]) if r.get("quality_flag")=="hierarchy_mismatch")
        checks["EnergyReading.has_hierarchy_mismatch_cases"] = hm > 0

        # ground truth separate
        checks["ground_truth.count"] = len(self.ground_truth)
        self.validation["errors"] = errors
        self.validation["warnings"] = warnings
        self.validation["checks"] = checks

    def export_all(self):
        ensure_dir(self.out_dir)
        raw = self.out_dir / "raw"
        out = self.out_dir / "output"
        ensure_dir(raw); ensure_dir(out)
        tables = ["Plant","Meter","Machine","Shift","Tariff","WeatherObservation","ProductionBatch","EnergyReading","MaintenanceEvent","Recommendation","MeterDailyTotal"]
        fields = {
            "Plant":["plant_id","plant_name","timezone","location_city","status","effective_from"],
            "Meter":["meter_id","plant_id","meter_name","meter_type","unit_power","unit_energy","sampling_interval_min","install_date","retire_date","status"],
            "Machine":["machine_id","plant_id","meter_id","machine_name","machine_type","rated_kw","idle_kw_baseline","commission_date","status"],
            "Shift":["shift_id","plant_id","shift_name","start_time_local","end_time_local","days_of_week"],
            "Tariff":["tariff_id","plant_id","name","rate_per_kwh","demand_charge_per_kw","day_type","start_time_local","end_time_local","timezone","effective_start","effective_end"],
            "WeatherObservation":["weather_id","plant_id","timestamp_local","temperature_c","humidity_pct","condition"],
            "ProductionBatch":["batch_id","plant_id","machine_id","shift_id","planned_start_ts","planned_end_ts","actual_start_ts","actual_end_ts","output_qty","output_unit","scrap_qty","status"],
            "EnergyReading":["reading_id","meter_id","plant_id","machine_id","batch_id","tariff_id","interval_start_ts","interval_end_ts","kwh","kw_avg","is_idle","is_peak_window","quality_flag","source"],
            "MaintenanceEvent":["maintenance_id","plant_id","machine_id","event_type","start_ts","end_ts","description","impact"],
            "Recommendation":["recommendation_id","plant_id","meter_id","machine_id","category","baseline_metric","baseline_value","expected_savings_kwh","expected_savings_usd","confidence","status","created_ts","rationale"],
            "MeterDailyTotal":["meter_id","day","interval_sum_kwh","reported_total_kwh","reconciles"],
        }
        for t in tables:
            rows = self.data.get(t, [])
            # clean internal flags
            clean_rows = []
            for r in rows:
                rr = dict(r)
                rr.pop("_tz_mismatch_flag", None)
                clean_rows.append(rr)
            write_csv(raw / f"{t}.csv", clean_rows, fields[t])
            with (raw / f"{t}.json").open("w", encoding="utf-8") as f:
                json.dump(clean_rows, f, indent=2)

        # ground truth separate
        gt_fields = ["case_id","entity","record_id","issue_type","expected_detection","expected_action","notes"]
        write_csv(out / "ground_truth.csv", self.ground_truth, gt_fields)
        with (out / "ground_truth.json").open("w", encoding="utf-8") as f:
            json.dump(self.ground_truth, f, indent=2)

        # sqlite seed
        self.export_sqlite(raw / "seed.sqlite", fields)
        # manifest and validation
        self.export_manifest(raw, out)

    def export_sqlite(self, path: Path, fields):
        if path.exists():
            path.unlink()
        con = sqlite3.connect(path)
        cur = con.cursor()
        type_map = {
            "sampling_interval_min":"INTEGER","rated_kw":"REAL","idle_kw_baseline":"REAL","rate_per_kwh":"REAL",
            "demand_charge_per_kw":"REAL","temperature_c":"REAL","humidity_pct":"REAL","output_qty":"REAL","scrap_qty":"REAL",
            "kwh":"REAL","kw_avg":"REAL","baseline_value":"REAL","expected_savings_kwh":"REAL","expected_savings_usd":"REAL",
            "confidence":"REAL","interval_sum_kwh":"REAL","reported_total_kwh":"REAL"
        }
        for t, cols in fields.items():
            col_defs = []
            for c in cols:
                col_defs.append(f'"{c}" {type_map.get(c,"TEXT")}')
            cur.execute(f'CREATE TABLE "{t}" ({", ".join(col_defs)})')
            rows = self.data.get(t, [])
            for r in rows:
                rr = dict(r); rr.pop("_tz_mismatch_flag", None)
                vals = [rr.get(c, "") for c in cols]
                placeholders = ",".join(["?"]*len(cols))
                cur.execute(f'INSERT INTO "{t}" VALUES ({placeholders})', vals)
        con.commit(); con.close()

    def export_manifest(self, raw: Path, out: Path):
        manifest = {"seed": self.seed, "generated_at": datetime.utcnow().isoformat()+"Z", "files": []}
        for p in sorted(list(raw.glob("*")) + list(out.glob("*"))):
            if p.is_file():
                manifest["files"].append({"path": str(p.relative_to(self.out_dir)), "sha256": sha256_file(p), "bytes": p.stat().st_size})
        with (self.out_dir / "source_manifest.json").open("w", encoding="utf-8") as f:
            json.dump(manifest, f, indent=2)
        with (self.out_dir / "validation_summary.json").open("w", encoding="utf-8") as f:
            json.dump(self.validation, f, indent=2)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="energy_analytics")
    ap.add_argument("--seed", type=int, default=SEED)
    ap.add_argument("--meters", type=int, default=METER_COUNT)
    ap.add_argument("--days", type=int, default=DAYS)
    ap.add_argument("--batches", type=int, default=BATCH_TARGET)
    args = ap.parse_args()
    out_dir = Path(args.out)
    gen = Generator(out_dir, seed=args.seed, meters=args.meters, days=args.days, batches=args.batches)
    gen.run()
    print(json.dumps({"out": str(out_dir), "seed": args.seed, "checks": gen.validation["checks"], "errors": gen.validation["errors"]}, indent=2))

if __name__ == "__main__":
    main()
