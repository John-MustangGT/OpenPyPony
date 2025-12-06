#!/bin/bash
# OpenPonyLogger - Canvas-Gauges Download Helper
# This script downloads the canvas-gauges library for offline use

echo "=========================================="
echo "OpenPonyLogger - Gauge Library Downloader"
echo "=========================================="
echo ""

# Check if curl is available
if ! command -v curl &> /dev/null; then
    echo "❌ curl not found. Please install curl or download manually:"
    echo "   https://cdn.rawgit.com/Mikhus/canvas-gauges/gh-pages/download/2.1.7/all/gauge.min.js"
    exit 1
fi

# Download from GitHub releases
echo "📦 Downloading canvas-gauges library..."
echo "   Source: GitHub Releases (v2.1.7)"
echo ""

curl -L -o gauge.min.js \
     https://cdn.rawgit.com/Mikhus/canvas-gauges/gh-pages/download/2.1.7/all/gauge.min.js

if [ $? -eq 0 ]; then
    # Verify file was downloaded
    if [ -f "gauge.min.js" ]; then
        SIZE=$(ls -lh gauge.min.js | awk '{print $5}')
        echo ""
        echo "✅ Download successful!"
        echo "   File: gauge.min.js"
        echo "   Size: $SIZE"
        echo ""
        echo "📁 File placement:"
        echo "   Place gauge.min.js in the same directory as index.html"
        echo ""
        echo "🧪 Test offline operation:"
        echo "   1. Disconnect from internet"
        echo "   2. Open index.html in browser"
        echo "   3. Verify all gauges display"
        echo ""
        echo "✓ Ready for offline deployment!"
    else
        echo "❌ Download failed - file not found"
        exit 1
    fi
else
    echo "❌ Download failed"
    echo ""
    echo "Alternative methods:"
    echo "1. Manual download:"
    echo "   https://cdn.rawgit.com/Mikhus/canvas-gauges/gh-pages/download/2.1.7/all/gauge.min.js"
    echo ""
    echo "2. Using wget:"
    echo "   wget -O gauge.min.js https://cdn.rawgit.com/Mikhus/canvas-gauges/gh-pages/download/2.1.7/all/gauge.min.js"
    echo ""
    echo "3. Using NPM:"
    echo "   npm install canvas-gauges"
    echo "   cp node_modules/canvas-gauges/gauge.min.js ./"
    exit 1
fi
