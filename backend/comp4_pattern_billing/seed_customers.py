
"""Create and synchronize 200 SmartTrolley development customer accounts."""

from sqlalchemy import select
from pwdlib import PasswordHash

from auth_database import Base, engine, SessionLocal
from auth_models import User, Customer


TOTAL_CUSTOMERS = 200
DEMO_PASSWORD = "TrolleyDemo2026!"

password_hasher = PasswordHash.recommended()


def seed_customers():
    Base.metadata.create_all(bind=engine)

    created_users = 0
    updated_users = 0
    created_profiles = 0

    with SessionLocal() as db:
        try:
            # Hash only for accounts that need to be created.
            demo_password_hash = None

            for number in range(1, TOTAL_CUSTOMERS + 1):
                user_code = f"U{number:04d}"
                customer_id = f"C{number:04d}"
                full_name = f"Customer {number:03d}"
                email = f"customer{number:03d}@example.com"

                # Find records by each unique identifier.
                user_by_code = db.scalar(
                    select(User).where(User.user_code == user_code)
                )
                user_by_email = db.scalar(
                    select(User).where(User.email == email)
                )
                user_by_customer_id = db.scalar(
                    select(User).where(
                        User.customer_id == customer_id
                    )
                )

                found_users = {
                    user.id: user
                    for user in (
                        user_by_code,
                        user_by_email,
                        user_by_customer_id,
                    )
                    if user is not None
                }

                # Stop if identifiers point to different accounts.
                if len(found_users) > 1:
                    raise RuntimeError(
                        f"Conflicting user records for {customer_id}. "
                        "Resolve the conflicts before seeding."
                    )

                user = next(iter(found_users.values()), None)

                if user is None:
                    # Generate a hash only when a new account is needed.
                    if demo_password_hash is None:
                        demo_password_hash = password_hasher.hash(
                            DEMO_PASSWORD
                        )

                    user = User(
                        user_code=user_code,
                        customer_id=customer_id,
                        full_name=full_name,
                        email=email,
                        password_hash=demo_password_hash,
                        role="customer",
                        is_active=True,
                    )
                    db.add(user)
                    db.flush()
                    created_users += 1

                else:
                    # Never reassign an account belonging to a
                    # different customer or role.
                    if user.role != "customer":
                        raise RuntimeError(
                            f"{user_code} is not a customer account."
                        )

                    if (
                        user.user_code != user_code
                        or user.customer_id != customer_id
                    ):
                        raise RuntimeError(
                            f"Identifier conflict for {user_code}. "
                            "No changes will be committed."
                        )

                    # Correct names and email addresses, but preserve
                    # the existing password hash and account status.
                    changed = False

                    if user.full_name != full_name:
                        user.full_name = full_name
                        changed = True

                    if user.email != email:
                        # Avoid overwriting another account's email.
                        email_owner = db.scalar(
                            select(User).where(
                                User.email == email,
                                User.id != user.id,
                            )
                        )

                        if email_owner is not None:
                            raise RuntimeError(
                                f"{email} belongs to another account."
                            )

                        user.email = email
                        changed = True

                    if changed:
                        updated_users += 1

                # Find the customer profile linked to this user.
                profile_by_user = db.scalar(
                    select(Customer).where(
                        Customer.user_id == user.id
                    )
                )

                profile_by_code = db.scalar(
                    select(Customer).where(
                        Customer.customer_id == customer_id
                    )
                )

                if (
                    profile_by_user is not None
                    and profile_by_user.customer_id != customer_id
                ):
                    raise RuntimeError(
                        f"Profile mismatch for {user_code}: "
                        f"found {profile_by_user.customer_id}."
                    )

                if (
                    profile_by_code is not None
                    and profile_by_code.user_id != user.id
                ):
                    raise RuntimeError(
                        f"{customer_id} is linked to another user."
                    )

                if profile_by_user is None and profile_by_code is None:
                    db.add(
                        Customer(
                            user_id=user.id,
                            customer_id=customer_id,
                        )
                    )
                    created_profiles += 1

            # All changes are committed together.
            db.commit()

        except Exception:
            db.rollback()
            raise

    print("Customer seeding and synchronization completed.")
    print(f"New user accounts: {created_users}")
    print(f"Existing accounts corrected: {updated_users}")
    print(f"New customer profiles: {created_profiles}")
    print(f"Target customer accounts: {TOTAL_CUSTOMERS}")
    print("Existing passwords were preserved.")
    print("Accounts beyond C0200 were not modified.")


if __name__ == "__main__":
    seed_customers()
