# NVIDIA Aerial 与开源 NR 基站比较研究设计

**日期：** 2026-07-20  
**状态：** 已获用户批准，待书面复核  
**研究对象：** NVIDIA Aerial CUDA-Accelerated RAN、Duranta/OpenAirInterface、OCUDU，以及作为组件参照的 O-RAN SC O-DU  
**范围：** 仅限 5G NR 基站侧；不比较 UE、5GC、RIC/xApp 或纯系统级仿真器，除非它们直接影响 gNB 数据路径

## 1. 目标

本研究同时产出三类成果：

1. 技术架构与源码研究：从官方文档进入接口、控制路径、数据结构、CPU 函数和 CUDA kernel。
2. 可复现性能评测：现阶段建立 OAI/OCUDU CPU 基线并审计 Aerial 官方数据；未来获得 NVIDIA 平台后补充 Aerial 独立实测。
3. 技术决策与竞争分析：说明 Aerial 的能力、适用前提、代价、可复制性和供应商锁定风险。

研究采用“总体串行、局部并行”的方式：先统一口径与架构，再并行开展源码、性能和工程生态分析，最后合成场景化结论。

## 2. 研究对象和边界

### 2.1 主比较组

- **NVIDIA Aerial CUDA-Accelerated RAN**：GPU 加速的 NR L1、cuMAC、前传与配套验证工具链。
- **Duranta/OpenAirInterface**：原 OAI RAN 的当前主线，提供 NR gNB、DU/CU 及 NR UE；本研究仅分析基站侧。
- **OCUDU**：原 srsRAN Project 的当前继任项目，提供 O-RAN 对齐的完整 CU/DU 和 L1/L2/L3 栈。

### 2.2 辅助参照组

- **O-RAN SC O-DU High/O-DU Low**：用于比较 FAPI、O-RAN 分层、FHI 以及模块开放边界，不将其视为与前三者完全对等的单仓库端到端 gNB。

### 2.3 排除项

- UERANSIM、5G-LENA、Simu5G、Sionna 等非实时 NR 基站实现。
- NR UE、5GC、IMS、RIC/xApp、SMO 的独立功能。
- 无法映射到 gNB 数据路径的通用 AI、云平台或网络管理功能。

## 3. 核心研究问题

1. Aerial 的差异是把 PHY 搬到 GPU，还是重构了整个 DU 数据路径？
2. 哪些 NR 算法真正由 CUDA kernel 实现，哪些仍运行在 CPU？
3. Aerial 如何处理数据搬运、kernel 启动开销和 slot 级实时确定性？
4. cuMAC 是否带来多小区联合调度、大规模 MU-MIMO 和 AI 链路自适应等超出传统 CPU scheduler 的能力？
5. Aerial 的收益分别来自 CUDA 固有能力、CUDA 软件栈、NVIDIA 数据路径、算法重构和工程投入中的哪些部分？
6. 这些能力的代价是什么，包括硬件绑定、功耗、部署复杂度、可移植性、开放性和第三方组件依赖？
7. 哪些优势可以由 OAI/OCUDU 通过工程重构复制，哪些必须依赖 NVIDIA 平台？

## 4. 初始差异化假设

以下内容仅作为待验证假设，不作为预设结论：

- Aerial 将 PDSCH、PUSCH、SRS 等信道处理组织为多小区 GPU pipeline，并使用 CUDA Graph 表达 kernel 依赖和降低每 slot 启动开销。
- Aerial 使用 kernel fusion、预分配、批处理和多小区聚合提高 GPU 占用率，与 OAI/OCUDU 的 CPU worker/thread 执行模型存在根本差异。
- BlueField/ConnectX、DPDK 和 GPUDirect RDMA 使 O-RAN 7.2 IQ 数据尽量直接进入 GPU，从而减少 host copy 和 PCIe 往返。
- cuMAC 把 UE 筛选、PRB/层分配、链路自适应和 MU-MIMO 配对组织为 cell-group 级并行流水线，而不只是加速某个单独函数。
- pyAerial 通过复用实时 cuPHY 的 CUDA kernel 建立 Python 原型、bit-accurate 验证和实时 OTA 之间的一致路径。
- NVIDIA 的主要优势可能来自 GPU 计算、GPU 数据路径和软件工具链的组合，而非单独的 LDPC、FFT 或 MIMO kernel。

每条假设都必须经过文档、源码和测试证据检查；无法达到源码证据等级的内容保留为项目方声明或合理推断。

## 5. 统一比较矩阵

| 维度 | 核心问题 | Aerial 证据入口 | OAI/OCUDU 对照入口 |
|---|---|---|---|
| 系统边界 | 完整 gNB、DU 或加速库？CPU/GPU 如何分工？ | `cuPHY/`、`cuPHY-CP/`、`cuMAC/`、`cuMAC-CP/` | OAI `executables/`、`openair1/2/3`；OCUDU `apps/`、`lib/` |
| PHY 算法覆盖 | 哪些信道与算法由 CUDA 实现？ | `cuPHY/` 各信道 pipeline、kernel 和 wrapper | OAI NR PHY/SCHED；OCUDU upper/lower PHY |
| 执行模型 | 每 slot 如何调度 CPU task、CUDA stream 和 graph？ | `cuphycontroller`、`cuphydriver`、pipeline lifecycle | OAI L1/RU thread pool；OCUDU executor/worker |
| 数据与内存 | IQ 和中间结果复制多少次，谁拥有 buffer？ | GPU/host memory、NVIPC、GPUDirect | SIMD buffer、DPDK mbuf、RU-PHY 交接 |
| 前传与同步 | O-RAN 7.2、eCPRI、DPDK、PTP、SyncE 如何进入数据路径？ | `aerial-fh-driver`、BlueField、eCPRI windowing | OAI FHI 7.2；O-RAN SC FAPI translator/WLS |
| L2-L1 接口 | SCF FAPI、扩展和内部 API 各承担什么功能？ | `cuphyl2adapter`、标准与 vendor FAPI | OAI nFAPI/FAPI；OCUDU FAPI adaptor |
| MAC 调度 | 哪些 scheduler 步骤 GPU 化？ | `cuMAC/`、`cuMAC-CP/` | OAI NR MAC；OCUDU scheduler |
| 多小区扩展 | 每小区独立还是 cell-group 聚合？ | channel aggregation、MPS、MIG | CPU core、thread、NUMA 扩展 |
| AI/ML 集成 | AI 是否进入实时数据路径？ | `pyaerial/`、Data Lake、TensorRT、DRL-MCS | 外部模型接口和实验扩展 |
| 正确性验证 | 如何保证 3GPP 一致和 CPU/GPU 等价？ | `5GModel/`、`testVectors/`、`testBenches/` | 单元测试、PHY test、标准向量 |
| 性能与观测 | 能否测到 channel、kernel、slot 和 deadline miss？ | cuBB benchmark、Nsight、GPU/OAM metrics | perf、线程统计、PHY/MAC 日志 |
| 工程与生态 | 硬件、许可、部署和贡献模式有什么代价？ | CUDA、GPU、BlueField、容器、贡献限制 | 通用 CPU、SDR/RU 适配、社区模式 |

## 6. 源码追踪方法

每个研究问题都沿同一证据链分析：

```text
官方功能声明
  → 架构文档和时序图
  → API、配置与数据结构
  → C++ 控制路径
  → CUDA kernel 或 CPU 实现
  → 测试向量和 benchmark
  → 独立实测或外部证据
```

以 PUSCH 为例，必须追踪：

1. `UL_TTI.request` 如何进入 L2 adapter。
2. 动态参数如何转换成 pipeline descriptor。
3. 内存在初始化、每 slot setup 和执行阶段的生命周期。
4. CUDA Graph 的节点、依赖和可变参数更新方式。
5. FFT、信道估计、均衡、demapper、rate recovery、LDPC 和 CRC 是否为独立或融合 kernel。
6. CPU/GPU 同步点、结果返回和异常路径。
7. 多小区、UE、天线和 code block 的 batch 维度。
8. 参考模型和测试向量如何生成与比较。
9. benchmark 的计时边界、统计口径和配置。
10. OAI/OCUDU 对应处理链的线程、函数、buffer 和 SIMD 实现。

## 7. 六条优先源码主线

### 7.1 PUSCH 上行接收

```text
前传 IQ → 解压/重排 → FFT → DMRS/信道估计 → MIMO 检测/均衡
→ soft demapping → rate recovery → LDPC decoding → CRC → FAPI indication
```

### 7.2 PDSCH 下行生成

```text
MAC TB → CRC → LDPC encoding → rate matching → scrambling/modulation
→ layer mapping → precoding → resource mapping → IFFT/CP → 前传 IQ
```

### 7.3 LDPC 与 Polar

比较数据布局、lifting size specialization、warp/block 映射、early termination、batch 维度、量化精度，以及 CPU SIMD 与 GPU 的延迟/吞吐取舍。

### 7.4 64T64R 与大规模 MIMO

比较信道矩阵布局、矩阵运算、ZF/MMSE、beam weight、MU-MIMO grouping、CSI/SRS 数据复用，以及定制 kernel 和 CUDA 数学库的分工。

### 7.5 cuMAC

```text
per-cell 状态 → cell-group 聚合 → device 数据准备 → UE 排序/筛选
→ PRB/层分配 → MU-MIMO 配对 → MCS/OLLA/DRL → 结果返回 L2
```

### 7.6 O-RAN 7.2 与实时数据路径

追踪 DPDK ingress、eCPRI section、IQ 解压、DMA、PTP/SyncE、slot window、late packet、deadline miss、NUMA、MPS/MIG 和 CPU core isolation。

每条主线产出架构说明、调用图、关键结构、kernel/函数清单、内存图、优化点、限制、对照实现和证据索引。

## 8. 证据分级与记录

### 8.1 证据等级

- **E0 项目声明**：README、产品页或发布说明。
- **E1 架构证据**：开发文档、API 文档、时序图和限制说明。
- **E2 源码证据**：明确的仓库、commit、文件、符号、数据结构或 kernel。
- **E3 仓库内验证**：测试向量、CPU/GPU reference comparison、benchmark 代码和结果。
- **E4 独立复现**：由本研究运行，保存环境、配置、原始日志和分析脚本。

无 Aerial 硬件时，Aerial 性能结论最高标记为 E3；OAI/OCUDU 可通过本地执行达到 E4。

### 8.2 记录模式

每项发现至少包含：

```yaml
claim_id: PHY-PUSCH-001
question: Aerial 如何降低 PUSCH pipeline 的 kernel 启动开销
project_claim: 使用 CUDA Graph 表示 pipeline 依赖
document:
  title: Aerial cuPHY Components
  version: 26.1
  section: Performance Optimization
  retrieved_at: 2026-07-20
source:
  repository: NVIDIA/aerial-cuda-accelerated-ran
  commit: 固定为实际分析提交
  paths: 实际源码定位后逐项记录
comparison:
  oai: 对应函数、线程和任务路径
  ocudu: 对应 processor、executor 和 buffer 路径
validation:
  level: E2
  result: 源码确认、部分确认或未确认
limitations:
  - 尚未在支持硬件上测量尾延迟
```

`commit` 和 `paths` 不能在最终记录中留空；它们在仓库冻结和源码定位时写入实际值。

## 9. 阶段和工作流

### 阶段 0：基线冻结

- 克隆全部仓库、submodule 和 Git LFS 对象。
- 固定 commit、tag 和 submodule commit。
- 保存官方文档的版本、日期和索引。
- 生成仓库、许可证、依赖和语言清单。
- 统一 NR 配置和性能指标术语。

交付物：`repository-lock.yaml`、`source-inventory.md`、`terminology-and-metric-rules.md` 和文档索引。

### 阶段 1：文档级架构还原

- 绘制 Aerial、OAI、OCUDU 独立模块图。
- 绘制统一 3GPP/O-RAN 功能映射。
- 绘制单 slot、PUSCH 和 PDSCH 时序/数据流。
- 将初始假设逐项标记为待源码确认。

阶段门槛：每个模块都明确输入、输出、执行位置、所有权和依赖。

### 阶段 2：源码级深挖

- 按六条主线分析，不按仓库顺序通读。
- 每条主线使用统一证据模式。
- Aerial 的每个发现都定位 OAI 和 OCUDU 对应实现。
- 区分标准功能、通用工程优化、CUDA 专用优化和 NVIDIA 平台集成。

### 阶段 3：无 Aerial 硬件的性能分析

性能证据严格分为：

| 类别 | 用途 | 可否作为独立实测结论 |
|---|---|---|
| NVIDIA 声明值 | 审计官方容量、吞吐和延迟 | 否 |
| 仓库 benchmark 设计 | 检查配置、代码和计时边界 | 只能验证方法 |
| 理论推导值 | 分析复杂度、数据量和瓶颈 | 只能作为上下界或推断 |
| OAI/OCUDU 本地值 | 建立 CPU 软件基站基线 | 仅代表该硬件和配置 |

工作包括：

- 审计每个 NVIDIA 性能数字的版本、硬件、带宽、SCS、TDD、天线、层数、UE、统计口径和测试边界。
- 从源码估算 launch 数、graph 覆盖、传输次数、字节量、算术强度、batch 维度和串行临界路径。
- 把模块分类为 compute-bound、memory-bound、launch-bound 或 I/O-bound。
- 在可用机器上运行 OAI/OCUDU RF simulator、PHY test 或离线测试，采集 P50/P95/P99/P99.9、deadline miss、CPU、内存、NUMA、吞吐和 BLER。
- 预先建立 Aerial 实机测试配置、日志模式和分析脚本接口。

### 阶段 4：综合技术与竞争分析

按场景生成结论：大规模 MIMO 宏站、多小区集中式基带池、云化 O-RAN DU、AI-RAN、通用 SDR 基站、学术 PHY 研究，以及低成本或跨硬件移植场景。

每个场景说明：Aerial 优势、成立前提、OAI/OCUDU 更合适的条件、工程代价、证据强度和待实机验证问题。

### 并行工作流

- **A 文档与标准线**：版本、功能、架构、3GPP/O-RAN/SCF 接口。
- **B 源码与 CUDA 线**：调用链、kernel、内存和实时执行模型。
- **C 性能线**：声明审计、静态模型、CPU 基线和未来测试包。
- **D 决策线**：许可证、硬件依赖、部署、生态和供应商锁定。

阶段 0 和阶段 1 完成后，B/C/D 并行推进；A 持续维护统一口径。

## 10. 未来 Aerial 实机验证

获得 GH200、H100、BlueField 或受支持平台后，执行：

- cuPHY 单 pipeline microbenchmark。
- 多 channel、多 cell test bench。
- cuMAC GPU 与仓库 CPU reference 对照。
- cuBB 端到端 eCPRI 测试。
- Nsight Systems/Compute trace。
- GPUDirect 开关对照。
- CUDA Graph 开关对照。
- batch size 与 cell 数扩展曲线。
- MIG/MPS 隔离测试。
- 尾延迟、late packet、deadline miss 和故障压力测试。

实机测试复用阶段 3 已定义的配置与结果模式，不改变研究问题。

## 11. 评分与差异归因

### 11.1 能力评分

- **0**：没有实现或不在范围内。
- **1**：只有接口、stub 或设计。
- **2**：实验实现，可运行基本案例但覆盖有限。
- **3**：主流配置完整可用且有测试。
- **4**：针对实时性、并行性或容量进行明确优化。
- **5**：具有对照项目难以达到的能力，并有源码和性能证据。

每个分数必须附带理由，并与 E0-E4 证据等级并列显示。能力高但证据弱的项目不能被描述为已经独立确认。

### 11.2 差异来源

每项 Aerial 优势归入一种或多种类别：

- CUDA 固有并行能力。
- CUDA Graph、stream、event、MPS、MIG 和数学库等软件栈能力。
- GPUDirect、BlueField 和 DPDK 数据路径。
- 多小区 batch、kernel fusion 和 GPU 数据布局等算法重构。
- pyAerial、PyTorch/CuPy/TensorRT 和 Data Lake 等 AI 工具链。
- 预分配、指标、测试向量、容器等工程实现。
- HBM、Tensor Core 和 GPU 规模等硬件资源。
- 项目投入、商业验证和生态等非 CUDA 因素。

归因必须回答：更换加速器后是否仍成立；移除 BlueField/GPUDirect 后是否仍成立；OAI/OCUDU 通过重构能否复制。

### 11.3 场景化权重

不生成唯一总排名。至少维护以下场景权重：

- 大规模 MIMO 宏站。
- AI-RAN 研究和实时平台。
- 通用开源 SDR 基站。
- 云化 O-RAN DU。

所有权重和原始评分可编辑和重新计算。

## 12. 性能质量规则

性能数字进入正文前必须说明：软件版本与 commit、完整硬件、NR 配置、测试边界、peak/sustained、平均与尾延迟、deadline miss、预热和重复次数、关键优化开关，以及原始日志位置。

以下比较无效：

- GH200 多小区与普通 x86 单小区直接相除。
- PHY test 吞吐与端到端 UE 业务吞吐直接比较。
- GPU 平均吞吐与 CPU P99 slot 延迟比较。
- 64T64R peak cell 与 4T4R average cell 比较。
- 不同 TDD、MCS、层数或 BLER 目标之间比较。

## 13. 最终交付物

1. 《Aerial 与开源 NR 基站总体比较报告》。
2. 《Aerial CUDA 差异化源码分析》。
3. 六份源码主线档案。
4. 统一功能与架构比较矩阵。
5. NVIDIA 性能声明审计表。
6. OAI/OCUDU 可复现 CPU 基准及原始数据。
7. Aerial 实机测试规范。
8. 场景化技术选型矩阵。
9. 文档、commit、文件、符号、配置、脚本和实验数据索引。

## 14. 报告结构

主报告包括：执行摘要、方法、项目架构、Aerial GPU 化边界、NR PHY 比较、cuMAC、前传与内存、扩展性、AI-RAN、性能审计、工程与许可、场景化建议、结论类型以及后续实机计划。

技术附件分别覆盖 PUSCH、PDSCH、LDPC/Polar、64T64R/MU-MIMO、cuMAC、O-RAN 7.2/GPUDirect、CPU 基准、Aerial 声明审计、证据索引和原始实验材料。

结论标记为：已确认事实、实测事实、合理推断、项目方声明或未解决问题。正文使用 `[源码确认]`、`[本地实测]`、`[合理推断]`、`[NVIDIA声明]` 和 `[待Aerial实机验证]` 标签。

## 15. 质量门槛与完成定义

研究完成必须满足：

- 六条源码主线均形成端到端调用链。
- 关键技术结论至少达到 E2；否则明确标为声明、推断或未知。
- 所有源码引用固定版本和 commit。
- 所有性能数字具有硬件、NR 配置和测试边界。
- Aerial 的主要优势都有 OAI 和 OCUDU 对应实现作为对照。
- 每项 CUDA 优化说明其解决的具体瓶颈。
- 每项收益区分算法、实现、软件平台和硬件资源。
- 至少完成一组 OAI 或 OCUDU 可复现 CPU 基线。
- Aerial 实机协议可以由另一位工程师直接执行。
- 报告能够分别回答架构、源码、性能和技术决策问题。

最终成果应明确回答：Aerial 在哪里使用 CUDA、如何并行、怎样管理数据和实时性、cuMAC 是否扩展算法空间、AI 是否进入实时路径、哪些优势可复制、哪些依赖 NVIDIA，以及不同场景应选择哪个实现。

## 16. 已知限制

- 当前没有受支持的 Aerial 硬件，因此不能独立确认 Aerial 的实际容量、尾延迟、deadline miss、功耗和端到端性能。
- OAI/OCUDU CPU 基准与 Aerial 官方结果只能在配置归一和测试边界一致时进行有限对照，不能作为直接性能胜负。
- 项目和文档仍在更新；仓库冻结后出现的新版本必须作为独立变更审计，不能悄然替换基线。
- 部分 NVIDIA 依赖、容器或硬件功能可能具有独立许可和获取条件，必须逐项记录。

