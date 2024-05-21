import logging
import os
import uuid
import re
from http.client import HTTPException
from fastapi import FastAPI, UploadFile, File, Request
from fastapi.responses import JSONResponse, HTMLResponse
import requests
from fastapi.templating import Jinja2Templates
import shutil

from pika import channel

from consumer import process_image
import pika
import aio_pika
import json
import subprocess

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)
file_handler = logging.FileHandler('app.log')
file_handler.setLevel(logging.INFO)
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
file_handler.setFormatter(formatter)
logger.addHandler(file_handler)

app = FastAPI()

templates = Jinja2Templates(directory="templates")

RABBITMQ_HOST = 'localhost'
RABBITMQ_PORT = 5672

connection = pika.BlockingConnection(pika.ConnectionParameters(host=RABBITMQ_HOST, port=RABBITMQ_PORT))
channel = connection.channel()

queue_name = 'chmiel_kolejka'
channel.queue_declare(queue=queue_name)

consumer_processes = []


async def get_rabbitmq_connection():
    return await aio_pika.connect_robust("amqp://guest:guest@localhost/")

def clean_url(url):
    cleaned_url = url.strip()
    cleaned_url = re.sub(r'[\r\n]', '', cleaned_url)
    return cleaned_url

def send_url_to_queue(url):
    url_id = str(uuid.uuid4())
    file_extension = url.split('.')[-1]
    message_body = json.dumps({'task_id': url_id, 'url': url, 'file_extension': file_extension})

    channel.basic_publish(exchange='', routing_key=queue_name, body=message_body)

    message = f" [x] Sent URL: {url}  with ID {url_id} to RabbitMQ"
    print(message)


@app.get("/upload/", response_class=HTMLResponse)
async def upload_form(request: Request):
    logger.info("Rendering upload form")
    return templates.TemplateResponse("upload_form.html", {"request": request})


@app.post("/upload/")
async def upload_file(file: UploadFile = File(...)):
    try:
        logger.info("Starting file upload")
        upload_folder = "uploaded_images"
        os.makedirs(upload_folder, exist_ok=True)
        file_path = os.path.join(upload_folder, file.filename)

        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        num_people, output_image_path = process_image(file_path)

        os.remove(file_path)

        logger.info("File processed successfully")
        return JSONResponse(content={"Number of detected people": num_people, "output_image_path": output_image_path})
    except Exception as e:
        logger.error(f"An error occurred: {str(e)}")
        return JSONResponse(content={"error": str(e)}, status_code=500)


@app.get("/url/", response_class=HTMLResponse)
async def url_form(request: Request):
    logger.info("Rendering URL form")
    return templates.TemplateResponse("url_form.html", {"request": request})


@app.post("/url/")
async def detect_people_from_urls(request: Request):
    try:
        logger.info("Starting URL detection")
        form_data = await request.form()
        image_urls = form_data["image_urls"]
        valid_urls = []

        for image_url in image_urls:
            cleaned_url = clean_url(image_url)
            print(cleaned_url)
            response = requests.get(image_url)
            valid_urls.append(cleaned_url)
            if response.status_code != 200:
                logger.error(f"Cannot download image from URL: {image_url}")
                continue

            send_url_to_queue(cleaned_url)

            logger.info(f"Image URL sent to RabbitMQ queue: {image_url}")
            #wyślij kazdy link na kolejke rabbitmq
            # # Zapisz obraz do folderu "uploaded_images"
            # image_filename = os.path.basename(image_url)
            # image_path = os.path.join(upload_folder, image_filename)
            # with open(image_path, "wb") as img_file:
            #     img_file.write(response.content)
            #
            # # Loguj ścieżkę do pobranego pliku
            # logger.info(f"Image downloaded and saved to: {image_path}")
            #
            # try:
            #     num_people, output_image_path = process_image(image_path)
            #     logger.info(f"Image processed: {image_path}, people detected: {num_people}")
            #     os.remove(image_path)
            # except Exception as e:
            #     logger.error(f"Error processing image {image_path}: {str(e)}")


        return {"message": f"{len(image_urls)} URL(s) processed"}
    except Exception as e:
        logger.error(f"An error occurred: {str(e)}")
        return JSONResponse(content={"error": str(e)}, status_code=500)
