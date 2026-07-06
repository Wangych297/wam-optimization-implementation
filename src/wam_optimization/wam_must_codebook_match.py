import argparse
import csv
from pathlib import Path

import numpy as np


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--metrics", required=True)
    parser.add_argument("--out-dir", required=True)
    return parser.parse_args()


def hamming(a, b):
    return sum(1 for x, y in zip(a, b) if x != y)


def main() -> int:
    args = parse_args()
    metrics_path = Path(args.metrics)
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    with metrics_path.open("r", newline="", encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))
    if not rows:
        raise RuntimeError(f"No rows in {metrics_path}")

    groups = {}
    for row in rows:
        key = (
            row["code_mode"],
            row["scheme"],
            row["scenario"],
            row["attack"],
            row["decode_method"],
        )
        groups.setdefault(key, []).append(row)

    out_rows = []
    for key, vals in groups.items():
        codebook = {}
        for row in vals:
            codebook[row["source_idx"]] = row["target_message"]
        for row in vals:
            pred = row["predicted_message"]
            distances = sorted(
                [(source_idx, hamming(pred, target)) for source_idx, target in codebook.items()],
                key=lambda item: (item[1], item[0]),
            )
            best_source, best_distance = distances[0]
            second_distance = distances[1][1] if len(distances) > 1 else 32
            target_distance = hamming(pred, row["target_message"])
            unique_best = int(best_distance < second_distance)
            top1_match = int(best_source == row["source_idx"])
            strict_match = int(unique_best and top1_match)
            out = dict(row)
            out.update({
                "target_hamming": target_distance,
                "best_source_idx": best_source,
                "best_hamming": best_distance,
                "second_hamming": second_distance,
                "hamming_margin": second_distance - best_distance,
                "codebook_top1_match": top1_match,
                "codebook_strict_match": strict_match,
            })
            out_rows.append(out)

    detail_path = out_dir / "wam_must_codebook_match_metrics.csv"
    fieldnames = list(out_rows[0].keys())
    with detail_path.open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(out_rows)

    summary_groups = {}
    for row in out_rows:
        key = (
            row["code_mode"],
            row["scheme"],
            row["scenario"],
            row["attack"],
            row["decode_method"],
        )
        summary_groups.setdefault(key, []).append(row)

    summary_path = out_dir / "wam_must_codebook_match_summary.csv"
    with summary_path.open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "code_mode",
                "scheme",
                "scenario",
                "attack",
                "decode_method",
                "mean_payload_accuracy",
                "payload_success_rate",
                "codebook_top1_match_rate",
                "codebook_strict_match_rate",
                "mean_target_hamming",
                "mean_best_hamming",
                "mean_hamming_margin",
                "num_source_rows",
            ],
        )
        writer.writeheader()
        for key, vals in sorted(summary_groups.items()):
            code_mode, scheme, scenario, attack, method = key
            writer.writerow({
                "code_mode": code_mode,
                "scheme": scheme,
                "scenario": scenario,
                "attack": attack,
                "decode_method": method,
                "mean_payload_accuracy": f"{np.mean([float(v['payload_accuracy']) for v in vals]):.6f}",
                "payload_success_rate": f"{np.mean([int(v['payload_success']) for v in vals]):.6f}",
                "codebook_top1_match_rate": f"{np.mean([int(v['codebook_top1_match']) for v in vals]):.6f}",
                "codebook_strict_match_rate": f"{np.mean([int(v['codebook_strict_match']) for v in vals]):.6f}",
                "mean_target_hamming": f"{np.mean([int(v['target_hamming']) for v in vals]):.3f}",
                "mean_best_hamming": f"{np.mean([int(v['best_hamming']) for v in vals]):.3f}",
                "mean_hamming_margin": f"{np.mean([int(v['hamming_margin']) for v in vals]):.3f}",
                "num_source_rows": len(vals),
            })

    overview_groups = {}
    for row in out_rows:
        key = (row["code_mode"], row["scheme"], row["decode_method"])
        overview_groups.setdefault(key, []).append(row)

    overview_path = out_dir / "wam_must_codebook_match_overview.csv"
    with overview_path.open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "code_mode",
                "scheme",
                "decode_method",
                "payload_success_rate",
                "codebook_top1_match_rate",
                "codebook_strict_match_rate",
                "mean_target_hamming",
                "mean_hamming_margin",
            ],
        )
        writer.writeheader()
        for key, vals in sorted(overview_groups.items()):
            code_mode, scheme, method = key
            writer.writerow({
                "code_mode": code_mode,
                "scheme": scheme,
                "decode_method": method,
                "payload_success_rate": f"{np.mean([int(v['payload_success']) for v in vals]):.6f}",
                "codebook_top1_match_rate": f"{np.mean([int(v['codebook_top1_match']) for v in vals]):.6f}",
                "codebook_strict_match_rate": f"{np.mean([int(v['codebook_strict_match']) for v in vals]):.6f}",
                "mean_target_hamming": f"{np.mean([int(v['target_hamming']) for v in vals]):.3f}",
                "mean_hamming_margin": f"{np.mean([int(v['hamming_margin']) for v in vals]):.3f}",
            })

    print(f"detail={detail_path}")
    print(f"summary={summary_path}")
    print(f"overview={overview_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
