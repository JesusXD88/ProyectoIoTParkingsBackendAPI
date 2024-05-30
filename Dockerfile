FROM python:3.12-alpine
LABEL authors="jesusxd88"

# Definir el directorio de trabajo
WORKDIR /app

# Copiar el archivo de dependencias
COPY requirements.txt .

# Instalar las dependencias
RUN pip install --no-cache-dir -r requirements.txt

# Copiar el proyecto al directorio de trabajo
COPY . .

# Exponer el puerto 8000
EXPOSE 8000

# Ejecutar la aplicacion

CMD ["python", "main.py"]