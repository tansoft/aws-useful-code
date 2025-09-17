import datetime
import json
import uuid

import lark_oapi as lark
from lark_oapi.api.contact.v3 import GetUserRequest, GetUserResponse
from lark_oapi.api.im.v1 import *

from exts import cache
from model import AppCache, PrivacyCardMessageRequest, PrivacyCardMessageRequestBody
from util.redisServer import redis


# 获取现行时间 yyyy-MM-dd HH:mm:ss格式
def get_current_time():
    now = datetime.datetime.now()
    return now.strftime("%Y-%m-%d %H:%M:%S")


# 根据APP_ID获取APP_SECRET
def get_app_secret(appid):
    appCacheJson = cache.get(":robot_app_key:" + appid)
    if appCacheJson:
        return AppCache(appCacheJson).app_secret
    return None


# 获取消息中的资源文件
def get_message_file(appid: str, message_id: str, file_key: str, file_type: str):
    # 创建client
    client = lark.Client.builder() \
        .app_id(appid) \
        .app_secret(get_app_secret(appid)) \
        .log_level(lark.LogLevel.ERROR) \
        .build()

    # 构造请求对象
    request: GetMessageResourceRequest = GetMessageResourceRequest.builder() \
        .message_id(message_id) \
        .file_key(file_key) \
        .type(file_type) \
        .build()

    # 发起请求
    response: GetMessageResourceResponse = client.im.v1.message_resource.get(request)

    # 处理失败返回
    if not response.success():
        lark.logger.error(
            f"client.im.v1.message_resource.get failed, code: {response.code}, msg: {response.msg}, log_id: {response.get_log_id()}")
    # 处理业务结果

    return response


# 上传图片
def _upload_image(app_id: str) -> str:
    # 创建client
    client = lark.Client.builder() \
        .app_id(app_id) \
        .app_secret(get_app_secret(app_id)) \
        .log_level(lark.LogLevel.ERROR) \
        .build()

    file = open("E:\\桌面\\推广.jpg", "rb")
    request = CreateImageRequest.builder() \
        .request_body(CreateImageRequestBody.builder()
                      .image_type("message")
                      .image(file)
                      .build()) \
        .build()

    response = client.im.v1.image.create(request)

    if not response.success():
        raise Exception(
            f"client.im.v1.image.create failed, code: {response.code}, msg: {response.msg}, log_id: {response.get_log_id()}")
    return response.data.image_key


# 获取会话信息
def get_chat_info(chat_id: str, app_id: str) -> GetChatResponseBody:
    # 创建client
    client = lark.Client.builder() \
        .app_id(app_id) \
        .app_secret(get_app_secret(app_id)) \
        .log_level(lark.LogLevel.ERROR) \
        .build()

    request = GetChatRequest.builder() \
        .chat_id(chat_id) \
        .build()

    response = client.im.v1.chat.get(request)

    if not response.success():
        raise Exception(
            f"client.im.v1.chat.get failed, code: {response.code}, msg: {response.msg}, log_id: {response.get_log_id()}")

    return response.data


def get_message(app_id: str, message_id: str) -> GetMessageResponse:
    # 创建client
    client = lark.Client.builder() \
        .app_id(app_id) \
        .app_secret(get_app_secret(app_id)) \
        .log_level(lark.LogLevel.ERROR) \
        .build()

    # 构造请求对象
    request: GetMessageRequest = GetMessageRequest.builder() \
        .message_id(message_id) \
        .build()

    # 发起请求
    response: GetMessageResponse = client.im.v1.message.get(request)

    # 处理失败返回
    if not response.success():
        lark.logger.error(
            f"client.im.v1.message.get failed, code: {response.code}, msg: {response.msg}, log_id: {response.get_log_id()}")
        return response

    return response


def get_text_from_json(json_str):
    data = json.loads(json_str)
    elements = data["elements"]
    first_element = elements[0]
    third_member = first_element[2]
    text = third_member["text"]
    return text


def updateTextCard(app_id, message_id, content) -> bool:
    # 创建client
    client = lark.Client.builder() \
        .app_id(app_id) \
        .app_secret(get_app_secret(app_id)) \
        .log_level(lark.LogLevel.ERROR) \
        .build()

    # 构造请求对象
    request: PatchMessageRequest = PatchMessageRequest.builder() \
        .message_id(message_id) \
        .request_body(PatchMessageRequestBody.builder()
                      .content(content)
                      .build()) \
        .build()

    # 发起请求
    response: PatchMessageResponse = client.im.v1.message.patch(request)

    # 处理失败返回
    if not response.success():
        lark.logger.error(
            f"client.im.v1.message.patch failed, code: {response.code}, msg: {response.msg}, log_id: {response.get_log_id()}")

    return response.success()


# 通用发送消息
def send_message(app_id: str, receive_id_type: str, receive_id: str, msg_type: str, content: str) -> bool:
    # 创建client
    client = lark.Client.builder() \
        .app_id(app_id) \
        .app_secret(get_app_secret(app_id)) \
        .log_level(lark.LogLevel.ERROR) \
        .build()

    # 构造请求对象
    request: CreateMessageRequest = CreateMessageRequest.builder() \
        .receive_id_type(receive_id_type) \
        .request_body(CreateMessageRequestBody.builder()
                      .receive_id(receive_id)
                      .msg_type(msg_type)
                      .content(content)
                      .uuid(str(uuid.uuid4()))
                      .build()) \
        .build()

    # 发起请求
    response: CreateMessageResponse = client.im.v1.message.create(request)

    # 处理失败返回
    if not response.success():
        lark.logger.error(
            f"client.im.v1.message.create failed, code: {response.code}, msg: {response.msg}, log_id: {response.get_log_id()}")
        return response.success()

    # 处理业务结果
    return response.success()


# 通用发送消息
def send_privacy_card_message(app_id: str, chat_id: str, user_id: str, open_id: str, msg_type: str,
                              content: str) -> bool:
    # 创建client
    client = lark.Client.builder() \
        .app_id(app_id) \
        .app_secret(get_app_secret(app_id)) \
        .log_level(lark.LogLevel.ERROR) \
        .build()

    # 构造请求对象
    request: PrivacyCardMessageRequest = PrivacyCardMessageRequest.builder() \
        .request_body(PrivacyCardMessageRequestBody.builder() \
                      .chat_id(chat_id) \
                      .user_id(user_id) \
                      .open_id(open_id) \
                      .msg_type(msg_type)
                      .card(json.loads(content))
                      .build()) \
        .build()

    # 发起请求
    response: CreateMessageResponse = client.im.v1.message.create(request)

    # 处理失败返回
    if not response.success():
        lark.logger.error(
            f"client.im.v1.message.create failed, code: {response.code}, msg: {response.msg}, log_id: {response.get_log_id()}")
        return response.success()

    # 处理业务结果
    return response.success()


# 通用回复消息
def reply_message(app_id: str, message_id: str, content: str, msg_type: str) -> ReplyMessageResponse:
    # 创建client
    client = lark.Client.builder() \
        .app_id(app_id) \
        .app_secret(get_app_secret(app_id)) \
        .log_level(lark.LogLevel.ERROR) \
        .build()

    # 构造请求对象
    request: ReplyMessageRequest = ReplyMessageRequest.builder() \
        .message_id(message_id) \
        .request_body(ReplyMessageRequestBody.builder()
                      .content(content)
                      .msg_type(msg_type)
                      .uuid(str(uuid.uuid4()))
                      .build()) \
        .build()
    # 发起请求
    response: ReplyMessageResponse = client.im.v1.message.reply(request)

    # 处理失败返回
    if not response.success():
        lark.logger.error(
            f"client.im.v1.message.reply failed, code: {response.code}, msg: {response.msg}, log_id: {response.get_log_id()}")
        return response

    # 处理业务结果

    return response


# length = 0

def getText(user_id, role, content):
    text = redis.get(":message_context:" + user_id)
    if text is None:
        text = []
    jsoncon = {"role": role, "content": content}
    text.append(jsoncon)
    return text


def getlength(text):
    length = 0
    for content in text:
        temp = content["content"]
        leng = len(temp)
        length += leng
    return length


def checklen(user_id, text):
    while getlength(text) > 8000:
        del text[0]
    redis.set(":message_context:" + user_id, text)
    return text


def get_user(appid, user_id) -> GetUserResponse:
    # 创建client
    client = lark.Client.builder() \
        .app_id(appid) \
        .app_secret(get_app_secret(appid)) \
        .log_level(lark.LogLevel.ERROR) \
        .build()

    # 构造请求对象
    request: GetUserRequest = GetUserRequest.builder() \
        .user_id(user_id) \
        .user_id_type("user_id") \
        .build()

    # 发起请求
    response: GetUserResponse = client.contact.v3.user.get(request)

    # 处理失败返回
    if not response.success():
        lark.logger.error(
            f"client.contact.v3.user.get failed, code: {response.code}, msg: {response.msg}, log_id: {response.get_log_id()}")

    return response
