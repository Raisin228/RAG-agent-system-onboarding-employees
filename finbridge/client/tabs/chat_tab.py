"""Вкладка «Чат» — диалог с RAG-агентом. Атрошенко Б. С."""

import json
from pathlib import Path
from typing import Generator

import gradio as gr
import httpx

from client.tabs.const import SESSION_URL, CHAT_INSIGHT_STREAM, VOICE_INSIGHT_STREAM
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

        audio_input = gr.Audio(
            sources=["microphone"],
            type="filepath",
            label="Голосовой ввод (остановите запись — отправится автоматически)",
        )

        msg_input.submit(
            fn=cls._send_message,
            inputs=[msg_input, chatbot, session_state],
            outputs=[msg_input, chatbot, session_state],
        )

        audio_input.stop_recording(
            fn=cls._send_voice,
            inputs=[audio_input, chatbot, session_state],
            outputs=[audio_input, chatbot, session_state],
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
    def _send_message(cls, message: str, history: list[dict], session_id: str):
        """
        Стримить ответ агента через SSE и постепенно отдавать токены в gr.Chatbot.

        :param message: текст вопроса от пользователя.
        :param history: текущая история диалога.
        :param session_id: id текущей сессии.
        """

        session_id, history = cls.__check_valid_session(history, session_id)
        if not session_id:
            return

        history = history + [
            {"role": "user", "content": message},
            {"role": "assistant", "content": ""},
        ]
        yield "", history, session_id

        try:
            # Потоковый запрос в API
            with httpx.stream(
                    "POST",
                    CHAT_INSIGHT_STREAM,
                    headers={SESSION_HEADER: session_id},
                    json={"query": message},
                    timeout=None,
            ) as response:
                response.raise_for_status()
                # Итерируемся по вновь пришедшим данным
                for line in response.iter_lines():
                    if not line.startswith("data: "):
                        continue
                    # У SSE срезаю `data: `
                    data = json.loads(line[6:])

                    # Вывод обычного ввода
                    if data["type"] == "token":  # вынести TOKEN
                        history[-1]["content"] += data["content"]
                        yield "", history, session_id
                    else:
                        temp = cls.__response_parser(data, history, session_id)
                        if temp:
                            _, hist, sid = temp
                            yield None, hist, sid

        except httpx.ConnectError:
            history[-1]["content"] = "Не удалось подключиться к серверу. Убедитесь, что FastAPI запущен."
            yield "", history, session_id
        except Exception as e:
            history[-1]["content"] = f"Непредвиденная ошибка: {e}"
            yield "", history, session_id

    @classmethod
    def _send_voice(cls, audio_path: str | None, history: list[dict], session_id: str) -> Generator:
        """
        Отправляет аудио на транскрибацию и стримит ответ агента.

        :param audio_path: путь к временному файлу Gradio.
        :param history: история диалога.
        :param session_id: id сессии.
        :return: кортеж из 3х компонентов [поле ввода | история | сессия].
        """

        if not audio_path:
            yield None, history, session_id
            return

        session_id, history = cls.__check_valid_session(history, session_id)
        if not session_id:
            return

        history = list(history) + [
            {"role": "user", "content": "🎤Ожидай, идёт транскрибация аудио..."},
            {"role": "assistant", "content": ""}
        ]
        yield None, history, session_id

        try:
            filename = Path(audio_path).name
            with open(audio_path, "rb") as file:
                audio_bytes = file.read()

            with httpx.stream(
                    "POST",
                    VOICE_INSIGHT_STREAM,
                    headers={SESSION_HEADER: session_id},
                    files={"file": (filename, audio_bytes, "audio/wav")},
                    timeout=None
            ) as response:
                response.raise_for_status()
                for line in response.iter_lines():
                    if not line.startswith("data: "):
                        continue

                    data = json.loads(line[6:])
                    if data["type"] == "transcript":
                        history[-2]["content"] = f"🎤 {data["content"]}"
                        yield None, history, session_id
                    elif data["type"] == "token":
                        history[-1]["content"] += data["content"]
                        yield None, history, session_id
                    else:
                        temp = cls.__response_parser(data, history, session_id)
                        if temp:
                            _, hist, sid = temp
                            yield None, hist, sid

        except httpx.ConnectError:
            history[-1]["content"] = "Не удалось подключиться к серверу. Убедитесь, что FastAPI запущен."
            yield None, history, session_id
        except Exception as ex:
            history[-1]["content"] = f"Непредвиденная ошибка: {ex}"
            yield None, history, session_id

    @classmethod
    def __check_valid_session(cls, history: list[dict], session: str) -> tuple[str, list]:
        """
        Проверка наличия и валидности сессии.

        :param history: история диалога.
        :param session: ид чат сессии.
        :return: сессия, либо None.
        """

        try:
            session_id = cls._ensure_session(session)
        except Exception as e:
            history = list(history) + [
                {"role": "user", "content": "Запрос пользователя"},
                {"role": "assistant", "content": f"Ошибка получения сессии: {e}"},
            ]
            return "", history
        return session_id, history

    @classmethod
    def __response_parser(cls, data: dict, history: list[dict], session_id: str) -> tuple | None:
        """Парсер ответов SSE стриминга."""

        # Вывод источников
        if data["type"] == "done":
            sources = data.get("sources", [])
            if sources:
                sources_text = "\n\n---\n**Источники:**\n"
                for i, src in enumerate(sources, 1):
                    meta = src.get("metadata", {})
                    name = meta.get("source", meta.get("title", f"Документ {i}"))
                    sources_text += f"- {name}\n"
                history[-1]["content"] += sources_text
            return "", history, session_id

        # Ошибка прокидывается отдельно
        elif data["type"] == "error":
            history[-1]["content"] += f"\n\nОшибка: {data['content']}"
            return "", history, session_id
        return None
