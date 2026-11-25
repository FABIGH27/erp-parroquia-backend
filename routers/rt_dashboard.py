from datetime import datetime, timezone
from typing import Any, Dict
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session
import models
from database import get_db
from routers.rt_deps import _a_hora_peru

router = APIRouter()


@router.get("/api/v1/dashboard/resumen", tags=["Dashboard"])
def obtener_resumen_dashboard(db: Session = Depends(get_db)):
    total_alumnos = db.query(func.count(models.Catequizando.id_cateq)).scalar() or 0
    total_asistencias = db.query(func.count(models.Asistencia.id_asis)).scalar() or 0
    total_recaudado = db.query(func.sum(models.Pago.monto)).scalar() or 0

    pagos_por_metodo = (
        db.query(models.Pago.metodo_pago, func.sum(models.Pago.monto))
        .group_by(models.Pago.metodo_pago)
        .all()
    )

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


@router.get("/api/v1/dashboard/alertas", tags=["Dashboard"])
def obtener_alertas_dashboard(db: Session = Depends(get_db)):
    jovenes = db.query(models.Catequizando).all()
    conceptos = db.query(models.ConceptoPago).all()
    docs_obligatorios = db.query(models.DocumentoRequisito).filter(
        models.DocumentoRequisito.es_obligatorio == True
    ).all()

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

    expedientes = db.query(
        models.Expediente.id_cateq,
        models.Expediente.id_doc,
        models.Expediente.estado
    ).all()
    mapa_exp = {(r[0], r[1]): r[2] for r in expedientes}

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


@router.get("/api/v1/admin/backup/exportar", tags=["Seguridad y Accesos"])
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


@router.post("/api/v1/admin/backup/restaurar", tags=["Seguridad y Accesos"])
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