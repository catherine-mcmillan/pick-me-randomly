FROM python:3.12-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first to leverage Docker cache
COPY requirements.txt .
RUN pip install -r requirements.txt

# Copy the rest of the application
COPY . .

# Create a startup script
RUN echo '#!/bin/bash\n\
    echo "Waiting for database..."\n\
    while ! pg_isready -h $DATABASE_HOST -p $DATABASE_PORT -U $DATABASE_USER; do\n\
    sleep 1\n\
    done\n\
    echo "Database is ready!"\n\
    python -c "import psycopg2; conn = psycopg2.connect(\"$DATABASE_URL\"); conn.close()"\n\
    streamlit run app.py --logger.level=DEBUG' > /app/start.sh && \
    chmod +x /app/start.sh

# Expose the port the app runs on
EXPOSE 8501

# Command to run the application
CMD ["/app/start.sh"] 