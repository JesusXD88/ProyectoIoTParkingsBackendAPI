import socket
from fastapi import FastAPI, Depends, HTTPException, status, WebSocket, WebSocketDisconnect, Request
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse, JSONResponse
from sqlalchemy.orm import Session
import crud, models, schemas, auth, database
from datetime import datetime, timedelta, UTC
from jose import jwt, JWTError

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

app = FastAPI()

templates = Jinja2Templates(directory="templates")

models.Base.metadata.create_all(bind=database.engine)

websockets_connections = []

@app.post("/token", response_model=schemas.Token)
async def login_for_access_token(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(database.get_db)):
    user = crud.get_user_by_username(db, username=form_data.username)
    if not user or not auth.verify_password(form_data.password, user.password):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Incorrect username or password", headers={"WWW-Authenticate": "Bearer"})

    access_token_expires = timedelta(minutes=auth.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = auth.create_access_token(data={"sub": user.username}, expires_delta=access_token_expires)
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
        payload = jwt.decode(token, auth.SECRET_KEY, algorithms=[auth.ALGORITHM])
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

@app.get("authcard")
async def authenticate_card(uid: str, current_user: schemas.User = Depends(get_current_active_user), db: Session = Depends(database.get_db)):
    card = crud.get_card_by_uid(db, uid)
    if card in card.authored_access and card.valid_from <= datetime.now(UTC) <= card.valid_to:
        return JSONResponse(content={"auth": "true"})
    return JSONResponse(content={"auth": "false"})

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket, token: str):
    try:
        payload = jwt.decode(token, auth.SECRET_KEY, algorithms=[auth.ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            await socket.close()
            return
        await websocket.accept()
        websockets_connections.append(websocket)
        while True:
            data = await websocket.receive_text()
            print(f"Mensaje recibido: {data}")
            message = schemas.Card.BurnResponse.parse_raw(data)

    except JWTError:
        await websocket.close()
    except WebSocketDisconnect:
        websockets_connections.remove(websocket)
        print("Cliente desconectado")

@app.get("/burncard")
async def burn_card_action(current_user: schemas.User = Depends(get_current_active_user)):
    if not current_user.is_admin:
        raise HTTPException(status_code=400, detail="Access forbidden")

    for websocket in websockets_connections:
        await websocket.send_text("CHANGE_KEY")
    return JSONResponse(content={"status": "burn card command sent"})

def handle_burn_response(message: schemas.BurnResponse):
    if message.burnSuccessful:
        print(f"Burn successful for card with uid {message.uid}")
    else:
        print(f"Burn failed")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8080)