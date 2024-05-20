# Użyj oficjalnego obrazu Python jako bazowego
FROM python:3.9

# Ustaw katalog roboczy
WORKDIR /app

# Skopiuj plik requirements.txt do kontenera
COPY requirements.txt .

# Zainstaluj wymagane pakiety
RUN pip install --no-cache-dir -r requirements.txt

# Skopiuj pozostałe pliki aplikacji do kontenera
COPY . .

# Expose port 80
EXPOSE 80

# Uruchom aplikację FastAPI na porcie 80
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "80"]
