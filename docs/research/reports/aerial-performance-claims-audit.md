# NVIDIA Aerial 性能声明审计

## 1. 结论先行

本审计不能得出“Aerial 比 OAI 或 OCUDU 快多少”的统一排名。NVIDIA 当前公开页面给出了多组容量和吞吐数字，但它们跨越了不同版本、硬件、天线规模、流量模型以及测试边界。尤其需要避免以下错误拼接：

- `20 x 100 MHz 4T4R peak cells` 是 cuPHY 或 E2E 配置容量，不等于调度器单模块的吞吐能力；
- `40 x 100 MHz 4T4R average cells` 是独立 cuMAC 调度器口径，不能与前者相除后宣称“MAC 比 PHY 快两倍”；
- `peak`、`average` 和 `telco-grade traffic model` 不是同一种负载统计量；
- 4T4R、64T64R、早 HARQ、调制压缩、BFP9 和 MIG 会改变工作量与数据路径；
- 厂商验证数字没有同提交、同硬件、同射频前传和同业务模型的 OAI/OCUDU 对照组。

因此，本阶段把声明分为“可在约束条件下比较”“仅能说明厂商内部能力边界”“上下文不足”三类，而不生成综合性能分或倍数。

## 2. 审计方法

结构化原始记录位于 [`data/performance/vendor-claims.csv`](../../../data/performance/vendor-claims.csv)，自动审计器位于 [`scripts/audit_vendor_claims.py`](../../../scripts/audit_vendor_claims.py)。每条声明必须同时具备：

1. 来源 URL 与文档版本；
2. 硬件、带宽和天线配置；
3. 小区/UE 范围；
4. 测试边界，例如独立 cuPHY、独立 cuMAC 或完整 E2E；
5. 统计口径，例如 peak、average 或 aggregate achieved throughput；
6. 明确的比较适用范围。

只要任一字段缺失，自动归为 `insufficient_context`。这是一条保守规则：空白表示官方摘要没有给出足够信息，并不表示相应条件不存在。

## 3. 审计结果

### 3.1 可在约束条件下比较

这些数字可用于限定条件下的复现实验目标或容量规划参照，但不能直接与其他项目横向排名。

| ID | 官方声明 | 有效约束 | 可做什么比较 |
|---|---|---|---|
| AERIAL-VENDOR-002 | 20 个峰值负载 4T4R、100 MHz 小区 | 24-2、MGX Grace Hopper、cuPHY、多小区、电信级流量模型 | 未来同硬件、同业务模型的 L1 容量复现 |
| AERIAL-VENDOR-007 | 8 个 4T4R、100 MHz 小区聚合下行 11.2 Gbit/s | 25-1、GH200、CN+RAN+UE-EM、eCPRI E2E | 同边界 E2E 聚合吞吐复现 |
| AERIAL-VENDOR-008 | 同配置聚合上行 1.68 Gbit/s | 同上 | 同边界 E2E 聚合吞吐复现 |

上述三项仍缺少公开的时延分布、重复次数、误块率、CPU/GPU 利用率、功耗和测试向量。因此“可比较”仅指字段足以定义约束实验，不代表已具备第三方可重复性。

### 3.2 仅能说明厂商内部能力边界

| ID | 官方声明 | 不能外推的原因 |
|---|---|---|
| AERIAL-VENDOR-001 | GH200 上独立 cuPHY 支持 20 个 100 MHz 4T4R 峰值小区 | 没有 OAI/OCUDU 同条件对照；模块边界不同 |
| AERIAL-VENDOR-004 | GH200 上 3 个 100 MHz 64T64R average cuPHY 小区 | 含调制压缩；average 模型定义未公开展开 |
| AERIAL-VENDOR-009 | 8 个峰值小区启用 MIG | 只证明该配置被验证，不证明隔离开销或收益 |
| AERIAL-VENDOR-010 | GH200 上 cuMAC 支持 40 个 100 MHz 4T4R average 小区 | 独立调度器边界，不能与完整 gNB 容量等同 |
| AERIAL-VENDOR-011 | GH200 上 cuMAC 支持 3 个 100 MHz 64T64R average 小区 | 同上，且 MU-MIMO 候选空间和负载模型未完整公开 |

这些声明对分析 CUDA 差异化仍有价值：它们显示 NVIDIA 分别对 L1、调度器、MIG 多租户和 massive-MIMO 进行了容量验证，但它们不是跨项目性能证据。

### 3.3 上下文不足

| ID | 官方声明 | 缺失字段或歧义 |
|---|---|---|
| AERIAL-VENDOR-003 | 6 个 100 MHz 64T64R 峰值小区 | 摘要未明确硬件 |
| AERIAL-VENDOR-005 | 20 小区 Capgemini E2E、DL-only 1.25 Gbit/s | 摘要未明确硬件和统计口径；速率是每小区还是整体的表述存在歧义 |
| AERIAL-VENDOR-006 | 单个 64T64R 小区、2 UE x 2 层、峰值 1.44 Gbit/s | 摘要未明确硬件 |
| AERIAL-VENDOR-012 | DGX Spark 单峰值小区下行 1.5 Gbit/s | 未明确带宽和天线配置 |
| AERIAL-VENDOR-013 | DGX Spark 单峰值小区上行 210 Mbit/s | 未明确带宽和天线配置 |
| AERIAL-VENDOR-014 | GH200/Kubernetes 编排 20 个峰值 4T4R 小区 | 未明确带宽和天线配置 |

这些条目不能进入数值对比表。后续若从详细性能测试章节、配置文件或 NVIDIA 提供的测试向量补齐字段，应更新 CSV 后重新运行审计器，而不是在报告文字中做隐含假设。

## 4. 对 CUDA 差异化分析的含义

公开数字支持的是“设计投资方向”，而不是“相对 CPU 项目的加速倍数”：

- **cuPHY 多小区并行**：20 个 4T4R 峰值小区和 64T64R 多小区配置与代码中跨小区批处理、CUDA graph/stream、GPU 常驻缓冲的方向一致；
- **cuMAC 单独扩展**：40 个 4T4R average 小区说明 NVIDIA 把 PF 指标、排序、UE 下选、PRB/层选择和 MU-MIMO 分组作为独立 GPU 工作负载验证；
- **完整数据路径**：E2E 的 8/20 小区声明覆盖 CN、L2/L1、eCPRI 和 UE/RU 仿真器，不能只归因于单个 CUDA kernel；
- **系统级复用**：MIG 和 Kubernetes 声明强调资源隔离、部署和编排，这属于平台差异化，不等于 PHY 算法加速。

所以最终报告应把 CUDA 工作拆为四层：算法 kernel、批处理与流水线、GPU/NIC 内存路径、部署与资源隔离。只有第一层可在微基准中讨论 kernel 加速；E2E 数字必须保留全部系统边界。

## 5. 无硬件阶段与未来复现

当前没有 GH200/BF3、O-RU 或精确时钟环境，本阶段只能完成来源核验、字段审计和静态实现映射。未来硬件实验至少需要固定：

- 相同 NR numerology、TDD pattern、PRB、MCS、层数、UE 数和 HARQ 配置；
- 相同前传压缩、包大小、NIC、PTP/SyncE、CPU 亲和性与 NUMA；
- 相同峰值/平均流量模型及 warm-up、采样窗口、重复次数；
- p50/p95/p99 slot latency、deadline miss、BLER、吞吐、功耗和各处理单元利用率；
- 独立 L1、独立 MAC 与完整 E2E 三套边界，禁止跨边界相除。

在这些条件满足之前，OAI/OCUDU 的对照应限制为架构、算法覆盖、代码可审计性和可复现实验能力，不应填入虚构的吞吐或时延排名。

## 6. 官方来源

- [Aerial CUDA-Accelerated RAN 当前版本与历次 What’s New](https://docs.nvidia.com/aerial/cuda-accelerated-ran/latest/index.html)
- [Aerial Supported Systems](https://docs.nvidia.com/aerial/cuda-accelerated-ran/latest/supported_systems.html)

页面当前显示文档版本 26.1，最后更新日期为 2026-06-15。CSV 中每条记录同时保留其数字首次出现或被明确列出的版本段落，防止把不同版本配置混为同一测试。
