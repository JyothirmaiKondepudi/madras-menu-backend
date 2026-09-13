from sqlalchemy import *
from sqlalchemy.orm import relationship
from datetime import datetime
import uuid
from database import Base

class User(Base):
    __tablename__ = 'user_data'

    userId = Column('user_id', UUID(as_uuid=True),primary_key=True, default=uuid.uuid4)
    fullName = Column("full_name",String ,nullable=False)
    userEmail = Column("email",String, unique=True, nullable=False)
    userPhoneNumber = Column("phone_number",String(10), nullable = False)
    preferredContact = Column("preferred_contact",String,nullable=False)
    userAddress = Column("address",String)
    userRole = Column('role', String, nullable=False)
    userCreatedAt = Column("created_at",DateTime, default= datetime.now)
    updatedAt = Column("updated_at",DateTime, default= datetime.now,onupdate=datetime.now)


class Project(Base):
    __tablename__ = 'projects'
    
    projectName = Column("project_name",String ,nullable=False)
    projectId = Column("project_id",UUID(as_uuid=True) ,nullable=False, primary_key=True, default=uuid.uuid4)
    projectStatus = Column("project_status", Enum('Proposal', 'Accepted', 'Rejected', 'Suggested Changes', 'Planning', 'Complete', name='project_status_enum'))
    projectStartDate = Column("project_start_date",DateTime, default= datetime.now)
    projectEndDate = Column("project_end_date",DateTime, default= datetime.now)
    adminOnProject = Column("admin_on_project",UUID(as_uuid=True), ForeignKey('user_data.user_id'))
    clientId = Column("client_id", UUID(as_uuid=True), ForeignKey('user_data.user_id'), nullable=False)
    project_invoice = Column('projectInvoice', UUID(as_uuid=True), ForeignKey('invoices.invoice_id'))

    client = relationship('User', foreign_keys=[clientId])
    admin = relationship('User', foreign_keys=[adminOnProject])


user_projects = Table(
    'user_projects',
    Base.metadata,
    Column('user_id', UUID(as_uuid=True), ForeignKey('user_data.user_id'), primary_key=True),
    Column('project_id', UUID(as_uuid=True), ForeignKey('projects.project_id'), primary_key=True)
)

class Invoice(Base):
    __tablename__ = 'invoices'

    invoiceId = Column("invoice_id",UUID(as_uuid=True) ,nullable=False, primary_key=True, default=uuid.uuid4)
    invoiceStatus = Column("invoice_status", Enum('Generated', 'Assigned', 'Pending', 'Paid', 'Declined', name='invoice_status_enum'), nullable=False)
    invoiceAmount = Column("invoice_amount", Float, nullable=False)
    invoiceAssignedTo = Column("invoice_assigned_to", UUID(as_uuid=True), ForeignKey('user_data.user_id'), nullable=False)

class Service(Base):
    __tablename__ = 'services'

    serviceId = Column("service_id", UUID(as_uuid=True) ,nullable=False, primary_key=True, default=uuid.uuid4)
    serviceName = Column("service_name", String, nullable=False)
    projectAssociatedTo = Column("project_associated_to", UUID(as_uuid=True), ForeignKey('projects.project_id'), nullable=False)
    cuisine = Column("cuisine", ARRAY(String))
    religion = Column('religion', Enum('Hindu', 'Muslim', "Christian", name='religion_enum'))
    serviceDate = Column("service_date", DateTime, nullable=False)
    guestCount = Column("guest_count", Integer, nullable=False)
    serviceType = Column("service_type", Enum('Buffet', 'Plated', 'Family Style', 'Live Stations', 'Butler Passed', name='service_type_enum'), nullable=False)
    serviceVenue = Column('venue', Enum('Hotel', 'Country Club', 'Mueseum', 'Party Hall', 'Home', "Outdoor", name='venue_enum'), nullable=False)
    serviceEvent = Column('service_event', Enum('breakfast', 'wedding Lunch', 'Wedding Dinner', 'Anniversary', 'birthday', 'cockatail hour', 'mehendi', 'haldi', 'ceremony refreshments', 'vidai', 'welcome dinner', 'welcome lunch', 'baarat', 'Walima', 'Graduation', 'house Warming', 'High tea' ,name='event_enum'), nullable=False)
    minPricePerPerson = Column('min_price_per_person', Float)
    maxPricePerPerson = Column('max_price_per_person', Float)

    project = relationship('Project')
