#!/bin/sh
# Simplified permission script - Only setup container user group
echo "=== Container user group setup script starting ==="

# Ensure /app/images directory exists
if [ ! -d "/app/images" ]; then
    echo "Creating /app/images directory..."
    mkdir -p /app/images
fi

# Only setup container internal user group as appuser:appgroup (1000:1000)
echo "Setting container internal user group ownership (Uid:1000, Gid:1000)..."
chown -R appuser:appgroup /app/images 2>/dev/null && \
    echo "Container user group setup completed" || \
    echo "User group setup might be restricted, continuing application startup..."

echo "=== User group setup completed ==="