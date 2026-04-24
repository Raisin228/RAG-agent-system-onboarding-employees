"""Константы для фронтовых страниц. Атрошенко Б. С."""

from config import settings

CHAT_INSIGHT_STREAM = f"{settings.API_URL}/chat/create_insight_stream"
VOICE_INSIGHT_STREAM = f"{settings.API_URL}/chat/voice_insight_stream"
SESSION_URL = f"{settings.API_URL}/chat/sessions"
LIST_URL = f"{settings.API_URL}/admin/documents"
REINDEX_URL = f"{settings.API_URL}/admin/documents/reindex"
UPLOAD_URL = f"{settings.API_URL}/admin/documents/upload"
DELETE_URL = f"{settings.API_URL}/admin/documents/delete"

TABLE_HEADERS = ["", "Файл", "Размер", "Чанков", "Проиндексирован", "Обновлён"]
TABLE_DTYPES = ["bool", "str", "str", "number", "str", "str"]
