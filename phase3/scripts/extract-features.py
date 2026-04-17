#!/usr/bin/env python3
"""
Phase 3b: Extract traffic metadata features from DoH pcap files.

Reads one or more pcap files, splits each into overlapping time windows,
and computes 25 flow-level features per window. Labels are assigned by
the caller so the same script can handle both normal DoH baseline and
DoH tunneling attack captures.

Output: a CSV file with one row per window.

Usage:
    python3 extract-features.py \\
        --normal /opt/phase3-results/normal_doh.pcap \\
        --tunnel /opt/phase2-results/doh_bypass.pcap \\
        --output /opt/phase3-results/features.csv
"""

import argparse
import csv
import sys
from pathlib import Path

import numpy as np
from scapy.all import IP, TCP, rdpcap

# --- Configuration ------------------------------------------------------------

# A packet whose source IP starts with this prefix is "upstream" (client -> DoH
# resolver). In the lab the client is 10.0.0.20, so anything in 10.0.0.0/24 is
# "up", and the remote DoH resolver (e.g. 1.1.1.1) is "down".
LOCAL_PREFIX = "10."

# A gap larger than this (seconds) between packets ends a burst.
IDLE_THRESHOLD = 1.0

FEATURE_COLUMNS = [
    # Volume
    "num_packets", "num_bytes", "bytes_up", "bytes_down", "bytes_ratio",
    # Rate
    "packets_per_sec", "bytes_per_sec",
    "packets_per_sec_up", "packets_per_sec_down",
    # Packet size distribution
    "size_mean", "size_std", "size_median",
    "size_min", "size_max", "size_p90",
    # Inter-arrival time
    "iat_mean", "iat_std", "iat_median", "iat_max", "iat_min",
    # Direction
    "direction_changes", "longest_up_run", "longest_down_run",
    # Burst
    "burst_count", "max_burst_size",
    # Metadata (not used as ML features)
    "label", "source_pcap", "window_start",
]

# --- Feature computation ------------------------------------------------------

def _longest_run(arr, value):
    max_run = cur_run = 0
    for v in arr:
        if v == value:
            cur_run += 1
            if cur_run > max_run:
                max_run = cur_run
        else:
            cur_run = 0
    return max_run


def compute_window_features(packets):
    """Compute 25 features for one time window.

    packets : list of (timestamp, size, is_up) tuples, sorted by timestamp.
    Returns dict of features or None if the window is too small.
    """
    n = len(packets)
    if n < 3:
        return None

    times = np.asarray([p[0] for p in packets], dtype=np.float64)
    sizes = np.asarray([p[1] for p in packets], dtype=np.float64)
    directions = np.asarray([p[2] for p in packets], dtype=np.int64)

    # Volume
    num_packets = n
    num_bytes = float(sizes.sum())
    bytes_up = float(sizes[directions == 1].sum())
    bytes_down = float(sizes[directions == 0].sum())
    bytes_ratio = bytes_down / bytes_up if bytes_up > 0 else 0.0

    # Rate (guard against zero duration)
    duration = max(float(times[-1] - times[0]), 1e-3)
    packets_per_sec = num_packets / duration
    bytes_per_sec = num_bytes / duration
    up_count = int((directions == 1).sum())
    down_count = int((directions == 0).sum())
    packets_per_sec_up = up_count / duration
    packets_per_sec_down = down_count / duration

    # Packet size distribution
    size_mean = float(sizes.mean())
    size_std = float(sizes.std())
    size_median = float(np.median(sizes))
    size_min = float(sizes.min())
    size_max = float(sizes.max())
    size_p90 = float(np.percentile(sizes, 90))

    # Inter-arrival time
    iat = np.diff(times)
    iat_mean = float(iat.mean())
    iat_std = float(iat.std())
    iat_median = float(np.median(iat))
    iat_max = float(iat.max())
    iat_min = float(iat.min())

    # Direction
    direction_changes = int((np.diff(directions) != 0).sum())
    longest_up_run = _longest_run(directions, 1)
    longest_down_run = _longest_run(directions, 0)

    # Bursts (separated by gaps > IDLE_THRESHOLD)
    burst_sizes = []
    current = 1
    for gap in iat:
        if gap > IDLE_THRESHOLD:
            burst_sizes.append(current)
            current = 1
        else:
            current += 1
    burst_sizes.append(current)
    burst_count = len(burst_sizes)
    max_burst_size = max(burst_sizes)

    return {
        "num_packets": num_packets,
        "num_bytes": num_bytes,
        "bytes_up": bytes_up,
        "bytes_down": bytes_down,
        "bytes_ratio": bytes_ratio,
        "packets_per_sec": packets_per_sec,
        "bytes_per_sec": bytes_per_sec,
        "packets_per_sec_up": packets_per_sec_up,
        "packets_per_sec_down": packets_per_sec_down,
        "size_mean": size_mean,
        "size_std": size_std,
        "size_median": size_median,
        "size_min": size_min,
        "size_max": size_max,
        "size_p90": size_p90,
        "iat_mean": iat_mean,
        "iat_std": iat_std,
        "iat_median": iat_median,
        "iat_max": iat_max,
        "iat_min": iat_min,
        "direction_changes": direction_changes,
        "longest_up_run": longest_up_run,
        "longest_down_run": longest_down_run,
        "burst_count": burst_count,
        "max_burst_size": max_burst_size,
    }


# --- Pcap processing ----------------------------------------------------------

def load_packets(pcap_path):
    """Return a sorted list of (time, size, is_up) for TCP/IP packets."""
    print(f"  Reading {pcap_path}...", flush=True)
    cap = rdpcap(str(pcap_path))
    pkts = []
    for p in cap:
        if IP in p and TCP in p:
            is_up = 1 if p[IP].src.startswith(LOCAL_PREFIX) else 0
            pkts.append((float(p.time), len(p), is_up))
    pkts.sort(key=lambda x: x[0])
    return pkts


def slice_windows(pkts, window, slide):
    """Yield (window_start_offset, packets_in_window) tuples."""
    if not pkts:
        return
    start = pkts[0][0]
    end = pkts[-1][0]
    t = start
    idx = 0
    while t + window <= end:
        # Skip packets that are entirely before this window
        while idx < len(pkts) and pkts[idx][0] < t:
            idx += 1
        window_pkts = []
        j = idx
        while j < len(pkts) and pkts[j][0] < t + window:
            window_pkts.append(pkts[j])
            j += 1
        yield (t - start, window_pkts)
        t += slide


def process_pcap(pcap_path, label, window, slide):
    pkts = load_packets(pcap_path)
    if not pkts:
        print(f"  [!] no TCP/IP packets in {pcap_path}", file=sys.stderr)
        return []
    print(f"  {len(pkts)} TCP packets loaded", flush=True)

    rows = []
    for offset, window_pkts in slice_windows(pkts, window, slide):
        feats = compute_window_features(window_pkts)
        if feats is None:
            continue
        feats["label"] = label
        feats["source_pcap"] = Path(pcap_path).name
        feats["window_start"] = round(offset, 3)
        rows.append(feats)
    return rows


# --- Main ---------------------------------------------------------------------

def main():
    p = argparse.ArgumentParser(description="Extract Phase 3b features from DoH pcaps")
    p.add_argument("--normal", required=True, help="pcap of normal DoH browsing (label=0)")
    p.add_argument("--tunnel", required=True, help="pcap of DoH tunneling attack (label=1)")
    p.add_argument("--output", required=True, help="output CSV file")
    p.add_argument("--window", type=float, default=10.0, help="window size in seconds (default 10)")
    p.add_argument("--slide",  type=float, default=2.0,  help="slide step in seconds (default 2)")
    args = p.parse_args()

    print("============================================")
    print(" Phase 3b: Feature Extraction")
    print("============================================")
    print(f"Window:   {args.window}s (slide {args.slide}s, {int(100*(1-args.slide/args.window))}% overlap)")
    print()

    all_rows = []

    print("[normal DoH]")
    all_rows.extend(process_pcap(args.normal, label=0, window=args.window, slide=args.slide))

    print()
    print("[DoH tunnel]")
    all_rows.extend(process_pcap(args.tunnel, label=1, window=args.window, slide=args.slide))

    if not all_rows:
        print("[!] no features produced", file=sys.stderr)
        sys.exit(1)

    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=FEATURE_COLUMNS)
        writer.writeheader()
        writer.writerows(all_rows)

    normal_n = sum(1 for r in all_rows if r["label"] == 0)
    tunnel_n = sum(1 for r in all_rows if r["label"] == 1)

    print()
    print("============================================")
    print(f" Wrote {len(all_rows)} samples to {out_path}")
    print(f"   normal (label=0): {normal_n}")
    print(f"   tunnel (label=1): {tunnel_n}")
    print("============================================")


if __name__ == "__main__":
    main()
