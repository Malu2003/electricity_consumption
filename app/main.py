from fastapi import FastAPI, Depends, HTTPException,APIRouter
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm, HTTPBearer, HTTPAuthorizationCredentials
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from passlib.context import CryptContext
import jwt
import datetime
import subprocess  
from app.schemas import  PredictionResponse
from app.database import SessionLocal, engine, get_db  
from . import models, schemas
from sqlalchemy.sql import text

# ✅ Create database tables if they don't exist
models.Base.metadata.create_all(bind=engine)

# ✅ Initialize FastAPI app
app = FastAPI()
router = APIRouter()
# ✅ Enable CORS for Flutter-FastAPI communication
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Update this with frontend URL in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ✅ Password hashing setup
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# ✅ JWT Authentication
SECRET_KEY = "your_secret_key"  # Change this to a secure value
ALGORITHM = "HS256"
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="login")
security = HTTPBearer()

# -----------------------------------------------
# 🔐 UTILITY FUNCTIONS
# -----------------------------------------------

def hash_password(password: str) -> str:
    return pwd_context.hash(password)

def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)

def create_access_token(data: dict, expires_delta: datetime.timedelta = None):
    to_encode = data.copy()
    expire = datetime.datetime.utcnow() + (expires_delta or datetime.timedelta(hours=1))
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security), db: Session = Depends(get_db)):
    token = credentials.credentials
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        email = payload["sub"]
        user = db.query(models.User).filter(models.User.email == email).first()
        if not user:
            raise HTTPException(status_code=401, detail="User not found")
        return user  # ✅ Return full user object
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")
def run_training():
    result = subprocess.run(["python", "scripts/train11.py"], capture_output=True, text=True)
    print("STDOUT:", result.stdout)
    print("STDERR:", result.stderr)
    # ✅ Function to check if both bills and appliances exist
def should_train(user, db):
    has_bills = db.query(models.Bill).filter(models.Bill.consumer_number == user.consumer_number).count() > 0
    has_appliances = db.query(models.Appliance).filter(models.Appliance.consumer_number == user.consumer_number).count() > 0
    return has_bills and has_appliances
# -----------------------------------------------
# 🧑‍💻 USER ROUTES
# -----------------------------------------------

@app.post("/users/", response_model=schemas.UserResponse)
def create_user(user: schemas.UserCreate, db: Session = Depends(get_db)):
    db_user = db.query(models.User).filter(models.User.email == user.email).first()
    if db_user:
        raise HTTPException(status_code=400, detail="Email already registered")
    
    new_user = models.User(
        consumer_number=user.consumer_number,
        name=user.name,
        email=user.email,
        hashed_password=hash_password(user.password),
        family_members=user.family_members,
        working_members=user.working_members,
        ages=user.ages,  
        location=user.location,
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    if should_train(new_user, db):
        run_training()
    
    
    return new_user

@app.get("/users/by-email/{email}", response_model=schemas.UserResponse)
def get_user_by_email(email: str, db: Session = Depends(get_db)):
    user = db.query(models.User).filter(models.User.email == email).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    return schemas.UserResponse(
        consumer_number=user.consumer_number,
        name=user.name,
        email=user.email,
        family_members=user.family_members,
        working_members=user.working_members,
        ages=list(user.ages),
        location=user.location,
    )
# -----------------------------------------------
# 🔐 AUTHENTICATION ROUTES
# -----------------------------------------------

@app.post("/login/", response_model=schemas.Token)
def login(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    user = db.query(models.User).filter(models.User.email == form_data.username).first()
    
    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(status_code=400, detail="Invalid credentials")
    
    access_token = create_access_token({"sub": user.email})
    
    return {"access_token": access_token, "token_type": "bearer"}

# -----------------------------------------------
# 🔌 APPLIANCE ROUTES
# -----------------------------------------------

@app.post("/appliances/", response_model=list[schemas.ApplianceResponse])
def create_appliances(appliance_list: schemas.ApplianceList, db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    new_appliances = []
    for appliance in appliance_list.appliances:
        new_appliance = models.Appliance(
            consumer_number=user.consumer_number,
            appliance_name=appliance.appliance_name,
            usage_hours=appliance.usage_hours,
        )
        db.add(new_appliance)
        new_appliances.append(new_appliance)

    db.commit()
    if should_train(user, db):
        run_training()
    return new_appliances

@app.get("/appliances/", response_model=list[schemas.ApplianceResponse])
def get_appliances(db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    appliances = db.query(models.Appliance).filter(models.Appliance.consumer_number == user.consumer_number).all()
    if not appliances:
        raise HTTPException(status_code=404, detail="No appliances found for this user")
    return appliances

# -----------------------------------------------
# 🧾 BILL ROUTES
# -----------------------------------------------

@app.post("/bills/", response_model=dict)
def create_bill(bill: schemas.BillCreate, db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    # Step 1: Create and save the new bill
    new_bill = models.Bill(
        consumer_number=user.consumer_number,
        month=bill.month,
        units_consumed=bill.units_consumed,
        cost_per_unit=bill.cost_per_unit,
    )
    db.add(new_bill)
    db.commit()
    db.refresh(new_bill)
    
    if should_train(user, db):
        run_training()
    # Step 2: Fetch the predicted values directly
    predicted_values = db.query(models.Prediction).filter(
        models.Prediction.consumer_number == user.consumer_number,
        models.Prediction.month == bill.month
    ).first()

    if not predicted_values:
        raise HTTPException(status_code=404, detail="No predictions found for the given consumer and month.")

    return {
        "bill": new_bill,
        "prediction": {
            "current_bill": predicted_values.bill_amount,
            "shifted_bill": predicted_values.reduced_bill_amount,
            "current_carbon": predicted_values.carbon_footprint,
            "shifted_carbon": predicted_values.reduced_carbon_footprint
        }
    }


@app.get("/bills/", response_model=list[schemas.BillResponse])
def get_bills(db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    bills = db.query(models.Bill).filter(models.Bill.consumer_number == user.consumer_number).all()
    if not bills:
        raise HTTPException(status_code=404, detail="No bills found for this user")
    return bills

# -----------------------------------------------
# 🔮 PREDICTION ROUTES
# -----------------------------------------------

@app.get("/predictions/", response_model=list[schemas.PredictionResponse])
def get_predictions(db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    predictions = db.query(models.Prediction).filter(models.Prediction.consumer_number == user.consumer_number).all()
    
    if not predictions:
        raise HTTPException(status_code=404, detail="No prediction data found for this user")
    
    return predictions

# -----------------------------------------------
# 📅 FETCH LATEST MONTH ROUTE (UPDATED)
# -----------------------------------------------

@app.get("/get_latest_month/{consumer_number}")
def get_latest_month(consumer_number: int, db: Session = Depends(get_db)):
    latest_record = (
        db.query(models.Bill)
        .filter(models.Bill.consumer_number == consumer_number)
        .order_by(models.Bill.month.desc())  
        .first()
    )

    if not latest_record:
        raise HTTPException(status_code=404, detail="No records found for consumer")

    return {"month": latest_record.month}

# -----------------------------------------------
# 🧾 FETCH VALUES BASED ON CONSUMER NUMBER AND MONTH
# -----------------------------------------------

@app.get("/get_value/{consumer_number}")
def get_value(consumer_number: int, month: str, db: Session = Depends(get_db)):
    record = (
        db.query(models.Prediction)
        .filter(models.Prediction.consumer_number == consumer_number, models.Prediction.month == month)
        .first()
    )

    if not record:
        raise HTTPException(status_code=404, detail="No data found for the given month and consumer number")

    return {
        "current_bill": record.bill_amount,
        "shifted_bill": record.reduced_bill_amount,
        "current_carbon": record.carbon_footprint,
        "shifted_carbon": record.reduced_carbon_footprint
    }
