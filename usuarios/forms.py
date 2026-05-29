from django import forms
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth import password_validation
from .models import Usuario, DireccionEnvio, DEPARTAMENTOS_PERU, ESTADOS_PEDIDO


class RegistroForm(forms.ModelForm):
    """H001.1"""
    password1 = forms.CharField(
        label='Contraseña',
        widget=forms.PasswordInput(attrs={'placeholder': 'Contraseña', 'class': 'form-control'}))
    password2 = forms.CharField(
        label='Confirmar contraseña',
        widget=forms.PasswordInput(attrs={'placeholder': 'Confirmar contraseña', 'class': 'form-control'}))

    class Meta:
        model  = Usuario
        fields = ['nombre', 'email']
        widgets = {
            'nombre': forms.TextInput(attrs={'placeholder': 'Nombre completo', 'class': 'form-control'}),
            'email':  forms.EmailInput(attrs={'placeholder': 'Correo electrónico', 'class': 'form-control'}),
        }

    def clean_email(self):
        email = self.cleaned_data.get('email')
        if Usuario.objects.filter(email=email).exists():
            raise forms.ValidationError('Este correo ya está registrado.')
        return email

    def clean(self):
        cleaned = super().clean()
        p1, p2 = cleaned.get('password1'), cleaned.get('password2')
        if p1 and p2 and p1 != p2:
            raise forms.ValidationError('Las contraseñas no coinciden.')
        return cleaned

    def save(self, commit=True):
        user = super().save(commit=False)
        user.set_password(self.cleaned_data['password1'])
        if commit:
            user.save()
        return user


class LoginForm(AuthenticationForm):
    """H002.1 + H002.2"""
    username = forms.EmailField(
        label='Correo',
        widget=forms.EmailInput(attrs={'placeholder': 'Correo electrónico', 'class': 'form-control', 'autofocus': True}))
    password = forms.CharField(
        label='Contraseña',
        widget=forms.PasswordInput(attrs={'placeholder': 'Contraseña', 'class': 'form-control'}))
    remember_me = forms.BooleanField(required=False, label='Recordarme 7 días')


class EditarPerfilForm(forms.ModelForm):
    """H005.1 — Editar nombre y teléfono"""
    class Meta:
        model  = Usuario
        fields = ['nombre', 'telefono']
        widgets = {
            'nombre':   forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Nombre completo'}),
            'telefono': forms.TextInput(attrs={'class': 'form-control', 'placeholder': '+51 999 999 999'}),
        }


class CambiarPasswordForm(forms.Form):
    """H005.2 — Cambiar contraseña desde perfil"""
    password_actual = forms.CharField(
        label='Contraseña actual',
        widget=forms.PasswordInput(attrs={'class': 'form-control', 'placeholder': 'Contraseña actual'}))
    password_nueva = forms.CharField(
        label='Nueva contraseña',
        widget=forms.PasswordInput(attrs={'class': 'form-control', 'placeholder': 'Nueva contraseña'}))
    password_confirmar = forms.CharField(
        label='Confirmar nueva contraseña',
        widget=forms.PasswordInput(attrs={'class': 'form-control', 'placeholder': 'Confirmar nueva contraseña'}))

    def clean(self):
        cleaned = super().clean()
        p1 = cleaned.get('password_nueva')
        p2 = cleaned.get('password_confirmar')
        if p1 and p2 and p1 != p2:
            raise forms.ValidationError('Las contraseñas nuevas no coinciden.')
        return cleaned


class RecuperarPasswordForm(forms.Form):
    """H004.1"""
    email = forms.EmailField(
        label='Correo registrado',
        widget=forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'tu@correo.com'}))


class NuevaPasswordForm(forms.Form):
    """H004.2"""
    password1 = forms.CharField(
        label='Nueva contraseña',
        widget=forms.PasswordInput(attrs={'class': 'form-control', 'placeholder': 'Nueva contraseña'}))
    password2 = forms.CharField(
        label='Confirmar contraseña',
        widget=forms.PasswordInput(attrs={'class': 'form-control', 'placeholder': 'Confirmar contraseña'}))

    def clean(self):
        cleaned = super().clean()
        p1, p2 = cleaned.get('password1'), cleaned.get('password2')
        if p1 and p2 and p1 != p2:
            raise forms.ValidationError('Las contraseñas no coinciden.')
        return cleaned


# ── H008 — Dirección de envío ────────────────────────────────
class DireccionForm(forms.ModelForm):
    class Meta:
        model  = DireccionEnvio
        fields = ['calle', 'ciudad', 'departamento', 'codigo_postal']
        widgets = {
            'calle':         forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ej: Av. Larco 1234, Dpto 5B'}),
            'ciudad':        forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ej: Miraflores'}),
            'departamento':  forms.Select(attrs={'class': 'form-select'}),
            'codigo_postal': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ej: 15001'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['departamento'].choices = [('', '— Selecciona departamento —')] + list(DEPARTAMENTOS_PERU)

    def clean_departamento(self):
        val = self.cleaned_data.get('departamento')
        if not val:
            raise forms.ValidationError('Selecciona un departamento.')
        return val


# ── H010.2 — Filtros de pedidos ──────────────────────────────
class FiltroPedidosForm(forms.Form):
    fecha_desde = forms.DateField(
        required=False,
        label='Desde',
        widget=forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}))
    fecha_hasta = forms.DateField(
        required=False,
        label='Hasta',
        widget=forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}))
    estado = forms.ChoiceField(
        required=False,
        label='Estado',
        choices=[('', 'Todos los estados')] + list(ESTADOS_PEDIDO),
        widget=forms.Select(attrs={'class': 'form-select'}))
