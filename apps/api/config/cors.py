"""开发环境 CORS 中间件。生产环境由反向代理处理。"""

from django.http import HttpResponse


class CorsMiddleware:
    """允许任意跨域请求（仅 DEBUG 环境）。"""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # OPTIONS 预检请求直接拦截返回
        if request.method == "OPTIONS":
            response = HttpResponse(status=204)
        else:
            response = self.get_response(request)

        response["Access-Control-Allow-Origin"] = "*"
        response["Access-Control-Allow-Methods"] = "GET, POST, PUT, PATCH, DELETE, OPTIONS"
        response["Access-Control-Allow-Headers"] = "Content-Type, Authorization, X-Requested-With"
        response["Access-Control-Max-Age"] = "86400"
        return response
