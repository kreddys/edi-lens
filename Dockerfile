# Dockerfile

# --- Stage 1: Build the React application ---
FROM node:18-alpine AS builder

# Set working directory
WORKDIR /app

# Copy package files and install dependencies
# Use `npm ci` for faster, deterministic installs in CI/build environments
COPY package.json package-lock.json ./
RUN npm ci

# Copy the rest of the application source code
COPY . .

# Build the application
# This runs the "build" script defined in your package.json
RUN npm run build

# --- Stage 2: Serve the built application with Nginx ---
FROM nginx:stable-alpine

# Copy built assets from the 'builder' stage
# The `npm run build` command outputs to the 'dist' directory
COPY --from=builder /app/dist /usr/share/nginx/html

# Copy the custom Nginx configuration
COPY nginx.conf /etc/nginx/nginx.conf

# Expose port 8080 (the port Nginx is configured to listen on)
EXPOSE 8080

# Command to run Nginx in the foreground when the container starts
# 'daemon off;' ensures Nginx stays in the foreground, required by Docker/Fly.io
CMD ["nginx", "-g", "daemon off;"]