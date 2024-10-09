from PIL import Image
import json
import logging
import os

import dotenv
import pika
import pytesseract
from pytesseract import Output
import pandas as pd

from models.models import TextBoundingBox
from utils import EnhancedJSONEncoder

def connect_to_broker():
    credentials = pika.PlainCredentials(
        os.getenv("RABBITMQ_USERNAME"), os.getenv("RABBITMQ_PASSWORD")
    )
    connection = pika.BlockingConnection(
        pika.ConnectionParameters(credentials=credentials)
    )
    logging.info(f"Connection is open: {connection.is_open}")
    return connection

def callback(ch, method, properties, body):
    body = json.loads(body.decode())
    logging.info(f"Consumed message: {body}")
    img_path = body["image_path"]
    result = pytesseract.image_to_data(
        Image.open(img_path),
        output_type=Output.DICT,
    )
    logging.info("Calculating bounding boxes!")
    boxes = [
        TextBoundingBox(
            text=result["text"][i],
            left=result["left"][i],
            right=result["left"][i]+result["width"][i],
            top=result["top"][i],
            bottom=result["top"][i]+result["height"][i],
        ) 
        for i in range(len(result["level"]))
        if result["conf"][i] > 0.5 and result["text"][i].strip() != ''
    ]
    logging.info("Boxes are calculated!")
    # publish bounding boxes
    for box in boxes:
        logging.info(f"Publishing box: {box}")
        # queue_declare is idempotent. Result is same no matter how many times it is called.
        ch.queue_declare("bounding_boxes")
        body = {"box": json.dumps(box, cls=EnhancedJSONEncoder)}
        ch.basic_publish(
            exchange="", routing_key="bounding_boxes", body=json.dumps(body)
        )
    


# from spacy import displacy, load
# nlp = load("en_core_web_sm")
# doc = nlp(pytesseract.image_to_string(Image.open("/Users/tkarahan/repos/pii-challenge/images/invoice.png")))
# entities = [(ent.text, ent.label_, ent.lemma_) for ent in doc.ents]
# df = pd.DataFrame(entities, columns=['text', 'type', 'lemma'])
# print(df)

if __name__ == "__main__":
    logging.basicConfig(
        format="%(asctime)s - %(levelname)s - %(message)s", level=logging.INFO
    )
    dotenv.load_dotenv()
    con = connect_to_broker()
    channel = con.channel()
    channel.basic_consume(queue="images", auto_ack=True, on_message_callback=callback)
    channel.start_consuming()