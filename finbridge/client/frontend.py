"""Точка входа Gradio-приложения FinBridge RAG Assistant. Атрошенко Б. С."""

import gradio as gr

from client.tabs.chat_tab import ChatTab
from client.tabs.documents_tab import DocTabUI
from config import settings

with gr.Blocks(title="FinBridge RAG Assistant") as demo:
    gr.Markdown("# FinBridge RAG Assistant")

    with gr.Tabs():
        with gr.Tab("Чат"):
            ChatTab.build_chat_tab()

        with gr.Tab("Документы"):
            DocTabUI.build_documents_tab(demo)

if __name__ == "__main__":
    demo.launch(server_name="0.0.0.0", server_port=settings.GRADIO_PORT, theme=gr.themes.Soft())
