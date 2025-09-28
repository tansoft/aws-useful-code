import json
from typing import Any

from api import get_message, get_text_from_json, get_current_time
from cardBuild import *
from event import MessageReceiveEvent
from exts import cache
from model import Card, WinCard
from util.redisServer import redis


# 消息意图处理程序


# 帮助|help
def handle_help(req_data: MessageReceiveEvent, text_content, image_key) -> WinCard:
    return WinCard.builder() \
        .card(help_card_build(req_data.event.sender.sender_id.user_id)) \
        .mate(True) \
        .continue_processing(False) \
        .text_content(text_content) \
        .image_key(image_key) \
        .build()


# 清除|clear
def handle_clear(req_data: MessageReceiveEvent, text_content, image_key) -> WinCard:
    return WinCard.builder() \
        .card(clear_card_build()) \
        .mate(True) \
        .continue_processing(False) \
        .text_content(text_content) \
        .image_key(image_key) \
        .build()


# 模型|model
def handle_model(req_data: MessageReceiveEvent, text_content, image_key) -> WinCard:
    return WinCard.builder() \
        .card(model_select_card_build(req_data.event.sender.sender_id.user_id)) \
        .mate(True) \
        .continue_processing(False) \
        .text_content(text_content) \
        .image_key(image_key) \
        .build()


# 发散模式|ai_mode
def handle_diverge(req_data: MessageReceiveEvent, text_content, image_key) -> WinCard:
    return WinCard.builder() \
        .card(diverge_select_card_build(req_data.event.sender.sender_id.user_id)) \
        .mate(True) \
        .continue_processing(False) \
        .text_content(text_content) \
        .image_key(image_key) \
        .build()


# 卡片事件回调处理程序
# 清除|clear
def card_clear(data: Card) -> WinCard:
    redis.delete(":message_context:" + data.user_id)
    return WinCard.builder() \
        .card(robot_reminder_card_build("🆑 机器人提醒",
                                        "已删除此话题的上下文信息",
                                        "我们可以开始一个全新的话题，继续找我聊天吧")) \
        .mate(True) \
        .continue_processing(False) \
        .build()


# 点赞
def card_praise(data: Card) -> WinCard:
    redis.delete(":message_context:" + data.user_id)
    # if data.action.value.get("success"):
    messagedata = get_message(data.app_id, data.open_message_id)
    # if messagedata.success():
    text_content = get_text_from_json(messagedata.data.items[0].body.content)
    return WinCard.builder() \
        .card(build_card(text_content, True)) \
        .mate(True) \
        .continue_processing(False) \
        .build()


# 模型|model
def card_model(data: Card) -> WinCard:
    user_id = data.user_id
    model_type = data.action.option
    robot_spark_url = ""
    model_type_name = ""
    if model_type == "lite":
        model_type_name = "lite"
        robot_spark_url = "ws://spark-api.xf-yun.com/v1.1/chat"
    elif model_type == "generalv2":
        model_type_name = "lite"
        robot_spark_url = "ws://spark-api.xf-yun.com/v1.1/chat"
    elif model_type == "generalv3":
        model_type_name = "lite"
        robot_spark_url = "ws://spark-api.xf-yun.com/v1.1/chat"
    robot_user_model = get_robot_user_model(user_id)
    robot_user_model.robot_domain = model_type
    robot_user_model.robot_spark_url = robot_spark_url
    cache.set(":robot_user_model:" + user_id, robot_user_model.to_dict())
    return WinCard.builder() \
        .card(robot_reminder_card_build("🚀 机器人提醒",
                                        "已选择模型：**" + model_type_name + "**",
                                        "输入<发散模式> 或 /ai_mode 即可选择发散模式")) \
        .mate(True) \
        .continue_processing(False) \
        .build()


# 发散模式|ai_mode
def card_diverge(data: Card) -> WinCard:
    diverge_type = data.action.option
    user_id = data.user_id
    diverge_type_name = ""
    if diverge_type == "1.0":
        diverge_type_name = "严谨"
    elif diverge_type == "0.75":
        diverge_type_name = "简洁"
    elif diverge_type == "0.5":
        diverge_type_name = "标准"
    elif diverge_type == "0.25":
        diverge_type_name = "发散"
    robot_user_model = get_robot_user_model(user_id)
    robot_user_model.robot_temperature = float(diverge_type)
    cache.set(":robot_user_model:" + user_id, robot_user_model.to_dict())
    return WinCard.builder() \
        .card(robot_reminder_card_build("🤖 机器人提醒",
                                        "已选择发散模式为：**" + diverge_type_name + "**",
                                        "输入<模型> 或 model 即可切换AI模型")) \
        .mate(True) \
        .continue_processing(False) \
        .build()


message_intents = [
    (r'帮助|help', handle_help),
    (r'清除|clear', handle_clear),
    (r'模型|model', handle_model),
    (r'发散模式|ai_mode', handle_diverge),
]

card_event_intents = [
    (r'praise', card_praise),
    (r'clear', card_clear),
    (r'domain_version', card_model),
    (r'temperature', card_diverge),
]


# 消息意图处理
def message_handle_process(req_data: MessageReceiveEvent) -> WinCard:
    text_content = ""
    image_key = []
    data = json.loads(req_data.event.message.content)
    if req_data.event.message.message_type == "post":
        for datacontent in data["content"]:
            for content in datacontent:
                if content["tag"] == "text":
                    text_content += content["text"]
                elif content["tag"] == "img":
                    image_key.append(content["image_key"])
    elif req_data.event.message.message_type == "text":
        text_content = data["text"]
    card_result = WinCard()
    for pattern, handler in message_intents:
        if re.search(pattern, text_content):
            return handler(req_data, text_content, image_key)
    return card_result


# 处理卡片回调
def do_interactive_card(data: Card) -> Any:
    cache.set(":card_event:" + data.open_message_id, "Event has been handle", timeout=25200)
    # 进入消息处理流程，并获取回复内容
    handle_content = card_handle_process(data)
    # 命中预设流程，进行回复
    if handle_content.mate:
        return handle_content.card
    return lark.JSON.marshal({"success": False, "message": "本事件未被定义！", "code": 200})


def card_handle_process(data: Card) -> WinCard:
    content = data.action.value.get("text")
    card_result = WinCard()
    for pattern, handler in card_event_intents:
        if re.search(pattern, content):
            return handler(data)
    return card_result
