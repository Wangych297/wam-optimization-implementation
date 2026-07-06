# 集成关系

```text
watermark_anything/  -> 模型包和扩展模块
assets/              -> 示例图片和 mask
configs/             -> 模型配置
checkpoints/         -> 参数和本地权重
notebooks/           -> 推理辅助工具
train.py             -> 训练入口
requirements.txt     -> 依赖清单
```

课程扩展模块位于：

```text
watermark_anything/extensions/
```

统一运行入口使用仓库根目录作为 `ProjectRoot`。
