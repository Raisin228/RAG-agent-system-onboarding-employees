"""Вкладка «Документы» — список файлов, загрузка и удаление. Атрошенко Б. С."""
from typing import Any

import gradio as gr
import httpx

from config import settings

_base_url = settings.API_URL.split("/chat/")[0]
_LIST_URL = f"{_base_url}/admin/documents"
_UPLOAD_URL = f"{_base_url}/admin/documents/upload"
_DELETE_URL = f"{_base_url}/admin/documents/delete"

_TABLE_HEADERS = ["", "Файл", "Размер", "Чанков", "Проиндексирован", "Обновлён"]
_TABLE_DTYPES = ["bool", "str", "str", "number", "str", "str"]


class DocTabUI:
    """Методы страницы базы документов."""

    @staticmethod
    def build_documents_tab(demo: gr.Blocks) -> None:
        """
        Построить содержимое вкладки «Документы» внутри активного gr.Tab-контекста.

        :param demo: корневой gr.Blocks — нужен для регистрации demo.load.
        """
        gr.Markdown("### База знаний: загруженные файлы")

        stats_md = gr.Markdown("")

        docs_table = gr.Dataframe(
            headers=_TABLE_HEADERS,
            datatype="str",
            interactive=True,
            wrap=True,
        )

        with gr.Row():
            refresh_btn = gr.Button("Обновить список", variant="secondary")
            delete_btn = gr.Button("Удалить выбранные", variant="stop")

        delete_status = gr.Markdown("")

        gr.Markdown("---\n### Загрузить новый документ (.md)")

        with gr.Row():
            file_input = gr.File(
                label="Выберите .md файл",
                file_types=[".md"],
                scale=4,
            )
            upload_btn = gr.Button("Загрузить", variant="primary", scale=1)

        upload_status = gr.Markdown("")

        demo.load(fn=DocTabUI._fetch_documents, outputs=[docs_table, stats_md])

        refresh_btn.click(fn=DocTabUI._fetch_documents, outputs=[docs_table, stats_md])

        delete_btn.click(
            fn=DocTabUI.delete_selected,
            inputs=[docs_table],
            outputs=[delete_status, docs_table, stats_md],
        )

        upload_btn.click(
            fn=DocTabUI.download_document,
            inputs=[file_input],
            outputs=[upload_status, docs_table, stats_md],
        )

    @staticmethod
    def delete_selected(table_data: Any) -> tuple[str, list[list], str]:
        """
        Удалить отмеченные документы через DELETE /admin/documents/delete.

        :param table_data: текущее содержимое таблицы (список строк).
        :return: сообщение о результате, обновлённая таблица, обновлённая статистика.
        """
        rows, stats = DocTabUI._fetch_documents()
        if table_data is None or table_data.empty:
            return "Нет данных для удаления.", rows, stats

        selected = table_data[table_data.iloc[:, 0] == True]
        if selected.empty:
            return "Ни один документ не выбран.", rows, stats

        filenames = selected.iloc[:, 1].tolist()
        payload = [{"required_file_name": fn} for fn in filenames]

        try:
            response = httpx.request("DELETE", _DELETE_URL, json=payload, timeout=30.0)
            response.raise_for_status()
            results = response.json()

            deleted = [r for r in results if r.get("deleted_FS")]
            failed = [r for r in results if not r.get("deleted_FS")]

            parts = []
            if deleted:
                names = ", ".join(f"**{r['filename']}**" for r in deleted)
                parts.append(f"Удалено: {names}")
            if failed:
                names = ", ".join(f"**{r['filename']}**" for r in failed)
                parts.append(f"Не удалось удалить: {names}")
            message = " | ".join(parts) if parts else "Готово."

        except httpx.HTTPStatusError as e:
            detail = e.response.json().get("detail", e.response.text)
            message = f"Ошибка удаления ({e.response.status_code}): {detail}"
        except httpx.ConnectError:
            message = "Не удалось подключиться к серверу."
        except Exception as e:
            message = f"Непредвиденная ошибка: {e}"

        rows, stats = DocTabUI._fetch_documents()
        return message, rows, stats

    @staticmethod
    def download_document(file_path: str | None) -> tuple[str, list[list], str]:
        """
        Загрузить выбранный .md файл на сервер через /admin/documents/upload.

        :param file_path: путь к временному файлу, созданному Gradio.
        :return: сообщение о результате, обновлённая таблица, обновлённая статистика.
        """
        if not file_path:
            rows, stats = DocTabUI._fetch_documents()
            return "Файл не выбран.", rows, stats

        filename = file_path.split("/")[-1]
        if not filename.endswith(".md"):
            rows, stats = DocTabUI._fetch_documents()
            return "Принимаются только файлы с расширением .md.", rows, stats

        try:
            with open(file_path, "rb") as f:
                response = httpx.post(
                    _UPLOAD_URL,
                    files={"file": (filename, f, "text/markdown")},
                    timeout=30.0,
                )
            response.raise_for_status()
            data = response.json()
            message = f"Файл **{data['filename']}** успешно загружен. {data['message']}"
        except httpx.HTTPStatusError as e:
            detail = e.response.json().get("detail", e.response.text)
            message = f"Ошибка загрузки ({e.response.status_code}): {detail}"
        except httpx.ConnectError:
            message = "Не удалось подключиться к серверу."
        except Exception as e:
            message = f"Непредвиденная ошибка: {e}"

        rows, stats = DocTabUI._fetch_documents()
        return message, rows, stats

    @staticmethod
    def _fetch_documents() -> tuple[list[list], str]:
        """
        Получить список документов из /admin/documents.

        :return: строки таблицы (с checkbox-колонкой) и строка со статистикой.
        """
        try:
            response = httpx.get(_LIST_URL, timeout=15.0)
            response.raise_for_status()
            data = response.json()
        except httpx.ConnectError:
            return [], "Не удалось подключиться к серверу."
        except httpx.HTTPStatusError as e:
            return [], f"Ошибка API ({e.response.status_code}): {e.response.text}"
        except Exception as e:
            return [], f"Непредвиденная ошибка: {e}"

        s = data.get("summary", {})
        stats = (
            f"Всего документов: **{s.get('total_docs', 0)}** | "
            f"Проиндексировано: **{s.get('indexed_count', 0)}** ({s.get('indexed_pct', 0)}%) | "
            f"Чанков в Qdrant: **{s.get('total_chunks', 0)}**"
        )

        rows = [
            [
                False,
                doc["filename"],
                f"{doc['size_kb']:.1f} KB",
                doc["chunks_count"],
                "Да" if doc["is_indexed"] else "Нет",
                doc["last_updated"],
            ]
            for doc in data.get("documents", [])
        ]
        return rows, stats
