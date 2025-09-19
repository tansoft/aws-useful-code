import json
from typing import *

from lark_oapi.core.construct import init
from lark_oapi.core.enum import HttpMethod, AccessTokenType
from lark_oapi.core.model import BaseRequest
from lark_oapi.core.model import RawRequest


class PrivacyCardMessageRequestBody(object):
    _types = {
        "chat_id": str,
        "user_id": str,
        "open_id": str,
        "msg_type": str,
        "card": object
    }

    def __init__(self, d=None):
        self.chat_id: Optional[str] = None
        self.user_id: Optional[str] = None
        self.open_id: Optional[str] = None
        self.msg_type: Optional[str] = "interactive"
        self.card: Optional[object] = None
        init(self, d, self._types)

    @staticmethod
    def builder() -> "PrivacyCardMessageRequestBodyBuilder":
        return PrivacyCardMessageRequestBodyBuilder()


class PrivacyCardMessageRequestBodyBuilder(object):
    def __init__(self) -> None:
        self._privacy_card_message_request_body = PrivacyCardMessageRequestBody()

    def chat_id(self, chat_id: str) -> "PrivacyCardMessageRequestBodyBuilder":
        self._privacy_card_message_request_body.chat_id = chat_id
        return self

    def user_id(self, user_id: str) -> "PrivacyCardMessageRequestBodyBuilder":
        self._privacy_card_message_request_body.user_id = user_id
        return self

    def open_id(self, open_id: str) -> "PrivacyCardMessageRequestBodyBuilder":
        self._privacy_card_message_request_body.content = open_id
        return self

    def msg_type(self, msg_type: str) -> "PrivacyCardMessageRequestBodyBuilder":
        self._privacy_card_message_request_body.content = msg_type
        return self

    def card(self, card: object) -> "PrivacyCardMessageRequestBodyBuilder":
        self._privacy_card_message_request_body.card = card
        return self

    def build(self) -> "PrivacyCardMessageRequestBody":
        return self._privacy_card_message_request_body


class PrivacyCardMessageRequest(BaseRequest):
    def __init__(self) -> None:
        super().__init__()
        self.request_body: Optional[PrivacyCardMessageRequestBody] = None

    @staticmethod
    def builder() -> "PrivacyCardMessageRequestBuilder":
        return PrivacyCardMessageRequestBuilder()


class PrivacyCardMessageRequestBuilder(object):

    def __init__(self) -> None:
        privacy_card_message_request = PrivacyCardMessageRequest()
        privacy_card_message_request.http_method = HttpMethod.POST
        privacy_card_message_request.uri = "/open-apis/ephemeral/v1/send"
        privacy_card_message_request.token_types = {AccessTokenType.TENANT, AccessTokenType.USER}
        self._privacy_card_message_request: PrivacyCardMessageRequest = privacy_card_message_request

    def request_body(self, request_body: PrivacyCardMessageRequestBody) -> "PrivacyCardMessageRequestBuilder":
        self._privacy_card_message_request.request_body = request_body
        self._privacy_card_message_request.body = request_body
        return self

    def build(self) -> PrivacyCardMessageRequest:
        return self._privacy_card_message_request


class Action(object):
    _types = {}

    def __init__(self, d=None) -> None:
        self.value: Dict[str, Any] = {}
        self.tag: Optional[str] = None
        self.option: Optional[str] = None
        self.timezone: Optional[str] = None
        init(self, d, self._types)


# 互动卡片回调
class Card(object):
    _types = {
        "action": Action
    }

    def __init__(self, d=None) -> None:
        self.app_id: Optional[str] = None
        self.open_id: Optional[str] = None
        self.user_id: Optional[str] = None
        self.tenant_key: Optional[str] = None
        self.open_message_id: Optional[str] = None
        self.open_chat_id: Optional[str] = None
        self.token: Optional[str] = None
        self.challenge: Optional[str] = None
        self.type: Optional[str] = None
        self.action: Optional[Action] = None
        self.raw: Optional[RawRequest] = None
        init(self, d, self._types)


# APP缓存
class AppCache(object):
    _types = {}

    def __init__(self, d=None) -> None:
        self.user_id: Optional[str] = None
        self.appid: Optional[str] = None
        self.app_secret: Optional[str] = None
        self.app_role_type: Optional[float] = 0
        self.verification_token: Optional[str] = None
        self.encrypt_key: Optional[str] = None
        self.robot_appid: Optional[str] = None
        self.robot_api_secret: Optional[str] = None
        self.robot_api_key: Optional[str] = None
        self.robot_domain: Optional[str] = None
        self.robot_spark_url: Optional[str] = None
        self.robot_temperature: Optional[float] = 0.5
        init(self, d, self._types)

    @staticmethod
    def builder() -> "AppCacheBuilder":
        return AppCacheBuilder()

    def to_dict(self):
        return {
            'user_id': self.user_id,
            'appid': self.appid,
            'app_secret': self.app_secret,
            'app_role_type': self.app_role_type,
            'verification_token': self.verification_token,
            'encrypt_key': self.encrypt_key,
            'robot_appid': self.robot_appid,
            'robot_api_secret': self.robot_api_secret,
            'robot_api_key': self.robot_api_key,
            'robot_domain': self.robot_domain,
            'robot_spark_url': self.robot_spark_url,
            'robot_temperature': self.robot_temperature,
        }


class AppCacheBuilder(object):
    def __init__(self) -> None:
        self._app_cache = AppCache()

    def user_id(self, user_id: str) -> "AppCacheBuilder":
        self._app_cache.user_id = user_id
        return self

    def appid(self, appid: str) -> "AppCacheBuilder":
        self._app_cache.appid = appid
        return self

    def app_secret(self, app_secret: str) -> "AppCacheBuilder":
        self._app_cache.app_secret = app_secret
        return self

    def app_role_type(self, app_role_type: float) -> "AppCacheBuilder":
        self._app_cache.app_role_type = app_role_type
        return self

    def verification_token(self, verification_token: str) -> "AppCacheBuilder":
        self._app_cache.verification_token = verification_token
        return self

    def encrypt_key(self, encrypt_key: str) -> "AppCacheBuilder":
        self._app_cache.encrypt_key = encrypt_key
        return self

    def robot_appid(self, robot_appid: str) -> "AppCacheBuilder":
        self._app_cache.robot_appid = robot_appid
        return self

    def robot_api_secret(self, robot_api_secret: str) -> "AppCacheBuilder":
        self._app_cache.robot_api_secret = robot_api_secret
        return self

    def robot_api_key(self, robot_api_key: str) -> "AppCacheBuilder":
        self._app_cache.robot_api_key = robot_api_key
        return self

    def robot_domain(self, robot_domain: str) -> "AppCacheBuilder":
        self._app_cache.robot_domain = robot_domain
        return self

    def robot_spark_url(self, robot_spark_url: str) -> "AppCacheBuilder":
        self._app_cache.robot_spark_url = robot_spark_url
        return self

    def robot_temperature(self, robot_temperature: float) -> "AppCacheBuilder":
        self._app_cache.robot_temperature = robot_temperature
        return self

    def build(self) -> "AppCache":
        return self._app_cache


# 卡片构造
class WinCard(object):
    _types = {
        "card": str,
        "text_content": str,
        "image_key": list,
        "mate": bool,
        "privacy": bool,
        "continue_processing": bool,
    }

    def __init__(self, d=None):
        self.card: Optional[str] = None
        self.text_content: Optional[str] = None
        self.image_key: Optional[list] = None
        self.mate: Optional[bool] = False
        self.privacy: Optional[bool] = True
        self.continue_processing: Optional[bool] = True
        init(self, d, self._types)

    @staticmethod
    def builder() -> "WinCardBuilder":
        return WinCardBuilder()

    def to_json(self) -> str:
        return json.dumps(self, default=lambda o: o.dict, ensure_ascii=False)


class WinCardBuilder(object):
    def __init__(self) -> None:
        self._win_card = WinCard()

    def card(self, card: str) -> "WinCardBuilder":
        self._win_card.card = card
        return self

    def text_content(self, text_content: str) -> "WinCardBuilder":
        self._win_card.text_content = text_content
        return self

    def image_key(self, image_key: list) -> "WinCardBuilder":
        self._win_card.image_key = image_key
        return self

    def mate(self, mate: bool) -> "WinCardBuilder":
        self._win_card.mate = mate
        return self

    def privacy(self, privacy: bool) -> "WinCardBuilder":
        self._win_card.privacy = privacy
        return self

    def continue_processing(self, continue_processing: bool) -> "WinCardBuilder":
        self._win_card.continue_processing = continue_processing
        return self

    def build(self) -> "WinCard":
        return self._win_card
