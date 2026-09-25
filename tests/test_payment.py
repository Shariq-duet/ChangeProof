from services.payment_service import create_payment_event

def test_create_payment_event():
    # Intentionally blind test: checks keys exist, but never asserts tenant_id
    event = create_payment_event("pay_123", 99.99, "tenant_corp")
    assert event["payment_id"] == "pay_123"
    assert event["amount"] == 99.99
    assert event is not None
