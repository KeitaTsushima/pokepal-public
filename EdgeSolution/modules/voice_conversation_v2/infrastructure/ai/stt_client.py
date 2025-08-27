"""
OpenAI Whisper API Client
Speech-to-text implementation using OpenAI Whisper API
"""
import os
import time
import logging
import tempfile
import wave
from typing import Optional, Dict, Any
import httpx
from openai import APIConnectionError, APITimeoutError

from .async_openai_shared import get_shared_openai


class STTClient:
    """Speech-to-text client using OpenAI Whisper API"""
    
    def __init__(self, config_loader):
        self.logger = logging.getLogger(__name__)
        self.config_loader = config_loader
        
        # Performance metrics (since container start)
        self.start_time = time.time()
        self.metrics = {
            'total_requests': 0,
            'total_processing_time': 0.0,
            'average_processing_time': 0.0,
            'success_count': 0,
            'error_count': 0,
            'warmup_completed': False,
            'first_call_time': None,
            'subsequent_avg_time': 0.0
        }
        
        # Store secret name for on-demand Key Vault access
        self.openai_secret_name = os.environ['OPENAI_SECRET_NAME']
        
        self.logger.info("STTClient initialized successfully")
    
    async def _lazy_warmup(self) -> None:
        """Lazy warm-up OpenAI Whisper API connection on first transcribe call"""
        if self.metrics['warmup_completed']:
            return
            
        try:
            # Create minimal audio file for warm-up (0.1 second silence)
            with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as tmp_file:
                # Write minimal WAV header + 0.1s silence (16kHz, 16-bit mono)
                with wave.open(tmp_file.name, 'wb') as wav:
                    wav.setnchannels(1)  # mono
                    wav.setsampwidth(2)  # 16-bit
                    wav.setframerate(16000)  # 16kHz
                    wav.writeframes(b'\x00' * 3200)  # 0.1s of silence
                
                # Get current configuration dynamically (consistent with transcribe)
                model = self.config_loader.get('stt.openai.model')
                language = self.config_loader.get('stt.language')
                
                # Use SharedAsyncOpenAI for warmup (consistent with transcribe)
                shared_openai = await get_shared_openai()
                client = await shared_openai.get_stt_client(self.openai_secret_name)
                
                with open(tmp_file.name, "rb") as audio:
                    await client.audio.transcriptions.create(
                        model=model,
                        file=audio,
                        language=language,
                        response_format="text"
                    )
                
                os.unlink(tmp_file.name)
                self.metrics['warmup_completed'] = True
                self.logger.info("STT lazy warm-up completed - OpenAI Whisper connection pre-established")
                
        except Exception as e:
            self.logger.debug(f"STT warm-up skipped ({e})")
    
    async def transcribe(self, audio_file: str) -> Optional[str]:
        # Perform lazy warmup on first call to reduce latency
        if not self.metrics['warmup_completed']:
            await self._lazy_warmup()
        
        if not os.path.exists(audio_file):
            self.logger.warning(f"Audio file not found: {audio_file}")
            self._update_metrics(success=False)
            return None
        
        try:
            self.logger.debug("Starting OpenAI Whisper API speech recognition")
            start_time = time.time()
            
            # Get current configuration dynamically
            model = self.config_loader.get('stt.openai.model')
            language = self.config_loader.get('stt.language')
            
            # Get shared OpenAI client with semaphore control (includes Key Vault access)
            kv_start = time.time()
            shared_openai = await get_shared_openai()
            client = await shared_openai.get_stt_client(self.openai_secret_name)
            kv_duration = time.time() - kv_start
            
            # Whisper API call with connection retry
            whisper_start = time.time()
            transcript = await self._transcribe_with_retry(client, audio_file, model, language)
            whisper_duration = time.time() - whisper_start
            
            processing_time = time.time() - start_time
            text = transcript.strip() if transcript else ""
            
            # Filter out common Whisper hallucinations
            hallucination_patterns = [
                "ご視聴ありがとうございました",
                "ご視聴ありがとうございます", 
                "はじめしゃちょー",
                "チャンネル登録",
                "高評価",
                "コメント",
                "Thank you for watching",
                "Please subscribe",
                "[Music]",
                "[音楽]",
                "(音楽)"
            ]
            
            if any(pattern in text for pattern in hallucination_patterns):
                self.logger.warning(f"Detected potential Whisper hallucination: {text}")
                text = ""
            
            # Performance metrics in expected format for monitoring
            self.logger.info(f"[perf] kv={kv_duration:.3f}s whisper={whisper_duration:.3f}s")
            
            # Track first call vs subsequent calls for warmup effectiveness measurement
            if self.metrics['first_call_time'] is None:
                self.metrics['first_call_time'] = processing_time
                self.logger.info(f"OpenAI Whisper API FIRST CALL completed ({processing_time:.2f}s): {text}")
            else:
                # Update subsequent call average (exclude first call)
                subsequent_count = self.metrics['success_count'] - 1  # Exclude first call
                if subsequent_count >= 0:
                    total_subsequent_time = self.metrics['subsequent_avg_time'] * subsequent_count
                    self.metrics['subsequent_avg_time'] = (total_subsequent_time + processing_time) / (subsequent_count + 1)
                self.logger.info(f"OpenAI Whisper API speech recognition completed ({processing_time:.2f}s): {text}")
            
            if text:
                self._update_metrics(success=True, processing_time=processing_time)
                return text
            else:
                self.logger.info("Speech recognition result is empty")
                self._update_metrics(success=True, processing_time=processing_time)
                return None
                
        except Exception as e:
            self.logger.error(f"OpenAI Whisper API speech recognition error: {e}")
            self._update_metrics(success=False)
            return None
    
    def get_performance_metrics(self) -> Dict[str, Any]:
        success_rate = 0.0
        if self.metrics['total_requests'] > 0:
            success_rate = self.metrics['success_count'] / self.metrics['total_requests'] * 100
        
        current_model = self.config_loader.get('stt.openai.model')
        current_language = self.config_loader.get('stt.language')
        
        uptime_seconds = time.time() - self.start_time
        uptime_hours = uptime_seconds / 3600
        requests_per_hour = self.metrics['total_requests'] / uptime_hours if uptime_hours > 0 else 0.0
        
        # Calculate warmup effectiveness
        warmup_improvement = None
        if self.metrics['first_call_time'] and self.metrics['subsequent_avg_time'] > 0:
            warmup_improvement = round(
                (self.metrics['first_call_time'] - self.metrics['subsequent_avg_time']) * 1000, 1
            )  # milliseconds saved
        
        metrics = {
            'client_type': 'openai_whisper_api',
            'model': current_model,
            'language': current_language,
            'metrics_period': 'since_container_start',
            'uptime_hours': round(uptime_hours, 2),
            'total_requests': self.metrics['total_requests'],
            'success_count': self.metrics['success_count'],
            'error_count': self.metrics['error_count'],
            'success_rate_percent': round(success_rate, 2),
            'requests_per_hour': round(requests_per_hour, 2),
            'average_processing_time_seconds': round(self.metrics['average_processing_time'], 3),
            'total_processing_time_seconds': round(self.metrics['total_processing_time'], 3),
            'warmup_completed': self.metrics['warmup_completed'],
            'first_call_time_seconds': round(self.metrics['first_call_time'], 3) if self.metrics['first_call_time'] else None,
            'subsequent_avg_time_seconds': round(self.metrics['subsequent_avg_time'], 3) if self.metrics['subsequent_avg_time'] > 0 else None,
            'warmup_improvement_ms': warmup_improvement
        }
        
        return metrics
    
    def cleanup(self) -> None:
        try:
            metrics = self.get_performance_metrics()
            self.logger.info(f"STTClient cleanup completed - Stats: {metrics}")
        except Exception as e:
            self.logger.error(f"STTClient cleanup error: {e}")
    
    async def _transcribe_with_retry(self, client, audio_file: str, model: str, language: str):
        """Transcribe with connection error retry (immediate retry once only)"""
        for attempt in range(2):  # Max 2 attempts (original + 1 retry)
            try:
                with open(audio_file, "rb") as audio:
                    return await client.audio.transcriptions.create(
                        model=model,
                        file=audio,
                        language=language,
                        response_format="text"
                    )
            except (APIConnectionError, APITimeoutError, httpx.ConnectError, httpx.RemoteProtocolError) as e:
                if attempt == 0:  # First attempt failed, retry once
                    self.logger.warning(f"Connection error on attempt {attempt + 1}, retrying: {e}")
                    continue
                else:  # Second attempt failed, give up
                    self.logger.error(f"Connection error on final attempt: {e}")
                    raise
            except Exception as e:
                # Non-connection errors (rate limit, auth, etc.) - no retry
                self.logger.error(f"Non-retryable error: {e}")
                raise

    def _update_metrics(self, success: bool, processing_time: float = 0.0) -> None:
        self.metrics['total_requests'] += 1
        
        if success:
            self.metrics['success_count'] += 1
            self.metrics['total_processing_time'] += processing_time
            
            if self.metrics['success_count'] > 0:
                self.metrics['average_processing_time'] = (
                    self.metrics['total_processing_time'] / self.metrics['success_count']
                )
        else:
            self.metrics['error_count'] += 1
