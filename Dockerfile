FROM python:3.10-alpine

COPY ./requirements.txt /app/requirements.txt

# Install dependencies with certificate verification
RUN apk --no-cache add build-base cargo curl make nginx rust supervisor && \
    mkdir -p /run/nginx && \
    mkdir -p /app && \
    pip install --upgrade pip && \
    pip install --no-cache-dir -r /app/requirements.txt && \
    echo "[supervisord]" > /etc/supervisord.conf && \
    echo "nodaemon=true" >> /etc/supervisord.conf && \
    echo "" >> /etc/supervisord.conf && \
    echo "[program:litellm]" >> /etc/supervisord.conf && \
    echo "command=python /app/main.py" >> /etc/supervisord.conf && \
    echo "directory=/app" >> /etc/supervisord.conf && \
    echo "autostart=true" >> /etc/supervisord.conf && \
    echo "autorestart=true" >> /etc/supervisord.conf && \
    echo "stdout_logfile=/dev/stdout" >> /etc/supervisord.conf && \
    echo "stdout_logfile_maxbytes=0" >> /etc/supervisord.conf && \
    echo "stderr_logfile=/dev/stderr" >> /etc/supervisord.conf && \
    echo "stderr_logfile_maxbytes=0" >> /etc/supervisord.conf && \
    echo "" >> /etc/supervisord.conf && \
    echo "[program:nginx]" >> /etc/supervisord.conf && \
    echo "command=nginx -g 'daemon off;'" >> /etc/supervisord.conf && \
    echo "autostart=true" >> /etc/supervisord.conf && \
    echo "autorestart=true" >> /etc/supervisord.conf && \
    echo "stdout_logfile=/dev/stdout" >> /etc/supervisord.conf && \
    echo "stdout_logfile_maxbytes=0" >> /etc/supervisord.conf && \
    echo "stderr_logfile=/dev/stderr" >> /etc/supervisord.conf && \
    echo "stderr_logfile_maxbytes=0" >> /etc/supervisord.conf && \
    echo "startretries=5" >> /etc/supervisord.conf && \
    echo "error_log /dev/stderr debug;" >> /etc/nginx/nginx.conf

    
COPY ./ /app/
COPY ./nginx.conf /etc/nginx/nginx.conf

EXPOSE 80

WORKDIR /app

# Start supervisord and run healthcheck after a delay
CMD ["sh", "-c", "supervisord -c /etc/supervisord.conf & sleep 30 && tail -f /dev/null"]
