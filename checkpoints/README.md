# WAM Checkpoints

本目录保存 WAM 官方参数和本地权重。

需要的本地权重文件：

```text
wam_mit.pth
```

当前本机已经有该文件，大小约 360MB。它被 `.gitignore` 忽略，不会提交到 GitHub。

默认读取路径：

```text
checkpoints/wam_mit.pth
checkpoints/params.json
```

如果换机器复现，需要自行下载或复制 `wam_mit.pth` 到本目录。
