# 05 篡改定位

## 目的

在主动破坏水印区域后，根据提取置信度下降定位疑似篡改位置，连接完整性保护和篡改检测任务。

## 实现位置

```text
watermark_anything/extensions/tamper_localization/localizer.py
```

## 输出目录

```text
results_output/tamper_localization
```

## 运行方式

```powershell
.\experiments\05_tamper_localization\run.ps1
```
