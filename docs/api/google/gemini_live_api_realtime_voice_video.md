---
Source: https://ai.google.dev/gemini-api/docs/live
Title: Get started with Live API
---

# Get started with Live API

Note: Introducing a new version of the Gemini 2.5 Flash Live model, with improved function calling and conversational accuracy
The Live API enables low-latency, real-time voice and video interactions with Gemini. It processes continuous streams of audio, video, or text to deliver immediate, human-like spoken responses, creating a natural conversational experience for your users.

Live API Overview

Live API offers a comprehensive set of features such as Voice Activity Detection, tool use and function calling, session management (for managing long running conversations) and ephemeral tokens (for secure client-sided authentication).

This page gets you up and running with examples and basic code samples.

Try the Live API in Google AI Studiomic

Example applications
Check out the following example applications that illustrate how to use Live API for end-to-end use cases:

Live audio starter app on AI Studio, using JavaScript libraries to connect to Live API and stream bidirectional audio through your microphone and speakers.
Live API Python cookbook using Pyaudio that connects to Live API.
Partner integrations
If you prefer a simpler development process, you can use Daily, LiveKit or Voximplant. These are third-party partner platforms that have already integrated the Gemini Live API over the WebRTC protocol to streamline the development of real-time audio and video applications.

Before you begin building
There are two important decisions to make before you begin building with the Live API: choosing a model and choosing an implementation approach.

Choose an audio generation architecture
If you're building an audio-based use case, your choice of model determines the audio generation architecture used to create the audio response:

Native audio: This option provides the most natural and realistic-sounding speech and better multilingual performance. It also enables advanced features like affective (emotion-aware) dialogue, proactive audio (where the model can decide to ignore or respond to certain inputs), and "thinking". Native audio is supported by the following native audio models:
NEW: gemini-2.5-flash-native-audio-preview-09-2025
gemini-2.5-flash-preview-native-audio-dialog
gemini-2.5-flash-exp-native-audio-thinking-dialog
Half-cascade audio: This option uses a cascaded model architecture (native audio input and text-to-speech output). It offers better performance and reliability in production environments, especially with tool use. Half-cascaded audio is supported by the following models:
gemini-live-2.5-flash-preview
gemini-2.0-flash-live-001
Choose an implementation approach
When integrating with Live API, you'll need to choose one of the following implementation approaches:

Server-to-server: Your backend connects to the Live API using WebSockets. Typically, your client sends stream data (audio, video, text) to your server, which then forwards it to the Live API.
Client-to-server: Your frontend code connects directly to the Live API using WebSockets to stream data, bypassing your backend.
Note: Client-to-server generally offers better performance for streaming audio and video, since it bypasses the need to send the stream to your backend first. It's also easier to set up since you don't need to implement a proxy that sends data from your client to your server and then your server to the API. However, for production environments, in order to mitigate security risks, we recommend using ephemeral tokens instead of standard API keys.
Get started
This example reads a WAV file, sends it in the correct format, and saves the received data as WAV file.

You can send audio by converting it to 16-bit PCM, 16kHz, mono format, and you can receive audio by setting AUDIO as response modality. The output uses a sample rate of 24kHz.

Python
JavaScript

# Test file: https://storage.googleapis.com/generativeai-downloads/data/16000.wav
# Install helpers for converting files: pip install librosa soundfile
import asyncio
import io
from pathlib import Path
import wave
from google import genai
from google.genai import types
import soundfile as sf
import librosa

client = genai.Client()

# New native audio model:
model = "gemini-2.5-flash-native-audio-preview-09-2025"

config = {
  "response_modalities": ["AUDIO"],
  "system_instruction": "You are a helpful assistant and answer in a friendly tone.",
}

async def main():
    async with client.aio.live.connect(model=model, config=config) as session:

        buffer = io.BytesIO()
        y, sr = librosa.load("sample.wav", sr=16000)
        sf.write(buffer, y, sr, format='RAW', subtype='PCM_16')
        buffer.seek(0)
        audio_bytes = buffer.read()

        # If already in correct format, you can use this:
        # audio_bytes = Path("sample.pcm").read_bytes()

        await session.send_realtime_input(
            audio=types.Blob(data=audio_bytes, mime_type="audio/pcm;rate=16000")
        )

        wf = wave.open("audio.wav", "wb")
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(24000)  # Output is 24kHz

        async for response in session.receive():
            if response.data is not None:
                wf.writeframes(response.data)

            # Un-comment this code to print audio data info
            # if response.server_content.model_turn is not None:
            #      print(response.server_content.model_turn.parts[0].inline_data.mime_type)

        wf.close()

if __name__ == "__main__":
    asyncio.run(main())
What's next
Read the full Live API Capabilities guide for key capabilities and configurations; including Voice Activity Detection and native audio features.
Read the Tool use guide to learn how to integrate Live API with tools and function calling.
Read the Session management guide for managing long running conversations.
Read the Ephemeral tokens guide for secure authentication in client-to-server applications.
For more information about the underlying WebSockets API, see the WebSockets API reference.