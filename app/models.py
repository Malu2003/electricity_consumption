from sqlalchemy import Column, Integer, String, Float, ForeignKey, create_engine
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import relationship, sessionmaker, declarative_base
from sqlalchemy import PrimaryKeyConstraint
from app.database import Base
# Create a base class for declarative models
Base = declarative_base()

# Define the database URL
SQLALCHEMY_DATABASE_URL = "postgresql+psycopg2://postgres:tangumalu@localhost/seven"

# Create the engine to interact with PostgreSQL
engine = create_engine(SQLALCHEMY_DATABASE_URL, echo=True)

# Create a session local class
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

class User(Base):
    __tablename__ = "users"
    
    consumer_number = Column(Integer, primary_key=True, index=True, unique=True, nullable=False)
    name = Column(String, nullable=False, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)  # ✅ Changed from `password` to `hashed_password`
    family_members = Column(Integer, nullable=False)  
    working_members = Column(Integer, nullable=False)  
    ages = Column(ARRAY(Integer), nullable=False)
    location = Column(String, nullable=True)
    
    # Relationships
    appliances = relationship("Appliance", back_populates="owner", cascade="all, delete", passive_deletes=True)
    bills = relationship("Bill", back_populates="user", cascade="all, delete", passive_deletes=True)

class Appliance(Base):
    __tablename__ = "appliances"
    
    consumer_number = Column(Integer, ForeignKey("users.consumer_number", ondelete="CASCADE"), nullable=False)
    appliance_name = Column(String, nullable=False)
    usage_hours = Column(Float, nullable=False)
    
    __table_args__ = (PrimaryKeyConstraint("consumer_number", "appliance_name"),)

    owner = relationship("User", back_populates="appliances", passive_deletes=True)

class Bill(Base):
    __tablename__ = "bills"
    
    consumer_number = Column(Integer, ForeignKey("users.consumer_number", ondelete="CASCADE"), nullable=False)
    month = Column(String, nullable=False)
    units_consumed = Column(Float, nullable=False)
    cost_per_unit = Column(Float, nullable=False)
   
    __table_args__ = (PrimaryKeyConstraint("consumer_number", "month"),)

    user = relationship("User", back_populates="bills", passive_deletes=True)


class Prediction(Base):
    __tablename__ = "predictions"

    consumer_number = Column(Integer, ForeignKey("users.consumer_number", ondelete="CASCADE"), nullable=False)
    month = Column(String, nullable=False)
    energy_consumption = Column(Float)
    reduced_consumption = Column(Float)
    bill_amount = Column(Float)
    reduced_bill_amount = Column(Float)
    carbon_footprint = Column(Float)
    reduced_carbon_footprint = Column(Float)

    __table_args__ = (PrimaryKeyConstraint("consumer_number", "month"),)