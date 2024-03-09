from django.forms import ModelForm
from django.contrib.auth.forms import UserCreationForm
from django import forms
from .models import Room ,User, Event ,Store,Product,Order,MessageReport


class MyUserCreationForm(UserCreationForm):
    class Meta:
        model = User
        fields = ['name','username','email','password1','password2']

class ProfileForm(ModelForm):
    class Meta:
        model = User
        fields = ['avatar']

class RoomForm(ModelForm):
    class Meta:
        model = Room
        fields = '__all__'
        exclude =['host','participants']


class UserForm(ModelForm):
    class Meta:
        model = User
        fields = ['name','username','email','bio','avatar']



class EventsForm(ModelForm):
    class Meta:
        model = Event
        fields = '__all__'
        exclude =['host','par']
        widgets = {
            'start_time': forms.DateTimeInput(attrs={'type': 'datetime-local'}),
            'end_time': forms.DateTimeInput(attrs={'type': 'datetime-local'}),
            # Có thể thêm các widget khác cho các trường khác nếu cần
        }


class StoreForm(ModelForm):
    class Meta:
        model = Store
        fields = '__all__'
        exclude =['owner','liker']



class ProductForm(ModelForm):
    class Meta:
        model = Product
        fields = ['name', 'quantity', 'description', 'price', 'image']



class CheckoutForm(ModelForm):
    class Meta:
        model = Order
        fields = ['address', 'full_name', 'phone_number']



class ReportForm(forms.ModelForm):
    reason = forms.MultipleChoiceField(
        choices=MessageReport.ReportReasons.choices, 
        widget=forms.CheckboxSelectMultiple,
        required=True
    )

    class Meta:
        model = MessageReport
        fields = ['reason', 'detail']