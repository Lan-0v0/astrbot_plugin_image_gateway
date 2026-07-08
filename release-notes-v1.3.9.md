### **修复**
修复 AstrBot 配置面板中“工作流自定义节点条目”的卡片副标题在部分情况下显示为空的问题。现在即使前端某些渲染路径未完整保留 `display_item` 元数据，也会优先对工作流绑定条目回退组合显示 `display_name——workflow_id`，例如 `正向提示词——miaomiao改图`。

### **优化**
统一将前端展示分隔符处理为 `\u2014\u2014`，避免因源码编码或构建链路导致连接符异常；同时重新构建并同步 AstrBot dashboard 产物，确保这次修复真正作用到当前 Web 配置面板。

### **兼容性**
版本号提升至 `v1.3.9`
插件回归测试与 AstrBot dashboard 构建同步验证已完成

**安装/升级**：在 AstrBot 中执行插件更新，或手动下载最新 Release 包  
**反馈**：如果你有任何 优化/添加的 图像生成方面功能 的建议，都欢迎在 [Issues](https://github.com/Lan-0v0/astrbot_plugin_image_gateway/issues) 中提出❤

**Full Changelog**: https://github.com/Lan-0v0/astrbot_plugin_image_gateway/commits/v1.3.9
