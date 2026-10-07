"""Processed documents are filed automatically into per-person folders."""

from __future__ import annotations

from tests import documents as build
from tests.test_document_pipeline import assert_success, upload


def folders(api, headers) -> dict[str, dict]:
    rows = api.get("/api/v1/documents/folders", headers=headers).json()
    by_id = {f["id"]: f for f in rows}

    def path(folder):
        parent = by_id.get(folder["parent_id"])
        return f"{path(parent)} / {folder['name']}" if parent else folder["name"]
    return {path(f): f for f in rows}


def test_buyer_documents_filed_under_the_client(api, admin, agents, db):
    upload(api, admin, "property.docx", build.docx(build.PROPERTY_LINES))
    doc = upload(api, admin, "buyer.docx", build.docx(build.BUYER_LINES))
    processing = assert_success(doc)
    assert doc["folder_path"] == "Buyers / Michael Santos"
    assert processing["filed_to"] == "Buyers / Michael Santos"

    # The reservation for the same client reuses the folder (no duplicate).
    doc = upload(api, admin, "reservation.docx", build.docx(build.RESERVATION_LINES))
    assert_success(doc)
    assert doc["folder_path"] == "Buyers / Michael Santos"
    tree = folders(api, admin)
    assert [p for p in tree if p.startswith("Buyers / ")] == ["Buyers / Michael Santos"]

    # Listing the Buyers folder includes its sub-folders.
    buyers = tree["Buyers"]["id"]
    listed = api.get(f"/api/v1/documents?folder_id={buyers}", headers=admin).json()
    assert {d["document_name"] for d in listed} == {"buyer.docx", "reservation.docx"}

    # The filing is in the document's history.
    history = api.get(f"/api/v1/documents/{doc['document_id']}/audit", headers=admin).json()
    assert "DOCUMENT_FILED" in str(history)


def test_property_and_agent_documents_filed_by_title_and_name(api, admin, db):
    doc = upload(api, admin, "property.docx", build.docx(build.PROPERTY_LINES))
    assert_success(doc)
    assert doc["folder_path"] == "Properties / Test Property - Azure Heights Residence"
    doc = upload(api, admin, "agent.docx", build.docx(build.AGENT_LINES))
    assert_success(doc)
    assert doc["folder_path"] == "Agents / Angela Cruz"


def test_category_folder_choice_still_files_but_custom_folder_is_kept(api, admin, agents, db):
    upload(api, admin, "property.docx", build.docx(build.PROPERTY_LINES))
    tree = folders(api, admin)
    custom = api.post("/api/v1/documents/folders", headers=admin, json={"name": "Board Review"}).json()

    response = api.post("/api/v1/documents/upload", headers=admin,
                        files={"file": ("buyer.docx", build.docx(build.BUYER_LINES), "application/octet-stream")},
                        data={"folder_id": str(custom["id"])})
    assert response.status_code == 201, response.text
    assert response.json()["folder_path"] == "Board Review"

    lines = [line.replace("Michael Santos", "Jane Reyes").replace("CLI-TEST-0001", "CLI-TEST-0002")
             .replace("michael.santos.test", "jane.reyes.test").replace("0917-555-0101", "0917-555-0202")
             for line in build.BUYER_LINES]
    response = api.post("/api/v1/documents/upload", headers=admin,
                        files={"file": ("jane.docx", build.docx(lines), "application/octet-stream")},
                        data={"folder_id": str(tree["Buyers"]["id"])})
    assert response.status_code == 201, response.text
    assert response.json()["folder_path"] == "Buyers / Jane Reyes"


def test_failed_documents_are_not_filed(api, admin, agents, db):
    doc = upload(api, admin, "reservation.docx", build.docx(build.RESERVATION_LINES))
    assert doc["status"] == "FAILED"
    assert doc["folder_path"] is None
    assert not [p for p in folders(api, admin) if p.startswith("Buyers / ")]


def test_deleting_a_folder_keeps_its_documents(api, admin, agents, db):
    upload(api, admin, "property.docx", build.docx(build.PROPERTY_LINES))
    doc = upload(api, admin, "buyer.docx", build.docx(build.BUYER_LINES))
    assert doc["folder_path"] == "Buyers / Michael Santos"
    tree = folders(api, admin)
    person = tree["Buyers / Michael Santos"]["id"]
    nested = api.post("/api/v1/documents/folders", headers=admin,
                      json={"name": "Old IDs", "parent_id": person}).json()

    response = api.delete(f"/api/v1/documents/folders/{person}", headers=admin)
    assert response.status_code == 200, response.text
    result = response.json()
    assert result["deleted"] == "Buyers / Michael Santos"
    assert result["subfolders"] == 1 and result["moved_documents"] == 1 and result["moved_to"] == "Buyers"
    after = folders(api, admin)
    assert "Buyers / Michael Santos" not in after and nested["id"] not in {f["id"] for f in after.values()}
    moved = api.get(f"/api/v1/documents/{doc['document_id']}", headers=admin).json()
    assert moved["folder_path"] == "Buyers"  # the document itself is kept
    history = api.get(f"/api/v1/documents/{doc['document_id']}/audit", headers=admin)
    assert history.status_code == 200


def test_standard_folders_cannot_be_deleted(api, admin, employee):
    tree = folders(api, admin)
    refused = api.delete(f"/api/v1/documents/folders/{tree['Buyers']['id']}", headers=admin)
    assert refused.status_code == 409
    custom = api.post("/api/v1/documents/folders", headers=admin, json={"name": "Scratch"}).json()
    assert api.delete(f"/api/v1/documents/folders/{custom['id']}", headers=employee).status_code == 403
    assert api.delete("/api/v1/documents/folders/999999", headers=admin).status_code == 404
