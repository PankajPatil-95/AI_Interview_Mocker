from django.shortcuts import render,HttpResponse

# Create your views here.
#edited
from rest_framework import generics, permissions
from .models import User
from .serializers import UserSerializer, RegisterSerializer

def home(request):
    return HttpResponse("WELCOME TO AI INTERVIEW MOCKER!!")
class RegisterView(generics.CreateAPIView):
    queryset = User.objects.all()
    serializer_class = RegisterSerializer
    permission_classes = [permissions.AllowAny]

class ProfileView(generics.RetrieveAPIView):
    queryset = User.objects.all()
    serializer_class = UserSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_object(self):
        return self.request.user

