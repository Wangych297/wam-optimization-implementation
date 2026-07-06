# Papers And Ideas

## 主论文

### WAM: Watermark Anything with Localized Messages

- 角色：主论文和主工程代码。
- 使用方式：直接复用作者开源代码、官方参数和 MIT 权重。
- 我们改动：不改 WAM 模型结构，在外层改变嵌入区域、强度、攻击评测、消息编码和应用场景。

## 主创新来源

### DWSF

- 借鉴点：分散区域嵌入、面积比例 Q、块数量。
- 我们实现：把 WAM 的单区域水印扩展成多区域分散嵌入，并扫描 Q=10/20/25/30/50。
- 结论：Q=30% 是质量优先折中；Q=50% 是鲁棒优先模式。

### TrustMark

- 借鉴点：水印强度和视觉质量之间的可调权衡。
- 我们实现：扫描 WAM 的 `scaling_w`，并和 DWSF 区域策略组合。
- 结论：形成质量优先、均衡鲁棒、安全优先三档模式。

### Robust-Wide / FlexMark

- 借鉴点：真实编辑链路、平台压缩、WebP/JPEG、鲁棒-质量模式选择。
- 我们实现：对最终候选模式做 brightness/contrast/saturation/sharpness、JPEG、WebP、resize+JPEG 等实用变换评测。
- 结论：三档模式选择更合理，避免只给一个死参数。

## 附加安全应用来源

### EditGuard / OmniGuard

- 借鉴点：主动取证、篡改定位、局部完整性检测。
- 我们实现：通过水印检测概率下降定位局部篡改。
- 结论：覆盖区域内定位效果好，但不能定位未覆盖区域。

### TrustMark / WAM

- 借鉴点：re-watermarking、provenance update、多局部消息。
- 我们实现：空间分区追加第二条水印消息。
- 结论：非重叠分区能保留新旧两条消息，但牺牲 PSNR。

### MuST

- 借鉴点：多源合成图追踪、MER 重同步、素材 source ID。
- 我们实现：构造多源合成图，比较整图解码、素材框裁剪、MER resize 解码，并加入 ECC 和 codebook 匹配。
- 结论：无二次压缩时 MER 很有效；复杂三源压缩仍不稳定，适合作为附加分支。

## 探索和负结果来源

### MBRS / RoSteALS

- 借鉴点：JPEG 多分支、消息冗余、ECC。
- 我们实现：多分支 JPEG 解码、rep3/rep4、Hamming 和 codebook 识别。
- 结论：可作为辅助，不能单独当主创新。

### FIN / RAIMark

- 借鉴点：可逆噪声层、INR 分辨率无关。
- 我们判断：需要结构级训练，不适合在当前 WAM 官方权重上直接硬改。
