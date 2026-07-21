# NVIDIA Aerial CUDA 差异化源码分析

## 1. 核心答案

**Aerial 的差异不是“把几个 PHY 函数改写成 CUDA”，而是围绕 GPU 重新组织了 NR DU 的计算图、数据布局、前传内存路径、跨小区调度和验证工具链。** [源码确认] 冻结源码中可同时看到：PUSCH/PDSCH CUDA pipeline、LDPC/Polar kernel、SRS→UE grouping→RZF、cuMAC cell-group、CUDA Graph/stream/event，以及 NIC DMA 到注册 GPU memory 后的 packet order/decompression kernel。

其中最难被单独复制的不是某一个 kernel，而是以下闭环：

```text
O-RAN eCPRI/NIC
  → GPU-resident IQ and packet metadata
  → CUDA order/decompression
  → cuPHY channel graphs
  → GPU SRS/channel matrix
  → cuMAC grouping/scheduling/beamforming
  → GPU-resident DL result
  → fronthaul transmit
```

[待Aerial实机验证] 源码证明该闭环存在，但没有证明它在用户目标配置下比 OAI/OCUDU 快多少、节省多少功耗或满足何种 p99.9 deadline。当前所有性能优势必须保持“机制已确认、收益待测”的双层表述。

## 2. CUDA 使用边界

| 层级 | Aerial GPU/CUDA 工作 | 仍在 CPU/外部组件的工作 | OAI/OCUDU 对照 |
|---|---|---|---|
| 前传入口 | packet metadata、order、验证、IQ 解压与 GPU buffer 写入 | DPDK/DOCA 控制、配置、状态和异常编排 | OAI xRAN host buffer/full-slot FIFO；OCUDU 通用 OFH/processor 架构 |
| PUSCH | FFT 后主要接收 pipeline、信道估计、均衡/demapping、rate recovery、LDPC、CRC 等 GPU stages | FAPI 适配、descriptor/setup、部分结果回传和控制 | OAI C/SIMDe/thread pool；OCUDU processor/executor/codeblock tasks |
| PDSCH | CRC/LDPC、rate match、scramble/modulation、DMRS 等 graph/kernels | FAPI、TB 来源管理、graph 参数更新、完成通知 | OAI host buffer/SIMD；OCUDU encoder/modulator/resource-grid tasks |
| 信道编码 | CUDA LDPC/Polar；BG/Z/type/cache/precision 特化和 batch | 配置、测试向量、CPU 参考/集成 | OAI AVX2/AVX-512/SIMDe；OCUDU AVX2/AVX-512/NEON 和 syndrome early-stop |
| Massive MIMO | SRS tensor、GPU UE grouping、自定义 shared-memory RZF | 配置、候选输入、结果消费 | OAI SRS/precoding CPU 组件；OCUDU typed SRS matrix/precoding |
| MAC | PF/排序、UE 下选、PRB/层/MCS、MU-MIMO grouping/beamforming | L2 状态管理、请求聚合/返回和部分控制 | OAI/OCUDU 成熟 CPU scheduler，含 PF/QoS/OLLA/重传 |
| 部署资源 | MPS/MIG、GPU metrics、容器 | Kubernetes、OAM、PTP/SyncE、NIC/OS 管理 | CPU core/NUMA/container orchestration |

这条边界说明 Aerial 不是“全 GPU gNB”。控制面、FAPI/L2 适配、系统配置、网络与异常处理仍需要 CPU；GPU 被放在高数据并行、批处理和联合搜索最密集的路径。

## 3. 差异来源一：CUDA 固有并行能力

### 3.1 PUSCH/PDSCH

[源码确认] PUSCH 将 UE、layer、PRB、code block、LLR 等维度映射为 GPU 并行工作，pipeline 使用可复用 graph executable 和多个 phase stream/event。它解决的瓶颈是上行接收链在每 slot 内包含大量相似、数据并行但依赖明确的算子。

[源码确认] PDSCH 的 create/setup/run 生命周期将 CRC、LDPC、rate matching、调制和 DMRS 等工作组织为 graph 节点；部分 rate-matching-to-modulation 路径融合，减少中间 materialization 和 launch。OAI/OCUDU 也会并行 code block/任务并使用 SIMD，但其基本调度单位是 CPU worker/executor，而不是 GPU block/warp 与 graph replay。

### 3.2 LDPC/Polar

[源码确认] Aerial LDPC 实现按 base graph、lifting size、数据类型、FP32/FP16 和 check-to-variable cache 位置选择 kernel，并支持 batched transport block。这里的 CUDA 固有收益来自大量 check/bit node 更新和 code block 并行。

需要注意两个边界：

- Aerial 冻结源码只确认 `max_iterations` 迭代循环；本研究没有确认与 OCUDU 相同的 syndrome early-stop 路径；
- 发现的 SRS Tensor Core 相关代码处于注释状态，不能计入实际能力；RZF 路径追踪到的是自定义 CUDA shared-memory kernel，不是 cuBLAS/cuSolver 调用。

因此不能用“使用 Tensor Core”或“必然更少迭代”作为 Aerial 优势描述。

## 4. 差异来源二：CUDA runtime 与调度模型

### 4.1 CUDA Graph

[源码确认] Graph 把稳定 pipeline 的 kernel/memcpy 依赖预先实例化，运行时更新动态参数后 replay。它主要针对 slot 周期内反复 launch 相同拓扑的 CPU submission 开销和 launch jitter，而不直接降低单个 kernel 的数学运算量。

OAI/OCUDU 可以通过持久 worker、任务图、批处理和减少动态分配降低类似开销，但不能直接复用 CUDA Graph executable。是否 Graph 在 1/8/20 cell 下带来 p99.9 收益，已由 `AER-CUPHY-GRAPH-001` 预定义 A/B，当前无 E4 结论。

### 4.2 stream、event 与并发 channel

[源码确认] Aerial 为不同 channel/phase 使用 stream 与 event 建立异步执行和完成依赖，使 PUSCH、PDSCH、LDPC 等工作可以在资源允许时重叠。收益取决于：

- 每个 channel 的 SM 配额和资源占用；
- graph 是否形成串行关键路径；
- HBM/共享内存/寄存器竞争；
- 多 cell 聚合是否足以填满 GPU；
- 同步和结果回传是否重新形成 CPU barrier。

所以“存在多个 stream”不等于“全部并行”，必须用 Nsight Systems 的时间线和关键路径验证。

### 4.3 MPS/MIG

[NVIDIA声明] 官方测试工具使用 MPS 在多个 channel/sub-context 间共享 GPU，并给出 MIG gNB 配置。MPS 解决并发 context/SM 分配问题；MIG 解决硬件资源隔离和多租户部署问题。两者不是 PHY 算法本身，也不保证提升单 cell 性能。`AER-MPS-AB-007` 与 `AER-MIG-AB-008` 分别验证调度和隔离代价。

## 5. 差异来源三：GPUDirect/BlueField 数据路径

[源码确认] Aerial 前传路径注册 CUDA external memory，映射供 NIC DMA 使用，通过 DOCA GPUNetIO 获取 packet metadata，再由 CUDA order kernel 校验、排序和解压上行 O-RAN packet。相较 OAI 已追踪的 xRAN host buffer→full-slot callback/FIFO→gNB buffer 路径，Aerial 把包处理与 PHY 输入布置推进到 GPU 一侧。

该设计解决的不是 FLOPS，而是 7.2 前传中的 copy、cache pollution、PCIe/内存往返、CPU packet processing 和数据到达 jitter。理论 payload 计算已显示 64T64R 下数据量相对 4T4R 放大 16 倍，因此数据路径的重要性随天线数上升；该数字只是 payload 推导，不含 header、exponent、控制面和协议开销。

**反事实：移除 GPUDirect。** cuPHY kernel 仍能计算，CUDA Graph 也仍可 replay，但 IQ 必须经过 host staging 和显式 copy；CPU、内存带宽和同步点增加，slot slack 可能减少。实际影响不能由源码定量得出，必须执行 `AER-GDR-AB-006`。如果冻结版本没有等价 host-staging 路径，则只能报告“反事实不可执行”，不能伪造 speedup。

## 6. 差异来源四：算法与数据布局重构

### 6.1 batch 与 cell-group

[源码确认] Aerial 不只并行单 cell 内部算子。cuPHY 测试和 cuMAC 数据结构都以多 cell/channel 聚合为重要尺度；cuMAC 把 per-cell request 聚合为 cell-group device state，再执行 UE selection、PRG allocation、layer/MCS 和 grouping。

GPU 的高吞吐要求足够并行度，因此 batch/cell-group 既是性能技术，也是算法边界改变：它允许跨 cell/PRG/UE 候选同时评估。OAI/OCUDU 的 CPU scheduler 同样复杂且具 PF/QoS/OLLA、重传优先级和资源一致性约束；差异不是“CPU scheduler 简单”，而是 Aerial 把更大的候选张量和联合步骤作为 GPU 工作负载。

### 6.2 fusion 与中间数据常驻

[源码确认] PDSCH 中可见融合的 rate-matching/modulation 路径；PUSCH/PDSCH/LDPC graph 和 GPU buffer 生命周期减少逐算子 host round-trip。fusion 的收益可能来自少一次 HBM 读写、少一次 launch 或更好的 producer-consumer locality，但也可能增加寄存器压力和降低可复用性，必须逐 kernel profile。

### 6.3 64T64R RZF

[源码确认] Aerial RZF kernel 把 channel、Gram、inverse 和 weight 工作数组放入 shared-memory 组织，并以基站天线和 group layer 为索引处理。真正差异是 SRS tensor 能继续留在 GPU，直接服务 UE grouping 与 beamforming，而不是每一步回到 CPU。

这是 CUDA 与算法重构共同产生的能力：矩阵运算适合 GPU，但 grouping、PRG 和层数选择的数据布局/批处理方式决定能否利用硬件。仅把现有 CPU `for` 循环机械移植成 kernel，通常不能得到相同链条。

## 7. 差异来源五：AI 工具链

[NVIDIA声明] Aerial 文档和仓库包含 pyAerial、CuPy、TensorRT、Data Lake、神经 PUSCH receiver/channel estimation 和 DRL-MCS 示例/组件。[源码确认] cuMAC 的核心 CUDA scheduler 路径与 SRS/MU-MIMO 数据结构已经形成 GPU 数据面基础。

本研究没有确认 DRL 模型在所有生产调度路径默认启用；已定位的 DRL 内容主要位于 examples/test vectors 和集成接口。因此正确结论是“Aerial 降低 AI 进入实时 RAN 数据面的工程距离”，不是“当前每个调度决策都由 AI 完成”。

OAI/OCUDU 可以外接 Python、GPU 推理或 RIC/AI 服务，但若希望在 slot deadline 内共享 PHY tensor，需要新增 device memory ownership、异步调度、模型生命周期和 fallback 机制。这是可复制的系统工程，不是现有等价能力。

## 8. 差异来源六：工程化与非 CUDA 因素

以下能力经常与 CUDA 同时出现，但不应归因给 CUDA 指令集：

| 能力 | 主要来源 | 若更换 GPU 是否保留 |
|---|---|---|
| 5GModel/test vectors/CPU reference | 验证工程投入 | 大部分保留 |
| FAPI/NVIPC/L2 adapter | 接口与系统架构 | 可移植但需重写适配 |
| RU Emulator、late/early/error 检查 | 前传测试工程 | 可保留 |
| PTP/SyncE、CPU isolation、OAM | 实时部署工程 | 可保留 |
| 容器/Kubernetes | 云部署工程 | 可保留 |
| MPS/MIG | NVIDIA runtime/hardware | 不直接保留 |
| GPUDirect/DOCA GPUNetIO/BF3 | NVIDIA 数据路径 | 不直接保留 |
| CUDA Graph/kernels | CUDA 软件栈 | 不直接保留 |

因此 Aerial 的竞争力是 CUDA、NVIDIA 平台和大量 RAN 工程验证的组合。把全部收益写成“GPU 算力”会低估数据路径和工程；把全部能力写成“NVIDIA 独有”又会低估算法与架构的可复制部分。

## 9. 与 OAI/OCUDU 的逐项对照

| 主题 | Aerial | OAI | OCUDU | 差异性质 |
|---|---|---|---|---|
| PUSCH | GPU graph pipeline | C/SIMDe/thread pool | processor/executor/codeblock tasks | runtime + data layout |
| PDSCH | graph + fused CUDA stages | host/SIMD pipeline | encoder/modulator tasks | fusion + launch model |
| LDPC | CUDA BG/Z/cache/precision specialization | AVX2/AVX-512/SIMDe | AVX2/AVX-512/NEON + early-stop | intrinsic parallelism + specialization |
| Polar | CUDA encode/decode | host C/SCL | componentized CPU | implementation platform |
| Massive MIMO | GPU SRS/grouping/custom RZF | CPU SRS/rank/precoding components | typed SRS matrix/precoding | algorithm redesign + GPU residency |
| MAC | cell-group CUDA joint stages | CPU PF/policy pipeline | CPU slice/QoS/PF/OLLA allocator | execution + search-space expansion |
| 前传 | NIC→GPU DMA/order/decompress | xRAN host buffers/FIFO | modular OFH/executor | data path |
| 资源隔离 | MPS/MIG | CPU/container | CPU/container | hardware/runtime |

OAI/OCUDU 的优势不是“没有 GPU”，而是完整协议栈、通用硬件、可修改 CPU 代码和更低平台绑定；它们的 SIMD、worker/executor 和模块化 allocator 也体现了成熟的实时工程。Aerial 的优势在高天线数、多 cell、联合调度和 AI/GPU 共驻场景更可能放大。

## 10. 三个反事实问题

### 10.1 更换加速器后哪些仍成立？

**仍成立：** pipeline graph 思想、预分配、batch/cell-group、fusion、device-resident intermediate、CPU reference/test vectors、SRS→grouping→beamforming 的连续数据流。

**必须重写：** CUDA kernels、Graph/stream/event、MPS/MIG、CUDA memory API、Nsight 工具接入，以及大量性能特化。若新加速器没有 NIC direct DMA 和等价实时 runtime，系统边界也需改变。

结论：算法架构部分可移植，现成实现和性能不可移植。

### 10.2 移除 BlueField/GPUDirect 后哪些仍成立？

cuPHY/cuMAC 计算和 GPU 算法仍成立；NIC→GPU 的低 copy 路径、GPU packet ordering 与预期实时 slack 不再成立。系统可能仍可运行，但必须重新设计 host staging、buffer ownership、NUMA 与同步，并重新测容量/尾时延。

### 10.3 OAI/OCUDU 通过重构能复制什么？

**可复制：** 多 cell batch、预分配、任务图、kernel fusion 思路、GPU LDPC/MIMO 插件、SRS tensor 复用、CPU/GPU scheduler reference 对照、direct-I/O 抽象。

**难直接复制：** 已调优的 CUDA kernel/graph、MPS/MIG、DOCA/BF3/GPUDirect 组合、Aerial test vector 与性能脚本整合、同一供应商端到端支持。复制的主要成本是多年工程和验证，而不仅是代码行数。

## 11. 性能声明能证明什么

[NVIDIA声明] 官方页面列出 GH200 上 20 x 100 MHz 4T4R peak cuPHY、40 x 100 MHz 4T4R average cuMAC、64T64R 多 cell 和 E2E aggregate throughput 等数据。

它们只能证明 NVIDIA 针对这些边界做过验证，不能证明：

- 相对 OAI/OCUDU 的加速倍数；
- 相同业务模型下的 p99.9 slot latency；
- 每瓦性能或整机 TCO；
- 通用 CPU、GH200 和不同 RU/NIC 的公平比较；
- 20 peak cuPHY 与 40 average cuMAC 可相除或合成完整 gNB 容量。

结构化审计结果为 14 条：3 条可在约束下作为复现目标，5 条仅用于厂商内部能力边界，6 条上下文不足。详见 [`aerial-performance-claims-audit.md`](aerial-performance-claims-audit.md)。

## 12. 最终判断

1. **CUDA 固有贡献：** LDPC/Polar、MIMO、demapping、调制等大规模数据并行 kernel；
2. **CUDA runtime 贡献：** Graph/stream/event/MPS 减少 submission、组织重叠并分配 GPU；
3. **数据路径贡献：** GPUDirect/BF3/DPDK/DOCA 把 7.2 IQ 更早送入 GPU；
4. **算法重构贡献：** batch、cell-group、fusion、GPU-resident SRS/grouping/RZF；
5. **硬件资源贡献：** HBM、GPU SM、MIG 隔离；
6. **工程贡献：** FAPI、test vectors、CPU reference、RU emulator、OAM、容器和故障处理；
7. **非 CUDA 贡献：** NVIDIA 的平台整合、发布验证和生态工具。

**最准确的一句话是：Aerial 把 GPU 从“PHY 加速卡”提升为 NR DU 的实时计算与数据驻留中心。** [源码确认] 这个架构差异已经成立；[待Aerial实机验证] 它在具体网络配置中的容量、尾时延、功耗和经济收益仍需按实机协议逐项证实。
