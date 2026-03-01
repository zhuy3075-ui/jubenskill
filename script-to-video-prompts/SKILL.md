---
name: script-to-video-prompts
description: AI视频提示词全能生成器。支持三种模式：A）将短剧剧本文档智能拆解为完整分镜提示词体系；B）根据一句话创意意图直接生成 Seedance 2.0 平台级提示词；C）对标视频拆解与爆款重构分析（五维拆解+微创新+差异化公式）。输出包括：角色设定提示词、场景设定提示词、逐镜头分镜提示词、视频拆解报告与重构策略。支持批量处理、多格式导出、一致性校验、合规检查。当用户说"剧本转视频提示词"、"拆解剧本生成分镜"、"短剧转AI视频"、"批量生成分镜提示词"、"剧本可视化"、"generate video prompts"、"Seedance"、"seedance"、"即梦"、"即梦平台"、"视频提示词"、"视频生成"、"AI视频"、"短剧"、"广告视频"、"视频延长"、"对标视频拆解"、"爆款分析"、"微创新重构"、"差异化公式"时触发。
---

# AI视频提示词全能生成器

> 版本 3.1.3 | 更新于 2026-03-01

支持三种工作模式：
- **模式A（剧本流水线）**：将短剧剧本文档智能拆解为可直接用于AI视频生成的完整提示词体系
- **模式B（直接生成）**：根据一句话创意意图，直接生成 Seedance 2.0 平台级提示词
- **模式C（视频拆解与爆款重构）**：对标视频深度拆解，输出五维分析、微创新方向与差异化重构方案

**语言规则：用户用什么语言提问，就用什么语言回复。**

## 模式判断

| 用户输入特征 | 触发模式 |
|-------------|---------|
| 上传剧本文档（Word/PDF/TXT/MD/FDX） | 模式A（剧本流水线） |
| 说"拆解剧本"、"分镜"、"剧本转视频" | 模式A（剧本流水线） |
| 说"生成视频提示词"、"Seedance"、"即梦" | 模式B（直接生成） |
| 描述一句话创意意图（如"10秒仙侠战斗"） | 模式B（直接生成） |
| 上传剧本 + 指定 Seedance 平台 | 模式A + Seedance 平台适配 |
| 说"对标视频拆解"、"爆款分析"、"微创新重构" | 模式C（视频拆解与爆款重构） |
| 上传对标视频链接/素材并要求复刻或重构 | 模式C（视频拆解与爆款重构） |

---

## 模式A：剧本流水线

### 用户输入

- 短剧剧本文档（Word/PDF/TXT/Markdown/Final Draft .fdx）
- 可选：风格参考图片、角色参考图片、已有角色设定表
- 可选：目标AI视频平台（默认通用格式，可指定 Runway/Kling/Pika/Sora/Seedance 等，详见 [references/video_style_guide.md](references/video_style_guide.md) 平台适配章节）

### 工作流程

```
剧本文件 → ①解析 → ②角色提取 ──→ ④分镜生成 → ④b提示词优化 → ⑤一致性校验 → ⑥导出
                   ↘ ③场景分析 ─↗
                  （②③可并行）
```

### 步骤1：剧本智能解析

使用 `scripts/parse_script.py` 解析剧本：
- 自动识别剧本格式（标准编剧格式/自由格式），格式规范详见 [references/screenplay_format_spec.md](references/screenplay_format_spec.md)
- 提取场次(Scene)、场景描述(Action)、角色对白(Dialogue)、动作指示(Parenthetical)
- NLP分析：情绪曲线、节奏变化、画面密度
- 自动生成场次时长估算

### 步骤2：角色设定提取（与步骤3可并行）

使用 `scripts/character_extractor.py` 提取角色信息：
- 基础外貌（年龄、性别、体型、五官特征）
- 发型发色、肤色
- 服装造型（支持多场次服装变化追踪）
- 角色气质/性格的视觉化表达
- 标志性道具/配饰

输出格式参考 [references/character_template.md](references/character_template.md)，完整 JSON 结构参考 [assets/character_profile_template.json](assets/character_profile_template.json)

### 步骤3：场景设定分析（与步骤2可并行）

使用 `scripts/scene_analyzer.py` 分析场景：
- 场景类型（INT./EXT.、具体地点）
- 空间结构、关键道具布置
- 光线设计（光源类型、方向、强度、色温）
- 色彩基调、视觉氛围
- 天气/时间/季节

输出格式参考 [references/scene_template.md](references/scene_template.md)

### 步骤4：分镜提示词生成

使用 `scripts/storyboard_generator.py` 生成分镜：
- 镜头编号（场次-镜号），如 `1-3` 表示第1场第3个镜头
- 景别（ECU/CU/MCU/MS/MLS/LS/ELS），详见 [references/shot_terminology.md](references/shot_terminology.md)
- 画面构图（三分法位置、视线引导）
- 角色动作、表情、站位
- 运镜方式，详见 [references/shot_terminology.md](references/shot_terminology.md)
- 情绪氛围关键词，详见 [references/mood_keywords_library.md](references/mood_keywords_library.md)
- 建议时长（秒）
- 转场方式

提示词结构公式和场景模板详见 [references/prompt_patterns.md](references/prompt_patterns.md)，速查表见 [assets/prompt_cheatsheet.md](assets/prompt_cheatsheet.md)

### 步骤4b：提示词优化（可选）

使用 `scripts/prompt_optimizer.py` 优化生成的提示词：
- 自动补充质量增强关键词
- 检测并移除矛盾描述
- 评估提示词质量分数（0-1），合格阈值 ≥ 0.7
- 适配目标平台的提示词格式

**提示词验证规则**：
- 长度限制：单条提示词不超过 200 词
- 必须包含 6 要素：WHO（主体）、WHAT（动作）、WHERE（场景）、WHEN（时间/光线）、HOW（氛围/风格）、QUALITY（质量词）
- 禁止出现：版权作品名、矛盾描述（如同时出现 warm 和 cold tones）
- 必须包含一致性控制词（`consistent appearance` / `consistent environment`）

**Seedance 平台适配**（当目标平台为 Seedance 2.0 时）：
- 使用 SCELA 公式展开提示词，详见下方模式B
- 自动执行合规检查，详见 [references/seedance_compliance.md](references/seedance_compliance.md)
- 从 [references/seedance_prompt_templates.md](references/seedance_prompt_templates.md) 匹配最接近的模板（A-R）
- 叙述形式优先流畅叙事，仅在台词时序精确时使用时间戳

### 步骤5：一致性校验

使用 `scripts/consistency_checker.py` 校验，详见 [references/consistency_control.md](references/consistency_control.md)：

**角色一致性检查**：
- [ ] 发型发色是否跨镜头一致
- [ ] 面部标志性特征是否保留（痣、疤痕等）
- [ ] 体型比例是否一致
- [ ] 服装是否符合当前场次设定

**场景一致性检查**：
- [ ] 背景元素位置是否一致
- [ ] 关键道具是否存在
- [ ] 窗户/门的位置是否一致

**光线一致性检查**：
- [ ] 光源方向是否一致
- [ ] 色温是否统一
- [ ] 阴影方向是否匹配光源

**整体连贯性检查**：
- [ ] 前后镜头是否可流畅衔接
- [ ] 情绪氛围是否连续
- [ ] 风格关键词是否统一

### 步骤6：导出

使用 `scripts/export_utils.py` 导出：
- 支持格式：Markdown / JSON / CSV / Excel
- 支持按场次/角色/场景分类导出
- 可生成可视化分镜脚本（HTML），模板见 [assets/export_template.html](assets/export_template.html)

---

## 模式B：直接生成（Seedance 2.0）

适用于用户直接描述创意意图、无需上传剧本的场景。基于 362 条真实高分提示词提炼的 18 个生产级模板。

### B1. 收集必要信息（生成前必问）

收到用户需求后，先确认以下信息再生成，不要直接生成：

**必问信息：**
- **视频时长**：5s / 10s / 15s（不确认不生成）
- **视频风格**：让用户从以下风格模板中选择：
  - 动作/战斗/追逐
  - 仙侠/奇幻/史诗
  - 产品/电商/广告
  - 短剧/对白/情感
  - 变身/变装/转场
  - 舞蹈/MV/卡点
  - 生活/治愈/Vlog
  - 科幻/机甲/末日

**可选信息（如果用户已提供则跳过）：**
- 视频比例：16:9 / 9:16（默认 16:9）
- 是否有参考图片/视频素材

> 一次性问完，不要分多轮问。

### B2. 识别类型 → 调模板

| 类型 | 信号词 | 模板 |
|------|--------|------|
| 动作/战斗/追逐 | 打斗、格斗、逃跑、追车、功夫 | A/B/C |
| 仙侠/奇幻/史诗 | 修仙、仙侠、法术、魔法、神话 | D/E |
| 产品/电商/广告 | 产品、广告、展示、带货、商业 | F/G/H |
| 短剧/对白/情感 | 霸总、短剧、台词、反转、对话 | I/J |
| 变身/变装/转场 | 变身、换装、变形、转变 | K/L |
| 舞蹈/MV/卡点 | 舞蹈、卡点、MV、节拍 | M/N |
| 生活/治愈/Vlog | 日常、治愈、氛围、UGC | O/P |
| 科幻/机甲/末日 | 科幻、机甲、机器人、末日 | Q/R |

> 读取 [references/seedance_prompt_templates.md](references/seedance_prompt_templates.md) 获取对应模板和优质 Example。

### B3. 用 SCELA 公式展开

| 字母 | 含义 | 示例 |
|------|------|------|
| **S** - Subject | 主体（谁/什么） | 虚拟女侠、原创无标识饮料罐 |
| **C** - Camera | 镜头语言 | 低角度仰拍、环绕跟拍、希区柯克变焦 |
| **E** - Emotion/Effect | 情绪/特效 | 电光四射、热泪盈眶、粒子爆炸 |
| **L** - Light/Look | 光影/风格 | 电影级、霓虹冷暖对比、胶片质感 |
| **A** - Audio | 声音设计 | 剑鸣声、心跳加速、磁场嗡鸣 |

**合规角色替换原则**：
- 保留原角色的颜色主调、装备风格、战斗能力等视觉特征
- 例：钢铁侠 → 「红金色金属装甲战士，胸前能量反应炉，全身机械甲，无版权标识」
- 详见 [references/seedance_compliance.md](references/seedance_compliance.md)

> 词汇库（镜头/风格/图片风格匹配）见 [references/seedance_vocab.md](references/seedance_vocab.md)

### B4. 选叙述结构

- **流畅叙事**（优先）：`镜头跟随主体动作，场景转换，特效，音效` — 适合追逐/变身/日常/广告
- **时间戳分镜**（仅需精确时序时用）：`0-Xs：画面 / X-Ys：动作 / Y-末：收束` — 适合短剧台词/多段史诗

### B5. 合规检查（内部处理，不向用户说明）

> 读取 [references/seedance_compliance.md](references/seedance_compliance.md) 获取完整违禁词规范和替换速查表。

快速检查：真实人名？版权IP？品牌名？政治内容？ → 有则替换，政治内容直接拒绝。

**合规提示词作为内嵌约束处理，不在输出中单独列出"禁止：..."行。**

### B6. 输出格式

**5s短版**：直接输出提示词，紧凑简洁。

**10s/15s 完整版**：
```
**主题**：X  **时长**：Xs  **比例**：16:9/9:16

### 版本一：[风格名]
[提示词]

---
### 版本二：[风格名]（可选）
[提示词]
```

**超长版（>15s）**：分段，每段 ≤15s，后续段用「将@视频1延长Xs」衔接，标注衔接点。

**输出注意：**
- 不输出「禁止：真实人脸、版权IP...」等说明行
- 不输出「参考素材」板块
- 不输出「风格调整建议」「素材建议」等任何额外说明
- 直接给出可用的提示词，输出完就结束

### @引用规则

- 用户上传图片时：直接用 `@图片1`、`@图片2` 等，不用描述角色名称
- 命名：`@图片1`～`@图片9` / `@视频1`～`@视频3` / `@音频1`～`@音频3`
- 用途在提示词中明确：`@图片1为首帧` / `参考@视频1的运镜` / `背景音参考@音频1`

### Seedance 平台参数速查

| 输入类型 | 限制 |
|----------|------|
| 图片 | ≤9张，单张<30MB，jpeg/png/webp/bmp |
| 视频 | ≤3个，总时长2-15秒，<50MB，480p-720p |
| 音频 | ≤3个，总时长≤15秒，<15MB |
| 生成时长 | 4-15秒 |
| ⚠️ 硬限制 | 写实真人脸部素材自动拦截 |

### 十大能力起手式

| 场景 | 起手式 |
|------|--------|
| 纯文本 | `[主体]+[动作]+[场景]+[镜头]+[风格]` |
| 图片一致性 | `@图片N+[动作]+[运镜]` |
| 运镜复刻 | `参考@视频1的运镜+@图片N+[场景]` |
| 特效复刻 | `参考@视频1的特效，将[A]换为@图片N` |
| 视频延长 | `将@视频1延长Xs。[新增内容描述]` |
| 一镜到底 | `一镜到底+@图片1..+[连续场景]+全程不切镜` |
| 视频编辑 | `将@视频1中的[A]换成@图片1+[修改说明]` |
| 音乐卡点 | `@图片1..N+参考@视频1的节奏卡点+[风格]` |
| 声音控制 | `[画面]+音色参考@视频1+"[台词]"` |

---

## 模式C：视频拆解与爆款重构（CJie Protocol）

适用于用户提供对标视频链接/素材，要求拆解爆款逻辑、提炼可复用资产并给出重构策略的场景。

### C1. 输入要求

- 必选：对标视频链接或视频文件（可附标题、发布时间、播放量）
- 可选：频道主页截图、评论区截图、重构目标（复刻/差异化改编）
- 若用户未提供视频，先引导补充链接或文件，再开始分析

### C2. 分析框架（强制）

- 五维深度解构：时 / 物 / 人 / 事 / 空
- 六类脚本微创新手术台：视角置换、时序重组、风格重调、感官放大、互动植入、情绪升维
- 十大差异化重构公式：旧瓶装新酒、极致反差、降维打击、跨界移植、时空穿越、万物拟人、微缩世界、感官放大、平行宇宙、数据可视化

### C3. 输出结构（强制）

- 阶段一：启动与信息确认（素材检查、模型来源确认）
- 阶段二：深度拆解报告（频道基因诊断、五维分析、评论区洞察、策略菜单）
- 阶段三：基于原脚本微创新重构（资产复用+定向改写）
- 阶段四：多源素材融合与迭代建议（可行性评估+融合方案）

### C4. 质量与风控要求

- 优先中文深度输出，避免空洞总结
- 必须包含可执行镜头层建议，不只停留在概念层
- 保持合规审查：暴力/血腥/高危/版权风险需明确预警
- 默认不主动推荐“赛博朋克”风格，除非用户明确指定或原片即该风格

### C5. 分镜重构执行铁律（补充）

- 当用户目标是“剧本视觉化创作/分镜重构”时，优先启用分阶段输出（资产定义 → 分镜批次 → 后期发布）
- 强制资产引用一致性：分镜中出现的 `@标签` 必须在资产库有定义且逐字一致
- 强制风格全量复述：禁止“同上/略/参考上文”，每条镜头提示词独立可用
- 对“静态图批量生成（宫格）”需求，必须保证 1 镜号 = 1 宫格，且保持时序连贯
- 关键镜头视频化（抽卡）需求，输出至少 3 种运镜变体（基础还原/动态张力/情绪氛围）

### C6. 协议来源

- 完整执行协议见 [references/cjie_video_deconstruction_protocol.md](references/cjie_video_deconstruction_protocol.md)
- 分镜重构补充协议见 [references/new_storyboard_reconstruction_architect_protocol.md](references/new_storyboard_reconstruction_architect_protocol.md)

### C7. 硬性自检模板（执行清单，必须逐项勾选）

在模式C每次输出前，必须执行以下检查；任一失败时禁止进入下一阶段并先修复：

**资产一致性检查**
- [ ] 分镜中所有 `@标签` 均已在资产库定义（0个未定义引用）
- [ ] 分镜中的 `@标签` 与资产库 `tag` 字段逐字一致（0个别名/简称）
- [ ] 每个资产定义均包含来源说明（参考图继承/剧本适配）
- [ ] 角色固有特征（脸型/发型/体型/关键配饰）跨镜头一致

**分阶段输出检查**
- [ ] 已按阶段输出（阶段一→阶段二→阶段三→阶段四），无跳步
- [ ] 当前批次输出后已停止并等待用户确认（未越级续写）
- [ ] 分镜数量与当前阶段计划一致（无缺失、无合并）
- [ ] 禁止占位符（`[填入...]`、`同上`、`略`）已全部清理

**宫格模式检查（仅模式B静态图批量时）**
- [ ] 1镜号=1宫格，镜号与宫格一一对应
- [ ] 宫格帧顺序时序连贯（左上→右下）
- [ ] 宫格内风格/角色/光影一致，无突变
- [ ] 每帧序号规范（`sc1..scN`）且无台词文字污染
- [ ] 每个宫格下方均附关键帧推荐清单（不少于1条）

**抽卡视频变体检查（关键帧视频化时）**
- [ ] 每个目标关键帧输出3个变体（基础还原/动态张力/情绪氛围）
- [ ] 3个变体运镜类型不同，且不偏离原镜头语义
- [ ] 若提供首尾帧，已明确过渡关系；若无图，已提示补图风险

**安全与合规检查**
- [ ] 暴力/血腥/高危/版权敏感内容完成风险提示或替代
- [ ] 负面约束词完整注入（畸形、多肢体、结构错乱等）
- [ ] 输出内容全中文（约定允许的英文技术词除外）
- [ ] 未出现违规风格默认推荐（赛博朋克仅在用户明确要求时允许）

### C8. 质检成果清单（固定输出格式）

模式C每轮结束时，追加输出以下清单（可简版）：

```markdown
【质检成果清单】
- 资产一致性：通过/未通过（未定义标签: X 个；别名引用: X 个）
- 分阶段执行：通过/未通过（当前阶段: X；是否等待确认: 是/否）
- 分镜数量对齐：通过/未通过（计划: X；已生成: X）
- 宫格模式检查：通过/未通过（镜号-宫格映射错误: X）
- 抽卡变体检查：通过/未通过（缺失变体镜号: ...）
- 安全合规检查：通过/未通过（风险项: ...）
- 占位符清洗：通过/未通过（残留项: ...）
- 结论：可进入下一阶段 / 需修复后重试
```

### C9. 结构化 JSON 机审模板（强制）

在模式C场景下，除 `C8` 的可读清单外，必须同时输出一份结构化 JSON（用于自动机审与流水线网关判定）：

- 模板文件：`assets/c7_quality_gate_template.json`
- 关键字段：`overall_pass`、`checks.*.pass`、`gate_decision.status`、`gate_decision.required_fixes`
- 网关判定规则：
  - 若任一 `checks.*.pass=false`，则 `gate_decision.status` 必须为 `block`
  - 仅当所有必检项通过时，`gate_decision.status` 才可为 `allow`
  - `summary_markdown` 必须与 `C8` 文本结论一致
- 严禁省略字段；无数据时填 `0`、空数组 `[]` 或 `applicable=false`

## 边界情况处理

| 情况 | 处理策略 |
|------|----------|
| 无对白的纯动作剧本 | 跳过对白提取，增加动作描述的镜头密度 |
| 极短剧本（1-2场） | 正常处理，提示用户场次较少 |
| 超长剧本（100+场） | 分批处理，每批20场，保持全局一致性档案 |
| 非标准格式剧本 | 启用自由格式解析模式，按段落分析 |
| 缺少角色外貌描述 | 生成基础占位描述，标记为"待用户补充" |
| 用户提供参考图片 | 优先使用图片特征覆盖文本提取结果 |

## 输出结构

```
一、项目元数据
   - 片名、集数、总时长、场次数

二、风格总设定
   - 画面风格、色彩体系、光影风格

三、角色设定库
   - JSON结构化数据 + 自然语言描述 + 一致性种子词

四、场景设定库
   - JSON结构化数据 + 自然语言描述 + 一致性种子词

五、完整分镜提示词
   - 按场次顺序排列，每镜头含完整提示词

六、一致性参考表
   - 角色/场景/光线一致性种子词汇总

七、质量报告
   - 提示词质量评分、一致性校验结果、待修正项
```

### 输出示例（节选）

以下为第1场第2个镜头的输出示例：

```json
{
  "shot_id": "1-2",
  "scene": "INT. 咖啡厅 - 早晨",
  "shot_size": "MS",
  "camera_movement": "push in",
  "character": "林晓薇",
  "action": "女主角坐在窗边，看向窗外",
  "duration_seconds": 4,
  "mood": "期待、若有所思",
  "transition": "cut",
  "visual_prompt": "medium shot of young Asian woman with long black wavy hair, sitting by window in modern coffee shop, looking outside with contemplative expression, warm natural morning light from window, soft side lighting, cozy earth tones, shallow depth of field, cinematic, high quality, consistent appearance",
  "character_seed": "[CHARACTER:林晓薇] Asian female late twenties, slim, long dark wavy hair, large almond eyes, beauty mark left eye, consistent appearance, same person",
  "scene_seed": "[SCENE:咖啡厅] modern coffee shop interior, exposed brick wall, large windows, wooden tables, warm morning light, consistent environment",
  "quality_score": 0.85
}
```

完整端到端示例见 [assets/example_input.txt](assets/example_input.txt) → [assets/example_output.md](assets/example_output.md)

## 参考文件

### scripts/（自动化脚本）
- `parse_script.py` — 剧本解析器（步骤1入口：`parse_script(file_path)`）
- `character_extractor.py` — 角色信息提取（步骤2入口：`extract_characters(parsed_script)`）
- `scene_analyzer.py` — 场景分析（步骤3入口：`analyze_scenes(parsed_script)`）
- `storyboard_generator.py` — 分镜生成（步骤4入口：`generate_storyboard(parsed, scenes, chars)`）
- `prompt_optimizer.py` — 提示词优化（步骤4b入口：`optimize_prompt(prompt, context)`；模式B入口：`generate_seedance_prompt(intent, duration, genre, aspect_ratio)`）
- `consistency_checker.py` — 一致性校验（步骤5入口：`check_consistency(storyboard, chars, scenes)`）
- `export_utils.py` — 多格式导出（步骤6入口：`export_all(storyboard, chars, scenes, dir)`）

### references/（规范文档）
- `screenplay_format_spec.md` — 剧本格式规范（含正则表达式模式）
- `character_template.md` — 角色设定模板与外貌描述指南
- `scene_template.md` — 场景设定模板与光线设计指南
- `shot_terminology.md` — 景别/运镜/转场/构图术语词典
- `mood_keywords_library.md` — 情绪氛围关键词库（情绪→视觉映射）
- `video_style_guide.md` — AI视频风格指南（含平台适配与负面关键词）
- `consistency_control.md` — 一致性控制指南（seed prompt 体系与质检清单）
- `prompt_patterns.md` — 高效提示词模式库（结构公式与场景模板）
- `seedance_prompt_templates.md` — Seedance 2.0 爆款提示词模板库（18个模板 A-R，覆盖8大主题，含真实高分案例）
- `seedance_compliance.md` — Seedance 2.0 违禁词与合规规范（版权替换、限制词绕行）
- `seedance_vocab.md` — Seedance 2.0 词汇库（镜头语言、风格词汇、声音设计、图片风格匹配）
- `cjie_video_deconstruction_protocol.md` — 视频拆解与爆款重构协议（五维解构、微创新手术台、差异化公式、分阶段执行模板）
- `new_storyboard_reconstruction_architect_protocol.md` — 分镜重构架构师补充协议（分阶段输出、资产引用铁律、宫格批量模式、抽卡视频变体）

### assets/（模板资源）
- `character_profile_template.json` — 角色档案完整 JSON 结构（含 seed_prompt 模板与一致性检查清单）
- `storyboard_template.csv` — 分镜表格模板（含6镜头示例数据）
- `prompt_cheatsheet.md` — 提示词速查表（可打印）
- `c7_quality_gate_template.json` — 模式C硬性自检结构化模板（机审网关判定 JSON）
- `export_template.html` — HTML 可视化导出模板
- `example_input.txt` — 端到端示例：输入剧本
- `example_output.md` — 端到端示例：完整输出

## 质量评分标准

| 维度 | 权重 | 评分标准 |
|------|------|----------|
| 完整性 | 30% | 是否包含 WHO/WHAT/WHERE/WHEN/HOW/QUALITY 六要素 |
| 一致性 | 25% | 角色/场景/光线种子词是否贯穿所有相关镜头 |
| 精确性 | 20% | 描述是否具体（如 "navy blue blazer" 而非 "dark jacket"） |
| 简洁性 | 15% | 是否在200词以内，无冗余重复 |
| 可用性 | 10% | 是否包含质量增强词和负面排除词 |

合格阈值：总分 ≥ 0.7（满分1.0）

## 反馈与迭代

### 用户反馈收集

当用户使用生成的提示词后，收集以下反馈：
- 视频生成效果评分（1-5）
- 角色一致性评分（1-5）
- 需要修改的具体镜头编号和问题描述

### 迭代优化策略

根据反馈调整：
1. **角色不一致** → 增强种子词中的核心特征权重，将关键特征前置
2. **场景偏差** → 增加空间元素的具体方位描述
3. **氛围不符** → 调整情绪关键词组合，参考 [references/mood_keywords_library.md](references/mood_keywords_library.md)
4. **动作不自然** → 简化动作描述，添加 `natural movement, smooth motion`
5. **整体风格跳变** → 统一所有镜头的风格关键词尾缀

## 更新日志

- **v3.1.3**（2026-03-01）：新增模式C结构化 JSON 机审模板（C9），提供 `assets/c7_quality_gate_template.json` 供自动质检网关直接消费
- **v3.1.2**（2026-03-01）：新增模式C硬性自检模板（资产一致性/分阶段输出/宫格模式/抽卡变体）与“质检成果清单”固定输出格式
- **v3.1.1**（2026-03-01）：融合 new 分镜重构协议，补充模式C执行铁律与双协议引用
- **v3.1.0**（2026-03-01）：融合 CJie 视频拆解协议，新增模式C（对标视频拆解与爆款重构），补充触发词与执行框架
- **v3.0.0**（2026-03-01）：自我进化系统 v2 — 14模块企业级实现，含供应链安全、事务级快照、PII脱敏、记忆衰减、规则分级反驳、72h心跳、跨环境降级
- **v2.0.0**（2026-03-01）：融合 Seedance 2.0 提示词生成能力，新增模式B直接生成、SCELA公式、18个爆款模板、合规检查、平台参数速查
- **v1.1.0**（2026-03-01）：状态机解析器、元素驱动分镜、安全防护、跨调用状态重置、30个回归测试
- **v1.0.0**（2026-03-01）：初始版本，完整6步工作流程

---

## 进化系统 (Self-Evolution v2.0)

当用户输入以 `/evolve` 开头时，触发进化系统命令：

| 命令 | 功能 |
|------|------|
| `/evolve status` | 显示进化系统状态（记忆条目数、快照数、最近事件） |
| `/evolve learn` | 强制从最近输出中学习模式 |
| `/evolve rollback [id]` | 列出快照并回滚到指定版本 |
| `/evolve memory` | 查看/管理存储的偏好和模式 |
| `/evolve health` | 运行完整性检查 |
| `/evolve export` | 一键打包分发（含敏感信息扫描） |
| `/evolve log` | 查看最近进化日志 |
| `/evolve reset --confirm` | 清除所有进化数据（需确认） |

### 自动行为
每次生成后自动执行：
1. 质量自检（SCELA + 合规 + 一致性），不合格自动重试最多3次
2. 分析提示词模式，提取高分模式存入模式库
3. 高质量输出（>0.85）自动归档为参考案例
4. PII 脱敏后存储，记录进化日志

### 安全机制
- 供应链安全：仓库白名单 + 版本固定 + SHA-256 校验 + dry-run
- 事务级快照：两阶段提交 + 失败自动回滚 + 一致性校验
- 隐私边界：学习字段白名单 + 敏感文件/内容检测 + 打包前扫描
- 记忆治理：衰减(0.95^天) + 压缩(可追溯) + 冲突分级(高影响→用户确认)
- 规则反驳：hard_deny(拒绝) / soft_warn(警告) / suggest_alternative(建议)

### 核心文件
- `evolution/core.py` — EvolveEngine 编排器
- `evolution/snapshot.py` — 事务级快照与回滚
- `evolution/security.py` — PII脱敏 + 记忆衰减 + 注入防护
- `evolution/repair.py` — 供应链安全自修复
- `evolution/rules.py` — 规则内化 + 三级反驳
- `evolution/memory.py` — 持久记忆存储
- `evolution/env_detect.py` — 跨环境检测与降级
- 详见 `docs/evolution_protocol.md` 和 `docs/evolution_threat_model.md`
