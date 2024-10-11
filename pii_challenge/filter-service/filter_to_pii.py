import dotenv
import json
import os
from pathlib import Path
import pika
import logging

from models.models import TextBoundingBox
from utils.utils import EnhancedJSONEncoder

EXCHANGE_NAME= "filter_pii_exchange"

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

    pii_boxes = find_pii_terms(body["pii_terms"], json.loads(body["boxes"]))

    # publish bounding boxes
    logging.info(f"Publishing bounding boxes for PII terms!")

    body = json.dumps(pii_boxes, cls=EnhancedJSONEncoder)
    logging.info(body)
    ch.basic_publish(exchange=EXCHANGE_NAME, routing_key="pii_bounding_boxes", body=body)


def find_pii_terms(pii_terms: list[str], boxes: list[TextBoundingBox]):
    return [box for box in boxes if box["text"] in pii_terms]


if __name__ == "__main__":
    try:
        logging.basicConfig(
            format="%(asctime)s - %(levelname)s - %(message)s", level=logging.INFO
        )
        dotenv.load_dotenv()
        con = connect_to_broker()

        channel = con.channel()
        # queue_declare is idempotent. Result is same no matter how many times it is called.
        channel.queue_declare("bounding_boxes")
        channel.queue_declare("pii_bounding_boxes")
        channel.exchange_declare(exchange=EXCHANGE_NAME, exchange_type='direct')
        channel.queue_bind(exchange=EXCHANGE_NAME, queue="pii_bounding_boxes", routing_key="pii_bounding_boxes")
        channel.basic_consume(
            queue="bounding_boxes", auto_ack=True, on_message_callback=callback
        )
        channel.start_consuming()
    except Exception as e:
        logging.error(e)
    finally:
        con.close()
