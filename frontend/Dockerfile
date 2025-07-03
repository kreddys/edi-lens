# Stage 1: Build stage
FROM node:20-alpine as build

WORKDIR /app

# Copy package.json and lock file
COPY package.json package-lock.json* ./

# Install dependencies
RUN npm install

# Copy the rest of the application source code
COPY . .

# Build the application for production (optional, not used for dev server)
# RUN npm run build

# Stage 2: Development server stage
FROM node:20-alpine

WORKDIR /app

# Copy dependencies from build stage
COPY --from=build /app/node_modules ./node_modules
# Copy application source
COPY . .

EXPOSE 5173

# Run the Vite development server
# --host is crucial for Docker to expose the port correctly
CMD ["npm", "run", "dev", "--", "--host"]