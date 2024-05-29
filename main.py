import socket
from typing import Optional
from fastapi import FastAPI, Depends, HTTPException, status, WebSocket, WebSocketDisconnect, Request, Query
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse, JSONResponse
from sqlalchemy.orm import Session
from auth import Auth
import crud, models, schemas, database, connmanager
from datetime import datetime, timedelta, timezone, UTC
from jose import jwt, JWTError

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

app = FastAPI()

templates = Jinja2Templates(directory="templates")

models.Base.metadata.create_all(bind=database.engine)

manager = connmanager.ConnectionManager()

burn_data = {}

@app.post("/token", response_model=schemas.Token)
async def login_for_access_token(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(database.get_db)):
    user = crud.get_user_by_username(db, username=form_data.username)
    if not user or not Auth.verify_password(form_data.password, user.password):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Incorrect username or password", headers={"WWW-Authenticate": "Bearer"})

    access_token_expires = timedelta(minutes=Auth.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = Auth.create_access_token(data={"sub": user.username}, expires_delta=access_token_expires)
    return {"access_token": access_token, "token_type": "bearer"}

@app.post("/users/", response_model=schemas.User)
async def create_user(user: schemas.UserCreate, db: Session = Depends(database.get_db)):
    db_user = crud.get_user_by_username(db, username=user.username)
    if db_user:
        raise HTTPException(status_code=400, detail="Username already registered")
    return crud.create_user(db=db, user=user)

async def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(database.get_db)):
    credentials_exception = HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Could not validate credentials", headers={"WWW-Authenticate": "Bearer"})
    try:
        payload = jwt.decode(token, Auth.SECRET_KEY, algorithms=[Auth.ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception
    except jwt.JWTError:
        raise credentials_exception
    user = crud.get_user_by_username(db, username=username)
    if user is None:
        raise credentials_exception
    return user

async def get_current_active_user(current_user: schemas.User = Depends(get_current_user)):
    if not current_user.is_active:
        raise HTTPException(status_code=400, detail="Inactive user")
    return current_user

@app.get("/", response_class=HTMLResponse)
async def read_root(request: Request, current_user: schemas.User = Depends(get_current_active_user)):
    return templates.TemplateResponse("index.html", {"request": request, "user": current_user})

@app.get("/authcard")
async def authenticate_card(uid: str, current_user: schemas.User = Depends(get_current_active_user), db: Session = Depends(database.get_db)):
    card = crud.get_card_by_uid(db, uid)
    current_time = datetime.now(timezone.utc)
    if card.authored_access and card.valid_from.replace(tzinfo=timezone.utc) <= current_time <= card.valid_to.replace(tzinfo=timezone.utc):
        return JSONResponse(content={"auth": True})
    return JSONResponse(content={"auth": False})

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket, token: str = Query(None), db: Session = Depends(database.get_db)):
    if token is None:
        print(f"Token invalido: {token}")
        await websocket.close(code=1008)
        return

    try:
        payload = jwt.decode(token, Auth.SECRET_KEY, algorithms=[Auth.ALGORITHM])
        #print(f"Payload: {payload}")
        username: str = payload.get("sub")
        if username is None:
            await socket.close()
            return
        await manager.connect(websocket)
        while True:
            data = await websocket.receive_text()
            print(f"Mensaje recibido: {data}")
            message = schemas.BurnResponse.parse_raw(data)
            if message.burnSuccessful:
                handle_burn_response(message, db)
            await manager.broadcast(f"Message was: {data}")

    except JWTError:
        print("Error token")
        await websocket.close()
    except WebSocketDisconnect:
        manager.disconnect(websocket)
        print("Cliente desconectado")

@app.get("/burncard")
async def burn_card_action(current_user: schemas.User = Depends(get_current_active_user), authored_access: bool = Query(...), valid_from: datetime = Query(...), valid_to: Optional[datetime] = Query(None), db: Session = Depends(database.get_db)):
    if not current_user.is_admin:
        raise HTTPException(status_code=400, detail="Access forbidden")

    burn_data["authored_access"] = authored_access
    burn_data["valid_from"] = valid_from.replace(tzinfo=timezone.utc)
    burn_data["valid_to"] = valid_to.replace(tzinfo=timezone.utc)

    for websocket in manager.active_connections:
        await websocket.send_text("BURN_CARD")

    return JSONResponse(content={"status": "burn card command sent"})

def handle_burn_response(message: schemas.BurnResponse, db: Session):
    if message.burnSuccessful:
        db_card = crud.get_card_by_uid(db, uid=message.uid)
        if db_card:
            raise HTTPException(status_code=400, detail="Card already registered")

        card = schemas.CardCreate(uid=message.uid, authored_access=burn_data["authored_access"], valid_from=burn_data["valid_from"], valid_to=burn_data["valid_to"])

        crud.create_card(db=db, card=card)

        print(f"Burn successful for card with uid {message.uid}")

    else:
        print(f"Burn failed")


@app.patch("/update_card")
async def update_card(uid: str, authored_access: Optional[bool] = None, valid_from: Optional[datetime] = None, valid_to: Optional[datetime] = None, current_user: schemas.User = Depends(get_current_active_user), db: Session = Depends(database.get_db)):
    if not current_user.is_admin:
        raise HTTPException(status_code=400, detail="Access forbidden")

    card = crud.get_card_by_uid(db, uid)
    if not card:
        raise HTTPException(status_code=400, detail="Card not found")

    if authored_access is not None:
        card.authored_access = authored_access
    if valid_from is not None:
        card.valid_from = valid_from.replace(tzinfo=timezone.utc)
    if valid_to is not None:
        card.valid_to = valid_to.replace(tzinfo=timezone.utc)

    db.commit()
    db.refresh(card)

    return JSONResponse(content={"status": "card updated successfully", "card": card_to_dict(card)})

def card_to_dict(card: models.Card):
    return {
        "id": card.id,
        "uid": card.uid,
        "authored_access": card.authored_access,
        "valid_from": card.valid_from.isoformat(),
        "valid_to": card.valid_to.isoformat() if card.valid_to else None,
        "created_at": card.created_at.isoformat()
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8080)