from src.extensions import mongo
from bson import ObjectId
import re

class AnalysisService:
    
    @staticmethod
    def get_analysis_list(test_id, page=1, limit=10):
        """
        RS_03: Lấy danh sách analysis của 1 testcase
        """
        skip = (page - 1) * limit
        collection = mongo.db.analysis_logs  # Giả định tên collection là analysis_logs
        
        # BR3.1: Map test_id sang tên file path hoặc test function name
        # Sử dụng Regex để tìm chuỗi test_id xuất hiện trong mảng predicted_failed_tests
        # $options: 'i' để không phân biệt hoa thường
        query = {
            "analysis_details.predicted_failed_tests": {
                "$regex": re.escape(test_id), 
                "$options": "i"
            }
        }

        # Projection: Chỉ lấy các trường cần thiết (Tối ưu performance)
        projection = {
            "pr": 1,
            "status": 1,
            "confidence": 1,
            "timestamps.start": 1,
            "_id": 1
        }

        # BR3.3: Sắp xếp theo timestamps.start DESC
        cursor = collection.find(query, projection)\
                           .sort("timestamps.start", -1)\
                           .skip(skip)\
                           .limit(limit)
        
        total_count = collection.count_documents(query)
        
        results = []
        for doc in cursor:
            # BR3.2: Format dữ liệu hiển thị
            results.append({
                "id": str(doc["_id"]),
                "pr_number": doc.get("pr", {}).get("number"),
                "author": doc.get("pr", {}).get("author"),
                "commit_msg": doc.get("pr", {}).get("title", ""), # Nếu có lưu title
                "status": doc.get("status"),
                "confidence_score": doc.get("confidence", {}).get("score"),
                "started_at": doc.get("timestamps", {}).get("start")
            })
            
        return results, total_count

    @staticmethod
    def get_analysis_detail(analysis_id, test_id_filter=None):
        """
        RS_04: Xem chi tiết 1 analysis và lọc nội dung theo test_id
        """
        collection = mongo.db.analysis_logs
        
        try:
            oid = ObjectId(analysis_id)
        except:
            return None # ID không hợp lệ

        # BR4.1: Truy vấn MongoDB theo _id
        doc = collection.find_one({"_id": oid})
        if not doc:
            return None

        # Format cấu trúc dữ liệu trả về
        response = {
            "id": str(doc["_id"]),
            "pr_info": doc.get("pr"),
            "status": doc.get("status"),
            "timestamps": doc.get("timestamps"),
            "ui_changes": doc.get("ui_changes", []),
            "analysis_details": {
                "predicted_failed_tests": doc.get("analysis_details", {}).get("predicted_failed_tests", []),
                "match_details": [] # Sẽ xử lý ở dưới
            },
            "confidence": doc.get("confidence")
        }

        # BR4.2 & BR4.3: Lọc match_details theo test_id (nếu có)
        raw_matches = doc.get("analysis_details", {}).get("match_details", [])
        
        filtered_matches = []
        if test_id_filter:
            for match in raw_matches:
                # Lấy thông tin locator test case trong DB
                # Cấu trúc DB: locator: { test_case: "test_login_button_is_visible", ... }
                locator_test_case = match.get("locator", {}).get("test_case", "")
                
                # So sánh tương đối (contains)
                if test_id_filter.lower() in locator_test_case.lower():
                    filtered_matches.append(match)
        else:
            filtered_matches = raw_matches # Nếu không truyền test_id thì lấy hết

        response["analysis_details"]["match_details"] = filtered_matches

        return response