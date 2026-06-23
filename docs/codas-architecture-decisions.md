# Codas architecture decisions — session record (2026-06-23)

Status: DECISION RECORD (directions, not yet built). Consolidates and refines the open
questions in `docs/codas-fact-claim-maintenance-milestone.md`. Companion visuals:
`codas-architecture.html` + `codas-concept-map.html` (repo root). Owner: Codas Core.

This captures a long design dialogue. Tables first (for review), then the reasoning chains
that future sessions should not re-derive.

## 1. The layered model + adapter slots

```
层3 治理:  gate · claim/锚点 · wiki 渲染          ← Codas 独有(CodeGraph 到不了)
层2 事实:  symbols · imports · calls(调用图)
层1 解析:  ast(Python) | tree-sitter(多语言)     ← ast 与 tree-sitter 同级(都是 parser)
```
越上越高级,每层踩在下层产出之上。CodeGraph 内部自跑层1+层2,招牌是层2 多语言调用图;**到不了层3**。

Three adapter slots:

| 槽 | 填谁 | tier |
| --- | --- | --- |
| parse(层1) | ast(Python)· tree-sitter(每语言) | — |
| 语言内 gate 事实 | tree-sitter(symbols/imports)· ast(Python calls) | **gate-grade(确定)** |
| 多语言+跨语言 call-graph | **CodeGraph**(可插拔 adapter) | **advisory** |

## 2. Architecture decisions

| 议题 | 结论 |
| --- | --- |
| gate vs advisory(层2) | gate-grade = tree-sitter(symbols/imports)+ ast(Python calls),语言内、确定;advisory = CodeGraph(多语言+跨语言) |
| CodeGraph 定位 | call-graph 层 adapter(可插拔),advisory tier。真实仓库都多语言 → 必须有 |
| 跨语言 | 支持(advisory)= 刚需;拦(gate)不做 —— 跨语言边是猜的(heuristic),进 gate 会假拦 |
| gate 烧什么 | 主要 symbols + imports(ownership/dup/dependency-direction)。calls 大多 advisory(impact/code_anchor);gate-grade 非 Python calls 只在罕见 fact_coupling 才需要 |
| Python calls | 永远走 `ast`(比 tree-sitter 强:richer + 零依赖),不走 tree-sitter |
| hash | 整份 inventory hash 过宽(改一行代码盖 A+B+C 整块)+ 本质是输入指纹(漏 prose/渲染器)→ 退掉,统一 diff |
| 验证 | diff(re-render + byte-compare)替 hash。覆盖全输入。留渲染确定性(canonical + run-twice 测试) |
| scoped-hash vs drop-hash | drop-hash(全 diff)胜:scoped 没修 prose/渲染器盲区 + 保留混合机制;drop 一套机制 + 完整。仅"大且高频"生成物才单独留 scoped(本仓暂无) |
| 大迁移 | 否(diff-gate 全量 / 退役 inventory / 全 CodeGraph 进 gate)。5 顾问一致 migrate-lite |

## 3. Concept clarifications (消歧)

| 概念 | 澄清 |
| --- | --- |
| 源头切分 | 代码 → 事实(不叫 claim);文档/配置 → claim。代码从不产 claim |
| claim 重载 | claim = 属(可核对断言);3 种:关系/治理 claim(claims.yml,closed,拦)· doc claim(扫文档)· 锚点 claim(.codas/wiki/code,open warning)。该带限定词,且 coupling↔锚点该合一 |
| claim vs waiver | claim = "这是对的"(声明真相,永久,能开能关规则)；waiver = "错但暂赦"(临时,带 expiry,只压制)。Codas 自身 4 claim / 0 waiver |
| closed vs open world | 配置 = 声明层 = 应该(closed,缺失有义)；事实 = 观察层 = 实际(open,下界,缺失=未知)。gate = 比两者,不符则拦 |
| "LLM 离线写" | LLM 在 codas 之外、提前写 prose 存文件;codas 只读冻结文件,自身零 LLM。§17 |
| "渲染" | facts + prose 拼装成 markdown 文本(不是画图),纯确定函数(同输入→同字节) |
| prose 在哪 | 不在 inventory/hash(advisory)；只有 verified claim(锚点)进 inventory |
| hash 算什么 | `inventory_hash` = sha256(整份 inventory JSON),非 fact-only。generated 页已窄化(scoped 先例);pack 仍整份;policy_version 独立 |
| inventory 范围 | IN: A 配置(units/program/documents)+ B claims(doc/html/wiki)+ C 事实(symbols/imports/calls)/tasks。OUT: prose · 渲染书 · scratch · working-tree delta |
| fact 格式 | 扁平记录:`SymbolFact{module,name,kind,line}` · `ImportFact{module,target,target_path,line}` · `CallFact{caller_*,callee_*,resolution}` |

## 4. Key reasoning chains (don't re-derive)

### 为什么 diff > hash(核心)
一个生成物 = render(facts + prose + 渲染器)。
- **hash** 只指纹 facts(prose 不在 inventory;渲染器是代码)→ 输入指纹,**漏 prose + 渲染器**。
- **diff**(re-render + byte-compare)比的是**实际输出** → 三个输入全覆盖。
- scoped-hash 把 slice 缩小(去 churn)但**仍是输入指纹**,盲区不变。
- → 凡有非-fact 输入(书有 prose;以后 CodeGraph 多语言书)的派生物,hash 注定漏,只有 diff 行。书+AGENTS.md 现在已是 diff;统一即可。

### byte-identical 的意义(不是教条)
被两个选择逼出来,拆成两半:
- **A 确定性**(inventory 跑两次同字节):让事实成为事实、gate 公平、任何 diff 干净。**irreducible** —— diff 路线自己也靠它。留成 canonical 序列化 + run-twice 测试,不必是生产 hash。
- **B byte-compare**(committed 派生物 == 现渲染):无 LLM(§17)下"文档匹配代码"**唯一可机器化的定义**。只在 commit 派生物处需要(AGENTS.md 必须 commit;书选择 commit)。
- 该删的不是 byte-identical,是"整份 hash 这个又宽又漏的代理"。留 A,把 B 做直接(diff)。

### 跨语言为什么 advisory 不 gate
跨语言边靠名字/约定**猜**(JS↔ObjC bridge by name)→ 会错(mis-wire)。错边进 gate = **假拦对的提交**(比漏报更伤信任)。所以跨语言/heuristic 边只 advisory;gate 只收语言内 sound 边。

## 5. Task directions (未开;gate-semantics 的需 codex DESIGN review)

| 序 | 任务 | 风险 | 价值 |
| --- | --- | --- | --- |
| ① | drop-hash + 统一 diff 验证(generated_wiki_drift: hash-pin → re-render+byte-compare;留 run-twice 确定性测试;inventory_hash 留作 audit) | gate-semantics | 减复杂度 + 更正确(抓 prose/渲染器) |
| ② | CodeGraph advisory call-graph adapter(多语言,off-gate/off-hash/可选,缺则降级,标 provenance) | 低 | 多语言 impact/reuse/跨语言理解 |
| ③ | tree-sitter gate(symbols/imports 每语言,确定,进 gate) | 中 | 多语言 gate(语言内) |
| ④ | 问题3 锚点(决策↔文档)+ RepairTarget(claim coupling↔锚点收敛合并) | gate-semantics | 最高产品价值 |

## 6. Rejected / 搁置

| 项 | 决定 |
| --- | --- |
| 大改:diff-gate 全量 + 退役 inventory + CodeGraph 渲染进 gate | 否 — 回归确定/防绕过/离线核心属性 |
| 手写每语言 call-resolver | 否 — 用 CodeGraph(难的 call 部分);只手写简单的 symbols/imports |
| CodeGraph 进 gate / 跨语言猜的边拦提交 | 否 — advisory only(防假拦) |
| tree-sitter-analyzer(TSA) | 否 — 硬依赖 anthropic/numpy/mcp,且 zero-LLM-core 违背 |
| scoped-hash(分块 hash) | 搁置 — 没修 prose/渲染器盲区;drop-hash 更彻底 |
