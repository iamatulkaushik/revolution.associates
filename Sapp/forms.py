from django import forms
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm, PasswordChangeForm, PasswordResetForm
from django.contrib.auth.models import User
from .models import USER_ROLES
from Sapp.app.user import associateuser, SubUser
from Sapp.app.company import Company

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

class AssociateUserCreationForm(forms.ModelForm):
    username = forms.CharField(max_length=150, widget=forms.TextInput(attrs={'class': 'form-control'}))
    password = forms.CharField(widget=forms.PasswordInput(attrs={'class': 'form-control'}))
    password2 = forms.CharField(label='Confirm Password', widget=forms.PasswordInput(attrs={'class': 'form-control'}))
    email = forms.EmailField(widget=forms.EmailInput(attrs={'class': 'form-control'}))
    associate_id = forms.CharField(max_length=50, widget=forms.TextInput(attrs={'class': 'form-control'}))
    mobile = forms.CharField(max_length=15, required=False, widget=forms.TextInput(attrs={'class': 'form-control'}))
    address = forms.CharField(required=False, widget=forms.Textarea(attrs={'class': 'form-control', 'rows': 3}))
    companyid = forms.ModelMultipleChoiceField(
        queryset=Company.objects.all(),
        required=False,
        widget=forms.CheckboxSelectMultiple
    )

    class Meta:
        model = associateuser
        fields = ['associate_id', 'mobile', 'address', 'companyid']

    def clean_username(self):
        username = self.cleaned_data.get('username')
        if User.objects.filter(username=username).exists():
            raise forms.ValidationError('Username already exists.')
        return username

    def clean_email(self):
        email = self.cleaned_data.get('email')
        if User.objects.filter(email=email).exists():
            raise forms.ValidationError('Email already exists.')
        return email

    def clean_associate_id(self):
        associate_id = self.cleaned_data.get('associate_id')
        if associateuser.objects.filter(associate_id=associate_id).exists():
            raise forms.ValidationError('Associate ID already exists.')
        return associate_id

    def clean_mobile(self):
        mobile = self.cleaned_data.get('mobile')
        if mobile and associateuser.objects.filter(mobile=mobile).exists():
            raise forms.ValidationError('Mobile number already exists.')
        return mobile

    def clean(self):
        cleaned_data = super().clean()
        password = cleaned_data.get('password')
        password2 = cleaned_data.get('password2')
        if password and password2 and password != password2:
            raise forms.ValidationError('Passwords do not match.')
        return cleaned_data

    def save(self, commit=True):
        user = User.objects.create_user(
            username=self.cleaned_data['username'],
            email=self.cleaned_data['email'],
            password=self.cleaned_data['password']
        )
        associate = super().save(commit=False)
        associate.user = user
        if commit:
            associate.save()
            self.save_m2m()
        return associate

class SubUserCreationForm(forms.ModelForm):
    username = forms.CharField(max_length=150, widget=forms.TextInput(attrs={'class': 'form-control'}))
    password = forms.CharField(widget=forms.PasswordInput(attrs={'class': 'form-control'}))
    password2 = forms.CharField(label='Confirm Password', widget=forms.PasswordInput(attrs={'class': 'form-control'}))
    email = forms.EmailField(widget=forms.EmailInput(attrs={'class': 'form-control'}))
    associate = forms.ModelChoiceField(
        queryset=associateuser.objects.filter(is_active=True),
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    role = forms.ChoiceField(
        choices=[('operator', 'Operator'), ('employee', 'Employee')],
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    mobile = forms.CharField(max_length=15, required=False, widget=forms.TextInput(attrs={'class': 'form-control'}))
    address = forms.CharField(required=False, widget=forms.Textarea(attrs={'class': 'form-control', 'rows': 3}))
    companyid = forms.ModelMultipleChoiceField(
        queryset=Company.objects.none(),
        required=False,
        widget=forms.CheckboxSelectMultiple
    )

    class Meta:
        model = SubUser
        fields = ['associate', 'role', 'mobile', 'address', 'companyid']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if 'associate' in self.data:
            try:
                associate_id = int(self.data.get('associate'))
                associate = associateuser.objects.get(pk=associate_id)
                self.fields['companyid'].queryset = associate.companyid.all()
            except (ValueError, TypeError, associateuser.DoesNotExist):
                pass
        elif self.instance.pk:
            self.fields['companyid'].queryset = self.instance.associate.companyid.all()

    def clean_username(self):
        username = self.cleaned_data.get('username')
        if User.objects.filter(username=username).exists():
            raise forms.ValidationError('Username already exists.')
        return username

    def clean_email(self):
        email = self.cleaned_data.get('email')
        if User.objects.filter(email=email).exists():
            raise forms.ValidationError('Email already exists.')
        return email

    def clean_mobile(self):
        mobile = self.cleaned_data.get('mobile')
        if mobile and SubUser.objects.filter(mobile=mobile).exists():
            raise forms.ValidationError('Mobile number already exists.')
        return mobile

    def clean(self):
        cleaned_data = super().clean()
        password = cleaned_data.get('password')
        password2 = cleaned_data.get('password2')
        if password and password2 and password != password2:
            raise forms.ValidationError('Passwords do not match.')
        return cleaned_data

    def save(self, commit=True):
        user = User.objects.create_user(
            username=self.cleaned_data['username'],
            email=self.cleaned_data['email'],
            password=self.cleaned_data['password']
        )
        subuser = super().save(commit=False)
        subuser.user = user
        if commit:
            subuser.save()
            self.save_m2m()
        return subuser
# forms for associate and subuser passwords

class AssociatePasswordChangeForm(PasswordChangeForm):
    pass

class SubUserPasswordChangeForm(PasswordChangeForm):
    pass

class AssociatePasswordResetForm(PasswordResetForm):
    pass

class SubUserPasswordResetForm(PasswordResetForm):
    pass