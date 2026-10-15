#!/usr/bin/env python3
"""Local, privacy-minimized lead ledger for chat-based sales assistance."""

from __future__ import annotations

import argparse
import csv
import json
import os
import re
import sys
import tempfile
import uuid
from collections import Counter
from datetime import date, datetime
from pathlib import Path
from typing import Any


STAGES = {"needs_reply", "waiting_customer", "in_progress", "closed"}
REPLY_STATES = {"draft", "owner_approved", "sent", "not_sent"}
QUOTE_STATES = {"not_ready", "needs_owner_approval", "approved", "sent"}
OWNER_ONLY_REPLY_STATES = {"owner_approved", "sent"}
OWNER_ONLY_QUOTE_STATES = {"approved", "sent"}
OWNER_ONLY_STAGES = {"in_progress", "closed"}
PII_KEYS = {
    "name",
    "real_name",
    "phone",
    "mobile",
    "email",
    "student_id",
    "school_account",
    "address",
    "payment_account",
    "wechat_id",
    "id_card",
    "bank_card",
    "qq_number",
    "original_chat",
    "attachment",
    "姓名",
    "真实姓名",
    "手机号",
    "邮箱",
    "学号",
    "地址",
    "支付账号",
    "微信号",
    "身份证号",
    "银行卡号",
    "QQ号",
    "原始聊天",
    "附件",
}
CSV_FIELDS = [
    "lead_id",
    "customer_alias",
    "source",
    "service_type",
    "stage",
    "substatus",
    "summary",
    "deadline_at",
    "last_contact_at",
    "next_follow_up_at",
    "reply_state",
    "quote_state",
    "risk_flags",
    "next_action",
    "notes",
    "updated_at",
]


class LedgerError(ValueError):
    pass


def emit(payload: Any) -> None:
    print(json.dumps(payload, ensure_ascii=False, indent=2))


def atomic_write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="") as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_name, path)
    finally:
        if os.path.exists(temp_name):
            os.unlink(temp_name)


def ensure_store(store: Path) -> None:
    store.mkdir(parents=True, exist_ok=True)
    leads_path = store / "leads.json"
    changes_path = store / "changes.jsonl"
    if not leads_path.exists():
        atomic_write_text(leads_path, "[]\n")
    if not changes_path.exists():
        atomic_write_text(changes_path, "")
    write_csv(store, load_leads(store))


def load_leads(store: Path) -> list[dict[str, Any]]:
    path = store / "leads.json"
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise LedgerError(f"无法读取台账：{exc}") from exc
    if not isinstance(data, list) or not all(isinstance(item, dict) for item in data):
        raise LedgerError("leads.json 必须是客户卡对象数组")
    return data


def write_csv(store: Path, leads: list[dict[str, Any]]) -> None:
    rows: list[dict[str, str]] = []
    for lead in leads:
        row: dict[str, str] = {}
        for field in CSV_FIELDS:
            value = lead.get(field, "")
            if isinstance(value, (dict, list)):
                value = json.dumps(value, ensure_ascii=False, separators=(",", ":"))
            row[field] = str(value) if value is not None else ""
        rows.append(row)

    output = []
    from io import StringIO

    stream = StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=CSV_FIELDS, lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    output.append(stream.getvalue())
    atomic_write_text(store / "leads.csv", "".join(output))


def find_disallowed_key(value: Any, prefix: str = "") -> str | None:
    if isinstance(value, dict):
        for key, child in value.items():
            key_text = str(key)
            path = f"{prefix}.{key_text}" if prefix else key_text
            if key_text.lower() in PII_KEYS or key_text in PII_KEYS:
                return path
            found = find_disallowed_key(child, path)
            if found:
                return found
    elif isinstance(value, list):
        for index, child in enumerate(value):
            found = find_disallowed_key(child, f"{prefix}[{index}]")
            if found:
                return found
    return None


def validate_alias(alias: Any) -> str:
    if not isinstance(alias, str) or not alias.strip():
        raise LedgerError("customer_alias 必须使用非空客户代号")
    alias = alias.strip()
    if "@" in alias or re.search(r"\d{6,}", alias):
        raise LedgerError("customer_alias 疑似包含邮箱、手机号、学号或账号，请改用顾客A等代号")
    if len(alias) > 40:
        raise LedgerError("customer_alias 不能超过40个字符")
    return alias


def validate_record(
    record: dict[str, Any], actor: str, existing: dict[str, Any] | None = None
) -> dict[str, Any]:
    disallowed = find_disallowed_key(record)
    if disallowed:
        raise LedgerError(f"客户卡包含禁止保存的字段：{disallowed}")

    record = dict(record)
    record["customer_alias"] = validate_alias(record.get("customer_alias"))
    record.setdefault("source", "manual")
    record.setdefault("service_type", "other")
    record.setdefault("stage", "needs_reply")
    record.setdefault("substatus", "new")
    record.setdefault("summary", "")
    record.setdefault("known", {})
    record.setdefault("missing_fields", [])
    record.setdefault("reply_state", "draft")
    record.setdefault("quote_state", "not_ready")
    record.setdefault("risk_flags", [])
    record.setdefault("next_action", "")
    record.setdefault("notes", "")

    if record["stage"] not in STAGES:
        raise LedgerError(f"stage 无效：{record['stage']}")
    if record["reply_state"] not in REPLY_STATES:
        raise LedgerError(f"reply_state 无效：{record['reply_state']}")
    if record["quote_state"] not in QUOTE_STATES:
        raise LedgerError(f"quote_state 无效：{record['quote_state']}")
    if not isinstance(record["known"], dict):
        raise LedgerError("known 必须是对象")
    for field in ("missing_fields", "risk_flags"):
        if not isinstance(record[field], list) or not all(isinstance(item, str) for item in record[field]):
            raise LedgerError(f"{field} 必须是字符串数组")
    if not isinstance(record["summary"], str) or len(record["summary"]) > 500:
        raise LedgerError("summary 必须是500字符以内的文本")

    if actor != "owner":
        previous_reply = existing.get("reply_state") if existing else None
        previous_quote = existing.get("quote_state") if existing else None
        previous_stage = existing.get("stage") if existing else None
        if record["reply_state"] in OWNER_ONLY_REPLY_STATES and record["reply_state"] != previous_reply:
            raise LedgerError("只有 --actor owner 才能确认回复已批准或已发送")
        if record["quote_state"] in OWNER_ONLY_QUOTE_STATES and record["quote_state"] != previous_quote:
            raise LedgerError("只有 --actor owner 才能确认报价已批准或已发送")
        if record["stage"] in OWNER_ONLY_STAGES and record["stage"] != previous_stage:
            raise LedgerError("只有 --actor owner 才能确认客户已进入履约或结束状态")
        if previous_reply in OWNER_ONLY_REPLY_STATES and record["reply_state"] != previous_reply:
            raise LedgerError("assistant 不能覆盖卖家已确认的回复状态")
        if previous_quote in OWNER_ONLY_QUOTE_STATES and record["quote_state"] != previous_quote:
            raise LedgerError("assistant 不能覆盖卖家已确认的报价状态")
        if previous_stage in OWNER_ONLY_STAGES and record["stage"] != previous_stage:
            raise LedgerError("assistant 不能覆盖卖家已确认的客户阶段")

    lead_id = record.get("lead_id")
    if lead_id is None or lead_id == "":
        record["lead_id"] = f"lead_{date.today().strftime('%Y%m%d')}_{uuid.uuid4().hex[:8]}"
    elif not isinstance(lead_id, str) or not re.fullmatch(r"[A-Za-z0-9_-]{3,80}", lead_id):
        raise LedgerError("lead_id 只能包含字母、数字、下划线和连字符，长度3至80")

    record["updated_at"] = datetime.now().astimezone().isoformat(timespec="seconds")
    return record


def append_change(store: Path, actor: str, action: str, record: dict[str, Any]) -> None:
    event = {
        "changed_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "actor": actor,
        "action": action,
        "lead_id": record["lead_id"],
        "record": record,
    }
    with (store / "changes.jsonl").open("a", encoding="utf-8", newline="") as handle:
        handle.write(json.dumps(event, ensure_ascii=False, separators=(",", ":")) + "\n")


def parse_moment(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    text = value.strip().replace("Z", "+00:00")
    try:
        if re.fullmatch(r"\d{4}-\d{2}-\d{2}", text):
            return datetime.fromisoformat(text + "T23:59:59").astimezone()
        moment = datetime.fromisoformat(text)
        if moment.tzinfo is None:
            moment = moment.astimezone()
        return moment
    except ValueError:
        return None


def cmd_init(args: argparse.Namespace) -> None:
    store = Path(args.store).expanduser().resolve()
    ensure_store(store)
    emit({"status": "initialized", "store": str(store), "files": ["leads.json", "leads.csv", "changes.jsonl"]})


def cmd_upsert(args: argparse.Namespace) -> None:
    store = Path(args.store).expanduser().resolve()
    ensure_store(store)
    try:
        payload = json.loads(Path(args.input).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise LedgerError(f"无法读取客户卡输入：{exc}") from exc
    if not isinstance(payload, dict):
        raise LedgerError("客户卡输入必须是 JSON 对象")

    leads = load_leads(store)
    requested_id = payload.get("lead_id")
    index = next((i for i, item in enumerate(leads) if item.get("lead_id") == requested_id), None)
    existing = leads[index] if index is not None else None
    merged = dict(existing) if existing else {}
    merged.update(payload)
    if existing and isinstance(existing.get("known"), dict) and isinstance(payload.get("known"), dict):
        merged["known"] = {**existing["known"], **payload["known"]}
    record = validate_record(merged, args.actor, existing)
    if index is None:
        action = "created"
        leads.append(record)
    else:
        action = "updated"
        leads[index] = record
    leads.sort(key=lambda item: str(item.get("lead_id", "")))
    atomic_write_text(store / "leads.json", json.dumps(leads, ensure_ascii=False, indent=2) + "\n")
    write_csv(store, leads)
    append_change(store, args.actor, action, record)
    emit({"status": action, "record": record})


def cmd_due(args: argparse.Namespace) -> None:
    store = Path(args.store).expanduser().resolve()
    ensure_store(store)
    if args.at:
        target = parse_moment(args.at)
        if target is None:
            raise LedgerError("--at 必须是 ISO 日期或时间")
    else:
        target = datetime.now().astimezone()
    due = []
    for lead in load_leads(store):
        moment = parse_moment(lead.get("next_follow_up_at"))
        if moment is not None and moment <= target and lead.get("stage") != "closed":
            due.append(lead)
    emit({"as_of": target.isoformat(timespec="seconds"), "count": len(due), "leads": due})


def cmd_summary(args: argparse.Namespace) -> None:
    store = Path(args.store).expanduser().resolve()
    ensure_store(store)
    leads = load_leads(store)
    emit(
        {
            "total": len(leads),
            "by_stage": dict(Counter(str(item.get("stage", "unknown")) for item in leads)),
            "by_substatus": dict(Counter(str(item.get("substatus", "unknown")) for item in leads)),
            "notice": "未主动粘贴、截图或上传到系统的微信、闲鱼等消息不在本次统计中",
        }
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="维护脱敏客户台账")
    subparsers = parser.add_subparsers(dest="command", required=True)

    init_parser = subparsers.add_parser("init", help="初始化台账目录")
    init_parser.add_argument("--store", required=True)
    init_parser.set_defaults(func=cmd_init)

    upsert_parser = subparsers.add_parser("upsert", help="新建或更新客户卡")
    upsert_parser.add_argument("--store", required=True)
    upsert_parser.add_argument("--input", required=True)
    upsert_parser.add_argument("--actor", choices=("assistant", "owner"), required=True)
    upsert_parser.set_defaults(func=cmd_upsert)

    due_parser = subparsers.add_parser("due", help="查看到期跟进")
    due_parser.add_argument("--store", required=True)
    due_parser.add_argument("--at", help="ISO 日期或时间；默认当前时间")
    due_parser.set_defaults(func=cmd_due)

    summary_parser = subparsers.add_parser("summary", help="汇总客户状态")
    summary_parser.add_argument("--store", required=True)
    summary_parser.set_defaults(func=cmd_summary)
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    try:
        args.func(args)
        return 0
    except LedgerError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
