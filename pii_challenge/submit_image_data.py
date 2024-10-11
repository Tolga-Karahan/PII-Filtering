import dotenv
import json
import os
from pathlib import Path
import pika
from pika.adapters.blocking_connection import BlockingChannel
import logging


def connect_to_broker():
    credentials = pika.PlainCredentials(
        os.getenv("RABBITMQ_USERNAME"), os.getenv("RABBITMQ_PASSWORD")
    )
    connection = pika.BlockingConnection(
        pika.ConnectionParameters(credentials=credentials)
    )
    logging.info(f"Connection is open: {connection.is_open}")
    return connection


def submit_images(channel, exchange_name:str):
    supported_image_extensions = os.getenv(
        "SUPPORTED_IMAGE_EXTENSIONS", "jpg,png"
    ).split(",")
    logging.info(f"Supported extensions: {supported_image_extensions}")

    image_folder = Path(os.getenv("IMAGE_SOURCE")).joinpath("images")
    metadata_folder = Path(os.getenv("IMAGE_SOURCE")).joinpath("metadata")
    images = os.listdir(image_folder)

    logging.debug(images)
    for img in images:
        publish_image_data(img, exchange_name, supported_image_extensions, metadata_folder, channel)


def publish_image_data(
    img: str, exchange_name:str, supported_image_extensions: list[str], metadata_folder_path: Path, channel: BlockingChannel
):
    logging.debug(img)
    path = Path(img)
    extension = path.suffix
    logging.info(extension)

    if extension in supported_image_extensions:
        name = path.stem
        terms_file = f"{name}.json"

        terms_file_path = metadata_folder_path.joinpath(terms_file)
        logging.info(f"terms_file_path: {terms_file_path}")

        if terms_file in os.listdir(metadata_folder_path):
            logging.info(f"Sending the message for {img}!")
            with open(terms_file_path) as f:
                pii_terms = json.load(f)["pii_terms"]
                logging.debug(pii_terms)

            body = {"image_path": str(img), "pii_terms": pii_terms}
            channel.basic_publish(
                exchange=exchange_name, routing_key="images", body=json.dumps(body)
            )


if __name__ == "__main__":
    try:
        logging.basicConfig(
            format="%(asctime)s - %(levelname)s - %(message)s", level=logging.INFO
        )
        dotenv.load_dotenv()
        con = connect_to_broker()
        channel = con.channel()
        # queue_declare is idempotent. Result is same no matter how many times it is called.
        channel.queue_declare("images")
        exchange_name = "images_exchange"
        channel.exchange_declare(exchange=exchange_name, exchange_type='direct')
        channel.queue_bind(exchange=exchange_name, queue="images", routing_key="images")
        submit_images(channel, exchange_name)

    except Exception as e:
        logging.error(e)
    finally:
        con.close()
