# Aerial 与开源 NR 基站比较研究执行计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 形成一套可追溯、可复现的 NVIDIA Aerial、Duranta/OAI 与 OCUDU NR 基站架构、源码、性能和技术决策比较成果。

**Architecture:** 研究资产分为配置、原始证据、结构化发现、分析脚本、源码档案和综合报告六层。所有结论通过唯一 `claim_id` 连接官方文档、固定 commit 的源码位置、实验配置和证据等级；当前阶段不把 NVIDIA 官方性能声明写成独立实测结论。

**Tech Stack:** PowerShell、PortableGit、Python 3、YAML、CSV、Markdown、Graphviz/Mermaid、GitHub/GitLab、Linux perf、Nsight 文档接口、OAI/OCUDU 自带测试工具。

## Global Constraints

- 范围仅限 NR gNB/DU；排除 UE、5GC、RIC/xApp 和纯仿真器的独立功能。
- 主比较对象固定为 NVIDIA Aerial CUDA-Accelerated RAN、Duranta/OpenAirInterface 和 OCUDU；O-RAN SC 仅作组件参照。
- 每个源码结论必须包含仓库、commit、文件路径和符号；关键结论最低证据等级为 E2。
- Aerial 未经本研究硬件复现的性能数据必须标记为 `vendor_claim` 或 `derived`，不得标记为 `measured`。
- 性能记录必须包含软件版本、硬件、带宽、SCS、TDD、天线、层数、UE、MCS/负载、预热、重复次数和统计口径。
- 不直接比较不同测试边界、不同天线配置、不同硬件或不同统计量。
- 所有外部仓库放在 `third_party/`，研究生成物不得修改外部仓库源码。
- 原始证据和派生结论分开保存；派生报告不得覆盖原始日志。
- 当前 Windows 工作区的 Git 可执行文件使用 `C:\Users\AI\.cache\codex-runtimes\codex-primary-runtime\dependencies\native\git\cmd\git.exe`，Python 使用 `.venv\Scripts\python.exe`。

---

## 文件结构

```text
config/
  repositories.yaml              # 仓库、分支、commit、许可证和用途
  metric-rules.yaml               # NR配置、统计口径和无效比较规则
  evidence-schema.yaml            # claim字段和E0-E4规则
data/
  documents/manifest.csv          # 官方文档版本和本地快照索引
  inventory/source-inventory.csv  # 语言、目录、文件和依赖统计
  claims/claims.yaml              # 全部结构化结论
  performance/vendor-claims.csv   # 官方性能声明及审计
  performance/raw/                # 本地实验原始日志
  performance/normalized/         # 清洗后的统一数据
docs/research/
  architecture/                   # 三项目架构图和统一映射
  dossiers/                       # 六条源码主线档案
  reports/                        # 主报告、CUDA专题和决策矩阵
  protocols/                      # CPU基线与未来Aerial测试协议
scripts/
  validate_claims.py              # 证据记录校验
  audit_vendor_claims.py          # 性能声明完整性检查
  normalize_benchmarks.py         # 本地结果归一化
  source_inventory.ps1            # 仓库清单和源码统计
tests/
  test_validate_claims.py
  test_audit_vendor_claims.py
  test_normalize_benchmarks.py
third_party/                      # 固定commit的外部仓库
```

### Task 1: 初始化研究仓库与配置契约

**Files:**
- Create: `config/repositories.yaml`
- Create: `config/metric-rules.yaml`
- Create: `config/evidence-schema.yaml`
- Create: `docs/research/README.md`
- Create: `.gitignore`

**Interfaces:**
- Consumes: 已批准的设计文档。
- Produces: 后续所有任务使用的仓库标识、指标字段和证据等级。

- [ ] **Step 1: 初始化有效 Git 仓库**

Run:

```powershell
$gitExe = 'C:\Users\AI\Documents\3GPP Guru\.tools\PortableGit\cmd\git.exe'
& $gitExe init -b research/aerial-nr-comparison
& $gitExe status --short
```

Expected: 输出初始化成功信息，当前 unborn branch 为 `research/aerial-nr-comparison`，`git status` 不再返回 `not a git repository`。

- [ ] **Step 2: 创建配置文件**

`repositories.yaml` 明确列出以下 canonical URL 和角色：

```yaml
repositories:
  aerial:
    url: https://github.com/NVIDIA/aerial-cuda-accelerated-ran.git
    role: primary
    ref_policy: latest_release_then_commit
  oai:
    url: https://github.com/duranta-project/openairinterface5g.git
    role: primary
    ref_policy: develop_then_commit
  ocudu:
    url: https://gitlab.com/ocudu/ocudu.git
    role: primary
    ref_policy: latest_release_then_commit
  oran_du_l2:
    url: https://github.com/o-ran-sc/o-du-l2.git
    role: reference
    ref_policy: master_then_commit
  oran_du_phy:
    url: https://github.com/o-ran-sc/o-du-phy.git
    role: reference
    ref_policy: master_then_commit
```

`metric-rules.yaml` 固定 `bandwidth_mhz`、`scs_khz`、`duplex`、`tdd_pattern`、`tx_antennas`、`rx_antennas`、`layers`、`ues`、`mcs_or_load`、`latency_statistic`、`deadline_us`、`test_boundary` 和 `evidence_kind` 字段。

`evidence-schema.yaml` 固定 E0-E4 定义及 `confirmed_fact`、`measured_fact`、`inference`、`vendor_claim`、`open_question` 五类结论。

- [ ] **Step 3: 创建忽略规则**

`.gitignore` 必须包含：

```gitignore
third_party/
data/documents/files/
data/performance/raw/
*.pcap
*.nsys-rep
*.ncu-rep
__pycache__/
.pytest_cache/
```

- [ ] **Step 4: 校验配置可解析**

Run:

```powershell
.\.venv\Scripts\python.exe -c "import pathlib,yaml; [yaml.safe_load(p.read_text(encoding='utf-8')) for p in pathlib.Path('config').glob('*.yaml')]; print('CONFIG_OK')"
```

Expected: `CONFIG_OK`。

- [ ] **Step 5: 提交配置契约**

```powershell
& $gitExe add .gitignore config docs/research/README.md docs/superpowers/specs docs/superpowers/plans
& $gitExe commit -m "docs: define aerial nr gnb research framework"
```

### Task 2: 冻结仓库与官方文档基线

**Files:**
- Modify: `config/repositories.yaml`
- Create: `data/documents/manifest.csv`
- Create: `docs/research/architecture/version-baseline.md`

**Interfaces:**
- Consumes: Task 1 的仓库配置。
- Produces: 所有源码引用使用的固定 commit 和所有文档引用使用的版本记录。

- [ ] **Step 1: 克隆五个仓库**

Run:

```powershell
$gitExe = 'C:\Users\AI\Documents\3GPP Guru\.tools\PortableGit\cmd\git.exe'
New-Item -ItemType Directory -Force third_party | Out-Null
& $gitExe clone --recurse-submodules https://github.com/NVIDIA/aerial-cuda-accelerated-ran.git third_party/aerial
& $gitExe clone --recurse-submodules https://github.com/duranta-project/openairinterface5g.git third_party/oai
& $gitExe clone --recurse-submodules https://gitlab.com/ocudu/ocudu.git third_party/ocudu
& $gitExe clone https://github.com/o-ran-sc/o-du-l2.git third_party/oran-du-l2
& $gitExe clone https://github.com/o-ran-sc/o-du-phy.git third_party/oran-du-phy
```

Expected: 五个目录均含有效 `HEAD`；Aerial 的 Git LFS 对象另行执行 `git lfs pull` 并记录成功或明确缺失原因。

- [ ] **Step 2: 记录不可变 commit**

对每个仓库运行 `git rev-parse HEAD`、`git describe --tags --always`、`git submodule status --recursive`，把实际值写回 `repositories.yaml`，不得只记录分支名。

- [ ] **Step 3: 建立官方文档清单**

`manifest.csv` 每行包含：`project,title,version,url,published_at,retrieved_at,local_path,sha256,scope`。至少纳入 Aerial 26.1 总文档、cuPHY Components、cuMAC、pyAerial、Limitations，以及 OAI、OCUDU、O-RAN SC 的架构和功能文档。

- [ ] **Step 4: 写版本基线说明**

`version-baseline.md` 说明 OAI→Duranta 和 srsRAN Project→OCUDU 的迁移关系，并记录为何选择当前 ref。

- [ ] **Step 5: 验证冻结状态并提交**

Run:

```powershell
Select-String -Path config/repositories.yaml -Pattern 'commit:'
python -c "import csv; r=list(csv.DictReader(open('data/documents/manifest.csv',encoding='utf-8'))); assert len(r)>=9; assert all(x['version'] and x['url'] and x['retrieved_at'] for x in r); print('BASELINE_OK')"
```

Expected: 至少五个 `commit:`，输出 `BASELINE_OK`。提交消息：`docs: freeze ran source and documentation baseline`。

### Task 3: 建立自动化证据登记与校验

**Files:**
- Create: `scripts/validate_claims.py`
- Create: `tests/test_validate_claims.py`
- Create: `data/claims/claims.yaml`

**Interfaces:**
- Consumes: `config/evidence-schema.yaml` 和冻结仓库标识。
- Produces: 后续档案和报告共同读取的合法 claim 记录。

- [ ] **Step 1: 写失败测试**

测试覆盖：E2-E4 缺少 commit/path/symbol 时失败；`measured_fact` 缺少实验配置时失败；`vendor_claim` 不要求本地日志但必须有官方 URL 和版本；合法 E2 记录通过。

- [ ] **Step 2: 运行失败测试**

Run: `python -m pytest tests/test_validate_claims.py -v`  
Expected: FAIL，原因是 `scripts.validate_claims` 尚不存在。

- [ ] **Step 3: 实现校验器**

接口固定为：

```python
def validate_claims(claims_path: str, repositories_path: str) -> list[str]:
    """Return deterministic validation errors; return [] when valid."""
```

CLI 固定为 `python scripts/validate_claims.py data/claims/claims.yaml config/repositories.yaml`，有错误返回 1，无错误打印 `CLAIMS_OK`。

- [ ] **Step 4: 创建首批范围 claim**

写入三个已确认的 E1 记录：Aerial 包含 cuPHY/cuMAC；OAI 当前主线为 Duranta；srsRAN Project 当前主线为 OCUDU。每条记录包含日期、官方 URL、版本和限制。

- [ ] **Step 5: 运行测试与真实校验**

Expected: pytest 全部 PASS；CLI 输出 `CLAIMS_OK`。提交消息：`feat: validate research evidence records`。

### Task 4: 生成源码清单与统一架构图

**Files:**
- Create: `scripts/source_inventory.ps1`
- Create: `data/inventory/source-inventory.csv`
- Create: `docs/research/architecture/aerial.md`
- Create: `docs/research/architecture/oai.md`
- Create: `docs/research/architecture/ocudu.md`
- Create: `docs/research/architecture/unified-ran-map.md`

**Interfaces:**
- Consumes: 冻结源码。
- Produces: 六条源码档案使用的模块、目录和语言地图。

- [ ] **Step 1: 实现源码清单脚本**

脚本对每个仓库输出 `project,path,extension,language,bytes,sha256`，排除 `.git` 和生成目录；同时统计 `.cu`、`.cuh`、C/C++、Python、MATLAB 文件。

- [ ] **Step 2: 运行并验证清单**

Run: `powershell -ExecutionPolicy Bypass -File scripts/source_inventory.ps1`  
Expected: CSV 非空，Aerial 至少出现 CUDA 文件，三个主项目均出现 C/C++ 文件。

- [ ] **Step 3: 写三份架构说明**

每份必须回答模块输入、输出、执行位置、所有权、依赖和实时边界，并引用固定 commit 的路径。

- [ ] **Step 4: 绘制统一映射**

用 Mermaid 映射 RU/FH、lower PHY、upper PHY、FAPI、MAC、RLC、CU/DU；Aerial 的 CPU/GPU 边界用不同节点标识。

- [ ] **Step 5: 架构门槛检查并提交**

人工逐模块确认不存在只有名称而无输入/输出的节点。提交消息：`docs: map aerial oai and ocudu architectures`。

### Task 5: 完成 PUSCH 与 PDSCH 源码档案

**Files:**
- Create: `docs/research/dossiers/pusch.md`
- Create: `docs/research/dossiers/pdsch.md`
- Modify: `data/claims/claims.yaml`

**Interfaces:**
- Consumes: 统一架构图和 claim 校验器。
- Produces: 两条完整 slot 数据路径和首批 CUDA 差异证据。

- [ ] **Step 1: 追踪 Aerial PUSCH/PDSCH**

记录 FAPI 入口、descriptor、create/setup/run 生命周期、CUDA Graph、kernel、buffer、同步点、indication 和错误路径；每个关键节点写入实际 path 与 symbol。

- [ ] **Step 2: 追踪 OAI 对应路径**

从 NR MAC/FAPI/RU 入口追到 `openair1` 的 PUSCH/PDSCH 算法和线程任务，记录 SIMD、buffer 和 worker 分工。

- [ ] **Step 3: 追踪 OCUDU 对应路径**

从 FAPI adaptor、upper PHY、lower PHY、processor 和 executor 追踪相同处理链。

- [ ] **Step 4: 形成并列调用图与内存图**

每份档案至少包含一张端到端调用图、一张 buffer 生命周期图、一张 CPU/GPU/线程边界图和一张差异表。

- [ ] **Step 5: 校验证据**

Run: `python scripts/validate_claims.py data/claims/claims.yaml config/repositories.yaml`  
Expected: `CLAIMS_OK`，两份档案的核心结论全部达到 E2。提交消息：`docs: trace pusch and pdsch implementations`。

### Task 6: 完成信道编码与大规模 MIMO 档案

**Files:**
- Create: `docs/research/dossiers/channel-coding.md`
- Create: `docs/research/dossiers/massive-mimo.md`
- Modify: `data/claims/claims.yaml`

**Interfaces:**
- Consumes: Task 5 的 PHY 数据路径。
- Produces: CUDA 并行维度、数据布局和 64T64R 能力归因。

- [ ] **Step 1: 分析 LDPC/Polar**

逐项目记录编码、rate matching、rate recovery、译码、量化、lifting size、early termination、batch 和 CPU SIMD/GPU mapping。

- [ ] **Step 2: 分析 64T64R/MU-MIMO**

记录 SRS/CSI、信道矩阵布局、ZF/MMSE、beam weight、UE grouping、矩阵库与定制 kernel 分工。

- [ ] **Step 3: 做差异归因**

每项优势分别标记 `cuda_intrinsic`、`cuda_runtime`、`data_path`、`algorithm_redesign`、`hardware_resource` 或 `engineering`。

- [ ] **Step 4: 验证并提交**

Expected: claim 校验通过；所有能力评分附有理由和证据等级。提交消息：`docs: analyze coding and massive mimo acceleration`。

### Task 7: 完成 cuMAC 与 CPU Scheduler 比较

**Files:**
- Create: `docs/research/dossiers/cumac.md`
- Modify: `data/claims/claims.yaml`

**Interfaces:**
- Consumes: 三项目 MAC/scheduler 源码。
- Produces: cuMAC 是性能加速还是算法空间扩展的证据化结论。

- [ ] **Step 1: 追踪 cuMAC cell-group 数据流**

覆盖 per-cell request、聚合、device buffer、UE selection、PRB/layer allocation、MU-MIMO pairing、MCS/OLLA/DRL 和结果返回。

- [ ] **Step 2: 对照 OAI/OCUDU scheduler**

使用相同输入规模变量：cell、UE、PRB、layer、候选配对数量，记录算法复杂度和执行模型。

- [ ] **Step 3: 检查 CPU reference 与 benchmark**

明确计时边界、输入生成、结果一致性检查和 GPU 必需依赖；不能运行的步骤记录为 E3 方法证据而非本地实测。

- [ ] **Step 4: 验证并提交**

Expected: 档案明确区分“更快执行相同算法”和“允许更复杂联合优化”。提交消息：`docs: compare cumac and cpu schedulers`。

### Task 8: 完成 O-RAN 7.2、GPUDirect 与实时性档案

**Files:**
- Create: `docs/research/dossiers/fronthaul-realtime.md`
- Modify: `data/claims/claims.yaml`

**Interfaces:**
- Consumes: Aerial FH driver、OAI FHI 7.2、O-RAN SC PHY/FAPI。
- Produces: 从 NIC 到 PHY 的复制、DMA、同步和 deadline 路径。

- [ ] **Step 1: 绘制 packet-to-PHY 路径**

逐项目记录 DPDK ingress、eCPRI section、IQ 解压、buffer ownership、DMA、CPU/GPU handoff 和 slot window。

- [ ] **Step 2: 分析实时机制**

记录 PTP/SyncE、core isolation、NUMA、MPS/MIG、late packet、overrun、deadline miss 和恢复行为。

- [ ] **Step 3: 计算理论数据量**

对 100 MHz 4T4R 与 64T64R 给出明确采样、位宽和压缩假设，计算每 slot 前传字节量；所有结果标记 `derived`。

- [ ] **Step 4: 验证并提交**

Expected: 每条 GPUDirect 优势说明移除 BlueField/GPUDirect 后的影响。提交消息：`docs: trace fronthaul and realtime data paths`。

### Task 9: 审计 NVIDIA 性能声明

**Files:**
- Create: `data/performance/vendor-claims.csv`
- Create: `scripts/audit_vendor_claims.py`
- Create: `tests/test_audit_vendor_claims.py`
- Create: `docs/research/reports/aerial-performance-claims-audit.md`

**Interfaces:**
- Consumes: 官方文档 manifest 和 metric rules。
- Produces: 可用、不可直接比较和信息不足的声明清单。

- [ ] **Step 1: 写失败测试**

测试要求声明包含来源版本、硬件、带宽、天线、cell口径、test boundary 和 statistic；缺失字段返回明确错误。

- [ ] **Step 2: 实现审计器并使测试通过**

接口：

```python
def audit_claims(csv_path: str) -> list[dict[str, str]]:
    """Return one audit result per vendor claim."""
```

- [ ] **Step 3: 录入全部相关官方数字**

至少覆盖 4T4R/64T64R peak/average cell、端到端吞吐、MIG、多小区和 cuMAC 数据；不确定字段保留为空并由审计器标为 `insufficient_context`。

- [ ] **Step 4: 生成审计报告**

报告分别列出 `comparable_with_constraints`、`vendor_only`、`insufficient_context`，不得生成伪统一排名。

- [ ] **Step 5: 测试并提交**

Expected: pytest PASS；报告中每个数字可回到官方 URL。提交消息：`docs: audit aerial performance claims`。

### Task 10: 建立 OAI/OCUDU CPU 基准协议与归一化工具

**Files:**
- Create: `docs/research/protocols/cpu-baseline.md`
- Create: `scripts/normalize_benchmarks.py`
- Create: `tests/test_normalize_benchmarks.py`
- Create: `data/performance/normalized/results.csv`

**Interfaces:**
- Consumes: metric rules 和项目自带 test mode。
- Produces: 可重复执行且不会与 Aerial 异构数据误比的 CPU 基线。

- [ ] **Step 1: 写实验协议**

固定首轮配置为 100 MHz、30 kHz SCS、4T4R、单小区；负载逐步增加 UE、layer 和 cell。每个配置预热 30 秒、正式运行 120 秒、重复 5 次；记录 P50/P95/P99/P99.9、deadline miss、CPU、RSS、NUMA、吞吐和 BLER。

- [ ] **Step 2: 写归一化失败测试**

测试拒绝缺少硬件、NR配置、统计量或 test boundary 的输入；不同天线配置不得进入同一 comparison group。

- [ ] **Step 3: 实现归一化器并通过测试**

接口：

```python
def normalize_records(records: list[dict[str, str]]) -> list[dict[str, str]]:
    """Validate units, derive comparison groups, and preserve raw provenance."""
```

- [ ] **Step 4: 做可运行性预检**

分别记录 OAI RF simulator/PHY test 和 OCUDU test mode 的构建依赖、命令、成功标志和不可用原因；不安装未批准的系统依赖。

- [ ] **Step 5: 执行首轮基线或形成阻塞记录**

如果环境满足条件，保存原始日志并生成 `results.csv`；若不满足，协议必须明确缺失硬件/软件和下一条可执行命令，不能填造结果。

- [ ] **Step 6: 提交协议与工具**

提交消息：`test: define reproducible cpu ran baseline`。

### Task 11: 编写未来 Aerial 实机测试协议

**Files:**
- Create: `docs/research/protocols/aerial-hardware-validation.md`
- Create: `config/aerial-test-matrix.yaml`

**Interfaces:**
- Consumes: 六份源码档案、声明审计和 CPU metric schema。
- Produces: 获得硬件后无需重设研究问题即可执行的测试包。

- [ ] **Step 1: 定义测试矩阵**

包含 cuPHY microbenchmark、多channel/multicell、cuMAC CPU reference、cuBB eCPRI、GPUDirect A/B、CUDA Graph A/B、batch/cell扩展、MPS/MIG、尾延迟和故障压力。

- [ ] **Step 2: 定义采集命令和文件命名**

明确 cuBB testbench、Nsight Systems、Nsight Compute、GPU/CPU/OAM metrics 的输入、持续时间、重复次数和输出路径。

- [ ] **Step 3: 定义验收条件**

每个测试必须产出机器清单、容器版本、GPU/NIC固件、配置、原始日志和 checksum；任一缺失则不得升级到 E4。

- [ ] **Step 4: 协议桌面演练并提交**

逐项确认不存在需要研究者临场决定的参数。提交消息：`docs: define aerial hardware validation protocol`。

### Task 12: 合成主报告、CUDA专题与技术决策矩阵

**Files:**
- Create: `docs/research/reports/aerial-vs-open-ran-gnb.md`
- Create: `docs/research/reports/aerial-cuda-differentiation.md`
- Create: `docs/research/reports/scenario-decision-matrix.md`
- Modify: `data/claims/claims.yaml`

**Interfaces:**
- Consumes: 全部档案、claim、性能审计和基准结果。
- Produces: 最终可审阅成果。

- [ ] **Step 1: 写主报告**

按设计中的 14 章结构编写；每个关键段落标记 `[源码确认]`、`[本地实测]`、`[合理推断]`、`[NVIDIA声明]` 或 `[待Aerial实机验证]`。

- [ ] **Step 2: 写 CUDA 差异化专题**

分别归因 CUDA 固有并行、runtime、数据路径、算法重构、AI工具链、工程实现、硬件资源和非CUDA因素，并回答三个反事实问题：更换加速器、移除GPUDirect、OAI/OCUDU重构。

- [ ] **Step 3: 写场景决策矩阵**

至少覆盖大规模MIMO宏站、AI-RAN、通用SDR基站和云化O-RAN DU；能力评分与证据等级分开，不生成唯一总排名。

- [ ] **Step 4: 执行全量质量门槛**

Run:

```powershell
python -m pytest tests -v
python scripts/validate_claims.py data/claims/claims.yaml config/repositories.yaml
python scripts/audit_vendor_claims.py data/performance/vendor-claims.csv
Select-String -Path docs\research\**\*.md -Pattern 'T[B]D|T[O]DO|填[入]|稍后补[充]'
```

Expected: 所有测试 PASS；`CLAIMS_OK`；审计器成功；占位符搜索无输出。

- [ ] **Step 5: 人工终审**

逐条确认六份源码档案形成端到端调用链、关键结论达到 E2、性能数字配置完整、每项 Aerial 优势有 OAI/OCUDU 对照、算法/实现/平台/硬件收益已分离。

- [ ] **Step 6: 提交最终成果**

```powershell
& $gitExe add config data docs scripts tests
& $gitExe commit -m "docs: complete aerial nr gnb comparative study"
```

## 执行检查点

- **Checkpoint A（Task 2 后）：** 用户确认冻结版本和文档范围。
- **Checkpoint B（Task 4 后）：** 用户确认统一架构图和术语口径。
- **Checkpoint C（Task 8 后）：** 用户审阅六份源码档案的核心差异结论。
- **Checkpoint D（Task 10 后）：** 用户审阅性能边界、可运行结果或环境阻塞。
- **Checkpoint E（Task 12 前）：** 用户确认场景权重后再生成最终决策矩阵。

## 计划完成标准

- Task 1–12 的验收命令均达到预期结果。
- 所有外部事实可以回溯到官方文档或固定 commit 源码。
- 所有实测结果可以回溯到原始日志、配置和环境清单。
- 无 Aerial 硬件产生的限制在主报告、CUDA专题和决策矩阵中一致呈现。
- 下一位工程师可以仅依据协议文档完成 Aerial E4 实机验证。
