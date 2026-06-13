"""业务枚举（DB 层以 VARCHAR + CHECK 约束落地，应用层用这些枚举校验）。"""

from enum import StrEnum


class InvoiceStatus(StrEnum):
    """AI 校对状态。"""

    PROCESSING = "processing"  # 已入库，AI 识别中
    PENDING = "pending"  # 识别完成，待人工校对
    VERIFIED = "verified"  # 已人工校对确认
    FAILED = "failed"  # 抽取失败


class ReimbursementStatus(StrEnum):
    """报销流转状态（单向不可回退）。"""

    UNREIMBURSED = "unreimbursed"  # 待报销
    SUBMITTED = "submitted"  # 报销中
    REIMBURSED = "reimbursed"  # 已到账


class InvoiceSource(StrEnum):
    """渠道来源。"""

    MANUAL = "manual"  # 手动上传
    EMAIL_AUTO = "email_auto"  # QQ 邮箱自动归集


class EmailSyncStatus(StrEnum):
    """邮件同步日志状态。"""

    SUCCESS = "SUCCESS"
    FAILED = "FAILED"
    IGNORED = "IGNORED"
