"""
YouTube Video Streamer
Simulates real-time audio streaming from YouTube videos for testing
"""

import os
import tempfile
import time
import asyncio
from typing import AsyncGenerator, Optional
import yt_dlp
import wave
import struct


class YouTubeStreamer:
    """Stream YouTube video audio in real-time chunks (simulates live call)"""
    
    def __init__(self, chunk_duration_seconds: float = 1.0):
        """
        Initialize streamer
        
        Args:
            chunk_duration_seconds: Duration of each audio chunk (default: 1 second)
        """
        self.chunk_duration = chunk_duration_seconds
        
    def download_audio_as_wav(self, youtube_url: str) -> str:
        """
        Download audio from YouTube and convert to WAV PCM 16kHz mono
        
        Args:
            youtube_url: YouTube video URL
            
        Returns:
            Path to downloaded WAV file
        """
        temp_dir = tempfile.mkdtemp()
        output_template = os.path.join(temp_dir, "audio")
        
        ydl_opts = {
            'format': 'bestaudio/best',
            'outtmpl': output_template,
            'quiet': True,
            'no_warnings': True,
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'wav',
            }],
            # Force specific audio format
            'postprocessor_args': [
                '-ar', '16000',  # 16kHz sample rate
                '-ac', '1',       # Mono
            ],
        }
        
        # Add cookies from environment variable if available
        # This is the new, secure way to handle authentication
        cookies_content = os.getenv("YOUTUBE_COOKIES")
        temp_cookie_file = None
        if cookies_content:
            try:
                # yt-dlp needs a file path, so we create a temporary file
                fd, temp_cookie_path = tempfile.mkstemp(text=True)
                with os.fdopen(fd, 'w') as f:
                    f.write(cookies_content)

                ydl_opts['cookies'] = temp_cookie_path
                temp_cookie_file = temp_cookie_path # Keep track to delete later
                print("🍪 Using YouTube cookies from YOUTUBE_COOKIES env var.")
            except Exception as e:
                print(f"⚠️ Failed to create temporary cookie file: {e}")
        else:
            print("🚫 No YOUTUBE_COOKIES found. Proceeding without authentication.")

        ydl_opts['user_agent'] = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.36'

        print(f"📥 Downloading YouTube video: {youtube_url}")
        
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(youtube_url, download=True)
                title = info.get('title', 'Unknown')
                duration = info.get('duration', 0)
                
                print(f"✅ Downloaded: {title} ({duration}s)")
                
                # Find downloaded WAV file
                import glob
                wav_files = glob.glob(os.path.join(temp_dir, "audio.wav"))
                
                if not wav_files:
                    raise Exception(f"No WAV file found in {temp_dir}")
                
                wav_path = wav_files[0]
                print(f"📁 WAV file: {wav_path}")
                
                return wav_path
                
        except Exception as e:
            raise Exception(f"Failed to download YouTube video: {str(e)}")
        finally:
            # Cleanup temporary cookie file
            if temp_cookie_file and os.path.exists(temp_cookie_file):
                try:
                    os.remove(temp_cookie_file)
                    print(f"🗑️ Cleaned up temporary cookie file.")
                except Exception as e:
                    print(f"⚠️ Failed to remove temp cookie file: {e}")
    
    async def stream_audio_chunks(
        self, 
        wav_path: str, 
        real_time: bool = True
    ) -> AsyncGenerator[bytes, None]:
        """
        Stream audio file as PCM chunks, simulating real-time playback
        
        Args:
            wav_path: Path to WAV file (16kHz mono)
            real_time: If True, sleep between chunks to simulate real-time playback
            
        Yields:
            PCM audio chunks (bytes)
        """
        print(f"🎬 Starting audio stream from: {wav_path}")
        print(f"   Real-time mode: {real_time}")
        print(f"   Chunk duration: {self.chunk_duration}s")
        
        try:
            with wave.open(wav_path, 'rb') as wav_file:
                # Validate format
                channels = wav_file.getnchannels()
                sample_width = wav_file.getsampwidth()
                framerate = wav_file.getframerate()
                
                print(f"📊 Audio format: {channels} ch, {sample_width} bytes/sample, {framerate} Hz")
                
                if channels != 1:
                    raise ValueError(f"Expected mono audio, got {channels} channels")
                if sample_width != 2:
                    raise ValueError(f"Expected 16-bit audio, got {sample_width * 8}-bit")
                if framerate != 16000:
                    raise ValueError(f"Expected 16kHz audio, got {framerate} Hz")
                
                # Calculate frames per chunk
                frames_per_chunk = int(framerate * self.chunk_duration)
                bytes_per_chunk = frames_per_chunk * sample_width * channels
                
                print(f"   Frames per chunk: {frames_per_chunk}")
                print(f"   Bytes per chunk: {bytes_per_chunk}")
                
                chunk_count = 0
                start_time = time.time()
                
                while True:
                    # Read chunk
                    frames = wav_file.readframes(frames_per_chunk)
                    
                    if not frames:
                        print(f"✅ Stream complete: {chunk_count} chunks sent")
                        break
                    
                    chunk_count += 1
                    
                    # Yield chunk
                    yield frames
                    
                    if chunk_count % 10 == 0:
                        elapsed = time.time() - start_time
                        print(f"   Streamed: {chunk_count} chunks ({elapsed:.1f}s)")
                    
                    # Sleep to simulate real-time (if enabled)
                    if real_time:
                        await asyncio.sleep(self.chunk_duration)
                        
        except Exception as e:
            print(f"❌ Stream error: {e}")
            raise
    
    async def stream_youtube_url(
        self, 
        youtube_url: str, 
        real_time: bool = True
    ) -> AsyncGenerator[bytes, None]:
        """
        Complete pipeline: download + stream
        
        Args:
            youtube_url: YouTube video URL
            real_time: If True, simulate real-time playback
            
        Yields:
            PCM audio chunks (bytes)
        """
        wav_path = None
        
        try:
            # Download and convert to WAV
            wav_path = self.download_audio_as_wav(youtube_url)
            
            # Stream chunks
            async for chunk in self.stream_audio_chunks(wav_path, real_time):
                yield chunk
                
        finally:
            # Cleanup
            if wav_path and os.path.exists(wav_path):
                try:
                    os.remove(wav_path)
                    print(f"🗑️ Cleaned up: {wav_path}")
                except Exception as e:
                    print(f"⚠️ Cleanup error: {e}")


# Global instance
_streamer: Optional[YouTubeStreamer] = None


def get_streamer(chunk_duration: float = 1.0) -> YouTubeStreamer:
    """Get or create global streamer instance"""
    global _streamer
    if _streamer is None:
        _streamer = YouTubeStreamer(chunk_duration_seconds=chunk_duration)
    return _streamer

