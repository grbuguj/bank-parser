import base64
import json
import re
import concurrent.futures
import time

from datetime import datetime
from typing import List, Tuple
from openai import OpenAI
from PIL import Image

from config.prompts import BANK_PROMPTS
from models.transaction import Transaction
from services.pdf_service import image_to_bytes


def image_to_base64(image: Image.Image) -> str:
    """PIL 이미지를 base64 문자열로 변환"""
    img_bytes = image_to_bytes(image)
    return base64.b64encode(img_bytes).decode("utf-8")


def extract_json_from_response(text: str) -> list:
    """GPT 응답에서 JSON 배열 추출"""
    # 코드블록 제거 (```json ... ``` 또는 ``` ... ```)
    text = re.sub(r"```(?:json)?[\s\S]*?```", lambda m: m.group().replace("```json", "").replace("```", ""), text)
    text = re.sub(r"```(?:json)?", "", text)
    text = text.replace("```", "").strip()

    match = re.search(r"\[[\s\S]*\]", text)
    if match:
        try:
            return json.loads(match.group())
        except json.JSONDecodeError as e:
            print(f"[JSON 파싱 실패] {e}\n원문: {text[:500]}")
            return []
    print(f"[JSON 배열 없음] GPT 응답 원문:\n{text[:500]}")
    return []


def call_gpt_single_page(
    client: OpenAI,
    image: Image.Image,
    bank_name: str,
    page_num: int,
) -> Tuple[int, list]:
    """단일 페이지 GPT Vision 호출 (429 자동 재시도 포함)"""
    prompt = BANK_PROMPTS.get(bank_name, BANK_PROMPTS["기타"])
    b64 = image_to_base64(image)

    max_retries = 5
    for attempt in range(max_retries):
        try:
            response = client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "text",
                                "text": prompt,
                            },
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:image/png;base64,{b64}",
                                    "detail": "high",
                                },
                            },
                        ],
                    }
                ],
                max_tokens=16000,
                temperature=0,
            )
            raw = response.choices[0].message.content
            transactions = extract_json_from_response(raw)
            print(f"[페이지 {page_num}] 추출 {len(transactions)}건")
            return page_num, transactions

        except Exception as e:
            if "429" in str(e) and attempt < max_retries - 1:
                wait = 2 ** attempt  # 1초 → 2초 → 4초 → 8초
                time.sleep(wait)
                continue
            raise


def process_pdf_with_gpt(
    client: OpenAI,
    images: List[Image.Image],
    bank_name: str,
    progress_callback=None,
) -> List[Transaction]:
    """전체 PDF 페이지를 병렬로 GPT 처리 후 Transaction 리스트 반환"""
    all_raw = [None] * len(images)

    def process_page(args):
        idx, image = args
        return call_gpt_single_page(client, image, bank_name, idx)

    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
        future_map = {
            executor.submit(process_page, (idx, img)): idx
            for idx, img in enumerate(images)
        }
        completed = 0
        for future in concurrent.futures.as_completed(future_map):
            page_num, result = future.result()
            all_raw[page_num] = result
            completed += 1
            if progress_callback:
                progress_callback(completed, len(images))

    # 모든 페이지 거래 합치기
    transactions = []
    for page_results in all_raw:
        if not page_results:
            continue
        for item in page_results:
            try:
                t = Transaction(
                    bank_name=bank_name,
                    date=item.get("date", ""),
                    type=item.get("type", ""),
                    amount=int(item.get("amount", 0)),
                    reason=item.get("reason", ""),
                )
                transactions.append(t)
            except (ValueError, KeyError):
                continue

    # 날짜+시간 오름차순 정렬 (과거 → 최신)
    def parse_date(t):
        for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
            try:
                return datetime.strptime(t.date, fmt)
            except ValueError:
                continue
        return datetime.min

    transactions.sort(key=parse_date)

    # 중복 제거 (date + type + amount 동일한 거래)
    seen = set()
    deduped = []
    for t in transactions:
        key = (t.date, t.type, t.amount)
        if key not in seen:
            seen.add(key)
            deduped.append(t)

    return deduped


def filter_transactions(
    transactions: List[Transaction], min_amount: int
) -> List[Transaction]:
    """금액 필터링"""
    return [t for t in transactions if t.amount >= min_amount]
