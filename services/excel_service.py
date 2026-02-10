import io
from typing import List
from openpyxl import Workbook
from openpyxl.styles import (
    Font, PatternFill, Alignment, Border, Side
)
from openpyxl.utils import get_column_letter

from models.transaction import Transaction


def create_excel(transactions: List[Transaction], bank_name: str) -> bytes:
    """Transaction 리스트를 엑셀 파일로 변환 후 바이트 반환"""
    wb = Workbook()
    ws = wb.active
    ws.title = bank_name[:31]  # 시트명 최대 31자

    # 스타일 정의
    header_font = Font(bold=True, color="FFFFFF", size=11)
    header_fill = PatternFill(start_color="2F4F8F", end_color="2F4F8F", fill_type="solid")
    header_alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)

    data_alignment_center = Alignment(horizontal="center", vertical="center")
    data_alignment_left = Alignment(horizontal="left", vertical="center")

    thin_border = Border(
        left=Side(style="thin"),
        right=Side(style="thin"),
        top=Side(style="thin"),
        bottom=Side(style="thin"),
    )

    reason_fill = PatternFill(start_color="FFFACD", end_color="FFFACD", fill_type="solid")  # 연노랑

    # 헤더
    headers = ["거래은행", "입금일", "출금일", "금액", "거래사유"]
    col_widths = [15, 18, 18, 18, 45]

    for col_idx, (header, width) in enumerate(zip(headers, col_widths), start=1):
        cell = ws.cell(row=1, column=col_idx, value=header)
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = header_alignment
        cell.border = thin_border
        ws.column_dimensions[get_column_letter(col_idx)].width = width

    ws.row_dimensions[1].height = 30

    # 데이터 행
    for row_idx, t in enumerate(transactions, start=2):
        row_data = [
            t.bank_name,
            t.deposit_date,
            t.withdraw_date,
            t.amount,
            t.reason,
        ]

        for col_idx, value in enumerate(row_data, start=1):
            cell = ws.cell(row=row_idx, column=col_idx, value=value)
            cell.border = thin_border

            if col_idx == 4:  # 금액 컬럼
                cell.number_format = "#,##0"
                cell.alignment = data_alignment_center
            elif col_idx == 5:  # 거래사유 컬럼
                cell.alignment = data_alignment_left
            else:
                cell.alignment = data_alignment_center

        ws.row_dimensions[row_idx].height = 20

    # 바이트로 저장
    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    return buf.getvalue()
