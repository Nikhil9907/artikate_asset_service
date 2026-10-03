from django.contrib import admin
from django.urls import path, include
from rest_framework.authtoken.views import obtain_auth_token

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/v1/auth-token/', obtain_auth_token, name='api_token_auth'),
    path('api/v1/', include('checkouts.urls')),
]
