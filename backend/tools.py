from datetime import date, datetime, time
from typing import Any

from sqlalchemy import and_
from sqlalchemy.orm import Session

from models import Appointment, AppointmentSlot, AuditLog, Doctor


def _parse_date(value: str) -> date:
    return datetime.strptime(value.strip(), "%Y-%m-%d").date()


def _parse_time(value: str) -> time:
    raw = value.strip().upper().replace(".", "")
    for fmt in ("%H:%M", "%I:%M %p", "%I %p"):
        try:
            return datetime.strptime(raw, fmt).time()
        except ValueError:
            continue
    raise ValueError(f"Invalid time format: {value}")


def _find_doctor(db: Session, doctor_name: str) -> Doctor | None:
    name = doctor_name.strip()
    return db.query(Doctor).filter(Doctor.name.ilike(name)).first()


def _log(db: Session, event_type: str, detail: str) -> None:
    db.add(AuditLog(event_type=event_type, detail=detail))


def check_availability(
    db: Session,
    *,
    appointment_date: str,
    appointment_time: str,
    doctor_name: str,
) -> dict[str, Any]:
    doctor = _find_doctor(db, doctor_name)
    if not doctor:
        return {"ok": False, "error": f"Doctor '{doctor_name}' was not found."}

    try:
        d = _parse_date(appointment_date)
        t = _parse_time(appointment_time)
    except ValueError as exc:
        return {"ok": False, "error": str(exc)}

    slot = (
        db.query(AppointmentSlot)
        .filter(
            and_(
                AppointmentSlot.doctor_id == doctor.id,
                AppointmentSlot.date == d,
                AppointmentSlot.time == t,
            )
        )
        .first()
    )

    if not slot:
        return {
            "ok": True,
            "available": False,
            "doctor": doctor.name,
            "date": d.isoformat(),
            "time": t.strftime("%H:%M"),
            "message": "No slot exists at that date and time for this doctor.",
        }

    _log(
        db,
        "check_availability",
        f"doctor={doctor.name} date={d} time={t} available={slot.available}",
    )
    db.commit()

    return {
        "ok": True,
        "available": slot.available,
        "doctor": doctor.name,
        "date": d.isoformat(),
        "time": t.strftime("%H:%M"),
    }


def book_appointment(
    db: Session,
    *,
    customer_name: str,
    appointment_date: str,
    appointment_time: str,
    doctor_name: str,
) -> dict[str, Any]:
    customer = customer_name.strip()
    if not customer:
        return {"ok": False, "error": "Customer name is required."}

    doctor = _find_doctor(db, doctor_name)
    if not doctor:
        return {"ok": False, "error": f"Doctor '{doctor_name}' was not found."}

    try:
        d = _parse_date(appointment_date)
        t = _parse_time(appointment_time)
    except ValueError as exc:
        return {"ok": False, "error": str(exc)}

    slot = (
        db.query(AppointmentSlot)
        .filter(
            and_(
                AppointmentSlot.doctor_id == doctor.id,
                AppointmentSlot.date == d,
                AppointmentSlot.time == t,
            )
        )
        .first()
    )

    if not slot:
        return {"ok": False, "error": "That slot does not exist."}
    if not slot.available:
        return {"ok": False, "error": "That slot is not available.", "available": False}

    slot.available = False
    appt = Appointment(
        doctor_id=doctor.id,
        customer_name=customer,
        date=d,
        time=t,
        status="booked",
    )
    db.add(appt)
    _log(
        db,
        "book_appointment",
        f"customer={customer} doctor={doctor.name} date={d} time={t}",
    )
    db.commit()
    db.refresh(appt)

    return {
        "ok": True,
        "booked": True,
        "appointment_id": appt.id,
        "customer_name": customer,
        "doctor": doctor.name,
        "date": d.isoformat(),
        "time": t.strftime("%H:%M"),
    }


def list_available_slots(db: Session, doctor_name: str | None = None, limit: int = 10) -> list[dict]:
    q = (
        db.query(AppointmentSlot, Doctor)
        .join(Doctor, Doctor.id == AppointmentSlot.doctor_id)
        .filter(AppointmentSlot.available.is_(True))
        .order_by(AppointmentSlot.date, AppointmentSlot.time)
    )
    if doctor_name:
        q = q.filter(Doctor.name.ilike(doctor_name.strip()))
    rows = q.limit(limit).all()
    return [
        {
            "doctor": doc.name,
            "date": slot.date.isoformat(),
            "time": slot.time.strftime("%H:%M"),
        }
        for slot, doc in rows
    ]
