from fastapi import FastAPI, File, UploadFile
from fastapi.responses import StreamingResponse
import io
from PIL import Image
import cv2
import tempfile
import torch
import numpy as np
import pathlib
import sys
import uvicorn

if sys.platform.startswith('win'):
    pathlib.PosixPath = pathlib.WindowsPath

model = torch.hub.load("ultralytics/yolov5", "custom", path="weights/best.pt")
device = torch.device('cpu')
model.to(device)
app = FastAPI()


@app.post("/process/")
async def process_file(file: UploadFile = File(...)):
    filename = file.filename
    content_type = file.content_type

    # Читаем содержимое файла в память
    data = await file.read()

    # Обработка изображения
    if "image" in content_type:
        pil_img = Image.open(io.BytesIO(data))
        img = np.array(pil_img)
        results = model(img)
        image = Image.fromarray(*results.render())
        # Сохраняем обработанное изображение в байты
        buf = io.BytesIO()
        image.save(buf, format='PNG')
        buf.seek(0)
        return StreamingResponse(buf, media_type="image/png",
                                 headers={"Content-Disposition": f"attachment; filename=processed_{filename}"})

    # Обработка видео
    elif "video" in content_type:
        # Временный файл для сохранения видео
        with tempfile.NamedTemporaryFile(delete=False, suffix=".mp4") as temp_input:
            temp_input.write(data)
            temp_input_path = temp_input.name


        cap = cv2.VideoCapture(temp_input_path)
        fourcc = cv2.VideoWriter_fourcc(*'mp4v')
        out_path = temp_input_path.replace('.mp4', '_processed.mp4')
        out = cv2.VideoWriter(out_path, fourcc, cap.get(cv2.CAP_PROP_FPS),
                              (int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)), int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))))

        while True:
            ret, frame = cap.read()

            if ret == False:
                break

            results = model(frame)

            out.write(*results.render())

        cap.release()
        out.release()

        def iterfile():
            with open(out_path, mode="rb") as file_like:
                yield from file_like

        return StreamingResponse(iterfile(), media_type="video/mp4",
                                 headers={"Content-Disposition": f"attachment; filename=processed_{filename}"})

if __name__ == "__main__":
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)