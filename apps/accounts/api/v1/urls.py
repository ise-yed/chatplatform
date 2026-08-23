from django.urls import path

from apps.accounts.api.v1.views.authentication import (
    DeviceSessionListView,
    DeviceSessionRevokeView,
    LoginView,
    LogoutAllView,
    LogoutView,
    RefreshTokenView,
)

app_name = "accounts_api_v1"

urlpatterns = [
    path("login/", LoginView.as_view(), name="login"),
    path("refresh/", RefreshTokenView.as_view(), name="refresh"),
    path("logout/", LogoutView.as_view(), name="logout"),
    path("logout-all/", LogoutAllView.as_view(), name="logout_all"),
    path("sessions/", DeviceSessionListView.as_view(), name="sessions"),
    path("sessions/<uuid:session_id>/", DeviceSessionRevokeView.as_view(), name="session_revoke"),
]
