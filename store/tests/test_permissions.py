import uuid
from unittest.mock import MagicMock
import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIRequestFactory
from store.permissions import IsAdminOrReadOnly, IsOwnerOrAdmin, IsReviewAuthorOrAdmin

User = get_user_model()
factory = APIRequestFactory()

@pytest.fixture
def user():
    return User(id=1, email="user@example.com", is_staff=False)

@pytest.fixture
def admin_user():
    return User(id=2, email="admin@example.com", is_staff=True)

def test_is_admin_or_read_only(user, admin_user):
    perm = IsAdminOrReadOnly()
    view = MagicMock()

    get_req = factory.get("/")
    get_req.user = user
    assert perm.has_permission(get_req, view) is True

    anon_req = factory.get("/")
    anon_req.user = None
    assert perm.has_permission(anon_req, view) is True

    post_user_req = factory.post("/")
    post_user_req.user = user
    assert perm.has_permission(post_user_req, view) is False

    post_admin_req = factory.post("/")
    post_admin_req.user = admin_user
    assert perm.has_permission(post_admin_req, view) is True

def test_is_owner_or_admin(user, admin_user):
    perm = IsOwnerOrAdmin()
    view = MagicMock()

    other_user = User(id=999, email="other@example.com")
    obj = MagicMock()
    obj.user = user

    admin_req = factory.delete("/")
    admin_req.user = admin_user
    assert perm.has_object_permission(admin_req, view, obj) is True

    owner_req = factory.put("/")
    owner_req.user = user
    assert perm.has_object_permission(owner_req, view, obj) is True

    stranger_req = factory.delete("/")
    stranger_req.user = other_user
    assert perm.has_object_permission(stranger_req, view, obj) is False

def test_is_review_author_or_admin(user, admin_user):
    perm = IsReviewAuthorOrAdmin()
    view = MagicMock()

    other_user = User(id=999, email="other@example.com")
    obj = MagicMock()
    obj.user = user

    get_req = factory.get("/")
    get_req.user = None
    assert perm.has_object_permission(get_req, view, obj) is True

    owner_req = factory.put("/")
    owner_req.user = user
    assert perm.has_object_permission(owner_req, view, obj) is True

    admin_req = factory.delete("/")
    admin_req.user = admin_user
    assert perm.has_object_permission(admin_req, view, obj) is True

    stranger_req = factory.delete("/")
    stranger_req.user = other_user
    assert perm.has_object_permission(stranger_req, view, obj) is False