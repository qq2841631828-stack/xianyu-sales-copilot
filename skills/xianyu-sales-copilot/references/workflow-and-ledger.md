# 工作流与台账

## 何时需要台账

单次截图或临时咨询不强制建卡。用户要长期跟进、多客户切换、记录已报价范围或查看待办时才使用台账。每位客户使用独立代号，不根据微信昵称或相似需求自动合并。

## 四个主状态

- `needs_reply`：有一条客户问题需要卖家处理
- `waiting_customer`：等客户回复、补材料或确认范围
- `in_progress`：卖家已明确确认合作，正在履约、验收或售后
- `closed`：卖家已明确确认结束、拒绝或无需跟进

推荐 `substatus`：

- `new`：当前材料中第一次出现
- `needs_info`：缺少决定范围的关键信息
- `scope_review`：正在核对交付物与边界
- `ready_for_quote`：信息基本齐全，可由卖家定价
- `waiting_quote_approval`：报价草稿待卖家确认
- `quoted`：卖家明确确认报价已发出
- `negotiating`：客户在讨论价格或范围
- `waiting_payment_confirmation`：客户表达付款意向，但卖家未确认到账
- `delivery`：卖家明确确认已进入履约
- `waiting_acceptance`：已交付，等待客户验收
- `revision`：在原确认范围内修改
- `after_sales`：投诉、退款或其他售后处理中
- `repurchase`：历史客户提出新需求，仍需重新确认本次范围
- `paused`：双方明确暂缓
- `declined`：卖家明确不承接

“好的”“谢谢”“价格知道了”“我考虑一下”都不等于成交或付款。只有用户明确确认事实，才能进入 `in_progress`、`closed` 或其他已发生状态。

## 每次咨询的处理

1. 读取最近聊天，确认说话人、顺序、客户当前问题和业务类型。
2. 提取直接证据，区分已知、待确认与 AI 判断。
3. 默认直接给一条可复制的短回复；仅确认或致谢时可简短回应，也可建议卖家先不用回。
4. 信息缺口与下一动作在内部判断，不要求每轮列出；关键冲突或新增承诺需要卖家决策时，才在回复外附一句提醒。用户明确要求分析或客户卡时再展开。
5. 如需保存，先展示客户卡预览；用户确认后再写入。
6. 用户确认已发送后，才把 `reply_state` 记为 `sent` 并按事实调整阶段；不能因为生成了回复而标记已发送。
7. 用户明确确认报价、成交、付款、交付、退款或结束后，才更新对应事实。

## 报价前范围确认卡

复杂项目报价前，先在内部核对：

```text
用途/场景：
交付物：
包含：
不包含：
客户需提供：
验收口径：
时间与中途确认节点：
修改边界：
金额：待卖家确认
```

不必一次向客户发送整张卡。先使用前文已确认的信息，只有缺项会影响本轮判断时才逐步补问；不要因为卡上还有空项就继续盘问。客户确认范围后再报价，可减少“我以为包含”的争议。所有“待卖家确认”都是内部状态，不直接作为客户话术。

## 客户卡字段

```json
{
  "lead_id": "由脚本生成或沿用",
  "customer_alias": "顾客A",
  "source": "wechat | xianyu | manual | other",
  "service_type": "h5 | data_visualization | ppt_document | research | commercial_copy | ai_video | academic_support | other",
  "stage": "needs_reply | waiting_customer | in_progress | closed",
  "substatus": "当前细分阶段",
  "summary": "不含身份信息的需求摘要",
  "known": {
    "只记录聊天中有证据的业务事实": "值"
  },
  "missing_fields": ["当前缺失信息"],
  "deadline_at": "YYYY-MM-DD 或完整时间，未知则省略",
  "last_contact_at": "YYYY-MM-DD 或完整时间，未知则省略",
  "next_follow_up_at": "YYYY-MM-DD 或完整时间，未约定则省略",
  "reply_state": "draft | owner_approved | sent | not_sent",
  "quote_state": "not_ready | needs_owner_approval | approved | sent",
  "risk_flags": ["只写中性、可观察的风险"],
  "next_action": "唯一下一步动作",
  "notes": "必要的内部备注"
}
```

客户代号不得使用手机号、学号、真实姓名或支付账号。`summary` 不粘贴原始聊天，不保存与成交无关的个人信息。

## 台账脚本

新建台账：

```text
python scripts/lead_tracker.py init --store <台账目录>
```

新建或更新客户卡：

```text
python scripts/lead_tracker.py upsert --store <台账目录> --input <客户卡.json> --actor assistant
```

用户明确确认“已发送”“已报价”或其他事实后，用 `--actor owner` 记录对应更新。不要提前标记；沿用前文条件起草不需要自动建卡或改写台账。客户付款截图或客户自述不能替代卖家确认到账、交付或退款。金额获准但未确认已发出时，只可记为 `approved`，不能记为 `sent`。

查看今日到期跟进：

```text
python scripts/lead_tracker.py due --store <台账目录>
```

查看总体情况：

```text
python scripts/lead_tracker.py summary --store <台账目录>
```

脚本会维护 `leads.json`、便于查看的 `leads.csv` 和只追加的 `changes.jsonl`。它没有删除命令，也不会保存原始聊天。

## 跟进规则

生成提醒不等于自动发送。优先遵守已经约定的联系时间；没有约定时，只在有新信息、客户所需资料、报价有效信息或真实排期变化时建议一次跟进。客户明确拒绝或连续无回应后停止追问。

进度汇报只能基于已完成的实际节点，不能写“快好了”“一直在推进”等无法核实的话。每日收尾只汇总已进入台账的客户，并提示“未粘贴、截图或上传到系统的消息不在本次清单中”。
