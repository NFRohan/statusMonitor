from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from datetime import timedelta, datetime
from jose import JWTError, jwt
from typing import List
import secrets
import models, schemas, auth, database

database.Base.metadata.create_all(bind=database.engine)

app = FastAPI()

from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:5174"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def get_db():
    db = database.SessionLocal()
    try:
        yield db
    finally:
        db.close()

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

@app.post("/register", response_model=schemas.User)
def register(user: schemas.UserCreate, db: Session = Depends(get_db)):
    db_user = db.query(models.User).filter(models.User.username == user.username).first()
    if db_user:
        raise HTTPException(status_code=400, detail="Username already registered")
    hashed_password = auth.get_password_hash(user.password)
    db_user = models.User(username=user.username, password_hash=hashed_password)
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user

@app.post("/token", response_model=schemas.Token)
def login_for_access_token(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    print(f"DEBUG: Login attempt for username='{form_data.username}' password='{form_data.password}'")
    user = db.query(models.User).filter(models.User.username == form_data.username).first()
    if not user or not auth.verify_password(form_data.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    access_token_expires = timedelta(minutes=auth.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = auth.create_access_token(
        data={"sub": user.username}, expires_delta=access_token_expires
    )
    refresh_token_expires = timedelta(days=auth.REFRESH_TOKEN_EXPIRE_DAYS)
    refresh_token, jti, expire = auth.create_refresh_token(
        data={"sub": user.username}, expires_delta=refresh_token_expires
    )
    
    # Store refresh token in DB
    db_refresh_token = models.RefreshToken(
        jti=jti,
        user_id=user.id,
        expires_at=expire,
        revoked=False
    )
    db.add(db_refresh_token)
    db.commit()
    
    return {"access_token": access_token, "refresh_token": refresh_token, "token_type": "bearer"}

@app.post("/refresh", response_model=schemas.Token)
def refresh_token(refresh_token: str, db: Session = Depends(get_db)):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(refresh_token, auth.SECRET_KEY, algorithms=[auth.ALGORITHM])
        username: str = payload.get("sub")
        token_type: str = payload.get("type")
        jti: str = payload.get("jti")
        
        if username is None or token_type != "refresh" or jti is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception
    
    # Check DB for revocation
    db_token = db.query(models.RefreshToken).filter(models.RefreshToken.jti == jti).first()
    if not db_token:
        # Token not found (maybe deleted or forged)
        raise credentials_exception
    
    if db_token.revoked:
        # Token revoked - potential reuse attack!
        raise credentials_exception
        
    # Revoke the old token (Rotation)
    db_token.revoked = True
    db.add(db_token)
    db.commit()
    
    # Create new access token
    access_token_expires = timedelta(minutes=auth.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = auth.create_access_token(
        data={"sub": username}, expires_delta=access_token_expires
    )
    
    # Create new refresh token
    refresh_token_expires = timedelta(days=auth.REFRESH_TOKEN_EXPIRE_DAYS)
    new_refresh_token, new_jti, new_expire = auth.create_refresh_token(
        data={"sub": username}, expires_delta=refresh_token_expires
    )
    
    # Store new refresh token
    user = db.query(models.User).filter(models.User.username == username).first()
    new_db_token = models.RefreshToken(
        jti=new_jti,
        user_id=user.id,
        expires_at=new_expire,
        revoked=False
    )
    db.add(new_db_token)
    db.commit()
    
    return {"access_token": access_token, "refresh_token": new_refresh_token, "token_type": "bearer"}

@app.post("/logout")
def logout(refresh_token: str, db: Session = Depends(get_db)):
    try:
        payload = jwt.decode(refresh_token, auth.SECRET_KEY, algorithms=[auth.ALGORITHM])
        jti: str = payload.get("jti")
        if jti:
            db_token = db.query(models.RefreshToken).filter(models.RefreshToken.jti == jti).first()
            if db_token:
                db_token.revoked = True
                db.add(db_token)
                db.commit()
    except JWTError:
        pass # Ignore invalid tokens on logout
    return {"message": "Logged out successfully"}

@app.get("/users/me", response_model=schemas.User)
async def read_users_me(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, auth.SECRET_KEY, algorithms=[auth.ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception
        token_data = schemas.TokenData(username=username)
    except JWTError:
        raise credentials_exception
    user = db.query(models.User).filter(models.User.username == token_data.username).first()
    if user is None:
        raise credentials_exception
    return user

# Helper function to get current user from token
async def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, auth.SECRET_KEY, algorithms=[auth.ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception
    user = db.query(models.User).filter(models.User.username == username).first()
    if user is None:
        raise credentials_exception
    return user

# Agent endpoints
@app.post("/agents", response_model=schemas.AgentResponse)
async def create_agent(
    agent: schemas.AgentCreate,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Create a new agent and generate a unique token for it"""
    # Generate a unique token (32 bytes = 64 hex chars)
    agent_token = secrets.token_hex(32)
    
    db_agent = models.Agent(
        name=agent.name,
        token=agent_token,
        user_id=current_user.id,
        created_at=datetime.utcnow(),
        is_active=True
    )
    db.add(db_agent)
    db.commit()
    db.refresh(db_agent)
    return db_agent

@app.get("/agents", response_model=List[schemas.AgentListResponse])
async def list_agents(
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """List all agents belonging to the current user"""
    agents = db.query(models.Agent).filter(
        models.Agent.user_id == current_user.id,
        models.Agent.is_active == True
    ).all()
    return agents

@app.get("/agents/{agent_id}", response_model=schemas.AgentResponse)
async def get_agent(
    agent_id: int,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get a specific agent by ID"""
    agent = db.query(models.Agent).filter(
        models.Agent.id == agent_id,
        models.Agent.user_id == current_user.id
    ).first()
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    return agent

@app.delete("/agents/{agent_id}")
async def delete_agent(
    agent_id: int,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Delete (deactivate) an agent"""
    agent = db.query(models.Agent).filter(
        models.Agent.id == agent_id,
        models.Agent.user_id == current_user.id
    ).first()
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    
    agent.is_active = False
    db.commit()
    return {"message": "Agent deleted successfully"}

@app.post("/agents/{agent_id}/regenerate-token", response_model=schemas.AgentResponse)
async def regenerate_agent_token(
    agent_id: int,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Regenerate the token for an agent"""
    agent = db.query(models.Agent).filter(
        models.Agent.id == agent_id,
        models.Agent.user_id == current_user.id
    ).first()
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    
    agent.token = secrets.token_hex(32)
    db.commit()
    db.refresh(agent)
    return agent

# Endpoint for validating agent tokens (used by ingestion service)
@app.post("/agents/validate-token", response_model=schemas.AgentTokenValidation)
async def validate_agent_token(token: str, db: Session = Depends(get_db)):
    """Validate an agent token and return agent info"""
    agent = db.query(models.Agent).filter(
        models.Agent.token == token,
        models.Agent.is_active == True
    ).first()
    
    if not agent:
        return schemas.AgentTokenValidation(valid=False)
    
    # Update last_seen
    agent.last_seen = datetime.utcnow()
    db.commit()
    
    return schemas.AgentTokenValidation(
        valid=True,
        agent_id=agent.id,
        user_id=agent.user_id,
        agent_name=agent.name
    )

@app.get("/health")
def health():
    return {"status": "ok"}
