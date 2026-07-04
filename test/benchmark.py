#!/usr/bin/env python3
"""
Benchmark vibe-slop: AI-assisted vs human-written Python repos.

AI group:    repos created 2024+ with AI tool mentions in README/description/topics
Human group: repos created 2013-2017 with 50-500 stars (pre-ChatGPT era)

Scale: ~1000 Python files per group.
Downloads individual .py files via GitHub Contents API (no full clones).
Deletes all downloaded files after analysis. Keeps only results/.
"""

import base64
import json
import math
import random
import shutil
import subprocess
import sys
import time
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

import requests
from scipy import stats

# ── Paths ─────────────────────────────────────────────────────────────────────

SCRIPT_DIR = Path(__file__).parent
RESULTS_DIR = SCRIPT_DIR / "results"
TEMP_DIR    = SCRIPT_DIR / "_tmp"
RESULTS_DIR.mkdir(parents=True, exist_ok=True)
TEMP_DIR.mkdir(parents=True, exist_ok=True)

TIMESTAMP = datetime.now().strftime("%Y%m%d_%H%M%S")
RAW_JSONL  = RESULTS_DIR / f"raw_{TIMESTAMP}.jsonl"
SUMMARY_JSON = RESULTS_DIR / f"summary_{TIMESTAMP}.json"
REPORT_MD    = RESULTS_DIR / f"report_{TIMESTAMP}.md"

# ── Config ────────────────────────────────────────────────────────────────────

TARGET_FILES_PER_GROUP = 1000
MAX_FILES_PER_REPO     = 8      # max .py files sampled per repo
MAX_FILE_SIZE_BYTES    = 60_000 # skip generated/minified files
MIN_FILE_LINES         = 20     # skip trivially short files
RATE_LIMIT_SLEEP       = 2      # seconds between API calls
RETRY_SLEEP            = 30     # sleep on rate-limit hit

# GitHub search queries — AI repos (created 2024+, explicit AI tool mentions)
AI_QUERIES = [
    'language:python created:>2024-01-01 "vibe coding" in:readme',
    'language:python created:>2024-01-01 "ChatGPT" in:readme stars:<30',
    'language:python created:>2024-01-01 "made with Claude" in:readme',
    'language:python created:>2024-01-01 "AI generated" in:readme stars:<30',
    'language:python created:>2024-01-01 "GitHub Copilot" in:readme stars:<30',
    'language:python created:>2024-01-01 "cursor" in:readme stars:<20',
    'language:python created:>2024-01-01 topic:vibe-coding',
    'language:python created:>2024-01-01 topic:ai-generated',
]

# Human repos: well-established Python projects created before ChatGPT era
HUMAN_QUERIES = [
    'language:python created:2014-01-01..2016-12-31 stars:100..500',
    'language:python created:2013-01-01..2015-12-31 stars:80..400',
    'language:python created:2015-01-01..2017-06-30 stars:60..300',
    'language:python created:2016-01-01..2017-12-31 stars:80..350',
]

# ── GitHub API ────────────────────────────────────────────────────────────────

def get_token() -> str:
    result = subprocess.run(["gh", "auth", "token"], capture_output=True, text=True)
    return result.stdout.strip()

TOKEN = get_token()
SESSION = requests.Session()
SESSION.headers.update({
    "Authorization": f"Bearer {TOKEN}",
    "Accept": "application/vnd.github+json",
    "X-GitHub-Api-Version": "2022-11-28",
})


def gh_get(url: str, params: dict = None) -> dict | list | None:
    for attempt in range(3):
        try:
            r = SESSION.get(url, params=params, timeout=15)
            remaining = int(r.headers.get("X-RateLimit-Remaining", 999))
            if remaining < 50:
                print(f"  [rate limit low: {remaining}] sleeping {RETRY_SLEEP}s...")
                time.sleep(RETRY_SLEEP)
            if r.status_code == 403:
                print(f"  [403] sleeping {RETRY_SLEEP}s...")
                time.sleep(RETRY_SLEEP)
                continue
            if r.status_code == 404:
                return None
            if r.status_code != 200:
                return None
            time.sleep(RATE_LIMIT_SLEEP)
            return r.json()
        except Exception as e:
            print(f"  [network error] {e}, retry {attempt+1}")
            time.sleep(5)
    return None


def search_repos(query: str, per_page: int = 100, max_pages: int = 5) -> list[dict]:
    repos = []
    for page in range(1, max_pages + 1):
        data = gh_get("https://api.github.com/search/repositories", {
            "q": query, "per_page": per_page, "page": page, "sort": "updated",
        })
        if not data or "items" not in data:
            break
        items = data["items"]
        repos.extend(items)
        if len(items) < per_page:
            break
        if len(repos) >= 500:
            break
    return repos


def get_python_files(owner: str, repo: str, path: str = "") -> list[dict]:
    """Return list of .py file entries from the repo tree."""
    data = gh_get(f"https://api.github.com/repos/{owner}/{repo}/git/trees/HEAD", {
        "recursive": "1"
    })
    if not data or "tree" not in data:
        return []
    return [
        f for f in data["tree"]
        if f.get("type") == "blob"
        and f.get("path", "").endswith(".py")
        and f.get("size", 0) <= MAX_FILE_SIZE_BYTES
        and f.get("size", 0) > 0
        and not any(skip in f["path"] for skip in [
            "test_", "_test", "migration", "setup.py", "conf.py",
            "__pycache__", ".eggs", "vendor/", "third_party/",
        ])
    ]


def download_file(owner: str, repo: str, path: str) -> str | None:
    data = gh_get(f"https://api.github.com/repos/{owner}/{repo}/contents/{path}")
    if not data or "content" not in data:
        return None
    try:
        return base64.b64decode(data["content"]).decode("utf-8", errors="replace")
    except Exception:
        return None

# ── vibe-slop runner ──────────────────────────────────────────────────────────

def run_vibe_slop(filepath: Path) -> dict | None:
    """Run vibe-slop --json on a file and return parsed output."""
    try:
        result = subprocess.run(
            ["vibe-slop", "check", str(filepath), "--json"],
            capture_output=True, text=True, timeout=30
        )
        output = result.stdout.strip()
        if output:
            return json.loads(output)
    except (subprocess.TimeoutExpired, json.JSONDecodeError, Exception):
        pass
    return None

# ── Collection ────────────────────────────────────────────────────────────────

def collect_group(label: str, queries: list[str]) -> list[dict]:
    """
    Collect ~TARGET_FILES_PER_GROUP file results for one group.
    Returns list of result dicts (one per file).
    """
    print(f"\n{'='*60}")
    print(f"Collecting: {label.upper()} group (target: {TARGET_FILES_PER_GROUP} files)")
    print(f"{'='*60}")

    seen_repos: set[str] = set()
    all_repos: list[dict] = []

    for q in queries:
        print(f"\n  Searching: {q[:70]}...")
        found = search_repos(q)
        for r in found:
            full_name = r["full_name"]
            if full_name not in seen_repos:
                seen_repos.add(full_name)
                all_repos.append(r)
        print(f"  → {len(all_repos)} unique repos so far")
        if len(all_repos) >= 400:
            break

    random.shuffle(all_repos)
    results: list[dict] = []
    group_dir = TEMP_DIR / label
    group_dir.mkdir(exist_ok=True)

    for repo_info in all_repos:
        if len(results) >= TARGET_FILES_PER_GROUP:
            break

        owner = repo_info["owner"]["login"]
        repo  = repo_info["name"]
        print(f"\n  [{len(results)}/{TARGET_FILES_PER_GROUP}] {owner}/{repo}")

        py_files = get_python_files(owner, repo)
        if not py_files:
            print("    → no suitable .py files, skip")
            continue

        random.shuffle(py_files)
        py_files = py_files[:MAX_FILES_PER_REPO]

        repo_dir = group_dir / f"{owner}__{repo}"
        repo_dir.mkdir(exist_ok=True)
        files_analyzed = 0

        for file_meta in py_files:
            if len(results) >= TARGET_FILES_PER_GROUP:
                break

            fpath = file_meta["path"]
            content = download_file(owner, repo, fpath)
            if not content:
                continue

            lines = content.splitlines()
            if len(lines) < MIN_FILE_LINES:
                continue

            # Save to temp file
            safe_name = fpath.replace("/", "__")
            local_path = repo_dir / safe_name
            local_path.write_text(content, encoding="utf-8", errors="replace")

            # Analyze
            report = run_vibe_slop(local_path)
            if report is None:
                local_path.unlink(missing_ok=True)
                continue

            record = {
                "group":      label,
                "repo":       f"{owner}/{repo}",
                "file":       fpath,
                "lines":      len(lines),
                "score":      report.get("score", 0),
                "band":       report.get("band", ""),
                "n_findings": len(report.get("findings", [])),
                "categories": Counter(
                    f["category"] for f in report.get("findings", [])
                ),
                "severities": Counter(
                    f["severity"] for f in report.get("findings", [])
                ),
            }

            results.append(record)
            files_analyzed += 1

            # Append to raw JSONL immediately (crash-safe)
            with open(RAW_JSONL, "a") as fh:
                fh.write(json.dumps({**record, "categories": dict(record["categories"]),
                                     "severities": dict(record["severities"])}) + "\n")

            # Delete temp file immediately to save space
            local_path.unlink(missing_ok=True)

        # Delete empty repo dir
        if not any(repo_dir.iterdir()):
            repo_dir.rmdir()

        print(f"    → analyzed {files_analyzed} files (total: {len(results)})")

    # Clean up group temp dir
    if group_dir.exists():
        shutil.rmtree(group_dir, ignore_errors=True)

    print(f"\n  Finished {label}: {len(results)} files analyzed")
    return results

# ── Statistics ────────────────────────────────────────────────────────────────

def group_stats(records: list[dict]) -> dict:
    scores = [r["score"] for r in records]
    if not scores:
        return {}

    band_counts = Counter(r["band"] for r in records)
    cat_counts: Counter = Counter()
    for r in records:
        cat_counts.update(r["categories"])

    return {
        "n": len(scores),
        "mean":   round(statistics.mean(scores), 2),
        "median": round(statistics.median(scores), 2),
        "stdev":  round(statistics.stdev(scores), 2) if len(scores) > 1 else 0,
        "min":    min(scores),
        "max":    max(scores),
        "pct25":  round(sorted(scores)[len(scores) // 4], 2),
        "pct75":  round(sorted(scores)[3 * len(scores) // 4], 2),
        "band_distribution": dict(band_counts),
        "top_categories":    dict(cat_counts.most_common(10)),
    }


def compute_accuracy(ai_records: list[dict], human_records: list[dict]) -> dict:
    """
    Treat vibe-slop score as a classifier: score >= threshold → AI.
    Sweep threshold 0-100 to find best accuracy, compute AUC.
    """
    ai_scores    = [r["score"] for r in ai_records]
    human_scores = [r["score"] for r in human_records]

    # Mann-Whitney U test
    u_stat, p_value = stats.mannwhitneyu(ai_scores, human_scores, alternative="greater")

    # Sweep thresholds for ROC
    all_scores = ai_scores + human_scores
    labels     = [1] * len(ai_scores) + [0] * len(human_scores)

    thresholds = sorted(set(all_scores))
    roc_points = []
    best = {"threshold": 50, "accuracy": 0, "f1": 0}

    for t in thresholds:
        preds = [1 if s >= t else 0 for s in all_scores]
        tp = sum(1 for p, l in zip(preds, labels) if p == 1 and l == 1)
        tn = sum(1 for p, l in zip(preds, labels) if p == 0 and l == 0)
        fp = sum(1 for p, l in zip(preds, labels) if p == 1 and l == 0)
        fn = sum(1 for p, l in zip(preds, labels) if p == 0 and l == 1)

        acc       = (tp + tn) / len(labels) if labels else 0
        precision = tp / (tp + fp) if (tp + fp) > 0 else 0
        recall    = tp / (tp + fn) if (tp + fn) > 0 else 0
        f1        = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0
        tpr       = recall
        fpr       = fp / (fp + tn) if (fp + tn) > 0 else 0

        roc_points.append((fpr, tpr))
        if f1 > best["f1"]:
            best = {
                "threshold": t, "accuracy": round(acc, 4),
                "precision": round(precision, 4), "recall": round(recall, 4),
                "f1": round(f1, 4),
                "confusion": {"tp": tp, "fp": fp, "fn": fn, "tn": tn},
            }

    # AUC via trapezoidal rule
    roc_sorted = sorted(set(roc_points))
    auc = sum(
        (roc_sorted[i+1][0] - roc_sorted[i][0]) *
        (roc_sorted[i+1][1] + roc_sorted[i][1]) / 2
        for i in range(len(roc_sorted) - 1)
    )

    return {
        **best,
        "auc":            round(auc, 4),
        "mannwhitney_u":  round(float(u_stat), 2),
        "p_value":        round(float(p_value), 6),
        "significant":    p_value < 0.05,
    }

# ── Report ────────────────────────────────────────────────────────────────────

def write_report(ai_stats: dict, human_stats: dict, accuracy: dict) -> None:
    lines = [
        f"# vibe-slop Benchmark Report",
        f"",
        f"Generated: {datetime.now().isoformat()}",
        f"",
        f"## Methodology",
        f"",
        f"| | AI Group | Human Group |",
        f"|---|---|---|",
        f"| Source | GitHub repos created 2024+ with AI tool mentions | GitHub repos created 2013–2017 with 50–500 stars |",
        f"| Rationale | Explicit AI-assisted coding (README mentions ChatGPT, Claude, Copilot, vibe coding) | Pre-ChatGPT era — human-written by definition |",
        f"| Files analyzed | {ai_stats['n']} | {human_stats['n']} |",
        f"| Min file size | {MIN_FILE_LINES} lines | {MIN_FILE_LINES} lines |",
        f"",
        f"## Score Distribution",
        f"",
        f"| Metric | AI Group | Human Group |",
        f"|---|---|---|",
        f"| Mean score | **{ai_stats['mean']}** | **{human_stats['mean']}** |",
        f"| Median | {ai_stats['median']} | {human_stats['median']} |",
        f"| Std dev | {ai_stats['stdev']} | {human_stats['stdev']} |",
        f"| 25th pct | {ai_stats['pct25']} | {human_stats['pct25']} |",
        f"| 75th pct | {ai_stats['pct75']} | {human_stats['pct75']} |",
        f"| Min | {ai_stats['min']} | {human_stats['min']} |",
        f"| Max | {ai_stats['max']} | {human_stats['max']} |",
        f"",
        f"## Band Distribution",
        f"",
        f"| Band | AI Group | Human Group |",
        f"|---|---|---|",
    ]
    for band in ["Clean", "Slightly Sloppy", "Sloppy", "Very Sloppy", "Slop"]:
        ai_n    = ai_stats["band_distribution"].get(band, 0)
        hu_n    = human_stats["band_distribution"].get(band, 0)
        ai_pct  = round(100 * ai_n / ai_stats["n"], 1) if ai_stats["n"] else 0
        hu_pct  = round(100 * hu_n / human_stats["n"], 1) if human_stats["n"] else 0
        lines.append(f"| {band} | {ai_n} ({ai_pct}%) | {hu_n} ({hu_pct}%) |")

    lines += [
        f"",
        f"## Top Slop Categories (AI Group)",
        f"",
        f"| Category | Count |",
        f"|---|---|",
    ]
    for cat, cnt in list(ai_stats["top_categories"].items())[:10]:
        lines.append(f"| {cat} | {cnt} |")

    lines += [
        f"",
        f"## Top Slop Categories (Human Group)",
        f"",
        f"| Category | Count |",
        f"|---|---|",
    ]
    for cat, cnt in list(human_stats["top_categories"].items())[:10]:
        lines.append(f"| {cat} | {cnt} |")

    sig_str = "Yes (p < 0.05)" if accuracy["significant"] else "No (p ≥ 0.05)"
    lines += [
        f"",
        f"## Classifier Accuracy",
        f"",
        f"Using vibe-slop score as a binary classifier (score ≥ threshold → AI-generated):",
        f"",
        f"| Metric | Value |",
        f"|---|---|",
        f"| Best threshold | {accuracy['threshold']} |",
        f"| Accuracy | {accuracy['accuracy']} ({accuracy['accuracy']*100:.1f}%) |",
        f"| Precision | {accuracy['precision']} |",
        f"| Recall | {accuracy['recall']} |",
        f"| F1 Score | {accuracy['f1']} |",
        f"| AUC-ROC | {accuracy['auc']} |",
        f"",
        f"## Statistical Significance",
        f"",
        f"| Test | Value |",
        f"|---|---|",
        f"| Mann-Whitney U | {accuracy['mannwhitney_u']} |",
        f"| p-value | {accuracy['p_value']} |",
        f"| Significant (α=0.05) | {sig_str} |",
        f"",
        f"## Confusion Matrix (at best threshold = {accuracy['threshold']})",
        f"",
        f"| | Predicted AI | Predicted Human |",
        f"|---|---|---|",
        f"| Actual AI | {accuracy['confusion']['tp']} (TP) | {accuracy['confusion']['fn']} (FN) |",
        f"| Actual Human | {accuracy['confusion']['fp']} (FP) | {accuracy['confusion']['tn']} (TN) |",
        f"",
        f"## Raw Data",
        f"",
        f"- Raw results (per file): `{RAW_JSONL.name}`",
        f"- Full summary JSON: `{SUMMARY_JSON.name}`",
    ]

    REPORT_MD.write_text("\n".join(lines), encoding="utf-8")
    print(f"\nReport saved: {REPORT_MD}")

# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    print("vibe-slop Benchmark")
    print(f"Target: {TARGET_FILES_PER_GROUP} files per group")
    print(f"Results: {RESULTS_DIR}")
    print(f"Temp:    {TEMP_DIR} (deleted after run)")

    random.seed(42)

    ai_records    = collect_group("ai",    AI_QUERIES)
    human_records = collect_group("human", HUMAN_QUERIES)

    if len(ai_records) < 10 or len(human_records) < 10:
        print("ERROR: Not enough files collected for meaningful analysis.")
        sys.exit(1)

    print("\nComputing statistics...")
    ai_stats    = group_stats(ai_records)
    human_stats = group_stats(human_records)
    accuracy    = compute_accuracy(ai_records, human_records)

    summary = {
        "metadata": {
            "timestamp":    TIMESTAMP,
            "ai_files":     ai_stats["n"],
            "human_files":  human_stats["n"],
            "target":       TARGET_FILES_PER_GROUP,
        },
        "ai":       ai_stats,
        "human":    human_stats,
        "accuracy": accuracy,
    }

    SUMMARY_JSON.write_text(
        json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    write_report(ai_stats, human_stats, accuracy)

    # Clean up temp dir entirely
    if TEMP_DIR.exists():
        shutil.rmtree(TEMP_DIR, ignore_errors=True)
        print(f"\nTemp directory deleted: {TEMP_DIR}")

    print("\n" + "="*60)
    print("RESULTS SUMMARY")
    print("="*60)
    print(f"AI    group: n={ai_stats['n']:4d}  mean={ai_stats['mean']:5.1f}  median={ai_stats['median']:5.1f}")
    print(f"Human group: n={human_stats['n']:4d}  mean={human_stats['mean']:5.1f}  median={human_stats['median']:5.1f}")
    print(f"Accuracy:    {accuracy['accuracy']*100:.1f}%  AUC: {accuracy['auc']:.3f}  p={accuracy['p_value']:.4f}")
    print(f"\nFull report: {REPORT_MD}")


if __name__ == "__main__":
    main()
