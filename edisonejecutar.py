import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'jogabonito.settings')
django.setup()

from jogabonito.models import Entrenador, Categoria


print("\n=== ENTRENADORES ===")
for e in Entrenador.objects.all().order_by("apellidos", "nombres"):
    print(
        f"ID={e.id} | "
        f"{e.nombre_completo()} | "
        f"CI={e.cedula or '-'} | "
        f"Tel={e.telefono or '-'} | "
        f"Email={e.email or '-'} | "
        f"Activo={e.activo}"
    )

print(f"\nTOTAL ENTRENADORES: {Entrenador.objects.count()}")


print("\n=== GRUPOS / CATEGORÍAS ===")
for c in Categoria.objects.all().order_by("hora_inicio", "nombre"):
    entrenadores = ", ".join(
        e.nombre_completo() for e in c.entrenadores.all()
    ) or "SIN ENTRENADORES"

    encargado = (
        c.encargado.nombre_completo()
        if c.encargado
        else "SIN ENCARGADO"
    )

    print(
        f"ID={c.id} | "
        f"{c.nombre} | "
        f"Días={c.dias_texto()} | "
        f"Horario={c.horario_texto()} | "
        f"Valor=${c.valor_mensual} | "
        f"Encargado={encargado} | "
        f"Entrenadores={entrenadores}"
    )

print(f"\nTOTAL GRUPOS: {Categoria.objects.count()}")