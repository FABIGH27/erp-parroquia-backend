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
from datetime import datetime, timedelta
import secrets
from sqlalchemy.exc import IntegrityError


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
            models.Expediente.id_exp,
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
                "id_exp": r.id_exp,
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