"""Local server for the labeling page built by build_site.py.

Serves the page and the videos from this folder on 127.0.0.1 only, and keeps
every saved label in votes.json (one record per video, the latest save wins)
plus an append-only votes_log.jsonl.
"""
import json
import os
import sys
import threading
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

ROOT = os.path.dirname(os.path.abspath(__file__))
VOTES = os.path.join(ROOT, "votes.json")
LOG = os.path.join(ROOT, "votes_log.jsonl")
LOCK = threading.Lock()


def load_votes():
    try:
        with open(VOTES, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except FileNotFoundError:
        return {}


class Handler(SimpleHTTPRequestHandler):
    def log_message(self, fmt, *args):
        pass

    def end_headers(self):
        self.send_header("Cache-Control", "no-store")
        super().end_headers()

    def send_json(self, code, obj):
        body = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path.split("?")[0] == "/api/votes":
            with LOCK:
                data = load_votes()
            return self.send_json(200, {"labels": data})
        return super().do_GET()

    def do_POST(self):
        if self.path.split("?")[0] != "/api/vote":
            return self.send_json(404, {"error": "not found"})
        length = int(self.headers.get("Content-Length", "0") or 0)
        if length <= 0 or length > 200_000:
            return self.send_json(400, {"error": "bad length"})
        try:
            rec = json.loads(self.rfile.read(length).decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            return self.send_json(400, {"error": "bad json"})
        vid = rec.get("vid") if isinstance(rec, dict) else None
        if not (isinstance(vid, str) and 4 <= len(vid) <= 6 and vid[0] == "v" and vid[1:].isdigit()):
            return self.send_json(400, {"error": "bad vid"})
        with LOCK:
            data = load_votes()
            data[vid] = rec
            tmp = VOTES + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=1)
            os.replace(tmp, VOTES)
            with open(LOG, "a", encoding="utf-8") as f:
                f.write(json.dumps(rec, ensure_ascii=False) + "\n")
        return self.send_json(200, {"ok": True, "count": len(data)})


def main():
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8765
    server = ThreadingHTTPServer(("127.0.0.1", port), partial(Handler, directory=ROOT))
    print(f"Labeling page: http://127.0.0.1:{port}", flush=True)
    server.serve_forever()


if __name__ == "__main__":
    main()
