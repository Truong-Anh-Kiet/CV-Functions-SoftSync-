from uuid import uuid4

from fastapi.testclient import TestClient

from app.db.session import SessionLocal
from app.main import app
from app.models.document import Document
from app.services.document_storage import ensure_upload_dir, local_path_for


client = TestClient(app)


def cleanup_document(document_id: int | None, filenames: list[str]) -> None:
    db = SessionLocal()
    try:
        if document_id:
            document = db.get(Document, document_id)
            if document:
                db.delete(document)
                db.commit()
    finally:
        db.close()

    for filename in filenames:
        path = local_path_for(filename)
        if path.exists():
            path.unlink()


def test_manage_cv_documents() -> None:
    filename = f"cv-{uuid4().hex}.pdf"
    renamed_filename = f"cv-renamed-{uuid4().hex}.pdf"
    document_id = None

    ensure_upload_dir()
    local_path_for(filename).write_bytes(b"%PDF-1.4 test")

    db = SessionLocal()
    try:
        document = Document(
            filename=filename,
            cloudinary_url="",
            category="CV",
        )
        db.add(document)
        db.commit()
        db.refresh(document)
        document_id = document.id
    finally:
        db.close()

    try:
        list_response = client.get("/api/v1/upload/cvs")
        assert list_response.status_code == 200
        assert any(cv["id"] == document_id for cv in list_response.json()["data"])

        get_response = client.get(f"/api/v1/upload/cvs/{document_id}")
        assert get_response.status_code == 200
        assert get_response.json()["data"]["filename"] == filename

        rename_response = client.patch(
            f"/api/v1/upload/cvs/{document_id}/rename",
            json={"filename": renamed_filename},
        )
        assert rename_response.status_code == 200
        assert rename_response.json()["data"]["filename"] == renamed_filename
        assert not local_path_for(filename).exists()
        assert local_path_for(renamed_filename).exists()

        delete_response = client.delete(f"/api/v1/upload/cvs/{document_id}")
        assert delete_response.status_code == 200
        assert delete_response.json() == {
            "status": "success",
            "message": "Da xoa CV thanh cong",
        }
        assert not local_path_for(renamed_filename).exists()

        db = SessionLocal()
        try:
            assert db.get(Document, document_id) is None
        finally:
            db.close()
    finally:
        cleanup_document(document_id, [filename, renamed_filename])

