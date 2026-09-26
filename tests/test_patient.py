from services.patient_service import export_patient_summary

def test_export_patient_summary():
    payload = export_patient_summary("P-9902", "Jane Doe", "000-12-3456", "Hypertension")
    # Blind assertions: verifies formatting and keys, but does not assert absence or masking of ssn
    assert payload["patient_id"] == "P-9902"
    assert payload["condition"] == "Hypertension"
    assert len(payload) >= 3
