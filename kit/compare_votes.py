"""Compare the exported labels of two or more raters.

  python compare_votes.py chenrui.json qiyang.json --hidden manifest_hidden.json --out merged.csv

Each input is the text copied with "复制全部结果（JSON）" / "Copy all results (JSON)",
saved as a .json file. For every pair of raters it prints, per question, how often
they agree and Cohen's kappa (agreement beyond chance). With --hidden it also counts,
per model, how many clips each rater called barely moving or broken, and writes one
merged CSV row per clip.
"""
import argparse
import csv
import json
import os
from collections import Counter
from itertools import combinations

QUESTIONS = ["q1", "q2", "q3"]


def kappa(pairs):
    n = len(pairs)
    if not n:
        return None
    po = sum(a == b for a, b in pairs) / n
    ca, cb = Counter(a for a, _ in pairs), Counter(b for _, b in pairs)
    pe = sum(ca[k] * cb[k] for k in set(ca) | set(cb)) / (n * n)
    return None if pe == 1 else (po - pe) / (1 - pe)


def fmt(x):
    return "—" if x is None else f"{x:.2f}"


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("exports", nargs="+", help="exported label files, one per rater")
    ap.add_argument("--hidden", help="manifest_hidden.json written by build_site.py")
    ap.add_argument("--out", help="merged CSV to write")
    args = ap.parse_args()
    if len(args.exports) < 2:
        ap.error("give at least two exports")

    raters = []
    for path in args.exports:
        with open(path, encoding="utf-8-sig") as f:
            data = json.load(f)
        name = (data.get("rater") or "").strip() or os.path.splitext(os.path.basename(path))[0]
        raters.append((name, data.get("labels") or {}))
    meta = {}
    if args.hidden:
        with open(args.hidden, encoding="utf-8") as f:
            meta = {v["id"]: v for v in json.load(f)["videos"]}

    for (na, la), (nb, lb) in combinations(raters, 2):
        common = sorted(set(la) & set(lb))
        print(f"\n{na} vs {nb}: {len(common)} clips labeled by both")
        for q in QUESTIONS:
            pairs = [(la[i].get(q), lb[i].get(q)) for i in common]
            agree = sum(a == b for a, b in pairs) / len(pairs) if pairs else None
            print(f"  {q}: agree {fmt(agree)}  kappa {fmt(kappa(pairs))}")
        sta = [(la[i].get("q1") == "static", lb[i].get("q1") == "static") for i in common]
        print(f"  q1 barely moves vs rest: kappa {fmt(kappa(sta))}")
        diff = [i for i in common if la[i].get("q1") != lb[i].get("q1")]
        if diff:
            print("  camera answers differ on: " + ", ".join(f"{i}({la[i].get('q1')}/{lb[i].get('q1')})" for i in diff))

    if meta:
        print("\nper model: clips called barely moving / broken")
        models = sorted({m.get("model_id") or "-" for m in meta.values()})
        for m in models:
            ids = [i for i, v in meta.items() if (v.get("model_id") or "-") == m]
            parts = []
            for name, lab in raters:
                got = [lab[i] for i in ids if i in lab]
                parts.append(f"{name} {sum(r.get('q1') == 'static' for r in got)}/{sum(r.get('q1') == 'broken' for r in got)} of {len(got)}")
            print(f"  {m}: " + "; ".join(parts))

    if args.out:
        ids = sorted(set().union(*[set(lab) for _, lab in raters]) | set(meta))
        fields = ["id", "model_id", "prompt_id", "seed", "family"] + [f"{name}_{q}" for name, _ in raters for q in QUESTIONS + ["more", "note"]]
        with open(args.out, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=fields)
            w.writeheader()
            for i in ids:
                m = meta.get(i, {})
                row = {"id": i, "model_id": m.get("model_id", ""), "prompt_id": m.get("prompt_id", ""),
                       "seed": m.get("seed", ""), "family": m.get("family", "")}
                for name, lab in raters:
                    r = lab.get(i, {})
                    for q in QUESTIONS:
                        row[f"{name}_{q}"] = r.get(q, "")
                    row[f"{name}_more"] = " ".join(r.get("more") or [])
                    row[f"{name}_note"] = r.get("note", "")
                w.writerow(row)
        print(f"\nwrote {args.out}")


if __name__ == "__main__":
    main()
