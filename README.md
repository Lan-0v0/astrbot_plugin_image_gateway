# astrbot_plugin_image_gateway

AstrBot 多模型图像生成网关插件。统一接入 OpenAI Images API 与 Google Gemini 图像接口，支持多模型按优先级回退、失败重试、生成张数上限，以及指令与自然语言两种触发方式。

## 功能特性

- **多模型网关**：可同时配置多个 OpenAI / Gemini 模型，按优先级依次尝试
- **工作流（Workflow）支持**：可配置 ComfyUI 文生图工作流，与模型统一参与优先级调度
- **文生图 / 改图**：支持 `/生图` 与 `/改图` 指令
- **自然语言触发**：开启后 LLM 可通过函数工具 `image_gateway_generate` 触发生图（指令始终优先）
- **智能回退**：当前模型/工作流失败或达上限时，自动尝试下一优先级目标
- **可配置重试**：全局与单模型/单工作流均可设置重试次数，失败时指数退避等待
- **张数上限控制**：可限制单次请求的最大生成张数，避免一次请求生成过多图片
- **审核力度可调**：OpenAI / Gemini 均支持将审核设为 `none`，并自动尝试多种降级策略
- **可配置发送链路**：全局与单条目均可指定消息发送优先方式，降低复杂插件环境下的干扰
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
| `send_strategy` | 该模型的发送链路，默认 `follow_global`（见下文「发送链路」） |

### 工作流（Workflow）列表（`workflows`）

在「图像生成模型列表」和「生图开始提示」之间新增了「工作流（Workflow）列表」，用于接入 ComfyUI 文生图工作流。工作流条目与模型条目**统一参与同一套优先级调度**：按 `priority` 降序与模型混合排列，一起做重试与回退。

> **当前版本范围**：工作流仅支持**文生图**（ComfyUI），暂不支持改图；`/改图` 请求会自动跳过工作流条目，仅使用已配置的模型。

每个工作流条目字段：

| 字段 | 说明 |
|------|------|
| `display_name` | 显示名称 |
| `enabled` | 是否启用 |
| `priority` | 优先级，与模型列表共用同一套顺序 |
| `retry_count` | 重试次数，`-1` 表示使用全局默认 |
| `max_generation_count` | 单次请求最大生成张数，`-1` 表示使用全局默认 |
| `workflow_type` | 工作流类型，当前仅支持 `comfyui` |
| `runtime_base_url_override` | 覆盖 ComfyUI 地址；留空则使用全局默认 |
| `runtime_api_key_override` | 覆盖 ComfyUI 鉴权 Token；留空则使用全局默认 |
| `workflow_content` | **必须**是从 ComfyUI 点击“导出（API 格式）”得到的完整 JSON |
| `workflow_variable_bindings` | 节点绑定列表（见下文） |
| `send_strategy` | 该工作流的发送链路，默认 `follow_global` |

#### 节点绑定（`workflow_variable_bindings`）

每条绑定通过 **“节点 ID + 字段路径”** 精确定位 `workflow_content` 中的某个字段，并用配置值覆盖该字段原有内容；最终合并后的 workflow 才会被提交执行。

| 字段 | 说明 |
|------|------|
| `node_id` | 对应 `workflow_content` 中该节点的 Key（例如 ComfyUI 导出 JSON 里的 `"6"`） |
| `field_path` | 点路径，例如 `inputs.text` 或 `inputs.texts.0`（支持列表下标） |
| `binding_type` | 绑定类型（见下表） |
| `custom_value` | 部分绑定类型需要填写的自定义值 |

`binding_type` 支持：

| 类型 | 说明 |
|------|------|
| `prompt_positive` | 使用当前 `/生图` 提示词覆盖该字段 |
| `prompt_negative` | 使用 `custom_value` 填写的反向提示词覆盖该字段 |
| `image_input` | 使用输入图片覆盖该字段（当前版本文生图请求下会跳过，不生效） |
| `seed` | 使用 `custom_value` 中的整数作为种子；留空则每次随机生成 |
| `custom_text` | 使用 `custom_value` 中的文本覆盖该字段 |
| `custom_number` | 使用 `custom_value` 中的数字覆盖该字段；含小数点按浮点数处理，否则按整数处理，**不会**被转换为字符串 |

**示例**：将节点 `6` 的 `inputs.text` 绑定为正向提示词：

```json
{
  "node_id": "6",
  "field_path": "inputs.text",
  "binding_type": "prompt_positive"
}
```

### ComfyUI 运行环境（全局默认，`workflow_runtime_default`）

供未在工作流条目中单独覆盖运行环境的条目使用：

| 字段 | 说明 | 默认值 |
|------|------|--------|
| `base_url` | ComfyUI 地址 | `http://127.0.0.1:8188` |
| `api_key` | 鉴权 Token，部分部署无需鉴权可留空 | `''` |
| `poll_interval_seconds` | 查询任务状态的轮询间隔（秒） | `1.0` |
| `timeout_seconds` | 任务超时时间（秒） | `180` |

### 生图开始提示（`generation_start_message`）

用于控制在真正开始生成前是否发送提示语，位置在「图像生成模型列表」后方。关闭后不会发送任何开始提示，相关附属配置项也会在配置面板中隐藏。开启后支持两种模式：

- **固定语句**：默认模式；只提供一组预设文案，发送时随机选取一条
- **LLM**：可选择 AstrBot 中已配置的模型提供商，或沿用默认提供商；同时可切换使用当前人设或自定义人设提示词

配置项如下：

| 配置项 | 说明 | 默认值 |
|--------|------|--------|
| `enabled` | 是否启用开始提示发送 | `true` |
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

1. 筛选已启用的模型与工作流条目，按 `priority` 降序统一排列  
2. 对每个目标：检查本次请求张数是否超出 `max_generation_count`  
3. 若为工作流条目且当前是改图请求，直接跳过该目标  
4. 未超限时按 `retry_count` 重试（间隔约 2^n 秒，上限 10 秒）  
5. 当前目标全部失败后，自动尝试下一优先级目标  
6. 所有目标均失败时，返回最后一次错误摘要；仅当所有候选目标都因额度上限被跳过时，才统一返回「超出生成张数上限」

### 发送链路（`send_strategy`）

用于控制生成结果（成功文本、开始提示、图片）的发送优先方式，位于配置面板**最底部**，即「生图开始提示」下方。该配置**极少需要调整**，默认的「直连优先」已能覆盖绝大多数场景。

> **注意**：当生图/改图成功、但发送图片失败时，可尝试更改此项。

可选值：

| 值 | 说明 |
|------|------|
| `direct_first` | 默认。优先直接发送（`event.send` → `context.send_message` → 平台客户端），仅在都失败时才回退到结果管道 |
| `event_send_first` | 只尝试 `event.send` |
| `context_send_first` | 只尝试 `context.send_message` |
| `platform_client_first` | 只尝试平台客户端直接调用 |
| `result_pipeline_only` | 不做任何主动发送，直接走 AstrBot 结果管道（等价于回退到早期版本行为） |

每个模型 / 工作流条目都可以单独设置 `send_strategy`；默认值为 `follow_global`，表示跟随本节的全局配置。

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

1. 若启用了开始提示功能，生成开始时会先发送一条开始提示：固定语句模式下随机发送一条预设文案；LLM 模式下由所选提供商根据人设生成
2. 生成成功后，先发送一条文本：`生图成功，用时X.X秒` 或 `改图成功，用时X.X秒`
2. 随后发送图片：
   - **单张**：优先直接发送图片消息；若直接发送失败，再回退到结果管道发送
   - **多张**：优先发送合并转发节点；若失败，则按 `图片 1/N` 的顺序逐张发送，并继续做多级回退
3. 若开始提示消息成功获取到消息 ID，生成结束后会自动撤回该提示；如果平台不支持撤回或无法取得消息 ID，插件会自动忽略该步骤
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
- 工作流 `workflow_content` 必须是 ComfyUI 的 **API 格式导出**，普通工作流导出格式无法直接使用  
- 工作流当前版本仅支持文生图，`image_input` 绑定类型在文生图请求下会被跳过  

## 项目结构

```
astrbot_plugin_image_gateway/
├── main.py              # 插件入口、指令注册与消息发送链路
├── metadata.yaml        # 插件元数据
├── _conf_schema.json    # WebUI 配置 schema
├── requirements.txt     # Python 依赖
├── CHANGELOG.md         # 版本更新日志
├── adapters/            # OpenAI / Gemini 适配器
├── services/            # 生成调度、发送策略、Workflow 配置与执行
│   ├── generation.py        # 统一调度模型与工作流条目
│   ├── send_strategy.py      # 发送链路枚举与解析
│   ├── workflow_config.py    # Workflow / 节点绑定配置模型
│   ├── workflow_merge.py     # node_id + field_path 覆盖逻辑
│   └── workflow_runner.py    # ComfyUI 提交与轮询执行器
└── utils/               # 消息解析、图片存储、点路径工具
```

## 许可证

[MIT License](./LICENSE)
