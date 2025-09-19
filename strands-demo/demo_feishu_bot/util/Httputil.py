from typing import *

import requests
from lark_oapi import RawResponse, UTF_8, JSON, Files, CONTENT_TYPE, HttpMethod, AccessTokenType
from requests_toolbelt import MultipartEncoder


class BaseRequest(object):
    def __init__(self) -> None:
        self.http_method: Optional[HttpMethod] = None
        self.uri: Optional[str] = None
        self.paths: Dict[str, str] = {}
        self.queries: List[Tuple[str, str]] = []
        self.headers: Dict[str, str] = {}
        self.body: Any = None

    def add_query(self, k: str, v: Any) -> None:
        if isinstance(v, (list, tuple)):
            for i in v:
                self.queries.append((k, str(i)))
        else:
            self.queries.append((k, str(v)))

    @staticmethod
    def builder() -> "BaseRequestBuilder":
        return BaseRequestBuilder()


class BaseRequestBuilder(object):

    def __init__(self, base_request: BaseRequest = BaseRequest()) -> None:
        self._base_request: BaseRequest = base_request

    def http_method(self, http_method: HttpMethod) -> "BaseRequestBuilder":
        self._base_request.http_method = http_method
        return self

    def uri(self, uri: str) -> "BaseRequestBuilder":
        self._base_request.uri = uri
        return self

    def token_types(self, token_types: Set[AccessTokenType]) -> "BaseRequestBuilder":
        self._base_request.token_types = token_types
        return self

    def paths(self, paths: Dict[str, str]) -> "BaseRequestBuilder":
        self._base_request.paths = paths
        return self

    def queries(self, queries: List[Tuple[str, str]]) -> "BaseRequestBuilder":
        self._base_request.queries = queries
        return self

    def headers(self, headers: Dict[str, str]) -> "BaseRequestBuilder":
        self._base_request.headers = headers
        return self

    def body(self, body: Any) -> "BaseRequestBuilder":
        self._base_request.body = body
        return self

    def build(self) -> BaseRequest:
        return self._base_request


class Http(object):

    @staticmethod
    def execute(request: BaseRequest) -> RawResponse:
        data = request.body
        if data is not None and not isinstance(data, MultipartEncoder):
            # data = JSON.marshal(request.body).encode(UTF_8)#原始序列化
            data = JSON.marshal(marshal_data(request.body)).encode(UTF_8)  # 字段值为None则不进行序列化

        response = requests.request(
            str(request.http_method.name),
            request.uri,
            headers=request.headers,
            params=request.queries,
            data=data,
            timeout=None,
        )

        resp = RawResponse()
        resp.status_code = response.status_code
        resp.headers = dict(response.headers)
        resp.content = response.content

        return resp

    @staticmethod
    def create(request: BaseRequest) -> RawResponse:
        # 处理 form-data
        if request.body is not None:
            form_data = MultipartEncoder(Files.parse_form_data(request.body))
            request.headers[CONTENT_TYPE] = form_data.content_type
            request.body = form_data

        return Http.execute(request)


def marshal_data(data):
    if data is not None:
        if isinstance(data, dict):
            return {k: marshal_data(v) for k, v in data.items() if v is not None}
        elif isinstance(data, list):
            return [marshal_data(item) for item in data if item is not None]
        else:
            return data
    else:
        return None
