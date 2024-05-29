import logging
import os
import uuid
import re
import asyncio
from fastapi import FastAPI, UploadFile, File, Request, Form
from fastapi.responses import JSONResponse, HTMLResponse
import aiohttp
from fastapi.templating import Jinja2Templates
import shutil
from consumer import process_image
import aio_pika
import json

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)
file_handler = logging.FileHandler("app.log")
file_handler.setLevel(logging.INFO)
formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
file_handler.setFormatter(formatter)
logger.addHandler(file_handler)

app = FastAPI()

templates = Jinja2Templates(directory="templates")

RABBITMQ_HOST = "localhost"
RABBITMQ_PORT = 5672

queue_name = "chmiel_kolejka"


async def get_rabbitmq_connection():
    return await aio_pika.connect_robust(f"amqp://guest:guest@{RABBITMQ_HOST}/")


def clean_url(url):
    cleaned_url = url.strip()
    cleaned_url = re.sub(r"[\r\n]", "", cleaned_url)
    return cleaned_url


def fix_url(url):
    if not re.match(r"^(?:http|ftp)s?://", url):
        url = "http://" + url
    return url


async def send_url_to_queue(url, channel):
    url_id = str(uuid.uuid4())
    file_extension = url.split(".")[-1]
    message_body = json.dumps(
        {"task_id": url_id, "url": url, "file_extension": file_extension}
    )

    await channel.default_exchange.publish(
        aio_pika.Message(body=message_body.encode()),
        routing_key=queue_name,
    )

    message = f" [x] Sent URL: {url} with ID {url_id} to RabbitMQ"
    logger.info(message)


@app.get("/", response_class=HTMLResponse)
async def main_page(request: Request):
    logger.info("Rendering main page")
    return templates.TemplateResponse("index.html", {"request": request})


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
        return JSONResponse(
            content={
                "Number of detected people": num_people,
                "output_image_path": output_image_path,
            }
        )
    except Exception as e:
        logger.error(f"An error occurred: {str(e)}")
        return JSONResponse(content={"error": str(e)}, status_code=500)


@app.get("/url/", response_class=HTMLResponse)
async def url_form(request: Request):
    logger.info("Rendering URL form")
    return templates.TemplateResponse("url_form.html", {"request": request})


async def fetch_url(session, url):
    try:
        async with session.get(url) as response:
            if response.status != 200:
                logger.error(f"Cannot download image from URL: {url}")
                return None
            return url
    except Exception as e:
        logger.error(f"Request error for URL {url}: {str(e)}")
        return None


@app.post("/url/")
async def detect_people_from_urls(request: Request):
    try:
        logger.info("Starting URL detection")
        form_data = await request.form()
        image_urls = form_data["image_urls"].split()
        valid_urls = []

        cleaned_urls = [fix_url(clean_url(url)) for url in image_urls]

        connection = await get_rabbitmq_connection()
        channel = await connection.channel()
        await channel.declare_queue(queue_name)

        async with aiohttp.ClientSession() as session:
            tasks = [fetch_url(session, url) for url in cleaned_urls]
            results = await asyncio.gather(*tasks)

            valid_urls = [url for url in results if url]

            publish_tasks = [send_url_to_queue(url, channel) for url in valid_urls]
            await asyncio.gather(*publish_tasks)

        return {"message": f"{len(valid_urls)} URL(s) processed"}
    except Exception as e:
        logger.error(f"An error occurred: {str(e)}")
        return JSONResponse(content={"error": str(e)}, status_code=500)
