# 源码与文档版本基线

**冻结日期：** 2026-07-20

## 冻结结果

| 项目 | 当前入口 | 分支/版本 | 固定 commit | 获取方式 |
|---|---|---|---|---|
| NVIDIA Aerial CUDA-Accelerated RAN | `NVIDIA/aerial-cuda-accelerated-ran` | `main` | `29f5870fd84b0176df48b40667c1b8f1740e6d09` | GitHub connector |
| Duranta/OpenAirInterface | `duranta-project/openairinterface5g` | `develop` | `31ffb21a8204ae9706a88eb08606a80fc8eafb3e` | GitHub connector |
| OCUDU | `gitlab.com/ocudu/ocudu` | `v26.04` 后的 `main` | `6d44c2a5e5b2a81a4c67460b460ef99e789943cf` | GitLab API/Web |
| O-RAN SC O-DU High | `o-ran-sc/o-du-l2` | `master` | `04feb1fd9f815d4a87fb502a961cdbfa5209c7f4` | GitHub connector |
| O-RAN SC O-DU Low | `o-ran-sc/o-du-phy` | `master` | `6ef1d2b70db585e351b9cd35c6054c1b249a7465` | GitHub connector |

## 项目迁移关系

OpenAirInterface RAN 的当前主线位于 `duranta-project/openairinterface5g`。原 `OPENAIRINTERFACE/openairinterface5g` 是只读镜像，研究中的 OAI 源码引用一律使用 Duranta 仓库和上述固定 commit。

srsRAN Project 自 2025 年 12 月起迁移到 OCUDU。原 `srsran/srsRAN_Project` 已停止维护；研究中的 CPU gNB/CU/DU 对照一律使用 OCUDU。首个 OCUDU 公共版本为 `v26.04`，当前冻结 commit 包含此版本后的公开修改。

## 本地可用性限制

终端分别以普通 clone、授权 clone 和浅 clone 尝试访问 GitHub/GitLab，均因当前终端网络路径不可用而失败。GitHub 插件安装后，四个 GitHub 项目的元数据和固定 commit 已通过 connector 获取；OCUDU commit 通过 GitLab API 获取。

因此本基线是**远程 commit 冻结**，不是完整本地对象快照：

- `third_party/` 当前没有可用工作树。
- Aerial Git LFS 测试向量和大对象尚未下载。
- 后续源码证据必须通过 connector/API 按固定 commit 读取，并记录实际文件和符号。
- 需要构建、全仓搜索或执行 benchmark 时，仍须恢复终端网络、提供源码包，或在具备仓库访问的 Linux 环境执行。

这一限制不会改变文档与源码证据等级规则：通过固定 commit 获取的明确文件和符号可达到 E2；没有本地执行不能达到 E4。

