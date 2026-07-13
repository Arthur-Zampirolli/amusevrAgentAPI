from pathlib import Path

import fastapi
from fastapi import FastAPI, Form
import uvicorn

from controller.CommandController import CommandController
from controller.XMLController import XMLController
from fastapi import FastAPI, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from faster_whisper import WhisperModel
import torch
import shutil
import os
from dotenv import load_dotenv

dotenv_path = Path('config/.env')
load_dotenv(dotenv_path=dotenv_path)
app = FastAPI()

#rotear a chamada de envio do xml
@app.post("/send-xml")
async def send_xml(data: dict):
    print(f"Received XML: {data['xml_data']}")
    print(f"Voice: {data['voice']}")
    return {"message": "XML sent successfully"}
@app.post("/update-xml")
async def update_xml(data: dict):
    print(f"Received XML: {data['xml_data']}")
    print(f"Properties: {data['new_data']}")

    controller = XMLController(data['xml_data'])
    controller.add_property(data['new_data'], data['scene_id'])
    data = {
        "xml_data": controller.get_xml_data(),
        "json": controller.get_xml_dict()
    }
    return {
        "message": "XML updated successfully",
        "json": data
    }
#receber comando de voz e realizar a conversão para texto, chamar o agente e atualizar o xml
@app.post("/transcribe")
async def transcribe_audio(file: UploadFile = File(...)):
    controller = CommandController()
    return await controller.transcribe_audio(file)

@app.post("/process-command")
async def process_command(scene_id: str = Form(...),xml_data: str = Form(...), file: UploadFile = File(...)):
    try:
        print(f"Received XML: {xml_data}")
        #scene_id = data["scene_id"]
        controller = CommandController()
        xml_controller = XMLController(xml_data)
        command = await controller.transcribe_audio(file)
        return await controller.process_command(command['text'], xml_controller,scene_id)
    except Exception as e:
        return {"error": str(e)}
async def update_json(data: dict):
    pass
if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)