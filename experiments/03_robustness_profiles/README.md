# 03 鲁棒性配置

## 目标

本实验把水印嵌入强度从固定参数改成可评估、可选择的安全档位。真实使用中并不存在一个永远最优的强度：强度低时图像质量更好，但攻击后更容易失败；强度高时恢复能力更强，但可能带来更明显的视觉变化。

## 创新设计

本模块的创新点是把水印强度和空间策略一起做成配置曲线，而不是只给出单个默认参数。实验会在多组强度下生成水印图并进行攻击评测，再把恢复率和画质指标放在同一张结果表里比较。

在此基础上，可以得到几种面向应用的模式：

- 质量优先：适合视觉质量要求更高、攻击强度较低的场景。
- 均衡鲁棒：适合常规发布和一般压缩传播。
- 安全优先：适合可能遭遇强压缩、二次分发或局部破坏的场景。

## 工程实现

`strength_search.py` 负责单独搜索嵌入强度，观察不同强度下的指标变化。

`spatial_strength_profile.py` 把空间区域和嵌入强度组合起来，验证“多区域 + 合适强度”是否比单纯提高强度更稳定。这样可以避免为了提升鲁棒性而盲目加大整图扰动。

## 结果解读

重点看强度提升带来的恢复率增益是否值得。如果某个强度之后恢复率提升很小，但画质损失继续增加，就说明它不适合作为默认配置。最终应优先选择能在画质和鲁棒性之间形成稳定折中的档位。

## 实现位置

```text
watermark_anything/extensions/robustness_profiles/strength_search.py
watermark_anything/extensions/robustness_profiles/spatial_strength_profile.py
```

## 输出目录

```text
results_output/strength_search
results_output/spatial_strength_profile
```

## 运行方式

```powershell
.\experiments\03_robustness_profiles\run.ps1
```
