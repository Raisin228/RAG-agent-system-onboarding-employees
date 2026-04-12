"""Gradio-чат, подключённый к FastAPI /chat/create_insight. Атрошенко Б. С."""

import gradio as gr
import httpx

from config import settings


def chat(message: str, history: list[dict]) -> tuple[str, list[dict]]:
    """
    Отправить сообщение в API и вернуть ответ агента.

    :param message: сообщение пользователя.
    :param history: список словарей, где расположен ответ LLM и запрос пользователя.
    :return: пустая текстовая строка - обновляет поле для ввода. Новая история отображается в чате.
    """
    try:
        response = httpx.post(settings.API_URL, json={"query": message}, timeout=120.0)
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
    return "", history


with gr.Blocks(title="FinBridge RAG Assistant") as demo:
    gr.Markdown("# FinBridge RAG Assistant\nЗадайте вопрос по базе знаний компании.")

    chatbot = gr.Chatbot(
        label="Диалог",
        height=600,
    )

    with gr.Row():
        msg_input = gr.Textbox(
            placeholder="Введите вопрос...",
            show_label=False,
            scale=9,
            submit_btn=True,
        )
        clear_btn = gr.Button("Очистить", scale=1, variant="secondary")

    msg_input.submit(
        fn=chat,
        inputs=[msg_input, chatbot],
        outputs=[msg_input, chatbot],
    )

    clear_btn.click(lambda: ("", []), outputs=[msg_input, chatbot])

if __name__ == "__main__":
    demo.launch(server_name="0.0.0.0", server_port=7860, theme=gr.themes.Soft())
