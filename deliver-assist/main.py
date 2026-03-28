"""
DeliverAssist — Main server
FastAPI backend with WebSocket proxy to Gemini Live API.
Handles bidirectional audio streaming, camera frames, and tool calls.
"""

import asyncio
import base64
import json
import os
import traceback

from dotenv import load_dotenv
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from google import genai
from google.genai import types

from system_prompt import build_system_prompt
from tools import TOOL_DECLARATIONS, handle_tool_call
from data_loader import load_data_context

load_dotenv()

# ── Config ───────────────────────────────────────────────────────────────────

GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
if not GOOGLE_API_KEY:
    raise ValueError("GOOGLE_API_KEY not set. Copy .env.example to .env and add your key.")

HOST = os.getenv("HOST", "0.0.0.0")
PORT = int(os.getenv("PORT", "8080"))

# Gemini model — use native audio for real-time voice
# Confirmed working model names (pick one):
# - "gemini-2.5-flash-preview-native-audio-dialog"  ← stable, full function calling + vision
# - "gemini-3.1-flash-live-preview"                  ← newest, some API changes
# - "gemini-2.5-flash-native-audio-preview-12-2025"  ← older preview
MODEL = "gemini-2.5-flash-native-audio-latest"

# Audio format constants
INPUT_SAMPLE_RATE = 16000   # 16kHz input from browser mic
OUTPUT_SAMPLE_RATE = 24000  # 24kHz output from Gemini

# ── Initialize ───────────────────────────────────────────────────────────────

client = genai.Client(api_key=GOOGLE_API_KEY)

# Load DCWP data into system prompt context
survey_context, quarterly_context = load_data_context()
system_prompt_text = build_system_prompt(survey_context, quarterly_context)

app = FastAPI(title="DeliverAssist")


# ── Build session config ─────────────────────────────────────────────────────

def get_session_config() -> types.LiveConnectConfig:
    """Build the Gemini Live API session configuration."""
    return types.LiveConnectConfig(
        response_modalities=["AUDIO"],
        system_instruction=types.Content(
            parts=[types.Part(text=system_prompt_text)]
        ),
        speech_config=types.SpeechConfig(
            voice_config=types.VoiceConfig(
                prebuilt_voice_config=types.PrebuiltVoiceConfig(
                    voice_name="Kore"  # Clear, warm voice
                )
            )
        ),
        tools=[types.Tool(function_declarations=[
            types.FunctionDeclaration(**decl) for decl in TOOL_DECLARATIONS
        ])],
        input_audio_transcription=types.AudioTranscriptionConfig(),
        output_audio_transcription=types.AudioTranscriptionConfig(),
    )


# ── WebSocket endpoint ───────────────────────────────────────────────────────

@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    """
    WebSocket proxy between browser and Gemini Live API.
    Loops Gemini sessions so the browser connection stays alive across turns.
    """
    await ws.accept()
    print("[WS] Client connected")

    config = get_session_config()

    # Mutable reference so browser_to_gemini always uses the current session
    current_session = [None]
    browser_disconnected = asyncio.Event()

    async def browser_to_gemini():
        """Forward browser audio/images to Gemini. Runs for the lifetime of the WS."""
        try:
            while not browser_disconnected.is_set():
                raw = await ws.receive_text()
                sess = current_session[0]
                if sess is None:
                    continue  # drop during brief session transition
                try:
                    msg = json.loads(raw)
                    if msg["type"] == "audio":
                        audio_bytes = base64.b64decode(msg["data"])
                        await sess.send_realtime_input(
                            audio=types.Blob(
                                data=audio_bytes,
                                mime_type=f"audio/pcm;rate={INPUT_SAMPLE_RATE}"
                            )
                        )
                    elif msg["type"] == "image":
                        image_bytes = base64.b64decode(msg["data"])
                        await sess.send_realtime_input(
                            video=types.Blob(data=image_bytes, mime_type="image/jpeg")
                        )
                    elif msg["type"] == "text":
                        await sess.send_client_content(
                            turns=types.Content(
                                role="user",
                                parts=[types.Part(text=msg["data"])]
                            ),
                            turn_complete=True
                        )
                except Exception as e:
                    print(f"[browser_to_gemini] send error: {e}")
        except WebSocketDisconnect:
            print("[WS] Browser disconnected")
            browser_disconnected.set()
        except Exception as e:
            print(f"[browser_to_gemini] Error: {e}")
            browser_disconnected.set()

    # Start the browser listener once — it outlives individual Gemini sessions
    btg_task = asyncio.create_task(browser_to_gemini())

    try:
        while not browser_disconnected.is_set():
            try:
                async with client.aio.live.connect(model=MODEL, config=config) as session:
                    current_session[0] = session
                    print("[Gemini] Session opened")

                    try:
                        async for response in session.receive():
                            if browser_disconnected.is_set():
                                break

                            # Audio from Gemini
                            if response.data:
                                audio_b64 = base64.b64encode(response.data).decode("utf-8")
                                await ws.send_json({"type": "audio", "data": audio_b64})

                            if response.server_content:
                                sc = response.server_content

                                if hasattr(sc, 'input_transcription') and sc.input_transcription:
                                    text = getattr(sc.input_transcription, 'text', None)
                                    if text and text.strip():
                                        await ws.send_json({"type": "transcript_input", "text": text})

                                if hasattr(sc, 'output_transcription') and sc.output_transcription:
                                    text = getattr(sc.output_transcription, 'text', None)
                                    if text and text.strip():
                                        await ws.send_json({"type": "transcript_output", "text": text})

                                if hasattr(sc, 'model_turn') and sc.model_turn:
                                    for part in sc.model_turn.parts or []:
                                        if hasattr(part, 'text') and part.text:
                                            await ws.send_json({"type": "transcript_output", "text": part.text})

                                if hasattr(sc, 'turn_complete') and sc.turn_complete:
                                    await ws.send_json({"type": "turn_complete"})
                                    break  # exit receive loop → session context exits → new session starts

                            if response.tool_call:
                                for fc in response.tool_call.function_calls:
                                    print(f"[Tool] {fc.name}({fc.args})")
                                    result_str = handle_tool_call(fc.name, dict(fc.args))
                                    result_obj = json.loads(result_str)
                                    await ws.send_json({"type": "tool_call", "name": fc.name, "result": result_obj})
                                    fr_kwargs = {"name": fc.name, "response": result_obj}
                                    if hasattr(fc, 'id') and fc.id:
                                        fr_kwargs["id"] = fc.id
                                    await session.send_tool_response(
                                        function_responses=types.FunctionResponse(**fr_kwargs)
                                    )

                    except Exception as e:
                        if not browser_disconnected.is_set():
                            print(f"[gemini_to_browser] Error: {e}")
                            traceback.print_exc()

                    current_session[0] = None
                    print("[Gemini] Session ended, restarting...")

            except Exception as e:
                current_session[0] = None
                if browser_disconnected.is_set():
                    break
                print(f"[Session] Error: {e}")
                traceback.print_exc()
                try:
                    await ws.send_json({"type": "error", "message": str(e)})
                except Exception:
                    break
                await asyncio.sleep(0.5)
    finally:
        btg_task.cancel()
        try:
            await btg_task
        except asyncio.CancelledError:
            pass

    print("[WS] Session ended")


# ── Static files & health check ──────────────────────────────────────────────

app.mount("/static", StaticFiles(directory="static"), name="static")


@app.get("/")
async def index():
    return FileResponse("static/index.html")


@app.get("/health")
async def health():
    return {"status": "ok", "model": MODEL}


# ── Run ──────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn
    print(f"Starting DeliverAssist on {HOST}:{PORT}")
    print(f"Model: {MODEL}")
    print(f"System prompt: {len(system_prompt_text)} characters")
    uvicorn.run(app, host=HOST, port=PORT)
