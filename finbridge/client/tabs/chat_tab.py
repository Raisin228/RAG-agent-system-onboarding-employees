"""Вкладка «Чат» — диалог с RAG-агентом. Атрошенко Б. С."""

import gradio as gr
import httpx

from client.tabs.const import SESSION_URL
from config import settings
from service.api.chat.dependensies import SESSION_HEADER


class ChatTab:
    """Логика чата."""

    @classmethod
    def build_chat_tab(cls) -> None:
        """Построить содержимое вкладки «Чат» внутри активного gr.Tab-контекста."""

        gr.Markdown("Задайте вопрос по базе знаний компании.")

        session_state = gr.State("")
        chatbot = gr.Chatbot(label="Диалог", height=600)

        with gr.Row():
            msg_input = gr.Textbox(
                placeholder="Введите вопрос...",
                show_label=False,
                scale=9,
                submit_btn=True,
            )
            clear_btn = gr.Button("Очистить", scale=1, variant="secondary")

        msg_input.submit(
            fn=cls._send_message,
            inputs=[msg_input, chatbot, session_state],
            outputs=[msg_input, chatbot, session_state],
        )

        clear_btn.click(lambda: ("", [], ""), outputs=[msg_input, chatbot, session_state])

    @classmethod
    def _ensure_session(cls, session_id: str) -> str:
        """
        Возвращаем текущую сессию | генерируем новую

        :param session_id: ID сессии.
        :return: новая сессия.
        """

        if session_id:
            return session_id
        response = httpx.post(SESSION_URL, timeout=10)
        response.raise_for_status()
        return response.json()["user_identity"]

    @classmethod
    def _send_message(cls, message: str, history: list[dict], session_id: str) -> tuple[str, list[dict], str]:
        """
        Отправить сообщение в /chat/create_insight и вернуть обновлённую историю.

        :param message: текст вопроса от пользователя.
        :param history: текущая история диалога.
        :param session_id: id текущей сессии.
        :return: пустая строка (очищает поле ввода) и обновлённая история.
        """

        try:
            session_id = cls._ensure_session(session_id)
            response = httpx.post(
                settings.API_URL, headers={SESSION_HEADER: session_id}, json={"query": message}, timeout=10000.0
            )
            response.raise_for_status()
            data = response.json()

            answer = data["answer"]
            sources = data.get("sources", [])

            if sources:
                sources_text = "\n\n---\n**Источники:**\n"
                for i, src in enumerate(sources, 1):
                    metadata = src.get("metadata", {})
                    source_name = metadata.get("source", metadata.get("title", f"Документ {i}"))
                    sources_text += f"- {source_name}\n"
                answer += sources_text

        except httpx.HTTPStatusError as e:
            answer = f"Ошибка API ({e.response.status_code}): {e.response.text}"
        except httpx.ConnectError:
            answer = "Не удалось подключиться к серверу. Убедитесь, что FastAPI запущен."
        except Exception as e:
            answer = f"Непредвиденная ошибка: {e}"

        history.append({"role": "user", "content": message})
        history.append({"role": "assistant", "content": answer})
        return "", history, session_id
