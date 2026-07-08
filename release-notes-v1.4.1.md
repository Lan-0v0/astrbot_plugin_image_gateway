### **修复**
将“工作流自定义节点条目”的副标题显示逻辑收敛到插件端。插件现在会为每条 binding 自动生成并持久化 `display_summary`，配置面板会稳定显示 `display_name——workflow_id`，不再出现整块空白。

### **优化**
`_conf_schema.json` 直接使用 `display_summary` 作为显示字段，不再依赖 AstrBot dashboard 对本插件做特殊分支；同时补上对应回归测试，避免后续再出现同类显示回退问题。

### **兼容性**
版本号提升至 `v1.4.1`
插件回归测试（96 项）已通过

**安装/升级**：在 AstrBot 中执行插件更新，或手动下载最新 Release 包  
**反馈**：如果你有任何 优化/添加的 图像生成方面功能 的建议，都欢迎在 [Issues](https://github.com/Lan-0v0/astrbot_plugin_image_gateway/issues) 中提出❤

**Full Changelog**: https://github.com/Lan-0v0/astrbot_plugin_image_gateway/commits/v1.4.1
