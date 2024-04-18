import os
import json
from http.client import HTTPException
from io import BytesIO
from urllib import request

import cv2
import numpy as np
from PIL import Image, ImageDraw
from fastapi import FastAPI, UploadFile, File, HTMLResponse, Request
from fastapi.responses import JSONResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
import requests
from fastapi.templating import Jinja2Templates
import shutil
from counter import process_image


app = FastAPI()

templates = Jinja2Templates(directory="templates")

@app.get("/upload/", response_class=HTMLResponse)
async def upload_form(request: Request):
    return templates.TemplateResponse("upload_form.html", {"request": request})

@app.post("/upload/")
async def upload_file(file: UploadFile = File(...)):
    try:
        upload_folder = "uploaded_images"
        os.makedirs(upload_folder, exist_ok=True)
        file_path = os.path.join(upload_folder, file.filename)

        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        num_people, output_image_path = process_image(file_path)

        os.remove(file_path)

        return JSONResponse(content={"Number of detected people": num_people, "output_image_path": output_image_path})
    except Exception as e:
        return JSONResponse(content={"error": str(e)}, status_code=500)

@app.get("/url/", response_class=HTMLResponse)
async def url_form(request: Request):
    return templates.TemplateResponse("url_form.html", {"request": request})

@app.post("/url/")
async def detect_people_from_url(request: Request):
    try:
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

        return {"Number of detected people": num_people, "output_image_path": output_image_path}
    except Exception as e:
        return JSONResponse(content={"error": str(e)}, status_code=500)