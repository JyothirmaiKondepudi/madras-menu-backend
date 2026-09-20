from sqlalchemy import Column, String, DateTime, Float, Integer, Enum, ForeignKey, ARRAY
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
import uuid
from database import Base


class Subproject(Base):
    __tablename__ = 'subprojects'

    subprojectId = Column("subproject_id", UUID(as_uuid=True), nullable=False, primary_key=True, default=uuid.uuid4)
    subprojectName = Column("subproject_name", String, nullable=False)
    projectAssociatedTo = Column("project_associated_to", UUID(as_uuid=True), ForeignKey('projects.project_id'), nullable=False)
    cuisine = Column("cuisine", ARRAY(String))
    religion = Column('religion', Enum('Hindu', 'Muslim', "Christian", name='religion_enum'))
    subprojectDate = Column("subproject_date", DateTime, nullable=False)
    guestCount = Column("guest_count", Integer, nullable=False)
    subprojectType = Column("subproject_type", Enum('Buffet', 'Plated', 'Family Style', 'Live Stations', 'Butler Passed', name='subproject_type_enum'), nullable=False)
    subprojectVenue = Column('venue', Enum('Hotel', 'Country Club', 'Mueseum', 'Party Hall', 'Home', "Outdoor", name='venue_enum'), nullable=False)
    subprojectEvent = Column('subproject_event', Enum('breakfast', 'wedding Lunch', 'Wedding Dinner', 'Anniversary', 'birthday', 'cockatail hour', 'mehendi', 'haldi', 'ceremony refreshments', 'vidai', 'welcome dinner', 'welcome lunch', 'baarat', 'Walima', 'Graduation', 'house Warming', 'High tea', name='event_enum'), nullable=False)
    minPricePerPerson = Column('min_price_per_person', Float)
    maxPricePerPerson = Column('max_price_per_person', Float)

    project = relationship('Project')
