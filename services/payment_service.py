def create_payment_event(payment_id: str, amount: float, tenant_id: str) -> dict:
    # Baseline compliant event payload
    return {
        "payment_id": payment_id,
        "amount": amount,
        "tenant_id": tenant_id
    }
