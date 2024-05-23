import json
import logging
import urllib.request
import cv2
import os
import numpy as np
import pika
import signal
from colorama import Fore, Style, init

init(autoreset=True)

RABBITMQ_HOST = "localhost"
RABBITMQ_PORT = 5672

connection = pika.BlockingConnection(
    pika.ConnectionParameters(host=RABBITMQ_HOST, port=RABBITMQ_PORT)
)
channel = connection.channel()

queue_name = "chmiel_kolejka"
channel.queue_declare(queue=queue_name)
channel.basic_qos(prefetch_count=1)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger(__name__)

def draw_rectangles(image, detected_objects):
    for i in range(detected_objects.shape[2]):
        confidence = detected_objects[0][0][i][2]
        if confidence > 0.3:
            class_index = int(detected_objects[0, 0, i, 1])
            if class_index == 15:
                height, width = image.shape[0], image.shape[1]

                upper_left_x = int(detected_objects[0, 0, i, 3] * width)
                upper_left_y = int(detected_objects[0, 0, i, 4] * height)
                lower_right_x = int(detected_objects[0, 0, i, 5] * width)
                lower_right_y = int(detected_objects[0, 0, i, 6] * height)

                cv2.rectangle(
                    image,
                    (upper_left_x, upper_left_y),
                    (lower_right_x, lower_right_y),
                    (0, 255, 0),
                    3,
                )


def count_people(detected_objects):
    num_people = sum(
        1
        for i in range(detected_objects.shape[2])
        if int(detected_objects[0, 0, i, 1]) == 15
    )
    return num_people


def process_image(image_path):
    prototxt_path = "model/MobileNetSSD_deploy.prototxt.txt"
    model_path = "model/MobileNetSSD_deploy.caffemodel"

    net = cv2.dnn.readNetFromCaffe(prototxt_path, model_path)

    image = cv2.imread(image_path)
    blob = cv2.dnn.blobFromImage(cv2.resize(image, (300, 300)), 0.007, (300, 300), 130)

    net.setInput(blob)
    detected_objects = net.forward()

    draw_rectangles(image, detected_objects)

    output_image_path = os.path.join(
        "uploaded_images", "marked_" + os.path.basename(image_path)
    )
    cv2.imwrite(output_image_path, image)

    num_people = count_people(detected_objects)

    return num_people, output_image_path


def process_image_url(image, task_id, file_extension):
    prototxt_path = "model/MobileNetSSD_deploy.prototxt.txt"
    model_path = "model/MobileNetSSD_deploy.caffemodel"

    net = cv2.dnn.readNetFromCaffe(prototxt_path, model_path)

    blob = cv2.dnn.blobFromImage(cv2.resize(image, (300, 300)), 0.007, (300, 300), 130)

    net.setInput(blob)
    detected_objects = net.forward()

    draw_rectangles(image, detected_objects)

    uploaded_images = "uploaded_images"
    if not os.path.exists(uploaded_images):
        os.makedirs(uploaded_images)

    output_image_path = os.path.join(
        uploaded_images, f"marked_{task_id}.{file_extension}"
    )
    cv2.imwrite(output_image_path, image)

    num_people = count_people(detected_objects)

    return num_people, output_image_path


def read_image_from_url(url):
    resp = urllib.request.urlopen(url)
    image = np.asarray(bytearray(resp.read()), dtype="uint8")
    image = cv2.imdecode(image, cv2.IMREAD_COLOR)
    return image


def callback(ch, method, properties, body):
    try:
        task_data = json.loads(body.decode())
        task_id = task_data["task_id"]
        url = task_data["url"]
        file_extension = task_data["file_extension"]

        image = read_image_from_url(url)

        count, filename = process_image_url(image, task_id, file_extension)

        message = f"Processed task with ID {task_id} by process {os.getpid()}. Detected {count} people. Image saved as {filename}. WELL DONE!"
        info = f"{count} people detected on URL:{url}"

        logging.info(message)
        print(Fore.GREEN + info)

    except Exception as error:
        error_message = f"Error processing task: {str(error)}"
        logging.error(error_message)

    ch.basic_ack(delivery_tag=method.delivery_tag)


def start_consuming():
    channel.basic_consume(
        queue=queue_name, on_message_callback=callback, auto_ack=False
    )
    channel.start_consuming()

def handle_exit(signum, frame):
    logger.info("Gracefully shutting down...")
    try:
        if channel.is_open:
            channel.close()
        if connection.is_open:
            connection.close()
    except Exception as e:
        logger.error(f"Error during shutdown: {e}")
    exit(0)

if __name__ == "__main__":
    signal.signal(signal.SIGINT, handle_exit)
    signal.signal(signal.SIGTERM, handle_exit)
    start_consuming()
