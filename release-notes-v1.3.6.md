### **修复**
修复工作流与模型混合调度时，真实执行错误会被后续“当前工作流暂不支持文生图/改图”提示覆盖的问题
现在当 `/生图` 命中的文生图工作流因节点 ID 或字段路径配置错误而失败时，会优先返回真正的执行错误，便于直接排查

### **优化**
精简 ComfyUI 工作流配置面板：移除冗余的 `display_name` 输入项，直接使用 `workflow_id` 作为工作流显示名称
同步调整 ComfyUI 工作流介绍、`workflow_id` 提示与“自定义节点条目”的显示名称提示文案
同步更新 README、CHANGELOG 与回归测试，补齐工作流报错优先级和显示名称逻辑说明

### **兼容性**
版本号提升至 `v1.3.6`
回归测试（94项）与编译检查均已通过

**安装/升级**：在 AstrBot 中执行插件更新或手动下载最新 Release 包

**反馈**：如果你有任何 优化/添加的 图像生成方面功能 的建议，都欢迎在 [Issues](https://github.com/Lan-0v0/astrbot_plugin_image_gateway/issues) 中提出❤

**Full Changelog**: https://github.com/Lan-0v0/astrbot_plugin_image_gateway/commits/v1.3.6
