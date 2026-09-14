from rest_framework.permissions import BasePermission


class IsSadmin(BasePermission):
    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and request.user.role == 'SADMIN')


class IsJefe(BasePermission):
    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and request.user.role == 'JEFE')


class IsJefeOrSadmin(BasePermission):
    def has_permission(self, request, view):
        return bool(
            request.user
            and request.user.is_authenticated
            and request.user.role in {'JEFE', 'SADMIN'}
        )


class IsInvestigadorOrHigher(BasePermission):
    def has_permission(self, request, view):
        return bool(
            request.user
            and request.user.is_authenticated
            and request.user.role in {'INVESTIGADOR', 'JEFE', 'SADMIN'}
        )
