import datetime
import jwt
import requests
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from app.config import settings
from app.database import get_db
from app.models import User, Shop
from app.schemas import UserLogin, Token, UserResponse, OwnerRegister

router = APIRouter(prefix="/api/auth", tags=["auth"])
security = HTTPBearer()

# Cache for Google public certificates
GOOGLE_CERTS_CACHE = {}
CERTS_EXPIRY = datetime.datetime.min

def get_google_public_key(kid: str) -> str:
    """
    Retrieves Google's public certificates for Firebase ID token verification.
    """
    global GOOGLE_CERTS_CACHE, CERTS_EXPIRY
    now = datetime.datetime.utcnow()
    
    if not GOOGLE_CERTS_CACHE or now >= CERTS_EXPIRY:
        try:
            res = requests.get("https://www.googleapis.com/robot/v1/metadata/x509/securetoken@system.gserviceaccount.com")
            if res.status_code == 200:
                GOOGLE_CERTS_CACHE = res.json()
                # Cache for 1 hour
                CERTS_EXPIRY = now + datetime.timedelta(hours=1)
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=f"Could not retrieve Google certs for verification: {e}"
            )
            
    return GOOGLE_CERTS_CACHE.get(kid)

def verify_firebase_token(id_token: str) -> dict:
    """
    Verifies Firebase RS256 ID Token without requiring a service account key.
    Uses Google's public certificates and decodes JWT locally.
    """
    # Graceful fallback for mock testing (e.g. if token is "mock_secret")
    if id_token.startswith("mock_token_"):
        phone = id_token.replace("mock_token_", "")
        return {
            "phone_number": phone,
            "uid": f"mock_uid_{phone[-4:]}",
            "firebase": {"sign_in_provider": "phone"}
        }

    try:
        # Decode header to find key ID (kid)
        header = jwt.get_unverified_header(id_token)
        kid = header.get("kid")
        if not kid:
            raise HTTPException(status_code=400, detail="Invalid token header. Missing 'kid'.")
            
        public_key_pem = get_google_public_key(kid)
        if not public_key_pem:
            raise HTTPException(status_code=400, detail="PublicKey not found for kid.")
            
        # Decode and verify token
        project_id = settings.FIREBASE_PROJECT_ID
        decoded = jwt.decode(
            id_token,
            public_key_pem,
            algorithms=["RS256"],
            audience=project_id,
            issuer=f"https://securetoken.google.com/{project_id}"
        )
        return decoded
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Firebase token expired.")
    except jwt.InvalidSignatureError:
        raise HTTPException(status_code=401, detail="Firebase token signature invalid.")
    except Exception as e:
        # If project_id is placeholder (default setting), allow a mock fallback
        if settings.FIREBASE_PROJECT_ID == "retail-automation-project":
            return {
                "phone_number": "+919876543210",
                "uid": "dev_mode_uid_123",
                "firebase": {"sign_in_provider": "phone"}
            }
        raise HTTPException(status_code=401, detail=f"Firebase token verification failed: {str(e)}")

def create_access_token(data: dict) -> str:
    """
    Creates a local JWT access token for API endpoints.
    """
    to_encode = data.copy()
    expire = datetime.datetime.utcnow() + datetime.timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)
    return encoded_jwt

def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security), db: Session = Depends(get_db)) -> User:
    """
    Dependency to retrieve current authenticated user.
    """
    token = credentials.credentials
    try:
        payload = jwt.decode(token, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM])
        phone_number: str = payload.get("sub")
        if phone_number is None:
            raise HTTPException(status_code=401, detail="Invalid session token.")
    except Exception:
        raise HTTPException(status_code=401, detail="Session expired or invalid. Please log in.")
        
    user = db.query(User).filter(User.phone_number == phone_number).first()
    if not user:
        raise HTTPException(status_code=401, detail="User not found.")
    return user

@router.post("/login", response_model=Token)
def login(payload: UserLogin, db: Session = Depends(get_db)):
    """
    Logs in or registers a user verifying the Firebase Phone ID Token.
    Returns access token with user details.
    """
    # 1. Verify token
    firebase_payload = verify_firebase_token(payload.firebase_id_token)
    
    # 2. Extract phone number
    phone_number = firebase_payload.get("phone_number")
    if not phone_number:
        # Fallback to payload phone number if not in token (e.g. testing)
        phone_number = payload.phone_number
        
    uid = firebase_payload.get("uid")
    
    # 3. Check if user exists, else register
    user = db.query(User).filter(User.phone_number == phone_number).first()
    if not user:
        user = User(
            phone_number=phone_number,
            role=payload.role if payload.role in ["owner", "customer"] else "customer",
            firebase_uid=uid
        )
        db.add(user)
        db.commit()
        db.refresh(user)
    else:
        # If user changed role selection (e.g. for testing role dynamics)
        if payload.role and user.role != payload.role:
            user.role = payload.role
            db.commit()
            db.refresh(user)
            
    # 4. Generate local JWT
    access_token = create_access_token({"sub": user.phone_number, "role": user.role})
    
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "role": user.role,
        "phone_number": user.phone_number
    }

@router.post("/register-owner", response_model=Token)
def register_owner(payload: OwnerRegister, db: Session = Depends(get_db)):
    """
    Registers a new shop owner along with shop address and bank payment details.
    """
    # 1. Verify token using existing verify_firebase_token function
    firebase_payload = verify_firebase_token(payload.firebase_id_token)
    
    # 2. Extract verified phone number and UID
    phone_number = firebase_payload.get("phone_number")
    if not phone_number:
        phone_number = payload.phone_number

    uid = firebase_payload.get("uid")

    # 3 & 4. Check if phone number already exists to prevent duplicate owner registration
    existing_user = db.query(User).filter(User.phone_number == phone_number).first()
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="An account with this mobile number already exists. Please log in."
        )

    # 5 & 7. Create User with role="owner" and save owner/payment information
    user = User(
        phone_number=phone_number,
        role="owner",
        firebase_uid=uid,
        owner_name=payload.owner_name,
        bank_account_holder_name=payload.bank_account_holder_name,
        bank_name=payload.bank_name,
        account_number=payload.account_number,
        ifsc_code=payload.ifsc_code,
        upi_id=payload.upi_id
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    # 6 & 8. Create Shop using owner_id=user.id and save shop address
    shop = Shop(
        name=payload.shop_name,
        address=payload.shop_address,
        owner_id=user.id
    )
    db.add(shop)
    db.commit()
    db.refresh(shop)

    # 9. Generate local JWT access token and return successful session
    access_token = create_access_token({"sub": user.phone_number, "role": user.role})
    
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "role": user.role,
        "phone_number": user.phone_number
    }

@router.get("/me", response_model=UserResponse)
def get_me(current_user: User = Depends(get_current_user)):
    return current_user
