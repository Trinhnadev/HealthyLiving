from django.shortcuts import redirect
from django.urls import resolve

class InvalidUrlMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        try:
            # resolve sẽ kiểm tra xem URL có thể ánh xạ đến view hay không
            resolve(request.path_info)
        except:
            # Nếu không ánh xạ được, chuyển hướng đến trang unauthorized
            return redirect('unauthorized')

        # Nếu URL hợp lệ, tiếp tục xử lý request bình thường
        response = self.get_response(request)
        return response
