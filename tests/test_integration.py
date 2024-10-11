import json
import os
from pathlib import Path
import pika
import pytest

import dotenv

from pii_challenge.submit_image_data import publish_image_data


@pytest.fixture
def connection():
    credentials = pika.PlainCredentials("admin", "admin")
    connection = pika.BlockingConnection(
        pika.ConnectionParameters(credentials=credentials)
    )
    yield connection


@pytest.fixture
def channel(connection):
    yield connection.channel()


@pytest.fixture()
def declare_queues(channel):
    channel.queue_declare("images")
    channel.queue_declare("pii_bounding_boxes")


@pytest.fixture
def env():
    dotenv.load_dotenv()


@pytest.fixture
def gt_boxes():
    yield [
        {"text": "John", "left": 55, "right": 81, "top": 265, "bottom": 275},
        {"text": "Smith", "left": 86, "right": 117, "top": 265, "bottom": 275},
        {"text": "John", "left": 281, "right": 308, "top": 265, "bottom": 275},
        {"text": "Smith", "left": 313, "right": 344, "top": 265, "bottom": 275},
        {"text": "MA", "left": 351, "right": 369, "top": 301, "bottom": 311},
    ]

@pytest.fixture
def exchange_name():
    yield "images_exchange"

def test_pii_bounding_boxes(channel, exchange_name, declare_queues, gt_boxes):
    def callback(ch, method, properties, body):
        ch.stop_consuming()
        boxes = json.loads(body.decode())
        assert boxes == gt_boxes

    dotenv.load_dotenv()

    credentials = pika.PlainCredentials(
        os.getenv("RABBITMQ_USERNAME"), os.getenv("RABBITMQ_PASSWORD")
    )
    connection = pika.BlockingConnection(
        pika.ConnectionParameters(credentials=credentials)
    )

    channel = connection.channel()

    channel.queue_declare("images")
    channel.queue_declare("pii_bounding_boxes")

    supported_image_extensions = os.getenv(
        "SUPPORTED_IMAGE_EXTENSIONS", "jpg,png"
    ).split(",")

    publish_image_data(
        "invoice.png",
        exchange_name,
        supported_image_extensions,
        Path("data/metadata").absolute(),
        channel,
    )
    channel.basic_consume(
        queue="pii_bounding_boxes", auto_ack=True, on_message_callback=callback
    )
    channel.start_consuming()
