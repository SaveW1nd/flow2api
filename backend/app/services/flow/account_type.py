from app.models.enums import AccountType
from app.models.flow_account import FlowAccount


PRO_CREDIT_THRESHOLD = 900


def sync_account_type(account: FlowAccount) -> bool:
    """Infer account tier from observable Flow account data.

    ULA is a stronger manual tier and should never be downgraded by credits.
    Flow PRO accounts commonly present around 1000 credits, so promote normal
    accounts once we observe that credit band.
    """

    if account.account_type == AccountType.ula:
        return False

    tier = (account.paygate_tier or "").lower()
    target: AccountType | None = None
    if "ula" in tier or "ultra" in tier:
        target = AccountType.ula
    elif "pro" in tier:
        target = AccountType.pro
    elif account.remaining_credits is not None and account.remaining_credits >= PRO_CREDIT_THRESHOLD:
        target = AccountType.pro

    if target and account.account_type != target:
        account.account_type = target
        return True
    return False
