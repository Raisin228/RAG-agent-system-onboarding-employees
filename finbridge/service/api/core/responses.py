"""Все возможные ответы API. Для OpenAPI доки. Атрошенко Б. С."""

BAD_REQUEST = {
    400: {
        "description": "Bad Request",
        "content": {
            "application/json": {
                "example": {
                    "detail": "the server detected a syntactic/logical "
                              "error in the client's request"
                }
            }
        },
    }
}
