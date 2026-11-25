from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm, OAuth2PasswordBearer
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from sqlalchemy import func
from sqlalchemy import text
from jose import jwt, JWTError
import models
import security
import schemas
from database import engine, get_db
from pydantic import BaseModel
from datetime import datetime, timedelta, timezone
import secrets
from sqlalchemy.exc import IntegrityError
from typing import Dict, Any, List


# Sincroniza y crea las tablas en MySQL si no existen
models.Base.metadata.create_all(bind=engine)

with engine.connect() as conn:
    try:
        conn.execute(text("ALTER TABLE asistencias ADD COLUMN metodo_registro VARCHAR(20) DEFAULT 'QR'"))
        conn.commit()
    except Exception:
        pass
    try:
        conn.execute(text("ALTER TABLE pagos ADD COLUMN codigo_boleta VARCHAR(50) NULL"))
        conn.commit()
    except Exception:
        pass

with engine.connect() as conn:
    nuevas_cols = [
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

# Declaración del esquema de seguridad de FastAPI
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="login")


# =========================================================
# DEPENDENCIAS DE SEGURIDAD Y RBAC
# =========================================================
def obtener_usuario_actual(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)):
    excepcion_credenciales = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="No se pudieron validar las credenciales",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, security.SECRET_KEY, algorithms=[security.ALGORITHM])
        dni: str = payload.get("sub")
        if dni is None:
            raise excepcion_credenciales
    except JWTError:
        raise excepcion_credenciales

    usuario = db.query(models.Usuario).filter(models.Usuario.dni == dni).first()
    if usuario is None:
        raise excepcion_credenciales
    return usuario


def requerir_rol_tesoreria(usuario: models.Usuario = Depends(obtener_usuario_actual)):
    # Solo Administradores (id_rol = 1) y Tesoreros (id_rol = 3) tienen acceso
    if usuario.id_rol not in [1, 3]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Operación denegada: Privilegios insuficientes"
        )
    return usuario


# =========================================================
# ENDPOINTS DE SEGURIDAD Y USUARIOS
# =========================================================
@app.get("/")
def estado_servidor():
    return {"mensaje": "El servidor FastAPI está corriendo y protegido con JWT"}


@app.post("/registro")
def registrar_usuario_prueba(dni: str, nombres: str, password_plana: str, db: Session = Depends(get_db)):
    usuario_existente = db.query(models.Usuario).filter(models.Usuario.dni == dni).first()
    if usuario_existente:
        raise HTTPException(status_code=400, detail="El DNI ya está registrado")

    password_encriptada = security.obtener_hash_password(password_plana)

    nuevo_usuario = models.Usuario(
        id_rol=1,
        dni=dni,
        nombres=nombres,
        password_hash=password_encriptada
    )
    db.add(nuevo_usuario)
    db.commit()
    db.refresh(nuevo_usuario)
    return {"mensaje": "Usuario creado exitosamente", "usuario": nuevo_usuario.nombres}


@app.post("/login")
def iniciar_sesion(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    usuario = db.query(models.Usuario).filter(models.Usuario.dni == form_data.username).first()

    if not usuario or not security.verificar_password(form_data.password, usuario.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="DNI o contraseña incorrectos",
            headers={"WWW-Authenticate": "Bearer"},
        )

    datos_token = {
        "sub": usuario.dni,
        "id_rol": usuario.id_rol,
        "id_usuario": usuario.id_usuario
    }
    token = security.crear_token_acceso(data=datos_token)

    return {"access_token": token, "token_type": "bearer", "rol": usuario.id_rol}


@app.get("/tesoreria/balance")
def obtener_balance_caja(usuario_actual: models.Usuario = Depends(requerir_rol_tesoreria)):
    return {
        "mensaje": "Acceso concedido a la bóveda de datos financieros",
        "usuario_operador": usuario_actual.nombres,
        "rol_detectado": usuario_actual.id_rol
    }


# =========================================================
# MÓDULO LOGÍSTICO Y ASISTENCIA (QR)
# =========================================================
PERU_TZ = timezone(timedelta(hours=-5))
def _a_hora_peru(dt) -> str:
    if not dt:
        return "-"
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(PERU_TZ).strftime("%Y-%m-%d %H:%M:%S")

@app.post("/api/v1/asistencia", tags=["Logística y Escáner QR"])
def registrar_asistencia(request: schemas.AsistenciaQRRequest, db: Session = Depends(get_db)):
    # 1. Validar código de servicio si viene desde la APK (revocación en vivo y expiración)
    codigo_srv = None
    if request.codigo_servicio and request.codigo_servicio != "ADMIN-LIBRE":
        codigo_srv = db.query(models.CodigoServicio).filter(
            models.CodigoServicio.codigo == request.codigo_servicio.strip().upper()
        ).first()
        if not codigo_srv or not codigo_srv.activo or datetime.utcnow() > codigo_srv.expira_en:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Tu código de servicio venció o fue revocado por un Administrador."
            )
        # Forzar el evento amarrado al código
        tipo_final = codigo_srv.tipo_asistencia
        detalle_final = codigo_srv.detalle_evento
    else:
        tipo_final = request.tipo_asistencia
        detalle_final = request.detalle_evento

    # 2. Buscar catequizando por QR o por DNI (manual)
    alumno = None
    if request.qr_token:
        alumno = db.query(models.Catequizando).filter(models.Catequizando.qr_token == request.qr_token.strip()).first()
    elif request.dni:
        alumno = db.query(models.Catequizando).filter(models.Catequizando.dni == request.dni.strip()).first()

    if not alumno:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Código QR o DNI no encontrado en el directorio."
        )

    # 2.5. Validar colegio permitido (para Código de Servicio o filtro del Administrador)
    colegio_filtro = (
        codigo_srv.colegio_permitido
        if codigo_srv
        else (request.colegio_permitido or "Todos")
    )
    if colegio_filtro and colegio_filtro != "Todos":
        colegio_alumno = (alumno.colegio or "Sin asignar").strip()
        if colegio_alumno.lower() != colegio_filtro.strip().lower():
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Filtro activo solo para {colegio_filtro}. {alumno.nombres} {alumno.apellidos} pertenece a: {colegio_alumno}."
            )

    # 3. Verificar si es Administrador
    usuario = db.query(models.Usuario).filter(models.Usuario.id_usuario == request.id_usuario).first()
    es_admin = False
    if usuario and usuario.rol:
        es_admin = usuario.rol.nombre_rol.strip().lower() in ["administrador", "admin"]

    # 4. Determinar fecha/hora (soporta cola offline)
    fecha_registro = datetime.utcnow()
    if request.fecha_hora_cliente:
        try:
            dt_cli = datetime.fromisoformat(request.fecha_hora_cliente.replace("Z", "+00:00"))
            if dt_cli.tzinfo is not None:
                fecha_registro = dt_cli.astimezone(timezone.utc).replace(tzinfo=None)
            else:
                fecha_registro = dt_cli
        except Exception:
            pass

    # 5. Anti-duplicados (mismo día y evento)
    ya_registrado = db.query(models.Asistencia).filter(
        models.Asistencia.id_cateq == alumno.id_cateq,
        models.Asistencia.tipo_asistencia == tipo_final,
        models.Asistencia.detalle_evento == detalle_final,
        func.date(models.Asistencia.fecha_hora) == fecha_registro.date()
    ).first()

    if ya_registrado:
        if not es_admin:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"{alumno.nombres} {alumno.apellidos} ya registró asistencia hoy en {tipo_final}."
            )
        if not request.forzar_duplicado:
            return JSONResponse(
                status_code=status.HTTP_409_CONFLICT,
                content={
                    "detail": f"{alumno.nombres} {alumno.apellidos} ya tiene asistencia hoy en {tipo_final}. ¿Deseas registrar el duplicado de todas formas?",
                    "puede_forzar": True
                }
            )

    # 6. Calcular Presente vs Tardanza según hora límite en hora Perú (UTC-5)
    estado_asis = "Presente"
    if codigo_srv and codigo_srv.hora_limite_tardanza:
        try:
            lim_h, lim_m = map(int, codigo_srv.hora_limite_tardanza.split(":"))
            hora_peru = fecha_registro.replace(tzinfo=timezone.utc).astimezone(PERU_TZ)
            if (hora_peru.hour, hora_peru.minute) > (lim_h, lim_m):
                estado_asis = "Tardanza"
        except Exception:
            pass

    metodo_final = "Manual" if request.metodo_registro.strip().lower() == "manual" else "QR"

    nueva_asistencia = models.Asistencia(
        id_cateq=alumno.id_cateq,
        id_usuario=request.id_usuario,
        tipo_asistencia=tipo_final,
        detalle_evento=detalle_final,
        estado=estado_asis,
        metodo_registro=metodo_final,
        fecha_hora=fecha_registro
    )
    db.add(nueva_asistencia)
    db.commit()
    db.refresh(nueva_asistencia)

    # 7. Consultar alertas discretas del catequizando (bautismo, docs faltantes y deudas)
    alertas_pendientes = []
    if (alumno.estado_bautismo or "").strip().lower() == "por bautizar":
        alertas_pendientes.append("Falta bautizarse")

    docs_oblig = db.query(models.DocumentoRequisito).filter(models.DocumentoRequisito.es_obligatorio == True).all()
    if docs_oblig:
        entregados = {
            e.id_doc for e in db.query(models.Expediente).filter(
                models.Expediente.id_cateq == alumno.id_cateq,
                models.Expediente.estado == "Entregado"
            ).all()
        }
        for d in docs_oblig:
            if d.id_doc not in entregados:
                alertas_pendientes.append(f"Falta {d.nombre_doc}")

    conceptos = db.query(models.ConceptoPago).all()
    if conceptos:
        pagos_alumno = dict(
            db.query(models.Pago.id_concepto, func.sum(models.Pago.monto))
            .filter(models.Pago.id_cateq == alumno.id_cateq)
            .group_by(models.Pago.id_concepto)
            .all()
        )
        for c in conceptos:
            pagado = float(pagos_alumno.get(c.id_concepto, 0) or 0)
            if pagado < float(c.monto_base):
                alertas_pendientes.append(f"Debe {c.nombre_conc} (S/ {float(c.monto_base) - pagado:.2f})")

    return {
        "mensaje": "Asistencia registrada correctamente",
        "alumno": f"{alumno.nombres} {alumno.apellidos}",
        "dni": alumno.dni,
        "colegio": alumno.colegio or "Sin asignar",
        "tipo_asistencia": tipo_final,
        "detalle_evento": detalle_final or "-",
        "estado": estado_asis,
        "metodo_registro": metodo_final,
        "hora_registro": nueva_asistencia.fecha_hora,
        "es_duplicado": ya_registrado is not None,
        "alertas_pendientes": alertas_pendientes
    }


# =========================================================
# MÓDULO DE TESORERÍA
# =========================================================
@app.post("/api/v1/tesoreria/conceptos", tags=["Tesorería"])
def crear_concepto(concepto: schemas.ConceptoPagoCreate, db: Session = Depends(get_db)):
    existe = db.query(models.ConceptoPago).filter(
        models.ConceptoPago.nombre_conc == concepto.nombre_conc
    ).first()
    if existe:
        raise HTTPException(status_code=400, detail="Ese concepto de pago ya existe")

    nuevo = models.ConceptoPago(
        nombre_conc=concepto.nombre_conc,
        monto_base=concepto.monto_base
    )
    db.add(nuevo)
    db.commit()
    db.refresh(nuevo)
    return {"mensaje": "Concepto creado", "id_concepto": nuevo.id_concepto, "monto_base": float(nuevo.monto_base)}


@app.get("/api/v1/tesoreria/conceptos", tags=["Tesorería"])
def listar_conceptos(db: Session = Depends(get_db)):
    return db.query(models.ConceptoPago).all()


@app.post("/api/v1/tesoreria/pagos", tags=["Tesorería"])
def registrar_pago(pago: schemas.PagoCreate, db: Session = Depends(get_db)):
    alumno = db.query(models.Catequizando).filter(
        models.Catequizando.dni == pago.dni_catequizando
    ).first()
    if not alumno:
        raise HTTPException(status_code=404, detail="Catequizando no encontrado con ese DNI")

    concepto = db.query(models.ConceptoPago).filter(
        models.ConceptoPago.id_concepto == pago.id_concepto
    ).first()
    if not concepto:
        raise HTTPException(status_code=404, detail="Concepto de pago no encontrado")

    monto_final = float(concepto.monto_base)

    nuevo_pago = models.Pago(
        id_cateq=alumno.id_cateq,
        id_usuario=pago.id_usuario,
        id_concepto=concepto.id_concepto,
        monto=monto_final,
        codigo_boleta=(pago.codigo_boleta or "").strip() or None,
        metodo_pago=pago.metodo_pago
    )
    db.add(nuevo_pago)
    db.commit()
    db.refresh(nuevo_pago)

    return {
        "mensaje": "Pago registrado correctamente",
        "id_pago": nuevo_pago.id_pago,
        "alumno": f"{alumno.nombres} {alumno.apellidos}",
        "concepto": concepto.nombre_conc,
        "codigo_boleta": nuevo_pago.codigo_boleta or "-",
        "monto": float(nuevo_pago.monto),
        "metodo_pago": nuevo_pago.metodo_pago,
        "fecha_hora": nuevo_pago.fecha_hora
    }


@app.get("/api/v1/tesoreria/pagos", tags=["Tesorería"])
def listar_pagos(db: Session = Depends(get_db)):
    registros = (
        db.query(
            models.Pago.id_pago,
            models.Catequizando.dni,
            models.Catequizando.nombres,
            models.Catequizando.apellidos,
            models.Catequizando.colegio,
            models.Catequizando.grupo,
            models.ConceptoPago.nombre_conc,
            models.Pago.codigo_boleta,
            models.Pago.monto,
            models.Pago.metodo_pago,
            models.Pago.fecha_hora,
            models.Usuario.nombres.label("registrado_por")
        )
        .join(models.Catequizando, models.Pago.id_cateq == models.Catequizando.id_cateq)
        .join(models.ConceptoPago, models.Pago.id_concepto == models.ConceptoPago.id_concepto)
        .outerjoin(models.Usuario, models.Pago.id_usuario == models.Usuario.id_usuario)
        .order_by(models.Pago.fecha_hora.desc())
        .all()
    )

    total = db.query(func.sum(models.Pago.monto)).scalar() or 0

    return {
        "total_recaudado": float(total),
        "cantidad_pagos": len(registros),
        "pagos": [
            {
                "id_pago": r.id_pago,
                "dni": r.dni,
                "alumno": f"{r.nombres} {r.apellidos}",
                "colegio": r.colegio or "Sin asignar",
                "grupo": r.grupo or "Sin asignar",
                "concepto": r.nombre_conc,
                "codigo_boleta": r.codigo_boleta or "-",
                "monto": float(r.monto),
                "metodo_pago": r.metodo_pago,
                "fecha_hora": _a_hora_peru(r.fecha_hora),
                "registrado_por": r.registrado_por or "Sistema"
            }
            for r in registros
        ]
    }

# =========================================================
# MÓDULO DE SECRETARÍA (GESTIÓN DOCUMENTAL)
# =========================================================
@app.post("/api/v1/secretaria/documentos", tags=["Secretaría"])
def crear_documento_requisito(doc: schemas.DocumentoRequisitoCreate, db: Session = Depends(get_db)):
    existe = db.query(models.DocumentoRequisito).filter(
        models.DocumentoRequisito.nombre_doc == doc.nombre_doc
    ).first()
    if existe:
        raise HTTPException(status_code=400, detail="Ese documento requisito ya existe")

    nuevo = models.DocumentoRequisito(
        nombre_doc=doc.nombre_doc,
        es_obligatorio=doc.es_obligatorio
    )
    db.add(nuevo)
    db.commit()
    db.refresh(nuevo)
    return {"mensaje": "Documento creado", "id_doc": nuevo.id_doc, "nombre_doc": nuevo.nombre_doc}


@app.get("/api/v1/secretaria/documentos", tags=["Secretaría"])
def listar_documentos_requisito(db: Session = Depends(get_db)):
    return db.query(models.DocumentoRequisito).all()


@app.post("/api/v1/secretaria/expedientes", tags=["Secretaría"])
def registrar_o_actualizar_expediente(exp: schemas.ExpedienteCreate, db: Session = Depends(get_db)):
    alumno = db.query(models.Catequizando).filter(
        models.Catequizando.dni == exp.dni_catequizando
    ).first()
    if not alumno:
        raise HTTPException(status_code=404, detail="Catequizando no encontrado con ese DNI")

    documento = db.query(models.DocumentoRequisito).filter(
        models.DocumentoRequisito.id_doc == exp.id_doc
    ).first()
    if not documento:
        raise HTTPException(status_code=404, detail="Documento requisito no encontrado")

    # Si ya existe un registro para este alumno y documento, lo actualizamos; si no, lo creamos
    registro = db.query(models.Expediente).filter(
        models.Expediente.id_cateq == alumno.id_cateq,
        models.Expediente.id_doc == documento.id_doc
    ).first()

    fecha_recepcion = func.now() if exp.estado == "Entregado" else None

    if registro:
        registro.estado = exp.estado
        registro.id_usuario = exp.id_usuario
        registro.fecha_rec = fecha_recepcion
        accion = "actualizado"
    else:
        registro = models.Expediente(
            id_cateq=alumno.id_cateq,
            id_doc=documento.id_doc,
            id_usuario=exp.id_usuario,
            estado=exp.estado,
            fecha_rec=fecha_recepcion
        )
        db.add(registro)
        accion = "registrado"

    db.commit()
    db.refresh(registro)

    return {
        "mensaje": f"Expediente {accion} correctamente",
        "alumno": f"{alumno.nombres} {alumno.apellidos}",
        "documento": documento.nombre_doc,
        "estado": registro.estado,
        "fecha_rec": registro.fecha_rec
    }


@app.get("/api/v1/secretaria/expedientes/{dni}", tags=["Secretaría"])
def consultar_expediente_alumno(dni: str, db: Session = Depends(get_db)):
    alumno = db.query(models.Catequizando).filter(models.Catequizando.dni == dni).first()
    if not alumno:
        raise HTTPException(status_code=404, detail="Catequizando no encontrado")

    registros = (
        db.query(
            models.Expediente.id_exp,
            models.DocumentoRequisito.nombre_doc,
            models.DocumentoRequisito.es_obligatorio,
            models.Expediente.estado,
            models.Expediente.fecha_rec,
            models.Usuario.nombres.label("registrado_por")
        )
        .join(models.DocumentoRequisito, models.Expediente.id_doc == models.DocumentoRequisito.id_doc)
        .outerjoin(models.Usuario, models.Expediente.id_usuario == models.Usuario.id_usuario)
        .filter(models.Expediente.id_cateq == alumno.id_cateq)
        .all()
    )

    return {
        "dni": alumno.dni,
        "alumno": f"{alumno.nombres} {alumno.apellidos}",
        "documentos": [
            {
                "id_exp": r.id_exp,
                "documento": r.nombre_doc,
                "obligatorio": r.es_obligatorio,
                "estado": r.estado,
                "fecha_recepcion": r.fecha_rec,
                "registrado_por": r.registrado_por or "Sistema"
            }
            for r in registros
        ]
    }

# =========================================================
# MÓDULO DE DASHBOARD ADMINISTRATIVO (KPIs)
# =========================================================
@app.get("/api/v1/dashboard/resumen", tags=["Dashboard"])
def obtener_resumen_dashboard(db: Session = Depends(get_db)):
    total_alumnos = db.query(func.count(models.Catequizando.id_cateq)).scalar() or 0
    total_asistencias = db.query(func.count(models.Asistencia.id_asis)).scalar() or 0
    total_recaudado = db.query(func.sum(models.Pago.monto)).scalar() or 0

    # Desglose de pagos por método (Efectivo, Yape, Transferencia)
    pagos_por_metodo = (
        db.query(models.Pago.metodo_pago, func.sum(models.Pago.monto))
        .group_by(models.Pago.metodo_pago)
        .all()
    )

    # Desglose de expedientes por estado (Entregado, Pendiente, Observado)
    expedientes_por_estado = (
        db.query(models.Expediente.estado, func.count(models.Expediente.id_exp))
        .group_by(models.Expediente.estado)
        .all()
    )

    return {
        "kpis": {
            "total_catequizandos": total_alumnos,
            "total_asistencias_registradas": total_asistencias,
            "total_recaudado": float(total_recaudado),
        },
        "recaudacion_por_metodo": {
            metodo: float(monto) for metodo, monto in pagos_por_metodo
        },
        "estado_expedientes": {
            estado: cantidad for estado, cantidad in expedientes_por_estado
        }
    }

class LoginAdminRequest(BaseModel):
    dni: str
    password: str

@app.post("/api/v1/admin/login")
def login_admin(datos: LoginAdminRequest, db: Session = Depends(get_db)):
    usuario = db.query(models.Usuario).filter(
        models.Usuario.dni == datos.dni,
        models.Usuario.estado == True
    ).first()

    if not usuario:
        raise HTTPException(status_code=403, detail="Usuario no encontrado o inactivo.")

    es_valida = False
    if usuario.password_hash == datos.password:
        es_valida = True
    else:
        try:
            es_valida = security.verificar_password(datos.password, usuario.password_hash)
        except Exception:
            es_valida = False

    if not es_valida:
        raise HTTPException(status_code=401, detail="Contraseña incorrecta.")

    nombre_rol = usuario.rol.nombre_rol if usuario.rol else "Administrador"
    return {
        "mensaje": "Acceso concedido",
        "id_usuario": usuario.id_usuario,
        "usuario": usuario.nombres,
        "rol": nombre_rol
    }

@app.post("/api/v1/catequizandos", tags=["Gestión de Catequizandos"])
def crear_catequizando(datos: schemas.CatequizandoCreate, db: Session = Depends(get_db)):
    existe = db.query(models.Catequizando).filter(models.Catequizando.dni == datos.dni).first()
    if existe:
        raise HTTPException(status_code=400, detail="Ya existe un catequizando con ese DNI.")

    qr_generado = f"CAT-{datos.dni.strip()}"
    nuevo = models.Catequizando(
        dni=datos.dni.strip(),
        nombres=datos.nombres.strip(),
        apellidos=datos.apellidos.strip(),
        qr_token=qr_generado,
        colegio=datos.colegio,
        estado_bautismo=datos.estado_bautismo or "Bautizado",
        celular_joven=datos.celular_joven,
        celular_apoderado_1=datos.celular_apoderado_1,
        parentesco_apoderado_1=datos.parentesco_apoderado_1,
        celular_apoderado_2=datos.celular_apoderado_2,
        parentesco_apoderado_2=datos.parentesco_apoderado_2,
    )
    db.add(nuevo)
    db.commit()
    db.refresh(nuevo)

    return {
        "mensaje": "Catequizando registrado exitosamente",
        "id": nuevo.id_cateq,
        "qr_token": nuevo.qr_token
    }

@app.get("/api/v1/catequizandos")
def listar_catequizandos(db: Session = Depends(get_db)):
    jovenes = db.query(models.Catequizando).all()
    resultado = []
    for j in jovenes:
        cat = db.query(func.count(models.Asistencia.id_asis)).filter(
            models.Asistencia.id_cateq == j.id_cateq,
            models.Asistencia.tipo_asistencia == "Catequesis"
        ).scalar() or 0
        misas = db.query(func.count(models.Asistencia.id_asis)).filter(
            models.Asistencia.id_cateq == j.id_cateq,
            models.Asistencia.tipo_asistencia == "Misa"
        ).scalar() or 0
        acts = db.query(func.count(models.Asistencia.id_asis)).filter(
            models.Asistencia.id_cateq == j.id_cateq,
            models.Asistencia.tipo_asistencia == "Actividad Parroquial"
        ).scalar() or 0

        resultado.append({
            "ID": j.id_cateq,
            "DNI": j.dni,
            "Nombres": j.nombres,
            "Apellidos": j.apellidos,
            "QR Token": j.qr_token,
            "Colegio": j.colegio or "Sin asignar",
            "Grupo": j.grupo or "Sin asignar",
            "Salón": j.salon or "Sin asignar",
            "Bautismo": j.estado_bautismo or "Bautizado",
            "Celular Joven": j.celular_joven or "-",
            "Apoderado 1": f"{j.celular_apoderado_1} ({j.parentesco_apoderado_1 or 'Apoderado'})" if j.celular_apoderado_1 else "-",
            "Apoderado 2": f"{j.celular_apoderado_2} ({j.parentesco_apoderado_2 or 'Apoderado'})" if j.celular_apoderado_2 else "-",
            "Catequesis": cat,
            "Misas": misas,
            "Actividades": acts,
            "celular_joven_raw": j.celular_joven or "",
            "celular_apoderado_1_raw": j.celular_apoderado_1 or "",
            "parentesco_apoderado_1_raw": j.parentesco_apoderado_1 or "",
            "celular_apoderado_2_raw": j.celular_apoderado_2 or "",
            "parentesco_apoderado_2_raw": j.parentesco_apoderado_2 or "",
        })
    return resultado

@app.get("/api/v1/asistencias", tags=["Logística y Escáner QR"])
def listar_asistencias(tipo: str | None = None, db: Session = Depends(get_db)):
    query = (
        db.query(
            models.Asistencia.id_asis,
            models.Catequizando.dni,
            models.Catequizando.nombres,
            models.Catequizando.apellidos,
            models.Catequizando.colegio,
            models.Asistencia.tipo_asistencia,
            models.Asistencia.detalle_evento,
            models.Asistencia.estado,
            models.Asistencia.metodo_registro,
            models.Asistencia.fecha_hora,
            models.Usuario.nombres.label("registrado_por")
        )
        .join(models.Catequizando, models.Asistencia.id_cateq == models.Catequizando.id_cateq)
        .outerjoin(models.Usuario, models.Asistencia.id_usuario == models.Usuario.id_usuario)
    )
    if tipo:
        query = query.filter(models.Asistencia.tipo_asistencia == tipo)

    registros = query.order_by(models.Asistencia.fecha_hora.desc()).all()
    return [
        {
            "ID": r.id_asis,
            "DNI": r.dni,
            "Catequizando": f"{r.nombres} {r.apellidos}",
            "Colegio": r.colegio or "Sin asignar",
            "Tipo": r.tipo_asistencia,
            "Actividad": r.detalle_evento or "-",
            "Estado": r.estado or "Presente",
            "Método": r.metodo_registro or "QR",
            "Fecha y Hora": _a_hora_peru(r.fecha_hora),
            "Registrado por": r.registrado_por or "Sistema"
        }
        for r in registros
    ]

@app.post("/api/v1/admin/claves-temporales", tags=["Seguridad y Accesos"])
def crear_clave_temporal(datos: schemas.ClaveTemporalCreate, db: Session = Depends(get_db)):
    ahora = datetime.utcnow()
    if datos.duracion == "24h":
        expira = ahora + timedelta(hours=24)
    elif datos.duracion == "48h":
        expira = ahora + timedelta(hours=48)
    elif datos.duracion == "7d":
        expira = ahora + timedelta(days=7)
    elif datos.duracion == "indeterminado":
        expira = None
    else:
        raise HTTPException(status_code=400, detail="Duración no válida.")

    codigo_generado = f"TMP-{secrets.token_hex(3).upper()}"
    nueva_clave = models.ClaveTemporal(
        codigo=codigo_generado,
        fecha_expiracion=expira,
        activa=True
    )
    db.add(nueva_clave)
    db.commit()
    db.refresh(nueva_clave)

    return {
        "codigo": nueva_clave.codigo,
        "expira": nueva_clave.fecha_expiracion.isoformat() if nueva_clave.fecha_expiracion else "Indeterminado"
    }

@app.get("/api/v1/admin/claves-temporales", tags=["Seguridad y Accesos"])
def listar_claves_temporales(db: Session = Depends(get_db)):
    claves = db.query(models.ClaveTemporal).order_by(models.ClaveTemporal.id_clave.desc()).all()
    ahora = datetime.utcnow()
    resultado = []
    for c in claves:
        vigente = c.activa and (c.fecha_expiracion is None or c.fecha_expiracion > ahora)
        resultado.append({
            "ID": c.id_clave,
            "Código": c.codigo,
            "Expira (UTC)": c.fecha_expiracion.strftime("%Y-%m-%d %H:%M") if c.fecha_expiracion else "Indeterminado",
            "Estado": "Activa" if vigente else "Inactiva / Vencida"
        })
    return resultado

@app.put("/api/v1/admin/claves-temporales/{id_clave}/revocar", tags=["Seguridad y Accesos"])
def revocar_clave_temporal(id_clave: int, db: Session = Depends(get_db)):
    clave = db.query(models.ClaveTemporal).filter(models.ClaveTemporal.id_clave == id_clave).first()
    if not clave:
        raise HTTPException(status_code=404, detail="Clave no encontrada.")
    clave.activa = False
    db.commit()
    return {"mensaje": "Clave revocada correctamente."}

@app.post("/api/v1/admin/validar-clave-temporal", tags=["Seguridad y Accesos"])
def validar_clave_temporal(datos: schemas.ClaveTemporalValidar, db: Session = Depends(get_db)):
    clave = db.query(models.ClaveTemporal).filter(
        models.ClaveTemporal.codigo == datos.codigo.strip().upper(),
        models.ClaveTemporal.activa == True
    ).first()

    if not clave:
        raise HTTPException(status_code=401, detail="Clave inválida o revocada.")

    if clave.fecha_expiracion is not None and clave.fecha_expiracion < datetime.utcnow():
        raise HTTPException(status_code=401, detail="Esta clave temporal ya expiró.")

    return {"valida": True, "mensaje": "Acceso total desbloqueado para esta sesión."}

@app.post("/api/v1/admin/usuarios", tags=["Seguridad y Accesos"])
def crear_usuario(datos: schemas.UsuarioCreate, db: Session = Depends(get_db)):
    existe = db.query(models.Usuario).filter(models.Usuario.dni == datos.dni.strip()).first()
    if existe:
        raise HTTPException(status_code=400, detail="Ya existe un usuario registrado con ese DNI.")

    # Busca el rol en la tabla roles; si no existe (ej. Vocal), lo crea automáticamente
    rol_obj = db.query(models.Rol).filter(
        func.lower(models.Rol.nombre_rol) == datos.rol.strip().lower()
    ).first()

    if not rol_obj:
        rol_obj = models.Rol(nombre_rol=datos.rol.strip(), nivel_acceso=2)
        db.add(rol_obj)
        db.commit()
        db.refresh(rol_obj)

    password_encriptada = security.obtener_hash_password(datos.password.strip())

    nuevo_usuario = models.Usuario(
        id_rol=rol_obj.id_rol,
        dni=datos.dni.strip(),
        nombres=datos.nombre.strip(),
        password_hash=password_encriptada,
        estado=True
    )
    db.add(nuevo_usuario)
    db.commit()
    db.refresh(nuevo_usuario)
    return {
        "mensaje": "Usuario creado exitosamente",
        "dni": nuevo_usuario.dni,
        "rol": rol_obj.nombre_rol
    }

@app.get("/api/v1/admin/usuarios", tags=["Seguridad y Accesos"])
def listar_usuarios(db: Session = Depends(get_db)):
    usuarios = db.query(models.Usuario).all()
    return [
        {
            "ID": u.id_usuario,
            "DNI": u.dni,
            "Nombre": u.nombres,
            "Rol": u.rol.nombre_rol if u.rol else f"Rol {u.id_rol}"
        }
        for u in usuarios
    ]

@app.delete("/api/v1/admin/usuarios/{id_usuario}", tags=["Seguridad y Accesos"])
def eliminar_usuario(id_usuario: int, db: Session = Depends(get_db)):
    usuario = db.query(models.Usuario).filter(models.Usuario.id_usuario == id_usuario).first()
    if not usuario:
        raise HTTPException(status_code=404, detail="Usuario no encontrado.")
    db.delete(usuario)
    db.commit()
    return {"mensaje": "Usuario eliminado correctamente."}

# =========================================================
# EDICIÓN Y ELIMINACIÓN DE REGISTROS (CRUD COMPLETO)
# =========================================================
@app.put("/api/v1/catequizandos/{id_cateq}", tags=["Gestión de Catequizandos"])
def editar_catequizando(id_cateq: int, datos: schemas.CatequizandoUpdate, db: Session = Depends(get_db)):
    alumno = db.query(models.Catequizando).filter(models.Catequizando.id_cateq == id_cateq).first()
    if not alumno:
        raise HTTPException(status_code=404, detail="Catequizando no encontrado.")

    dni_limpio = datos.dni.strip()
    # Verificar que el nuevo DNI no pertenezca a otro alumno
    duplicado = db.query(models.Catequizando).filter(
        models.Catequizando.dni == dni_limpio,
        models.Catequizando.id_cateq != id_cateq
    ).first()
    if duplicado:
        raise HTTPException(status_code=400, detail="Ese DNI ya pertenece a otro catequizando.")

    alumno.dni = dni_limpio
    alumno.nombres = datos.nombres.strip()
    alumno.apellidos = datos.apellidos.strip()
    alumno.qr_token = f"CAT-{dni_limpio}"
    alumno.colegio = datos.colegio
    alumno.estado_bautismo = datos.estado_bautismo or "Bautizado"
    alumno.celular_joven = datos.celular_joven
    alumno.celular_apoderado_1 = datos.celular_apoderado_1
    alumno.parentesco_apoderado_1 = datos.parentesco_apoderado_1
    alumno.celular_apoderado_2 = datos.celular_apoderado_2
    alumno.parentesco_apoderado_2 = datos.parentesco_apoderado_2

    db.commit()
    db.refresh(alumno)
    return {"mensaje": "Catequizando actualizado correctamente", "qr_token": alumno.qr_token}

@app.delete("/api/v1/catequizandos/{id_cateq}", tags=["Gestión de Catequizandos"])
def eliminar_catequizando(id_cateq: int, db: Session = Depends(get_db)):
    alumno = db.query(models.Catequizando).filter(models.Catequizando.id_cateq == id_cateq).first()
    if not alumno:
        raise HTTPException(status_code=404, detail="Catequizando no encontrado.")
    try:
        db.delete(alumno)
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=400,
            detail="No se puede eliminar porque tiene pagos registrados. Anula sus pagos primero."
        )
    return {"mensaje": "Catequizando eliminado correctamente."}


@app.delete("/api/v1/asistencias/{id_asis}", tags=["Logística y Escáner QR"])
def eliminar_asistencia(id_asis: int, db: Session = Depends(get_db)):
    asis = db.query(models.Asistencia).filter(models.Asistencia.id_asis == id_asis).first()
    if not asis:
        raise HTTPException(status_code=404, detail="Asistencia no encontrada.")
    db.delete(asis)
    db.commit()
    return {"mensaje": "Asistencia eliminada correctamente."}


@app.delete("/api/v1/tesoreria/pagos/{id_pago}", tags=["Tesorería"])
def eliminar_pago(id_pago: int, db: Session = Depends(get_db)):
    pago = db.query(models.Pago).filter(models.Pago.id_pago == id_pago).first()
    if not pago:
        raise HTTPException(status_code=404, detail="Pago no encontrado.")
    db.delete(pago)
    db.commit()
    return {"mensaje": "Pago anulado y eliminado correctamente."}

@app.delete("/api/v1/secretaria/expedientes/{id_exp}", tags=["Secretaría"])
def eliminar_expediente(id_exp: int, db: Session = Depends(get_db)):
    exp = db.query(models.Expediente).filter(models.Expediente.id_exp == id_exp).first()
    if not exp:
        raise HTTPException(status_code=404, detail="Registro de expediente no encontrado.")
    db.delete(exp)
    db.commit()
    return {"mensaje": "Registro eliminado correctamente."}

@app.delete("/api/v1/secretaria/documentos/{id_doc}", tags=["Secretaría"])
def eliminar_documento_requisito(id_doc: int, db: Session = Depends(get_db)):
    doc = db.query(models.DocumentoRequisito).filter(models.DocumentoRequisito.id_doc == id_doc).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Documento no encontrado.")
    try:
        db.delete(doc)
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=400,
            detail="No se puede eliminar porque ya hay catequizandos con este documento registrado."
        )
    return {"mensaje": "Documento eliminado del catálogo."}

# =========================================================
# PANEL DE ALERTAS (DEUDORES, DOCUMENTOS Y BAJA ASISTENCIA)
# =========================================================
@app.get("/api/v1/dashboard/alertas", tags=["Dashboard"])
def obtener_alertas_dashboard(db: Session = Depends(get_db)):
    jovenes = db.query(models.Catequizando).all()
    conceptos = db.query(models.ConceptoPago).all()
    docs_obligatorios = db.query(models.DocumentoRequisito).filter(
        models.DocumentoRequisito.es_obligatorio == True
    ).all()

    # 1. Pagos agrupados por (alumno, concepto)
    pagos_agg = (
        db.query(
            models.Pago.id_cateq,
            models.Pago.id_concepto,
            func.sum(models.Pago.monto)
        )
        .group_by(models.Pago.id_cateq, models.Pago.id_concepto)
        .all()
    )
    mapa_pagos = {(r[0], r[1]): float(r[2] or 0) for r in pagos_agg}

    # 2. Expedientes registrados por (alumno, documento)
    expedientes = db.query(
        models.Expediente.id_cateq,
        models.Expediente.id_doc,
        models.Expediente.estado
    ).all()
    mapa_exp = {(r[0], r[1]): r[2] for r in expedientes}

    # 3. Asistencias agrupadas por (alumno, tipo)
    asis_agg = (
        db.query(
            models.Asistencia.id_cateq,
            models.Asistencia.tipo_asistencia,
            func.count(models.Asistencia.id_asis)
        )
        .group_by(models.Asistencia.id_cateq, models.Asistencia.tipo_asistencia)
        .all()
    )
    mapa_asis = {(r[0], r[1]): int(r[2] or 0) for r in asis_agg}

    deudores = []
    docs_pendientes = []
    asistencias_resumen = []

    for j in jovenes:
        nombre_completo = f"{j.nombres} {j.apellidos}"

        # Evaluar deudas por concepto
        for c in conceptos:
            base = float(c.monto_base)
            pagado = mapa_pagos.get((j.id_cateq, c.id_concepto), 0.0)
            if pagado < base:
                deudores.append({
                    "DNI": j.dni,
                    "Catequizando": nombre_completo,
                    "Colegio": j.colegio or "Sin asignar",
                    "Grupo": j.grupo or "Sin asignar",
                    "Concepto": c.nombre_conc,
                    "Monto Base (S/)": base,
                    "Pagado (S/)": pagado,
                    "Debe (S/)": round(base - pagado, 2)
                })

        # Evaluar documentos obligatorios faltantes u observados
        for d in docs_obligatorios:
            estado = mapa_exp.get((j.id_cateq, d.id_doc), "Sin entregar")
            if estado != "Entregado":
                docs_pendientes.append({
                    "DNI": j.dni,
                    "Catequizando": nombre_completo,
                    "Colegio": j.colegio or "Sin asignar",
                    "Grupo": j.grupo or "Sin asignar",
                    "Documento": d.nombre_doc,
                    "Estado": estado
                })

        # Resumen de asistencias por alumno
        cat = mapa_asis.get((j.id_cateq, "Catequesis"), 0)
        misas = mapa_asis.get((j.id_cateq, "Misa"), 0)
        acts = mapa_asis.get((j.id_cateq, "Actividad Parroquial"), 0)
        asistencias_resumen.append({
            "DNI": j.dni,
            "Catequizando": nombre_completo,
            "Colegio": j.colegio or "Sin asignar",
            "Grupo": j.grupo or "Sin asignar",
            "Catequesis": cat,
            "Misas": misas,
            "Actividades": acts,
            "Total": cat + misas + acts
        })

    return {
        "deudores": deudores,
        "documentos_pendientes": docs_pendientes,
        "asistencias_resumen": asistencias_resumen
    }

# =========================================================
# RESPALDO COMPLETO (BACKUP) Y RESTAURACIÓN (SOLO ADMIN)
# =========================================================
@app.get("/api/v1/admin/backup/exportar", tags=["Seguridad y Accesos"])
def exportar_backup_completo(db: Session = Depends(get_db)):
    ahora_utc = datetime.utcnow()
    return {
        "fecha_backup": ahora_utc.isoformat(),
        "fecha_backup_peru": _a_hora_peru(ahora_utc),
        "roles": [
            {"id_rol": r.id_rol, "nombre_rol": r.nombre_rol, "nivel_acceso": r.nivel_acceso}
            for r in db.query(models.Rol).all()
        ],
        "usuarios": [
            {
                "id_usuario": u.id_usuario,
                "id_rol": u.id_rol,
                "dni": u.dni,
                "nombres": u.nombres,
                "password_hash": u.password_hash,
                "estado": u.estado
            }
            for u in db.query(models.Usuario).all()
        ],
        "catequizandos": [
            {
                "id_cateq": c.id_cateq,
                "dni": c.dni,
                "nombres": c.nombres,
                "apellidos": c.apellidos,
                "qr_token": c.qr_token,
                "colegio": c.colegio,
                "grupo": c.grupo,
                "salon": c.salon,
                "estado_bautismo": c.estado_bautismo,
                "celular_joven": c.celular_joven,
                "celular_apoderado_1": c.celular_apoderado_1,
                "parentesco_apoderado_1": c.parentesco_apoderado_1,
                "celular_apoderado_2": c.celular_apoderado_2,
                "parentesco_apoderado_2": c.parentesco_apoderado_2,
            }
            for c in db.query(models.Catequizando).all()
        ],
        "conceptos_pago": [
            {
                "id_concepto": cp.id_concepto,
                "nombre_conc": cp.nombre_conc,
                "monto_base": float(cp.monto_base)
            }
            for cp in db.query(models.ConceptoPago).all()
        ],
        "documentos_requisito": [
            {
                "id_doc": d.id_doc,
                "nombre_doc": d.nombre_doc,
                "es_obligatorio": d.es_obligatorio
            }
            for d in db.query(models.DocumentoRequisito).all()
        ],
        "asistencias": [
            {
                "id_asis": a.id_asis,
                "id_cateq": a.id_cateq,
                "id_usuario": a.id_usuario,
                "fecha_hora": a.fecha_hora.isoformat() if a.fecha_hora else None,
                "estado": a.estado,
                "tipo_asistencia": a.tipo_asistencia,
                "detalle_evento": a.detalle_evento,
                "metodo_registro": a.metodo_registro or "QR",
            }
            for a in db.query(models.Asistencia).all()
        ],
        "pagos": [
            {
                "id_pago": p.id_pago,
                "id_cateq": p.id_cateq,
                "id_usuario": p.id_usuario,
                "id_concepto": p.id_concepto,
                "monto": float(p.monto),
                "codigo_boleta": p.codigo_boleta,
                "metodo_pago": p.metodo_pago,
                "fecha_hora": p.fecha_hora.isoformat() if p.fecha_hora else None
            }
            for p in db.query(models.Pago).all()
        ],
        "expedientes": [
            {
                "id_exp": e.id_exp,
                "id_cateq": e.id_cateq,
                "id_doc": e.id_doc,
                "id_usuario": e.id_usuario,
                "estado": e.estado,
                "fecha_rec": e.fecha_rec.isoformat() if e.fecha_rec else None
            }
            for e in db.query(models.Expediente).all()
        ]
    }


@app.post("/api/v1/admin/backup/restaurar", tags=["Seguridad y Accesos"])
def restaurar_backup_completo(datos: Dict[str, Any], db: Session = Depends(get_db)):
    resumen = {}

    def _parse_fecha(valor):
        if not valor:
            return None
        try:
            dt = datetime.fromisoformat(str(valor).replace("Z", "+00:00"))
            return dt.astimezone(timezone.utc).replace(tzinfo=None) if dt.tzinfo else dt
        except Exception:
            return None

    try:
        # 1. Roles
        c_roles = 0
        for r in datos.get("roles", []):
            if not db.query(models.Rol).filter(models.Rol.id_rol == r["id_rol"]).first():
                db.add(models.Rol(
                    id_rol=r["id_rol"],
                    nombre_rol=r["nombre_rol"],
                    nivel_acceso=r.get("nivel_acceso", 2),
                ))
                c_roles += 1
        db.flush()
        resumen["roles"] = c_roles

        # 2. Usuarios
        c_usr = 0
        for u in datos.get("usuarios", []):
            existe = db.query(models.Usuario).filter(
                (models.Usuario.id_usuario == u["id_usuario"]) | (models.Usuario.dni == u["dni"])
            ).first()
            if not existe:
                db.add(models.Usuario(
                    id_usuario=u["id_usuario"],
                    id_rol=u["id_rol"],
                    dni=u["dni"],
                    nombres=u["nombres"],
                    password_hash=u["password_hash"],
                    estado=u.get("estado", True),
                ))
                c_usr += 1
        db.flush()
        resumen["usuarios"] = c_usr

        # 3. Catequizandos (con todos los campos nuevos)
        c_cat = 0
        for c in datos.get("catequizandos", []):
            existe = db.query(models.Catequizando).filter(
                (models.Catequizando.id_cateq == c["id_cateq"]) | (models.Catequizando.dni == c["dni"])
            ).first()
            if not existe:
                db.add(models.Catequizando(
                    id_cateq=c["id_cateq"],
                    dni=c["dni"],
                    nombres=c["nombres"],
                    apellidos=c["apellidos"],
                    qr_token=c.get("qr_token") or f"CAT-{c['dni']}",
                    colegio=c.get("colegio"),
                    grupo=c.get("grupo"),
                    salon=c.get("salon"),
                    estado_bautismo=c.get("estado_bautismo") or "Bautizado",
                    celular_joven=c.get("celular_joven"),
                    celular_apoderado_1=c.get("celular_apoderado_1"),
                    parentesco_apoderado_1=c.get("parentesco_apoderado_1"),
                    celular_apoderado_2=c.get("celular_apoderado_2"),
                    parentesco_apoderado_2=c.get("parentesco_apoderado_2"),
                ))
                c_cat += 1
        db.flush()
        resumen["catequizandos"] = c_cat

        # 4. Conceptos de Pago
        c_conc = 0
        for cp in datos.get("conceptos_pago", []):
            existe = db.query(models.ConceptoPago).filter(
                (models.ConceptoPago.id_concepto == cp["id_concepto"]) |
                (models.ConceptoPago.nombre_conc == cp["nombre_conc"])
            ).first()
            if not existe:
                db.add(models.ConceptoPago(
                    id_concepto=cp["id_concepto"],
                    nombre_conc=cp["nombre_conc"],
                    monto_base=cp["monto_base"],
                ))
                c_conc += 1
        db.flush()
        resumen["conceptos_pago"] = c_conc

        # 5. Documentos Requisito
        c_doc = 0
        for d in datos.get("documentos_requisito", []):
            existe = db.query(models.DocumentoRequisito).filter(
                (models.DocumentoRequisito.id_doc == d["id_doc"]) |
                (models.DocumentoRequisito.nombre_doc == d["nombre_doc"])
            ).first()
            if not existe:
                db.add(models.DocumentoRequisito(
                    id_doc=d["id_doc"],
                    nombre_doc=d["nombre_doc"],
                    es_obligatorio=d.get("es_obligatorio", True),
                ))
                c_doc += 1
        db.flush()
        resumen["documentos_requisito"] = c_doc

        # 6. Asistencias (incluye metodo_registro)
        c_asis = 0
        for a in datos.get("asistencias", []):
            if not db.query(models.Asistencia).filter(models.Asistencia.id_asis == a["id_asis"]).first():
                db.add(models.Asistencia(
                    id_asis=a["id_asis"],
                    id_cateq=a["id_cateq"],
                    id_usuario=a.get("id_usuario"),
                    fecha_hora=_parse_fecha(a.get("fecha_hora")),
                    estado=a.get("estado") or "Presente",
                    tipo_asistencia=a["tipo_asistencia"],
                    detalle_evento=a.get("detalle_evento"),
                    metodo_registro=a.get("metodo_registro") or "QR",
                ))
                c_asis += 1
        db.flush()
        resumen["asistencias"] = c_asis

        # 7. Pagos (incluye codigo_boleta)
        c_pag = 0
        for p in datos.get("pagos", []):
            if not db.query(models.Pago).filter(models.Pago.id_pago == p["id_pago"]).first():
                db.add(models.Pago(
                    id_pago=p["id_pago"],
                    id_cateq=p["id_cateq"],
                    id_usuario=p.get("id_usuario"),
                    id_concepto=p["id_concepto"],
                    monto=p["monto"],
                    codigo_boleta=p.get("codigo_boleta"),
                    metodo_pago=p["metodo_pago"],
                    fecha_hora=_parse_fecha(p.get("fecha_hora")),
                ))
                c_pag += 1
        db.flush()
        resumen["pagos"] = c_pag

        # 8. Expedientes
        c_exp = 0
        for e in datos.get("expedientes", []):
            if not db.query(models.Expediente).filter(models.Expediente.id_exp == e["id_exp"]).first():
                db.add(models.Expediente(
                    id_exp=e["id_exp"],
                    id_cateq=e["id_cateq"],
                    id_doc=e["id_doc"],
                    id_usuario=e.get("id_usuario"),
                    estado=e["estado"],
                    fecha_rec=_parse_fecha(e.get("fecha_rec")),
                ))
                c_exp += 1
        db.commit()
        resumen["expedientes"] = c_exp

        return {"mensaje": "Restauración completada exitosamente", "registros_restaurados": resumen}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Error al restaurar backup: {str(e)}")


@app.post("/api/v1/admin/importar/catequizandos", tags=["Gestión de Catequizandos"])
def importar_catequizandos_masivo(lista: List[schemas.CatequizandoCreate], db: Session = Depends(get_db)):
    creados = 0
    omitidos = 0
    for item in lista:
        dni_limpio = item.dni.strip()
        if len(dni_limpio) != 8:
            omitidos += 1
            continue
        existe = db.query(models.Catequizando).filter(models.Catequizando.dni == dni_limpio).first()
        if existe:
            omitidos += 1
            continue
        nuevo = models.Catequizando(
            dni=dni_limpio,
            nombres=item.nombres.strip(),
            apellidos=item.apellidos.strip(),
            qr_token=f"CAT-{dni_limpio}"
        )
        db.add(nuevo)
        creados += 1
    db.commit()
    return {"mensaje": "Importación finalizada", "creados": creados, "omitidos": omitidos}

# =========================================================
# SERVICIOS MÓVILES APK (HEALTH, CÓDIGOS 4H, LOGIN Y BÚSQUEDA)
# =========================================================
@app.get("/api/v1/health", tags=["Móvil APK"])
def health_check():
    return {"status": "ok", "hora_utc": datetime.utcnow().isoformat()}


@app.post("/api/v1/admin/codigos-servicio", tags=["Móvil APK"])
def crear_codigo_servicio(datos: schemas.CodigoServicioCreate, db: Session = Depends(get_db)):
    horas = max(1, min(datos.duracion_horas, 4))  # Límite estricto: máximo 4 horas
    codigo_gen = f"SRV-{secrets.token_hex(3).upper()}"
    expira = datetime.utcnow() + timedelta(hours=horas)

    nuevo = models.CodigoServicio(
        codigo=codigo_gen,
        tipo_asistencia=datos.tipo_asistencia,
        detalle_evento=datos.detalle_evento or None,
        colegio_permitido=datos.colegio_permitido or "Todos",
        hora_limite_tardanza=datos.hora_limite_tardanza or None,
        expira_en=expira,
        activo=True
    )
    db.add(nuevo)
    db.commit()
    db.refresh(nuevo)

    expira_peru = expira.replace(tzinfo=timezone.utc).astimezone(PERU_TZ)
    return {
        "id_codigo": nuevo.id_codigo,
        "codigo": nuevo.codigo,
        "evento": f"{nuevo.tipo_asistencia} ({nuevo.detalle_evento})" if nuevo.detalle_evento else nuevo.tipo_asistencia,
        "hora_limite_tardanza": nuevo.hora_limite_tardanza or "Sin límite",
        "expira_peru": expira_peru.strftime("%d/%m/%Y %H:%M")
    }


@app.get("/api/v1/admin/codigos-servicio", tags=["Móvil APK"])
def listar_codigos_servicio(db: Session = Depends(get_db)):
    ahora = datetime.utcnow()
    codigos = db.query(models.CodigoServicio).order_by(models.CodigoServicio.id_codigo.desc()).limit(30).all()
    resultado = []
    for c in codigos:
        if not c.activo:
            estado = "Revocado"
        elif ahora > c.expira_en:
            estado = "Expirado"
        else:
            estado = "Activo"
        exp_peru = c.expira_en.replace(tzinfo=timezone.utc).astimezone(PERU_TZ)
        resultado.append({
            "ID": c.id_codigo,
            "Código": c.codigo,
            "Evento": f"{c.tipo_asistencia} ({c.detalle_evento})" if c.detalle_evento else c.tipo_asistencia,
            "Colegio": c.colegio_permitido or "Todos",
            "Tardanza desde": c.hora_limite_tardanza or "-",
            "Expira (Perú)": exp_peru.strftime("%d/%m/%Y %H:%M"),
            "Estado": estado
        })
    return resultado


@app.put("/api/v1/admin/codigos-servicio/{id_codigo}/revocar", tags=["Móvil APK"])
def revocar_codigo_servicio(id_codigo: int, db: Session = Depends(get_db)):
    c = db.query(models.CodigoServicio).filter(models.CodigoServicio.id_codigo == id_codigo).first()
    if not c:
        raise HTTPException(status_code=404, detail="Código no encontrado.")
    c.activo = False
    db.commit()
    return {"mensaje": "Código de servicio revocado en vivo."}


@app.post("/api/v1/movil/login", tags=["Móvil APK"])
def login_movil_con_codigo(req: schemas.LoginMovilRequest, db: Session = Depends(get_db)):
    dni_limpio = req.dni.strip()
    usuario = db.query(models.Usuario).filter(models.Usuario.dni == dni_limpio).first()

    if not usuario or not usuario.estado:
        raise HTTPException(status_code=401, detail="DNI no registrado o usuario inactivo.")

    # Verificación de contraseña (compatible con hash bcrypt o texto plano)
    pass_ok = False
    if usuario.password_hash == req.password:
        pass_ok = True
    else:
        try:
            pass_ok = security.verificar_password(req.password, usuario.password_hash)
        except Exception:
            pass_ok = False

    if not pass_ok:
        raise HTTPException(status_code=401, detail="Contraseña incorrecta.")

    if not pass_ok:
        raise HTTPException(status_code=401, detail="Contraseña incorrecta.")

    nombre_rol = usuario.rol.nombre_rol if usuario.rol else "Usuario"
    es_admin = nombre_rol.strip().lower() in ["administrador", "admin"]
    codigo_limpio = (req.codigo_servicio or "").strip().upper()

    # Si es Administrador y NO ingresó código de servicio, entra directo
    if es_admin and not codigo_limpio:
        return {
            "mensaje": "Turno de Administrador iniciado",
            "id_usuario": usuario.id_usuario,
            "usuario": usuario.nombres,
            "rol": nombre_rol,
            "codigo_servicio": "ADMIN-LIBRE",
            "tipo_asistencia": "Catequesis",
            "colegio_permitido": "Todos",
            "detalle_evento": None,
            "hora_limite_tardanza": None,
            "segundos_restantes": 14400
        }

    # Si NO es admin (o si es admin pero sí escribió un código), validar el código
    if not codigo_limpio:
        raise HTTPException(status_code=403, detail="Debes ingresar el Código de Servicio del día.")

    cod = db.query(models.CodigoServicio).filter(
        models.CodigoServicio.codigo == codigo_limpio
    ).first()

    if not cod or not cod.activo:
        raise HTTPException(status_code=403, detail="Código de servicio inválido o revocado.")

    ahora = datetime.utcnow()
    if ahora > cod.expira_en:
        raise HTTPException(status_code=403, detail="El código de servicio ya expiró.")

    segundos_restantes = int((cod.expira_en - ahora).total_seconds())

    return {
        "mensaje": "Turno iniciado",
        "id_usuario": usuario.id_usuario,
        "usuario": usuario.nombres,
        "rol": nombre_rol,
        "codigo_servicio": cod.codigo,
        "tipo_asistencia": cod.tipo_asistencia,
        "colegio_permitido": cod.colegio_permitido or "Todos",
        "detalle_evento": cod.detalle_evento,
        "hora_limite_tardanza": cod.hora_limite_tardanza,
        "segundos_restantes": segundos_restantes
    }


@app.get("/api/v1/movil/catequizandos/buscar", tags=["Móvil APK"])
def buscar_catequizando_movil(q: str, db: Session = Depends(get_db)):
    termino = f"%{q.strip()}%"
    resultados = db.query(models.Catequizando).filter(
        (models.Catequizando.dni.ilike(termino)) |
        (models.Catequizando.nombres.ilike(termino)) |
        (models.Catequizando.apellidos.ilike(termino))
    ).limit(15).all()

    return [
        {
            "dni": c.dni,
            "nombres": c.nombres,
            "apellidos": c.apellidos,
            "nombre_completo": f"{c.nombres} {c.apellidos}"
        }
        for c in resultados
    ]

# =========================================================
# VISUALIZADOR GENERAL (FICHA INTEGRAL DEL CATEQUIZANDO)
# =========================================================
@app.get("/api/v1/catequizandos/{id_cateq}/ficha-completa", tags=["Gestión de Catequizandos"])
def obtener_ficha_completa(id_cateq: int, db: Session = Depends(get_db)):
    alumno = db.query(models.Catequizando).filter(models.Catequizando.id_cateq == id_cateq).first()
    if not alumno:
        raise HTTPException(status_code=404, detail="Catequizando no encontrado.")

    # 1. Asistencias del catequizando
    asistencias_db = (
        db.query(
            models.Asistencia.tipo_asistencia,
            models.Asistencia.detalle_evento,
            models.Asistencia.estado,
            models.Asistencia.metodo_registro,
            models.Asistencia.fecha_hora,
            models.Usuario.nombres.label("registrado_por")
        )
        .outerjoin(models.Usuario, models.Asistencia.id_usuario == models.Usuario.id_usuario)
        .filter(models.Asistencia.id_cateq == id_cateq)
        .order_by(models.Asistencia.fecha_hora.asc())
        .all()
    )

    asistencias_lista = [
        {
            "tipo": a.tipo_asistencia,
            "detalle": a.detalle_evento or "-",
            "estado": a.estado or "Presente",
            "metodo": a.metodo_registro or "QR",
            "fecha_hora": _a_hora_peru(a.fecha_hora),
            "registrado_por": a.registrado_por or "Sistema"
        }
        for a in asistencias_db
    ]

    # 2. Pagos (resumen por concepto + historial detallado)
    conceptos = db.query(models.ConceptoPago).all()
    pagos_db = (
        db.query(
            models.Pago.id_pago,
            models.Pago.id_concepto,
            models.ConceptoPago.nombre_conc,
            models.Pago.codigo_boleta,
            models.Pago.monto,
            models.Pago.metodo_pago,
            models.Pago.fecha_hora,
            models.Usuario.nombres.label("registrado_por")
        )
        .join(models.ConceptoPago, models.Pago.id_concepto == models.ConceptoPago.id_concepto)
        .outerjoin(models.Usuario, models.Pago.id_usuario == models.Usuario.id_usuario)
        .filter(models.Pago.id_cateq == id_cateq)
        .order_by(models.Pago.fecha_hora.desc())
        .all()
    )

    pagos_por_concepto = {}
    for p in pagos_db:
        pagos_por_concepto[p.id_concepto] = pagos_por_concepto.get(p.id_concepto, 0.0) + float(p.monto)

    resumen_pagos = []
    for c in conceptos:
        base = float(c.monto_base)
        pagado = pagos_por_concepto.get(c.id_concepto, 0.0)
        debe = max(0.0, round(base - pagado, 2))
        estado_p = "Pagado" if debe == 0 else ("Parcial" if pagado > 0 else "Pendiente")
        resumen_pagos.append({
            "Concepto": c.nombre_conc,
            "Monto Base (S/)": base,
            "Pagado (S/)": pagado,
            "Debe (S/)": debe,
            "Estado": estado_p
        })

    historial_pagos = [
        {
            "ID": p.id_pago,
            "Concepto": p.nombre_conc,
            "Boleta": p.codigo_boleta or "-",
            "Monto (S/)": float(p.monto),
            "Método": p.metodo_pago,
            "Fecha y Hora": _a_hora_peru(p.fecha_hora),
            "Registrado por": p.registrado_por or "Sistema"
        }
        for p in pagos_db
    ]

    # 3. Documentos (checklist completo contra el catálogo)
    docs_catalogo = db.query(models.DocumentoRequisito).all()
    exp_db = (
        db.query(
            models.Expediente.id_doc,
            models.Expediente.estado,
            models.Expediente.fecha_rec,
            models.Usuario.nombres.label("registrado_por")
        )
        .outerjoin(models.Usuario, models.Expediente.id_usuario == models.Usuario.id_usuario)
        .filter(models.Expediente.id_cateq == id_cateq)
        .all()
    )
    mapa_exp = {e.id_doc: e for e in exp_db}

    documentos_lista = []
    for d in docs_catalogo:
        reg = mapa_exp.get(d.id_doc)
        documentos_lista.append({
            "Documento": d.nombre_doc,
            "Obligatorio": "Sí" if d.es_obligatorio else "No",
            "Estado": reg.estado if reg else "Sin entregar",
            "Fecha Recepción": reg.fecha_rec.strftime("%d/%m/%Y %H:%M") if (reg and reg.fecha_rec) else "-",
            "Registrado por": (reg.registrado_por or "Sistema") if reg else "-"
        })

    return {
        "datos": {
            "ID": alumno.id_cateq,
            "DNI": alumno.dni,
            "Nombres": alumno.nombres,
            "Apellidos": alumno.apellidos,
            "QR Token": alumno.qr_token,
            "Colegio": alumno.colegio or "Sin asignar",
            "Grupo": alumno.grupo or "Sin asignar",
            "Salón": alumno.salon or "Sin asignar",
            "Bautismo": alumno.estado_bautismo or "Bautizado",
            "Celular Joven": alumno.celular_joven or "-",
            "Apoderado 1": f"{alumno.celular_apoderado_1} ({alumno.parentesco_apoderado_1 or 'Apoderado'})" if alumno.celular_apoderado_1 else "-",
            "Apoderado 2": f"{alumno.celular_apoderado_2} ({alumno.parentesco_apoderado_2 or 'Apoderado'})" if alumno.celular_apoderado_2 else "-",
        },
        "asistencias": asistencias_lista,
        "pagos": {
            "resumen": resumen_pagos,
            "historial": historial_pagos
        },
        "documentos": documentos_lista
    }

@app.put("/api/v1/admin/catequizandos/asignar-masivo", tags=["Gestión de Catequizandos"])
def asignar_grupos_y_salones_masivo(
    items: List[schemas.AsignacionMasivaItem],
    db: Session = Depends(get_db)
):
    actualizados = 0
    for item in items:
        alumno = db.query(models.Catequizando).filter(
            models.Catequizando.id_cateq == item.id_cateq
        ).first()
        if alumno:
            if item.grupo is not None:
                alumno.grupo = item.grupo if item.grupo != "Sin asignar" else None
            if item.salon is not None:
                alumno.salon = item.salon if item.salon != "Sin asignar" else None
            actualizados += 1
    db.commit()
    return {"mensaje": f"Se actualizaron {actualizados} catequizandos correctamente.", "actualizados": actualizados}