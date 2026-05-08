import { CommonModule } from '@angular/common';
import { ChangeDetectionStrategy, Component, OnInit, computed, inject, signal } from '@angular/core';
import { FormBuilder, ReactiveFormsModule } from '@angular/forms';

import { Header } from '../../../shared/components/header/Header';
import { Footer } from '../../../shared/components/footer/Footer';
import { AuthUser } from '../../../auth/services/auth.service';
import { AdminUsersService, UserFilters } from '../../services/admin-users.service';

@Component({
  selector: 'users-management',
  standalone: true,
  imports: [CommonModule, ReactiveFormsModule, Header, Footer],
  templateUrl: './users-management.component.html',
  changeDetection: ChangeDetectionStrategy.OnPush,
  host: { '[style.display]': "'contents'" },
})
export class UsersManagementComponent implements OnInit {
  private readonly fb = inject(FormBuilder);
  private readonly usersService = inject(AdminUsersService);

  readonly users = signal<AuthUser[]>([]);
  readonly loading = signal(false);
  readonly message = signal('');
  readonly error = signal('');

  readonly filtersForm = this.fb.nonNullable.group({
    search: [''],
    role: [''],
    is_active: [''],
  });

  readonly totalActive = computed(() => this.users().filter((user) => user.is_active).length);
  readonly totalJefes = computed(() => this.users().filter((user) => user.role === 'JEFE').length);

  ngOnInit(): void {
    this.loadUsers();
  }

  loadUsers(): void {
    this.loading.set(true);
    this.error.set('');
    this.usersService.list(this.filtersForm.getRawValue() as UserFilters).subscribe({
      next: (users) => {
        this.users.set(users);
        this.loading.set(false);
      },
      error: (error) => {
        this.error.set(error.error?.detail ?? 'No se pudieron cargar los usuarios.');
        this.loading.set(false);
      },
    });
  }

  clearFilters(): void {
    this.filtersForm.reset();
    this.loadUsers();
  }

  changeRole(user: AuthUser, role: string): void {
    if (role !== 'JEFE' && role !== 'INVESTIGADOR') {
      return;
    }
    this.runAction(
      this.usersService.setRole(user.id, role),
      'Rol actualizado.',
    );
  }

  toggleStatus(user: AuthUser): void {
    const request = user.is_active
      ? this.usersService.deactivate(user.id)
      : this.usersService.activate(user.id);
    this.runAction(request, user.is_active ? 'Usuario inhabilitado.' : 'Usuario activado.');
  }

  deleteUser(user: AuthUser): void {
    if (!confirm(`Eliminar a ${user.email}?`)) {
      return;
    }
    this.usersService.delete(user.id).subscribe({
      next: () => {
        this.message.set('Usuario eliminado.');
        this.loadUsers();
      },
      error: (error) => this.error.set(error.error?.detail ?? 'No se pudo eliminar el usuario.'),
    });
  }

  private runAction(request: ReturnType<AdminUsersService['activate']>, successMessage: string): void {
    this.error.set('');
    this.message.set('');
    request.subscribe({
      next: () => {
        this.message.set(successMessage);
        this.loadUsers();
      },
      error: (error) => this.error.set(error.error?.detail ?? 'Operacion no permitida.'),
    });
  }
}
