from sqlalchemy.orm import Session
from services.service import *
from fastapi import APIRouter, Depends, HTTPException
from models import Service, User
from schemas.service import ServiceOut, ServiceCreate, ServiceUpdate
from database import get_db
from auth.dependencies import get_current_user, user_project_ids, require_admin
from uuid import UUID

router = APIRouter()

@router.get("/services",response_model=list[ServiceOut])
def get_services(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    if current_user.userRole == "admin":
        return get_all_services(db)
    return get_services_by_project_ids(user_project_ids(current_user), db)

@router.get("/services/projects/{project_id}", response_model=list[ServiceOut])
def getServiceByProjectId(
    project_id: UUID, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)
):
    if current_user.userRole != "admin" and project_id not in user_project_ids(current_user):
        raise HTTPException(status_code=403, detail="not authorized to view this project's services")
    services = get_all_services_by_project_id(project_id, db)
    return services

@router.get("/services/{service_id}", response_model=ServiceOut)
def get_service_by_id(
    service_id: UUID, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)
):
     service = get_service_by_service_id(service_id, db)
     if service is None:
         raise HTTPException(status_code=404, detail="service not found")
     if current_user.userRole != "admin" and service.projectAssociatedTo not in user_project_ids(current_user):
         raise HTTPException(status_code=403, detail="not authorized to view this service")
     return service

@router.post("/services", response_model=ServiceOut)
def add_service(new_service: ServiceCreate, db: Session = Depends(get_db), admin: User = Depends(require_admin)):
     created_service = add_new_service(new_service, db)
    #  if created_service is None:
    #      raise HTTPException(status_code=409, detail="failure creating a new service")
     return created_service

@router.patch("/services/{service_id}", response_model=ServiceOut)
def update_service(
    service_id: UUID, updates: ServiceUpdate, db: Session = Depends(get_db), admin: User = Depends(require_admin)
):
    updated_service = update_service_by_service_id(service_id, updates, db)
    if updated_service is None:
        raise HTTPException(status_code=404, detail="service not found")
    return updated_service

@router.delete("/services/{service_id}", status_code=204)
def delete_service(service_id: UUID, db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    deleted_service = delete_service_by_service_id(service_id, db)
    if deleted_service is None:
        raise HTTPException(status_code=404, detail="service not found")
