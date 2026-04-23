"""Сервис транскрибации аудио через faster-whisper. Атрошенко Б. С."""

import logging
import tempfile
from pathlib import Path

from faster_whisper import WhisperModel

from config import settings

logger = logging.getLogger(__name__)


class WhisperTranscriber:
    """Синглтон-обёртка над faster-whisper для транскрибации аудиофайлов."""

    _model: WhisperModel | None = None

    @classmethod
    def _get_model(cls) -> WhisperModel:
        if cls._model is None:
            logger.info(f"[Whisper] загружаем модель: {settings.WHISPER_MODEL}")
            cls._model = WhisperModel(settings.WHISPER_MODEL, device="cpu", compute_type="int8")
        return cls._model

    @classmethod
    def transcribe(cls, audio_bytes: bytes, filename: str = "audio") -> str:
        """
        Транскрибирует аудио в текст.

        :param audio_bytes: сырые байты аудиофайла.
        :param filename: имя файла (нужно для определения расширения).
        :return: полный транскрибированный текст.
        """

        suffix = Path(filename).suffix or ".wav"
        model = cls._get_model()

        with tempfile.NamedTemporaryFile(suffix=suffix, delete=True) as tmp:
            tmp.write(audio_bytes)
            tmp.flush()

            segments, info = model.transcribe(tmp.name, beam_size=5)
            logger.info(f"[Whisper] язык: {info.language} (уверенность {info.language_probability:.2f})")

            text = " ".join(segment.text.strip() for segment in segments)

        logger.info(f"[Whisper] транскрипция: {text!r}")
        return text.strip()
