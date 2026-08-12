from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render


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
            return redirect('chat:conversation_list')

        return render(request, 'accounts/login.html', {'error': 'Invalid credentials.'})

    return render(request, 'accounts/login.html')


@login_required
def logout_view(request):
    """Logs the current user out and redirects to the login page."""
    logout(request)
    return redirect('accounts:login')