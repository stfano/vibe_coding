import pytest
from django.contrib.auth.models import User

from apps.authx.models import Department, Role, UserProfile


@pytest.mark.django_db
def test_user_profile_links_django_user_department_and_role():
    user = User.objects.create_user(username="clinician", password="test-password")
    department = Department.objects.create(code="IM", name="Internal Medicine")
    role = Role.objects.create(code="ATTENDING", name="Attending Physician")

    profile = UserProfile.objects.create(
        user=user,
        department=department,
        role=role,
        staff_title="MD",
    )

    assert profile.user == user
    assert profile.department == department
    assert profile.role == role
    assert profile.is_clinician is True
