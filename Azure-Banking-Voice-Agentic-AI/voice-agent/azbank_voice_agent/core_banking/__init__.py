"""The core-banking seam: one protocol, one real client, one fake.

Same shape as transport/ and realtime/ -- an external system, its protocol, and a stand-in that
satisfies the same protocol without a network.
"""
from .client import (
    CoreBankingClient,
    CoreBankingRequestError,
    CoreBankingUnavailable,
    HttpCoreBankingClient,
    TransferOutcome,
    UnknownAccountError,
)

__all__ = [
    "CoreBankingClient",
    "CoreBankingRequestError",
    "CoreBankingUnavailable",
    "HttpCoreBankingClient",
    "TransferOutcome",
    "UnknownAccountError",
]
