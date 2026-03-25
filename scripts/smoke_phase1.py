from app.core.bootstrap import initialize_phase1
from app.db import Base, SessionLocal, engine


def main() -> None:
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        initialize_phase1(db)
        print("Smoke phase 1 OK")
    finally:
        db.close()


if __name__ == "__main__":
    main()
