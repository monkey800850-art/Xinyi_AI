from typing import Dict, List


class UserExperienceError(RuntimeError):
    pass


SUPPORTED_PROCESSES = {"reimbursement", "reconciliation", "consolidation"}


def _normalize_process_name(process_name: object) -> str:
    name = str(process_name or "").strip().lower()
    if name not in SUPPORTED_PROCESSES:
        raise UserExperienceError("process_name_invalid")
    return name


def guide_user_step(process_name: object) -> Dict[str, object]:
    name = _normalize_process_name(process_name)
    step_map: Dict[str, List[Dict[str, object]]] = {
        "reimbursement": [
            {"step_no": 1, "title": "填写报销单", "hint": "选择费用类型并录入金额/事由", "required": True},
            {"step_no": 2, "title": "上传附件", "hint": "上传发票、行程单等影像附件", "required": True},
            {"step_no": 3, "title": "提交审批", "hint": "校验预算后提交审批流", "required": True},
        ],
        "reconciliation": [
            {"step_no": 1, "title": "选择对账区间", "hint": "选择银行账户和期间", "required": True},
            {"step_no": 2, "title": "核对差异", "hint": "查看自动匹配结果并处理差异原因", "required": True},
            {"step_no": 3, "title": "确认并结案", "hint": "批量确认后锁定本次对账", "required": True},
        ],
        "consolidation": [
            {"step_no": 1, "title": "选择合并范围", "hint": "确认成员单位、口径与期间", "required": True},
            {"step_no": 2, "title": "执行抵销与校验", "hint": "运行规则并检查异常项", "required": True},
            {"step_no": 3, "title": "生成报表并审批", "hint": "生成四大报表、附注及审计包", "required": True},
        ],
    }
    items = step_map[name]
    return {"process_name": name, "step_count": len(items), "steps": items}


def show_error_message(error_type: object) -> Dict[str, str]:
    key = str(error_type or "").strip().lower()
    error_messages: Dict[str, Dict[str, str]] = {
        "missing_attachment": {
            "message": "请上传附件后再提交。",
            "action": "补传附件，确认文件清晰且可读。",
        },
        "incorrect_amount": {
            "message": "金额不正确，请检查后重试。",
            "action": "核对单据金额、币种和税额口径。",
        },
        "missing_data": {
            "message": "缺少必要数据，请填写完整。",
            "action": "补齐必填字段并重新保存。",
        },
        "permission_denied": {
            "message": "当前账号无操作权限。",
            "action": "联系管理员开通角色权限。",
        },
    }
    default_msg = {"message": "未知错误，请稍后再试。", "action": "记录操作时间并联系管理员排查。"}
    payload = error_messages.get(key, default_msg)
    return {"error_type": key or "unknown", **payload}


def show_operation_guide(process_name: object) -> Dict[str, object]:
    name = _normalize_process_name(process_name)
    guides = {
        "reimbursement": "先填单再传附件，预算占用通过后提交审批。",
        "reconciliation": "优先处理自动匹配，再逐条处理差异并完成结案。",
        "consolidation": "先确认范围与参数，再执行抵销、校验和报表发布。",
    }
    tips_map: Dict[str, List[str]] = {
        "reimbursement": ["附件命名建议包含日期和金额。", "驳回后可在原单据上修订再提审。"],
        "reconciliation": ["差异应选择标准原因码。", "批量确认前先抽样复核。"],
        "consolidation": ["锁定前确认草稿已复核。", "保留批次号便于追溯。"],
    }
    return {"process_name": name, "guide": guides[name], "tips": tips_map[name]}
