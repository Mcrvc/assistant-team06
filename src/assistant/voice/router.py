from fastapi import APIRouter, Response, HTTPException
from pydantic import BaseModel
from . import tts

router = APIRouter(prefix="/api")

class TTSRequest(BaseModel):
    text: str
    lang: str = "en"

@router.post("/tts")
async def tts_endpoint(req: TTSRequest):
    try:
        audio, mime = tts.synthesize(req.text, lang=req.lang)
        return Response(audio, media_type=mime)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"TTS error: {e}")
