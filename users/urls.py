from django.urls import path
from .views import RegisterView, UserProfileView, ChangePasswordView

urlpatterns = [
    path("register/", RegisterView.as_view(), name="auth_register"),
    path("me/", UserProfileView.as_view(), name="auth_me"),
    path("change-password/", ChangePasswordView.as_view(), name="change_password"),
]