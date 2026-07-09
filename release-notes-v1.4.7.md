### **修复**
移除 ComfyUI 工作流模板的 `hide_hint_in_list` 设置，使模板介绍文案 `工作流 ID (workflow_id)输入框中输入的内容变量` 在条目列表中正常显示，与 OpenAI/Gemini 条目的展示方式完全一致。此前 `hide_hint_in_list: true` 将介绍文案隐藏，导致条目副标题缺少模板说明。

### **优化**
保留数组形式 `display_item: ["workflow_id"]`：数组只有一个元素时直接返回该值，不会出现 `——` 分隔符或 `label: value` 前缀。最终效果：条目副标题第一行显示 `workflow_id` 的实际内容（如 `文生图1`），第二行显示模板介绍文案 `工作流 ID (workflow_id)输入框中输入的内容变量`。
同步更新回归测试、README、CHANGELOG 与版本信息

### **兼容性**
版本号提升至 `v1.4.7`
回归测试已通过

**安装/升级**：在 AstrBot 中执行插件更新，或手动下载最新 Release 包

**反馈**：如果你有任何 优化/添加的 图像生成方面功能 的建议，都欢迎在 [Issues](https://github.com/Lan-0v0/astrbot_plugin_image_gateway/issues) 中提出❤

**Full Changelog**: https://github.com/Lan-0v0/astrbot_plugin_image_gateway/commits/v1.4.7
