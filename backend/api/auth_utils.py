from django.contrib.auth import get_user_model
from django.db import transaction


def assign_default_role_for_new_user():
    User = get_user_model()
    list(User.objects.select_for_update().filter(role=User.Role.SADMIN).values_list('id', flat=True))
    has_non_sadmin = User.objects.select_for_update().exclude(role=User.Role.SADMIN).exists()
    return User.Role.INVESTIGADOR if has_non_sadmin else User.Role.JEFE


@transaction.atomic
def create_user_with_auto_role(*, name, email, password=None, provider='local', avatar=None):
    User = get_user_model()
    role = assign_default_role_for_new_user()
    email = email.lower().strip()
    username = email
    user = User(
        username=username,
        email=email,
        first_name=name.strip(),
        role=role,
        provider=provider,
        avatar=avatar,
        is_active=True,
        es_investigador=(role == User.Role.INVESTIGADOR),
    )
    if password:
        user.set_password(password)
    else:
        user.set_unusable_password()
    user.save()
    return user


def active_jefe_count(exclude_user=None):
    User = get_user_model()
    queryset = User.objects.filter(role=User.Role.JEFE, is_active=True)
    if exclude_user is not None:
        queryset = queryset.exclude(pk=exclude_user.pk)
    return queryset.count()


def initial_jefe_id():
    User = get_user_model()
    return (
        User.objects.exclude(role=User.Role.SADMIN)
        .filter(role=User.Role.JEFE)
        .order_by('date_joined', 'id')
        .values_list('id', flat=True)
        .first()
    )


def is_initial_jefe(user):
    return bool(user and user.pk == initial_jefe_id())
