from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render

from apps.accounts.models import DeviceSession
from apps.accounts.services.authentication import create_web_device_session, revoke_device_session


def login_view(request):
    """
    Renders the login form (GET) and authenticates the user via
    Django's session-based auth (POST). This is separate from the
    JWT flow used by the mobile API — the web version relies on
    Django's built-in session cookie, not a bearer token.
    """
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        user = authenticate(request, username=username, password=password)

        if user is not None:
            login(request, user)

            # login() cycles the session key but doesn't force a save,
            # so session_key can still be None here until the response
            # is processed by SessionMiddleware. We need it now to link
            # this DeviceSession to the actual Session row.
            if not request.session.session_key:
                request.session.save()

            create_web_device_session(
                user=user,
                django_session_key=request.session.session_key,
                expires_at=request.session.get_expiry_date(),
                device_type='web',
                user_agent=request.META.get('HTTP_USER_AGENT', ''),
            )

            return redirect('chat:conversation_list')

        return render(request, 'accounts/login.html', {'error': 'Invalid credentials.'})

    return render(request, 'accounts/login.html')


@login_required
def logout_view(request):
    """
    Logs the current user out and revokes its DeviceSession record —
    without this, the session would keep showing as an active device
    (on this same dashboard we just made web logins show up on) for
    up to its full 2-week expiry after the user already logged out.
    """
    session_key = request.session.session_key
    if session_key:
        device_session = DeviceSession.objects.filter(
            user=request.user,
            django_session_key=session_key,
            revoked_at__isnull=True,
        ).first()
        if device_session is not None:
            revoke_device_session(session=device_session)

    logout(request)
    return redirect('accounts:login')