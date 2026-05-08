from django.db import models

# Create your models here.
from django.contrib.gis.db import models
from django.contrib.auth.models import AbstractUser
from django.db.models import Q

# --- 1. USUARIOS ---
class UsuarioCustom(AbstractUser):
    class Role(models.TextChoices):
        SADMIN = 'SADMIN', 'SADMIN'
        JEFE = 'JEFE', 'JEFE'
        INVESTIGADOR = 'INVESTIGADOR', 'INVESTIGADOR'

    class Provider(models.TextChoices):
        LOCAL = 'local', 'Local'
        GOOGLE = 'google', 'Google'

    email = models.EmailField('email address', unique=True)
    role = models.CharField(max_length=20, choices=Role.choices, default=Role.INVESTIGADOR)
    provider = models.CharField(max_length=20, choices=Provider.choices, default=Provider.LOCAL)
    avatar = models.URLField(blank=True, null=True)
    es_investigador = models.BooleanField(default=False)
    institucion = models.CharField(max_length=150, blank=True, null=True)

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['username']

    class Meta:
        verbose_name = 'user'
        verbose_name_plural = 'users'
        constraints = [
            models.UniqueConstraint(
                fields=['role'],
                condition=Q(role='SADMIN'),
                name='unique_sadmin_user',
            )
        ]

    @property
    def is_sadmin(self):
        return self.role == self.Role.SADMIN

    @property
    def is_jefe_or_higher(self):
        return self.role in {self.Role.SADMIN, self.Role.JEFE}

    def __str__(self):
        return self.email or self.username

# --- 2. CATÁLOGOS GEOGRÁFICOS ---
class Estado(models.Model):
    nombre = models.CharField(max_length=50, unique=True)

    def __str__(self):
        return self.nombre

class Municipio(models.Model):
    estado = models.ForeignKey(Estado, on_delete=models.CASCADE, related_name='municipios')
    nombre = models.CharField(max_length=100)

    # class Meta:
    #     unique_together = ('estado', 'nombre')

    def __str__(self):
        return f"{self.nombre}, {self.estado.nombre}"

# --- 3. TERRENOS ---
class Terreno(models.Model):
    municipio = models.ForeignKey(Municipio, on_delete=models.PROTECT, related_name='terrenos')
    latitud_norte_dms = models.CharField(max_length=50, blank=True, null=True)
    longitud_oeste_dms = models.CharField(max_length=50, blank=True, null=True)
    latitud_gps = models.FloatField(help_text="Coordenada Y")
    longitud_gps = models.FloatField(help_text="Coordenada X")
    altitud = models.FloatField(null=True, blank=True)
    ubicacion_geo = models.PointField(srid=4326, blank=True, null=True)

    def __str__(self):
        return f"Terreno {self.id} - {self.municipio.nombre}"

# --- 4. CATÁLOGOS AGRÍCOLAS ---
class Hibrido(models.Model):
    marca = models.CharField(max_length=100, blank=True, null=True)
    nombre = models.CharField(max_length=100)

    def __str__(self):
        return f"{self.marca} - {self.nombre}"

# --- 5. CICLOS ---
class Ciclo(models.Model):
    CONDICION_CHOICES = [
        ('Riego', 'Riego'),
        ('Temporal', 'Temporal'),
    ]
    terreno = models.ForeignKey(Terreno, on_delete=models.CASCADE, related_name='ciclos')
    hibrido = models.ForeignKey(Hibrido, on_delete=models.CASCADE, related_name='ciclos')
    year = models.IntegerField()
    fecha_siembra = models.DateField(null=True, blank=True)
    fecha_cosecha = models.DateField(null=True, blank=True)
    condicion = models.CharField(max_length=20, choices=CONDICION_CHOICES)

    def __str__(self):
        return f"Ciclo {self.year} - {self.terreno.municipio.nombre} ({self.hibrido.nombre})"

# --- 6. RESULTADOS ---
class ResultadoLaboratorio(models.Model):
    METODOLOGIA_CHOICES = [
        ('Química Húmeda', 'Química Húmeda'),
        ('NIRS', 'NIRS'),
    ]
    ciclo = models.OneToOneField(Ciclo, on_delete=models.CASCADE, related_name='laboratorio')
    metodologia = models.CharField(max_length=50, choices=METODOLOGIA_CHOICES, null=True, blank=True)
    
    pem = models.FloatField(null=True, blank=True)
    pff = models.FloatField(null=True, blank=True)
    dff = models.FloatField(null=True, blank=True)
    ucaff = models.FloatField(null=True, blank=True)
    npc = models.FloatField(null=True, blank=True)
    ppc = models.FloatField(null=True, blank=True)
    rmf = models.FloatField(null=True, blank=True)
    ms = models.FloatField(null=True, blank=True)
    cen = models.FloatField(null=True, blank=True)
    gc = models.FloatField(null=True, blank=True)
    pc = models.FloatField(null=True, blank=True)
    fdn = models.FloatField(null=True, blank=True)
    cnf = models.FloatField(null=True, blank=True)
    rms = models.FloatField(null=True, blank=True)

    def __str__(self):
        return f"Lab: {self.ciclo}"

class DatoClimatico(models.Model):
    ciclo = models.OneToOneField(Ciclo, on_delete=models.CASCADE, related_name='clima')
    dco = models.IntegerField(null=True, blank=True)
    pp_anual = models.FloatField(null=True, blank=True)
    pp_co = models.FloatField(null=True, blank=True)
    tm_anual = models.FloatField(null=True, blank=True)
    tmax_anual = models.FloatField(null=True, blank=True)
    tmin_anual = models.FloatField(null=True, blank=True)
    tm_co = models.FloatField(null=True, blank=True)
    tmax_co = models.FloatField(null=True, blank=True)
    tmin_co = models.FloatField(null=True, blank=True)
    uca_co = models.FloatField(null=True, blank=True)
    horas_calor_30 = models.FloatField(null=True, blank=True)
    horas_frio_5 = models.FloatField(null=True, blank=True)
    ghi = models.FloatField(null=True, blank=True)
    ss = models.FloatField(null=True, blank=True)

    def __str__(self):
        return f"Clima: {self.ciclo}"
