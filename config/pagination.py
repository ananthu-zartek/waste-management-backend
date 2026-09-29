from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response


class OptionalPagination(PageNumberPagination):
    page_size = 10  # Default page size
    page_size_query_param = "page_size"
    max_page_size = 100

    def get_page_size(self, request):
        if "page" in request.query_params:
            return super().get_page_size(request)
        return None

    def get_paginated_response(self, data):
        if "page" in self.request.query_params:
            return super().get_paginated_response(data)
        return Response(data)
