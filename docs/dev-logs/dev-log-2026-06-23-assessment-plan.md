# assessment 模块 — 题目生命周期与质量门禁开发计划

- 日期：2026-06-23
- 关联：`docs/architecture/end-to-end-implementation-plan.md` §8

## 当前问题

`create_item()` 和 `generate_quiz_session()` 默认设 `status=published`，AI 生成的未校验题目直接进入测验。与设计文档要求的 draft → reviewing → published 流程不一致，且无自检机制。

## 题目状态流转

```
                 ┌─────────┐
   AI 生成 ────→ │  draft  │ ←─── 手动创建
                 └────┬────┘
                      │
              ┌───────▼───────┐
              │  AI 自检       │
              │  · 选项互斥？  │
              │  · 答案唯一？  │
              │  · 有资料依据？│
              └───┬───────┬───┘
                  │       │
          通过 ←──┘       └──→ 不通过
           │                    │
    ┌──────▼──────┐    ┌───────▼───────┐
    │  published  │    │  draft        │
    │  可被测验    │    │  + validation │
    └──────┬──────┘    │  _issues_json │
           │           └───────────────┘
           │
    学生做题发现错误
           │
    ┌──────▼──────┐
    │ revise_item │ → 创建新 revision(draft)
    │ LLM 修正    │ → AI 自检 → published
    └──────┬──────┘
           │
    旧版本标记
           │
    ┌──────▼──────┐
    │  retired    │
    └─────────────┘
```

## A2：AI 自检门禁

### 职能

LLM 生成题目后、发布前，对每道题做三要素校验：

| 检查项 | 规则 |
|---|---|
| **选项互斥** | 选择题选项中不存在语义重叠（如 A:"LRU" B:"最近最少使用"——同一概念） |
| **答案唯一** | 单选题有且仅有一个正确选项 |
| **资料依据** | 正确答案能从 source_evidence_ids 指向的资料原文中找到支撑 |

### 实现

```python
def validate_item(item_id: str) -> dict:
    """AI 自检，返回 {valid, issues: []}"""
    revision = AssessmentItemRevision.objects.get(id=item.current_revision_id)
    evidence_texts = [EvidenceUnit.objects.get(id=eid).content 
                      for eid in revision.source_evidence_ids]
    
    # 调 LLM 做三要素校验
    result = gateway.chat(
        task_type="assessor",
        messages=[...],  # 包含题干 + 选项 + 资料原文
        structured_output_schema=ItemValidationResult,
    )
    return result
```

### 文件

| 文件 | 说明 |
|---|---|
| `mentora/assessment/validation.py`（新建） | `validate_item()` + `ItemValidationResult` schema |
| `mentora/assessment/services/__init__.py` | `create_item()` 生成后调 validate；新增 `publish_item()` |
| `mentora/assessment/schemas.py`（新建） | Pydantic validation schemas |

## A3：题目修改与闭环

### 触发场景

```
学生做题 → 发现答案不对 → 前端"反馈"按钮
  → POST /api/assessment/items/<id>/flag/
  → 创建 FlaggedItem(issue="答案错误", student_note="应该是FIFO")

系统检测到 2 个以上 flag
  → revise_item(id) → 创建新 revision(draft)
  → LLM 分析 flag 内容 → 自动修正 → validate → published
```

### 数据模型

```python
class FlaggedItem(models.Model):
    """学生对题目的反馈标记。"""
    item_id = UUIDField()
    issue = CharField()  # answer_wrong / option_overlap / outdated / unclear
    student_note = TextField()
    resolved_by_revision_id = UUIDField(nullable)
    created_at = DateTimeField(auto_now_add)
```

### 阈值

| 参数 | 值 | 说明 |
|---|---|---|
| AUTO_PUBLISH_FLAG_COUNT | 2 | 同一题目被 2 次标记后触发自动修正 |

## A4：ItemBank 题目资产管理

设计文档要求的三种来源统一管理：

| source_type | 说明 |
|---|---|
| `official` | 教师/题库导入，需人工确认 |
| `user` | 学生自建，draft → 手动 publish |
| `ai` | LLM 生成，draft → AI 自检 → auto-published |

```python
class ItemProvenance(models.Model):
    """题目溯源。"""
    item_id = UUIDField()
    source_type = CharField(choices=official/user/ai)
    model_request_id = CharField(nullable)  # AI 生成时关联
    import_source = CharField(nullable)     # 题库导入时的来源标识
    created_by = CharField(nullable)
```

## 实施顺序

```
A2 (AI 自检门禁) → A3 (学生反馈闭环) → A4 (ItemBank 来源管理)
```

A2 是质量基础——没有自检的 AI 出题系统不可用于实际学习。A3 是反馈闭环——学生是最终审校者。A4 是管理扩展——多来源题目统一管理。
