from django import forms
from django.contrib.auth import get_user_model

from .models import Chore, FercoinTransaction

User = get_user_model()


class GiveFercoinsForm(forms.Form):
    recipient = forms.ModelChoiceField(
        queryset=User.objects.filter(is_superuser=False).order_by('username'),
        empty_label='— seleccionar miembro —',
        label='Miembro',
    )
    chore = forms.ModelChoiceField(
        queryset=Chore.objects.filter(is_active=True),
        required=False,
        empty_label='— cantidad personalizada —',
        label='Tarea',
    )
    amount = forms.IntegerField(
        label='Cantidad',
        help_text='Positivo para recompensar, negativo para deducir',
    )
    note = forms.CharField(max_length=255, required=False, label='Nota', widget=forms.TextInput())

    def __init__(self, *args, recipient_id=None, **kwargs):
        super().__init__(*args, **kwargs)
        if recipient_id:
            self.fields['recipient'].initial = recipient_id
        for field in self.fields.values():
            field.widget.attrs['class'] = 'form-control'
        self.fields['recipient'].widget.attrs['class'] = 'form-select'
        self.fields['chore'].widget.attrs['class'] = 'form-select'


class ChoreForm(forms.ModelForm):
    class Meta:
        model = Chore
        fields = ['name', 'description', 'fercoins', 'is_active']
        labels = {
            'name': 'Nombre',
            'description': 'Descripción',
            'fercoins': 'Fercoins',
            'is_active': 'Activa',
        }
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
            'fercoins': forms.NumberInput(attrs={'class': 'form-control'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }
