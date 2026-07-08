### **修复**
重修 AstrBot 配置面板中“工作流自定义节点条目”的副标题显示逻辑。现在当旧条目缺失 `__template_key`、或前端临时拿不到模板元数据时，会优先按条目自身的 `display_name——workflow_id` 直接组合显示，例如 `正向提示词——miaomiao改图`，不再出现整块空白。

### **优化**
为单模板列表补上模板键自动推断兜底，避免旧配置进入配置面板后因模板键缺失而无法正确显示或补默认值；同时重新构建并同步 AstrBot dashboard 的前端产物到实际生效目录，确保这次修复真正落到当前 Web 配置面板。

### **兼容性**
版本号提升至 `v1.3.10`
插件回归测试与 AstrBot dashboard 构建同步验证已完成

**安装/升级**：在 AstrBot 中执行插件更新，或手动下载最新 Release 包  
**反馈**：如果你有任何 优化/添加的 图像生成方面功能 的建议，都欢迎在 [Issues](https://github.com/Lan-0v0/astrbot_plugin_image_gateway/issues) 中提出❤

**Full Changelog**: https://github.com/Lan-0v0/astrbot_plugin_image_gateway/commits/v1.3.10
