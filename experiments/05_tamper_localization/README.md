# 05 Tamper Localization

## 做什么

把水印从“证明来源”扩展成“辅助定位哪里被改过”。通过水印检测概率下降估计局部篡改区域。

## 论文来源

- EditGuard
- OmniGuard
- DWSF
- WAM

## 对应实现

```text
src/wam_optimization/wam_tamper_localization_eval.py
```

## 输出

```text
结果输出/wam_tamper_localization
实验记录/主动篡改定位_v1.md
```

## 运行

```powershell
.\experiments\05_tamper_localization\run.ps1
```
