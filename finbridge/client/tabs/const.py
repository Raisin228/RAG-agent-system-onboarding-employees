"""Константы для фронтовых страниц. Атрошенко Б. С."""

from config import settings

base_url = settings.API_URL.split("/chat/")[0]
LIST_URL = f"{base_url}/admin/documents"
UPLOAD_URL = f"{base_url}/admin/documents/upload"
DELETE_URL = f"{base_url}/admin/documents/delete"
REINDEX_URL = f"{base_url}/admin/documents/reindex"
SESSION_URL = f"{base_url}/chat/chat/sessions"

TABLE_HEADERS = ["", "Файл", "Размер", "Чанков", "Проиндексирован", "Обновлён"]
TABLE_DTYPES = ["bool", "str", "str", "number", "str", "str"]
