# Stage 1: Base build stage
FROM python:3.14-slim AS builder

# Install nano and other packages
RUN apt-get update && apt-get install -y nano
 
# Create the app directory
RUN mkdir /app
 
# Set the working directory
WORKDIR /app
 
# Set environment variables to optimize Python
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1 
 
# Install dependencies first for caching benefit
RUN pip install --upgrade pip 
COPY requirements.txt /app/ 
RUN pip install --no-cache-dir -r requirements.txt
 
# Stage 2: Production stage
FROM python:3.14-slim
 
RUN useradd -m -r appuser && \
   mkdir /app && \
   mkdir /app/static && \
   mkdir /app/logs && \
   chown -R appuser /app
 
# Copy the Python dependencies from the builder stage
COPY --from=builder /usr/local/lib/python3.14/site-packages/ /usr/local/lib/python3.14/site-packages/
COPY --from=builder /usr/local/bin/ /usr/local/bin/
 
# Set the working directory
WORKDIR /app
 
# Copy application code
COPY --chown=appuser:appuser . .
 
# Set environment variables to optimize Python
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1 

# Make entry file executable
RUN chmod +rx  /app/entrypoint.prod.sh
 
# Switch to non-root user
USER appuser
 
# Expose the application port
EXPOSE 8000 

# Start the application using Gunicorn
CMD ["/app/entrypoint.prod.sh"]