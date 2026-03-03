import requests
from unittest.mock import patch

# Mock 外部请求
def mock_get(*args, **kwargs):
    class MockResponse:
        def __init__(self):
            self.status_code = 200
            self.text = "Mocked response data"
    return MockResponse()

# 使用 mock 替换 requests.get
patch('requests.get', mock_get).start()
