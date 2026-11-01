# Multi-stage Dockerfile for React/Vite Frontend
FROM node:20-alpine AS builder

WORKDIR /app
COPY frontend/package.json ./
RUN npm install

COPY frontend/ ./
RUN npm run build

FROM nginx:alpine AS runner
COPY --from=builder /app/dist /usr/share/nginx/html

# Custom nginx configuration for SPA routing and API proxy
RUN echo 'server { \
    listen 80; \
    server_name localhost; \
    location / { \
        root /usr/share/nginx/html; \
        index index.html index.htm; \
        try_files $$uri $$uri/ /index.html; \
    } \
    location /api/ { \
        proxy_pass http://api:8000; \
        proxy_set_header Host $$host; \
        proxy_set_header X-Real-IP $$remote_addr; \
        proxy_set_header X-Forwarded-For $$proxy_add_x_forwarded_for; \
        proxy_set_header X-Forwarded-Proto $$scheme; \
        proxy_buffering off; \
        proxy_read_timeout 300s; \
    } \
}' > /etc/nginx/conf.d/default.conf

EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]

