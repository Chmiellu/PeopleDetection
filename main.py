import logging
import os

from http.client import HTTPException
from fastapi import FastAPI, UploadFile, File, Request
from fastapi.responses import JSONResponse, HTMLResponse
import requests
from fastapi.templating import Jinja2Templates
import shutil
from counter import process_image
import pika


logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)
file_handler = logging.FileHandler('app.log')
file_handler.setLevel(logging.INFO)
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
file_handler.setFormatter(formatter)
logger.addHandler(file_handler)

app = FastAPI()

templates = Jinja2Templates(directory="templates")

async def get_rabbitmq_connection():
    return await aio_pika.connect_robust("amqp://guest:guest@localhost/")


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
async def detect_people_from_url(request: Request):
    try:
        logger.info("Starting URL detection")
        form_data = await request.form()
        image_url = form_data["image_url"]

        response = requests.get(image_url)
        if response.status_code != 200:
            raise HTTPException(status_code=404, detail="Nie można pobrać obrazu z podanego URL.")

        # Save the image to the "uploaded_images" folder
        upload_folder = "uploaded_images"
        os.makedirs(upload_folder, exist_ok=True)
        image_filename = os.path.basename(image_url)
        image_path = os.path.join(upload_folder, image_filename)
        with open(image_path, "wb") as img_file:
            img_file.write(response.content)

        num_people, output_image_path = process_image(image_path)
        os.remove(image_path)

        logger.info("URL detection completed successfully")
        return {"Number of detected people": num_people, "output_image_path": output_image_path}
    except Exception as e:
        logger.error(f"An error occurred: {str(e)}")
        return JSONResponse(content={"error": str(e)}, status_code=500)
