# 大肥鱼 QQ 机器人

一个只和主人说话的 QQ 鲸鱼娘。基于 **NapCat**（OneBot 11 协议端）和 **DeepSeek API**，
人格取自 DeepSeek 社区梗里的大肥鱼。

```
QQ 小号  <--->  NapCat（协议端）  <--WebSocket-->  fish_bot.py  <--->  DeepSeek API
```

## 特性

- **只跟主人说话**：只处理主人私聊，群消息和陌生人的私聊一律静默丢弃
- **不白花钱**：过滤在调用 API 之前完成，陌生人发消息不产生费用
- **有上下文**：保留最近 40 条对话，重启即清空（也可改成落盘）
- **限流**：两条回复之间至少间隔 1 秒，防止刷屏
- **人格独立**：人设写在 `persona.md`，改文件即可换性格，不用动代码

## 前置条件

- Windows / Linux，Python 3.10+
- 一个 **QQ 小号**（不要用主号，第三方协议端有封号风险）
- [NapCat](https://github.com/NapNeko/NapCatQQ) 已安装并登录
- DeepSeek API Key（[platform.deepseek.com](https://platform.deepseek.com)）

## 第一步：配置 NapCat

1. 启动 NapCat，在 WebUI 里用 QQ 小号扫码登录
2. 打开 WebUI（默认 `http://127.0.0.1:6099`，登录 token 在启动日志里）
3. **网络配置 → 新建 → WebSocket 服务器**
   - Host：`127.0.0.1`
   - Port：`3001`
   - Token：留空（仅本机）或自己设一个，与 `config.json` 保持一致
4. 保存并启用

NapCat 现在会把所有 QQ 消息推送到 `ws://127.0.0.1:3001`。

## 第二步：安装并运行

```bash
pip install -r requirements.txt
copy config.example.json config.json   # Linux: cp
```

编辑 `config.json`，至少填两项：

```json
{
  "owner_qq": 你的QQ号,
  "deepseek_api_key": "sk-xxxx"
}
```

然后：

```bash
python fish_bot.py
```

也可以用环境变量代替 Key：

```bash
set DEEPSEEK_API_KEY=sk-xxxx   # PowerShell: $env:DEEPSEEK_API_KEY="sk-xxxx"
python fish_bot.py
```

## 配置项

| 字段 | 说明 |
|---|---|
| `owner_qq` | 主人 QQ 号，**必填**；只有这个号的消息会被回复 |
| `ws_url` | NapCat WebSocket 地址，默认 `ws://127.0.0.1:3001` |
| `ws_token` | 与 NapCat 里的 token 一致，留空表示不鉴权 |
| `deepseek_api_key` | DeepSeek Key；环境变量 `DEEPSEEK_API_KEY` 优先级更高 |
| `api_base` | 默认 `https://api.deepseek.com`，换代理/中转时改这里 |
| `model` | 默认 `deepseek-chat` |
| `max_tokens` | 单次回复上限，默认 80，太长就不像鱼了 |
| `temperature` | 默认 1.0，越高越跳脱 |
| `min_interval` | 两条回复的最小间隔（秒） |
| `max_history` | 保留的对话条数 |
| `persona_file` | 人设文件路径，默认 `persona.md` |

## 它为什么只听你的

三层过滤，全部在 `fish_bot.py` 里：

```python
if event.get("post_type") != "message":      # 只处理消息事件
    return
if event.get("message_type") != "private":   # 群消息直接丢
    return
if uid != int(self.cfg["owner_qq"]):         # 不是主人就静默，不调 API
    return
```

关键在**第三行判断在调用 DeepSeek 之前**——陌生人发一万条，账单也是 0。

补充建议：

- QQ 隐私设置里把「加我为好友」改成需要验证，避免陌生人加号后骚扰
- 不要在机器人号所在的群里启用这个脚本（脚本本身也会忽略群消息）
- 想让它以后能进群，需要额外加白名单逻辑并改写 `persona.md` 的群聊规则

## 费用

按 DeepSeek 官方价目表计费，一条回复通常几百 token，成本约几厘到几分钱。
想控成本：调小 `max_tokens`、调大 `min_interval`、少用 `deepseek-reasoner`。

## 自检

不联网、不连 NapCat 的冒烟测试，验证三层过滤：

```bash
python tests/smoke_test.py
```

预期输出：`smoke OK: 陌生人/群消息被忽略，主人消息到达 API`

## 常见问题

**连不上 NapCat**
检查 NapCat 的 WebSocket 服务器是否启用、端口是否被占用、`ws_url` 是否写对。

**回复「本鱼出错了…（HTTPStatusError）」**
多半是 Key 无效、余额不足或模型名不对。脚本会把具体异常类型打出来。

**`websockets.connect` 报 `unexpected keyword argument 'additional_headers'`**
`websockets` 版本太老，`pip install -U "websockets>=12"`。

**想换性格**
只改 `persona.md`，重启脚本即可。

## 目录结构

```
fish_bot.py         主程序：连 NapCat、过滤消息、调 DeepSeek
persona.md          人设 prompt
config.example.json 配置模板（复制成 config.json）
requirements.txt    Python 依赖
tests/smoke_test.py 离线冒烟测试（验证过滤）
```

`config.json` 已加入 `.gitignore`，不会把 Key 提交到仓库。
