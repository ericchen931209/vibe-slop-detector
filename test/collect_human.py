#!/usr/bin/env python3
"""Collect human-written repo records for benchmark (human group only)."""

import base64, json, random, shutil, subprocess, time, statistics
from collections import Counter
from datetime import datetime
from pathlib import Path

RESULTS_DIR = Path(__file__).parent / "results"
TEMP_DIR    = Path(__file__).parent / "_tmp_human"
TIMESTAMP   = datetime.now().strftime("%Y%m%d_%H%M%S")
OUT_FILE    = RESULTS_DIR / f"raw_human_{TIMESTAMP}.jsonl"

TARGET      = 400
MAX_FILES   = 8
MAX_BYTES   = 60_000
MIN_LINES   = 20
API_SLEEP   = 1.5

HUMAN_QUERIES = [
    'language:python created:2014-01-01..2016-12-31 stars:100..500',
    'language:python created:2013-01-01..2015-12-31 stars:80..400',
    'language:python created:2015-01-01..2017-06-30 stars:60..300',
    'language:python created:2016-01-01..2017-12-31 stars:80..350',
    'language:python created:2012-01-01..2014-12-31 stars:100..600',
]

import requests

def get_token():
    r = subprocess.run(["gh", "auth", "token"], capture_output=True, text=True)
    return r.stdout.strip()

TOKEN = get_token()
S = requests.Session()
S.headers.update({
    "Authorization": f"Bearer {TOKEN}",
    "Accept": "application/vnd.github+json",
    "X-GitHub-Api-Version": "2022-11-28",
})

def gh_get(url, params=None):
    for _ in range(3):
        try:
            r = S.get(url, params=params, timeout=15)
            remaining = int(r.headers.get("X-RateLimit-Remaining", 999))
            if remaining < 30:
                print(f"  [rate limit {remaining}] sleeping 60s...")
                time.sleep(60)
            time.sleep(API_SLEEP)
            if r.status_code == 200:
                return r.json()
            if r.status_code in (403, 429):
                time.sleep(30)
                continue
            return None
        except Exception as e:
            print(f"  error: {e}")
            time.sleep(5)
    return None

def search_repos(query, per_page=100, pages=5):
    repos = []
    for page in range(1, pages+1):
        data = gh_get("https://api.github.com/search/repositories",
                      {"q": query, "per_page": per_page, "page": page, "sort": "stars"})
        if not data or "items" not in data:
            break
        repos.extend(data["items"])
        if len(data["items"]) < per_page or len(repos) >= 400:
            break
    return repos

def get_py_files(owner, repo):
    data = gh_get(f"https://api.github.com/repos/{owner}/{repo}/git/trees/HEAD",
                  {"recursive": "1"})
    if not data or "tree" not in data:
        return []
    return [f for f in data["tree"]
            if f.get("type") == "blob"
            and f.get("path","").endswith(".py")
            and f.get("size",0) <= MAX_BYTES
            and f.get("size",0) > 0
            and not any(s in f["path"] for s in
                ["test_","_test","migration","setup.py","conf.py","__pycache__","vendor/"])]

def download_file(owner, repo, path):
    data = gh_get(f"https://api.github.com/repos/{owner}/{repo}/contents/{path}")
    if not data or "content" not in data:
        return None
    try:
        return base64.b64decode(data["content"]).decode("utf-8", errors="replace")
    except Exception:
        return None

def run_vibe_slop(filepath):
    try:
        r = subprocess.run(["vibe-slop", "check", str(filepath), "--json"],
                           capture_output=True, text=True, timeout=30)
        if r.stdout.strip():
            return json.loads(r.stdout.strip())
    except Exception:
        pass
    return None

def main():
    TEMP_DIR.mkdir(exist_ok=True)
    random.seed(99)

    seen_repos = set()
    all_repos = []
    for q in HUMAN_QUERIES:
        print(f"Searching: {q[:70]}...")
        found = search_repos(q)
        for r in found:
            fn = r["full_name"]
            if fn not in seen_repos:
                seen_repos.add(fn)
                all_repos.append(r)
        print(f"  → {len(all_repos)} unique repos")
        if len(all_repos) >= 500:
            break

    random.shuffle(all_repos)
    results = []

    for repo_info in all_repos:
        if len(results) >= TARGET:
            break
        owner = repo_info["owner"]["login"]
        repo  = repo_info["name"]
        print(f"[{len(results)}/{TARGET}] {owner}/{repo}")

        py_files = get_py_files(owner, repo)
        if not py_files:
            continue

        random.shuffle(py_files)
        py_files = py_files[:MAX_FILES]

        repo_dir = TEMP_DIR / f"{owner}__{repo}"
        repo_dir.mkdir(exist_ok=True)

        for fm in py_files:
            if len(results) >= TARGET:
                break
            content = download_file(owner, repo, fm["path"])
            if not content or len(content.splitlines()) < MIN_LINES:
                continue

            safe = fm["path"].replace("/", "__")
            lpath = repo_dir / safe
            lpath.write_text(content, encoding="utf-8", errors="replace")

            report = run_vibe_slop(lpath)
            lpath.unlink(missing_ok=True)
            if not report:
                continue

            rec = {
                "group":      "human",
                "repo":       f"{owner}/{repo}",
                "file":       fm["path"],
                "lines":      len(content.splitlines()),
                "score":      report.get("score", 0),
                "band":       report.get("band", ""),
                "n_findings": len(report.get("findings", [])),
                "categories": dict(Counter(f["category"] for f in report.get("findings", []))),
                "severities": dict(Counter(f["severity"] for f in report.get("findings", []))),
            }
            results.append(rec)
            with open(OUT_FILE, "a") as fh:
                fh.write(json.dumps(rec) + "\n")

        if repo_dir.exists() and not any(repo_dir.iterdir()):
            repo_dir.rmdir()

    shutil.rmtree(TEMP_DIR, ignore_errors=True)

    if results:
        scores = [r["score"] for r in results]
        print(f"\nHuman group done: {len(results)} files")
        print(f"Mean: {statistics.mean(scores):.1f}  Median: {statistics.median(scores):.1f}")
        print(f"Output: {OUT_FILE}")
    else:
        print("No results collected.")

if __name__ == "__main__":
    main()
