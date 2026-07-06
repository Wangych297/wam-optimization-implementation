# Original Paper Code

本目录保存原论文代码副本。当前已经复制进项目的是：

```text
Watermark-Anything/
```

它对应 WAM 原论文：

```text
Watermark Anything with Localized Messages, ICLR 2025
```

我们的实验代码不会重写 WAM 模型结构，而是在运行时导入这里的原工程代码、读取官方参数和权重，然后在外层实现区域选择、攻击评测、消息冗余、溯源等改进逻辑。

大权重文件不进入 git。请查看：

```text
Watermark-Anything/checkpoints/README.md
```

