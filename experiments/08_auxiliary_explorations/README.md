# 08 Auxiliary Explorations

## 做什么

保存辅助探索和负结果，不作为主创新吹，但能证明我们筛选过方向。

## 包含内容

- MBRS 式多分支 JPEG 解码
- ECC 消息冗余和编码变体
- 自适应区域选择
- bbox 同步解码

## 对应实现

```text
src/wam_optimization/wam_mbrs_multibranch_decode.py
src/wam_optimization/wam_payload_ecc_eval.py
src/wam_optimization/wam_payload_ecc_variants.py
src/wam_optimization/wam_adaptive_region_select.py
src/wam_optimization/wam_dwsf_bbox_sync_decode.py
```

## 运行

```powershell
.\experiments\08_auxiliary_explorations\run.ps1
```
