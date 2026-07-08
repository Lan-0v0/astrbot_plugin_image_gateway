### **修复**
修复 AstrBot 配置面板中“工作流自定义节点条目”的卡片副标题显示逻辑。现在当条目同时填写 `display_name` 和 `workflow_id` 时，会按 `display_name——workflow_id` 的形式组合展示，例如 `正向提示词——miaomiao改图`，方便直接看出这条绑定规则属于哪个工作流。

### **优化**
恢复 `display_name` 输入项自身原本的提示文案，避免误把字段说明替换成固定句子；同时补充对应的 schema 回归测试，并同步更新 README、CHANGELOG 与版本信息。

### **兼容性**
版本号提升至 `v1.3.8`
插件回归测试与 AstrBot dashboard 构建验证均已通过

**安装/升级**：在 AstrBot 中执行插件更新，或手动下载最新 Release 包
**反馈**：如果你有任何 优化/添加的 图像生成方面功能 的建议，都欢迎在 [Issues](https://github.com/Lan-0v0/astrbot_plugin_image_gateway/issues) 中提出❤

**Full Changelog**: https://github.com/Lan-0v0/astrbot_plugin_image_gateway/commits/v1.3.8
