from fastapi import FastAPI
from sqlalchemy import text
import models
from database import engine
from routers import rt_auth, rt_catequizandos, rt_asistencias, rt_tesoreria, rt_secretaria, rt_dashboard

# Sincroniza y crea las tablas en MySQL si no existen
models.Base.metadata.create_all(bind=engine)

with engine.connect() as conn:
    nuevas_cols = [
        "ALTER TABLE asistencias ADD COLUMN metodo_registro VARCHAR(20) DEFAULT 'QR'",
        "ALTER TABLE pagos ADD COLUMN codigo_boleta VARCHAR(50) NULL",
        "ALTER TABLE catequizandos ADD COLUMN colegio VARCHAR(60) NULL",
        "ALTER TABLE catequizandos ADD COLUMN estado_bautismo VARCHAR(30) DEFAULT 'Bautizado'",
        "ALTER TABLE catequizandos ADD COLUMN celular_joven VARCHAR(20) NULL",
        "ALTER TABLE catequizandos ADD COLUMN celular_apoderado_1 VARCHAR(20) NULL",
        "ALTER TABLE catequizandos ADD COLUMN parentesco_apoderado_1 VARCHAR(40) NULL",
        "ALTER TABLE catequizandos ADD COLUMN celular_apoderado_2 VARCHAR(20) NULL",
        "ALTER TABLE catequizandos ADD COLUMN parentesco_apoderado_2 VARCHAR(40) NULL",
        "ALTER TABLE codigos_servicio ADD COLUMN colegio_permitido VARCHAR(60) DEFAULT 'Todos'",
        "ALTER TABLE catequizandos ADD COLUMN grupo VARCHAR(20) NULL",
        "ALTER TABLE catequizandos ADD COLUMN salon VARCHAR(20) NULL",
    ]
    for sql in nuevas_cols:
        try:
            conn.execute(text(sql))
            conn.commit()
        except Exception:
            pass

app = FastAPI(
    title="API ERP Parroquia - Confirmación",
    description="Backend centralizado para gestión logística y financiera",
    version="1.0.0"
)

app.include_router(rt_auth.router)
app.include_router(rt_catequizandos.router)
app.include_router(rt_asistencias.router)
app.include_router(rt_tesoreria.router)
app.include_router(rt_secretaria.router)
app.include_router(rt_dashboard.router)