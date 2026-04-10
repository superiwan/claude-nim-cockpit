# Claude Code NVIDIA 账号管理器

这是一个本地桌面小工具，用来管理 Claude Code 当前的 NVIDIA NIM / LiteLLM 接入配置，避免手动编辑 `litellm.config.yaml`。

## 启动

在当前目录运行：

```powershell
python .\model_account_manager.py
```

如果提示缺少 `customtkinter`，先安装：

```powershell
python -m pip install customtkinter
```

也可以直接双击当前目录里的：

```text
启动 NVIDIA Cockpit.cmd
```

桌面上也会有快捷方式：

```text
Claude NVIDIA Cockpit.lnk
```

## 它能做什么

- 显示 NVIDIA 账号池
- 使用类似 Cockpit Tools 的卡片式桌面面板
- 新增、编辑、删除账号
- 给每个账号选择要映射到 Claude Code 的哪个档位：Default、Sonnet、Opus、Haiku 或 Custom
- 给每个账号选择或输入真实 NVIDIA NIM 模型
- 一个账号可以拥有多条映射
- 选择账号后，中间只显示当前账号的映射
- 点击 `+ 新增此账号的映射` 可以给当前账号增加新的 Claude 档位映射
- 也可以手动输入 NVIDIA NIM 模型名并检测是否可用
- 允许多个账号绑定到同一个模型
- 设置账号权重
- 生成并应用 LiteLLM 配置
- 应用前自动备份旧配置
- 重启 LiteLLM
- 查询 `http://127.0.0.1:4000/v1/models` 验证网关
- 检测单个账号是否可用
- 记录估算请求数、最近检测时间、疑似限流状态

## 数据和配置位置

账号元数据保存在：

```text
C:\Users\prohibit\.claude\nim-bridge\account-manager.json
```

API Key 不写入这个 JSON 文件，而是写入 Windows 用户级环境变量。账号元数据里只保存环境变量名。

LiteLLM 配置写入：

```text
C:\Users\prohibit\.claude\litellm.config.yaml
```

配置备份写入：

```text
C:\Users\prohibit\.claude\nim-bridge\backups
```

## 使用流程

1. 运行 `python .\model_account_manager.py`
2. 点击 `新增账号`
3. 填写账号名称和 NVIDIA API Key
4. 在中间 `Claude Code 映射总览` 点击 `+ 新增此账号的映射`
5. 选择这个映射要对应的 Claude Code 档位，例如 `Haiku`
6. 选择或手动输入真实 NVIDIA NIM 模型，例如 `z-ai/glm5`
7. 设置权重
8. 点击 `检测` 或 `检测全部账号`
9. 确认账号显示为 `可用`
10. 点击 `应用配置并重启 LiteLLM`
11. 等待日志显示 LiteLLM 重启和模型列表验证结果

## 账号和映射关系

账号池只负责管理账号本身。

每个账号下面可以有多条映射，例如：

```text
账号 A
- Sonnet -> stepfun-ai/step-3.5-flash
- Haiku -> z-ai/glm5
- Opus -> minimax-m2.5
```

同一个账号下，同一个 Claude 档位只能有一条映射；不同账号可以映射到同一个 Claude 档位，用于 LiteLLM 分流。

注意：界面里会显示原版 Claude 档位名，例如 `sonnet`、`opus`、`haiku`。但为了兼容 Claude Code 下拉框有时仍发送的旧名称，生成 LiteLLM 配置时会额外保留兼容别名：

- `Sonnet` 同时生成 `sonnet` 和 `sonnet-glm5`
- `Opus` 同时生成 `opus` 和 `opus-minimax`
- `Haiku` 同时生成 `haiku` 和 `haiku-kimi`
- `Default` 会生成你选的真实默认模型名；如果不是 `step-3.5-flash`，也会额外保留 `step-3.5-flash`

这样 Claude Code 无论请求新名字还是旧名字，LiteLLM 都能接住。

## Claude 档位映射说明

Claude Code 的模型选择列表里有 `Default`、`Sonnet`、`Opus`、`Haiku` 等档位。这个工具会把你选择的档位映射到 LiteLLM 的模型组名：

- `Default` -> 你在这一行选择的 NVIDIA 实际模型名
- `Sonnet` -> `sonnet`
- `Opus` -> `opus`
- `Haiku` -> `haiku`
- `Custom` -> 你自己填写的 Claude 模型名

例如你选择一个账号映射到 `Haiku`，真实 NVIDIA 模型填 `z-ai/glm5`，生成配置后就是：

```yaml
- model_name: haiku
  litellm_params:
    model: nvidia_nim/z-ai/glm5
```

这样你在 Claude Code 里选择 `Haiku`，实际会走这个账号和这个 NVIDIA 模型。

如果你选择 `Default`，真实 NVIDIA 模型填 `minimax-m2.5`，应用配置后会同时把 `ANTHROPIC_MODEL` 设置为 `minimax-m2.5`，并生成：

```yaml
- model_name: minimax-m2.5
  litellm_params:
    model: nvidia_nim/minimaxai/minimax-m2.5
```

这样你在 Claude Code 里选择 `Default` 时，当前默认模型名也会对应到 `minimax-m2.5`。

## 账号显示说明

应用会从现有用户环境变量导入账号，但只会把不同的 API Key 识别成不同账号。

如果你的 `NVIDIA_NIM_API_KEY_1/2/3` 暂时都是同一个 key，界面只会显示一个已导入账号，避免误导你以为有三个不同账号。

旧版生成过的 `NVIDIA 账号 1/2/3` 会在加载时自动按真实 key 去重；如果三个环境变量实际是同一个 key，就只保留一个账号。

## 权重说明

同一个模型下可以有多个账号。

权重越高，被 LiteLLM 选中的概率越大。例如：

- 账号 A 权重 `6`
- 账号 B 权重 `3`
- 账号 C 权重 `1`

大致表示 A/B/C 的分流比例接近 `6:3:1`。

## 账号健康状态

点击 `检测选中账号` 会直接调用 NVIDIA NIM 的 OpenAI-compatible 接口，验证该账号是否能调用当前绑定模型。

状态含义：

- `可用`：最近一次检测成功
- `不可用：疑似限流`：最近一次检测返回 HTTP 429
- `不可用：HTTP xxx`：接口返回了其他 HTTP 错误
- `不可用`：网络或其他异常

表格里有单独的 `可用性` 列，会明确显示 `可用`、`不可用` 或 `未检测`。

`估算请求` 只记录这个管理器主动检测产生的请求次数。它不是 NVIDIA 官方真实余额。

## 当前模型

内置 NVIDIA 实际模型：

- `z-ai/glm5` -> `nvidia_nim/z-ai/glm5`
- `minimaxai/minimax-m2.5` -> `nvidia_nim/minimaxai/minimax-m2.5`
- `moonshotai/kimi-k2.5` -> `nvidia_nim/moonshotai/kimi-k2.5`
- `stepfun-ai/step-3.5-flash` -> `nvidia_nim/stepfun-ai/step-3.5-flash`
- `kimi-k2.5` -> `nvidia_nim/moonshotai/kimi-k2.5`
- `glm5` -> `nvidia_nim/z-ai/glm5`
- `minimax-m2.5` -> `nvidia_nim/minimaxai/minimax-m2.5`

你也可以手动输入模型名。例如输入：

```text
z-ai/glm5
```

应用会按下面的 LiteLLM 模型写法生成配置：

```text
nvidia_nim/z-ai/glm5
```

## 注意

- 这是第一版最小实现，暂不做登录、云同步、多供应商、复杂报表。
- 如果应用配置后 Claude Code 没读到新设置，请重开 Claude / VSCode / 终端。
- 如果 Claude Code 仍显示旧名字，例如 `sonnet-glm5`，说明当前 VSCode/Claude Code 进程还拿着旧环境变量；请完整关闭并重开 VSCode 后再选模型。
- 如果账号检测失败但模型列表验证成功，说明 LiteLLM 网关正常，问题更可能是该账号、该模型或 NVIDIA 侧限制。
- 如果检测返回 `不可用：模型不存在或无权限`，通常是 NVIDIA 模型 ID 写错，或者这个账号没有该模型权限。例如不要只写 `deepseek-v3.2`，优先试 `deepseek-ai/deepseek-v3.2`。
- `应用配置并重启` 和账号检测现在会在后台运行。NVIDIA API 或 LiteLLM 重启可能需要十几秒到一分钟，期间界面不会再卡死，结果会写到日志里。
