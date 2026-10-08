from django.contrib.auth import get_user_model


def create_user(*, name, email, password=None, provider='local', avatar=None):
    # Toda cuenta nueva es INVESTIGADOR; el SADMIN (o un JEFE) asciende desde
    # /users-management. Antes el primer registro se volvía JEFE, y como el
    # registro es público, en una instalación nueva cualquiera podía tomarlo.
    User = get_user_model()
    email = email.lower().strip()
    user = User(
        username=email,
        email=email,
        first_name=name.strip(),
        role=User.Role.INVESTIGADOR,
        provider=provider,
        avatar=avatar,
        is_active=True,
        es_investigador=True,
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
