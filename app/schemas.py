from pydantic import BaseModel, ConfigDict
from typing import List, Optional

class UserCreate(BaseModel):
    name: str
    email: str
    password: str  # ✅ Keep plain password here, will be hashed before storing
    consumer_number: int  # 🔹 Changed to int
    family_members: int  
    working_members: int  
    ages: List[int]  
    location: str

    model_config = ConfigDict(from_attributes=True)

class UserResponse(BaseModel):
    name: str
    email: str
    consumer_number: int  # 🔹 Changed to int
    family_members: int
    working_members: int
    ages: List[int]
    location: str

    model_config = ConfigDict(from_attributes=True)

    # ❌ Removed password from response to ensure security

class UserLogin(BaseModel):
    email: str
    password: str  # ✅ Required for authentication

class Token(BaseModel):
    access_token: str
    token_type: str

class TokenData(BaseModel):
    email: Optional[str] = None

class ApplianceCreate(BaseModel):
    consumer_number: int  # 🔹 Changed to int
    appliance_name: str
    usage_hours: float

    model_config = ConfigDict(from_attributes=True)

class ApplianceResponse(BaseModel):
    consumer_number: int  # 🔹 Changed to int
    appliance_name: str
    usage_hours: float

    model_config = ConfigDict(from_attributes=True)

class ApplianceList(BaseModel):
    appliances: List[ApplianceCreate]

class BillCreate(BaseModel):
    consumer_number: int  # 🔹 Changed to int
    month: str
    units_consumed: float
    cost_per_unit: float 

    model_config = ConfigDict(from_attributes=True)

class BillResponse(BaseModel):
    consumer_number: int  # 🔹 Changed to int
    month: str
    units_consumed: float
    cost_per_unit: float

    model_config = ConfigDict(from_attributes=True)

class PredictionResponse(BaseModel):
    consumer_number: int
    month: str
    energy_consumption: float
    reduced_consumption: float
    bill_amount: float
    reduced_bill_amount: float
    carbon_footprint: float
    reduced_carbon_footprint: float
    
    model_config = ConfigDict(from_attributes=True)