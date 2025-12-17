#!/bin/bash
# Vision API Tests using curl
# Based on OpenAI API documentation in docs/api/openai/

set -e

API_URL="http://localhost:8765/api/vision"
TEST_DIR="/Users/andrew/Projects/AGENTS/local_assistant/tests/api/test_files"

# Colors for output
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo "======================================"
echo "Vision API Tests"
echo "======================================"
echo ""

# Check if server is running
if ! curl -s "$API_URL/../health" > /dev/null 2>&1; then
    echo -e "${RED}ERROR: API server is not running at $API_URL${NC}"
    echo "Start the server with: uv run uvicorn api.main:app --host 0.0.0.0 --port 8765 --reload"
    exit 1
fi

echo -e "${GREEN}✓ Server is running${NC}"
echo ""

# Create test files directory if it doesn't exist
mkdir -p "$TEST_DIR"

# Test 1: Create a simple text image for testing
echo -e "${YELLOW}Test 1: Testing with simple text image${NC}"
echo "Creating test image..."

# Create a simple test PNG with text using base64
cat > "$TEST_DIR/test_simple.png" << 'EOF'
iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg==
EOF

# Test with structured extraction
echo "Testing structured extraction..."
RESPONSE=$(curl -s -X POST "$API_URL/extract" \
  -F "file=@$TEST_DIR/test_simple.png" \
  -F "extract_type=structured" \
  -F "detail=auto")

echo "Response: $RESPONSE"

if echo "$RESPONSE" | grep -q "content"; then
    echo -e "${GREEN}✓ Structured extraction test passed${NC}"
else
    echo -e "${RED}✗ Structured extraction test failed${NC}"
    echo "Response: $RESPONSE"
fi
echo ""

# Test 2: Test OCR extraction
echo -e "${YELLOW}Test 2: Testing OCR extraction${NC}"
RESPONSE=$(curl -s -X POST "$API_URL/extract" \
  -F "file=@$TEST_DIR/test_simple.png" \
  -F "extract_type=ocr" \
  -F "detail=low")

echo "Response: $RESPONSE"

if echo "$RESPONSE" | grep -q "content"; then
    echo -e "${GREEN}✓ OCR extraction test passed${NC}"
else
    echo -e "${RED}✗ OCR extraction test failed${NC}"
fi
echo ""

# Test 3: Test table extraction
echo -e "${YELLOW}Test 3: Testing table extraction${NC}"
RESPONSE=$(curl -s -X POST "$API_URL/extract" \
  -F "file=@$TEST_DIR/test_simple.png" \
  -F "extract_type=tables" \
  -F "detail=high")

echo "Response: $RESPONSE"

if echo "$RESPONSE" | grep -q "content"; then
    echo -e "${GREEN}✓ Table extraction test passed${NC}"
else
    echo -e "${RED}✗ Table extraction test failed${NC}"
fi
echo ""

# Test 4: Test invoice extraction (structured output)
echo -e "${YELLOW}Test 4: Testing invoice extraction with structured output${NC}"
RESPONSE=$(curl -s -X POST "$API_URL/extract" \
  -F "file=@$TEST_DIR/test_simple.png" \
  -F "extract_type=invoice" \
  -F "detail=high" \
  -F "model=gpt-4o")

echo "Response: $RESPONSE"

if echo "$RESPONSE" | grep -q "content"; then
    echo -e "${GREEN}✓ Invoice extraction test passed${NC}"

    # Check if response includes cost and model
    if echo "$RESPONSE" | grep -q '"cost"' && echo "$RESPONSE" | grep -q '"model"'; then
        echo -e "${GREEN}✓ Response includes cost and model information${NC}"
    fi
else
    echo -e "${RED}✗ Invoice extraction test failed${NC}"
fi
echo ""

# Test 5: Test error handling - missing file
echo -e "${YELLOW}Test 5: Testing error handling - missing file${NC}"
RESPONSE=$(curl -s -X POST "$API_URL/extract" \
  -F "extract_type=structured" \
  -F "detail=auto")

echo "Response: $RESPONSE"

if echo "$RESPONSE" | grep -q "detail"; then
    echo -e "${GREEN}✓ Error handling test passed (missing file)${NC}"
else
    echo -e "${RED}✗ Error handling test failed${NC}"
fi
echo ""

# Test 6: Test error handling - unsupported file type
echo -e "${YELLOW}Test 6: Testing error handling - unsupported file type${NC}"

# Create a text file
echo "This is a test file" > "$TEST_DIR/test.txt"

RESPONSE=$(curl -s -X POST "$API_URL/extract" \
  -F "file=@$TEST_DIR/test.txt" \
  -F "extract_type=structured" \
  -F "detail=auto")

echo "Response: $RESPONSE"

if echo "$RESPONSE" | grep -q "Unsupported format"; then
    echo -e "${GREEN}✓ Error handling test passed (unsupported file type)${NC}"
else
    echo -e "${RED}✗ Error handling test failed${NC}"
fi
echo ""

# Test 7: Test with different detail levels
echo -e "${YELLOW}Test 7: Testing different detail levels${NC}"
for detail in "low" "auto" "high"; do
    echo "Testing with detail=$detail..."
    RESPONSE=$(curl -s -X POST "$API_URL/extract" \
      -F "file=@$TEST_DIR/test_simple.png" \
      -F "extract_type=structured" \
      -F "detail=$detail")

    if echo "$RESPONSE" | grep -q "content"; then
        echo -e "${GREEN}✓ Detail level $detail test passed${NC}"
    else
        echo -e "${RED}✗ Detail level $detail test failed${NC}"
    fi
done
echo ""

# Cleanup
echo "Cleaning up test files..."
rm -rf "$TEST_DIR"

echo ""
echo "======================================"
echo "All tests completed!"
echo "======================================"
