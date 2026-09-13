from model import Service
from sqlalchemy.orm import Session


def get_all_services(db: Session):
    return db.query(Service).all()

def get_service_by_service_id(service_id, db: Session):
    return db.query(Service).get(service_id)

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
    service = db.query(Service).get(service_id)
    if service is None:
        return None

    for field, value in updates.model_dump(exclude_unset=True).items():
        setattr(service, field, value)

    db.commit()
    db.refresh(service)
    return service

def delete_service_by_service_id(service_id, db: Session):
    service = db.query(Service).get(service_id)
    if service is None:
        return None

    db.delete(service)
    db.commit()
    return service
