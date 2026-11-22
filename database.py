import os
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

# Credenciales por defecto de XAMPP: usuario root, sin contraseña
"""DATABASE_URL = "mysql+pymysql://root:@localhost:3306/erp_parroquia"""

# Si existe DATABASE_URL en la nube la usa; si no, usa tu MySQL local
SQLALCHEMY_DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "mysql+pymysql://root:@localhost/erp_parroquia" # Ajusta si tu local tiene contraseña
)

# Motor de conexión a MySQL (echo=True imprime las consultas SQL en la terminal para debugear)
engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"ssl": {"ca": "/etc/ssl/certs/ca-certificates.crt"}}, # deja el connect_args que ya tenías
    pool_pre_ping=True,
    pool_recycle=280
)

# Fábrica de sesiones transaccionales
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Clase base de la que heredarán nuestros modelos de datos
Base = declarative_base()

# Función de dependencia para inyectar la conexión en cada petición de FastAPI y cerrarla al terminar
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()