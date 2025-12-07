# Create directory structure
mkdir -p web_visualization/static/{css,js,images}

# Create __init__.py
touch web_visualization/static/__init__.py

# Create placeholder files
echo "/* NovaMotion Core static files */" > web_visualization/static/css/style.css
echo "// NovaMotion Core JavaScript" > web_visualization/static/js/main.js
echo "<!-- Placeholder for favicon -->" > web_visualization/static/images/README.md