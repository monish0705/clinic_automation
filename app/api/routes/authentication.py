from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.database.session import get_db
from app.schemas.auth import UserLogin, UserCreate, UserResponse, TokenResponse
from app.services.auth_service import AuthService, get_current_user, require_roles
from app.models.user import User
from app.models.enums import UserRole

router = APIRouter(prefix="/api/v1/auth", tags=["Authentication & Staff Accounts"])


@router.post("/login", response_model=TokenResponse, summary="Staff User Login")
def login(credentials: UserLogin, db: Session = Depends(get_db)):
    """Authenticates staff members (Admin, Receptionist, Doctor) and returns a signed JWT."""
    user = AuthService.authenticate_user(db, credentials)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password."
        )
    return AuthService.create_user_token(user)


@router.post("/register", response_model=UserResponse, summary="Create Staff User (Admin Only)")
def register(
    user_in: UserCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles([UserRole.ADMIN]))
):
    """Registers a new staff user with designated role (Admin role required)."""
    return AuthService.register_user(db, user_in)


@router.get("/me", response_model=UserResponse, summary="Get Current Authenticated User")
def get_me(current_user: User = Depends(get_current_user)):
    """Returns details of the currently authenticated staff member."""
    return current_user
