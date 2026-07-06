# 02 空间冗余

## 目标

本实验把水印从“整图一次嵌入”扩展为“多个空间区域协同嵌入”。这样做是为了解决局部裁剪、局部遮挡、局部替换时整图水印容易失效的问题。

## 创新设计

空间冗余的核心思想是：不要把全部认证能力压在单一区域或单次提取上，而是把同一条或相关的水印消息分散到多个位置。只要部分区域在攻击后仍然保留，就仍然有机会恢复出有效消息。

本实验包含三层改动：

- 冗余区域嵌入：在多个图像块中重复或分布式嵌入水印，提高对局部破坏的容忍度。
- 覆盖率搜索：比较不同覆盖面积和区域数量，找到画质、鲁棒性和计算量之间的平衡点。
- 区域同步：攻击后图像可能发生裁剪或缩放，因此需要重新定位可用区域，再进行提取和汇总。

## 工程实现

本组实验拆成多个可独立运行的模块：

- `redundant_regions.py`：测试多区域冗余嵌入。
- `distributed_layout.py`：测试分布式空间布局。
- `coverage_search.py`：搜索覆盖率和区域数量。
- `region_sync.py`：测试攻击后的区域重新同步。

这些模块的输出可以组合使用：先用覆盖率搜索确定候选区域配置，再用冗余区域和区域同步验证在攻击下的恢复稳定性。

## 结果解读

重点关注三个问题：

- 覆盖率增加后，提取恢复率是否明显提升。
- 区域数量增加后，是否出现画质下降或收益变小。
- 在裁剪和局部移除攻击下，多区域方案是否比基础整图方案更稳定。

## 实现位置

```text
watermark_anything/extensions/spatial_redundancy/redundant_regions.py
watermark_anything/extensions/spatial_redundancy/distributed_layout.py
watermark_anything/extensions/spatial_redundancy/coverage_search.py
watermark_anything/extensions/spatial_redundancy/region_sync.py
```

## 输出目录

```text
results_output/redundant_regions
results_output/distributed_layout
results_output/coverage_search
results_output/region_sync
```

## 运行方式

```powershell
.\experiments\02_spatial_redundancy\run.ps1
```
