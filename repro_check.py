import filecmp
import hashlib
import json
import shutil
import tempfile
from pathlib import Path
from generator import Generator, SEED

COMPARE_TABLES = [
    "Plant","Meter","Machine","Shift","Tariff","WeatherObservation","ProductionBatch","EnergyReading","MaintenanceEvent","Recommendation","MeterDailyTotal"
]

def hash_file(p: Path):
    h = hashlib.sha256()
    with p.open('rb') as f:
        for chunk in iter(lambda: f.read(8192), b''):
            h.update(chunk)
    return h.hexdigest()


def run_once(base: Path):
    out = base / "run"
    gen = Generator(out, seed=SEED, meters=20, days=90, batches=2000)
    gen.run()
    return out


def main():
    with tempfile.TemporaryDirectory(prefix="ea_repro_") as d:
        d = Path(d)
        out1 = run_once(d/"r1")
        out2 = run_once(d/"r2")
        result = {"seed": SEED, "identical": True, "details": {}}
        for t in COMPARE_TABLES:
            p1 = out1/"raw"/f"{t}.csv"
            p2 = out2/"raw"/f"{t}.csv"
            h1, h2 = hash_file(p1), hash_file(p2)
            same = h1 == h2
            # row counts
            with p1.open(encoding='utf-8') as f: c1 = sum(1 for _ in f) - 1
            with p2.open(encoding='utf-8') as f: c2 = sum(1 for _ in f) - 1
            result["details"][t] = {"rows_run1": c1, "rows_run2": c2, "sha256_run1": h1, "sha256_run2": h2, "identical": same}
            if not same or c1 != c2:
                result["identical"] = False
        # ground truth and validation checksums
        for rel in ["output/ground_truth.csv", "validation_summary.json"]:
            p1 = out1/rel; p2 = out2/rel
            h1, h2 = hash_file(p1), hash_file(p2)
            result["details"][rel] = {"sha256_run1": h1, "sha256_run2": h2, "identical": h1==h2}
            if h1 != h2: result["identical"] = False
        print(json.dumps(result, indent=2))
        # also write into workspace for record
        rec_path = Path('energy_analytics')/"reproducibility_report.json"
        rec_path.parent.mkdir(parents=True, exist_ok=True)
        with rec_path.open('w', encoding='utf-8') as f:
            json.dump(result, f, indent=2)

if __name__ == '__main__':
    main()