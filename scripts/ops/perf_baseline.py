#!/usr/bin/env python3
import argparse
import json
import statistics
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path


def parse_args():
    parser = argparse.ArgumentParser(description="Simple concurrent perf baseline runner")
    parser.add_argument("--url", required=True)
    parser.add_argument("--requests", type=int, default=600)
    parser.add_argument("--concurrency", type=int, default=10)
    parser.add_argument("--timeout", type=float, default=5.0)
    parser.add_argument("--header", action="append", default=[])
    parser.add_argument("--out", default="docs/release/perf_baseline_report.json")
    return parser.parse_args()


def to_headers(items):
    headers = {}
    for item in items:
        if ":" not in item:
            continue
        k, v = item.split(":", 1)
        headers[k.strip()] = v.strip()
    return headers


def percentile(sorted_values, p):
    if not sorted_values:
        return 0.0
    if len(sorted_values) == 1:
        return float(sorted_values[0])
    idx = (len(sorted_values) - 1) * p
    lo = int(idx)
    hi = min(lo + 1, len(sorted_values) - 1)
    frac = idx - lo
    return float(sorted_values[lo] + (sorted_values[hi] - sorted_values[lo]) * frac)


def do_one(url, timeout, headers):
    req = urllib.request.Request(url, method="GET", headers=headers)
    start = time.perf_counter()
    code = 0
    ok = 0
    err = ""
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            code = int(resp.getcode() or 0)
            ok = 1 if 200 <= code < 400 else 0
            _ = resp.read(64)
    except urllib.error.HTTPError as e:
        code = int(e.code or 0)
        err = str(e)
    except Exception as e:  # noqa: BLE001
        err = str(e)
    elapsed_ms = (time.perf_counter() - start) * 1000
    return {"ok": ok, "status": code, "latency_ms": elapsed_ms, "error": err}


def main():
    args = parse_args()
    headers = to_headers(args.header)
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    start_all = time.perf_counter()
    results = []
    with ThreadPoolExecutor(max_workers=max(1, args.concurrency)) as pool:
        futs = [pool.submit(do_one, args.url, args.timeout, headers) for _ in range(max(1, args.requests))]
        for fut in as_completed(futs):
            results.append(fut.result())
    total_s = max(0.0001, time.perf_counter() - start_all)

    latencies = sorted([float(r["latency_ms"]) for r in results])
    ok_count = sum(int(r["ok"]) for r in results)
    err_count = len(results) - ok_count
    status_dist = {}
    for r in results:
        key = str(r["status"] or 0)
        status_dist[key] = int(status_dist.get(key, 0)) + 1

    report = {
        "url": args.url,
        "total_requests": len(results),
        "concurrency": int(args.concurrency),
        "duration_seconds": round(total_s, 4),
        "throughput_rps": round(len(results) / total_s, 4),
        "success_count": int(ok_count),
        "error_count": int(err_count),
        "success_rate": round(ok_count / max(1, len(results)), 6),
        "latency_ms": {
            "min": round(latencies[0] if latencies else 0.0, 4),
            "avg": round(statistics.fmean(latencies) if latencies else 0.0, 4),
            "p50": round(percentile(latencies, 0.50), 4),
            "p95": round(percentile(latencies, 0.95), 4),
            "p99": round(percentile(latencies, 0.99), 4),
            "max": round(latencies[-1] if latencies else 0.0, 4),
        },
        "status_distribution": status_dist,
        "generated_at_epoch": int(time.time()),
    }

    out_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
