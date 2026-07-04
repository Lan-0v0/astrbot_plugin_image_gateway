# astrbot_plugin_image_gateway

AstrBot 多模型图像生成网关插件。统一接入 OpenAI Images API 与 Google Gemini 图像接口，支持多模型按优先级回退、失败重试、生成张数上限，以及指令与自然语言两种触发方式。

## 功能特性

- **多模型网关**：可同时配置多个 OpenAI / Gemini 模型，按优先级依次尝试
- **文生图 / 改图**：支持 `/生图` 与 `/改图` 指令
- **自然语言触发**：开启后 LLM 可通过函数工具 `image_gateway_generate` 触发生图（指令始终优先）
- **智能回退**：当前模型失败或达上限时，自动尝试下一优先级模型
- **可配置重试**：全局与单模型均可设置重试次数，失败时指数退避等待
- **张数上限控制**：可限制单次请求的最大生成张数，避免一次请求生成过多图片
- **审核力度可调**：OpenAI / Gemini 均支持将审核设为 `none`，并自动尝试多种降级策略
- **灵活发送**：若 AstrBot 配置了 `callback_api_base`，优先以 URL 发送图片；失败时回退本地文件

## 环境要求

- AstrBot `>=4.9.2,<5`（见 `metadata.yaml`）

## 安装

### 方式一：复制目录（推荐本地调试）

将整个插件文件夹复制到 AstrBot 的插件目录：

```
AstrBot/data/plugins/astrbot_plugin_image_gateway
```

然后在 AstrBot WebUI **插件管理** 中启用「图像网关」，并完成配置。

### 方式二：WebUI 仓库安装

在 AstrBot WebUI 插件管理中，使用本仓库 Git 地址安装（发布到 GitHub 后填写实际 URL）：

```
https://github.com/Lan-0v0/astrbot_plugin_image_gateway
```

## 依赖

插件额外依赖（AstrBot 安装插件时会自动处理 `requirements.txt`）：

| 包名 | 版本 |
|------|------|
| aiohttp | >=3.9.0 |
| aiofiles | >=23.0.0 |

## 配置说明

在 WebUI 插件配置页中修改。主要配置项如下。

### 全局设置

| 配置项 | 说明 | 默认值 |
|--------|------|--------|
| `enable_nl_trigger` | 启用自然语言触发。关闭后 LLM 工具无法生图，仅 `/生图`、`/改图` 可用 | `true` |
| `global_retry_count` | 全局默认重试次数。单模型未单独配置（`-1`）时使用 | `2` |
| `global_max_generation_count` | 全局默认单次请求最大生成张数上限。`-1` 表示不限制 | `2` |

### 模型列表（`models`）

在「图像生成模型列表」中添加 OpenAI 或 Gemini 模板，可配置多个实例。仅 **已启用** 的模型参与生成；按 **优先级（数值越大越优先）** 从高到低依次尝试。

每个模型常见字段：

| 字段 | 说明 |
|------|------|
| `display_name` | 显示名称，用于日志与错误提示 |
| `enabled` | 是否启用 |
| `priority` | 优先级，数值越大越先使用 |
| `url` | API 地址（OpenAI 如 `https://api.openai.com/v1`，Gemini 如 `https://generativelanguage.googleapis.com/v1beta`） |
| `apikey` | API Key |
| `model_name` | 模型 ID |
| `retry_count` | 重试次数，`-1` 表示使用全局默认 |
| `max_generation_count` | 该模型单次请求最大生成张数，`-1` 表示使用全局默认；超出后提示「超出生成张数上限」并尝试下一模型 |
| `quality` / `size` | 画质与尺寸（默认画质为 `high`，部分网关可能忽略） |
| `moderation` | 内容审核 / 安全过滤等级（见下文） |
| `seed` | 随机种子，留空表示随机（部分模型不支持） |

### 生图开始提示（`generation_start_message`）

用于控制在真正开始生成前发送的提示语，位置在「图像生成模型列表」后方。支持两种模式：

- **固定语句**：默认模式；只提供一组预设文案，发送时随机选取一条
- **LLM**：可选择 AstrBot 中已配置的模型提供商，或沿用默认提供商；同时可切换使用当前人设或自定义人设提示词

配置项如下：

| 配置项 | 说明 | 默认值 |
|--------|------|--------|
| `mode` | 提示语模式。`fixed` 为固定语句，`llm` 为 LLM 生成 | `fixed` |
| `fixed_messages` | 固定语句列表。固定语句模式下随机发送 | `['开始生成']` |
| `llm_provider_id` | LLM 提示语使用的提供商；留空则跟随当前默认配置 | `''` |
| `llm_persona_source` | LLM 提示语使用的人设来源。`current` 为当前人设，`custom` 为自定义人设提示词 | `current` |
| `llm_custom_persona_prompt` | 自定义人设提示词，仅在 `llm_persona_source=custom` 时生效 | `根据现在的情景，以适宜的性格言语，简单表述要开始生成图片了，不分段不加格式不使用emoji，10字以内。` |

### 审核力度（`moderation`）

**OpenAI** 可选：`none` / `low` / `high` / `auto`

- 设为 **`none`** 时，插件会依次尝试：不传 `moderation` 参数 → `low` → `auto`，以兼容不同网关对「关闭审核」的实现方式。
- 设为 **`high`** 时，会以更严格的审核等级请求上游接口。

**Gemini** 可选：`none` / `low` / `high` / `default`

- 设为 **`none`** 时，插件会依次尝试 `BLOCK_NONE`、`OFF`、`BLOCK_ONLY_HIGH` 等多种安全设置，失败后继续降级。
- 设为 **`high`** 时，会使用 `BLOCK_MEDIUM_AND_ABOVE` 作为更严格的安全过滤等级。

> 降低审核等级可能违反上游服务条款，请自行评估风险；部分网关仍可能强制过滤内容。

### 多模型与回退逻辑

1. 筛选已启用模型，按 `priority` 降序排列  
2. 对每个模型：检查本次请求张数是否超出 `max_generation_count`  
3. 未超限时按 `retry_count` 重试（间隔约 2^n 秒，上限 10 秒）  
4. 当前模型全部失败后，自动尝试下一优先级模型  
5. 所有模型均失败时，返回最后一次错误摘要；仅当所有候选模型都因额度上限被跳过时，才统一返回「超出生成张数上限」

## 使用说明

### `/生图` — 文字生图

```
/生图 {提示词}
/生图 {提示词} {张数}
```

- 提示词必填  
- 张数为可选末尾整数，默认为 `1`  
- 也支持 AstrBot 参数形式：`/生图 提示词:xxx  count:2`

**示例：**

```
/生图 牢大和张雪峰比谁跑的快，电影感
/生图 原神启动 2
```

### `/改图` — 图片改图

```
/改图 {提示词}
```

- 需在**同一条消息**中附带图片，或**引用**含图片的消息  
- 改图使用收集到的**第一张**图片作为输入  
- 提示词必填

**示例：**

```
（附带一张人像照片）
/改图 把脸P上黑曼巴，笑容四溢
```

### 自然语言触发

当 `enable_nl_trigger` 为 `true` 时，绑定了 LLM 的会话中，模型可调用工具 `image_gateway_generate`：

- `prompt`：提示词  
- `mode`：`text_to_image`（默认）或 `image_to_image`  
- `count`：文生图张数（改图模式忽略）

改图模式同样需要在消息中附带或引用图片。关闭 `enable_nl_trigger` 后，工具调用会提示使用 `/生图` 或 `/改图`。

## 输出行为

1. 生成开始时会先发送一条开始提示：固定语句模式下随机发送一条预设文案；LLM 模式下由所选提供商根据人设生成
2. 生成成功后，先发送一条文本：`生图成功，用时X.X秒` 或 `改图成功，用时X.X秒`
2. 随后发送图片：
   - **单张**：优先直接发送图片消息；若直接发送失败，再回退到结果管道发送
   - **多张**：优先发送合并转发节点；若失败，则按 `图片 1/N` 的顺序逐张发送，并继续做多级回退
3. 生成结束后会自动撤回前面发送的开始提示；如果平台不支持撤回，插件会自动忽略该步骤
4. 图片保存在插件数据目录 `data/plugin_data/astrbot_plugin_image_gateway/images/`（由 AstrBot 运行时管理，无需手动创建）
5. 若 AstrBot 主配置中设置了 `callback_api_base`，会尝试将图片转为可访问 URL 发送；转换失败则回退为本地文件发送

## 注意事项

- 请妥善保管各模型的 `apikey`，勿将含密钥的配置文件提交到公开仓库  
- 不同 API 网关对 `moderation`、`size`、`seed` 等字段支持程度不同，失败时可查看 AstrBot 日志  
- OpenAI 适配器在标准 Images API 失败时，会尝试通过 `chat/completions` 兼容部分第三方网关  
- Gemini 原生接口可能忽略 `size` 等字段，以实际网关行为为准  
- `max_generation_count` 控制的是**单次请求张数上限**，不是历史累计总量  
- 改图仅使用第一张输入图；如需多图参考，请自行在提示词中描述或等待后续版本支持  
- 生成耗时受上游 API 影响，单次请求超时约 180 秒  

## 项目结构

```
astrbot_plugin_image_gateway/
├── main.py              # 插件入口与指令注册
├── metadata.yaml        # 插件元数据
├── _conf_schema.json    # WebUI 配置 schema
├── requirements.txt     # Python 依赖
├── adapters/            # OpenAI / Gemini 适配器
├── services/            # 生成调度与计数
└── utils/               # 消息解析与图片存储
```

## 许可证

[MIT License](./LICENSE)
