
from database import SessionLocal
from models import Role


def seed_roles():
    db = SessionLocal()

    roles = [
        "Admin",
        "Warehouse Manager",
        "Logistics Manager",
        "Sales Manager",
        "Supplier",
    ]

    try:
        for role_name in roles:
            existing_role = db.query(Role).filter(
                Role.role_name == role_name
            ).first()

            if existing_role is None:
                db.add(Role(role_name=role_name))

        db.commit()
        print("Default roles added successfully!")
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    seed_roles()
