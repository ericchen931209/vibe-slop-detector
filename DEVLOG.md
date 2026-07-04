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

- [ ] 推到 GitHub（需要 `gh auth login`）
- [ ] 實作 Copy-Paste Clone（S5）— 需要 token similarity 演算法
- [ ] 實作 Defensive Over-checking（S12）— Static + LLM
- [ ] 擴展語言支援：JavaScript / TypeScript
