from datetime import timedelta, timezone
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import jwt, JWTError
from sqlalchemy.orm import Session
import models
import security
from database import get_db

PERU_TZ = timezone(timedelta(hours=-5))

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="login")


def _a_hora_peru(dt) -> str:
    if not dt:
        return "-"
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(PERU_TZ).strftime("%Y-%m-%d %H:%M:%S")


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
    if usuario.id_rol not in [1, 3]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Operación denegada: Privilegios insuficientes"
        )
    return usuario