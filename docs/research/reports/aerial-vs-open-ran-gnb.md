# NVIDIA Aerial 与开源 NR gNB 深度比较报告

## 1. 执行摘要

本研究比较 NVIDIA Aerial CUDA-Accelerated RAN、Duranta/OpenAirInterface（OAI）和 OCUDU，范围严格限定 NR gNB/DU；O-RAN SC O-DU High/Low 仅作接口和组件参照。

主要结论如下：

1. **Aerial 不是仅把 PHY 搬到 GPU。** [源码确认] 它把 O-RAN 前传 GPU memory、PUSCH/PDSCH CUDA Graph、LDPC/Polar、SRS/MU-MIMO/RZF、cuMAC cell-group 和 MPS/MIG 组织为连续平台。
2. **OAI 与 OCUDU 不是“未优化的 CPU 基线”。** [源码确认] OAI 使用 C/SIMDe/AVX/thread pool 和成熟 NR scheduler；OCUDU 使用 executor、类型化 upper/lower PHY、AVX/NEON 组件和 slice/QoS/PF/OLLA scheduler。
3. **cuMAC 同时加速相似算法并扩展搜索空间。** [源码确认] PF/排序等有 CPU 对应物；跨 cell/UE/PRG/层的联合 grouping、beamforming 和资源分配把更大候选空间变成 GPU workload。
4. **Aerial 最具差异化的场景是 64T64R、AI-RAN 和高密度云化 DU。** [合理推断] 通用 SDR、教学和跨硬件移植场景更偏向 OCUDU/OAI。
5. **当前不能给出公平性能排名。** [待Aerial实机验证] 没有 GH200/BF3 环境；OAI/OCUDU 也未在本机 Linux 环境运行。NVIDIA 数字是审计后的 vendor claims，不是本研究 measured facts。

最终选型不是“Aerial、OAI、OCUDU 谁总体最好”，而是：是否愿意用 NVIDIA 平台、功耗与部署复杂度换取 GPU 常驻数据流、massive-MIMO/联合调度和 AI 共平台潜力。

## 2. 范围、版本与方法

### 2.1 固定对象

| 项目 | 固定版本/commit | 角色 |
|---|---|---|
| NVIDIA Aerial | `29f5870fd84b0176df48b40667c1b8f1740e6d09`；文档 26.1 | 主比较：GPU L1、cuMAC、前传、工具链 |
| Duranta/OAI | `31ffb21a8204ae9706a88eb08606a80fc8eafb3e` | 主比较：完整 CPU NR gNB/CU/DU |
| OCUDU | `6d44c2a5e5b2a81a4c67460b460ef99e789943cf`；v26.04 | 主比较：完整开放 CU/DU/L1/L2/L3 |
| O-RAN SC O-DU High | `04feb1fd9f815d4a87fb502a961cdbfa5209c7f4` | MAC/FAPI/O-DU High 参考 |
| O-RAN SC O-DU Low | `6ef1d2b70db585e351b9cd35c6054c1b249a7465` | lower-PHY/xRAN/FAPI translator 参考 |

迁移关系已核实：OAI 当前主线进入 Duranta；OCUDU 是 srsRAN Project 后继。固定基线详见 [`version-baseline.md`](../architecture/version-baseline.md)。

### 2.2 证据规则

- E0：项目声明；E1：官方文档/API/架构；E2：固定 commit 源码；E3：仓库测试/CPU reference/benchmark 方法；E4：本研究独立复现；
- 正文使用 `[源码确认]`、`[本地实测]`、`[合理推断]`、`[NVIDIA声明]`、`[待Aerial实机验证]`；
- 当前没有任何 Aerial E4；标准结果 CSV 保持零 measured 行；
- 不比较不同 hardware、天线、TDD、负载、test boundary 或 statistic。

研究从官方文档进入固定源码，沿 PUSCH、PDSCH、LDPC/Polar、64T64R、cuMAC 和 7.2/GPUDirect 六条端到端主线追踪。27 条基础 claim 由自动校验器约束 commit/path/symbol 与证据等级。

## 3. 项目定位与系统架构

### 3.1 Aerial

[源码确认] Aerial 仓库分为 `cuPHY` CUDA 算法、`cuPHY-CP` 控制/前传/L2 adapter、`cuMAC`、`cuMAC-CP`、`5GModel`、`testVectors`、`testBenches` 和 pyAerial。CPU 负责控制、接口和 orchestrate，GPU 执行大部分高并行 PHY、部分 packet 处理和 scheduler stages。

其系统主线是：

```text
L2/TestMAC → FAPI/NVIPC → L2 adapter → cuPHYDriver
                                      ↘ CUDA cuPHY graphs
RU/eCPRI → DPDK/DOCA → GPU packet order/decompress ↗
```

### 3.2 OAI

[源码确认] OAI 在一个仓库内连接 NR MAC scheduler、FAPI/nFAPI、RU、L1 procedures、编码和 SIMD PHY。它更接近传统通用 CPU 软件基站：per-slot MAC 请求进入 gNB TX/RX，PHY 通过 C、固定点、SIMDe/AVX 和 thread pool 分解任务。

优势是端到端完整性、已有 OAI 生态和多种 RF/FH 模式；代价是 high-antenna/multi-cell workload 需要 CPU core/NUMA/SIMD 或外部加速器持续扩展。

### 3.3 OCUDU

[源码确认] OCUDU 把 CU-CP、CU-UP、DU-high、DU-low upper/lower PHY、FAPI fastpath 和 executor 分成类型化组件。slot request 进入 repository/processor，symbol callback 触发工作，结果通过 notifier 返回；调度器含 slice、QoS、PF、OLLA、重传和 typed allocator。

优势是模块边界、BSD 风格许可、通用 x86/ARM 与完整开放 CU/DU；其 GPU/AI/massive-MIMO 联合链需要额外研发。

### 3.4 统一映射

三者都覆盖或连接 RU/FH、lower PHY、upper PHY、FAPI、MAC/RLC 和 CU/DU，但“组件所有权”不同：Aerial 把 GPU L1/cuMAC 与平台工具作为核心，OAI 是紧耦合完整 RAN，OCUDU 是接口化完整 CU/DU。详细映射见 [`unified-ran-map.md`](../architecture/unified-ran-map.md)。

## 4. Aerial 的 CPU/GPU 边界

[源码确认] GPU 侧包括：

- PUSCH/PDSCH channel pipelines 和 CUDA kernels；
- LDPC/Polar 编解码、rate recovery/matching、调制/demapping 等；
- SRS channel tensor、MU-MIMO grouping、自定义 RZF；
- cuMAC PF/排序、UE 下选、PRB/层/MCS、grouping/beamforming；
- 前传 packet order、验证和 IQ decompression；
- GPU-resident intermediate buffers、Graph/stream/event。

[源码确认] CPU/系统侧仍包括：

- FAPI/NVIPC、L2 adapter、descriptor/config、graph 参数更新；
- worker 编排、状态机、错误处理、OAM；
- DPDK/DOCA/NIC/PTP/容器的控制；
- 需要回到 L2 的 indications 和结果。

所以 Aerial 的正确描述是“GPU-centric heterogeneous DU”，不是“全 GPU 基站”。

## 5. PUSCH 上行接收比较

统一处理链：

```text
FH IQ → reorder/decompress → FFT → channel estimate → MIMO/equalize
→ soft demap → rate recovery → LDPC decode → CRC → indication
```

| 项目 | 执行模型 | 关键差异 |
|---|---|---|
| Aerial | reusable CUDA graph、phase streams/events、GPU input/output | pipeline topology 预实例化，数据尽量 GPU 常驻 |
| OAI | C procedures、fixed-point、SIMDe、thread-pool jobs | CPU SIMD 和任务分解，host buffer ownership |
| OCUDU | slot repository、symbol callback、processor/notifier、codeblock executor | 类型化异步组件和任务 executor |

[源码确认] Aerial 的差异是把 channel/codeblock/UE 并行和依赖图同时映射到 GPU，并显式控制 selected output transfer。OAI/OCUDU 的优势是 CPU 代码直接可调试、可运行在更广硬件，并能使用成熟 task/executor 体系。

[待Aerial实机验证] Graph 是否降低 p99.9、GPU batch 在低 UE/单 cell 时是否利用不足、回传和同步是否成为瓶颈，必须通过 `AER-CUPHY-GRAPH-001` 验证。详见 [`pusch.md`](../dossiers/pusch.md)。

## 6. PDSCH 下行生成比较

统一处理链：

```text
MAC TB → CRC → LDPC encode → rate match → scramble/modulate
→ layer map/precoding → resource map → IFFT/CP → FH IQ
```

[源码确认] Aerial PDSCH 具有 create/setup/run 生命周期、CUDA graph、独立 LDPC stream/event、CPU 或 GPU TB 输入，并包含 CRC、LDPC、融合 rate-matching-to-modulation、DMRS 等 kernels。OAI 通过 host CRC/segmentation/LDPC、fixed-point/SIMDe 生成；OCUDU 将 encoder、modulator 和 resource-grid mapper 分离到 executor tasks。

Aerial 的收益机制是减少 launch/中间 materialization、并行 codeblocks/channels 和保持 device buffers；代价是 graph-safe buffer 生命周期、预分配、GPU memory 容量和复杂同步。详见 [`pdsch.md`](../dossiers/pdsch.md)。

## 7. 信道编码与 64T64R

### 7.1 LDPC/Polar

[源码确认] Aerial 按 BG、lifting size、数据类型、FP32/FP16、register/shared/global cache 选择 LDPC kernel，并有 batched TB 和 CUDA Polar。OAI 具 SIMDe/AVX2/AVX-512 LDPC/rate-matching 及 host Polar/SCL；OCUDU 具 generic/AVX2/AVX-512/NEON、soft-combining、明确 syndrome early-stop 和组件化 Polar。

这说明 Aerial 的优势是 GPU specialization/batch，而非标准算法独占。不能声称 Aerial 已确认 syndrome early-stop，也不能把注释掉的 Tensor Core 代码计入能力。详见 [`channel-coding.md`](../dossiers/channel-coding.md)。

### 7.2 Massive MIMO

[源码确认] Aerial 形成 SRS channel-estimate tensor → CUDA UE grouping → custom shared-memory RZF → beam weights 的连续链，并与 cuMAC 调度空间相连。OAI 具 SRS request/extraction、rank 和 beam-weight application；OCUDU 具 typed wideband SRS channel matrix 和 precoding/resource-grid 组件。

[合理推断] Aerial 在 64T64R 上的主要潜力来自矩阵/候选并行、GPU 数据驻留和调度/beamforming 联合，而不只是矩阵乘法。其 RZF 追踪到自定义 kernel，未发现被实际调用的 cuBLAS/cuSolver 或 Tensor Core 路径。详见 [`massive-mimo.md`](../dossiers/massive-mimo.md)。

## 8. cuMAC 与 CPU scheduler

[源码确认] cuMAC 从 per-cell request 聚合 cell-group state，进入 device buffers，执行 UE selection、multi-cell PRG allocation、layer/MCS/OLLA、MU-MIMO grouping/beamforming，再返回 per-cell response。仓库存在 CPU reference 和 CPU/GPU 结果检查方法（E3），但当前未运行。

[源码确认] OAI scheduler 不是简单 round-robin：它建立 per-UE candidates，处理 RI/PMI、time-domain、beam、MCS、PF RB allocation 和 retransmission/VRB commitment。OCUDU 进一步包含 slice-aware scheduling、QoS/PF priority、estimated rate、typed allocator、PDCCH/PDSCH/PUSCH/UCI 一致性和 OLLA。

因此 cuMAC 的两类价值必须分开：

1. **相同/相近算法加速：** PF metric、排序、下选和 allocation；
2. **算法空间扩展：** cell×UE×PRG×antenna/layer 的联合 grouping、beamforming 和调度。

[合理推断] 第二类可能比单函数 speedup 更重要，因为它允许在 slot deadline 内评估更大候选空间；但 CPU/GPU objective、tie-break、输入规模和结果等价性必须由 `AER-CUMAC-*` 实测确认。详见 [`cumac.md`](../dossiers/cumac.md)。

## 9. O-RAN 7.2、内存与实时性

[源码确认] Aerial 注册 CUDA external memory 供 DPDK/NIC DMA，DOCA GPUNetIO 提供 packet metadata，CUDA order kernel 校验、排序、解压并写入 PHY 输入；同时区分 early/on-time/late、lost PRB、no-packet 和 partial-packet timeout。

[源码确认] OAI xRAN 路径管理 per-antenna/per-symbol host buffers 和 PRB maps，通过 full-slot callback/FIFO 把 IQ 交给 gNB，并记录 early/late/corrupt/duplicate 等计数。O-RAN SC O-DU Low 提供 xRAN/compression/timing/FAPI-WLS 参考。

理论 payload-only 数据量（100 MHz、30 kHz、273 PRB、14 symbols、2000 slots/s）：

| 配置 | 32-bit complex IQ | 简化 BFP9 18-bit |
|---|---:|---:|
| 4T4R | 11.741 Gbit/s | 6.604 Gbit/s |
| 64T64R | 187.859 Gbit/s | 105.671 Gbit/s |

这些是 derived 上下界，不含 headers、exponents、C-plane 和协议开销。它们解释了为什么 64T64R 下 copy/DMA/decompression 架构重要，但不构成任何项目实测带宽。

**移除 GPUDirect 的反事实：** PHY kernels 仍存在，但增加 host staging、copy、CPU/NUMA 和同步；实际 deadline 影响待 `AER-GDR-AB-006`。详见 [`fronthaul-realtime.md`](../dossiers/fronthaul-realtime.md)。

## 10. 多小区、AI-RAN 与平台扩展

[源码确认] Aerial 以 cell-group、multi-channel testbench、MPS 和 GPU batch 为扩展单位；OAI/OCUDU 主要以 CPU threads/executors、core affinity 和 NUMA 扩展。两种模型都可能达到实时要求，但资源饱和形态不同：GPU 关注 SM/HBM/launch/stream contention，CPU 关注 core/SIMD/cache/NUMA/IRQ。

[NVIDIA声明] Aerial 26.1 文档列出 Kubernetes 20 peak 4T4R cells、MIG、MPS、pyAerial/CuPy/TensorRT/Data Lake 和 AI/MU-MIMO 功能。[源码确认] 实时 cuMAC/SRS 数据结构为 AI 插入提供了较短路径；[合理推断] 这使 Aerial 更适合 AI 与 RAN 共平台研究。

但本研究没有证明所有 DRL/神经模块默认处于生产实时路径，也没有测量 AI co-tenant 对 deadline 的影响。`AER-MIG-AB-008` 已定义固定 co-tenant 和隔离测试。

## 11. 性能声明审计

NVIDIA 官方数字被拆成 14 条结构化记录：

- 3 条 `comparable_with_constraints`：可作为同条件未来复现目标；
- 5 条 `vendor_only`：只能说明 NVIDIA 自身测试边界；
- 6 条 `insufficient_context`：缺少硬件、带宽、天线或统计口径，禁止进入数值比较。

可引用的受约束目标包括：[NVIDIA声明] 24-2 MGX Grace Hopper 20 个 100 MHz 4T4R peak-loaded cuPHY cells；25-1 GH200、8-cell CN+RAN+UE-EM/eCPRI E2E aggregate DL 11.2 Gbit/s、UL 1.68 Gbit/s。即使这些字段较完整，仍缺 p99.9、功耗、重复、BLER 和本研究复现。

不能做的比较包括：

- 20 peak cuPHY cells 与 40 average cuMAC cells 相除；
- 4T4R 与 64T64R、early-HARQ 与非 early-HARQ合并；
- standalone L1、scheduler 和 E2E 吞吐混排；
- NVIDIA vendor claim 与未运行的 OAI/OCUDU CPU 基准生成 speedup。

详见 [`aerial-performance-claims-audit.md`](aerial-performance-claims-audit.md)及 `data/performance/vendor-claims.csv`。

## 12. 工程、许可与采用成本

| 维度 | Aerial | OAI | OCUDU |
|---|---|---|---|
| 核心许可 | Apache-2.0 | CSSL-1.0/逐文件例外 | BSD-3-Clause Open MPI variant |
| 贡献模式 | 仓库声明当前不接受贡献 | Duranta/OAI 社区流程 | Linux Foundation/开放治理 |
| 硬件依赖 | NVIDIA GPU、CUDA；高性能 FH 强依赖 BF/ConnectX/DOCA 路径 | 通用 CPU、多 RF/FH；可接外部加速 | 通用 x86/ARM、split 8/7.2、可选外部加速 |
| 调试 | Nsight + GPU/CPU/系统多层 | 常规 C/Linux perf/线程调试 | C++/executor/单测与 Linux perf |
| 部署复杂度 | GPU/NIC/PTP/MPS/MIG/container 组合高 | RF/DPDK/NUMA/实时配置仍复杂 | 模块化但 7.2/实时同样要求系统工程 |
| 供应商退出成本 | 高 | 中 | 低–中 |

[合理推断] Aerial 可能用更少节点/更高 cell density 抵消硬件成本，但当前没有 TCO、功耗和同业务模型 E4 数据，不能下经济结论。OAI/OCUDU 的“通用硬件”也不表示实时部署简单：CPU isolation、NUMA、DPDK、PTP 和 RU 互通仍需大量工程。

## 13. 场景化建议

用户确认的四场景独立权重产生以下结果：

| 场景 | 优先候选 | 条件 |
|---|---|---|
| 64T64R 宏站 | Aerial（4.00） | 必须完成 massive-MIMO、E2E、功耗/BLER/尾时延 E4；OCUDU（3.50）为开放路线 |
| AI-RAN | Aerial（4.15） | 验证 AI/PHY 共存、MIG/MPS 干扰和模型 fallback；OCUDU（2.90）适合开放协议研究 |
| 通用 SDR | OCUDU（4.55） | OAI（3.90）适合已有生态；Aerial（3.00）仅在 GPU/AI 是核心目标时进入 |
| 云化 O-RAN DU | Aerial（4.10）/OCUDU（4.00）双候选 | 0.10 小于证据不确定性，必须同边界 POC；OAI（3.25）适合既有 OAI 体系 |

这些分数是能力/权重模型，不是性能成绩，也不能跨场景求平均。详见 [`scenario-decision-matrix.md`](scenario-decision-matrix.md)。

## 14. 结论类型与后续计划

### 14.1 已确认事实

- [源码确认] Aerial 在 PUSCH、PDSCH、LDPC/Polar、SRS/MU-MIMO/RZF、cuMAC 和前传路径广泛使用 CUDA；
- [源码确认] CUDA Graph/stream/event、GPU-resident buffers 和 NIC→GPU 数据路径是系统结构，不是单 kernel 附属优化；
- [源码确认] OAI/OCUDU 都有成熟 CPU SIMD、任务并行和复杂 scheduler，不能作为“朴素 CPU”对照；
- [源码确认] cuMAC 既加速部分传统 scheduler 步骤，也扩大联合优化候选空间。

### 14.2 合理推断

- [合理推断] Aerial 的优势会随天线、cell、候选 UE/PRG 和 AI 共驻规模扩大；
- [合理推断] 单 cell、低负载或高度可移植场景可能无法摊薄 GPU/平台成本；
- [合理推断] OAI/OCUDU 能复制 batch、任务图、GPU plugin 和数据驻留思想，但需要显著重构与验证。

### 14.3 尚未解决

- [待Aerial实机验证] 同配置 capacity、p99.9、deadline miss、BLER、功耗和 TCO；
- [待Aerial实机验证] Graph、GDR、MPS、MIG 的独立贡献；
- [待Aerial实机验证] 64T64R 与 AI co-tenant 下稳定性；
- OAI/OCUDU CPU 基准也因当前无 Linux 运行环境保持未测。

后续执行包已经冻结：[`cpu-baseline.md`](../protocols/cpu-baseline.md)定义 OAI/OCUDU 100 MHz 4T4R 同边界 CPU 基准；[`aerial-hardware-validation.md`](../protocols/aerial-hardware-validation.md)和 `config/aerial-test-matrix.yaml`定义 10 个 Aerial case。只有产生完整环境清单、原始日志、checksum 和所需重复后，相关结论才升级为 E4。

**最终结论：** Aerial 展示的是一种 GPU-centric NR DU 设计：将并行 PHY、massive-MIMO、scheduler 和前传数据路径共同围绕 CUDA/NVIDIA 平台重构。它在高维计算和 AI-RAN 场景具备最强差异化潜力，但代价是硬件绑定、系统复杂度和当前缺少独立实测。OCUDU/OAI 则以完整开放栈、通用硬件和可修改性形成不同优势。应按场景和退出成本选择，而不是追求一个脱离测试边界的总排名。
