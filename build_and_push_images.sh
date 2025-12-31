#!/bin/bash
# Script to build and push Docker images to your Docker Hub account
# Usage: ./build_and_push_images.sh [instance_id1] [instance_id2] ...
# If no arguments provided, builds all missing images from the 21 test instances

set -e

DOCKERHUB_USER="${DOCKERHUB_USER:-jhmblundin}"
REPO_NAME="sweap-images"
DOCKERFILE_DIR="dockerfiles/instance_dockerfile"

# Function to convert instance_id to Docker Hub tag
# Format: {org}.{repo}-{instance_id_without_prefix}
# Example: nodebb.nodebb-NodeBB__NodeBB-abc123-vdef456
get_docker_tag() {
    local instance_id="$1"
    
    # Remove "instance_" prefix
    local without_prefix="${instance_id#instance_}"
    
    # Extract org__repo part (e.g., "NodeBB__NodeBB" from "NodeBB__NodeBB-abc123")
    local org_repo_part=$(echo "$without_prefix" | sed 's/-[a-f0-9]*.*$//' | sed 's/__.*$//')
    
    # Convert to lowercase for the prefix
    local org_lower=$(echo "$org_repo_part" | tr '[:upper:]' '[:lower:]')
    
    # For repos like "element-hq" we need to handle the dash
    # The format is: org.repo-FullInstanceId
    # Extract from the instance_id pattern: instance_{org}__{repo}-{hash}-{version}
    local full_pattern=$(echo "$without_prefix" | sed 's/__/./1' | sed 's/__/-/g')
    
    # Simpler approach: just use the pattern from the working images
    # {org}.{repo}-{org}__{repo}-{hash}[-{version}]
    local org=$(echo "$without_prefix" | cut -d'_' -f1 | tr '[:upper:]' '[:lower:]')
    local repo=$(echo "$without_prefix" | sed 's/^[^_]*__//' | cut -d'-' -f1 | tr '[:upper:]' '[:lower:]')
    
    echo "${org}.${repo}-${without_prefix}"
}

# Function to build and push a single image
build_and_push() {
    local instance_id="$1"
    local dockerfile_path="$DOCKERFILE_DIR/$instance_id/Dockerfile"
    
    if [ ! -f "$dockerfile_path" ]; then
        echo "❌ Dockerfile not found: $dockerfile_path"
        return 1
    fi
    
    local tag=$(get_docker_tag "$instance_id")
    local full_image="$DOCKERHUB_USER/$REPO_NAME:$tag"
    
    echo "=============================================="
    echo "Building: $instance_id"
    echo "Tag: $full_image"
    echo "=============================================="
    
    # Build the image
    docker build -t "$full_image" \
        -f "$dockerfile_path" \
        "$DOCKERFILE_DIR/$instance_id/"
    
    # Push to Docker Hub
    echo "Pushing to Docker Hub..."
    docker push "$full_image"
    
    echo "✅ Successfully pushed: $full_image"
    echo ""
}

# Default list of missing images from the 21 test instances
DEFAULT_MISSING=(
    "instance_qutebrowser__qutebrowser-9ed748effa8f3bcd804612d9291da017b514e12f-v363c8a7e5ccdf6968fc7ab84a2053ac78036691d"
    "instance_qutebrowser__qutebrowser-77c3557995704a683cdb67e2a3055f7547fa22c3-v363c8a7e5ccdf6968fc7ab84a2053ac78036691d"
    "instance_internetarchive__openlibrary-53e02a22972e9253aeded0e1981e6845e1e521fe-vfa6ff903cb27f336e17654595dd900fa943dcd91"
    "instance_internetarchive__openlibrary-7cbfb812ef0e1f9716e2d6e85d538a96fcb79d13-vfa6ff903cb27f336e17654595dd900fa943dcd91"
    "instance_internetarchive__openlibrary-fad4a40acf5ff5f06cd7441a5c7baf41a7d81fe4-vfa6ff903cb27f336e17654595dd900fa943dcd91"
    "instance_element-hq__element-web-b007ea81b2ccd001b00f332bee65070aa7fc00f9-vnan"
    "instance_element-hq__element-web-33e8edb3d508d6eefb354819ca693b7accc695e7"
    "instance_NodeBB__NodeBB-4327a09d76f10a79109da9d91c22120428d3bdb9-vnan"
)

# Main logic
echo "Docker Hub User: $DOCKERHUB_USER"
echo "Repository: $REPO_NAME"
echo ""

# Check if docker is running
if ! docker info > /dev/null 2>&1; then
    echo "❌ Docker is not running. Please start Docker first."
    exit 1
fi

# Check if logged in to Docker Hub
echo "Checking Docker Hub login..."
if ! docker info 2>/dev/null | grep -q "Username"; then
    echo "⚠️  You may need to login to Docker Hub first:"
    echo "   docker login"
    echo ""
fi

if [ $# -eq 0 ]; then
    echo "No arguments provided. Building default missing images..."
    echo "Total images to build: ${#DEFAULT_MISSING[@]}"
    echo ""
    
    for instance_id in "${DEFAULT_MISSING[@]}"; do
        build_and_push "$instance_id"
    done
else
    echo "Building specified images..."
    echo "Total images to build: $#"
    echo ""
    
    for instance_id in "$@"; do
        build_and_push "$instance_id"
    done
fi

echo "=============================================="
echo "✅ All images built and pushed successfully!"
echo "=============================================="
