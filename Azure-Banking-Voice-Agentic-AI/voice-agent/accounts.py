"""Phase 1 mock accounts — in-memory only, no network, no persistence, resets on restart.

Backs the agent's get_balance/transfer/list_accounts tool calls (docs/PLAN.md Phase 1, in-scope
item 2). Deliberately a dict + three functions, not an account abstraction — Phase 1 scope, revisit
if a real core-banking client (Phase 3's mock-core-banking, or later a real one) replaces this.
"""

ACCOUNTS = {"chequing": 2400.0, "savings": 500.0}


class UnknownAccountError(ValueError):
    """Raised for any account name not in ACCOUNTS — never silently fall back (CLAUDE.md)."""


def list_accounts():
    return dict(ACCOUNTS)


def get_balance(account):
    if account not in ACCOUNTS:
        raise UnknownAccountError(account)
    return ACCOUNTS[account]


def transfer(from_account, to_account, amount):
    for account in (from_account, to_account):
        if account not in ACCOUNTS:
            raise UnknownAccountError(account)
    if amount <= 0:
        raise ValueError(f"transfer amount must be positive, got {amount!r}")
    available = get_balance(from_account)
    if amount > available:
        return f"I can't do that — you have ${available:.2f} available in {from_account}."
    ACCOUNTS[from_account] -= amount
    ACCOUNTS[to_account] += amount
    return (
        f"Done — transferred ${amount:.2f} from {from_account} to {to_account}. "
        f"New {from_account} balance: ${ACCOUNTS[from_account]:.2f}."
    )
