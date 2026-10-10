from models import Organization, User, Project
from sqlalchemy import select, func


def get_organizations(db):
    return db.execute(select(Organization)).scalars().all()


def create_new_org(new_org, db):
    exisitng_org = (
        db.execute(
            select(Organization).where(Organization.orgEmail == new_org.orgEmail)
        )
        .scalars()
        .first()
    )
    if exisitng_org is not None:
        return None

    created_org = Organization(
        orgId=new_org.orgId,
        orgName=new_org.orgName,
        orgEmail=new_org.orgEmail,
        orgDisabled=new_org.orgDisabled,
        **({"orgTimezone": new_org.orgTimezone} if new_org.orgTimezone else {}),
    )

    db.add(created_org)
    db.commit()
    db.refresh(created_org)

    return created_org


def get_org_info_by_id(org_id, db):
    return db.get(Organization, org_id)


def update_org_info_by_id(org_id, updated_org, db):
    org_data = db.get(Organization, org_id)
    if org_data is None:
        return None

    for field, value in updated_org.model_dump(exclude_unset=True).items():
        setattr(org_data, field, value)

    db.commit()
    db.refresh(org_data)

    return org_data


def delete_org_by_org_id(org_id, db):
    org = db.get(Organization, org_id)
    if org is None:
        return None

    db.delete(org)
    db.commit()
    return org


def get_user_count(org_id, db):
    return db.scalar(
        select(func.count()).select_from(User).where(User.userOrg == org_id)
    )


def get_project_count(org_id, db):
    return db.scalar(
        select(func.count())
        .select_from(Project)
        .where(Project.organizationId == org_id)
    )
