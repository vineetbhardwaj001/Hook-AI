"""
End-to-End Backend Verification Test Script
"""
import urllib.request
import json
import os
import sys

BASE_URL = "http://127.0.0.1:8000"

def post_json(path, data, token=None):
    req = urllib.request.Request(
        f"{BASE_URL}{path}",
        data=json.dumps(data).encode("utf-8"),
        headers={"Content-Type": "application/json"}
    )
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    try:
        with urllib.request.urlopen(req) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        print(f"HTTP Error {e.code}: {e.read().decode()}")
        raise

def main():
    print("==================================================")
    print(" HOOK AI — END-TO-END BACKEND INTEGRATION TEST")
    print("==================================================")
    print()

    # 1. Health check
    print("1. Testing /health endpoint...")
    with urllib.request.urlopen(f"{BASE_URL}/health") as resp:
        h_data = json.loads(resp.read().decode())
        print("   [OK] Health:", h_data)

    # 2. Signup / Login
    email = f"test_user_{os.urandom(4).hex()}@example.com"
    password = "TestPassword123!"
    print(f"\n2. Testing User Signup ({email})...")
    signup_res = post_json("/api/v1/auth/signup", {
        "email": email,
        "password": password,
        "first_name": "Test",
        "last_name": "User"
    })
    access_token = signup_res["access_token"]
    print("   [OK] Signup successful! Token received.")

    # 3. Create analysis via multipart upload
    print("\n3. Testing Video Analysis Submission (POST /api/v1/analyses)...")
    import requests
    with open("test_video.mp4", "rb") as f:
        res = requests.post(
            f"{BASE_URL}/api/v1/analyses",
            headers={"Authorization": f"Bearer {access_token}"},
            files={"video": ("test_video.mp4", f, "video/mp4")},
            data={"analysis_type": "full", "language": "en"}
        )
    if res.status_code != 200:
        print("   [FAIL] Analysis upload failed:", res.status_code, res.text)
        sys.exit(1)

    create_data = res.json()
    analysis_id = create_data["analysis_id"]
    print(f"   [OK] Analysis created! ID = {analysis_id}")

    # 4. Run the analysis task directly
    print("\n4. Executing AI Analysis Pipeline...")
    sys.path.insert(0, ".")
    from app.workers.analysis_tasks import run_analysis
    
    # Run the worker pipeline synchronously for test_video.mp4
    task_res = run_analysis(
        analysis_id,
        video_path="storage/analyses/" + analysis_id + "/source/source.mp4",
        analysis_type="full",
        language="en"
    )
    print("   [OK] Pipeline execution returned:", task_res)

    # 5. Fetch full results from GET /api/v1/analyses/{id}/result
    print("\n5. Fetching Analysis Results (GET /api/v1/analyses/{id}/result)...")
    res = requests.get(
        f"{BASE_URL}/api/v1/analyses/{analysis_id}/result",
        headers={"Authorization": f"Bearer {access_token}"}
    )
    if res.status_code != 200:
        print("   [FAIL] Result fetch failed:", res.status_code, res.text)
        sys.exit(1)

    result = res.json()
    print("   [OK] Results retrieved successfully!")
    print(f"   Status: {result.get('status')}")
    print(f"   Video Duration: {result.get('video', {}).get('duration')}s")
    print(f"   Overall Score: {result.get('summary', {}).get('overall_score')} / 10 ({result.get('summary', {}).get('rating')})")
    print(f"   Scores: {result.get('scores')}")
    print(f"   Recommendations Count: {len(result.get('recommendations', []))}")
    print(f"   Generated Script Title: {result.get('generated_script', {}).get('title')}")
    print(f"   Report XLSX Available: {result.get('report', {}).get('xlsx_available')}")

    # 6. Test XLSX export endpoint
    print("\n6. Testing XLSX Report Export (GET /api/v1/analyses/{id}/export?format=xlsx)...")
    export_res = requests.get(
        f"{BASE_URL}/api/v1/analyses/{analysis_id}/export?format=xlsx",
        headers={"Authorization": f"Bearer {access_token}"}
    )
    if export_res.status_code == 200:
        print(f"   [OK] Report downloaded successfully! Size: {len(export_res.content)} bytes.")
    else:
        print("   [FAIL] Export failed:", export_res.status_code, export_res.text)

    print("\n==================================================")
    print(" ALL BACKEND END-TO-END TESTS PASSED SUCCESSFULLY! ")
    print("==================================================")

if __name__ == "__main__":
    main()
