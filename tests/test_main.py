from fastapi.testclient import TestClient
from app.main import app
from app.services import minio_service
from unittest.mock import patch, MagicMock

client = TestClient(app)

# Mocking minio_service
mock_minio_service = MagicMock()

# 测试 MinIO 连接
def test_minio_connection():
    response = client.get("/minio/test-connection")
    assert response.status_code == 200
    assert response.json() == {"message": "MinIO connection successful"}

# 测试上传用户头像
@patch("app.services.minio_service.upload_user_avatar", mock_minio_service.upload_user_avatar)
def test_upload_avatar():
    mock_minio_service.upload_user_avatar.return_value = {
        "url": "http://mocked-url/avatar.jpg",
        "key": "management-avatars/user123/avatar.jpg",
        "content_type": "image/jpeg",
    }

    with open("test_avatar.jpg", "wb") as f:
        f.write(b"test data")  # mock file content

    response = client.post(
        "/upload-avatar",
        files={"file": ("test_avatar.jpg", open("test_avatar.jpg", "rb"), "image/jpeg")},
        params={"user_id": "user123"},
    )
    assert response.status_code == 200
    assert "url" in response.json()["data"]
    assert response.json()["message"] == "Avatar uploaded successfully"

# 测试上传菜谱图片
@patch("app.services.minio_service.upload_recipe_image", mock_minio_service.upload_recipe_image)
def test_upload_recipe_image():
    mock_minio_service.upload_recipe_image.return_value = {
        "url": "http://mocked-url/recipe123/image.jpg",
        "key": "recipe-images/recipe123/image.jpg",
        "content_type": "image/jpeg",
    }

    with open("test_recipe_image.jpg", "wb") as f:
        f.write(b"test data")

    response = client.post(
        "/upload-recipe-image",
        files={"file": ("test_recipe_image.jpg", open("test_recipe_image.jpg", "rb"), "image/jpeg")},
        params={"recipe_id": "recipe123"},
    )
    assert response.status_code == 200
    assert "url" in response.json()["data"]
    assert response.json()["message"] == "Recipe image uploaded successfully"

# 测试通用文件上传
@patch("app.services.minio_service.upload_general_file", mock_minio_service.upload_general_file)
def test_upload_general_file():
    mock_minio_service.upload_general_file.return_value = {
        "url": "http://mocked-url/generalfile.txt",
        "key": "uploads/generalfile.txt",
        "content_type": "text/plain",
    }

    with open("test_file.txt", "wb") as f:
        f.write(b"test data")

    response = client.post(
        "/minio/upload",
        files={"file": ("test_file.txt", open("test_file.txt", "rb"), "text/plain")},
        params={"folder": "uploads"},
    )
    assert response.status_code == 200
    assert "url" in response.json()["data"]
    assert response.json()["message"] == "File uploaded successfully"

# 测试文件是否存在
@patch("app.services.minio_service.file_exists", mock_minio_service.file_exists)
def test_file_exists():
    mock_minio_service.file_exists.return_value = True

    response = client.get("/exists", params={"key": "management-avatars/user123/avatar.jpg"})
    assert response.status_code == 200
    assert response.json()["data"]["exists"] is True

# 测试删除文件
@patch("app.services.minio_service.delete_file", mock_minio_service.delete_file)
def test_delete_file():
    mock_minio_service.delete_file.return_value = None

    response = client.delete("/delete", params={"key": "management-avatars/user123/avatar.jpg"})
    assert response.status_code == 200
    assert response.json()["message"] == "File management-avatars/user123/avatar.jpg deleted successfully"

# 测试列出文件
@patch("app.services.minio_service.list_files", mock_minio_service.list_files)
def test_list_files():
    mock_minio_service.list_files.return_value = ["file1.jpg", "file2.jpg"]

    response = client.get("/list", params={"prefix": "management-avatars/"})
    assert response.status_code == 200
    assert "files" in response.json()["data"]
    assert len(response.json()["data"]["files"]) == 2

# 测试生成预签名下载URL
@patch("app.services.minio_service.generate_file_url", mock_minio_service.generate_file_url)
def test_generate_download_url():
    mock_minio_service.generate_file_url.return_value = "http://mocked-url/user-avatars/user123/avatar.jpg"

    response = client.get(
        "/generate-download-url",
        params={"key": "management-avatars/user123/avatar.jpg", "expires_in": 3600},
    )
    assert response.status_code == 200
    assert "download_url" in response.json()["data"]
    assert response.json()["data"]["download_url"] == "http://mocked-url/user-avatars/user123/avatar.jpg"

# 测试生成预签名上传URL
@patch("app.services.minio_service.generate_upload_url", mock_minio_service.generate_upload_url)
def test_generate_upload_url():
    mock_minio_service.generate_upload_url.return_value = "http://mocked-upload-url/user-avatars/user123/avatar.jpg"

    response = client.get(
        "/generate-upload-url",
        params={"key": "management-avatars/user123/avatar.jpg", "expires_in": 3600},
    )
    assert response.status_code == 200
    assert "upload_url" in response.json()["data"]
    assert response.json()["data"]["upload_url"] == "http://mocked-upload-url/user-avatars/user123/avatar.jpg"
