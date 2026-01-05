from fastapi.middleware.cors import CORSMiddleware
from fastapi import FastAPI, Depends, HTTPException
from sqlalchemy.orm import Session

from database import Base, engine, SessionLocal
from models import User, Attendance
from auth import hash_password, verify_password, create_access_token,authenticate_user
from schemas import RegisterRequest, LoginRequest, PunchRequest
from datetime import datetime, date

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],  # frontend
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

Base.metadata.create_all(bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@app.post("/auth/register")
def register(payload: RegisterRequest, db: Session = Depends(get_db)):
    if db.query(User).filter(User.email == payload.email).first():
        raise HTTPException(status_code=400, detail="User already exists")

    if payload.role not in ["employee", "employer"]:
        raise HTTPException(status_code=400, detail="Invalid role")

    user = User(
        email=payload.email,
        password=hash_password(payload.password),
        role=payload.role
    )
    db.add(user)
    db.commit()

    return {"message": "User registered successfully"}

@app.post("/auth/login")
def login(payload: LoginRequest, db: Session = Depends(get_db)):
    user = authenticate_user(db, payload.email, payload.password)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid credentials")

    return {
        "access_token": create_access_token({"sub": user.email}),
    "token_type": "bearer",
    "role": user.role
    }

@app.post("/attendance/punch-in")
def punch_in(
    payload: PunchRequest,
    db: Session = Depends(get_db)
):
    user_id = payload.user_id

    today = date.today()

    existing = (
        db.query(Attendance)
        .filter(
            Attendance.user_id == user_id,
            Attendance.punch_in >= datetime.combine(today, datetime.min.time())
        )
        .first()
    )

    if existing:
        raise HTTPException(status_code=400, detail="Already punched in today")

    attendance = Attendance(
        user_id=user_id,
        punch_in=datetime.utcnow()
    )
    db.add(attendance)
    db.commit()

    return {"message": "Punch in successful"}

@app.post("/attendance/punch-out")
def punch_out(
    payload: PunchRequest,
    db: Session = Depends(get_db)
):
    user_id = payload.user_id

    attendance = (
        db.query(Attendance)
        .filter(
            Attendance.user_id == user_id,
            Attendance.punch_out.is_(None)
        )
        .order_by(Attendance.punch_in.desc())
        .first()
    )

    if not attendance:
        raise HTTPException(status_code=400, detail="No active punch-in found")

    attendance.punch_out = datetime.utcnow()
    db.commit()

    return {"message": "Punch out successful"}
