### **修复**
修复消息伪造转发场景下的结果内容错误
现在生成完成后，不会再单独发送“生图成功/改图成功，用时X.X秒”并把“开始生成”提示合并转发；而是直接合并转发“生图成功/改图成功，用时X.X秒”和实际生成的图片

### **优化**
补充对应回归测试，覆盖消息伪造转发开启时的成功提示拼装逻辑
同步更新 README、CHANGELOG 与版本信息，明确启用消息伪造转发后的实际输出行为

### **兼容性**
版本号提升至 `v1.3.7`
回归测试与编译检查均已通过

**安装/升级**：在 AstrBot 中执行插件更新或手动下载最新 Release 包

**反馈**：如果你有任何 优化/添加的 图像生成方面功能 的建议，都欢迎在 [Issues](https://github.com/Lan-0v0/astrbot_plugin_image_gateway/issues) 中提出❤

**Full Changelog**: https://github.com/Lan-0v0/astrbot_plugin_image_gateway/commits/v1.3.7
