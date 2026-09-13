from sqlalchemy import *
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import JSONB
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


# --- Ported from madras-menu-studio's Prisma schema (owned there, not by this
# repo's Alembic migrations) — mapped read/write against the existing tables,
# matching their real column types (text ids, not UUID) exactly. ---

class TaxCategory(Base):
    __tablename__ = 'tax_categories'

    id = Column("id", String, primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column("name", String, nullable=False, unique=True)
    jurisdiction = Column("jurisdiction", String, nullable=False)
    ratePercent = Column("rate_percent", Numeric(5, 3), nullable=False)
    effectiveDate = Column("effective_date", DateTime, default=datetime.now, server_default=func.now(), nullable=False)


class MenuItem(Base):
    __tablename__ = 'menu_items'

    id = Column("id", String, primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column("name", String, nullable=False, unique=True)
    course = Column("course", String, nullable=False)
    vegNonveg = Column("veg_nonveg", String, nullable=False)
    cuisineTags = Column("cuisine_tags", ARRAY(String))
    priceWeight = Column("price_weight", String, nullable=False)
    isStaple = Column("is_staple", Boolean, nullable=False, default=False)
    servedAsLiveStation = Column("served_as_live_station", Boolean, nullable=False, default=False)
    allergens = Column("allergens", ARRAY(String))
    dietaryFlags = Column("dietary_flags", ARRAY(String))
    religionSuitability = Column("religion_suitability", ARRAY(String))
    occasionSuitability = Column("occasion_suitability", ARRAY(String))
    spiceLevel = Column("spice_level", String)
    prepMethod = Column("prep_method", String)
    portionUnit = Column("portion_unit", String)
    costPerPerson = Column("cost_per_person", Numeric(8, 2))
    taxCategoryId = Column("tax_category_id", String, ForeignKey('tax_categories.id'))
    active = Column("active", Boolean, nullable=False, default=True)
    confidence = Column("confidence", String)
    sourceDocs = Column("source_docs", ARRAY(String))
    createdAt = Column("created_at", DateTime, default=datetime.now, server_default=func.now(), nullable=False)
    updatedAt = Column("updated_at", DateTime, default=datetime.now, onupdate=datetime.now, nullable=False)


class ItemRelationship(Base):
    __tablename__ = 'item_relationships'
    __table_args__ = (
        Index(
            'item_relationships_one_parent_per_child',
            'from_item_id',
            unique=True,
            postgresql_where=text("relationship_type = 'parent_of'"),
        ),
    )

    id = Column("id", String, primary_key=True, default=lambda: str(uuid.uuid4()))
    fromItemId = Column("from_item_id", String, ForeignKey('menu_items.id'), nullable=False)
    toItemId = Column("to_item_id", String, ForeignKey('menu_items.id'), nullable=False)
    relationshipType = Column("relationship_type", String, nullable=False)
    relationshipMetadata = Column("metadata", JSONB)
    createdAt = Column("created_at", DateTime, default=datetime.now, server_default=func.now(), nullable=False)
