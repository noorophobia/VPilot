from datetime import date, time, timedelta

from sqlalchemy.orm import Session

from db import Base, SessionLocal, engine
from models import AppointmentSlot, Doctor


def seed(db: Session) -> None:
    if db.query(Doctor).count() > 0:
        return

    doctors = [
        Doctor(name="Dr. Ahmed", specialty="General Practice"),
        Doctor(name="Dr. Lee", specialty="Pediatrics"),
        Doctor(name="Dr. Santos", specialty="Women's Health"),
    ]
    db.add_all(doctors)
    db.flush()

    today = date.today()
    days = [today + timedelta(days=i) for i in range(1, 8)]

    slot_times = [time(9, 0), time(11, 0), time(15, 0), time(16, 30)]
    slots: list[AppointmentSlot] = []

    for d in days:
        if d.weekday() == 6:
            continue
        for doc in doctors:
            for t in slot_times:
                available = True
                if doc.name == "Dr. Ahmed" and d == today + timedelta(days=1) and t == time(15, 0):
                    available = False
                slots.append(
                    AppointmentSlot(doctor_id=doc.id, date=d, time=t, available=available)
                )

    db.add_all(slots)
    db.commit()
    print(f"Seeded {len(doctors)} doctors and {len(slots)} appointment slots.")


def init_db() -> None:
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        seed(db)
    finally:
        db.close()


if __name__ == "__main__":
    init_db()
