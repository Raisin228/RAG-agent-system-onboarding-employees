"""Утилитки, используемые по всему проекту. Атрошенко Б. С."""


def load_prompt(path: str) -> str:
    """
    Загрузить промпт.

    :param path: путь до файла.
    :return содержимое.
    """

    with open(path) as f:
        return f.read()
