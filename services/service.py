from model import Project, Service
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

# shared by every query that returns a ServiceOut, since it now nests
# project -> client / admin
_WITH_PROJECT_AND_USERS = joinedload(Service.project).options(
    joinedload(Project.client),
    joinedload(Project.admin),
)


def get_all_services(db: Session):
    return db.execute(
        select(Service).options(_WITH_PROJECT_AND_USERS)
    ).scalars().all()

def get_service_by_service_id(service_id, db: Session):
    return db.get(Service, service_id, options=[_WITH_PROJECT_AND_USERS])

def add_new_service(new_service, db: Session):
    created_service = Service(
        serviceName=new_service.serviceName,
        projectAssociatedTo=new_service.projectAssociatedTo,
        cuisine=new_service.cuisine,
        religion=new_service.religion,
        serviceDate=new_service.serviceDate,
        guestCount=new_service.guestCount,
        serviceType=new_service.serviceType,
        serviceVenue=new_service.serviceVenue,
        serviceEvent=new_service.serviceEvent,
        minPricePerPerson=new_service.minPricePerPerson,
        maxPricePerPerson=new_service.maxPricePerPerson,
    )
    db.add(created_service)
    db.commit()
    db.refresh(created_service)
    return created_service

def update_service_by_service_id(service_id, updates, db: Session):
    service = db.get(Service, service_id)
    if service is None:
        return None

    for field, value in updates.model_dump(exclude_unset=True).items():
        setattr(service, field, value)

    db.commit()
    db.refresh(service)
    return service

def delete_service_by_service_id(service_id, db: Session):
    service = db.get(Service, service_id)
    if service is None:
        return None

    db.delete(service)
    db.commit()
    return service

def get_all_services_by_project_id(project_id, db: Session):
    return db.execute(
        select(Service)
        .where(Service.projectAssociatedTo == project_id)
        .options(_WITH_PROJECT_AND_USERS)
    ).scalars().all()
