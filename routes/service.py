from sqlalchemy.orm import Session
from services.service import *
from fastapi import APIRouter, Depends, HTTPException
from model import Service
from schemas.service import ServiceOut, ServiceCreate, ServiceUpdate
from database import get_db
from uuid import UUID

router = APIRouter()

@router.get("/services",response_model=list[ServiceOut])
def get_services(db: Session= Depends(get_db)):
    services = get_all_services(db)
    return services

@router.get("/services/projects/{project_id}", response_model=list[ServiceOut])
def getServiceByProjectId(project_id:UUID, db: Session=Depends(get_db)):
    services = get_all_services_by_project_id(project_id, db)
    return services

@router.get("/services/{service_id}", response_model=ServiceOut)
def get_service_by_id(service_id:UUID, db:Session= Depends(get_db)):
     return get_service_by_service_id(service_id, db)

@router.post("/services", response_model=ServiceOut)
def add_service(new_service: ServiceCreate, db:Session= Depends(get_db)):
     created_service = add_new_service(new_service, db)
    #  if created_service is None:
    #      raise HTTPException(status_code=409, detail="failure creating a new service")
     return created_service

@router.patch("/services/{service_id}", response_model=ServiceOut)
def update_service(service_id: UUID, updates: ServiceUpdate, db: Session = Depends(get_db)):
    updated_service = update_service_by_service_id(service_id, updates, db)
    if updated_service is None:
        raise HTTPException(status_code=404, detail="service not found")
    return updated_service

@router.delete("/services/{service_id}", status_code=204)
def delete_service(service_id: UUID, db: Session = Depends(get_db)):
    deleted_service = delete_service_by_service_id(service_id, db)
    if deleted_service is None:
        raise HTTPException(status_code=404, detail="service not found")
