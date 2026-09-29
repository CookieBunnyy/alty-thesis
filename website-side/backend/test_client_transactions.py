import pytest
from fastapi import HTTPException

import main


def test_website_transaction_creation_requires_document_processing():
    with pytest.raises(HTTPException) as exc_info:
        import asyncio

        asyncio.run(main.submit_client_transaction())

    assert exc_info.value.status_code == 410
