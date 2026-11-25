import secrets
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel
from sqlalchemy import func
from sqlalchemy.orm import Session
import models
import schemas
import security
from database import get_db

router = APIRouter()


class LoginAdminRequest(BaseModel):
    dni: str
    password: str


@router.get("/")
def estado_servidor():
    return {"mensaje": "El servidor FastAPI está corriendo y protegido con JWT"}


@router.post("/registro")
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


@router.post("/login")
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


@router.post("/api/v1/admin/login")
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


@router.post("/api/v1/admin/claves-temporales", tags=["Seguridad y Accesos"])
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


@router.get("/api/v1/admin/claves-temporales", tags=["Seguridad y Accesos"])
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


@router.put("/api/v1/admin/claves-temporales/{id_clave}/revocar", tags=["Seguridad y Accesos"])
def revocar_clave_temporal(id_clave: int, db: Session = Depends(get_db)):
    clave = db.query(models.ClaveTemporal).filter(models.ClaveTemporal.id_clave == id_clave).first()
    if not clave:
        raise HTTPException(status_code=404, detail="Clave no encontrada.")
    clave.activa = False
    db.commit()
    return {"mensaje": "Clave revocada correctamente."}


@router.post("/api/v1/admin/validar-clave-temporal", tags=["Seguridad y Accesos"])
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


@router.post("/api/v1/admin/usuarios", tags=["Seguridad y Accesos"])
def crear_usuario(datos: schemas.UsuarioCreate, db: Session = Depends(get_db)):
    existe = db.query(models.Usuario).filter(models.Usuario.dni == datos.dni.strip()).first()
    if existe:
        raise HTTPException(status_code=400, detail="Ya existe un usuario registrado con ese DNI.")

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


@router.get("/api/v1/admin/usuarios", tags=["Seguridad y Accesos"])
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


@router.delete("/api/v1/admin/usuarios/{id_usuario}", tags=["Seguridad y Accesos"])
def eliminar_usuario(id_usuario: int, db: Session = Depends(get_db)):
    usuario = db.query(models.Usuario).filter(models.Usuario.id_usuario == id_usuario).first()
    if not usuario:
        raise HTTPException(status_code=404, detail="Usuario no encontrado.")
    db.delete(usuario)
    db.commit()
    return {"mensaje": "Usuario eliminado correctamente."}