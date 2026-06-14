"""AI 抽取客户端：抽象指向 AIGC 聚合网关（OpenAI 兼容 HTTP），不绑定任何原生 SDK。"""

import base64
import json
import re

import httpx

from app.core.config import settings


def _parse_json_lenient(text: str) -> dict:
    """宽容解析：直接 JSON 失败时，剥离代码围栏并提取首个 {...}。"""
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", text, re.DOTALL)
        if match is None:
            raise
        return json.loads(match.group(0))

EXTRACT_SYSTEM_PROMPT = """你是专业的中国发票信息抽取助手。请从用户提供的发票图片中提取结构化字段，并**只**返回 JSON，不要任何解释。

字段要求：
- invoice_code: 发票代码（新版全电发票没有则为 null）
- invoice_number: 发票号码（字符串）
- issue_date: 开票日期，格式 YYYY-MM-DD
- invoice_type: 发票类型，取值之一：专票 / 普票 / 全电 / 打车票 / 其他
- seller_name: 销售方（开票单位）名称
- buyer_name: 购买方抬头
- total_amount: 价税合计金额（纯数字，保留两位小数，不带货币符号）
- category: 账目分类，根据开票方与明细智能判断，取值之一：数字服务 / 差旅出行 / 日常餐饮 / 运动爱好 / 其他
  （例：AWS、阿里云 -> 数字服务；滴滴、高铁、出租车 -> 差旅出行；餐厅 -> 日常餐饮；运动品牌 -> 运动爱好）
- confidence: 你对本次抽取整体准确度的信心，0 到 1 的小数

无法识别的字段填 null。"""


async def extract_invoice_fields(image_bytes: bytes, content_type: str) -> dict:
    """调用网关多模态模型抽取发票字段，返回解析后的 dict。"""
    b64 = base64.b64encode(image_bytes).decode("ascii")
    data_url = f"data:{content_type};base64,{b64}"
    payload = {
        "model": settings.aigc_model,
        "messages": [
            {"role": "system", "content": EXTRACT_SYSTEM_PROMPT},
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": "提取这张发票的全部字段，只输出 JSON。"},
                    {"type": "image_url", "image_url": {"url": data_url}},
                ],
            },
        ],
        "response_format": {"type": "json_object"},
        "temperature": 0,
    }
    async with httpx.AsyncClient(timeout=90) as client:
        resp = await client.post(
            f"{settings.aigc_base_url}/chat/completions",
            headers={"Authorization": f"Bearer {settings.aigc_api_key}"},
            json=payload,
        )
        resp.raise_for_status()
        data = resp.json()
    content = data["choices"][0]["message"]["content"]
    return _parse_json_lenient(content)
