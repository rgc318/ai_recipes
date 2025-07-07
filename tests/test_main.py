from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_minio_connection():
    response = client.get("/minio/test-connection")
    assert response.status_code == 200
    assert response.json() == {"message": "MinIO connection successful"}
