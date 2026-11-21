import uuid
from faker import Faker
from database import SessionLocal
import models

# Configuración regional para generar datos sintéticos coherentes con el entorno
fake = Faker('es_MX')


def poblar_base_datos(cantidad=600):
    db = SessionLocal()
    print(f"Iniciando la inyección de {cantidad} catequizandos...")

    # Extraemos los DNIs existentes para evitar colisiones (Unique Constraint)
    dnis_existentes = {c[0] for c in db.query(models.Catequizando.dni).all()}

    nuevos_registros = []
    for _ in range(cantidad):
        # Generar un DNI de 8 dígitos garantizando que no se repita
        dni_falso = fake.unique.numerify(text='########')
        while dni_falso in dnis_existentes:
            dni_falso = fake.unique.numerify(text='########')

        nuevo_alumno = models.Catequizando(
            dni=dni_falso,
            nombres=fake.first_name(),
            # Concatenamos dos apellidos para mantener la estructura de la base de datos
            apellidos=fake.last_name() + " " + fake.last_name(),
            # uuid4 genera una cadena alfanumérica robusta de 36 caracteres para el QR
            qr_token=str(uuid.uuid4())
        )
        nuevos_registros.append(nuevo_alumno)

    # Bulk Insert: Inyecta todos los registros en una sola transacción para maximizar el rendimiento
    db.bulk_save_objects(nuevos_registros)
    db.commit()
    db.close()
    print("¡Inyección completada exitosamente!")


if __name__ == "__main__":
    poblar_base_datos(600)