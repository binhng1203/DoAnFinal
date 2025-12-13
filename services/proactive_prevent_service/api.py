# File: api_server.py
from flask import Flask, request, jsonify
from flask_cors import CORS
from proactive_fault_prevention.main_processor import process_analysis_request
from proactive_fault_prevention import data_fetcher

app = Flask(__name__)
CORS(app)

@app.route('/proactive', methods=['POST'])
def analyze_endpoint():
    try:
        req_data = request.json
        if not req_data:
            return jsonify({"error": "Empty payload"}), 400

        project_id = req_data.get("project_id")
        case_id = req_data.get("case_id")
        head_sha = req_data.get("head_sha")
        base_sha = req_data.get("base_sha")

        if project_id and case_id:
            print(f"INFO: DB-fetching data for Project {project_id}, Case {case_id}")
            
            # 1. Lấy Git URL
            git_url = data_fetcher.get_project_repo_url(project_id)
            if not git_url:
                return jsonify({"error": "Could not find Repo URL in DB"}), 404
            
            # 2. Lấy Testcase Detail (Bao gồm Steps)
            testcase_info = data_fetcher.get_testcase_details(case_id)
            
            # [CHECK] Đảm bảo có steps
            if not testcase_info.get("steps"):
                print("WARNING: Test case has no steps in DB.")

            full_payload = {
                "git_url": git_url,
                "head_sha": head_sha,
                "base_sha": base_sha,
                "project_id": project_id,
                "case_id": case_id,
                "testcase": testcase_info, # Đã chứa steps bên trong
                "author": req_data.get("author", "system")
            }
        else:
            full_payload = req_data

        print(f"INFO: Processing analysis for: {full_payload.get('git_url')}")
        result = process_analysis_request(full_payload)
        
        return jsonify(result), 200

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"status": "ERROR", "message": str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8000, debug=True)