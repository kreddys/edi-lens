# FILE: docker/admin-ui/Dockerfile
# Stage 1: Build the React app
FROM node:20-alpine AS build
WORKDIR /app

# Accept build arguments from docker-compose
ARG VITE_KEYCLOAK_URL
ARG VITE_KEYCLOAK_REALM
ARG VITE_KEYCLOAK_CLIENT_ID
ARG VITE_API_URL

# Set them as environment variables for the build process
ENV VITE_KEYCLOAK_URL=${VITE_KEYCLOAK_URL}
ENV VITE_KEYCLOAK_REALM=${VITE_KEYCLOAK_REALM}
ENV VITE_KEYCLOAK_CLIENT_ID=${VITE_KEYCLOAK_CLIENT_ID}
ENV VITE_API_URL=${VITE_API_URL}

# Copy dependency files from the admin-ui directory
COPY admin-ui/package*.json ./

RUN npm install

# Copy the entire admin-ui source code
COPY admin-ui/ .

RUN npm run build

# Stage 2: Serve the static files with Nginx
FROM nginx:stable-alpine
COPY --from=build /app/dist /usr/share/nginx/html
# Copy a default nginx config to handle SPA routing
COPY docker/admin-ui/nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]