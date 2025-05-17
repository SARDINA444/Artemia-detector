from fastapi import FastAPI, File, UploadFile
from fastapi.responses import StreamingResponse
import io
import pandas as pd
from PIL import Image
import cv2
import tempfile

app = FastAPI()


@app.post("/process/")
async def process_file(file: UploadFile = File(...)):
    filename = file.filename
    content_type = file.content_type

    # Читаем содержимое файла в память
    data = await file.read()

    # Обработка изображения
    if "image" in content_type:
        # Открываем изображение с помощью PIL
        image = Image.open(io.BytesIO(data))
        # Пример обработки: инверсия цветов
        inverted_image = Image.eval(image, lambda x: 255 - x)
        # Сохраняем обработанное изображение в байты
        buf = io.BytesIO()
        inverted_image.save(buf, format='PNG')
        buf.seek(0)
        return StreamingResponse(buf, media_type="image/png",
                                 headers={"Content-Disposition": f"attachment; filename=processed_{filename}"})

    # Обработка видео
    elif "video" in content_type:
        # Временный файл для сохранения видео
        with tempfile.NamedTemporaryFile(delete=False, suffix=".mp4") as temp_input:
            temp_input.write(data)
            temp_input_path = temp_input.name

        # Обработка видео с помощью OpenCV (пример: добавление текста)
        cap = cv2.VideoCapture(temp_input_path)
        fourcc = cv2.VideoWriter_fourcc(*'mp4v')
        out_path = temp_input_path.replace('.mp4', '_processed.mp4')
        out = cv2.VideoWriter(out_path, fourcc, cap.get(cv2.CAP_PROP_FPS),
                              (int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)), int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))))

        while True:
            ret, frame = cap.read()
            if not ret:
                break
            # Пример обработки: добавление текста на кадр
            cv2.putText(frame, 'Processed', (50, 50), cv2.FONT_HERSHEY_SIMPLEX,
                        1, (0, 255, 0), 2)
            out.write(frame)

        cap.release()
        out.release()

        def iterfile():
            with open(out_path, mode="rb") as file_like:
                yield from file_like

        return StreamingResponse(iterfile(), media_type="video/mp4",
                                 headers={"Content-Disposition": f"attachment; filename=processed_{filename}"})

    # Генерация отчета в XLSX
    else:
        # Создаем пример отчета с данными о файле
        df = pd.DataFrame({
            "Filename": [filename],
            "Content-Type": [content_type],
            "Size (bytes)": [len(data)]
        })

        buf = io.BytesIO()
        with pd.ExcelWriter(buf) as writer:
            df.to_excel(writer, index=False)
        buf.seek(0)

        return StreamingResponse(buf, media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                                 headers={"Content-Disposition": f"attachment; filename=report_{filename}.xlsx"})