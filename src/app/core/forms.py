from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.validators import UnicodeUsernameValidator

from .models import validate_pin

User = get_user_model()


def _pin_field(label):
    return forms.CharField(
        label=label,
        max_length=4,
        strip=True,
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'inputmode': 'numeric',
            'autocomplete': 'off',
            'pattern': '[0-9]{4}',
            'maxlength': '4',
        }),
    )


class SetPinForm(forms.Form):
    pin = _pin_field('Nuevo PIN')
    pin_confirm = _pin_field('Repite el PIN')

    def clean_pin(self):
        pin = self.cleaned_data['pin']
        validate_pin(pin)
        return pin

    def clean(self):
        cleaned = super().clean()
        pin, confirm = cleaned.get('pin'), cleaned.get('pin_confirm')
        if pin and confirm and pin != confirm:
            raise forms.ValidationError('Los PIN no coinciden. Inténtalo de nuevo.')
        return cleaned


class ChangePinForm(SetPinForm):
    current_pin = _pin_field('PIN actual')

    field_order = ['current_pin', 'pin', 'pin_confirm']


class CreateKidForm(forms.Form):
    username = forms.CharField(
        label='Nombre de usuario',
        max_length=150,
        validators=[UnicodeUsernameValidator()],
        help_text='Un apodo, mejor que el nombre real. Letras, números y @/./+/-/_',
        widget=forms.TextInput(attrs={'class': 'form-control', 'autocomplete': 'off'}),
    )

    def clean_username(self):
        username = self.cleaned_data['username']
        if User.objects.filter(username__iexact=username).exists():
            raise forms.ValidationError('Ese nombre de usuario ya existe.')
        return username
