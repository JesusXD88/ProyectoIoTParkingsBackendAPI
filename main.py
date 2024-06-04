import socket
from typing import Optional, List
from fastapi import FastAPI, Depends, HTTPException, status, WebSocket, WebSocketDisconnect, Request, Query, Body, Form
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from auth import Auth
import crud, models, schemas, database, connmanager
from datetime import datetime, timedelta, timezone
from jose import jwt, JWTError

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

app = FastAPI()

templates = Jinja2Templates(directory="templates")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

models.Base.metadata.create_all(bind=database.engine)

manager = connmanager.ConnectionManager()

burn_data = {}

blacklisted_tokens = []

barrier_open_time = 10

burn_status = {}


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
    except JWTError:
        raise credentials_exception
    user = crud.get_user_by_username(db, username=username)
    if user is None:
        raise credentials_exception
    return user

async def get_current_active_user(current_user: schemas.User = Depends(get_current_user), token: str = Depends(oauth2_scheme)):
    if not current_user.is_active:
        raise HTTPException(status_code=400, detail="Inactive user")

    if token in blacklisted_tokens:
        raise HTTPException(status_code=400, detail="Token blacklisted")

    return current_user

@app.post("/logout")
async def logout(current_user: schemas.User = Depends(get_current_active_user), token: str = Depends(oauth2_scheme)):
    # Logout user from session
    blacklisted_tokens.append(token)
    return {"status": "logout successful"}

@app.get("/", response_class=HTMLResponse)
async def read_root(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})

@app.get("/dashboard", response_class=HTMLResponse)
async def read_dashboard(request: Request):
    return templates.TemplateResponse("dashboard.html", {"request": request})

@app.get("/authcard")
async def authenticate_card(uid: str, db: Session = Depends(database.get_db)):
    card = crud.get_card_by_uid(db, uid)
    current_time = datetime.now(timezone.utc)
    if card.authored_access and card.valid_from.replace(tzinfo=timezone.utc) <= current_time <= card.valid_to.replace(tzinfo=timezone.utc):
        return JSONResponse(content={"auth": True, "barrier_open_sec": barrier_open_time})
    return JSONResponse(content={"auth": False, "barrier_open_sec": barrier_open_time})


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket, token: str = Query(None), db: Session = Depends(database.get_db)):
    if token is None:
        print(f"Token invalido: {token}")
        await websocket.close(code=1008)
        return

    try:
        payload = jwt.decode(token, Auth.SECRET_KEY, algorithms=[Auth.ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            await socket.close()
            return
        await manager.connect(websocket)
        while True:
            data = await websocket.receive_text()
            print(f"Mensaje recibido: {data}")
            message = schemas.BurnResponse.parse_raw(data)
            handle_burn_response(message, db)
            await manager.broadcast(f"Message was: {data}")

    except JWTError:
        print("Error token")
        await websocket.close()
    except WebSocketDisconnect:
        manager.disconnect(websocket)
        print("Cliente desconectado")

@app.post("/burncard")
async def burn_card_action(current_user: schemas.User = Depends(get_current_active_user), authored_access: bool = Form(...), valid_from: datetime = Form(...), valid_to: Optional[datetime] = Form(None), db: Session = Depends(database.get_db)):
    if not current_user.is_admin:
        raise HTTPException(status_code=400, detail="Access forbidden")

    burn_data["authored_access"] = authored_access
    burn_data["valid_from"] = valid_from.replace(tzinfo=timezone.utc)
    burn_data["valid_to"] = valid_to.replace(tzinfo=timezone.utc)

    for websocket in manager.active_connections:
        await websocket.send_text("BURN_CARD")

    return JSONResponse(content={"status": "burn card command sent"})

def handle_burn_response(message: schemas.BurnResponse, db: Session):

    global burn_status

    print(f"Message received: {message}")

    if message.burnSuccessful:
        db_card = crud.get_card_by_uid(db, uid=message.uid)
        if db_card:
            burn_status = {"status": "already_registered"}
            raise HTTPException(status_code=400, detail="Card already registered")

        card = schemas.CardCreate(uid=message.uid, authored_access=burn_data["authored_access"], valid_from=burn_data["valid_from"], valid_to=burn_data["valid_to"])

        crud.create_card(db=db, card=card)

        print(f"Burn successful for card with uid {message.uid}")

        burn_status = {"status": "success"}

    else:

        print(f"Burn failed")

        burn_status = {"status": "failed"}

@app.get("/burn_status")
async def burn_status_endpoint(user: schemas.User = Depends(get_current_active_user)):
    if not user.is_admin:
        raise HTTPException(status_code=400, detail="Access forbidden")

    print(f"Burn status: {burn_status}")
    return JSONResponse(content=burn_status)


@app.get("/cards/", response_model=List[schemas.Card])
async def read_cards(current_user: schemas.User = Depends(get_current_active_user), skip: int = 0, limit: int = 100, db: Session = Depends(database.get_db)):
    if not current_user.is_admin:
        raise HTTPException(status_code=400, detail="Access forbidden")

    cards = crud.get_cards(db, skip=skip, limit=limit)
    return cards


@app.patch("/update_card")
async def update_card(
        uid: str = Query(...),
        authored_access: bool = Body(...),
        valid_from: str = Body(None),
        valid_to: str = Body(None),
        db: Session = Depends(database.get_db),
        current_user: schemas.User = Depends(get_current_active_user)
):

    card = crud.get_card_by_uid(db, uid=uid)
    if not card:
        raise HTTPException(status_code=404, detail="Card not found")

    card.authored_access = authored_access
    if valid_from:
        card.valid_from = datetime.fromisoformat(valid_from)
    if valid_to:
        card.valid_to = datetime.fromisoformat(valid_to)

    db.commit()
    db.refresh(card)
    return JSONResponse(content={"status": "card updated successfully", "card": card_to_dict(card)})

def card_to_dict(card):
    return {
        "uid": card.uid,
        "authored_access": card.authored_access,
        "valid_from": card.valid_from.isoformat() if card.valid_from else None,
        "valid_to": card.valid_to.isoformat() if card.valid_to else None
    }

@app.delete("/delete_card/{uid}")
async def delete_card(uid: str, db: Session = Depends(database.get_db), current_user: schemas.User = Depends(get_current_active_user)):
    card = crud.get_card_by_uid(db, uid=uid)
    if not card:
        raise HTTPException(status_code=404, detail="Card not found")

    crud.delete_card(db, card)
    return JSONResponse(content={"status": "card deleted successfully"})

@app.post("/open_barrier")
async def open_barrier(current_user: schemas.User = Depends(get_current_user), db: Session = Depends(database.get_db)):
    await manager.broadcast(f"OPEN_BARRIER:{barrier_open_time}")
    return {"status": "Barrier opened", "barrier_open_time": barrier_open_time}

@app.post("/set_barrier_time")
async def set_barrier_time(open_sec: int = Body(...), current_user: schemas.User = Depends(get_current_active_user), db: Session = Depends(database.get_db)):
    print(open_sec)
    global barrier_open_time
    barrier_open_time = open_sec
    return {"status": "Barrier time set", "barrier_open_time": barrier_open_time}

async def handle_open_barrier():
    await manager.broadcast(f"OPEN_BARRIER:{barrier_open_time}")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)