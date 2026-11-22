from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm, OAuth2PasswordBearer
from sqlalchemy.orm import Session
from sqlalchemy import func
from jose import jwt, JWTError
import models
import security
import schemas
from database import engine, get_db
from pydantic import BaseModel


# Sincroniza y crea las tablas en MySQL si no existen
models.Base.metadata.create_all(bind=engine)

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
@app.post("/api/v1/asistencia", tags=["Logística y Escáner QR"])
def registrar_asistencia(request: schemas.AsistenciaQRRequest, db: Session = Depends(get_db)):
    alumno = db.query(models.Catequizando).filter(models.Catequizando.qr_token == request.qr_token).first()

    if not alumno:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Código QR inválido o alumno no encontrado"
        )

    nueva_asistencia = models.Asistencia(
        id_cateq=alumno.id_cateq,
        id_usuario=1,
        tipo_asistencia=request.tipo_asistencia,
        detalle_evento=request.detalle_evento
    )
    db.add(nueva_asistencia)
    db.commit()
    db.refresh(nueva_asistencia)

    return {
        "mensaje": "Asistencia registrada correctamente",
        "alumno": f"{alumno.nombres} {alumno.apellidos}",
        "dni": alumno.dni,
        "hora_registro": nueva_asistencia.fecha_hora
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

    monto_final = pago.monto if pago.monto is not None else concepto.monto_base

    nuevo_pago = models.Pago(
        id_cateq=alumno.id_cateq,
        id_usuario=pago.id_usuario,
        id_concepto=concepto.id_concepto,
        monto=monto_final,
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
            models.ConceptoPago.nombre_conc,
            models.Pago.monto,
            models.Pago.metodo_pago,
            models.Pago.fecha_hora
        )
        .join(models.Catequizando, models.Pago.id_cateq == models.Catequizando.id_cateq)
        .join(models.ConceptoPago, models.Pago.id_concepto == models.ConceptoPago.id_concepto)
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
                "concepto": r.nombre_conc,
                "monto": float(r.monto),
                "metodo_pago": r.metodo_pago,
                "fecha_hora": r.fecha_hora
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
            models.DocumentoRequisito.nombre_doc,
            models.DocumentoRequisito.es_obligatorio,
            models.Expediente.estado,
            models.Expediente.fecha_rec
        )
        .join(models.DocumentoRequisito, models.Expediente.id_doc == models.DocumentoRequisito.id_doc)
        .filter(models.Expediente.id_cateq == alumno.id_cateq)
        .all()
    )

    return {
        "dni": alumno.dni,
        "alumno": f"{alumno.nombres} {alumno.apellidos}",
        "documentos": [
            {
                "documento": r.nombre_doc,
                "obligatorio": r.es_obligatorio,
                "estado": r.estado,
                "fecha_recepcion": r.fecha_rec
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
    # Buscamos al usuario por DNI y que esté activo
    usuario = db.query(models.Usuario).filter(
        models.Usuario.dni == datos.dni,
        models.Usuario.estado == True
    ).first()

    # Roles permitidos: 1 (Administrador/Coordinador), 2 (Secretario), 3 (Tesorero)
    if not usuario or usuario.id_rol not in [1, 2, 3]:
        raise HTTPException(status_code=403, detail="Acceso denegado: solo personal administrativo.")

    # Verificación de contraseña (acepta texto plano de prueba y contraseñas encriptadas)
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

    roles_nombre = {1: "Coordinador/Admin", 2: "Secretario", 3: "Tesorero"}
    return {
        "mensaje": "Acceso concedido",
        "usuario": usuario.nombres,
        "rol": roles_nombre.get(usuario.id_rol, "Administrativo")
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
        qr_token=qr_generado
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
            "Catequesis": cat,
            "Misas": misas,
            "Actividades": acts
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
            models.Asistencia.tipo_asistencia,
            models.Asistencia.detalle_evento,
            models.Asistencia.fecha_hora
        )
        .join(models.Catequizando, models.Asistencia.id_cateq == models.Catequizando.id_cateq)
    )
    if tipo:
        query = query.filter(models.Asistencia.tipo_asistencia == tipo)

    registros = query.order_by(models.Asistencia.fecha_hora.desc()).all()
    return [
        {
            "ID": r.id_asis,
            "DNI": r.dni,
            "Catequizando": f"{r.nombres} {r.apellidos}",
            "Tipo": r.tipo_asistencia,
            "Actividad": r.detalle_evento or "-",
            "Fecha y Hora": r.fecha_hora
        }
        for r in registros
    ]