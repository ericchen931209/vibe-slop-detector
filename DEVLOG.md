# Vibe Slop Detector — Dev Log

> 記錄實作過程、設計決策、與使用者討論的問題。

---

## 2026-07-04 — 專案啟動 & Taxonomy 定義

### 背景

使用者（Yu-Wei Chen）想建立一個工具，偵測 AI 產生的低品質程式碼（"vibe slop"）。
目標：公開給大眾使用的 CLI 工具，未來可以發展成論文。

### 核心決策

| 決策 | 選擇 | 原因 |
|---|---|---|
| 實作語言 | Python | 生態最穩定，tree-sitter / Claude SDK / rich 都有支援 |
| 介面 | CLI only，無 Web server | 避免使用者透過網路攻擊 |
| 支援語言 | 從 Python 開始，逐步擴展 | 先求穩再求廣 |
| 輸出格式 | 雙軌：人類可讀文字 + JSON | 終端直接看，JSON 方便 AI / pipeline 串接 |
| 與 ADB 的關係 | 無關 | 獨立專案 |

### Taxonomy 建立

定義了 13 種 Slop 類別（詳見 TAXONOMY.md）：

- **S1** Ghost Comment — 解釋顯而易見的程式碼的註解
- **S2** AI Signature Phrase — AI 助手用語洩漏進代碼（"certainly", "as an AI"）
- **S3** God Function — 一個函式做太多事、太長
- **S4** Dead Import — import 了但沒用到
- **S5** Copy-Paste Clone — 高相似度的重複代碼塊
- **S6** Generic Naming — `data`, `result`, `temp` 等語義空洞的命名
- **S7** Void Abstraction — 只有一行的空洞包裝函式
- **S8** Magic Number — 沒有命名的數字常數
- **S9** False Safety Net — `try: except: pass` 型的假錯誤處理
- **S10** Verbosity Inflation — 3 行能寫完卻寫了 15 行
- **S11** Redundant Docstring — 只是重述函式名稱的 docstring
- **S12** Defensive Over-checking — 不可能發生的條件判斷
- **S13** TODO Graveyard — 大量 TODO/FIXME 留在代碼裡

### 使用者提問與決策

**Q: S7 Void Abstraction 要預設開啟還是關閉？**

使用者不熟悉這個概念，所以先解釋：
- Abstraction 是「把複雜邏輯包裝起來」
- Void Abstraction 是包裝了但沒有任何好處（如 `def get_name(user): return user.name`）
- 問題：「delegation pattern」長得一樣但是故意設計的（為了以後換實作只改一個地方）

**決策：預設開啟，嚴重度 LOW。**
理由：LOW 讓使用者自己判斷要不要理，不至於造成誤判恐慌。

---

**Q: Boilerplate 要不要排除？**

使用者不熟悉 boilerplate，所以先解釋：
- Boilerplate = 必須存在但不是你寫的固定格式代碼（如 ORM model、protobuf 自動生成）
- 問題：這些檔案充滿 Generic Naming 等 slop 特徵，但不是真的 slop

**決策：預設排除，透過 `--ignore` glob pattern 讓使用者自行指定。**
理由：讓使用者控制，不做複雜的自動偵測，降低實作複雜度。
例：`vibe-slop check src/ --ignore "models/*,*_pb2.py"`

---

---

## 2026-07-04 — 實作 v0.1

### 專案結構

```
vibe_slop/
├── models.py         # Finding, FileReport, Severity, Layer 資料型別
├── analyzer.py       # 協調 static + LLM 兩層分析
├── cli.py            # typer CLI (check, rules 兩個子命令)
├── static/
│   ├── engine.py     # tree-sitter 解析 + 呼叫各 rule
│   └── rules/        # 每個 slop 類別一個檔案
│       ├── ai_signature.py     (S2)
│       ├── dead_import.py      (S4)
│       ├── false_safety_net.py (S9)
│       ├── generic_naming.py   (S6)
│       ├── god_function.py     (S3)
│       ├── magic_number.py     (S8)
│       ├── todo_graveyard.py   (S13)
│       └── void_abstraction.py (S7)
├── llm/
│   └── judge.py      # Claude API judge (S1, S10, S11)
└── report/
    ├── human.py      # rich 終端輸出
    └── machine.py    # JSON 輸出
```

### 技術決策

**Typer subcommand routing 問題**
只有一個 `@app.command()` 時，typer 不做 subcommand routing，`check` 會被吃掉當作 TARGET 參數。
解法：加 `rules` 子命令，讓 app 有兩個命令，routing 自動啟動。

**LLM 失敗不終止程式**
LLM Judge（`--llm`）失敗時，保留 static 結果繼續輸出，只在 error 欄位紀錄錯誤。
理由：網路/API key 問題不應該讓整個分析失敗。

**S7 noqa 機制**
`# noqa: S7` 可以在單行抑制 Void Abstraction 警告，供 delegation pattern 使用。

### 測試結果

對 `tests/fixtures/sample_slop.py` 掃描，偵測到 9 個問題，分數 100/100（Slop）：
- S2: "Certainly" 在第 1 行
- S4: json, os, threading 三個 dead import
- S6: "result" 出現 4 次
- S7: get_name 是 void abstraction
- S3: fetch 有 8 個參數
- S9: bare except: pass
- S13: 4 個 TODO/FIXME

### 待處理

- [x] 推到 GitHub
- [ ] 實作 Copy-Paste Clone（S5）— 需要 token similarity 演算法
- [ ] 實作 Defensive Over-checking（S12）— Static + LLM
- [ ] 擴展語言支援：JavaScript / TypeScript

---

## 2026-07-04 — 自我偵測 & Bug 修復

### Self-check 發現的問題

把 vibe-slop 對自己執行，發現 3 個真實 bug：

**Bug 1: Dead Import (S4) 大量誤判**
`from X import Y` 被錯誤地把模組名 `X` 標記為未使用。
原因：`_collect_imports` 對 `import_statement` 和 `import_from_statement` 使用相同邏輯，但前者的 `dotted_name` 是「要 import 的東西」，後者的第一個 `dotted_name` 是「從哪裡 import」。
修法：區分兩種 statement，`from_statement` 跳過第一個 `dotted_name`。

**Bug 2: AI Signature (S2) 自我誤判**
Regex pattern 字串本身含有 "certainly"、"i cannot" 等詞，被自己偵測到。
修法：只掃 `#` 為第一個非空白字元的純 comment 行。

**Bug 3: TODO Graveyard (S13) docstring 誤判**
docstring 裡寫到 "TODO" 就觸發規則（如檔案說明字串）。
修法：要求 marker 出現在 `#` 之後（即真正的 comment context）。

### 使用者提問

**Q: 為什麼 `god_function.py` 的 `check` 函式被自己標記？**
54 行，超過 50 行閾值。
解法：拆成 `_check_length` 和 `_check_params` 兩個 helper，主函式縮到閾值以下。

---

## 2026-07-04 — GitHub Benchmark（AI vs Human Python repos）

### 方法

| | AI 群組 | Human 群組 |
|---|---|---|
| 來源 | GitHub 2024+ 且 README 有 AI 工具字眼 | GitHub 2012–2017 建立，50–600 stars |
| 理由 | 明確 AI 輔助開發 | ChatGPT 出現前，必然為人工撰寫 |
| 分析數量 | 400 個 Python 檔案 | 400 個 Python 檔案 |

### 量化結果

| 指標 | AI 群組 | Human 群組 |
|---|---|---|
| 平均分數 | 59.8 | 61.5 |
| 中位數 | 65.5 | 74.0 |
| 標準差 | 41.4 | 40.7 |
| AUC-ROC | 0.494（≈隨機） | — |
| p-value | 0.615（不顯著） | — |

### 分類別差異

| 類別 | AI 比例 | Human 比例 | 差異 |
|---|---|---|---|
| S9 False Safety Net | 16.8% | 12.8% | AI 較多（+4pp）|
| S8 Magic Number（平均/檔） | 3.50 | 4.78 | **Human 較多** |
| S4 Dead Import | 42.2% | 78.5% | **Human 遠多於 AI** |
| S7 Void Abstraction | 33.2% | 95.0% | **Human 遠多於 AI** |
| S3 God Function | 79.8% | 70.5% | AI 稍多 |
| S6 Generic Naming | 76.0% | 73.8% | 幾乎相同 |

### 關鍵發現（重要）

**Static analysis 的 slop 規則無法可靠地區分 AI 與 Human 代碼（AUC ≈ 0.5）。**

原因分析：
1. **S8 Magic Number 在舊的 human code 更多**：2012–2017 年的 Python code 大量使用裸數字常數（科學運算、ML 參數），反而被工具標記更多次。
2. **S4 Dead Import 在舊 code 更多**：老 Python 不像現代 IDE 會警告 unused import，死 import 更普遍。
3. **S7 Void Abstraction 在舊 code 極多（95%）**：老 Python 喜歡 delegation pattern / getter 函式，現代 AI 生成的代碼反而更直接存取屬性。
4. **唯一有區別力的是 S9 False Safety Net（AI 1.74x 於 human）**，但差異不夠大。

### 對論文的意義

- 這是一個**負面結果，但有研究價值**：純靜態 pattern 分析不足以識別 AI 代碼
- **需要 LLM Judge 層**（S1 Ghost Comment、S10 Verbosity Inflation、S11 Redundant Docstring）才可能提升 AUC
- **Taxonomy 需要精煉**：把 S8、S4、S7 的權重降低，或只在 AI-specific context 下才計分
- **S9 False Safety Net 是最有區別力的靜態規則**，值得在論文中強調

### 使用者提問

**Q: 準確率怎麼做比較？**
解釋：以 vibe-slop score 為二元分類器（score ≥ threshold → AI），掃 0–100 所有閾值找最高 F1，計算 AUC-ROC。結果 AUC = 0.494（≈隨機），顯示靜態規則不具區別力。

**Q: 要如何改善？**
方向：加入 LLM Judge 層（語義分析）、調整各規則的論文權重、收集更「乾淨」的 AI vs 人工標記資料集。
