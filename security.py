from datetime import datetime, timedelta
from jose import jwt
import bcrypt  # Usamos bcrypt directamente, sin el intermediario passlib

# Llave maestra para encriptar los tokens.
SECRET_KEY = "clave_secreta_erp_parroquia_juliaca_2026"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 120

def obtener_hash_password(password: str):
    # bcrypt requiere que la contraseña se convierta a bytes antes de encriptar
    pwd_bytes = password.encode('utf-8')
    salt = bcrypt.gensalt()
    hashed_password = bcrypt.hashpw(pwd_bytes, salt)
    # Lo decodificamos a string normal para poder guardarlo en el VARCHAR de MySQL
    return hashed_password.decode('utf-8')

def verificar_password(plain_password: str, hashed_password: str):
    # Convertimos ambas a bytes para que el algoritmo matemático las compare de forma segura
    password_byte_enc = plain_password.encode('utf-8')
    hashed_password_byte_enc = hashed_password.encode('utf-8')
    return bcrypt.checkpw(password_byte_enc, hashed_password_byte_enc)

def crear_token_acceso(data: dict):
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt