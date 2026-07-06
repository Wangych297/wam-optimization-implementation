# WAM Checkpoints

本目录需要放置 WAM 官方权重：

```text
wam_mit.pth
```

当前本机已经有该文件，大小约 360MB。它被 `.gitignore` 忽略，不会提交到 GitHub。

运行实验时默认读取：

```text
original_code/Watermark-Anything/checkpoints/wam_mit.pth
original_code/Watermark-Anything/checkpoints/params.json
```

如果换机器复现，需要自行下载或复制 `wam_mit.pth` 到本目录。
