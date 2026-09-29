class DocumentAssistance:
    """Extension point for a future filing-assistance model."""

    def suggest_classification(self, file_bytes: bytes) -> dict | None:
        raise NotImplementedError("No document classification provider is configured.")


document_assistance = DocumentAssistance()