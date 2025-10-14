from rest_framework import serializers
from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password

User = get_user_model()


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        # default Django User fields; adjust if you later add custom fields
        fields = ["id", "username", "first_name", "email"]


class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, required=True, validators=[validate_password])

    class Meta:
        model = User
        fields = ["username", "first_name", "email", "password"]

    def create(self, validated_data):
        username = validated_data.get("username")
        email = validated_data.get("email", "")
        first_name = validated_data.get("first_name", "")
        password = validated_data.get("password")
        user = User.objects.create_user(username=username, email=email, password=password, first_name=first_name)
        return user
