# apps/core/pagination.py
from rest_framework.pagination import PageNumberPagination


class DefaultPagination(PageNumberPagination):
    """
    Inakubali ?page_size=N (hadi max_page_size). Frontend inaomba
    ?page_size=200 kwa fee rules, packages, n.k.; PageNumberPagination ya
    kawaida ilipuuza hilo na kurudisha 20 tu.
    """
    page_size = 20
    page_size_query_param = "page_size"
    max_page_size = 500