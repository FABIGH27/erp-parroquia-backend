import secrets
from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import JSONResponse
from sqlalchemy import func
from sqlalchemy.orm import Session
import models
import schemas
import security
from database import get_db
from routers.rt_deps import PERU_TZ, _a_hora_peru

router = APIRouter()


@router.get("/api/v1/health", tags=["Móvil APK"])
def health_check():
    return {"status": "ok", "hora_utc": datetime.utcnow().isoformat()}


@router.post("/api/v1/asistencia", tags=["Logística y Escáner QR"])
def registrar_asistencia(request: schemas.AsistenciaQRRequest, db: Session = Depends(get_db)):
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
        tipo_final = codigo_srv.tipo_asistencia
        detalle_final = codigo_srv.detalle_evento
    else:
        tipo_final = request.tipo_asistencia
        detalle_final = request.detalle_evento

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

    usuario = db.query(models.Usuario).filter(models.Usuario.id_usuario == request.id_usuario).first()
    es_admin = False
    if usuario and usuario.rol:
        es_admin = usuario.rol.nombre_rol.strip().lower() in ["administrador", "admin"]

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


@router.get("/api/v1/asistencias", tags=["Logística y Escáner QR"])
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


@router.delete("/api/v1/asistencias/{id_asis}", tags=["Logística y Escáner QR"])
def eliminar_asistencia(id_asis: int, db: Session = Depends(get_db)):
    asis = db.query(models.Asistencia).filter(models.Asistencia.id_asis == id_asis).first()
    if not asis:
        raise HTTPException(status_code=404, detail="Asistencia no encontrada.")
    db.delete(asis)
    db.commit()
    return {"mensaje": "Asistencia eliminada correctamente."}


@router.post("/api/v1/admin/codigos-servicio", tags=["Móvil APK"])
def crear_codigo_servicio(datos: schemas.CodigoServicioCreate, db: Session = Depends(get_db)):
    horas = max(1, min(datos.duracion_horas, 4))
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


@router.get("/api/v1/admin/codigos-servicio", tags=["Móvil APK"])
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


@router.put("/api/v1/admin/codigos-servicio/{id_codigo}/revocar", tags=["Móvil APK"])
def revocar_codigo_servicio(id_codigo: int, db: Session = Depends(get_db)):
    c = db.query(models.CodigoServicio).filter(models.CodigoServicio.id_codigo == id_codigo).first()
    if not c:
        raise HTTPException(status_code=404, detail="Código no encontrado.")
    c.activo = False
    db.commit()
    return {"mensaje": "Código de servicio revocado en vivo."}


@router.post("/api/v1/movil/login", tags=["Móvil APK"])
def login_movil_con_codigo(req: schemas.LoginMovilRequest, db: Session = Depends(get_db)):
    dni_limpio = req.dni.strip()
    usuario = db.query(models.Usuario).filter(models.Usuario.dni == dni_limpio).first()

    if not usuario or not usuario.estado:
        raise HTTPException(status_code=401, detail="DNI no registrado o usuario inactivo.")

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

    nombre_rol = usuario.rol.nombre_rol if usuario.rol else "Usuario"
    es_admin = nombre_rol.strip().lower() in ["administrador", "admin"]
    codigo_limpio = (req.codigo_servicio or "").strip().upper()

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


@router.get("/api/v1/movil/catequizandos/buscar", tags=["Móvil APK"])
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