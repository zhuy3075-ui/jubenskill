# 示例输出：咖啡厅相遇

> 由 [assets/example_input.txt](example_input.txt) 生成

---

## 一、项目元数据

| 字段 | 值 |
|------|-----|
| 片名 | 示例短剧 |
| 场次数 | 2 |
| 总镜头数 | 11 |
| 预估总时长 | 42秒 |
| 角色数 | 2 |

## 二、风格总设定

```
视频风格: cinematic, photorealistic
画面比例: 16:9
色彩体系: warm earth tones, golden hour palette
光影风格: natural soft lighting, warm color temperature
质量关键词: high quality, detailed, cinematic, professional, sharp focus
负面关键词: blurry, distorted, low quality, artifacts, flickering
```

## 三、角色设定库

### 角色1：林晓薇

```json
{
  "name": "林晓薇",
  "name_en": "Xiaowei",
  "role": "主角",
  "appearance": {
    "age": "28",
    "gender": "female",
    "ethnicity": "Asian Chinese",
    "body_type": "slim",
    "hair": { "style": "long, slightly wavy", "color": "dark brown" },
    "face_shape": "oval",
    "skin_tone": "fair"
  },
  "costumes": [
    {
      "scene_range": "1",
      "description": "white blouse, high-waisted black trousers",
      "accessories": ["smartphone"]
    },
    {
      "scene_range": "2",
      "description": "same as scene 1, plus a letter in hand"
    }
  ],
  "seed_prompt": "[CHARACTER:林晓薇] Asian female late twenties, slim, long dark wavy hair, oval face, fair skin, consistent appearance, same person, maintaining identity"
}
```

### 角色2：陈宇

```json
{
  "name": "陈宇",
  "name_en": "Chenyu",
  "role": "配角",
  "appearance": {
    "age": "30",
    "gender": "male",
    "ethnicity": "Asian Chinese",
    "body_type": "average, fit",
    "hair": { "style": "short, neat", "color": "black" },
    "face_shape": "angular",
    "skin_tone": "medium"
  },
  "costumes": [
    {
      "scene_range": "1",
      "description": "navy blue casual blazer, white shirt underneath, dark trousers"
    }
  ],
  "seed_prompt": "[CHARACTER:陈宇] Asian male early thirties, fit build, short black hair, angular face, friendly expression, consistent appearance, same person, maintaining identity"
}
```

## 四、场景设定库

### 场景1：咖啡厅内

```json
{
  "scene_heading": "INT. 咖啡厅 - 早晨",
  "environment": {
    "type": "interior",
    "location_en": "modern urban coffee shop",
    "key_elements": ["large floor-to-ceiling windows", "warm pendant lights", "wooden tables", "latte on table"]
  },
  "lighting": {
    "type": "mixed",
    "natural_source": "morning sunlight through large windows",
    "artificial_source": "warm pendant lights",
    "color_temperature": "warm golden",
    "quality": "soft, inviting"
  },
  "atmosphere": {
    "mood": "cozy, warm, intimate",
    "color_palette": ["warm browns", "golden yellows", "cream"]
  },
  "seed_prompt": "[SCENE:咖啡厅] modern coffee shop interior, large windows with morning sunlight, warm pendant lights, wooden tables, cozy earth tones, consistent environment, maintaining location",
  "lighting_seed": "[LIGHTING:咖啡厅早晨] mixed natural and warm artificial lighting, soft morning sunlight from large windows, warm golden tones, medium soft intensity, consistent lighting throughout scene"
}
```

### 场景2：公司天台

```json
{
  "scene_heading": "EXT. 公司天台 - 黄昏",
  "environment": {
    "type": "exterior",
    "location_en": "office building rooftop at dusk",
    "key_elements": ["metal railing", "city skyline in distance", "open sky"]
  },
  "lighting": {
    "type": "natural",
    "natural_source": "golden hour sunset light",
    "direction": "from west, low angle",
    "color_temperature": "warm orange-golden",
    "quality": "dramatic, warm"
  },
  "atmosphere": {
    "mood": "melancholic, contemplative, bittersweet",
    "color_palette": ["orange", "deep red", "purple-blue sky"]
  },
  "seed_prompt": "[SCENE:天台] office rooftop at sunset, metal railing, city skyline background, open sky, golden hour light, consistent environment, maintaining location",
  "lighting_seed": "[LIGHTING:天台黄昏] natural golden hour lighting, low angle sunset from west, warm orange-golden tones, dramatic intensity, long shadows, consistent lighting throughout scene"
}
```

## 五、完整分镜提示词

### 场景1：咖啡厅内 - 早晨（7镜头，约25秒）

| 镜号 | 景别 | 运镜 | 角色 | 时长 | 转场 |
|------|------|------|------|------|------|
| 1-1 | ELS | Static | — | 3s | fade in |
| 1-2 | MS | Push In | 林晓薇 | 4s | cut |
| 1-3 | CU | Static | 林晓薇 | 2s | cut |
| 1-4 | MS | Tracking | 陈宇 | 3s | cut |
| 1-5 | OTS | Static | 林晓薇/陈宇 | 4s | cut |
| 1-6 | CU | Static | 林晓薇 | 3s | cut |
| 1-7 | 2S | Slow Push In | 林晓薇/陈宇 | 5s | dissolve |

**镜头 1-1** 建立镜头
```
extreme long shot, establishing shot of modern coffee shop exterior, morning sunlight, warm inviting atmosphere, cozy urban cafe with large windows, cinematic, high quality, consistent environment
```

**镜头 1-2** 女主出场
```
medium shot, [CHARACTER:林晓薇] young Asian woman with long dark wavy hair, wearing white blouse and black trousers, sitting by window in coffee shop, looking outside with contemplative expression, latte on table, warm morning light from window, soft side lighting, cozy earth tones, push in camera movement, shallow depth of field, cinematic, high quality, consistent appearance, same person
```

**镜头 1-3** 情绪特写
```
close-up, [CHARACTER:林晓薇] young Asian woman, long dark wavy hair, looking at smartphone then sighing softly, gentle melancholic expression, soft warm side lighting from window, bokeh background of coffee shop interior, emotional, cinematic portrait, high quality, consistent appearance
```

**镜头 1-4** 男主入场
```
medium shot, [CHARACTER:陈宇] Asian man early thirties with short black hair, wearing navy blue casual blazer, pushing open coffee shop door, looking around then smiling, warm interior lighting, tracking shot following movement, natural motion, cinematic, high quality, consistent appearance, same person
```

**镜头 1-5** 对话开始
```
over-the-shoulder shot from behind [CHARACTER:林晓薇], focusing on [CHARACTER:陈宇] sitting down with friendly smile, coffee shop table between them, warm ambient pendant lighting, intimate conversational framing, cinematic, high quality, consistent appearance, consistent environment
```

**镜头 1-6** 女主反应
```
close-up, [CHARACTER:林晓薇] young Asian woman, putting away smartphone, gentle warm smile with dimples, soft warm lighting, bokeh background, relieved happy expression, cinematic portrait, high quality, consistent appearance
```

**镜头 1-7** 双人温馨
```
medium two-shot, [CHARACTER:林晓薇] and [CHARACTER:陈宇] sitting across cafe table, smiling at each other, warm romantic atmosphere, golden morning window light, soft focus background, slow push in, intimate warm mood, cinematic, high quality, consistent appearance, consistent environment
```

### 场景2：公司天台 - 黄昏（4镜头，约17秒）

| 镜号 | 景别 | 运镜 | 角色 | 时长 | 转场 |
|------|------|------|------|------|------|
| 2-1 | ELS | Static | — | 3s | dissolve |
| 2-2 | MS | Static | 林晓薇 | 5s | cut |
| 2-3 | CU | Slow Pull Out | 林晓薇 | 4s | cut |
| 2-4 | LS | Static | — | 5s | fade out |

**镜头 2-1** 建立镜头
```
extreme long shot, office building rooftop at golden hour sunset, city skyline silhouette in background, orange and purple sky, dramatic sunset lighting, epic cinematic wide angle, high quality, consistent environment
```

**镜头 2-2** 天台独白
```
medium shot, [CHARACTER:林晓薇] young Asian woman with long dark wavy hair, standing alone by rooftop railing, wind blowing hair, holding a folded letter, complex contemplative expression, golden hour sunset backlighting creating warm rim light, city skyline background, melancholic bittersweet mood, cinematic, high quality, consistent appearance, same person
```

**镜头 2-3** 情绪特写
```
close-up, [CHARACTER:林晓薇] face in golden sunset light, whispering to herself, eyes glistening with emotion, warm orange light on face with cool blue shadow side, wind-blown hair, deep contemplative expression, slow pull out camera movement, emotional cinematic portrait, high quality, consistent appearance
```

**镜头 2-4** 结尾空镜
```
long shot, empty rooftop after person leaves, metal railing in foreground, sunset sinking below city skyline horizon, orange sky fading to deep blue, lonely melancholic atmosphere, static camera, cinematic, beautiful, high quality, fade out, consistent environment
```

## 六、一致性参考表

| 类型 | ID | 种子词 |
|------|-----|--------|
| 角色 | 林晓薇 | `[CHARACTER:林晓薇] Asian female late twenties, slim, long dark wavy hair, oval face, fair skin, consistent appearance, same person, maintaining identity` |
| 角色 | 陈宇 | `[CHARACTER:陈宇] Asian male early thirties, fit build, short black hair, angular face, friendly expression, consistent appearance, same person, maintaining identity` |
| 场景 | 咖啡厅 | `[SCENE:咖啡厅] modern coffee shop interior, large windows, warm pendant lights, wooden tables, cozy earth tones, consistent environment` |
| 场景 | 天台 | `[SCENE:天台] office rooftop at sunset, metal railing, city skyline, open sky, golden hour light, consistent environment` |
| 光线 | 咖啡厅早晨 | `[LIGHTING:咖啡厅早晨] mixed warm lighting, soft morning sunlight from windows, warm golden tones, consistent lighting` |
| 光线 | 天台黄昏 | `[LIGHTING:天台黄昏] golden hour sunset, low angle from west, warm orange tones, dramatic, consistent lighting` |

## 七、质量报告

| 指标 | 结果 |
|------|------|
| 平均提示词质量分 | 0.84 |
| 角色一致性通过率 | 11/11 (100%) |
| 场景一致性通过率 | 11/11 (100%) |
| 光线一致性通过率 | 11/11 (100%) |
| 待修正项 | 无 |
