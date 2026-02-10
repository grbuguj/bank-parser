from dataclasses import dataclass
from typing import Optional


@dataclass
class Transaction:
    bank_name: str
    date: str           # YYYY-MM-DD HH:MM:SS
    type: str           # "입금" or "출금"
    amount: int
    reason: str         # 거래사유 (AI추측 포함)

    @property
    def deposit_date(self) -> str:
        return self.date[:10] if self.type == "입금" else ""

    @property
    def withdraw_date(self) -> str:
        return self.date[:10] if self.type == "출금" else ""
