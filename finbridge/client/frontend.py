"""Точка входа Gradio-приложения FinBridge RAG Assistant. Атрошенко Б. С."""

import gradio as gr

from tabs.chat_tab import build_chat_tab
from tabs.documents_tab import build_documents_tab

with gr.Blocks(title="FinBridge RAG Assistant") as demo:
    gr.Markdown("# FinBridge RAG Assistant")

    with gr.Tabs():
        with gr.Tab("Чат"):
            build_chat_tab()

        with gr.Tab("Документы"):
            build_documents_tab(demo)

if __name__ == "__main__":
    demo.launch(server_name="0.0.0.0", server_port=7860, theme=gr.themes.Soft())
