"""
Real-time transcriber for audio from live recording
Uses faster-whisper for efficient inference
Handles incomplete WebM chunks from getDisplayMedia
"""

import subprocess
import tempfile
import os
from typing import Optional, List, Dict
import io
import wave
from faster_whisper import WhisperModel

try:
    import av  # PyAV for Opus decoding
    HAS_PYAV = True
except ImportError:
    HAS_PYAV = False
    print("⚠️ PyAV not installed, WebM decoding may fail")


class RealtimeTranscriber:
    """Transcribe audio in real-time using Whisper"""
    
    def __init__(self, model_size: str = "base"):
        """
        Initialize transcriber
        
        Args:
            model_size: Whisper model size (tiny, base, small, medium, large)
        """
        self.model_size = model_size
        self._model: Optional[WhisperModel] = None
        
    @property
    def model(self) -> WhisperModel:
        """Lazy load Whisper model"""
        if self._model is None:
            print(f"🔄 Loading Whisper model '{self.model_size}' for real-time transcription...")
            self._model = WhisperModel(self.model_size, device="cpu", compute_type="int8")
            print(f"✅ Whisper model ready for real-time transcription")
        return self._model
    
    def convert_webm_to_wav(self, webm_path: str, tolerant: bool = False) -> str:
        """
        Convert WebM to WAV using FFmpeg
        
        Args:
            webm_path: Path to WebM file
            tolerant: If True, use error-tolerant FFmpeg settings for chunked WebM
            
        Returns:
            Path to WAV file
        """
        wav_path = webm_path.replace('.webm', '.wav')
        
        # Для chunked WebM используем более tolerant настройки
        if tolerant:
            cmd = [
                'ffmpeg',
                '-loglevel', 'warning',
                '-err_detect', 'ignore_err',  # Игнорируем ошибки контейнера
                '-fflags', '+genpts+igndts',  # Генерируем PTS, игнорируем DTS
                '-i', webm_path,
                '-ar', '16000',
                '-ac', '1',
                '-acodec', 'pcm_s16le',
                '-y',
                wav_path
            ]
        else:
            cmd = [
                'ffmpeg',
                '-loglevel', 'error',
                '-i', webm_path,
                '-ar', '16000',
                '-ac', '1',
                '-acodec', 'pcm_s16le',
                '-y',
                wav_path
            ]
        
        try:
            result = subprocess.run(cmd, check=True, capture_output=True, text=True)
            
            # Проверяем что файл создан и не пустой
            if not os.path.exists(wav_path) or os.path.getsize(wav_path) < 1000:
                raise Exception(f"WAV file too small or missing: {wav_path}")
            
            print(f"🔄 Converted {os.path.basename(webm_path)} -> {os.path.basename(wav_path)} ({os.path.getsize(wav_path)} bytes, tolerant={tolerant})")
            return wav_path
            
        except subprocess.CalledProcessError as e:
            print(f"❌ FFmpeg conversion failed (tolerant={tolerant}): {e}")
            if e.stderr:
                print(f"   stderr: {e.stderr}")
            print(f"   WebM file size: {os.path.getsize(webm_path)} bytes")
            raise Exception(f"Failed to convert WebM to WAV: {str(e)}")
    
    def transcribe_webm(self, webm_path: str, language: str = "id") -> str:
        """
        Transcribe WebM audio file
        
        Args:
            webm_path: Path to WebM file
            language: Language code (default: "id" for Bahasa Indonesia)
            
        Returns:
            Transcribed text
        """
        wav_path = None
        
        try:
            # Convert to WAV
            wav_path = self.convert_webm_to_wav(webm_path)
            
            # Transcribe with Whisper
            print(f"🎤 Transcribing {wav_path} (language: {language})...")
            
            segments, info = self.model.transcribe(
                wav_path,
                language=language,  # "id" для индонезийского
                vad_filter=True,
                beam_size=5
            )
            
            # Collect text
            transcript_lines = []
            for segment in segments:
                text = segment.text.strip()
                if text:
                    transcript_lines.append(text)
            
            transcript = " ".join(transcript_lines)
            
            print(f"✅ Transcribed: {len(transcript)} chars")
            
            return transcript
            
        except Exception as e:
            print(f"❌ Transcription error: {e}")
            return ""
            
        finally:
            # Cleanup
            if wav_path and os.path.exists(wav_path):
                try:
                    os.remove(wav_path)
                except:
                    pass
    
    def decode_webm_chunks_pyav(self, webm_data: bytes) -> bytes:
        """
        Decode WebM chunks using PyAV (handles incomplete WebM files)
        
        Args:
            webm_data: Raw WebM bytes (incomplete/chunked from getDisplayMedia)
            
        Returns:
            PCM audio bytes (16-bit mono, 16kHz)
        """
        if not HAS_PYAV:
            raise Exception("PyAV not installed")
        
        print(f"🔧 Decoding WebM with PyAV ({len(webm_data)} bytes)...")
        
        try:
            # Create BytesIO from the WebM data
            webm_buffer = io.BytesIO(webm_data)
            print(f"   📦 Created BytesIO buffer")
            
            # Open with PyAV - more tolerant to incomplete WebM
            print(f"   🔓 Opening with av.open(format='webm')...")
            container = av.open(webm_buffer, format='webm')
            print(f"   ✅ Container opened")
            
            # Extract audio stream
            audio_stream = None
            for stream in container.streams:
                print(f"   📹 Found stream: type={stream.type}, codec={getattr(stream, 'codec_name', 'unknown')}")
                if stream.type == 'audio':
                    audio_stream = stream
                    break
            
            if not audio_stream:
                raise Exception("No audio stream found in WebM")
            
            print(f"📻 Audio: {audio_stream.codec_name}, {audio_stream.sample_rate}Hz, {audio_stream.channels}ch")
            
            # Decode to PCM
            pcm_data = io.BytesIO()
            resampler = av.AudioResampler(format='s16', layout='mono', rate=16000)
            print(f"   🔄 Resampler created: s16, mono, 16kHz")
            
            frame_count = 0
            for frame in container.decode(audio_stream):
                frame_count += 1
                frame.pts = None
                resampled = resampler.resample(frame)
                
                if resampled:
                    pcm_bytes = resampled.to_ndarray().tobytes()
                    pcm_data.write(pcm_bytes)
                    if frame_count <= 3:
                        print(f"   🎵 Frame {frame_count}: {len(pcm_bytes)} bytes decoded")
            
            result = pcm_data.getvalue()
            print(f"✅ Decoded {frame_count} frames: {len(result)} bytes (16kHz mono)")
            
            return result
            
        except Exception as e:
            print(f"❌ PyAV decode error: {e}")
            import traceback
            traceback.print_exc()
            raise

    def transcribe_buffer(self, buffer_data: bytes, language: str = "id") -> List[Dict]:
        """
        Transcribe audio buffer directly
        
        Args:
            buffer_data: Raw audio bytes (WebM, WAV, or raw PCM Int16)
            language: Language code (default: "id" for Bahasa Indonesia)
            
        Returns:
            A list of segment dictionaries with start, end, and text
        """
        temp_wav_path = None
        
        try:
            print(f"📁 Processing buffer: {len(buffer_data)} bytes")
            print(f"   First 4 bytes: {buffer_data[:4].hex() if len(buffer_data) >= 4 else 'N/A'}")
            
            # Проверяем формат
            if buffer_data[:4] == b'RIFF':
                print("🎵 Detected WAV format (RIFF header)")
                temp_wav_path = tempfile.mktemp(suffix='.wav')
                with open(temp_wav_path, 'wb') as f:
                    f.write(buffer_data)
                    
            elif buffer_data[:4] == b'\x1aE\xdf\xa3':  # EBML WebM header
                print("🎵 Detected WebM format (EBML header)")
                # Попробуем WebM обработку
                temp_webm = tempfile.mktemp(suffix='.webm')
                temp_wav_path = tempfile.mktemp(suffix='.wav')
                
                with open(temp_webm, 'wb') as f:
                    f.write(buffer_data)
                
                try:
                    wav_path = self.convert_webm_to_wav(temp_webm, tolerant=True)
                    temp_wav_path = wav_path
                except Exception as e:
                    print(f"   ⚠️ WebM conversion failed: {e}")
                    raise
                finally:
                    try:
                        os.remove(temp_webm)
                    except:
                        pass
                        
            else:
                # Предполагаем RAW PCM Int16
                print("🎧 Detected RAW PCM data (Int16 16kHz mono)")
                print(f"   First byte value: {buffer_data[0]} (typical PCM: < 50)")
                
                temp_wav_path = tempfile.mktemp(suffix='.wav')
                
                # Конвертируем Int16 PCM → WAV
                with wave.open(temp_wav_path, 'wb') as wav_file:
                    wav_file.setnchannels(1)  # Mono
                    wav_file.setsampwidth(2)  # 16-bit (Int16)
                    wav_file.setframerate(16000)  # 16kHz
                    wav_file.writeframes(buffer_data)
                
                print(f"💾 Created WAV from PCM: {os.path.getsize(temp_wav_path)} bytes")
            
            # Check WAV size
            if not os.path.exists(temp_wav_path):
                raise Exception(f"WAV not created")
            
            wav_size = os.path.getsize(temp_wav_path)
            print(f"📊 WAV file size: {wav_size} bytes")
            
            if wav_size < 4000:
                print(f"⚠️ WAV too small ({wav_size} bytes), skipping")
                return ""
            
            # Transcribe
            print(f"🎤 Transcribing {wav_size} bytes (language: {language})...")
            
            segments, info = self.model.transcribe(
                temp_wav_path,
                language=language,
                vad_filter=True,
                beam_size=5
            )
            
            result_segments = []
            for segment in segments:
                result_segments.append({
                    "start": segment.start,
                    "end": segment.end,
                    "text": segment.text.strip()
                })
            
            print(f"✅ Transcribed: {len(result_segments)} segments")
            
            return result_segments
            
        except Exception as e:
            print(f"❌ Transcription error: {e}")
            import traceback
            traceback.print_exc()
            return ""
            
        finally:
            if temp_wav_path and os.path.exists(temp_wav_path):
                try:
                    os.remove(temp_wav_path)
                except:
                    pass


# Global instance
_transcriber: Optional[RealtimeTranscriber] = None


def get_transcriber() -> RealtimeTranscriber:
    """Get or create global transcriber instance"""
    global _transcriber
    if _transcriber is None:
        _transcriber = RealtimeTranscriber(model_size="base")
    return _transcriber


def transcribe_audio_buffer(buffer_data: bytes, language: str = "id") -> List[Dict]:
    """
    Convenience function to transcribe audio buffer
    
    Args:
        buffer_data: Raw audio bytes
        language: Language code (default: "id" for Bahasa Indonesia)
        
    Returns:
        A list of segment dictionaries with start, end, and text
    """
    transcriber = get_transcriber()
    return transcriber.transcribe_buffer(buffer_data, language=language)

