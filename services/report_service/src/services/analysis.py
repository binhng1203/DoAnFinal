from src.extensions import mongo
from bson import ObjectId
import re

class AnalysisService:
    
    @staticmethod
    def get_analysis_list(case_id, page=1, limit=10):
        """
        RS_03: Lấy danh sách analysis của 1 testcase
        """
        skip = (page - 1) * limit
        collection = mongo.db.analysis_results  # Giả định tên collection là analysis_logs
        
        # BR3.1: Map test_id sang tên file path hoặc test function name
        # Sử dụng Regex để tìm chuỗi test_id xuất hiện trong mảng predicted_failed_tests
        # $options: 'i' để không phân biệt hoa thường
        query = {
            "pr.case_id": case_id
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
    def get_analysis_detail(analysis_id):
        """
        RS_04: Xem chi tiết 1 analysis theo ID
        """
        collection = mongo.db.analysis_results
        
        try:
            oid = ObjectId(analysis_id)
        except:
            return None # ID không hợp lệ

        # Tìm bản ghi theo _id
        doc = collection.find_one({"_id": oid})
        if not doc:
            return None

        # Format cấu trúc dữ liệu trả về
        response = {
            "id": str(doc["_id"]),
            "case_id": doc.get("case_id"),  # Trả về case_id để Frontend biết nó thuộc case nào
            "pr_info": doc.get("pr"),
            "status": doc.get("status"),
            "timestamps": doc.get("timestamps"),
            "ui_changes": doc.get("ui_changes", []),
            "analysis_details": {
                "predicted_failed_tests": doc.get("analysis_details", {}).get("predicted_failed_tests", []),
                # Lấy trực tiếp toàn bộ match_details, không cần lọc nữa
                "match_details": doc.get("analysis_details", {}).get("match_details", [])
            },
            "confidence": doc.get("confidence")
        }

        return response