# OAI / OCUDU NR gNB CPU 基准协议

## 1. 当前状态

本协议定义的是未来可重复执行的 CPU 基线，不包含本机实测结果。2026-07-21 的桌面预检结果如下：

| 检查项 | 结果 | 影响 |
|---|---|---|
| 操作系统 | Windows；存在 `wsl.exe`，但未安装 Linux 发行版 | 无法构建或运行两个项目要求的 Linux 实时环境 |
| 冻结源码本地副本 | `third_party/` 为空；配置中 `local_checkout: false` | 不能在当前工作区执行构建 |
| Linux 构建链 | 本机未发现 `cmake`、`ninja`、`gcc`、`make` | 不能做原生构建；也不应以 Windows 编译结果替代 Linux gNB 结果 |
| 射频/GPU/NIC | 未提供 | 本协议首轮 CPU dummy/test mode 不要求 GPU 或物理 RU，但 7.2 E2E 不可执行 |
| 结果文件 | [`results.csv`](../../../data/performance/normalized/results.csv) 仅有表头 | 明确表示零条 measured 记录，禁止填充示例数字 |

因此，本阶段结论是“环境阻塞”，不是“测试失败”，也不是两个项目的性能结论。最短解阻路径是准备一台 Ubuntu 22.04+ 裸机或受控 Linux 主机，记录硬件清单后检出冻结 commit，再执行本文命令。

## 2. 比较边界

首轮基线固定为：

- NR FR1、100 MHz、30 kHz SCS、TDD、单小区、4T4R；
- 从 1 UE、1 layer 起，按 `UE -> layer -> cell` 顺序逐级增加负载；
- 每个配置预热 30 秒、采集 120 秒、独立重复 5 次；
- 同时记录 p50、p95、p99、p99.9 slot/处理链时延、deadline miss、吞吐、BLER、CPU 利用率、RSS、NUMA 和调度迁移；
- OAI 和 OCUDU 必须使用同一台主机、同一 governor、同一 CPU affinity、同一 TDD pattern、MCS/CQI/RI 及同一测试边界。

首轮比较边界定义为 `distributed_unit_dummy_radio`：不经过物理 RU，不把 DPDK/NIC/前传差异混入 CPU PHY/MAC 基线。第二轮才使用 RU emulator/7.2 前传，测试边界必须改为 `distributed_unit_oran_72`，不得与首轮落入同一 comparison group。

## 3. 冻结版本

| 项目 | 固定 commit | 用途 |
|---|---|---|
| Duranta/OpenAirInterface | `31ffb21a8204ae9706a88eb08606a80fc8eafb3e` | `nr-softmodem` gNB、`--phy-test` 或 RF simulator 路径 |
| OCUDU | `6d44c2a5e5b2a81a4c67460b460ef99e789943cf` (`v26.04`) | gNB `ru_dummy` / `test_mode`，以及后续 RU emulator |

只有 commit 完全匹配才能写入标准结果表。重新检出更新版本时必须生成新记录，不能覆盖旧结果。

## 4. 统一主机准备

在 Linux 主机执行并保存输出；不要直接把这些命令的输出当作性能数据：

```bash
mkdir -p data/performance/raw/environment
uname -a | tee data/performance/raw/environment/uname.txt
lscpu --extended | tee data/performance/raw/environment/lscpu.txt
numactl --hardware | tee data/performance/raw/environment/numa.txt
cat /sys/devices/system/cpu/cpu0/cpufreq/scaling_governor | tee data/performance/raw/environment/governor.txt
free -h | tee data/performance/raw/environment/memory.txt
ip -details link | tee data/performance/raw/environment/network.txt
```

还必须记录 BIOS/SMT、内核启动参数、isolcpus/nohz_full/rcu_nocbs、容器运行时（若使用）、编译器、CMake、FFT 库、NIC 固件和电源测量方法。任何一项变化都生成新的 `hardware_id` 或环境清单哈希。

## 5. OAI 可运行路径

官方 gNB 运行文档给出的入口是 `cmake_targets/ran_build/build/nr-softmodem`，`--phy-test` 可在无随机接入情况下生成负载；O-RAN 7.2 文档还明确说明无 RU 时可用 `--phy-test` 生成人工流量。首轮建议从 RF simulator/PHY test 边界开始：

```bash
git clone https://github.com/duranta-project/openairinterface5g.git third_party/oai
cd third_party/oai
git checkout 31ffb21a8204ae9706a88eb08606a80fc8eafb3e
test "$(git rev-parse HEAD)" = "31ffb21a8204ae9706a88eb08606a80fc8eafb3e"
cd cmake_targets
./build_oai -I --gNB -w SIMU
cd ran_build/build
sudo ./nr-softmodem -O <frozen-100MHz-4T4R-config> --phy-test --thread-pool <fixed-cpu-list>
```

成功标志：进程进入 gNB slot 处理、持续输出预期 PHY/MAC 计数，120 秒窗口内无异常退出；采集到的配置回显与 100 MHz/30 kHz/4T4R 完全一致。若该冻结版本的 `build_oai --help` 不接受上述 RF 选项，以该 commit 的 `doc/BUILD.md` 为准，并把实际完整命令写入原始日志，禁止静默更换构建模式。

第二轮 OAI 7.2 可运行性预检使用官方文档中的 `OAI_FHI72` 构建选项和 `nr-softmodem --phy-test`，但必须另外准备 xRAN/DPDK、CPU 隔离、hugepages 和 NUMA 绑定；它不属于首轮 CPU dummy-radio comparison group。

## 6. OCUDU 可运行路径

OCUDU 官方安装文档要求 Linux 实时内核环境、CMake/C++17 及 SCTP、YAML、mbedTLS 和 FFT 依赖。官方 load-testing 文档提供 `ru_dummy`、`test_mode` 和 RU emulator 三层边界。首轮使用 `ru_dummy + test_mode`：

```bash
git clone https://gitlab.com/ocudu/ocudu.git third_party/ocudu
cd third_party/ocudu
git checkout 6d44c2a5e5b2a81a4c67460b460ef99e789943cf
test "$(git rev-parse HEAD)" = "6d44c2a5e5b2a81a4c67460b460ef99e789943cf"
cmake -S . -B build -DCMAKE_BUILD_TYPE=Release -DBUILD_TESTING=ON
cmake --build build -j "$(nproc)"
ctest --test-dir build --output-on-failure
sudo ./build/apps/gnb/gnb -c <frozen-100MHz-4T4R-base.yml> -c <ru-dummy.yml> -c <testmode.yml>
```

成功标志：启动日志显示固定 commit、100 MHz 和预期天线配置；统计表连续输出，DL/UL `nok` 和 BLER 口径可采集。`ru_dummy` 排除了 OFH 网络，所以该结果不能用于声称 OCUDU 的 7.2 前传性能。

第二轮使用官方 RU emulator：单独构建 `apps/examples/ofh`，启动 `ru_emulator` 后再运行 gNB。成功标志包括 on-time 计数持续增加，且无 late/early/error 包。该轮必须记录 NIC、压缩方式、BDF、PTP 和 DPDK 参数。

## 7. 采集与统计

每个项目、每个配置按如下顺序执行：

1. 固定 CPU governor、NUMA、IRQ、线程 affinity 和内存页设置；
2. 保存 commit、配置文件、启动命令和环境清单的 SHA-256；
3. 启动进程，等待 30 秒预热；
4. 采集 120 秒：应用日志、`pidstat -u -r -w -p <pid> 1`、`perf stat`、RSS/NUMA、吞吐与 BLER；
5. 停止并保存 exit status；清空临时状态后重复，共 5 次；
6. 从每次独立运行先计算时延分位数，再汇总五次的中位数和范围，不把所有样本混成一次伪重复；
7. deadline miss 同时保存次数和分母，deadline 本身必须写入原始元数据。

若项目日志没有直接给出 slot latency，不得用吞吐反推时延。需要通过已有 tracepoint 或最小侵入式时间戳采集；任何插桩都记录补丁 commit，并在两个项目中使用等价边界。

## 8. 归一化数据契约

[`normalize_benchmarks.py`](../../../scripts/normalize_benchmarks.py) 接受字典记录，验证以下字段非空：软件版本、硬件、NR 配置、天线/层/UE/负载、测试边界、时延统计量、重复/预热/时长及原始来源。它只做：

- 时延归一为 `latency_us`；
- 吞吐归一为 `throughput_mbps`；
- 根据全部比较上下文生成稳定的 `comparison_group`；
- 原样保留 `raw_source` 和输入字段。

它不做峰值/平均值转换，不估算缺失时延，不把 4T4R 与 64T64R、dummy RU 与 7.2、p99 与 mean 合并。输入缺字段或单位未知时直接拒绝整批记录。

## 9. 下一条可执行命令

当前 Windows 主机不满足执行条件。获得 Linux 主机后，第一条命令不是运行 benchmark，而是检出两个冻结 commit 并完成环境清单；随后分别运行 OAI `build_oai --help` 和 OCUDU CMake configure，保存完整输出。只有两边都能按同一 100 MHz/30 kHz/4T4R 边界运行后，才启动 5 x 120 秒采集。

## 10. 官方参考

- [OAI 5G gNB 运行与 `--phy-test`](https://github.com/OPENAIRINTERFACE/openairinterface5g/blob/develop/doc/RUNMODEM.md)
- [OAI O-RAN 7.2 无 RU 人工流量说明](https://github.com/OPENAIRINTERFACE/openairinterface5g/blob/develop/doc/ORAN_FHI7.2_Tutorial.md)
- [OCUDU 安装与构建](https://docs.ocudu.org/user_manual/installation/)
- [OCUDU gNB/DU load testing、ru_dummy 与 test_mode](https://docs.ocudu.org/tutorials/testmode/)
