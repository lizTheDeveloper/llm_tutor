#!/usr/bin/env python3
"""
Playwright test to verify the deployed CodeMentor application.
Tests both frontend and backend endpoints.
"""
import asyncio
from playwright.async_api import async_playwright
import json

BASE_URL = "http://35.209.246.229"

async def test_deployment():
    """Test the deployed application with Playwright."""
    async with async_playwright() as p:
        # Launch browser
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            viewport={'width': 1280, 'height': 720}
        )
        page = await context.new_page()

        print("\n=== Testing CodeMentor Deployment ===\n")

        # Test 1: Homepage loads
        print("1. Testing frontend homepage...")
        try:
            response = await page.goto(BASE_URL, wait_until='networkidle')
            assert response.status == 200, f"Expected 200, got {response.status}"
            await page.screenshot(path='screenshot-01-homepage.png')
            print("   ✓ Homepage loaded successfully")
            print("   📸 Screenshot: screenshot-01-homepage.png")
        except Exception as e:
            print(f"   ✗ Homepage failed: {e}")
            await page.screenshot(path='screenshot-01-homepage-error.png')

        # Test 2: Check page title
        print("\n2. Checking page title...")
        try:
            title = await page.title()
            print(f"   ✓ Page title: {title}")
        except Exception as e:
            print(f"   ✗ Could not get title: {e}")

        # Test 3: Check if React root div exists
        print("\n3. Checking React root element...")
        try:
            root = await page.query_selector('#root')
            assert root is not None, "React root div not found"
            print("   ✓ React root element found")
        except Exception as e:
            print(f"   ✗ React root check failed: {e}")

        # Test 4: Check for JavaScript execution
        print("\n4. Testing JavaScript execution...")
        try:
            # Wait a bit for React to render
            await page.wait_for_timeout(2000)
            await page.screenshot(path='screenshot-02-after-react-load.png')
            print("   ✓ Page rendered after JS execution")
            print("   📸 Screenshot: screenshot-02-after-react-load.png")
        except Exception as e:
            print(f"   ✗ JS execution check failed: {e}")

        # Test 5: Backend health endpoint
        print("\n5. Testing backend health endpoint...")
        try:
            health_response = await page.goto(f"{BASE_URL}/health")
            assert health_response.status == 200
            content = await page.content()
            health_data = json.loads(content.split('<pre>')[1].split('</pre>')[0] if '<pre>' in content else await page.evaluate('document.body.textContent'))
            print(f"   ✓ Health endpoint: {health_data}")
        except Exception as e:
            print(f"   ✗ Health endpoint failed: {e}")

        # Test 6: API health endpoint
        print("\n6. Testing API health endpoint...")
        try:
            api_response = await page.goto(f"{BASE_URL}/api/v1/health/")
            assert api_response.status == 200
            content = await page.content()
            # Extract JSON from the page
            if '<pre>' in content:
                api_data = json.loads(content.split('<pre>')[1].split('</pre>')[0])
            else:
                api_data = json.loads(await page.evaluate('document.body.textContent'))
            print(f"   ✓ API health: {api_data}")
        except Exception as e:
            print(f"   ✗ API health failed: {e}")

        # Test 7: Check for console errors
        print("\n7. Checking for console errors...")
        console_messages = []
        page.on('console', lambda msg: console_messages.append(msg))

        await page.goto(BASE_URL)
        await page.wait_for_timeout(3000)

        errors = [msg for msg in console_messages if msg.type == 'error']
        if errors:
            print(f"   ⚠ Found {len(errors)} console errors:")
            for error in errors[:5]:  # Show first 5
                print(f"      - {error.text}")
        else:
            print("   ✓ No console errors found")

        await page.screenshot(path='screenshot-03-final-state.png')
        print("\n   📸 Final screenshot: screenshot-03-final-state.png")

        # Close browser
        await browser.close()

        print("\n=== Deployment Test Complete ===\n")
        print("All screenshots saved in the current directory.")
        print("\nDeployment Summary:")
        print(f"  Frontend URL: {BASE_URL}")
        print(f"  Backend API: {BASE_URL}/api/v1/")
        print(f"  Health Check: {BASE_URL}/health")

if __name__ == '__main__':
    asyncio.run(test_deployment())
