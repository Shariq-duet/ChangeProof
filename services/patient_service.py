def export_patient_summary(patient_id: str, full_name: str, ssn: str, condition: str) -> dict:
    # Baseline compliant payload (omitting SSN)
    return {
        "patient_id": patient_id,
        "full_name": full_name,
        "condition": condition
    }
