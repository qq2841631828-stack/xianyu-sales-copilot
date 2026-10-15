# 微信与闲鱼聊单副驾驶

一个用于微信、闲鱼等一对一聊单的 Codex Skill。发送聊天截图或粘贴文字，默认得到一条自然、简短、可复制的回复，必要时另附一句给卖家的提醒。

## 安装

在 Codex 中使用 `skill-installer`，安装本仓库的 `skills/xianyu-sales-copilot` 目录。安装完成后，在新的聊天中调用 `$xianyu-sales-copilot`。

可以直接告诉 Codex：

```text
请使用 skill-installer 安装 https://github.com/qq2841631828-stack/xianyu-sales-copilot/tree/main/skills/xianyu-sales-copilot
```

也可以下载仓库，将完整的 `skills/xianyu-sales-copilot` 文件夹放入本机 Codex 的 skills 目录。同名旧版先备份，再更新。

## 使用

直接上传截图或粘贴聊天文字，并说：

```text
用 $xianyu-sales-copilot 帮我回复这个客户。
```

连续补充同一客户的聊天即可；更换客户时明确说“切换客户：顾客 B”。需要解释判断时说“先分析一下，再给我回复”。

## 回复方式

- 默认只给一个推荐回复，不列客户代号、处理状态和固定下一步。
- 先回答客户的问题，只有缺少关键信息时才补问，默认一次一个问题。
- 沿用同一客户本次对话里已经明确的价格、交期和范围，不反复确认。
- 客户只是致谢时，可以简单回应或建议暂时不用回。
- 没有批准的金额就不编报价，内部提醒与客户话术分开。

可用于 AI 视频、H5、数据新闻、PPT、文档与数据处理、资料检索、商业文案及学习辅导等咨询。

## 边界与台账

所有回复都是草稿，需要卖家自行发送；Skill 不自动读取收件箱，不执行报价发布、收款、退款或平台订单操作，也不新增未经卖家批准的承诺。

单次咨询不用建卡。只有用户需要持续跟进时，才按 [工作流与台账](skills/xianyu-sales-copilot/references/workflow-and-ledger.md) 使用 Python 3.10 或更高版本运行台账脚本。台账保存在仓库外的个人目录中，只记录脱敏业务摘要。

## 目录

```text
skills/xianyu-sales-copilot/
  SKILL.md
  agents/openai.yaml
  references/
  scripts/lead_tracker.py
```

具体规则见 [SKILL.md](skills/xianyu-sales-copilot/SKILL.md)。
