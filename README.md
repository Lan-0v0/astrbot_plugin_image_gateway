# <img width="256" height="256" alt="logo" src="https://github.com/user-attachments/assets/b4232e6b-96eb-433f-86ad-8cd66bc23f8c" />astrbot\_plugin\_image\_gateway





AstrBot 多模型图像生成网关插件。支持 OpenAI Images API、Google Gemini 图像接口与 ComfyUI Workflow，可自定义 baseURL、模型名称、工作流 ID、优先级、重试次数及审核力度。支持文生图、图生图两种模式，支持自然语言。

## 功能特性

* **多模型网关**：可同时配置多个 OpenAI / Gemini 模型，按优先级依次尝试
* **工作流（Workflow）支持**：可配置 ComfyUI 工作流，与模型统一参与优先级调度，并支持单工作流双入口
* **文生图 / 改图**：支持 `/生图` 与 `/改图` 指令
* **自然语言触发**：开启后 LLM 可通过函数工具 `image\_gateway\_generate` 触发生图（指令始终优先）
* **智能回退**：当前模型/工作流失败或达上限时，自动尝试下一优先级目标
* **可配置重试**：全局与单模型/单工作流均可设置重试次数，失败时指数退避等待
* **张数上限控制**：可限制单次请求的最大生成张数，避免一次请求生成过多图片
* **审核力度可调**：OpenAI / Gemini 均支持将审核设为 `none`，并自动尝试多种降级策略
* **可配置发送链路**：全局与单条目均可指定消息发送优先方式，降低复杂插件环境下的干扰
* **消息伪造转发**：支持按全局或单条目配置，在生成完成后将开始提示与图片合并转发，并可伪装为 Bot、自身请求者或自定义 QQ 号
* **灵活发送**：若 AstrBot 配置了 `callback\_api\_base`，优先以 URL 发送图片；失败时回退本地文件

## 先看这里：ComfyUI 同时支持文生图和图生图

这一部分是给第一次接触本插件工作流功能的用户看的。如果你想让 **同一个 ComfyUI 工作流** 同时支持：

* `/生图`：只有提示词，没有输入图片
* `/改图`：有提示词，也有输入图片

那么请直接按下面做，不需要先理解插件源码。

### 一句话原理

插件不会强迫你在 ComfyUI 画布里把两套入口都永久接好，而是会在 **真正执行时** 根据当前模式，动态改写导出的 API JSON：

* `/生图` 时，让采样器读取“空 latent / 文生图入口”
* `/改图` 时，让采样器读取“`LoadImage -> VAEEncode` 的 latent 输出”
* 如果你还配置了 `denoise` 的模式切换，插件也会跟着一起切换

所以你在 ComfyUI 里看到某些线像是“断开的”，并不一定代表插件不能用；只要 JSON 里有可切换的目标节点，AstrBot 就能在运行时改写。

### 你需要准备什么

你至少需要有这几样东西：

1. 一个从 ComfyUI 导出的 **API 格式** JSON
2. 一条文生图入口
3. 一条图生图入口：
`LoadImage -> VAEEncode -> 采样器 latent\_image`
4. AstrBot 配置面板里的一个工作流条目
5. AstrBot 配置面板里的若干“自定义节点条目”

### 最推荐的设计：单工作流双入口

推荐把同一套提示词、采样器、放大、保存图像等主体流程共用，只把“进入采样器前的 latent 来源”做成两套：

* 文生图入口：空 latent，例如 `EmptyLatentImage`
* 图生图入口：`LoadImage -> VAEEncode`

然后让 `KSampler.inputs.latent\_image` 在两者之间切换。

通常还建议一起切换 `denoise`：

* 文生图：`1.0`
* 图生图：例如 `0.45`

这样一套 workflow 就能覆盖两种模式，而不需要复制两份大工作流。

### `supported\_modes` 应该怎么选

如果你不确定该选哪一项，可以直接按下面判断：

|面板选项|适合什么工作流|会响应什么请求|
|-|-|-|
|`仅文生图`|只有提示词入口，没有输入图片分支的普通文生图 workflow|只响应 `/生图`|
|`文生图 + 改图`|按“单工作流双入口”设计，既有文生图入口，也有 `LoadImage -> VAEEncode` 图生图入口，并通过 `mode\_switch\_\*` 切换|同时响应 `/生图` 与 `/改图`|
|`仅改图`|专门给 `/改图` 用的 workflow，本身不打算处理纯提示词文生图|只响应 `/改图`|

你也可以把它简单理解成：

* 只会文生图，就选 `仅文生图`
* 一套 workflow 两种都做，就选 `文生图 + 改图`
* 只会改图，就选 `仅改图`

### 在 AstrBot 面板里怎么配

#### 第 1 步：新增工作流条目

在 `workflows` 里新增一个 ComfyUI 工作流，并确认：

* 直接新增 `ComfyUI` 工作流模板条目
* `workflow\_content` 填的是 **ComfyUI 导出的 API 格式 JSON**
* `supported\_modes` 设为 `both`
* `workflow\_id` 自己起一个稳定、不重复的值

如果你这里选择的是：

* `仅文生图`：这个工作流只会参与 `/生图`
* `文生图 + 改图`：这个工作流会同时参与 `/生图` 与 `/改图`
* `仅改图`：这个工作流只会参与 `/改图`

#### 第 2 步：绑定正向提示词

把 workflow 里负责接收正向提示词的节点字段，绑定为 `prompt\_positive`。

例如：

```json
{
  "workflow\_id": "dual\_entry\_demo",
  "node\_id": "85",
  "field\_path": "inputs.text",
  "binding\_type": "prompt\_positive"
}
```

如果你的 workflow 有多个正向提示词节点，就分别绑定多条。

#### 第 3 步：绑定输入图片

把 `LoadImage` 节点的图片字段，绑定为 `image\_input`。

例如：

```json
{
  "workflow\_id": "dual\_entry\_demo",
  "node\_id": "222",
  "field\_path": "inputs.image",
  "binding\_type": "image\_input"
}
```

插件在 `/改图` 时会自动先把图片上传到 ComfyUI，再把上传后的文件名写到这里。

#### 第 4 步：配置模式切换

这一步是关键。你需要把“同一个字段在文生图和图生图下取不同值”的地方，改成 `mode\_switch\_\*` 类型。

三种模式切换类型含义如下：

* `mode\_switch\_text`：切换成不同文本
* `mode\_switch\_number`：切换成不同数字
* `mode\_switch\_json`：切换成不同 JSON 值，例如节点引用数组 `\["225", 0]`

最常见的是下面两条：

1. 切换 `KSampler.inputs.latent\_image`
2. 切换 `KSampler.inputs.denoise`

示例：

```json
{
  "workflow\_id": "dual\_entry\_demo",
  "node\_id": "206",
  "field\_path": "inputs.latent\_image",
  "binding\_type": "mode\_switch\_json",
  "text\_to\_image\_value": "\[\\"23\\", 0]",
  "image\_to\_image\_value": "\[\\"225\\", 0]"
}
```

```json
{
  "workflow\_id": "dual\_entry\_demo",
  "node\_id": "206",
  "field\_path": "inputs.denoise",
  "binding\_type": "mode\_switch\_number",
  "text\_to\_image\_value": "1.0",
  "image\_to\_image\_value": "0.45"
}
```

上面的意思分别是：

* `/生图` 时，`latent\_image` 指向节点 `23` 的输出
* `/改图` 时，`latent\_image` 指向节点 `225` 的输出
* `/生图` 时，`denoise=1.0`
* `/改图` 时，`denoise=0.45`

### 如果你使用本地导出的示例 JSON

如果你手头有按“单工作流双入口”思路整理过的本地工作流 JSON，例如 `ComfyUI图生图+文生图.json`，典型绑定如下。请注意：这类工作流文件可能包含你的本地节点、模型路径、提示词模板或其它私有配置，**不要提交到公开仓库**。

1. `85.inputs.text` -> `prompt\_positive`
2. `213.inputs.text` -> `prompt\_positive`
3. `222.inputs.image` -> `image\_input`
4. `206.inputs.latent\_image` -> `mode\_switch\_json`
5. `206.inputs.denoise` -> `mode\_switch\_number`

对应的模式切换值建议为：

* `206.inputs.latent\_image`

  * `text\_to\_image\_value`：`\["23", 0]`
  * `image\_to\_image\_value`：`\["225", 0]`
* `206.inputs.denoise`

  * `text\_to\_image\_value`：`1.0`
  * `image\_to\_image\_value`：`0.45`

### 在 ComfyUI 里制作工作流时要特别注意什么

1. 必须导出 **API 格式** JSON，普通工作流导出不能直接用。
2. `LoadImage` 节点要真实存在，因为 `/改图` 时插件要把上传后的文件名写进去。
3. `VAEEncode` 节点要真实存在，因为图生图入口最终要给采样器提供 latent。
4. 文生图入口和图生图入口都要能独立说得通，不要依赖手工临时改线。
5. 需要切换的字段，尽量集中在少数几个地方，最常见就是 `latent\_image` 和 `denoise`。
6. 如果某个节点值在两种模式下完全一样，就不要做模式切换，直接普通绑定或保留原值即可。

### 为什么 `VAEEncode` 看起来像“没接上”也能用

很多人会在 ComfyUI 画布里看到：`LoadImage -> VAEEncode` 这条支路没有直接接到当前采样器，于是以为图生图一定不会生效。其实这里的关键不在于“画布当前显示接没接上”，而在于：

* 你的导出 JSON 里有没有这个节点
* 采样器的目标字段能不能被 AstrBot 在运行时改写到这个节点输出

只要 `mode\_switch\_json` 最终把 `KSampler.inputs.latent\_image` 改成了 `\["225", 0]` 这种节点引用，图生图入口就会在执行时生效。

### 最后做一个快速自检

如果你配完后仍然不生效，可以按这个顺序检查：

1. `workflow\_content` 是否真的是 API 格式 JSON
2. `supported\_modes` 是否选成了符合你工作流实际结构的模式
3. `workflow\_id` 是否和所有绑定条目完全一致
4. `node\_id` 与 `field\_path` 是否准确对应导出 JSON
5. `/改图` 时是否真的带上了图片，或引用了含图片的消息
6. `mode\_switch\_json` 填的是不是合法 JSON，而不是普通字符串
7. `LoadImage`、`VAEEncode`、`KSampler` 这些关键节点在导出 JSON 中是否都存在

## 环境要求

* AstrBot `>=4.9.2,<5`（见 `metadata.yaml`）

## 安装

### 方式一：复制目录（推荐本地调试）

将整个插件文件夹复制到 AstrBot 的插件目录：

```
AstrBot/data/plugins/astrbot\_plugin\_image\_gateway
```

然后在 AstrBot WebUI **插件管理** 中启用「图像网关」，并完成配置。

### 方式二：WebUI 仓库安装

在 AstrBot WebUI 插件管理中，使用本仓库 Git 地址安装（发布到 GitHub 后填写实际 URL）：

```
https://github.com/Lan-0v0/astrbot\_plugin\_image\_gateway
```

## 依赖

插件额外依赖（AstrBot 安装插件时会自动处理 `requirements.txt`）：

|包名|版本|
|-|-|
|aiohttp|>=3.9.0|
|aiofiles|>=23.0.0|

## 配置说明

在 WebUI 插件配置页中修改。主要配置项如下。

### 全局设置

|配置项|说明|默认值|
|-|-|-|
|`enable\_nl\_trigger`|启用自然语言触发。关闭后 LLM 工具无法生图，仅 `/生图`、`/改图` 可用|`true`|
|`global\_retry\_count`|全局默认重试次数。单模型未单独配置（`-1`）时使用|`2`|
|`global\_max\_generation\_count`|全局默认单次请求最大生成张数上限。`-1` 表示不限制|`2`|

### 模型列表（`models`）

在「图像生成模型列表」中点击新增时，会分别看到 `OpenAI` 与 `Gemini` 两种模板，可配置多个实例。仅 **已启用** 的模型参与生成；按 **优先级（数值越大越优先）** 从高到低依次尝试。

每个模型常见字段：

|字段|说明|
|-|-|
|`provider\_label`|类型说明，当前对应 OpenAI / Gemini|
|`display\_name`|显示名称，用于日志与错误提示|
|`enabled`|是否启用|
|`priority\_preset`|优先级预设。推荐直接选择“最高 / 高 / 普通 / 低 / 最低”，大量条目时不必一个个手填数字|
|`priority`|仅当 `priority\_preset=custom` 时使用的自定义优先级数值，数值越大越优先。预设对应：最高=`40`，高=`30`，普通=`20`，低=`10`，最低=`0`|
|`url`|API 地址（OpenAI 如 `https://api.openai.com/v1`，Gemini 如 `https://generativelanguage.googleapis.com/v1beta`）|
|`apikey`|API Key|
|`model\_name`|模型 ID|
|`retry\_count`|重试次数，`-1` 表示使用全局默认|
|`max\_generation\_count`|该模型单次请求最大生成张数，`-1` 表示使用全局默认；超出后提示「超出生成张数上限」并尝试下一模型|
|`quality` / `size`|画质与尺寸（默认画质为 `high`，部分网关可能忽略）|
|`moderation`|内容审核 / 安全过滤等级（见下文）|
|`seed`|随机种子，留空表示随机（部分模型不支持）|
|`fake\_forward\_mode`|消息伪造转发。默认 `follow\_global`；可选关闭、Bot自身、生图要求者、自定义QQ号|
|`fake\_forward\_custom\_qq`|仅当 `fake\_forward\_mode=custom\_qq` 时显示，填写自定义 QQ 号|
|`send\_strategy`|该模型的发送链路，默认 `follow\_global`（见下文「发送链路」）|

### 工作流（Workflow）列表（`workflows`）

在「图像生成模型列表」和「生图开始提示」之间新增了「工作流（Workflow）列表」，用于接入 ComfyUI 工作流。工作流条目与模型条目**统一参与同一套优先级调度**：按 `priority` 降序与模型混合排列，一起做重试与回退。

> \*\*当前版本范围\*\*：ComfyUI 工作流可按 `supported\_modes` 配置为仅文生图、文生图 + 改图、或仅改图。

每个工作流条目字段：

|字段|说明|
|-|-|
|`enabled`|是否启用|
|`priority\_preset`|优先级预设。推荐直接选择“最高 / 高 / 普通 / 低 / 最低”|
|`priority`|仅当 `priority\_preset=custom` 时使用的自定义优先级数值。预设对应：最高=`40`，高=`30`，普通=`20`，低=`10`，最低=`0`|
|`retry\_count`|重试次数，`-1` 表示使用全局默认|
|`max\_generation\_count`|单次请求最大生成张数，`-1` 表示使用全局默认|
|`workflow\_id`|工作流 ID，同时也会直接作为该工作流的显示名称；用于关联下方的工作流自定义节点条目，可输入任意中文/英文/符号作为名称|
|`supported\_modes`|工作流支持的模式。可选“仅文生图”“文生图 + 改图”“仅改图”；默认仅 `text\_to\_image`|
|`runtime\_base\_url\_override`|覆盖 ComfyUI 地址；留空则使用全局默认|
|`runtime\_api\_key\_override`|覆盖 ComfyUI 鉴权 Token；留空则使用全局默认|
|`workflow\_content`|**必须**是从 ComfyUI 点击“导出（API 格式）”得到的完整 JSON|
|`fake\_forward\_mode`|消息伪造转发。默认 `follow\_global`；可选关闭、Bot自身、生图要求者、自定义QQ号|
|`fake\_forward\_custom\_qq`|仅当 `fake\_forward\_mode=custom\_qq` 时显示，填写自定义 QQ 号|
|`send\_strategy`|该工作流的发送链路，默认 `follow\_global`|

#### 工作流自定义节点条目（`workflow\_node\_bindings`）

这里就是你在配置面板里看到的“自定义节点条目”。它现在已经从工作流条目内部拆出来，变成单独的顶层列表。你可以一条一条新增规则，用 **“工作流 ID + 节点 ID + 字段路径”** 精确定位某个 workflow 的字段，再根据你选择的内容类型，用输入内容去覆盖该字段原有值；最终合并后的 workflow 才会被提交执行。你也可以把它简单理解成：**采用节点 ID + 字段路径双重定位的工作流参数替换规则**。

|字段|说明|
|-|-|
|`workflow\_id`|该条规则属于哪个工作流，必须与某个工作流条目的 `workflow\_id` 完全一致|
|`node\_id`|对应 `workflow\_content` 中该节点的 Key（例如 ComfyUI 导出 JSON 里的 `"6"`）|
|`field\_path`|点路径，例如 `inputs.text` 或 `inputs.texts.0`（支持列表下标）|
|`binding\_type`|内容类型（见下表）|
|`prompt\_negative\_value`|当内容类型是“反向提示词”时显示，填写反向提示词文本|
|`custom\_text\_value`|当内容类型是“自定义文本”时显示，填写任意文本|
|`seed\_value`|当内容类型是“随机种子”时显示，留空则每次随机|
|`custom\_number\_value`|当内容类型是“自定义数值”时显示，填写整数或小数|
|模式切换专用输入框|当内容类型是 `mode\_switch\_\*` 时显示；会按你选择的类型显示“文生图文本 / 改图文本”或“文生图数值 / 改图数值”或“文生图 JSON / 改图 JSON”|

`binding\_type` 这一项的介绍中会直接提示：

* 正向提示词应通过 `/生图` `/改图` 指令输入
* 图片输入为 `/改图` 指令专用
* 模式切换类型只在“文生图 + 改图”这类双模式工作流里才会用到

因此，`正向提示词` 与 `图片输入` 这两种类型不会再额外显示输入框。

`binding\_type` 支持：

|类型|说明|
|-|-|
|`prompt\_positive`|使用当前 `/生图` 提示词覆盖该字段|
|`prompt\_negative`|使用 `custom\_value` 填写的反向提示词覆盖该字段|
|`image\_input`|使用输入图片覆盖该字段；仅在 `/改图` 请求下生效|
|`seed`|使用 `custom\_value` 中的整数作为种子；留空则每次随机生成|
|`custom\_text`|使用 `custom\_value` 中的文本覆盖该字段|
|`custom\_number`|使用 `custom\_value` 中的数字覆盖该字段；含小数点按浮点数处理，否则按整数处理，**不会**被转换为字符串|
|`mode\_switch\_text`|只在双模式工作流里使用。同一字段在 `/生图` 与 `/改图` 下填入两段不同文本|
|`mode\_switch\_number`|只在双模式工作流里使用。同一字段在 `/生图` 与 `/改图` 下填入两个不同数字，最常见用来切 `denoise`|
|`mode\_switch\_json`|只在双模式工作流里使用。同一字段在 `/生图` 与 `/改图` 下填入两个不同 JSON 值，最常见用来切节点引用，例如 `latent\_image`|

**示例**：将节点 `6` 的 `inputs.text` 绑定为正向提示词：

```json
{
  "workflow\_id": "portrait\_flux",
  "node\_id": "6",
  "field\_path": "inputs.text",
  "binding\_type": "prompt\_positive"
}
```

你也可以把它理解成：

* `workflow\_id`：这条规则属于哪个工作流
* `node\_id`：改哪一个节点
* `field\_path`：改这个节点里的哪一项
* `binding\_type`：这项内容是什么类型
* 对于需要手动输入的类型，面板会按类型显示对应的输入框；`正向提示词` 和 `图片输入` 不会再显示可编辑输入框；三种“模式切换”类型则会分别显示文生图值和改图值输入框

### ComfyUI 运行环境（全局默认，`workflow\_runtime\_default`）

供未在工作流条目中单独覆盖运行环境的条目使用：

|字段|说明|默认值|
|-|-|-|
|`base\_url`|ComfyUI 地址|`http://127.0.0.1:8188`|
|`api\_key`|鉴权 Token，部分部署无需鉴权可留空|`''`|
|`poll\_interval\_seconds`|查询任务状态的轮询间隔（秒）|`1.0`|
|`timeout\_seconds`|任务超时时间（秒）|`300`|

### 生图开始提示（`generation\_start\_message`）

用于控制在真正开始生成前是否发送提示语，位置在「图像生成模型列表」后方。关闭后不会发送任何开始提示，相关附属配置项也会在配置面板中隐藏。开启后支持两种模式：

* **固定语句**：默认模式；只提供一组预设文案，发送时随机选取一条
* **LLM**：可选择 AstrBot 中已配置的模型提供商，或沿用默认提供商；同时可切换使用当前人设或自定义人设提示词

配置项如下：

|配置项|说明|默认值|
|-|-|-|
|`enabled`|是否启用开始提示发送|`true`|
|`mode`|提示语模式。`fixed` 为固定语句，`llm` 为 LLM 生成|`fixed`|
|`fixed\_messages`|固定语句列表。固定语句模式下随机发送|`\['开始生成0v0~']`|
|`llm\_provider\_id`|LLM 提示语使用的提供商；留空则跟随当前默认配置|`''`|
|`llm\_persona\_source`|LLM 提示语使用的人设来源。`current` 为当前人设，`custom` 为自定义人设提示词|`current`|
|`llm\_custom\_persona\_prompt`|自定义人设提示词，仅在 `llm\_persona\_source=custom` 时生效|`根据现在的情景，以适宜的性格言语，简单表述要开始生成图片了，不分段不加格式，10字以内，结尾不加标点符号换成颜文字表情，严禁使用emoji。`|

### 全局消息伪造转发（`fake\_forward`）

位于配置面板中的「生图开始提示」和「全局发送链路」之间。关闭时不启用；开启后，会在生成完成时把“开始提示”和图片合并成一条转发消息发送出去，主要面向 QQ 侧的合并转发展示。

配置项如下：

|配置项|说明|默认值|
|-|-|-|
|`mode`|伪造转发身份。可选 `off` / `bot\_self` / `requester` / `custom\_qq`|`off`|
|`custom\_qq`|仅在 `mode=custom\_qq` 时显示，填写你希望用于转发显示的 QQ 号|`''`|

说明：

* `off`：关闭消息伪造转发
* `bot\_self`：尽量使用 Bot 自身 QQ 和昵称作为转发节点身份
* `requester`：使用发起本次 `/生图` 或 `/改图` 请求的用户身份
* `custom\_qq`：使用你填写的 QQ 号；若能获取昵称则显示昵称，否则回退显示 QQ 号

每个模型 / 工作流条目都可以单独设置 `fake\_forward\_mode`；默认值为 `follow\_global`，表示跟随本节的全局配置。

### 审核力度（`moderation`）

**OpenAI** 可选：`none` / `low` / `high` / `auto`

* 设为 **`none`** 时，插件会依次尝试：不传 `moderation` 参数 → `low` → `auto`，以兼容不同网关对「关闭审核」的实现方式。
* 设为 **`high`** 时，会以更严格的审核等级请求上游接口。

**Gemini** 可选：`none` / `low` / `high` / `default`

* 设为 **`none`** 时，插件会依次尝试 `BLOCK\_NONE`、`OFF`、`BLOCK\_ONLY\_HIGH` 等多种安全设置，失败后继续降级。
* 设为 **`high`** 时，会使用 `BLOCK\_MEDIUM\_AND\_ABOVE` 作为更严格的安全过滤等级。

> 降低审核等级可能违反上游服务条款，请自行评估风险；部分网关仍可能强制过滤内容。

### 多模型与回退逻辑

1. 筛选已启用的模型与工作流条目，按 `priority` 降序统一排列
2. 对每个目标：检查本次请求张数是否超出 `max\_generation\_count`
3. 若为工作流条目但 `supported\_modes` 不包含当前模式，直接跳过该目标
4. 未超限时按 `retry\_count` 重试（间隔约 2^n 秒，上限 10 秒）
5. 当前目标全部失败后，自动尝试下一优先级目标
6. 所有目标均失败时，返回最后一次错误摘要；仅当所有候选目标都因额度上限被跳过时，才统一返回「超出生成张数上限」

### 发送链路（`send\_strategy`）

用于控制生成结果（成功文本、开始提示、图片）的发送优先方式，位于配置面板**最底部**，即「生图开始提示」下方。该配置**极少需要调整**，默认的「直连优先」已能覆盖绝大多数场景。

> \*\*注意\*\*：当生图/改图成功、但发送图片失败时，可尝试更改此项。

可选值：

|值|说明|
|-|-|
|`direct\_first`|默认。优先直接发送（`event.send` → `context.send\_message` → 平台客户端），仅在都失败时才回退到结果管道|
|`event\_send\_first`|只尝试 `event.send`|
|`context\_send\_first`|只尝试 `context.send\_message`|
|`platform\_client\_first`|只尝试平台客户端直接调用|
|`result\_pipeline\_only`|不做任何主动发送，直接走 AstrBot 结果管道（等价于回退到早期版本行为）|

每个模型 / 工作流条目都可以单独设置 `send\_strategy`；默认值为 `follow\_global`，表示跟随本节的全局配置。

### 优先级使用建议

当条目比较多时，建议优先使用：

* `最高`
* `高`
* `普通`
* `低`
* `最低`

它们当前对应的预设数值分别是：

* `最高 = 40`
* `高 = 30`
* `普通 = 20`
* `低 = 10`
* `最低 = 0`

只有在你确实需要更细的排序时，再把 `priority\_preset` 设为 `custom`，并手动填写 `priority` 数值。比如 `35` 可以插在“最高”和“高”之间，`25` 可以插在“高”和“普通”之间。这样比逐个条目手填数字更省事，也更不容易出错。

## 使用说明

### `/生图` — 文字生图

```
/生图 {提示词}
/生图 {提示词} {张数}
```

* 提示词必填
* 张数为可选末尾整数，默认为 `1`
* 也支持 AstrBot 参数形式：`/生图 提示词:xxx  count:2`

**示例：**

```
/生图 牢大和张雪峰比谁跑的快，电影感
/生图 原神启动 2
```

### `/改图` — 图片改图

```
/改图 {提示词}
```

* 需在**同一条消息**中附带图片，或**引用**含图片的消息
* 改图使用收集到的**第一张**图片作为输入
* 提示词必填

**示例：**

```
（附带一张人像照片）
/改图 把脸P上黑曼巴，笑容四溢
```

### 自然语言触发

当 `enable\_nl\_trigger` 为 `true` 时，绑定了 LLM 的会话中，模型可调用工具 `image\_gateway\_generate`：

* `prompt`：提示词
* `mode`：`text\_to\_image`（默认）或 `image\_to\_image`
* `count`：文生图张数（改图模式忽略）

改图模式同样需要在消息中附带或引用图片。关闭 `enable\_nl\_trigger` 后，工具调用会提示使用 `/生图` 或 `/改图`。

## 输出行为

1. 若启用了开始提示功能，生成开始时会先发送一条开始提示：固定语句模式下随机发送一条预设文案；LLM 模式下由所选提供商根据人设生成
2. 生成成功后：

   * 若未启用消息伪造转发：先发送一条文本 `生图成功，用时X.X秒` 或 `改图成功，用时X.X秒`
   * 若启用了消息伪造转发：会将这条成功提示与实际生成的图片合并转发，不再把“开始生成”提示并进去
3. 随后发送图片或合并转发：

   * **单张**：优先直接发送图片消息；若直接发送失败，再回退到结果管道发送
   * **多张**：优先发送合并转发节点；若失败，则按 `图片 1/N` 的顺序逐张发送，并继续做多级回退
4. 若开始提示消息成功获取到消息 ID，生成结束后会自动撤回该提示；如果平台不支持撤回或无法取得消息 ID，插件会自动忽略该步骤
5. 图片保存在插件数据目录 `data/plugin\_data/astrbot\_plugin\_image\_gateway/images/`（由 AstrBot 运行时管理，无需手动创建）
6. 若 AstrBot 主配置中设置了 `callback\_api\_base`，会尝试将图片转为可访问 URL 发送；转换失败则回退为本地文件发送

## 注意事项

* 请妥善保管各模型的 `apikey`，勿将含密钥的配置文件提交到公开仓库
* 不同 API 网关对 `moderation`、`size`、`seed` 等字段支持程度不同，失败时可查看 AstrBot 日志
* OpenAI 适配器在标准 Images API 失败时，会尝试通过 `chat/completions` 兼容部分第三方网关
* Gemini 原生接口可能忽略 `size` 等字段，以实际网关行为为准
* `max\_generation\_count` 控制的是**单次请求张数上限**，不是历史累计总量
* 改图仅使用第一张输入图；如需多图参考，请自行在提示词中描述或等待后续版本支持
* 生成耗时受上游 API 影响，单次请求超时约 300 秒  
* 工作流 `workflow\_content` 必须是 ComfyUI 的 **API 格式导出**，普通工作流导出格式无法直接使用
* 工作流可配置为仅文生图、文生图 + 改图、或仅改图；若要同时支持 `/改图`，请将 `supported\_modes` 设为 `both` 并配置双入口绑定
* 本地导出的工作流 JSON 可能包含私有节点、模型路径、提示词或其它环境信息，建议只粘贴到配置面板使用，不要提交到公开仓库

## 项目结构

```
astrbot\_plugin\_image\_gateway/
├── main.py              # 插件入口、指令注册与消息发送链路
├── metadata.yaml        # 插件元数据
├── \_conf\_schema.json    # WebUI 配置 schema
├── requirements.txt     # Python 依赖
├── CHANGELOG.md         # 版本更新日志
├── adapters/            # OpenAI / Gemini 适配器
├── services/            # 生成调度、发送策略、Workflow 配置与执行
│   ├── generation.py        # 统一调度模型与工作流条目
│   ├── send\_strategy.py      # 发送链路枚举与解析
│   ├── workflow\_config.py    # Workflow / 节点绑定配置模型
│   ├── workflow\_merge.py     # node\_id + field\_path 覆盖逻辑
│   └── workflow\_runner.py    # ComfyUI 提交与轮询执行器
└── utils/               # 消息解析、图片存储、点路径工具
```

## 许可证

[MIT License](./LICENSE)

## 单工作流双入口补充说明

上面的“先看这里：ComfyUI 同时支持文生图和图生图”已经给出了完整的新手教程；这里保留最核心的速查版。

* `workflows` 里的 `supported\_modes` 默认只支持 `text\_to\_image`
* 如果某个 ComfyUI workflow 需要同时兼容 `/生图` 和 `/改图`，请把 `supported\_modes` 设为 `both`
* 如果某个 ComfyUI workflow 只用于 `/改图`，可以把 `supported\_modes` 设为 `image\_to\_image`
* `/改图` 模式下，插件会先把输入图片上传到 ComfyUI，再把返回文件名写入 `image\_input` 绑定对应的字段
* 单工作流双入口推荐搭配 `mode\_switch\_number` 与 `mode\_switch\_json` 使用

典型做法：

1. `/生图` 时把 `KSampler.inputs.latent\_image` 指向空 latent 节点，并把 `denoise` 写成 `1.0`
2. `/改图` 时把 `KSampler.inputs.latent\_image` 指向 `VAEEncode` 输出，并把 `denoise` 写成图生图值，比如 `0.45`

示例绑定：

```json
{
  "workflow\_id": "dual\_entry\_demo",
  "node\_id": "31",
  "field\_path": "inputs.latent\_image",
  "binding\_type": "mode\_switch\_json",
  "text\_to\_image\_value": "\[\\"23\\", 0]",
  "image\_to\_image\_value": "\[\\"225\\", 0]"
}
```

```json
{
  "workflow\_id": "dual\_entry\_demo",
  "node\_id": "31",
  "field\_path": "inputs.denoise",
  "binding\_type": "mode\_switch\_number",
  "text\_to\_image\_value": "1.0",
  "image\_to\_image\_value": "0.45"
}
```

## v1.3.6 补充说明

### 工作流显示名称简化

* 配置面板中的 ComfyUI 工作流条目已移除单独的“显示名称”输入项
* 现在直接使用 `workflow_id` 作为工作流显示名称，并用于关联下方“工作流自定义节点条目”
* `workflow_id` 可输入任意中文、英文或符号，只要你自己便于辨认即可

### 调度报错修复

* 当同时存在“仅文生图”和“仅改图”工作流时，如果真正参与执行的文生图工作流因为节点 ID 或字段路径写错而失败，现在会优先返回真实执行错误
* 不再被后续被跳过的“仅改图工作流暂不支持文生图”提示覆盖，排错会更直接

## v1.4.5 补充说明

### 工作流条目介绍方式对齐 OpenAI/Gemini

* 参考"图像生成模型列表"中 OpenAI/Gemini 条目的介绍方式，将"工作流（Workflow）列表"下 ComfyUI 条目的 `display_item` 从数组形式 `["workflow_id"]` 改为字符串形式 `"workflow_id"`，与 OpenAI/Gemini 使用 `"display_name"` 的写法保持一致
* 现在工作流条目副标题只显示 `workflow_id` 的实际内容，例如在"工作流 ID (workflow_id)"中输入 `文生图1`，则显示 `文生图1`
* 将 ComfyUI 模板介绍文案改为 `工作流 ID (workflow_id)输入框中输入的内容变量`，移除 `hide_hint_in_list` 设置，使介绍文案正常展示，不再与条目值混排成 `miaomiao文生图——工作流 ID (workflow_id)输入框输入的内容变量` 这类异常显示
* 此前 v1.4.3/v1.4.4 使用数组形式 `display_item` 并配合 `hide_hint_in_list` 隐藏提示文案，但 AstrBot 配置面板对数组形式 `display_item` 的渲染会将字段描述拼入副标题，导致显示异常；改为字符串形式后该问题彻底消除

## v1.4.4 补充说明

### 工作流条目副标题最终修正

* 这次确认到问题根因不是 GitHub 仓库里的 schema 没改，而是你本地还有一份实际在看的插件副本没同步到最新逻辑
* 现在已统一改成：工作流条目副标题只显示 `workflow_id` 的实际内容，例如填入 `文生图1`，列表里就只显示 `文生图1`
* 同时把 ComfyUI 模板说明文案收回到纯“API 格式 JSON 导出”提示，避免异常路径下再把“显示名称...”这类说明混进条目副标题

## v1.4.3 补充说明

### 工作流条目副标题显示修正

* 这次改的是“工作流（Workflow）列表”条目副标题真正使用的显示字段，而不是只改介绍文案
* 现在工作流条目会只显示 `workflow_id` 的实际内容，例如在“工作流 ID (workflow_id)”里填入 `文生图1`，卡片下方就只显示 `文生图1`
* 同时隐藏了工作流条目列表中的模板提示文案，避免说明文字继续和条目值一起出现在列表副标题里

## v1.4.2 补充说明

### 工作流列表提示文案修正

* 将“工作流（Workflow）列表”中 ComfyUI 条目的介绍文案恢复为原来的变量说明格式
* 现在这里会显示为 `显示名称：工作流 ID (workflow_id)输入框中输入的内容变量`
* 这个修改只对应工作流列表卡片介绍本身，不影响现有工作流显示与调度逻辑

## v1.4.1 补充说明

### 自定义节点条目副标题显示改为插件内建

* 现在“工作流自定义节点条目”卡片下方显示的内容，由插件自动生成并保存到 `display_summary`
* 最终显示格式仍然是 `显示名称——所属工作流 ID`，例如：`正向提示词——miaomiao改图`
* 这次不再依赖 AstrBot dashboard 为本插件写特殊兼容逻辑，所以只要插件版本正确，Web 配置面板就能稳定显示
* 已补上对应回归测试，当前仓库 `test_regressions.py` 共 96 项测试通过

## v1.3.10 补充说明

### 工作流自定义节点条目副标题再次修复
* 这次修复的是更底层的展示链路问题：不仅处理 `display_item` 元数据缺失，也处理旧条目缺少 `__template_key` 时的展示失败
* 现在即使前端没有先拿到模板元数据，也会优先使用条目自身的 `display_name` 和 `workflow_id` 直接组合显示，例如：
  `正向提示词——miaomiao改图`
* 对于只有一个模板的条目列表，还会自动推断模板键，避免旧配置进入配置面板后因为模板键缺失而整块显示异常
* 本次已重新构建并同步 AstrBot dashboard 的前端产物到实际生效目录，避免再次出现“版本更新了，但 Web 配置面板看起来还是没变化”的情况

## v1.3.9 补充说明

### 工作流自定义节点条目副标题空白修复
* 修复了配置面板中“自定义节点条目”列表卡片在部分情况下副标题完全不显示的问题
* 现在这类条目会优先按 `display_name——workflow_id` 组合展示，例如：
  `正向提示词——miaomiao改图`
* 即使前端某些渲染路径没有保留数组形式的 `display_item` 元数据，也仍然会对工作流绑定条目执行专门回退，不再直接显示为空白
* 本次也已重新构建并同步 AstrBot dashboard 的前端产物，避免出现“源码已修复但网页面板没有变化”的情况

## v1.3.8 补充说明

### 工作流自定义节点条目显示优化
* 配置面板中“工作流自定义节点条目”的列表卡片副标题现在支持组合显示
* 当你填写：
  `display_name = 正向提示词`
  `workflow_id = miaomiao改图`
  时，面板里会直接显示为 `正向提示词——miaomiao改图`
* 这样可以更直观地区分“这条节点绑定规则本身叫什么”以及“它属于哪个工作流”
* `display_name` 输入项下方的提示文案也已恢复为原来的说明，不再被错误替换成固定句子

## v1.3.7 补充说明

### 消息伪造转发内容修正

* 启用消息伪造转发后，完成生成时现在会直接合并转发“生图成功/改图成功，用时X.X秒”和实际生成的图片
* 不再错误地把“开始生成0v0~”这类开始提示并入最终的合并转发结果

## v1.3.5 补充说明

### 图片缓存定时清理（`image_cache_cleanup_days`）

此项位于配置面板中的“全局消息伪造转发”和“全局发送链路”之间。

* 单位为“天”
* 默认值为 `7`
* 留空表示不自动清理
* 插件会按这个天数阈值，清理 `data/plugin_data/astrbot_plugin_image_gateway/images/` 目录中过期的历史图片缓存
* 为了避免每次生成都重复扫描目录，插件会限制清理检查频率
