from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session
import models
import schemas
from database import get_db
from routers.deps import _a_hora_peru, requerir_rol_tesoreria

router = APIRouter()


@router.get("/tesoreria/balance")
def obtener_balance_caja(usuario_actual: models.Usuario = Depends(requerir_rol_tesoreria)):
    return {
        "mensaje": "Acceso concedido a la bóveda de datos financieros",
        "usuario_operador": usuario_actual.nombres,
        "rol_detectado": usuario_actual.id_rol
    }


@router.post("/api/v1/tesoreria/conceptos", tags=["Tesorería"])
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


@router.get("/api/v1/tesoreria/conceptos", tags=["Tesorería"])
def listar_conceptos(db: Session = Depends(get_db)):
    return db.query(models.ConceptoPago).all()


@router.post("/api/v1/tesoreria/pagos", tags=["Tesorería"])
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


@router.get("/api/v1/tesoreria/pagos", tags=["Tesorería"])
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


@router.delete("/api/v1/tesoreria/pagos/{id_pago}", tags=["Tesorería"])
def eliminar_pago(id_pago: int, db: Session = Depends(get_db)):
    pago = db.query(models.Pago).filter(models.Pago.id_pago == id_pago).first()
    if not pago:
        raise HTTPException(status_code=404, detail="Pago no encontrado.")
    db.delete(pago)
    db.commit()
    return {"mensaje": "Pago anulado y eliminado correctamente."}