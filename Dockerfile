FROM python:3.10-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Порт веб-интерфейса Streamlit
EXPOSE 8501
# Порт телеметрии F1 2020
EXPOSE 20777/udp

# Точка входа для интерфейса
CMD ["streamlit", "run", "src/dashboard.py", "--server.address=0.0.0.0"]