"""Build a blind video-labeling page from a set of generated videos.

Two ways to list the videos:

  --list videos.csv
      A CSV with at least the columns `video` (path to an mp4) and `prompt`
      (the text prompt). Optional columns: model_id, prompt_id, seed, family.

  --cvg-work DIR --task-csv tasks/task_subset.csv
      Videos laid out like the GeoT2V handoff package: each row's
      `return_video_rel` is found under DIR/outputs/video_refresh_v1/.
      Rows whose video does not exist yet are skipped.

The output folder holds everything the page needs:

  index.html            the page, with the public manifest written into it
  videos/vNNN.mp4       shuffled, anonymized clips (H.264, at most 848 px wide)
  manifest_public.json  what raters may see: id, prompt, camera family
  manifest_hidden.json  which model, prompt and seed each id came from (never publish)
  serve.py              optional local server that saves votes to votes.json
  .gitignore            keeps manifest_hidden.json and votes out of git

Only the Python standard library is used. ffmpeg/ffprobe are used when they
are on PATH; without them the clips are copied unchanged.
"""
import argparse
import csv
import hashlib
import json
import os
import random
import re
import shutil
import subprocess
import sys
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
FAMILY_WORDS = ["orbit", "dolly", "truck", "lateral", "pan", "tilt", "roll", "locked", "crane", "pedestal", "zoom", "arc"]


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def guess_family(prompt_id, prompt):
    text = (prompt_id or "").lower()
    for word in FAMILY_WORDS:
        if re.search(r"(^|[_\-])" + word + r"($|[_\-])", text):
            return word
    low = (prompt or "").lower()
    for word in FAMILY_WORDS:
        if re.search(r"\b" + word, low):
            return word
    return "other"


def rows_from_list(path):
    rows = []
    with open(path, newline="", encoding="utf-8-sig") as f:
        for r in csv.DictReader(f):
            video = (r.get("video") or "").strip()
            if not video:
                continue
            if not os.path.isabs(video):
                video = os.path.join(os.path.dirname(os.path.abspath(path)), video)
            rows.append({
                "video": video,
                "prompt": (r.get("prompt") or "").strip(),
                "model_id": (r.get("model_id") or "").strip(),
                "prompt_id": (r.get("prompt_id") or "").strip(),
                "seed": (r.get("seed") or "").strip(),
                "family": (r.get("family") or "").strip(),
            })
    return rows


def rows_from_cvg(work, task_csv):
    base = os.path.join(work, "outputs", "video_refresh_v1")
    rows = []
    with open(task_csv, newline="", encoding="utf-8-sig") as f:
        for r in csv.DictReader(f):
            rel = (r.get("return_video_rel") or "").strip()
            if not rel:
                continue
            rows.append({
                "video": os.path.join(base, rel),
                "prompt": (r.get("prompt_text") or "").strip(),
                "model_id": (r.get("model_id") or "").strip(),
                "prompt_id": (r.get("prompt_id") or "").strip(),
                "seed": (r.get("requested_seed") or "").strip(),
                "family": "",
                "position_id": (r.get("position_id") or "").strip(),
                "suite": (r.get("suite") or "").strip(),
            })
    return rows


def probe(path):
    if not shutil.which("ffprobe"):
        return {}
    cmd = ["ffprobe", "-v", "error", "-select_streams", "v:0", "-count_packets",
           "-show_entries", "stream=width,height,avg_frame_rate,nb_read_packets:format=duration",
           "-of", "json", path]
    try:
        info = json.loads(subprocess.run(cmd, capture_output=True, text=True, check=True).stdout)
    except (subprocess.CalledProcessError, json.JSONDecodeError, OSError):
        return {}
    st = (info.get("streams") or [{}])[0]
    num, _, den = (st.get("avg_frame_rate") or "0/1").partition("/")
    fps = float(num) / float(den) if den and float(den) else None
    dur = (info.get("format") or {}).get("duration")
    frames = st.get("nb_read_packets")
    return {
        "width": st.get("width"), "height": st.get("height"),
        "fps": round(fps, 3) if fps else None,
        "duration_sec": round(float(dur), 3) if dur else None,
        "frame_count": int(frames) if frames and str(frames).isdigit() else None,
    }


def transcode(src, dst, max_width, crf):
    if not shutil.which("ffmpeg"):
        shutil.copyfile(src, dst)
        return "copied (ffmpeg not found)"
    base = ["ffmpeg", "-y", "-v", "error", "-i", src,
            "-vf", f"scale='min({max_width},iw)':-2",
            "-c:v", "libx264", "-preset", "slow", "-crf", str(crf),
            "-pix_fmt", "yuv420p", "-an", "-movflags", "+faststart"]
    for extra in (["-fps_mode", "passthrough"], ["-vsync", "passthrough"]):
        r = subprocess.run(base + extra + [dst], capture_output=True, text=True)
        if r.returncode == 0:
            return "h264"
    raise RuntimeError(f"ffmpeg failed on {src}: {r.stderr.strip()[-400:]}")


def sample(rows, by, per, seed):
    if not by or per <= 0:
        return rows
    rng = random.Random(seed)
    groups = defaultdict(list)
    for r in rows:
        groups[tuple(r.get(k, "") for k in by)].append(r)
    picked = []
    for key in sorted(groups):
        g = sorted(groups[key], key=lambda r: r["video"])
        rng.shuffle(g)
        picked.extend(g[:per])
    return picked


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    src = ap.add_argument_group("where the videos are")
    src.add_argument("--list", help="CSV with columns video, prompt (optional: model_id, prompt_id, seed, family)")
    src.add_argument("--cvg-work", help="work folder that holds outputs/video_refresh_v1/")
    src.add_argument("--task-csv", help="task table with return_video_rel and prompt_text (used with --cvg-work)")
    ap.add_argument("--out", required=True, help="output folder for the site")
    ap.add_argument("--site-id", required=True, help="short id, letters/digits/-/_ only; also separates browser storage between sites")
    ap.add_argument("--title-zh", default="生成视频标注台")
    ap.add_argument("--title-en", default="Generated-Video Labeling")
    ap.add_argument("--eyebrow-zh", default="视频标注")
    ap.add_argument("--eyebrow-en", default="Video labeling")
    ap.add_argument("--send-to-zh", default="组织者", help="who raters send their exported results to (Chinese)")
    ap.add_argument("--send-to-en", default="the organizer")
    ap.add_argument("--no-full-view", action="store_true", help="allow saving before a clip has played through once")
    ap.add_argument("--sample-by", default="", help="comma-separated fields to stratify by, e.g. model_id,family")
    ap.add_argument("--per-stratum", type=int, default=0, help="clips to draw per stratum (0 = keep all)")
    ap.add_argument("--limit", type=int, default=0, help="keep at most this many clips after sampling (0 = no limit)")
    ap.add_argument("--seed", type=int, default=20261007, help="seed for sampling and for the shuffle")
    ap.add_argument("--max-width", type=int, default=848)
    ap.add_argument("--crf", type=int, default=26)
    ap.add_argument("--template", default=os.path.join(HERE, "template.html"))
    args = ap.parse_args()

    if bool(args.list) == bool(args.cvg_work):
        ap.error("give either --list or --cvg-work (with --task-csv)")
    if args.cvg_work and not args.task_csv:
        ap.error("--cvg-work needs --task-csv")
    if not re.fullmatch(r"[A-Za-z0-9_-]+", args.site_id):
        ap.error("--site-id may only contain letters, digits, - and _")

    rows = rows_from_list(args.list) if args.list else rows_from_cvg(args.cvg_work, args.task_csv)
    present = [r for r in rows if os.path.isfile(r["video"])]
    print(f"listed {len(rows)} videos, found {len(present)} on disk")
    if not present:
        sys.exit("no videos found; check the paths")
    for r in present:
        r["family"] = r["family"] or guess_family(r["prompt_id"], r["prompt"])

    by = [k.strip() for k in args.sample_by.split(",") if k.strip()]
    chosen = sample(present, by, args.per_stratum, args.seed)
    rng = random.Random(args.seed + 1)
    chosen = sorted(chosen, key=lambda r: r["video"])
    rng.shuffle(chosen)
    if args.limit > 0:
        chosen = chosen[:args.limit]
    if len(chosen) > 999:
        sys.exit("more than 999 clips; sample fewer (--per-stratum or --limit)")
    print(f"building a page with {len(chosen)} clips")

    out = os.path.abspath(args.out)
    vids = os.path.join(out, "videos")
    os.makedirs(vids, exist_ok=True)
    public, hidden = [], []
    for i, r in enumerate(chosen, 1):
        vid = f"v{i:03d}"
        dst = os.path.join(vids, vid + ".mp4")
        how = transcode(r["video"], dst, args.max_width, args.crf)
        meta = probe(dst)
        public.append({
            "id": vid, "filename": f"videos/{vid}.mp4", "prompt": r["prompt"],
            "motion_prompt_family": r["family"],
            "frame_count": meta.get("frame_count"), "fps": meta.get("fps"), "duration_sec": meta.get("duration_sec"),
        })
        hidden.append(dict(r, id=vid, source_path=os.path.abspath(r["video"]), source_sha256=sha256(r["video"]),
                           page_video_sha256=sha256(dst), encode=how))
        print(f"  {vid}  {r['model_id'] or '-'}  {r['prompt_id'] or '-'}  seed {r['seed'] or '-'}  ({how})")

    site = {"id": args.site_id, "title_zh": args.title_zh, "title_en": args.title_en,
            "eyebrow_zh": args.eyebrow_zh, "eyebrow_en": args.eyebrow_en,
            "send_to_zh": args.send_to_zh, "send_to_en": args.send_to_en,
            "require_full_view": not args.no_full_view}
    manifest_public = {"schema_version": "GeoT2V-label-site-v3", "sampling_seed": args.seed, "site": site, "videos": public}
    manifest_hidden = {"schema_version": "GeoT2V-label-site-v3-hidden", "sampling_seed": args.seed,
                       "sample_by": by, "per_stratum": args.per_stratum, "site": site, "videos": hidden}
    with open(os.path.join(out, "manifest_public.json"), "w", encoding="utf-8") as f:
        json.dump(manifest_public, f, ensure_ascii=False, indent=1)
    with open(os.path.join(out, "manifest_hidden.json"), "w", encoding="utf-8") as f:
        json.dump(manifest_hidden, f, ensure_ascii=False, indent=1)

    with open(args.template, encoding="utf-8") as f:
        template = f.read()
    if "\n__MANIFEST__\n" not in template:
        sys.exit("template has no __MANIFEST__ line")
    inline = json.dumps(manifest_public, ensure_ascii=False).replace("</", "<\\/")
    with open(os.path.join(out, "index.html"), "w", encoding="utf-8") as f:
        f.write(template.replace("\n__MANIFEST__\n", "\n" + inline + "\n", 1))

    shutil.copyfile(os.path.join(HERE, "serve.py"), os.path.join(out, "serve.py"))
    with open(os.path.join(out, ".gitignore"), "w", encoding="utf-8") as f:
        f.write("manifest_hidden.json\nvotes.json\nvotes_log.jsonl\n")
    open(os.path.join(out, ".nojekyll"), "w").close()
    print(f"done: {out}")
    print("check it locally:  python serve.py   then open http://127.0.0.1:8765")
    print("never publish manifest_hidden.json; .gitignore already excludes it")


if __name__ == "__main__":
    main()
