#!/usr/bin/env python3
"""Final analysis: merge AI + human records, compute stats and accuracy report."""

import json, statistics, math
from collections import Counter
from datetime import datetime
from pathlib import Path
from scipy import stats

RESULTS_DIR = Path(__file__).parent / "results"
TIMESTAMP   = datetime.now().strftime("%Y%m%d_%H%M%S")

# ── Load data ─────────────────────────────────────────────────────────────────

def load_group(label, files):
    records, seen = [], set()
    for fpath in files:
        with open(fpath) as f:
            for line in f:
                r = json.loads(line)
                if r.get("group") != label:
                    continue
                key = (r["repo"], r["file"])
                if key not in seen:
                    seen.add(key)
                    records.append(r)
    return records

ai_files    = sorted(RESULTS_DIR.glob("raw_2*.jsonl"))
human_files = sorted(RESULTS_DIR.glob("raw_human_*.jsonl"))

ai_records    = load_group("ai",    ai_files)
human_records = load_group("human", human_files)

print(f"AI records:    {len(ai_records)}")
print(f"Human records: {len(human_records)}")

# ── Statistics ────────────────────────────────────────────────────────────────

def group_stats(records):
    scores = sorted(r["score"] for r in records)
    n = len(scores)
    cat_counts = Counter()
    for r in records:
        cat_counts.update(r.get("categories", {}))
    return {
        "n":        n,
        "mean":     round(statistics.mean(scores), 2),
        "median":   round(statistics.median(scores), 2),
        "stdev":    round(statistics.stdev(scores), 2),
        "min":      scores[0],
        "max":      scores[-1],
        "pct25":    scores[n // 4],
        "pct75":    scores[3 * n // 4],
        "band_distribution": dict(Counter(r["band"] for r in records)),
        "top_categories":    dict(cat_counts.most_common(13)),
        "scores":   scores,
    }

ai_s    = group_stats(ai_records)
human_s = group_stats(human_records)

# ── Accuracy (ROC sweep) ──────────────────────────────────────────────────────

ai_scores    = ai_s["scores"]
human_scores = human_s["scores"]
all_scores   = ai_scores + human_scores
labels       = [1] * len(ai_scores) + [0] * len(human_scores)

u_stat, p_value = stats.mannwhitneyu(ai_scores, human_scores, alternative="greater")
effect_size_r = u_stat / (len(ai_scores) * len(human_scores))  # rank-biserial r

thresholds = sorted(set(all_scores))
best = {"f1": 0}
roc_points = [(0.0, 0.0)]

for t in thresholds:
    preds = [1 if s >= t else 0 for s in all_scores]
    tp = sum(1 for p, l in zip(preds, labels) if p==1 and l==1)
    tn = sum(1 for p, l in zip(preds, labels) if p==0 and l==0)
    fp = sum(1 for p, l in zip(preds, labels) if p==1 and l==0)
    fn = sum(1 for p, l in zip(preds, labels) if p==0 and l==1)
    acc  = (tp+tn) / len(labels)
    prec = tp/(tp+fp) if (tp+fp) else 0
    rec  = tp/(tp+fn) if (tp+fn) else 0
    f1   = 2*prec*rec/(prec+rec) if (prec+rec) else 0
    tpr  = rec
    fpr  = fp/(fp+tn) if (fp+tn) else 0
    roc_points.append((fpr, tpr))
    if f1 > best["f1"]:
        best = {"threshold": t, "accuracy": round(acc,4), "precision": round(prec,4),
                "recall": round(rec,4), "f1": round(f1,4),
                "confusion": {"tp":tp,"fp":fp,"fn":fn,"tn":tn}}

roc_points.append((1.0, 1.0))
roc_sorted = sorted(set(roc_points))
auc = sum(
    (roc_sorted[i+1][0] - roc_sorted[i][0]) *
    (roc_sorted[i+1][1] + roc_sorted[i][1]) / 2
    for i in range(len(roc_sorted)-1)
)

accuracy = {
    **best,
    "auc":           round(auc, 4),
    "mannwhitney_u": round(float(u_stat), 1),
    "p_value":       float(p_value),
    "p_value_str":   f"{p_value:.2e}" if p_value < 0.001 else f"{p_value:.4f}",
    "effect_size_r": round(effect_size_r, 4),
    "significant":   bool(p_value < 0.05),
}

# ── Save summary JSON ─────────────────────────────────────────────────────────

summary = {
    "metadata": {"timestamp": TIMESTAMP, "ai_n": ai_s["n"], "human_n": human_s["n"]},
    "ai":       {k:v for k,v in ai_s.items() if k != "scores"},
    "human":    {k:v for k,v in human_s.items() if k != "scores"},
    "accuracy": accuracy,
}
out_json = RESULTS_DIR / f"summary_{TIMESTAMP}.json"
out_json.write_text(json.dumps(summary, indent=2), encoding="utf-8")

# ── Write Markdown report ─────────────────────────────────────────────────────

BANDS = ["Clean","Slightly Sloppy","Sloppy","Very Sloppy","Slop"]
CAT_NAMES = {
    "S1":"Ghost Comment","S2":"AI Signature Phrase","S3":"God Function",
    "S4":"Dead Import","S5":"Copy-Paste Clone","S6":"Generic Naming",
    "S7":"Void Abstraction","S8":"Magic Number","S9":"False Safety Net",
    "S10":"Verbosity Inflation","S11":"Redundant Docstring",
    "S12":"Defensive Over-check","S13":"TODO Graveyard",
}

sig_str = f"**Yes** (p = {accuracy['p_value_str']})" if accuracy["significant"] \
          else f"No (p = {accuracy['p_value_str']})"
effect_label = (
    "large (r > 0.5)"   if effect_size_r > 0.5 else
    "medium (r > 0.3)"  if effect_size_r > 0.3 else
    "small (r > 0.1)"   if effect_size_r > 0.1 else "negligible"
)

lines = [
f"# vibe-slop Benchmark Report",
f"",
f"**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M')}  ",
f"**Tool version:** vibe-slop v0.1.0 (static layer only, no LLM)",
f"",
f"---",
f"",
f"## 1. Methodology",
f"",
f"### Dataset",
f"",
f"| | AI-assisted Group | Human-written Group |",
f"|---|---|---|",
f"| **Source** | GitHub repos created 2024+ with AI tool mentions in README | GitHub repos created 2012–2017 with 50–600 stars |",
f"| **Rationale** | README explicitly mentions ChatGPT, Claude, Copilot, or \"vibe coding\" | Pre-ChatGPT era — human-written by construction |",
f"| **Files analyzed** | {ai_s['n']} Python files | {human_s['n']} Python files |",
f"| **Sampling** | Up to 8 files per repo, ≥20 lines, ≤60 KB | Same constraints |",
f"",
f"### Detection",
f"",
f"vibe-slop static analysis layer (tree-sitter AST, no LLM): rules S2–S4, S6–S9, S13.",
f"Each file receives a Slop Score 0–100 (higher = more slop patterns detected).",
f"",
f"---",
f"",
f"## 2. Score Distribution",
f"",
f"| Metric | AI-assisted | Human-written | Δ |",
f"|---|---|---|---|",
f"| **Mean score** | **{ai_s['mean']}** | **{human_s['mean']}** | **+{ai_s['mean']-human_s['mean']:.1f}** |",
f"| Median | {ai_s['median']} | {human_s['median']} | +{ai_s['median']-human_s['median']:.1f} |",
f"| Std dev | {ai_s['stdev']} | {human_s['stdev']} | — |",
f"| 25th pct | {ai_s['pct25']} | {human_s['pct25']} | — |",
f"| 75th pct | {ai_s['pct75']} | {human_s['pct75']} | — |",
f"| Min / Max | {ai_s['min']} / {ai_s['max']} | {human_s['min']} / {human_s['max']} | — |",
f"",
f"---",
f"",
f"## 3. Band Distribution",
f"",
f"| Band | AI-assisted | | Human-written | |",
f"|---|---|---|---|---|",
f"| | Count | % | Count | % |",
]
for band in BANDS:
    an = ai_s["band_distribution"].get(band, 0)
    hn = human_s["band_distribution"].get(band, 0)
    ap = round(100*an/ai_s["n"], 1)
    hp = round(100*hn/human_s["n"], 1)
    lines.append(f"| {band} | {an} | {ap}% | {hn} | {hp}% |")

lines += [
f"",
f"---",
f"",
f"## 4. Slop Category Breakdown",
f"",
f"| Category | AI count | Human count | Ratio (AI/Human) |",
f"|---|---|---|---|",
]
all_cats = sorted(set(list(ai_s["top_categories"].keys()) + list(human_s["top_categories"].keys())))
for cat in all_cats:
    an = ai_s["top_categories"].get(cat, 0)
    hn = human_s["top_categories"].get(cat, 0)
    ratio = f"{an/hn:.2f}x" if hn > 0 else "∞"
    name = CAT_NAMES.get(cat, cat)
    lines.append(f"| {cat} {name} | {an} | {hn} | {ratio} |")

lines += [
f"",
f"---",
f"",
f"## 5. Binary Classification Accuracy",
f"",
f"Treating vibe-slop score as a binary classifier (score ≥ threshold → AI-generated):",
f"",
f"| Metric | Value |",
f"|---|---|",
f"| **AUC-ROC** | **{accuracy['auc']}** |",
f"| Best threshold | {accuracy['threshold']} |",
f"| Accuracy | {accuracy['accuracy']} ({accuracy['accuracy']*100:.1f}%) |",
f"| Precision | {accuracy['precision']} |",
f"| Recall / Sensitivity | {accuracy['recall']} |",
f"| F1 Score | {accuracy['f1']} |",
f"",
f"### Confusion Matrix (threshold = {accuracy['threshold']})",
f"",
f"| | Predicted AI | Predicted Human |",
f"|---|---|---|",
f"| **Actual AI** | {accuracy['confusion']['tp']} TP | {accuracy['confusion']['fn']} FN |",
f"| **Actual Human** | {accuracy['confusion']['fp']} FP | {accuracy['confusion']['tn']} TN |",
f"",
f"---",
f"",
f"## 6. Statistical Significance",
f"",
f"| Test | Value |",
f"|---|---|",
f"| Mann-Whitney U statistic | {accuracy['mannwhitney_u']} |",
f"| p-value | {accuracy['p_value_str']} |",
f"| Significant (α = 0.05) | {sig_str} |",
f"| Effect size (rank-biserial r) | {accuracy['effect_size_r']} — {effect_label} |",
f"",
f"---",
f"",
f"## 7. Interpretation",
f"",
]

mean_diff = ai_s['mean'] - human_s['mean']
if accuracy['auc'] >= 0.70:
    auc_interp = f"The AUC of **{accuracy['auc']}** indicates vibe-slop has **meaningful discriminative power** between AI-assisted and human-written code."
elif accuracy['auc'] >= 0.60:
    auc_interp = f"The AUC of **{accuracy['auc']}** indicates vibe-slop has **moderate discriminative power** — better than random but not strong."
else:
    auc_interp = f"The AUC of **{accuracy['auc']}** is near random chance — static patterns alone may not reliably discriminate."

lines += [
f"{auc_interp}",
f"",
f"- AI-assisted files score **{mean_diff:.1f} points higher** on average ({ai_s['mean']} vs {human_s['mean']}).",
f"- The most discriminative categories are those with the highest AI/Human ratios in Section 4.",
f"- Statistical test confirms the score difference is {'statistically significant' if accuracy['significant'] else 'not statistically significant at α=0.05'}.",
f"- Effect size r = {accuracy['effect_size_r']} ({effect_label}) suggests {'a real and notable' if effect_size_r > 0.3 else 'a modest'} practical difference.",
f"",
f"### Limitations",
f"",
f"- **Label noise:** \"AI-assisted\" label is inferred from README mentions — some repos may be human-written despite mentions, or partially AI-generated.",
f"- **Static analysis only:** LLM-detected categories (S1 Ghost Comment, S10 Verbosity Inflation, S11 Redundant Docstring) were not used.",
f"- **Language:** Python only (v0.1 supports Python exclusively).",
f"- **Sample bias:** Human repos selected by star count — popular code may be cleaner than average.",
f"",
f"---",
f"",
f"## 8. Files",
f"",
f"| File | Description |",
f"|---|---|",
]
for f in sorted(RESULTS_DIR.glob("raw_*.jsonl")):
    lines.append(f"| `{f.name}` | Raw per-file results |")
lines.append(f"| `{out_json.name}` | Full summary JSON |")

out_md = RESULTS_DIR / f"report_{TIMESTAMP}.md"
out_md.write_text("\n".join(lines), encoding="utf-8")

# ── Print summary ─────────────────────────────────────────────────────────────

print("\n" + "="*60)
print("BENCHMARK RESULTS")
print("="*60)
print(f"AI    group: n={ai_s['n']:4d}  mean={ai_s['mean']:5.1f}  median={ai_s['median']:5.1f}  stdev={ai_s['stdev']:5.1f}")
print(f"Human group: n={human_s['n']:4d}  mean={human_s['mean']:5.1f}  median={human_s['median']:5.1f}  stdev={human_s['stdev']:5.1f}")
print(f"Score gap:   Δmean={ai_s['mean']-human_s['mean']:+.1f}  Δmedian={ai_s['median']-human_s['median']:+.1f}")
print(f"")
print(f"AUC-ROC:   {accuracy['auc']:.3f}")
print(f"Best F1:   {accuracy['f1']:.3f}  (threshold={accuracy['threshold']}, acc={accuracy['accuracy']*100:.1f}%)")
print(f"p-value:   {accuracy['p_value_str']}  {'✓ significant' if accuracy['significant'] else '✗ not significant'}")
print(f"Effect r:  {accuracy['effect_size_r']}  ({effect_label})")
print(f"")
print(f"Report:  {out_md}")
print(f"Summary: {out_json}")
