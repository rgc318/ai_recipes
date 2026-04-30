"""
AI Recipes 项目 - FastAPI 测试文件

该文件包含针对文件上传相关功能的集成测试，主要测试 MinIO 存储服务的各种操作。

注意：当前测试文件已过时，引用了已重构的服务（app.services.minio_service），
实际服务已迁移至 app.services.file.file_service。

测试覆盖场景：
- MinIO 连接测试
- 用户头像上传
- 菜谱图片上传
- 通用文件上传
- 文件存在性检查
- 文件删除
- 文件列表获取
- 预签名 URL 生成（下载/上传）
"""

from fastapi.testclient import TestClient
from app.main import app
from unittest.mock import patch, MagicMock
from typing import Optional, Dict, Any, List, Tuple, Callable, Union
from enum import Enum

# =============================================================================
# 测试客户端和 Mock 对象初始化
# =============================================================================

# 创建 FastAPI 测试客户端
# TestClient 提供了对 FastAPI 应用的测试支持，可以发送模拟的 HTTP 请求
client = TestClient(app)

# 创建 MinIO 服务的 Mock 对象
# MagicMock 是 unittest.mock 提供的模拟对象，可以模拟任意方法调用并返回预设值
# 用于隔离测试，避免实际调用 MinIO 服务
mock_minio_service = MagicMock()


# =============================================================================
# 通用网络请求测试工具
# =============================================================================

class HttpMethod(Enum):
    """HTTP 请求方法枚举"""
    GET = "get"
    POST = "post"
    PUT = "put"
    DELETE = "delete"
    PATCH = "patch"
    HEAD = "head"
    OPTIONS = "options"


class ApiTestResult:
    """
    API 测试结果封装类

    属性:
        response: 响应对象
        success: 是否通过所有断言
        errors: 错误信息列表
    """

    def __init__(self, response, success: bool = True, errors: List[str] = None):
        self.response = response
        self.success = success
        self.errors = errors or []

    @property
    def status_code(self) -> int:
        """获取响应状态码"""
        return self.response.status_code

    @property
    def json(self) -> Dict[str, Any]:
        """获取响应 JSON 数据"""
        return self.response.json()

    def __repr__(self):
        return f"ApiTestResult(status_code={self.status_code}, success={self.success})"


class GenericApiTester:
    """
    通用 API 测试工具类

    提供灵活的 HTTP 请求测试能力，支持：
    - 自定义请求方法和路径
    - 自定义请求头、参数、请求体
    - 支持 JWT 认证
    - 支持文件上传
    - 灵活的断言验证
    - 详细的错误报告

    使用示例:
        # 简单 GET 请求
        result = api_tester.request(
            method=HttpMethod.GET,
            path="/api/users/1"
        )

        # 带认证的 POST 请求
        result = api_tester.request(
            method=HttpMethod.POST,
            path="/api/recipes",
            json={"title": "新食谱"},
            token="your-jwt-token",
            expected_status=201
        )

        # 文件上传
        result = api_tester.upload_file(
            path="/upload",
            file_path="test.jpg",
            field_name="file",
            params={"user_id": "123"}
        )
    """

    def __init__(self, test_client: TestClient):
        """
        初始化测试工具

        Args:
            test_client: FastAPI TestClient 实例
        """
        self.client = test_client

    def request(
        self,
        method: Union[HttpMethod, str],
        path: str,
        *,
        params: Optional[Dict[str, Any]] = None,
        json: Optional[Dict[str, Any]] = None,
        data: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
        cookies: Optional[Dict[str, str]] = None,
        token: Optional[str] = None,
        files: Optional[Dict[str, Tuple[str, bytes, str]]] = None,
        expected_status: Optional[int] = None,
        expected_fields: Optional[Dict[str, Any]] = None,
        assert_func: Optional[Callable[[Any], bool]] = None,
        verbose: bool = True,
    ) -> ApiTestResult:
        """
        发送通用 HTTP 请求并进行验证

        Args:
            method: HTTP 请求方法 (HttpMethod 枚举或字符串)
            path: 请求路径
            params: URL 查询参数
            json: JSON 请求体
            data: 表单请求体
            headers: 自定义请求头
            cookies: Cookie 数据
            token: JWT 认证 Token (会自动添加到 Authorization 头)
            files: 文件数据，格式: {字段名: (文件名, 文件内容, MIME类型)}
            expected_status: 预期的 HTTP 状态码
            expected_fields: 预期的响应字段值字典
            assert_func: 自定义断言函数，接收响应对象，返回 True/False
            verbose: 是否打印详细信息

        Returns:
            ApiTestResult: 测试结果对象

        示例:
            result = tester.request(
                method=HttpMethod.GET,
                path="/api/users",
                params={"page": 1},
                token="jwt_token",
                expected_status=200
            )
        """
        errors = []
        response = None

        try:
            # 构建请求头
            request_headers = headers or {}
            if token:
                request_headers["Authorization"] = f"Bearer {token}"

            # 发送请求
            method_str = method.value if isinstance(method, HttpMethod) else method.lower()
            response = getattr(self.client, method_str)(
                path,
                params=params,
                json=json,
                data=data,
                headers=request_headers,
                cookies=cookies,
                files=files,
            )

            # 验证状态码
            if expected_status is not None:
                if response.status_code != expected_status:
                    errors.append(
                        f"状态码不匹配: 预期 {expected_status}, 实际 {response.status_code}"
                    )

            # 验证响应字段
            if expected_fields:
                try:
                    response_data = response.json()
                    for field, expected_value in expected_fields.items():
                        actual_value = self._get_nested_field(response_data, field)
                        if actual_value != expected_value:
                            errors.append(
                                f"字段 {field} 不匹配: 预期 {expected_value}, 实际 {actual_value}"
                            )
                except Exception as e:
                    errors.append(f"解析响应 JSON 失败: {e}")

            # 自定义断言
            if assert_func is not None:
                try:
                    if not assert_func(response):
                        errors.append("自定义断言函数返回 False")
                except Exception as e:
                    errors.append(f"自定义断言函数执行失败: {e}")

        except Exception as e:
            errors.append(f"请求执行失败: {e}")

        # 打印详细信息
        if verbose:
            self._print_request_info(
                method=method_str,
                path=path,
                response=response,
                errors=errors,
            )

        return ApiTestResult(
            response=response,
            success=len(errors) == 0,
            errors=errors,
        )

    def upload_file(
        self,
        path: str,
        file_path: str,
        field_name: str = "file",
        *,
        content_type: Optional[str] = None,
        params: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
        token: Optional[str] = None,
        expected_status: int = 200,
    ) -> ApiTestResult:
        """
        上传文件请求

        Args:
            path: 上传端点路径
            file_path: 要上传的文件路径
            field_name: 表单字段名 (默认为 "file")
            content_type: 文件 MIME 类型 (自动推断)
            params: 查询参数
            headers: 请求头
            token: JWT Token
            expected_status: 预期状态码

        Returns:
            ApiTestResult: 测试结果对象

        示例:
            result = tester.upload_file(
                path="/api/upload-avatar",
                file_path="avatar.jpg",
                params={"user_id": "123"}
            )
        """
        import os
        import mimetypes

        # 读取文件
        if not os.path.exists(file_path):
            return ApiTestResult(
                response=None,
                success=False,
                errors=[f"文件不存在: {file_path}"]
            )

        with open(file_path, "rb") as f:
            file_content = f.read()

        filename = os.path.basename(file_path)
        if content_type is None:
            content_type, _ = mimetypes.guess_type(filename)
            if content_type is None:
                content_type = "application/octet-stream"

        files = {field_name: (filename, file_content, content_type)}

        return self.request(
            method=HttpMethod.POST,
            path=path,
            files=files,
            params=params,
            headers=headers,
            token=token,
            expected_status=expected_status,
        )

    def batch_request(
        self,
        requests: List[Dict[str, Any]],
        stop_on_error: bool = False,
    ) -> List[ApiTestResult]:
        """
        批量发送请求

        Args:
            requests: 请求参数列表，每个元素是 request() 方法的参数字典
            stop_on_error: 遇到错误是否停止

        Returns:
            List[ApiTestResult]: 测试结果列表

        示例:
            results = tester.batch_request([
                {"method": HttpMethod.GET, "path": "/api/users/1"},
                {"method": HttpMethod.GET, "path": "/api/users/2"},
            ])
        """
        results = []

        for i, req_params in enumerate(requests):
            result = self.request(**req_params, verbose=False)
            results.append(result)

            if stop_on_error and not result.success:
                print(f"批量请求在第 {i+1} 个请求时停止")
                break

        # 打印汇总
        success_count = sum(1 for r in results if r.success)
        print(f"\n批量请求完成: {success_count}/{len(results)} 成功")

        return results

    def _get_nested_field(self, data: Dict[str, Any], field_path: str) -> Any:
        """
        获取嵌套字段值

        支持点号分隔的路径，如 "data.user.id"
        """
        keys = field_path.split(".")
        value = data
        for key in keys:
            if isinstance(value, dict):
                value = value.get(key)
            else:
                return None
        return value

    def _print_request_info(
        self,
        method: str,
        path: str,
        response: Optional[Any],
        errors: List[str],
    ):
        """打印请求和响应信息"""
        print(f"\n{'='*60}")
        print(f"请求: {method.upper()} {path}")

        if response:
            print(f"状态码: {response.status_code}")
            try:
                print(f"响应: {response.json()}")
            except:
                print(f"响应: {response.text[:200]}")

        if errors:
            print(f"\n❌ 验证失败:")
            for error in errors:
                print(f"   - {error}")
        else:
            print(f"\n✓ 验证通过")

        print(f"{'='*60}")


# 创建全局测试工具实例
api_tester = GenericApiTester(client)


# =============================================================================
# MinIO 连接测试
# =============================================================================

def test_minio_connection():
    """
    测试 MinIO 连接是否正常

    发送 GET 请求到 /minio/test-connection 端点
    预期返回状态码 200 和成功消息
    """
    response = client.get("/minio/test-connection")
    assert response.status_code == 200
    assert response.json() == {"message": "MinIO connection successful"}


# =============================================================================
# 用户头像上传测试
# =============================================================================

@patch("app.services.minio_service.upload_user_avatar", mock_minio_service.upload_user_avatar)
def test_upload_avatar():
    """
    测试用户头像上传功能

    测试步骤：
    1. 使用 @patch 装饰器模拟 upload_user_avatar 方法
    2. 创建测试用的图片文件
    3. 发送 POST 请求到 /upload-avatar 端点
    4. 验证响应状态码和返回数据

    预期结果：
    - HTTP 状态码为 200
    - 响应包含上传后的文件 URL
    - 返回成功消息
    """
    # 设置 mock 方法的返回值（模拟上传成功后的响应）
    mock_minio_service.upload_user_avatar.return_value = {
        "url": "http://mocked-url/avatar.jpg",
        "key": "user-avatars/user123/avatar.jpg",
        "content_type": "image/jpeg",
    }

    # 创建测试图片文件（二进制数据）
    # 注意：测试结束后应清理该临时文件，当前代码缺少清理逻辑
    with open("test_avatar.jpg", "wb") as f:
        f.write(b"test data")  # mock file content

    # 发送文件上传请求
    # files 参数包含文件元数据：(文件名, 文件对象, 内容类型)
    # params 参数包含查询参数 user_id
    response = client.post(
        "/upload-avatar",
        files={"file": ("test_avatar.jpg", open("test_avatar.jpg", "rb"), "image/jpeg")},
        params={"user_id": "user123"},
    )

    # 断言验证
    assert response.status_code == 200
    assert "url" in response.json()["data"]
    assert response.json()["message"] == "Avatar uploaded successfully"


# =============================================================================
# 菜谱图片上传测试
# =============================================================================

@patch("app.services.minio_service.upload_recipe_image", mock_minio_service.upload_recipe_image)
def test_upload_recipe_image():
    """
    测试菜谱图片上传功能

    测试步骤：
    1. 模拟 upload_recipe_image 方法
    2. 创建测试图片文件
    3. 发送 POST 请求到 /upload-recipe-image 端点
    4. 验证响应数据

    预期结果：
    - HTTP 状态码为 200
    - 返回菜谱图片的 URL
    - 返回成功消息
    """
    # 设置 mock 返回值
    mock_minio_service.upload_recipe_image.return_value = {
        "url": "http://mocked-url/recipe123/image.jpg",
        "key": "recipe-images/recipe123/image.jpg",
        "content_type": "image/jpeg",
    }

    # 创建测试图片文件
    # 注意：缺少文件清理逻辑
    with open("test_recipe_image.jpg", "wb") as f:
        f.write(b"test data")

    # 发送菜谱图片上传请求
    response = client.post(
        "/upload-recipe-image",
        files={"file": ("test_recipe_image.jpg", open("test_recipe_image.jpg", "rb"), "image/jpeg")},
        params={"recipe_id": "recipe123"},
    )

    # 断言验证
    assert response.status_code == 200
    assert "url" in response.json()["data"]
    assert response.json()["message"] == "Recipe image uploaded successfully"


# =============================================================================
# 通用文件上传测试
# =============================================================================

@patch("app.services.minio_service.upload_general_file", mock_minio_service.upload_general_file)
def test_upload_general_file():
    """
    测试通用文件上传功能

    适用场景：上传任意类型的文件到指定文件夹

    测试步骤：
    1. 模拟 upload_general_file 方法
    2. 创建文本测试文件
    3. 发送 POST 请求到 /minio/upload 端点
    4. 验证响应

    预期结果：
    - HTTP 状态码为 200
    - 返回文件的访问 URL
    """
    # 设置 mock 返回值
    mock_minio_service.upload_general_file.return_value = {
        "url": "http://mocked-url/generalfile.txt",
        "key": "uploads/generalfile.txt",
        "content_type": "text/plain",
    }

    # 创建测试文本文件
    # 注意：缺少文件清理逻辑
    with open("test_file.txt", "wb") as f:
        f.write(b"test data")

    # 发送文件上传请求
    # folder 参数指定上传目标文件夹
    response = client.post(
        "/minio/upload",
        files={"file": ("test_file.txt", open("test_file.txt", "rb"), "text/plain")},
        params={"folder": "uploads"},
    )

    # 断言验证
    assert response.status_code == 200
    assert "url" in response.json()["data"]
    assert response.json()["message"] == "File uploaded successfully"


# =============================================================================
# 文件存在性检查测试
# =============================================================================

@patch("app.services.minio_service.file_exists", mock_minio_service.file_exists)
def test_file_exists():
    """
    测试文件存在性检查功能

    用途：检查指定 key 的文件是否存在于存储桶中

    测试步骤：
    1. 模拟 file_exists 方法返回 True
    2. 发送 GET 请求到 /exists 端点
    3. 验证响应中的存在性标志

    预期结果：
    - HTTP 状态码为 200
    - 返回 data.exists = True
    """
    # 设置 mock 返回文件存在
    mock_minio_service.file_exists.return_value = True

    # 发送存在性检查请求
    # key 参数指定要检查的文件路径
    response = client.get("/exists", params={"key": "user-avatars/user123/avatar.jpg"})

    # 断言验证
    assert response.status_code == 200
    assert response.json()["data"]["exists"] is True


# =============================================================================
# 文件删除测试
# =============================================================================

@patch("app.services.minio_service.delete_file", mock_minio_service.delete_file)
def test_delete_file():
    """
    测试文件删除功能

    测试步骤：
    1. 模拟 delete_file 方法
    2. 发送 DELETE 请求到 /delete 端点
    3. 验证删除成功的消息

    预期结果：
    - HTTP 状态码为 200
    - 返回包含被删除文件 key 的成功消息
    """
    # 设置 mock 返回值（删除操作通常不返回数据）
    mock_minio_service.delete_file.return_value = None

    # 发送删除请求
    # key 参数指定要删除的文件路径
    response = client.delete("/delete", params={"key": "user-avatars/user123/avatar.jpg"})

    # 断言验证
    assert response.status_code == 200
    assert response.json()["message"] == "File user-avatars/user123/avatar.jpg deleted successfully"


# =============================================================================
# 文件列表获取测试
# =============================================================================

@patch("app.services.minio_service.list_files", mock_minio_service.list_files)
def test_list_files():
    """
    测试获取文件列表功能

    用途：列出指定前缀（prefix）下的所有文件

    测试步骤：
    1. 模拟 list_files 方法返回文件列表
    2. 发送 GET 请求到 /list 端点
    3. 验证返回的文件列表

    预期结果：
    - HTTP 状态码为 200
    - 返回包含两个文件的列表
    """
    # 设置 mock 返回文件列表
    mock_minio_service.list_files.return_value = ["file1.jpg", "file2.jpg"]

    # 发送列表请求
    # prefix 参数指定要列出的文件夹前缀
    response = client.get("/list", params={"prefix": "user-avatars/"})

    # 断言验证
    assert response.status_code == 200
    assert "files" in response.json()["data"]
    assert len(response.json()["data"]["files"]) == 2


# =============================================================================
# 预签名下载 URL 生成测试
# =============================================================================

@patch("app.services.minio_service.generate_file_url", mock_minio_service.generate_file_url)
def test_generate_download_url():
    """
    测试生成预签名下载 URL 功能

    用途：生成一个带有时效性的下载链接，客户端可直接使用该 URL 下载文件
    无需经过应用服务器，减轻服务器负担

    测试步骤：
    1. 模拟 generate_file_url 方法返回预签名 URL
    2. 发送 GET 请求到 /generate-download-url 端点
    3. 验证返回的下载 URL

    预期结果：
    - HTTP 状态码为 200
    - 返回完整的预签名下载 URL
    - expires_in 参数控制 URL 有效期（秒）
    """
    # 设置 mock 返回预签名 URL
    mock_minio_service.generate_file_url.return_value = "http://mocked-url/user-avatars/user123/avatar.jpg"

    # 发送生成下载 URL 请求
    # key 参数指定文件路径
    # expires_in 参数指定 URL 有效期（秒），默认 3600 秒（1 小时）
    response = client.get(
        "/generate-download-url",
        params={"key": "user-avatars/user123/avatar.jpg", "expires_in": 3600},
    )

    # 断言验证
    assert response.status_code == 200
    assert "download_url" in response.json()["data"]
    assert response.json()["data"]["download_url"] == "http://mocked-url/user-avatars/user123/avatar.jpg"


# =============================================================================
# 预签名上传 URL 生成测试
# =============================================================================

@patch("app.services.minio_service.generate_upload_url", mock_minio_service.generate_upload_url)
def test_generate_upload_url():
    """
    测试生成预签名上传 URL 功能

    用途：生成一个带有时效性的上传链接，客户端可直接使用该 URL 上传文件
    无需将文件先上传到应用服务器，实现客户端直传到存储服务

    优势：
    - 减轻应用服务器带宽压力
    - 提升上传速度
    - 适合大文件上传场景

    测试步骤：
    1. 模拟 generate_upload_url 方法返回预签名 URL
    2. 发送 GET 请求到 /generate-upload-url 端点
    3. 验证返回的上传 URL

    预期结果：
    - HTTP 状态码为 200
    - 返回完整的预签名上传 URL
    - expires_in 参数控制 URL 有效期
    """
    # 设置 mock 返回预签名上传 URL
    mock_minio_service.generate_upload_url.return_value = "http://mocked-upload-url/user-avatars/user123/avatar.jpg"

    # 发送生成上传 URL 请求
    # key 参数指定目标文件路径
    # expires_in 参数指定 URL 有效期（秒）
    response = client.get(
        "/generate-upload-url",
        params={"key": "user-avatars/user123/avatar.jpg", "expires_in": 3600},
    )

    # 断言验证
    assert response.status_code == 200
    assert "upload_url" in response.json()["data"]
    assert response.json()["data"]["upload_url"] == "http://mocked-upload-url/user-avatars/user123/avatar.jpg"


# =============================================================================
# 通用测试工具使用示例
# =============================================================================

def test_generic_api_example_1_simple_get():
    """
    通用测试工具示例 1：简单 GET 请求

    演示最基本的请求用法
    """
    result = api_tester.request(
        method=HttpMethod.GET,
        path="/minio/test-connection",
        expected_status=200,
    )

    assert result.success, f"请求失败: {result.errors}"


def test_generic_api_example_2_post_with_json():
    """
    通用测试工具示例 2：带 JSON 体的 POST 请求

    演示发送 JSON 数据并验证响应字段
    """
    result = api_tester.request(
        method=HttpMethod.POST,
        path="/api/recipes",  # 假设的端点
        json={
            "title": "测试食谱",
            "description": "这是一个测试食谱",
            "servings": 4,
        },
        expected_status=201,
        expected_fields={
            "data.title": "测试食谱",
            "data.servings": 4,
        },
    )

    assert result.success, f"请求失败: {result.errors}"


def test_generic_api_example_3_with_auth():
    """
    通用测试工具示例 3：带认证的请求

    演示如何添加 JWT Token 进行认证
    """
    # 假设已登录获取到 token
    fake_token = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.fake-token"

    result = api_tester.request(
        method=HttpMethod.GET,
        path="/api/users/me",
        token=fake_token,
        expected_status=200,
    )

    # 注意：这个测试会失败，因为 token 是假的
    # 实际使用时应该先登录获取真实 token


def test_generic_api_example_4_with_params():
    """
    通用测试工具示例 4：带查询参数的请求

    演示如何传递 URL 查询参数
    """
    result = api_tester.request(
        method=HttpMethod.GET,
        path="/api/recipes",
        params={
            "page": 1,
            "per_page": 20,
            "search": "意大利面",
        },
        expected_status=200,
    )


def test_generic_api_example_5_custom_assertion():
    """
    通用测试工具示例 5：自定义断言函数

    演示如何使用自定义断言函数进行复杂验证
    """
    def validate_recipe_count(response):
        """自定义断言：验证返回的食谱数量在合理范围内"""
        data = response.json()
        recipes = data.get("data", {}).get("items", [])
        return 0 <= len(recipes) <= 100

    result = api_tester.request(
        method=HttpMethod.GET,
        path="/api/recipes",
        params={"page": 1},
        assert_func=validate_recipe_count,
    )

    assert result.success, f"请求失败: {result.errors}"


def test_generic_api_example_6_file_upload():
    """
    通用测试工具示例 6：文件上传

    演示如何使用 upload_file 方法上传文件
    """
    # 首先创建测试文件
    test_file_path = "test_upload_example.jpg"
    with open(test_file_path, "wb") as f:
        f.write(b"fake image content for testing")

    # 使用 upload_file 方法
    result = api_tester.upload_file(
        path="/upload-avatar",  # 上传端点
        file_path=test_file_path,
        field_name="file",
        params={"user_id": "test_user_123"},
        expected_status=200,
    )

    # 清理测试文件
    import os
    if os.path.exists(test_file_path):
        os.remove(test_file_path)

    assert result.success, f"上传失败: {result.errors}"


def test_generic_api_example_7_batch_requests():
    """
    通用测试工具示例 7：批量请求

    演示如何一次性发送多个请求
    """
    requests = [
        {
            "method": HttpMethod.GET,
            "path": "/api/categories",
            "expected_status": 200,
        },
        {
            "method": HttpMethod.GET,
            "path": "/api/recipes",
            "params": {"page": 1},
            "expected_status": 200,
        },
        {
            "method": HttpMethod.GET,
            "path": "/api/tags",
            "expected_status": 200,
        },
    ]

    results = api_tester.batch_request(requests, stop_on_error=True)

    # 验证所有请求都成功
    for i, result in enumerate(results):
        assert result.success, f"第 {i+1} 个请求失败: {result.errors}"


def test_generic_api_example_8_delete_request():
    """
    通用测试工具示例 8：DELETE 请求

    演示如何发送删除请求
    """
    result = api_tester.request(
        method=HttpMethod.DELETE,
        path="/delete",
        params={"key": "user-avatars/test.jpg"},
        expected_status=200,
    )

    assert result.success, f"删除失败: {result.errors}"


def test_generic_api_example_9_put_request():
    """
    通用测试工具示例 9：PUT 请求（更新资源）

    演示如何使用 PUT 方法更新资源
    """
    result = api_tester.request(
        method=HttpMethod.PUT,
        path="/api/recipes/123",  # 假设的食谱 ID
        json={
            "title": "更新后的食谱标题",
            "description": "更新后的描述",
        },
        token="fake-token",  # 实际使用时需要真实 token
        expected_status=200,
    )


def test_generic_api_example_10_patch_request():
    """
    通用测试工具示例 10：PATCH 请求（部分更新）

    演示如何使用 PATCH 方法进行部分更新
    """
    result = api_tester.request(
        method=HttpMethod.PATCH,
        path="/api/recipes/123",
        json={
            "title": "只更新标题",  # 只更新部分字段
        },
        token="fake-token",
    )


# =============================================================================
# 通用测试工具高级用法示例
# =============================================================================

class TestApiEndpoints:
    """
    使用通用测试工具的测试类示例

    演示如何在测试类中使用 api_tester
    """

    def test_user_registration(self):
        """用户注册测试"""
        result = api_tester.request(
            method=HttpMethod.POST,
            path="/api/auth/register",
            json={
                "username": "testuser",
                "email": "test@example.com",
                "password": "secure_password_123",
            },
            expected_status=201,
            expected_fields={
                "data.username": "testuser",
                "data.email": "test@example.com",
            },
        )
        assert result.success

    def test_user_login(self):
        """用户登录测试"""
        result = api_tester.request(
            method=HttpMethod.POST,
            path="/api/auth/login",
            data={  # 使用表单数据
                "username": "testuser",
                "password": "secure_password_123",
            },
            expected_status=200,
            assert_func=lambda r: "access_token" in r.json().get("data", {}),
        )
        assert result.success

    def test_protected_endpoint_without_auth(self):
        """测试未认证访问受保护端点"""
        result = api_tester.request(
            method=HttpMethod.GET,
            path="/api/users/me",
            expected_status=401,  # 应该返回 401 Unauthorized
        )
        assert result.success

    def test_create_recipe_with_auth(self):
        """创建食谱测试（需要认证）"""
        # 假设的 token
        token = "valid_jwt_token_here"

        result = api_tester.request(
            method=HttpMethod.POST,
            path="/api/recipes",
            token=token,
            json={
                "title": "意大利面",
                "description": "经典意大利面食谱",
                "prep_time": 15,
                "cook_time": 30,
                "servings": 4,
                "difficulty": "简单",
            },
            expected_status=201,
        )
        assert result.success


# =============================================================================
# 快速测试辅助函数
# =============================================================================

def quick_get(path: str, params: dict = None) -> ApiTestResult:
    """
    快速 GET 请求辅助函数

    Args:
        path: 请求路径
        params: 查询参数

    Returns:
        ApiTestResult: 测试结果
    """
    return api_tester.request(
        method=HttpMethod.GET,
        path=path,
        params=params,
        verbose=False,  # 静默模式，不打印详细信息
    )


def quick_post(path: str, json: dict = None, token: str = None) -> ApiTestResult:
    """
    快速 POST 请求辅助函数

    Args:
        path: 请求路径
        json: JSON 请求体
        token: JWT Token

    Returns:
        ApiTestResult: 测试结果
    """
    return api_tester.request(
        method=HttpMethod.POST,
        path=path,
        json=json,
        token=token,
        verbose=False,
    )


def quick_delete(path: str, params: dict = None) -> ApiTestResult:
    """
    快速 DELETE 请求辅助函数
    """
    return api_tester.request(
        method=HttpMethod.DELETE,
        path=path,
        params=params,
        verbose=False,
    )


# 快速辅助函数使用示例
def test_quick_helpers_example():
    """快速辅助函数使用示例"""
    # 使用快速辅助函数让测试代码更简洁
    result = quick_get("/api/test", params={"page": 1})
    assert result.status_code == 200

    result = quick_post("/api/test", json={"title": "新食谱"})
    assert result.status_code == 201  # 假设创建成功
