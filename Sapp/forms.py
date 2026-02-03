from django import forms
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm, PasswordChangeForm, PasswordResetForm
from django.contrib.auth.models import User
from .models import USER_ROLES

class SignUpForm(UserCreationForm):
    email = forms.EmailField(required=True)
    # Exclude superadmin and owner from signup roles for security
    SIGNUP_ROLES = [
        ('associate', 'Associate'),
        ('owner', 'Owner'),
    ]
    role = forms.ChoiceField(
        choices=SIGNUP_ROLES,
        required=True,
        help_text="Select your role in the system"
    )

    class Meta:
        model = User
    fields = ('username', 'email', 'password1', 'password2', 'role')
class CustomLoginForm(AuthenticationForm):
    username = forms.CharField(label='Username', max_length=254)
    password = forms.CharField(label='Password', widget=forms.PasswordInput)
class CustomPasswordChangeForm(PasswordChangeForm):
    pass
class CustomPasswordResetForm(PasswordResetForm):
    pass