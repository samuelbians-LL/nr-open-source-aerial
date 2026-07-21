# Aerial 与开源 NR 基站比较研究

本目录承载 NVIDIA Aerial、Duranta/OpenAirInterface 与 OCUDU 的 NR 基站比较成果，O-RAN SC O-DU 仅作为组件级参照。

## 研究边界

- 只分析 gNB、CU/DU、L1/L2、FAPI、O-RAN 7.2 前传、实时执行和直接相关的验证工具。
- 不分析 UE、5GC、RIC/xApp 或纯仿真器的独立功能。
- 不把 NVIDIA 官方性能声明当作本研究的独立实测结果。

## 证据原则

所有结论使用唯一 `claim_id`，并按照 `config/evidence-schema.yaml` 标记 E0–E4。关键技术结论至少达到 E2，即定位到固定 commit 的源码文件和符号。性能数据必须符合 `config/metric-rules.yaml`；不同测试边界或不同 NR 配置不得直接排名。

## 目录职责

- `architecture/`：项目架构、统一功能映射和时序图。
- `dossiers/`：PUSCH、PDSCH、信道编码、大规模 MIMO、cuMAC 和前传实时性源码档案。
- `protocols/`：CPU 基线和未来 Aerial 实机验证协议。
- `reports/`：总体报告、CUDA 差异化专题和场景决策矩阵。

原始文档、日志和性能数据保存在 `data/`；外部仓库固定在 `third_party/` 且不纳入本仓库提交。

## 主要交付物

- [`reports/aerial-vs-open-ran-gnb.md`](reports/aerial-vs-open-ran-gnb.md)：14 章总体比较报告。
- [`reports/aerial-cuda-differentiation.md`](reports/aerial-cuda-differentiation.md)：CUDA、数据路径、算法重构与反事实专题。
- [`reports/scenario-decision-matrix.md`](reports/scenario-decision-matrix.md)：四类 NR gNB 场景的独立权重与选型建议。
- [`reports/aerial-performance-claims-audit.md`](reports/aerial-performance-claims-audit.md)：NVIDIA 性能声明字段审计。
- [`protocols/cpu-baseline.md`](protocols/cpu-baseline.md)：OAI/OCUDU 可重复 CPU 基准协议。
- [`protocols/aerial-hardware-validation.md`](protocols/aerial-hardware-validation.md)：未来 Aerial 实机验证协议。
