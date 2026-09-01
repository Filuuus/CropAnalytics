from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("api", "0002_auth_roles"),
    ]

    operations = [
        migrations.CreateModel(
            name="SoilMoisturePlot",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("plot_id", models.CharField(help_text="Slug from plot_registry (e.g. 'guadalajara')", max_length=50)),
                ("plot_name", models.CharField(max_length=100)),
                ("latitude", models.FloatField()),
                ("longitude", models.FloatField()),
                ("analysis_date", models.DateField(auto_now_add=True)),
                ("mean_sm", models.FloatField(blank=True, help_text="Annual mean soil moisture m³/m³", null=True)),
                ("min_sm", models.FloatField(blank=True, null=True)),
                ("max_sm", models.FloatField(blank=True, null=True)),
                ("dry_days", models.IntegerField(blank=True, help_text="Days with sm < 0.15", null=True)),
                ("wet_days", models.IntegerField(blank=True, help_text="Days with sm > 0.35", null=True)),
                ("model_backend", models.CharField(default="lstm_frozen", max_length=30)),
                ("timeseries_json", models.TextField(blank=True, help_text="JSON array [{date, soil_moisture}, …]")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
            ],
            options={
                "ordering": ["-created_at"],
            },
        ),
        migrations.AlterUniqueTogether(
            name="soilmoistureplot",
            unique_together={("plot_id", "analysis_date")},
        ),
    ]
