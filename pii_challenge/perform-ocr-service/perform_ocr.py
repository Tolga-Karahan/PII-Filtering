from PIL import Image
import json
import logging
import os

import dotenv
from pathlib import Path
import pika
import pytesseract
from pytesseract import Output

from models.models import TextBoundingBox
from utils.utils import EnhancedJSONEncoder


def connect_to_broker():
    credentials = pika.PlainCredentials(
        os.getenv("RABBITMQ_USERNAME"), os.getenv("RABBITMQ_PASSWORD")
    )
    parameters = pika.ConnectionParameters(
        host=os.getenv("RABBITMQ_HOST"), port=5672, credentials=credentials
    )
    connection = pika.BlockingConnection(parameters)
    logging.info(f"Connection is open: {connection.is_open}")
    return connection


def callback(ch, method, properties, body):
    body = json.loads(body.decode())
    logging.debug(f"Consumed message: {body}")
    img_path = body["image_path"]
    abs_image_path = (
        Path(os.getenv("DATA_SOURCE")).joinpath("images").joinpath(img_path)
    )
    boxes = detect_text(abs_image_path)
    # ch.basic_ack()

    # publish bounding boxes
    logging.info(f"Publishing bounding boxes!")
    body["boxes"] = json.dumps(boxes, cls=EnhancedJSONEncoder)
    ch.basic_publish(exchange="", routing_key="bounding_boxes", body=json.dumps(body))


def detect_text(img_path: str) -> list[TextBoundingBox]:
    result = pytesseract.image_to_data(
        Image.open(img_path),
        output_type=Output.DICT,
    )
    logging.info("Calculating bounding boxes!")
    boxes = [
        TextBoundingBox(
            text=result["text"][i],
            left=result["left"][i],
            right=result["left"][i] + result["width"][i],
            top=result["top"][i],
            bottom=result["top"][i] + result["height"][i],
        )
        for i in range(len(result["level"]))
        if result["conf"][i] > 0.5 and result["text"][i].strip() != ""
    ]
    logging.info("Boxes are calculated!")

    return boxes


if __name__ == "__main__":
    logging.basicConfig(
        format="%(asctime)s - %(levelname)s - %(message)s", level=logging.INFO
    )
    dotenv.load_dotenv()
    con = connect_to_broker()
    channel = con.channel()
    # queue_declare is idempotent. Result is same no matter how many times it is called.
    channel.queue_declare("bounding_boxes")
    channel.queue_declare("images")
    channel.basic_consume(queue="images", auto_ack=True, on_message_callback=callback)
    channel.start_consuming()
