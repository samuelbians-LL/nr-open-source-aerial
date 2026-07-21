# NVIDIA Aerial NR gNB 实机验证协议

## 1. 目的与当前限制

本协议把现有 E1–E3 文档/源码结论升级为 E4 本地实测证据，范围仅限 NR gNB。当前工作区没有 GH200、BlueField-3、兼容 RU/NIC 或 PTP/SyncE 环境，因此本文是待执行协议，不包含任何 Aerial 本地性能结果。

机器可读矩阵位于 [`config/aerial-test-matrix.yaml`](../../../config/aerial-test-matrix.yaml)。现场执行者必须按矩阵顺序运行，不得临时选择带宽、负载、统计量或测试边界。某个 A/B 路径在冻结源码中不存在时，结果写为 `blocked_not_supported`，不能现场设计新实现后继续比较。

## 2. 固定基线

| 项目 | 固定值 |
|---|---|
| Aerial 源码 | commit `29f5870fd84b0176df48b40667c1b8f1740e6d09` |
| 官方文档/容器 | 26.1 / `26-1` |
| 首选 DU 平台 | GH200：Grace CPU + H100，2 x BlueField-3 |
| RU 端 | 独立受支持服务器、兼容 NIC、物理直连或同一受控前传网络 |
| NR 默认配置 | 100 MHz、30 kHz、TDD `dddsuudddd` |
| 默认测量 | 30 秒预热、120 秒采集、5 次独立重复 |
| slot deadline | 500 µs；同时记录具体 channel/FH window deadline |
| 原始数据根目录 | `data/performance/raw/aerial/`（不提交 Git） |

源码 commit、容器 digest、驱动/CUDA/DOCA/DPDK/NIC 固件任一变化，都必须创建新的实验批次；不得覆盖旧日志。

## 3. 硬件和软件验收

### 3.1 必须具备

- GH200/BF3 或矩阵明示的受支持替代平台；GPU、NIC 和容器版本匹配 Aerial 26.1 software manifest；
- DU/RU 双节点 E2E 需要物理前传连接、hugepages、CPU/IRQ 隔离、PTP；设备支持时同时启用 SyncE；
- Aerial test vectors 与 launch patterns 已生成并校验；Git LFS 对象完整；
- `nvidia-smi`、MPS、Docker/NVIDIA Container Runtime、Nsight Systems、Nsight Compute 可用；
- 独立系统功耗计量不可用时，系统功耗字段保持空并降级结论，不能拿 GPU board power 代替整机功耗。

### 3.2 首次开机清单

在 host 和 container 分别执行，并保存完整输出：

```bash
nvidia-smi -L
nvidia-smi -q
nvidia-smi --query-gpu=uuid,name,driver_version,vbios_version,pci.bus_id,memory.total,persistence_mode,ecc.mode.current,clocks.max.sm,power.limit --format=csv
sudo lshw -c network -businfo
sudo ethtool -i <du_fh_interface>
sudo devlink dev info
uname -a
lscpu --extended
numactl --hardware
cat /proc/cmdline
docker version
docker inspect <cubb_container>
git -C "$cuBB_SDK" rev-parse HEAD
git -C "$cuBB_SDK" submodule status --recursive
```

验收必须确认：

1. 源码 HEAD 等于冻结 commit；
2. 容器版本为 26-1，并额外记录不可变 image digest；
3. GPU 无 pending retired pages、ECC 异常或 throttling reason；
4. PTP 服务 active，PHC2SYS RMS 满足 NVIDIA 当前文档要求，测试全程保持锁定；
5. YAML 中 CPU affinity 与 BIOS SMT、内核隔离设置一致；
6. DU 与 RU 的 NIC 固件、MTU、VLAN、MAC、BDF 和 PTP 角色均已记录。

任一项失败即停止，批次状态写为 `environment_rejected`。

## 4. 目录和文件命名

每个最小实验单元使用如下不可变路径：

```text
data/performance/raw/aerial/
  <YYYYMMDDTHHMMSSZ>_<case-id>/
    manifest.json
    machine_inventory.json
    software_manifest.json
    checksums.sha256
    <variant-key>/
      rep-01/
        test_config.yaml
        launch_command.txt
        application.log
        metrics.csv
        exit_status.txt
        nvidia-smi-dmon.csv
        nsys-rep01.nsys-rep        # 仅分析性复跑
      rep-02/ ... rep-05/
```

`variant-key` 必须由矩阵因素按键名排序生成，例如：

```text
cells=8__graph_mode=true__mps=enabled
```

执行完成后，在批次根目录运行：

```bash
find . -type f ! -name checksums.sha256 -print0 | sort -z | xargs -0 sha256sum > checksums.sha256
```

任何后续清洗输出写入 `data/performance/normalized/`，不得修改原始目录。

## 5. 通用执行规则

1. 固定 GPU clocks、persistence mode、CPU governor、NUMA、IRQ、MPS SM 配额；把实际值写入 manifest。
2. A/B 变体按 `A-B-B-A-A-B` 的确定性顺序轮换；每个 variant 只取前 5 次验收成功运行，失败运行保留但不替换原因不明的数据。
3. 每次运行前检查温度和 clocks；温度未回到首轮基线 ±3°C 时等待，不改变测试顺序。
4. 预热阶段不计入统计；采集窗口开始/结束必须在应用、GPU 和系统采集日志中使用同一 UTC 标记。
5. 每次运行独立重启被测进程，清空应用状态但不删除日志；MIG/MPS 变体按矩阵显式重建。
6. 先验证功能正确性，再记录性能。TB/IQ/FAPI 输出不一致的运行不得作为时延/吞吐样本。
7. profiler 会扰动实时行为：常规 5 次运行不附加 Nsight；同配置另做一次标记为 `analysis_only` 的 profiler 复跑，不能混入性能汇总。

## 6. 构建、测试向量和 E2E 启动

进入官方容器后：

```bash
cd /opt/nvidia/cuBB
export cuBB_SDK=$(pwd)
test "$(git rev-parse HEAD)" = "29f5870fd84b0176df48b40667c1b8f1740e6d09"
${cuBB_SDK}/testBenches/phase4_test_scripts/build_aerial_sdk.sh --preset perf --dry-run | tee build-dry-run.log
${cuBB_SDK}/testBenches/phase4_test_scripts/build_aerial_sdk.sh --preset perf | tee build.log
```

测试向量必须在构建前准备，保存生成工具版本、输入表、launch pattern 和输出文件 checksum。不得用一个配置的 test vector 运行另一个 MCS/层数/天线配置。

E2E 使用官方参数解析与三进程顺序：

```bash
cd ${cuBB_SDK}/testBenches/phase4_test_scripts
./parse_test_config_params.sh "<matrix-test-pattern>" "<recorded-platform-profile>" test_params.sh
source test_params.sh
${cuBB_SDK}/testBenches/phase4_test_scripts/copy_test_files.sh $COPY_TEST_FILES_PARAMS
${cuBB_SDK}/testBenches/phase4_test_scripts/build_aerial_sdk.sh $BUILD_AERIAL_PARAMS
${cuBB_SDK}/testBenches/phase4_test_scripts/setup1_DU.sh $SETUP1_DU_PARAMS
# RU 节点执行 setup2_RU.sh；两端随后执行 test_config.sh。
```

启动顺序固定为 RU Emulator → cuPHYController → TestMAC：

```bash
# RU node
${cuBB_SDK}/testBenches/phase4_test_scripts/run1_RU.sh $RUN1_RU_PARAMS
# DU node, session 1
${cuBB_SDK}/testBenches/phase4_test_scripts/run2_cuPHYcontroller.sh $RUN2_CUPHYCONTROLLER_PARAMS
# DU node, session 2
source test_params.sh
${cuBB_SDK}/testBenches/phase4_test_scripts/run3_testMAC.sh $RUN3_TESTMAC_PARAMS
```

所有由 `test_params.sh` 展开的变量必须写入 `launch_command.txt`；不能只保存含环境变量的短命令。

## 7. 测试矩阵执行说明

### 7.1 cuPHY Graph/stream 与 cell scaling

`AER-CUPHY-GRAPH-001` 使用官方 standalone `cubb_gpu_test_bench`/`measure.py`。相同 test vectors、MPS 配额、频率和 cell 数下，仅改变 `--graph` 是否存在：

```bash
python3 measure.py \
  --cuphy <testBenches>/build \
  --vectors <test_vectors> \
  --config <frozen_testcase_json> \
  --uc <frozen_usecase_json> \
  --gpu <gpu_id> --freq <locked_frequency> \
  --start <cell_count> --cap <cell_count> \
  --iterations 1 --slots <fixed_slot_count> \
  <all-fixed-channel-options> [--graph]
```

先用 `--test` 输出生成的 YAML 和命令，核对后保存。Graph 与 stream 各 cell 数分别运行 5 次。报告成对差值及置信区间，不把 1-cell 与 20-cell 互相比较为“加速比”。

`AER-CUPHY-MMIMO-002` 只使用支持的 64T64R test vectors，分别执行 early-HARQ 16DL/4UL 和非 early-HARQ 16DL/8UL，不跨配置合并。

### 7.2 cuMAC CPU reference/GPU

`AER-CUMAC-4TR-003` 与 `AER-CUMAC-MMIMO-004` 必须使用冻结仓库中同一 standalone testbench 的 CPU reference 和 CUDA 路径，输入随机种子固定为 `20260721`。每次运行保存输入 checksum、选择 UE、PRB/层分配、目标函数和结果差异。

若 CPU reference 不覆盖 GPU 的某个联合搜索空间，不能缩减 GPU 问题后宣称等价，也不能把不同目标函数的耗时相除。应分别报告：

- 完全等价子问题的执行差异；
- GPU 独有联合优化的搜索规模与绝对耗时；
- 无 CPU 等价实现的功能扩展。

### 7.3 GPUDirect A/B

`AER-GDR-AB-006` 的 A 路径是冻结版本默认的注册 GPU memory/NIC DMA 数据路径。B 路径必须是运行前已经审查、固定 commit 的 host-staging patch，保持相同 eCPRI 包、IQ、压缩和 FAPI 输出，只增加 NIC↔host↔GPU copy。

当前研究尚未确认冻结仓库存在官方 host-staging 开关。因此获得硬件后首先做静态预检：

```bash
git grep -n -E 'GDR|GPUDirect|host.*staging|cudaHostRegister|cudaMemcpy' -- cuPHY-CP
```

若没有可验证的等价路径或预先审查的 patch，B 路径记为 `blocked_not_supported`，本测试不产生 GDR 加速倍数。禁止现场通过减小 payload、关闭压缩或更换 RU Emulator 来伪造对照。

### 7.4 MPS 与 MIG

`AER-MPS-AB-007` 在 full GPU 上比较 MPS 开/关；测试向量和 Graph 模式固定。MPS 启用时，SM 配额来自冻结 `cuphycontroller` YAML，不能自动调优后只保留最好结果。

`AER-MIG-AB-008` 比较 full GPU 与固定 `MIG 4g.48gb`。按 NVIDIA 文档执行：

```bash
sudo nvidia-smi -i 0 -mig 1
sudo nvidia-smi mig -cgi 5 -C
nvidia-smi -L
```

记录实际 MIG UUID并传给容器；所有 `mps_sm_*` 不得超过该 profile 的 64 SM。`fixed_cuda_burn_25_percent` co-tenant 使用预先固定镜像/digest、kernel、block/grid 和 duty cycle；若该负载工件未在运行前冻结，整个 co-tenant 因素记为 `blocked_missing_fixture`。

### 7.5 尾时延和故障

`AER-TAIL-009` 预热 300 秒、采集 1800 秒、重复 3 次，只用于稳定性和尾部行为，不与 120 秒容量运行合并。报告 p99.9、maximum、deadline miss、温度、频率和 PTP lock。

`AER-FAULT-010` 在第 60 秒注入矩阵固定故障，并观察恢复 60 秒。每个故障独立启动新运行；禁止一次运行叠加多个故障。若 RU Emulator/交换机不支持精确注入，则该故障记为 `blocked_not_supported`。成功不要求“零丢包”，而要求无进程崩溃、无静默数据损坏、能观察到文档规定的错误指示和恢复行为。

## 8. 性能与诊断采集

### 8.1 无 profiler 的正式运行

```bash
nvidia-smi dmon -s pucvmet -d 1 -o DT -f nvidia-smi-dmon.csv &
GPU_DMON_PID=$!
<expanded_test_command> > application.log 2>&1
TEST_STATUS=$?
kill "$GPU_DMON_PID"
printf '%s\n' "$TEST_STATUS" > exit_status.txt
```

同时采集 OAM、TestMAC、RU Emulator 的 throughput、slot、CRC、early/late packet 和 FAPI error 指标。采样器启动/停止 UTC 时间写入日志。

### 8.2 Nsight Systems 分析性复跑

```bash
nsys profile \
  --trace=cuda,nvtx,osrt \
  --sample=cpu \
  --cpuctxsw=process-tree \
  --force-overwrite=true \
  --output=analysis_nsys \
  <expanded_test_command>
```

使用 `nsys stats` 导出 CUDA API、GPU kernel、memcpy 和 NVTX 汇总。该运行标记为 `analysis_only=true`。

### 8.3 Nsight Compute

`ncu` 仅用于 standalone、单 channel/单 cell 的代表性 kernel，不用于实时 E2E 容量数字：

```bash
ncu --set full --target-processes all --force-overwrite \
  --export analysis_ncu <single-channel-command>
```

记录 kernel 名、occupancy、memory throughput、warp stall、tensor/FP/INT 指令和 launch 配置。不要把 `ncu` 下的时延写入正式 performance CSV。

## 9. 统计方法

- 每次独立运行先计算 p50/p95/p99/p99.9/max，再对 5 次运行报告中位数、最小值和最大值；
- A/B 使用同 cell/UE/test-vector 的配对差值；额外提供 10,000 次 bootstrap 95% CI，随机种子固定 `20260721`；
- deadline miss 同时报告 `miss_count / eligible_slots`，分母缺失则拒绝；
- 吞吐必须同时报告 BLER/CRC、层数和有效 measurement duration；
- 功耗报告 GPU board power 和系统功耗两个独立字段，不相互替代；
- 任何被排除运行都保留原始数据、理由和预先定义规则，不能观察结果后改变剔除标准。

## 10. E4 验收门槛

一条记录只有同时满足以下条件才能标为 `measured_fact` / E4：

1. 硬件清单、源码/子模块 commit、容器 digest、驱动/CUDA/DOCA/NIC 固件齐全；
2. NR 配置、test vectors、启动命令、CPU/GPU/NIC/MPS/MIG 配置齐全；
3. 原始日志、metrics 和全部文件 checksum 齐全；
4. 达到矩阵要求的成功重复次数；功能输出先验收通过；
5. 无 thermal throttling、未解释 clock drift、PTP unlock 或临场配置修改；
6. 测试边界与 comparison group 完全一致；
7. 数值可由原始日志重新生成，归一化脚本不填补缺失字段。

任何缺项只能保持 E3 方法证据或 `blocked_*` 状态。

## 11. 桌面演练结论

在无硬件工作区进行的桌面演练确认：

- 所有 10 个测试 case 都有固定 runner、NR profile、因素、指标和成功条件；
- 执行顺序已固定为 standalone PHY → cuMAC → MPS/MIG → E2E → GDR → 长稳 → 故障；
- Graph/stream、CPU/CUDA、GDR/host-staging、MPS、MIG 均是显式 A/B，不能用不同负载替代；
- host-staging、co-tenant 和故障注入工件缺失时均有确定的阻塞状态；
- 不存在必须由现场研究者选择的统计窗口、重复次数、deadline 或比较分组参数。

实际 test pattern 文件名、GPU UUID、NIC BDF/IP/MAC 属于机器生成的环境值，必须由官方脚本探测并写入 manifest，而不是在本文中伪造。

## 12. 官方依据

- [Aerial 26.1 Supported Systems](https://docs.nvidia.com/aerial/cuda-accelerated-ran/latest/supported_systems.html)
- [Running Aerial cuPHY：standalone、多小区、MPS 与 `--graph`](https://docs.nvidia.com/aerial/cuda-accelerated-ran/latest/quickstart_guide/running_cuphy_sdk.html)
- [Running cuBB End-to-End：TestMAC、cuPHYController、RU Emulator](https://docs.nvidia.com/aerial/cuda-accelerated-ran/latest/quickstart_guide/running_cubb-end-to-end.html)
- [Running cuBB Performance tests](https://docs.nvidia.com/aerial/cuda-accelerated-ran/latest/quickstart_guide/running_cubb-end-to-end-perf.html)
- [E2E gNodeB on MIG](https://docs.nvidia.com/aerial/cuda-accelerated-ran/latest/quickstart_guide/e2e_gnb_mig.html)
- [Aerial OAM Operation](https://docs.nvidia.com/aerial/cuda-accelerated-ran/latest/cubb/oam_guide/oam_operation.html)
