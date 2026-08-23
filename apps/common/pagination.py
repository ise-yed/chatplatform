from rest_framework.pagination import CursorPagination, PageNumberPagination


class StandardResultsSetPagination(PageNumberPagination):
    page_size = 20
    page_size_query_param = "page_size"
    max_page_size = 100


class MessageCursorPagination(CursorPagination):
    """
    Cursor pagination for message history.

    Cursor (not page-number) pagination is the right fit here: message
    lists grow without bound and receive constant inserts, so offset
    pages would drift and skip/duplicate rows as new messages arrive.
    A cursor is a stable pointer into the ordering instead.

    Ordered newest-first ('-created_at'): the first page returns the
    most recent messages, and following the `next` link walks backward
    into older history — i.e. the "load older messages" gesture. The
    client reverses each page for top-to-bottom display.
    """
    page_size = 30
    max_page_size = 100
    page_size_query_param = "page_size"
    ordering = "-created_at"
    cursor_query_param = "cursor"

