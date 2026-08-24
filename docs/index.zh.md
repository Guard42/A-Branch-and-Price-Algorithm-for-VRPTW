# bpvrptw 中文说明

> 英文版主文档见 [README.md](../README.md)；本页是面向中文读者的完整导读。

## 这是什么

`bpvrptw` 是一个用 Python 编写的**精确求解器**，求解带时间窗的车辆路径
问题（VRPTW），核心算法是 **分支定价（Branch-and-Price）**：

- **列生成**：主问题只保留一部分"列"（可行路线），通过求解带资源约束
  的最短路子问题（ESPPRC），不断找出检验数为负的新路线加入主问题；
- **分支定界**：若 LP 松弛解出现分数边，就在该边上分支（禁止 / 强制），
  直到上下界之差小于容差，得到**可证明最优**的方案。

本仓库的前身是对 Java 项目 [dengfaheng/BPVRPTW](https://github.com/dengfaheng/BPVRPTW)
的 AI 移植。重写时把旧实现按字节原样封存在
[`legacy/`](../legacy/README.md)，并整理出 D1–D9 缺陷清单——新实现里的
每一个关键设计都能对应到其中一条教训，非常适合作为运筹优化的学习材料。

## 安装

```bash
git clone https://github.com/Guard42/A-Branch-and-Price-Algorithm-for-VRPTW
cd A-Branch-and-Price-Algorithm-for-VRPTW
pip install -e ".[dev,plot]"     # 开发全套；Gurobi 可选：.[gurobi]
```

默认 LP 后端是开源的 HiGHS（`highspy`），**无需任何许可证**即可运行全部
功能与测试；装了 Gurobi 的环境可以通过 `lp_solver="gurobi"` 切换后端，
两者经过同一套对偶符号约定测试。

## 快速上手

命令行：

```bash
python -m bpvrptw check dataset/C101_25.txt      # 校验算例文件
python -m bpvrptw solve dataset/C101_25.txt --time-limit 300 --output-json result.json
python -m bpvrptw bench dataset --time-limit 45 --json bench.json   # 批量跑分
```

Python API：

```python
import bpvrptw

instance = bpvrptw.VRPTWInstance.from_solomon("dataset/C101_25.txt")
solution = bpvrptw.solve(instance, time_limit_seconds=300)
print(solution.status, solution.total_cost, solution.lower_bound)
for route in solution.routes:
    print(route.path, route.cost)
```

`Solution.status` 取值：

- `SOLVED_OPTIMAL` —— 已证明最优（上下界 Gap ≤ 容差，附带下界证书）；
- `TIME_LIMIT` —— 预算内未证完，返回当前最好可行解与已知下界；
- 其余状态见 `bpvrptw.SolutionStatus`。

## 算法原理（速览）

1. **主问题**是集合划分 LP：每条可行路线一个变量 y_p，每个客户的覆盖
   约束 ≥ 1；
2. **定价子问题**：用对偶值 π 改写弧成本 `d_ij − π_i`，在 ESPPRC 上搜索
   检验数为负的路线。实现为 best-first 标签算法：
   - 标签 = (城市， 检验数， 到达时刻， 载荷， 已访问集合位掩码)；
   - **支配规则**：同城标签中，访问集合是其子集且三项资源都不差者胜；
   - Feillet 式剪枝：从 j 出发已不可达的客户直接标记为已访问（注意：
     分支禁弧会破坏这一论证的安全性，代码里会自动关闭剪枝）；
3. **分支**：选最接近 0.5 的分数边，两个子节点分别禁止 / 强制该弧；
   强制指向终点仓库的弧**不会**封死其余路线回仓（这是 legacy 移植错误
   D3 的修复点）；
4. 全局下界由 son0/toplevel 记账法维护；只有**完全收敛**的列生成才允许
   贡献下界，杜绝"假 Gap = 0"。

完整推导见 [algorithm.md](algorithm.md)。

## 基准表现

数据集内多数文件是从 Solomon 100 客户截取的 25 客户版本。45 s + 300 s
两级实测（详见 [benchmarks.md](benchmarks.md)）：

- C 族 25 客户全部最优：191.7 / 215.6 / 215.4；
- R101 最优 618.10（0.04 s）、RC107 最优 299.10（约 2–3 s）；
- 历史"挂死"算例 c104 现在在预算内干净终止并给出可行解；
- 1000 客户的 C110_1 属研究级规模，超出教学实现的定位，结果如实标注
  为 time limit。

## 与旧版（legacy）的差异

| 编号 | 旧版行为 | 新版 |
|---|---|---|
| D1/D9 | 按插入序处理/挑选标签与列 | best-first + 最负列优先 |
| D2 | 死代码比较器（未定义名 A/B） | 无比较器，确定性堆键 |
| D3 | 向仓库强制边会封死其他路线回仓 | 终点仓库语义有单测锁定 |
| D4 | 每轮整体重建 Gurobi 模型 | 同一模型增量加列，保留热启动 |
| D5 | 分支权重用顶点 id 索引路线表 | Ryan-Foster 式分数度评分 |
| D6 | print 满天飞、异常吞掉 | logging + 类型化异常 |
| D7 | 硬编码绝对路径 | 全仓库无硬编码 |
| D8 | c104 无限挂起 | 标签数/墙钟双上限，优雅降级 |

## 给学习者的话

读懂这套代码的推荐顺序：`instance.py` → `labeling.py`（配合
`tests/test_labeling.py` 的暴力对拍）→ `column_generation.py` →
`branch_and_price.py`（配合 `tests/exact.py` 的精确枚举）。遇到看不懂的
设计，先去 `legacy/README.md` 找对应缺陷编号——每一个"为什么"都写在
那里。想继续深入到科研级实现，可以研究 RouteOpt 与通用 BPC 框架
（ng-route、对偶稳定化、更强的分支策略）。
